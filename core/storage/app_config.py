"""storage/app_config.py — 运行配置读写/归一/快照镜像（原 store §2/§8）。"""
import json
import os
import re
from . import state as _S
from .state import _bump_config_ver
from .collections import _coll_load, _coll_write, _coll_coerce, _sidecar_exists, coll_merge
from .secrets import wd_secret_load
from .kv import recall_set, recall_get
from .db import get_persistent_data_dir
def set_config(cfg: dict):
    if isinstance(cfg, dict):
        _S._CONFIG = cfg or {}
        try:
            _bump_config_ver()
        except Exception:
            pass


def cfg(sec, key, default=""):
    sec = str(sec).strip()
    # 商城/图鉴走独立 sidecar（内存/_CONFIG/文件/镜像均不经过，读穿透）
    if sec in _S._COLL_FILES:
        try:
            d = _coll_load(sec)
            if isinstance(d, dict) and str(key) in d:
                _vv = d[str(key)]
                if isinstance(_vv, (dict, list)):
                    try:
                        return json.dumps(_vv, ensure_ascii=False)
                    except Exception:
                        pass
                return str(_vv)
        except Exception:
            pass
        return str(default)
    # WebDAV 密钥走独立文件：运行时透明叠加，内存/备份/快照里只留空
    if sec == "备份配置" and key in _S._WD_SECRET_KEYS:
        try:
            if not _S._WD_SECRET_LOADED:
                wd_secret_load()
            sv = _S._WD_SECRET.get(key, "")
            if sv != "":
                return str(sv)
        except Exception:
            pass
    v = _S._CONFIG.get(sec) if isinstance(_S._CONFIG.get(sec), dict) else None
    if v is not None and key in v:
        _vv = v[key]
        # dict/list 用 JSON 序列化（repr 单引号会导致引擎 json.loads 全失败静默回退内置）
        if isinstance(_vv, (dict, list)):
            try:
                return json.dumps(_vv, ensure_ascii=False)
            except Exception:
                pass
        return str(_vv)
    return str(default)


def cfgi(sec, key, default=0):
    try:
        return int(float(cfg(sec, key, default)))
    except Exception:
        return int(default)


def cfgf(sec, key, default=0.0):
    try:
        return float(cfg(sec, key, default))
    except Exception:
        return float(default)


def cfg_dict(sec, key, default=None):
    """配置节 dict 口径单源：dict 直返 / JSON 串解析 / 空回退（商城图鉴×3＋精灵图鉴同构收口）。
    与旧四处内联逐行等价：空串/坏串/非dict→default（缺省 {}）。"""
    try:
        v = cfg(sec, key, "")
        if isinstance(v, dict) and v:
            return v
        if v:
            try:
                d = json.loads(v)
                if isinstance(d, dict) and d:
                    return d
            except Exception:
                pass
    except Exception:
        pass
    return default if isinstance(default, dict) else {}


def cfg_scope(sec):
    """单游戏 _cfg/_cfgi 绑定工厂（adventure/guild/spirit 同构收口，零语义差）。
    返回 (cfg_fn, cfgi_fn)，与旧各文件内联定义逐行等价。"""
    sec = str(sec)
    def _sc_cfg(key, default=""):
        return cfg(sec, key, default)
    def _sc_cfgi(key, default=0):
        try:
            return int(float(_sc_cfg(key, default)))
        except Exception:
            return int(default)
    return _sc_cfg, _sc_cfgi


def coin_name():
    return cfg("设置", "货币名称", "金币")


def wake(sysname, default):
    # 缓存 wake 列表，千群每消息 13 次解析→命中缓存 0.03ms→0.001ms
    key = (str(sysname), str(default))
    try:
        hit = _S._WAKE_CACHE.get(key)
        if hit is not None and hit[0] == _S._CONFIG_VER:
            return hit[1]
    except Exception:
        pass
    v = cfg("唤醒词配置", sysname, "").strip()
    lst = []
    for x in re.split(r"[|，,]+", v):
        x = x.strip()
        if x:
            lst.append(x)
    if str(default) not in lst:
        lst.append(str(default))
    try:
        _S._WAKE_CACHE[key] = (_S._CONFIG_VER, lst)
    except Exception:
        pass
    return lst

# ---- 配置路径（sidecar 缓存随目录失效） ----

def set_config_path(path):
    _S.CONFIG_FILE = path
    # 数据目录切换时 sidecar 缓存失效，下次按新目录重读
    try:
        _S._COLL_CACHE.clear()
    except Exception:
        pass


def set_astrbot_config(cfg):
    _S._ASTRBOT_CFG = cfg if isinstance(cfg, dict) else None


