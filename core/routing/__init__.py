# -*- coding: utf-8 -*-
"""core/routing — 路由层：protocol/router 单源（新分层前向路径）。"""
try:
    from .. import router as router  # type: ignore
    from .. import protocol as protocol  # type: ignore
except ImportError:
    try:
        from core import router as router  # type: ignore
        from core import protocol as protocol  # type: ignore
    except Exception:
        router = protocol = None  # type: ignore

__all__ = ["router", "protocol"]
