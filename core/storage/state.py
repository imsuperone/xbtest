# -*- coding: utf-8 -*-
"""storage/state.py — 共享态唯一家：锁/连接/缓存/配置/类/提交器。
子模块一律经 `state` 访问可重绑态（门面 __getattr__ 实时委托）。"""
import re
import threading
try:
    from ..keymap import cn_to_en, translate_dict
except ImportError:
    try:
        from core.keymap import cn_to_en, translate_dict
    except Exception:
        def cn_to_en(k): return k
        def translate_dict(d): return d
_AT_CQ = re.compile(r"\[CQ:at,qq=(\d+)[^\]]*\]")
_AT_QQ = re.compile(r"@\s*(\d{5,12})")
_AT_NAME = re.compile(r"@\s*([^@\s，,]+)")
try:
    from collections import OrderedDict as _OD2
    _AT_NAMES = _OD2()
except Exception:
    _AT_NAMES = {}
_AT_QQ_TO_NAME = {}  # 反向索引：qq -> name，用于增量更新时清理旧昵称
_AT_NAMES_LOCK = threading.RLock()
_LOCK = threading.RLock()
# ---- 全仓经济/IO常量单源（魔法数收口，语义零变化） ----
COIN_CAP = 100000000000  # 钱包/空投/红包统一钳位上限 1e11
DB_TIMEOUT = 10.0  # sqlite3.connect 超时（秒）：30s 高峰排队会雪崩，10s 快速失败由路由降级为繁忙提示
DB_BUSY_MS = 10000  # PRAGMA busy_timeout（毫秒，与 DB_TIMEOUT 同口径）
_DB = None
_DB_PATH = ""
_DB_R = None
_RLOCK = threading.RLock()
_CONFIG = {}
_ASTRBOT_CFG = None
try:
    from collections import OrderedDict as _OD
    _ACC_CACHE = _OD()
    _GROUP_CACHE = _OD()
except Exception:
    _ACC_CACHE = {}
    _GROUP_CACHE = {}
_ACC_CACHE_MAX = 50000  # 千群千人 1M 账户时，仅热缓存 5 万，常冷数据走 DB，控内存 500MB→~25MB
_GROUP_CACHE_MAX = 5000  # Group LRU：1000群×1000人 1M DirtyDict 常驻会 OOM，限 5000 群
def _safe_commit():
    """提交当前事务并返回是否成功。

    旧实现吞掉 commit 异常，调用方无法区分成功和回滚后的假成功。
    """
    if _DB is None:
        return False
    try:
        _DB.commit()
        return True
    except Exception:
        try:
            _DB.rollback()
        except Exception:
            pass
        return False
def _safe_rollback():
    if _DB is not None:
        try:
            _DB.rollback()
        except Exception:
            pass
def _maybe_commit(force=False):
    return _safe_commit()
def _force_commit():
    return _safe_commit()
_WAKE_CACHE = {}
_CONFIG_VER = 0
def _bump_config_ver():
    global _CONFIG_VER
    _CONFIG_VER += 1
    # 清 wake/守卫 缓存
    try:
        _WAKE_CACHE.clear()
    except Exception:
        pass
    try:
        from ..router import clear_guard_cache as _cgc
        _cgc()
    except Exception:
        try:
            from core.router import clear_guard_cache as _cgc2
            _cgc2()
        except Exception:
            pass
class Acct:
    __slots__ = ("gid", "qq", "kv", "dirty")
    def __init__(self, gid, qq, kv=None):
        self.gid = str(gid)
        self.qq = str(qq)
        if kv:
            has_cn = any('\u4e00' <= c <= '\u9fff' for c in "".join(kv.keys()))
            if has_cn:
                kv = translate_dict(kv)
        self.kv = kv if kv is not None else {}
        self.dirty = False
    def get(self, k, d="0"):
        k = cn_to_en(str(k))
        v = self.kv.get(k, d)
        return str(v) if v is not None else str(d)
    def set(self, k, v):
        k = cn_to_en(str(k))
        self.kv[k] = str(v)
        self.dirty = True
    def int(self, k, d=0):
        k = cn_to_en(str(k))
        try:
            return int(float(self.get(k, str(d))))
        except Exception:
            return int(d)