def sync_astrbot_config(merged):
    # AstrBot 实体瘦身同步：只回写 slim schema 已知键（_comment 占位），
    # 防 904 键旧残留经“不会删除多余项”机制污染原生页。原生页改后只剩引导行。
    # 全量配置以自有持久文件＋DB 镜像为准，不再经 AstrBot 实体（无任何代码读它）。
    if _S._ASTRBOT_CFG is None:
        return
    try:
        _keep = {}
        try:
            _cur_comment = merged.get("_comment", None) if isinstance(merged, dict) else None
        except Exception:
            _cur_comment = None
        if isinstance(_cur_comment, dict):
            _keep["_comment"] = _cur_comment.get("default", "None")
        elif isinstance(_cur_comment, str) and _cur_comment:
            _keep["_comment"] = _cur_comment
        else:
            _keep["_comment"] = "None"
        try:
            _S._ASTRBOT_CFG.clear()
        except Exception:
            for _k in list(_S._ASTRBOT_CFG.keys()):
                try:
                    del _S._ASTRBOT_CFG[_k]
                except Exception:
                    pass
        try:
            _S._ASTRBOT_CFG["_comment"] = _keep["_comment"]
        except Exception:
            pass
        if hasattr(_S._ASTRBOT_CFG, "save_config"):
            _S._ASTRBOT_CFG.save_config()
    except Exception:
        pass

# ==================== 商城/图鉴独立存储（sidecar，不进 config.json / DB 镜像 / 快照） ====================
# “正常库”只存玩法数值与账户资产；商城图鉴/精灵图鉴独立双文件，引擎与 WebUI 经 cfg/set_ini 透明读写。


def set_ini(sec, key, value):
    if sec in _S._COLL_FILES:
        # 商城/图鉴走 sidecar，不进内存/_CONFIG（防回写污染正常库）。
        # 语义：dict（含空）/JSON 串→存对象；None/空串→删键；不可解析串→跳过（防误清）。
        # 落盘失败回滚内存（与 coll_merge 同策，防内存新盘旧）。
        try:
            if value is None or (isinstance(value, str) and value.strip() == ""):
                op = ("del", None)
            elif isinstance(value, dict):
                op = ("set", value)
            elif isinstance(value, str):
                c = _coll_coerce(value)
                op = ("set", c) if c else ("skip", None)
            else:
                op = ("skip", None)

            def _apply():
                d = _coll_load(sec)
                try:
                    _backup = dict(d)
                except Exception:
                    _backup = None
                if op[0] == "set":
                    d[str(key)] = op[1]
                else:
                    d.pop(str(key), None)
                if not _coll_write(sec):
                    try:
                        if _backup is not None:
                            _S._COLL_CACHE[sec] = _backup
                    except Exception:
                        pass
                    return False
                return True

            if op[0] != "skip":
                if _S._COLL_LOCK is not None:
                    try:
                        with _S._COLL_LOCK:
                            _apply()
                    except Exception:
                        _apply()
                else:
                    _apply()
        except Exception:
            pass
        try:
            _bump_config_ver()
        except Exception:
            pass
        return
    _S._CONFIG.setdefault(sec, {})[key] = value if isinstance(value, dict) else str(value)
    try:
        _bump_config_ver()
    except Exception:
        pass


def _flatten_cfg(cfg):
    out = {}
    if not isinstance(cfg, dict):
        return out
    for sec, sub in cfg.items():
        if isinstance(sub, dict):
            for k, v in sub.items():
                key = str(k)
                if key == "":
                    out[str(sec)] = str(v)
                elif isinstance(v, dict):
                    out["%s__%s" % (sec, key)] = json.dumps(v, ensure_ascii=False)
                else:
                    out["%s__%s" % (sec, key)] = str(v)
        else:
            out[str(sec)] = str(sub)
    return out


def save_config():
    p = _S.CONFIG_FILE
    if not p:
        try:
            p = os.path.join(get_persistent_data_dir(), "config.json")
        except Exception:
            p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "config.json")
    try:
        # 防截断：内存配置为空时拒绝落盘，避免把有效持久文件清成 {}
        if not isinstance(_S._CONFIG, dict) or not _S._CONFIG:
            return
        # 商城/图鉴独立 sidecar：文件与镜像同步剥离，不进正常库
        _persist = {s: kv for s, kv in _S._CONFIG.items() if s not in _S._COLL_FILES} if isinstance(_S._CONFIG, dict) else {}
        flat = _flatten_cfg(_persist)
        if not flat:
            return
        # 原子落盘：先写临时文件再替换，防中途崩溃留半截文件
        tmp = p + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(flat, f, ensure_ascii=False, indent=2)
        os.replace(tmp, p)
    except Exception:
        pass
    # 同步落盘全量配置到 SQLite kv 表，确保 .db 文件自包含全部配置与用户资产
    try:
        if isinstance(_S._CONFIG, dict) and _S._CONFIG:
            _mirror = {s: kv for s, kv in _S._CONFIG.items() if s not in _S._COLL_FILES}
            recall_set("sys_config_json", json.dumps(_mirror, ensure_ascii=False))
    except Exception:
        pass
    # sidecar（商城/精灵图鉴）同步镜像进 kv：单 .db 即含全部配置，完整迁移不再依赖导出中心补图鉴；
    # 仅 sidecar 文件存在时镜像（文件缺失不判空，防止早初始化空缓存覆盖好镜像）
    try:
        _coll_secs = getattr(_S, "_COLL_FILES", {}) or {}
        _coll_mirror = {}
        _coll_any = False
        for _sec in _coll_secs:
            try:
                if not _sidecar_exists(_sec):
                    continue
                _coll_any = True
                _d = _coll_load(_sec)
                if isinstance(_d, dict):
                    _coll_mirror[_sec] = _d
            except Exception:
                pass
        if _coll_any:
            recall_set("sys_coll_json", json.dumps(_coll_mirror, ensure_ascii=False))
    except Exception:
        pass


