# -*- coding: utf-8 -*-
"""core/platform — 平台层：messaging/adapters（新分层前向路径）。"""
try:
    from .. import messaging as messaging  # type: ignore
    from .. import adapters as adapters  # type: ignore
except ImportError:
    try:
        from core import messaging as messaging  # type: ignore
        from core import adapters as adapters  # type: ignore
    except Exception:
        messaging = adapters = None  # type: ignore

__all__ = ["messaging", "adapters"]
