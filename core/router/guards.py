# -*- coding: utf-8 -*-
"""core/router/guards.py — 路由·guards（原 router.py 切分）。"""
from . import shared as _S

def _sys_off(gid, engine, store):
    sysname = _S._SYS_ENG.get(engine)
    if not sysname:
        return False
    key = ("swf", str(gid), sysname)
    try:
        hit = _S._GUARD_CACHE.get(key)
        if hit and _S._t_guard.time() - hit[0] < _S._GUARD_CACHE_TTL:
            return hit[1]
    except Exception:
        pass
    try:
        val = store.recall_get("swf_%s_%s" % (gid, sysname), "1") == "0"
        try:
            _S._GUARD_CACHE[key] = (_S._t_guard.time(), val)
            if len(_S._GUARD_CACHE) > _S._GUARD_CACHE_MAX:
                # FIFO 踢最旧 1/10（dict 有序，O(n) 远小于全排序；TTL 兜底过期）
                try:
                    for _k in list(_S._GUARD_CACHE.keys())[:_S._GUARD_CACHE_MAX // 10]:
                        _S._GUARD_CACHE.pop(_k, None)
                except Exception:
                    pass
        except Exception:
            pass
        return val
    except Exception:
        return False




def _cfg_sys_off(engine, store):
    sysname = _S._SYS_ENG.get(engine)
    if not sysname:
        return False
    key = ("cfg", sysname)
    try:
        hit = _S._GUARD_CACHE.get(key)
        if hit and _S._t_guard.time() - hit[0] < _S._GUARD_CACHE_TTL:
            return hit[1]
    except Exception:
        pass
    try:
        val = store.cfg("系统开关配置", sysname + "系统", "真") != "真"
        try:
            _S._GUARD_CACHE[key] = (_S._t_guard.time(), val)
        except Exception:
            pass
        return val
    except Exception:
        return False




def _guard(gid, engine, is_admin, raw, store):
    if is_admin:
        return None
    sysname = _S._SYS_ENG.get(engine, engine)
    # 群开关 gacha/守卫缓存需在配置变更时失效，由 store._bump_config_ver 清空 _GUARD_CACHE
    if _cfg_sys_off(engine, store):
        return "【%s系统】已经被关闭了，无法使用该功能！" % sysname
    if _sys_off(gid, engine, store):
        return "【%s系统】已经被关闭了，无法使用该功能！\r\n如需开启，请发送【%s开关】开启！" % (sysname, sysname)
    return None


def clear_guard_cache():
    try:
        _S._GUARD_CACHE.clear()
    except Exception:
        pass
    try:
        _S._GUARD_BATCH_CACHE.clear()
    except Exception:
        pass


def _batch_guard_map(gid, is_admin, store):
    # 批量预计算9引擎守卫结果，0.3s内同gid复用，避免每引擎2次kv读
    if is_admin:
        return {}
    try:
        now = _S._t_guard.time()
        hit = _S._GUARD_BATCH_CACHE.get(str(gid))
        if hit and now - hit[0] < _S._GUARD_BATCH_TTL:
            return hit[1]
    except Exception:
        hit = None
    res = {}
    for eng in ("slave", "sign", "bank", "ent", "spirit", "ride", "guild", "adventure", "superadmin"):
        msg = _guard(gid, eng, is_admin, "", store)
        res[eng] = msg  # None表示放行
    try:
        _S._GUARD_BATCH_CACHE[str(gid)] = (now, res)
    except Exception:
        pass
    return res


__all__ = ["_batch_guard_map", "_cfg_sys_off", "_guard", "_sys_off", "clear_guard_cache"]