def load_config_from_db():
    """从数据库恢复全量配置：若内存配置缺失或为空，从 kv 表补齐（跳过商城/图鉴 sidecar 节）"""
    try:
        raw = recall_get("sys_config_json", "")
        if raw:
            db_cfg = json.loads(raw)
            if isinstance(db_cfg, dict) and db_cfg:
                for sec, sub in db_cfg.items():
                    if sec in _S._COLL_FILES:
                        continue
                    if isinstance(sub, dict):
                        s = _S._CONFIG.setdefault(sec, {})
                        for k, v in sub.items():
                            if k not in s or s[k] in (None, ""):
                                s[k] = v
                _sidecar_heal_from_mirror()
                return True
    except Exception:
        pass
    try:
        _sidecar_heal_from_mirror()
    except Exception:
        pass
    return False


def _sidecar_heal_from_mirror():
    """sidecar 缺文件自愈：仅 sidecar 文件缺失时才从 kv 镜像回填（文件优先，坏文件不碰）。
    恢复全量替换语义由 reload_config_from_db 承担，此处只补“无文件”场景。"""
    try:
        raw = recall_get("sys_coll_json", "")
        if not raw:
            return False
        db_coll = json.loads(raw)
        if not isinstance(db_coll, dict) or not db_coll:
            return False
        healed = False
        for sec, kv in db_coll.items():
            try:
                if sec not in (getattr(_S, "_COLL_FILES", {}) or {}):
                    continue
                if not isinstance(kv, dict) or not kv:
                    continue
                if _sidecar_exists(sec):
                    continue
                # 直写（禁 coll_merge）：镜像值多为原生纯字符串，
                # coll_merge 的 JSON 串 coerce 会误杀，缺文件场景直写即等价替换
                _S._COLL_CACHE[sec] = dict(kv)
                if _coll_write(sec):
                    healed = True
            except Exception:
                pass
        return healed
    except Exception:
        return False


def reload_config_from_db():
    """恢复数据库后重新载入配置镜像；没有镜像时保留当前配置。"""
    try:
        raw = recall_get("sys_config_json", "")
        if not raw:
            return False
        db_cfg = json.loads(raw)
        if not isinstance(db_cfg, dict) or not db_cfg:
            return False
        _S._CONFIG.clear()
        for sec, sub in db_cfg.items():
            if sec in _S._COLL_FILES:
                continue
            _S._CONFIG[sec] = dict(sub) if isinstance(sub, dict) else sub
        _bump_config_ver()
        _sidecar_restore_from_mirror()
        return True
    except Exception:
        return False


def _sidecar_restore_from_mirror():
    """恢复路径 sidecar 落盘：kv 镜像整体替换 sidecar 文件（恢复即回滚语义）。
    老备份无镜像即跳过（行为不变）；坏文件由 _coll_write 拒写保护，不碰。"""
    try:
        raw = recall_get("sys_coll_json", "")
        if not raw:
            return False
        db_coll = json.loads(raw)
        if not isinstance(db_coll, dict) or not db_coll:
            return False
        done = False
        for sec, kv in db_coll.items():
            try:
                if sec not in (getattr(_S, "_COLL_FILES", {}) or {}):
                    continue
                if not isinstance(kv, dict):
                    continue
                _S._COLL_CACHE[sec] = dict(kv)
                if _coll_write(sec):
                    done = True
            except Exception:
                pass
        return done
    except Exception:
        return False

# ==================== 9. 备份 ====================

__all__ = ["cfg", "cfg_dict", "cfg_scope", "cfgf", "cfgi", "coin_name", "load_config_from_db", "reload_config_from_db", "save_config", "set_astrbot_config", "set_config", "set_config_path", "set_ini", "sync_astrbot_config", "wake"]
