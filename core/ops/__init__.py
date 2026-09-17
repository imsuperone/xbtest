# -*- coding: utf-8 -*-
"""core/ops — 运维面：superadmin/webdav/version/logger/keymap（新分层前向路径）。"""
try:
    from .. import superadmin as superadmin  # type: ignore
    from .. import webdav as webdav  # type: ignore
    from .. import version as version  # type: ignore
    from .. import logger as logger  # type: ignore
    from .. import keymap as keymap  # type: ignore
except ImportError:
    try:
        from core import superadmin as superadmin  # type: ignore
        from core import webdav as webdav  # type: ignore
        from core import version as version  # type: ignore
        from core import logger as logger  # type: ignore
        from core import keymap as keymap  # type: ignore
    except Exception:
        superadmin = webdav = version = logger = keymap = None  # type: ignore

__all__ = ["superadmin", "webdav", "version", "logger", "keymap"]
