# -*- coding: utf-8 -*-
"""core/router/cmds.py — 路由·cmds（原 router.py 切分）。"""
import os
from . import shared as _S
from .shared import _norm_cmd


def _engine_cache_ver(store=None):
    try:
        ver = getattr(store, "_CONFIG_VER", 0) if store is not None else 0
    except Exception:
        ver = 0
    try:
        _now = _S._t_guard.time()
        if _now - _S._ENGINE_MT_CACHE.get("t", 0.0) < _S._ENGINE_MT_TTL:
            return (_S._ENGINE_MT_CACHE.get("mt", 0.0), ver)
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        eng_dir = os.path.join(base, "games")
        if not os.path.isdir(eng_dir):
            try:
                eng_dir = os.path.join(os.path.dirname(base), "games")
            except Exception:
                pass
        max_mt = 0.0
        _watch = [os.path.join(eng_dir, _n + ".py")
                  for _n in ("sign", "spirit", "ride", "guild", "adventure", "chat")]
        for _pkg in ("slave", "bank", "ent"):
            _pd = os.path.join(eng_dir, _pkg)
            if os.path.isdir(_pd):
                _watch.extend(os.path.join(_pd, f) for f in os.listdir(_pd) if f.endswith(".py"))
        _watch.append(os.path.join(base, "core", "superadmin.py"))
        for _p in _watch:
            try:
                _mt = os.path.getmtime(_p)
                if _mt > max_mt:
                    max_mt = _mt
            except Exception:
                pass
        _S._ENGINE_MT_CACHE["t"] = _now
        _S._ENGINE_MT_CACHE["mt"] = max_mt
    except Exception:
        max_mt = _S._ENGINE_MT_CACHE.get("mt", 0.0)
    return (max_mt, ver)


def _get_engine_cmds(engine, store=None):
    try:
        cur_ver = _engine_cache_ver(store)
    except Exception:
        cur_ver = None
    try:
        if _S._ENGINE_CMDS_VER != cur_ver or engine not in _S._ENGINE_CMDS:
            try:
                from ..config import _collect_commands
                base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                all_cmds = _collect_commands(base, store)
                if all_cmds:
                    _S._ENGINE_CMDS.clear()
                    _S._ENGINE_CMDS.update(all_cmds)
                    _S._ENGINE_CMDS_VER = cur_ver
            except Exception:
                pass
            if engine not in _S._ENGINE_CMDS and not _S._ENGINE_CMDS:
                try:
                    from ..config import _collect_commands as _cc2
                    all_cmds2 = _cc2(base, store)
                    if all_cmds2:
                        _S._ENGINE_CMDS.update(all_cmds2)
                        _S._ENGINE_CMDS_VER = cur_ver
                except Exception:
                    pass
    except Exception:
        pass
    return _S._ENGINE_CMDS.get(engine, [])


def _matches_engine(raw, engine, store=None):
    if not raw:
        return False
    rt = str(raw).strip()
    sysname = _S._SYS_ENG.get(engine, engine)
    if store and hasattr(store, "wake"):
        try:
            wakes = store.wake(sysname + "系统", sysname + "系统")
            if rt in wakes:
                return True
        except Exception:
            pass
    if rt in (sysname + "系统", sysname + "菜单", sysname + "帮助"):
        return True
    cmds = _get_engine_cmds(engine, store)
    rt_n = _norm_cmd(rt)
    for c in cmds:
        if c and rt_n.startswith(_norm_cmd(c)):
            return True
    return False



__all__ = ["_engine_cache_ver", "_get_engine_cmds", "_matches_engine"]