class _DirtyDict(dict):
    """单群千人增量落盘：dict 写即标脏，避免 save_group 全量 1000→1"""
    def __init__(self, *args, _gid=None, _qq=None, _group=None, **kwargs):
        super().__init__(*args, **kwargs)
        object.__setattr__(self, "_gid", _gid)
        object.__setattr__(self, "_qq", _qq)
        object.__setattr__(self, "_group", _group)
    def __setitem__(self, k, v):
        super().__setitem__(k, v)
        g = getattr(self, "_group", None)
        if g is not None:
            try:
                g._dirty = True
                g._dirty_qqs.add(str(getattr(self, "_qq", "")))
            except Exception:
                pass
    def _mark(self):
        # 删改类操作统一标脏（旧代码仅 setitem/update 标脏，del/pop/clear 漏标致 save_group 跳过）
        try:
            g = getattr(self, "_group", None)
            if g is not None:
                g._dirty = True
                g._dirty_qqs.add(str(getattr(self, "_qq", "")))
        except Exception:
            pass
    def __delitem__(self, k):
        super().__delitem__(k)
        self._mark()
    def pop(self, *a, **kw):
        try:
            return super().pop(*a, **kw)
        finally:
            self._mark()
    def popitem(self):
        try:
            return super().popitem()
        finally:
            self._mark()
    def clear(self):
        try:
            super().clear()
        finally:
            self._mark()
    def setdefault(self, k, default=None):
        if k in self:
            return self[k]
        self[k] = default
        return default
    def __ior__(self, other):
        self.update(other)
        return self
    def update(self, *a, **kw):
        super().update(*a, **kw)
        g = getattr(self, "_group", None)
        if g is not None:
            try:
                g._dirty = True
                g._dirty_qqs.add(str(getattr(self, "_qq", "")))
            except Exception:
                pass
class Group:
    __slots__ = ("_gid", "_users", "_dirty", "_dirty_qqs")
    def __init__(self, gid, users=None):
        self._gid = str(gid)
        self._dirty = False
        self._dirty_qqs = set()
        # 包成 _DirtyDict，便于增量标脏
        self._users = {}
        if users:
            for qq, d in users.items():
                qq = str(qq)
                dd = _DirtyDict(d or {}, _gid=str(gid), _qq=qq, _group=self)
                self._users[qq] = dd
    def sections(self):
        return list(self._users.keys())
    def has_section(self, qq):
        return str(qq) in self._users
    def add_section(self, qq):
        qq = str(qq)
        if qq not in self._users:
            self._users[qq] = _DirtyDict(_gid=self._gid, _qq=qq, _group=self)
            self._dirty = True
            self._dirty_qqs.add(qq)
    def has_option(self, qq, k):
        return k in self._users.get(str(qq), {})
    def __getitem__(self, qq):
        qq = str(qq)
        if qq not in self._users:
            self._users[qq] = _DirtyDict(_gid=self._gid, _qq=qq, _group=self)
            self._dirty = True
            self._dirty_qqs.add(qq)
        return self._users[qq]
    def __setitem__(self, qq, value):
        qq = str(qq)
        # 赋值新 dict 也包成 DirtyDict
        if isinstance(value, dict) and not isinstance(value, _DirtyDict):
            value = _DirtyDict(value, _gid=self._gid, _qq=qq, _group=self)
        self._users[qq] = value
        self._dirty = True
        self._dirty_qqs.add(qq)
    def mark_dirty(self, qq):
        try:
            self._dirty = True
            self._dirty_qqs.add(str(qq))
        except Exception:
            pass
    def get(self, qq, default=None):
        return self._users.get(str(qq), default)
    def __contains__(self, qq):
        return str(qq) in self._users
    def users(self):
        return self._users
    def remove_section(self, qq):
        qq = str(qq)
        with _LOCK:
            if qq in self._users:
                removed = self._users.pop(qq, None)
                self._dirty = True
                self._dirty_qqs.add(qq)
                if _DB is None:
                    self._users[qq] = removed
                    return False
                try:
                    _DB.execute("DELETE FROM groups WHERE gid=? AND qq=?", (int(self._gid), int(qq)))
                    if not _maybe_commit():
                        raise RuntimeError("group delete commit failed")
                except Exception:
                    # 删除失败时恢复内存项，避免数据库旧值与内存状态分叉。
                    if removed is not None:
                        self._users[qq] = removed
                    self._dirty = True
                    self._dirty_qqs.add(qq)
                    try:
                        _safe_rollback()
                    except Exception:
                        pass
                    return False
                return True
            elif _DB is not None:
                try:
                    _DB.execute("DELETE FROM groups WHERE gid=? AND qq=?", (int(self._gid), int(qq)))
                    if not _maybe_commit():
                        raise RuntimeError("group delete commit failed")
                except Exception:
                    try:
                        _safe_rollback()
                    except Exception:
                        pass
        return False


