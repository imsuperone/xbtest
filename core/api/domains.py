# -*- coding: utf-8 -*-
"""core/api/domains — WebAPI 按域归拢（新增注册表，老 14 文件不动，WebUI 不受影响）。

目标 14→4：配置域 / 用户域 / 备份域 / 内容域。新代码从域导入，
老 `core.api.stats.handle_*` 逐个留作垫片。
"""
CONFIG_DOMAIN = ("settings", "snapshots")
USERS_DOMAIN = ("users", "user_io", "airdrop", "profiles")
BACKUP_DOMAIN = ("backup", "backup_cloud", "migration")
CONTENT_DOMAIN = ("stats", "atlas", "weapon_pool", "images")

DOMAINS = {
    "config": CONFIG_DOMAIN,
    "users": USERS_DOMAIN,
    "backup": BACKUP_DOMAIN,
    "content": CONTENT_DOMAIN,
}

__all__ = ["CONFIG_DOMAIN", "USERS_DOMAIN", "BACKUP_DOMAIN", "CONTENT_DOMAIN", "DOMAINS"]
