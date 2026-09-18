# -*- coding: utf-8 -*-
"""core/api package — WebAPI 域注册表重导出（单源在 domains，老路径兼容）"""
try:
    from .domains import (  # type: ignore
        CONFIG_DOMAIN, USERS_DOMAIN, BACKUP_DOMAIN, CONTENT_DOMAIN, DOMAINS,
    )
except ImportError:
    try:
        from core.api.domains import (  # type: ignore
            CONFIG_DOMAIN, USERS_DOMAIN, BACKUP_DOMAIN, CONTENT_DOMAIN, DOMAINS,
        )
    except Exception:
        CONFIG_DOMAIN = USERS_DOMAIN = BACKUP_DOMAIN = CONTENT_DOMAIN = ()
        DOMAINS = {}

__all__ = ["CONFIG_DOMAIN", "USERS_DOMAIN", "BACKUP_DOMAIN", "CONTENT_DOMAIN", "DOMAINS"]