def set_last_backup(value):
    """设置备份时钟；门面模块不能可靠拦截属性赋值。"""
    global _last_backup
    try:
        _last_backup = float(value or 0)
    except Exception:
        _last_backup = 0.0
_PERSISTENT_DATA_DIR = ""
CONFIG_FILE = ""
_COLL_FILES = {"商城图鉴": "shop.json", "精灵图鉴": "atlas.json"}
_COLL_CACHE = {}
try:
    import threading as _th_coll
    _COLL_LOCK = _th_coll.RLock()
except Exception:
    _COLL_LOCK = None
BACKUP_DIR = ""
BACKUP_INTERVAL = 3 * 3600
_last_backup = 0
_LAST_BACKUP_CHECK = 0.0
_LAST_BACKUP_PATH = ""
_LAST_BACKUP_TIME = 0.0
_BACKUP_GEN_LOCK = threading.Lock()
_BACKUP_IN_PROGRESS = None
_BACKUP_FILE_WINDOW = 30.0
_KV_CACHE = {}
_KV_CACHE_LOCK = threading.RLock()
_WD_SECRET_KEYS = ("WebDAV服务器地址", "WebDAV用户名", "WebDAV应用密码")
_WD_SECRET = {}
_WD_SECRET_LOADED = False


class Store:
    """存储实例门面（新增，旧 `import storage as ST` 模块级调用保持兼容）。

    目标：终结全局单例直调。新代码经 Store 实例拿 cfg/recall/acct，
    router.handle(store=...) 未来可注入不同 Store（测试/多租户）。
    当前实现全部委托模块级函数，零语义差。
    """

    def __getattr__(self, name):
        import sys as _sys
        # 1) state 自身
        _mod = _sys.modules.get(__name__)
        try:
            return getattr(_mod, name)
        except AttributeError:
            pass
        # 2) 同包兄弟模块（app_config/wallet/kv/...）：经 import 懒委托，
        #    与 storage/__init__ 门面同序，避免 cfg/recall 等落空
        for _sub in ("app_config", "wallet", "accounts", "groups", "kv",
                     "collections", "secrets", "backup", "db", "mentions"):
            try:
                import importlib as _il
                _pkg = __name__.rsplit(".", 1)[0] if "." in __name__ else __name__
                _m = _il.import_module(f"{_pkg}.{_sub}")
                if hasattr(_m, name):
                    return getattr(_m, name)
            except Exception:
                continue
        raise AttributeError(f"Store has no attribute {name!r}")


default_store = Store()
__all__ = ["Store", "default_store"]
