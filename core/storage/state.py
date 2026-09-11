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
DB_TIMEOUT = 30.0  # sqlite3.connect 超时（秒）
DB_BUSY_MS = 30000  # PRAGMA busy_timeout（毫秒，与 DB_TIMEOUT 同口径）
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
    if _DB is not None:
        try:
            _DB.commit()
        except Exception:
            try:
                _DB.rollback()
            except Exception:
                pass
def _safe_rollback():
    if _DB is not None:
        try:
            _DB.rollback()
        except Exception:
            pass
def _maybe_commit(force=False):
    _safe_commit()
def _force_commit():
    _safe_commit()
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
                self._users.pop(qq, None)
                self._dirty = True
                self._dirty_qqs.add(qq)
                if _DB is not None:
                    try:
                        _DB.execute("DELETE FROM groups WHERE gid=? AND qq=?", (int(self._gid), int(qq)))
                        _maybe_commit()
                    except Exception:
                        try:
                            _safe_rollback()
                        except Exception:
                            pass
                return True
            elif _DB is not None:
                try:
                    _DB.execute("DELETE FROM groups WHERE gid=? AND qq=?", (int(self._gid), int(qq)))
                    _maybe_commit()
                except Exception:
                    try:
                        _safe_rollback()
                    except Exception:
                        pass
        return False
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
