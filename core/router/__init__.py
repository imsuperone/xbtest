# -*- coding: utf-8 -*-
"""core/router/ — 统一指令路由包门面（原 router.py 726 行切分，对外一致）。
shared（常量/缓存/渲染）/ guards（开关守卫）/ commands（引擎指令）/
rules（自定义/禁用/权限）/ pipeline（11 层 handle）。"""
from .guards import *
from .commands import *
from .rules import *
from .pipeline import *
from . import shared as _state
from . import guards as guards
from . import commands as commands
from . import rules as rules
from . import pipeline as pipeline
from .shared import _MAIN_MENU, _SYS_ENG, _multi_reply, _render_vars

__all__ = ["_MAIN_MENU", "_SYS_ENG", "_resolve_reply", "_norm_cmd",
           "apply_reply_override", "_sys_off", "_cfg_sys_off", "_guard",
           "clear_guard_cache", "_batch_guard_map",
           "_engine_cache_ver", "_get_engine_cmds", "_matches_engine",
           "_multi_reply", "_render_vars",
           "_custom_fp", "_custom_idx", "_custom_cmd", "_cmd_disabled", "_cmd_need_admin",
           "handle"]
_SUBMODS = None


def __getattr__(name):
    try:
        return getattr(_state, name)
    except AttributeError:
        pass
    global _SUBMODS
    if _SUBMODS is None:
        _SUBMODS = (guards, commands, rules, pipeline)
    for _m in _SUBMODS:
        try:
            return getattr(_m, name)
        except Exception:
            continue
    raise AttributeError(f"router facade has no attribute {name!r}")
