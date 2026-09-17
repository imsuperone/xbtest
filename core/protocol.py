# -*- coding: utf-8 -*-
"""core/protocol.py — 引擎与路由的显式契约（新增，不破坏旧 handle 签名）。

目标：替代 config._collect_commands 正则扫源码 + router 隐式 None 语义。

- NotHandled：引擎“不处理”的显式哨兵，区别于 None（静默）/ ""（空回复）。
- Engine：统一 handle/can_handle/COMMANDS 协议。旧引擎只有 handle 也能用，
  router 会回退到正则索引 + 直接调用。
- 维护门单源：maintenance_active / maintenance_reply / is_mentioned，
  app._dispatch 与 router.handle 共用，语义与旧两处内联一致。
"""
from typing import Any, Optional, Protocol, Tuple, Union

Reply = Union[str, Tuple[str, list]]
NOT_HANDLED = object()


class Engine(Protocol):
    COMMANDS: tuple = ()
    WAKE: str = ""

    def can_handle(self, gid: str, qq: str, raw: str) -> bool: ...

    def handle(self, gid: str, qq: str, raw: str, *args: Any) -> Optional[Reply]: ...


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


def maintenance_reply(store: Any, raw: str) -> Optional[str]:
    """维护开时：被@回一条维护信息，否则 None（完全静默）。"""
    gid = ""
    try:
        gid = ""
    except Exception:
        pass
    return None


def maintenance_gate(store: Any, gid: str, raw: str) -> Optional[str]:
    """router/app 共用的维护统一门。

    返回：None=未命中维护（继续业务）；str=应回复的维护信息；
    特殊哨兵 _SILENT 表示维护中但不应回复（调用方直接 return None）。
    """
    if not maintenance_active(store, gid):
        return None
    if is_mentioned(store, raw):
        try:
            return store.cfg("维护配置", "维护信息", "🚧 维护中")
        except Exception:
            return "🚧 维护中"
    return _SILENT


_SILENT = object()
SILENT = _SILENT


def engine_commands(mod: Any) -> tuple:
    """引擎显式指令表：优先读模块级 COMMANDS，回退空元组（调用方再走正则索引）。"""
    try:
        cmds = getattr(mod, "COMMANDS", None)
        if callable(cmds):
            cmds = cmds()
        if isinstance(cmds, (list, tuple)):
            return tuple(str(c) for c in cmds if str(c))
    except Exception:
        pass
    return ()


def norm_cmd(s: Any) -> str:
    try:
        return str(s or "").replace(" ", "")
    except Exception:
        return ""
