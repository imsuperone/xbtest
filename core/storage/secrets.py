"""storage/secrets.py — WebDAV 密钥分存 webdav_secret.json（原 store 密钥节）。"""
import json
import os
from . import state as _S
from .db import get_persistent_data_dir
from .kv import recall_get, recall_set

def _wd_secret_path():
    try:
        base = ""
        try:
            if _S.CONFIG_FILE:
                base = os.path.dirname(os.path.abspath(_S.CONFIG_FILE))
        except Exception:
            base = ""
        if not base:
            try:
                base = get_persistent_data_dir()
            except Exception:
                base = ""
        if not base:
            return ""
        return os.path.join(base, "webdav_secret.json")
    except Exception:
        return ""




def wd_secret_load(force=False):
    """读独立密钥文件（内存缓存；备份/快照/导出永不触碰此文件）"""
    if _S._WD_SECRET_LOADED and not force:
        return dict(_S._WD_SECRET)
    d = {}
    try:
        p = _wd_secret_path()
        if p and os.path.isfile(p):
            with open(p, encoding="utf-8") as f:
                raw = json.load(f)
            if isinstance(raw, dict):
                for k in _S._WD_SECRET_KEYS:
                    if raw.get(k) not in (None, ""):
                        d[k] = str(raw.get(k))
    except Exception:
        pass
    _S._WD_SECRET = d
    _S._WD_SECRET_LOADED = True
    return dict(d)




def wd_secret_set(key, value):
    """写单密钥：空值=删除该键；落独立文件。返回 True=已变更"""
    try:
        sec = wd_secret_load()
        key = str(key)
        if key not in _S._WD_SECRET_KEYS:
            return False
        v = str(value or "")
        if v == "":
            if key not in sec:
                return False
            sec.pop(key, None)
        elif sec.get(key) == v:
            return False
        else:
            sec[key] = v
        p = _wd_secret_path()
        if not p:
            _S._WD_SECRET = sec
            _S._WD_SECRET_LOADED = True
            return True
        # 原子落盘成功才进内存：崩溃截断不再丢密钥，失败返 False 不谎报
        try:
            _t = p + ".tmp"
            with open(_t, "w", encoding="utf-8") as f:
                json.dump(sec, f, ensure_ascii=False, indent=2)
            os.replace(_t, p)
        except Exception:
            return False
        _S._WD_SECRET = sec
        _S._WD_SECRET_LOADED = True
        return True
    except Exception:
        return False




def _wd_secret_migrate():
    """一次性迁移：_CONFIG/DB 镜像里的旧密钥搬进独立文件并清空白 historically leaked 位置。
    新备份/快照自此不再含密钥（历史备份文件不受影响）。"""
    try:
        sec = _S._CONFIG.get("备份配置") if isinstance(_S._CONFIG, dict) else None
        moved = False
        if isinstance(sec, dict):
            for k in _S._WD_SECRET_KEYS:
                v = str(sec.get(k, "") or "")
                if v != "":
                    try:
                        cur = wd_secret_load().get(k, "")
                    except Exception:
                        cur = ""
                    if cur == "":
                        wd_secret_set(k, v)
                    sec[k] = ""
                    moved = True
        for k in _S._WD_SECRET_KEYS:
            try:
                if str(recall_get("wdcfg__" + k, "") or "") != "":
                    recall_set("wdcfg__" + k, "")
                    moved = True
            except Exception:
                pass
        if moved:
            try:
                from .app_config import save_config
                save_config()
            except Exception:
                pass
    except Exception:
        pass


__all__ = ["wd_secret_load", "wd_secret_set"]
