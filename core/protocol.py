# -*- coding: utf-8 -*-
"""core/protocol.py — 引擎与路由的显式契约（新增，不破坏旧 handle 签名）。

- 维护判定原语：maintenance_active / is_mentioned —— 统一门 maintenance_gate
  单源在 core/router（app._dispatch 与 router.handle 共用）。
- engine_commands：引擎显式 COMMANDS 表读取（V8 正则索引已退役，此表即唯一词表来源）。
"""
from typing import Any


def is_mentioned(store: Any, raw: str) -> bool:
    try:
        pa = getattr(store, "parse_at", None)
        if callable(pa):
            hit, _ = pa(str(raw or ""))
            return hit is not None
    except Exception:
        pass
    return "[CQ:at" in str(raw or "")


def maintenance_active(store: Any, gid: str) -> bool:
    try:
        if store is not None and store.cfg("维护配置", "维护开关", "假") == "真":
            return True
    except Exception:
        pass
    try:
        if gid and str(gid).isdigit() and store is not None \
                and store.recall_get("group_maint_%s" % gid, "0") == "1":
            return True
    except Exception:
        pass
    return False


SILENT = object()  # 维护中静默哨兵（core.router.maintenance_gate 的返回值之一）


def engine_commands(mod: Any) -> tuple:
    """引擎显式指令表：读模块级 COMMANDS（元组或 callable），缺失回退空元组。"""
    try:
        cmds = getattr(mod, "COMMANDS", None)
        if callable(cmds):
            cmds = cmds()
        if isinstance(cmds, (list, tuple)):
            return tuple(str(c) for c in cmds if str(c))
    except Exception:
        pass
    return ()
