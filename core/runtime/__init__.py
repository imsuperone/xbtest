# -*- coding: utf-8 -*-
"""core/runtime — 运行时层：启动/分发编排（新分层前向路径，老路径留垫片）。

前向 import：from core.runtime import app, dispatch, config
兼容：from core.app / core.dispatch / core.config 照旧可用（垫片未删）。
"""
try:
    from .. import app as app  # type: ignore
    from .. import dispatch as dispatch  # type: ignore
    from .. import config as config  # type: ignore
except ImportError:
    try:
        from core import app as app  # type: ignore
        from core import dispatch as dispatch  # type: ignore
        from core import config as config  # type: ignore
    except Exception:
        app = dispatch = config = None  # type: ignore

__all__ = ["app", "dispatch", "config"]
