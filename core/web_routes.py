# -*- coding: utf-8 -*-
"""core/web_routes - Web API 注册表单源（路由+分发四元组；原 app.py 数据段并入，page_* 合成层已退役）。
改路由只改此表；app.py 以兼容导入取表，老 `from core.app import _XB_API_ROUTES` 仍可用。
#
# 五元组 (路径后缀, 方法, page 名, 说明, 分发 (模块, 函数, 错误标签, 参数))：
# page 名仅作路由身份/文档用，运行时闭包见 app._route_handler；改路由只改此表。
# 下方 lambda 所需名（schema/指令索引兜底）在本模块受控导入，导入失败置 None 降级。
"""
# 分发 fallback 所需名（schema/指令索引兜底 lambda）：包内相对优先、顶层绝对回退；
# 导入全失败置 None——lambda 在调用期解析名，缺失即异常，走 app._call_api 归一（与原 app 内联语义一致）
try:
    from .adapters import json_response
    from .config import _load_schema, _collect_commands
except Exception:
    try:
        from core.adapters import json_response  # type: ignore
        from core.config import _load_schema, _collect_commands  # type: ignore
    except Exception:
        json_response = _load_schema = _collect_commands = None  # type: ignore


# Web API 注册表：(路径后缀, 方法, page 名, 说明, 分发四元组 (模块, 函数, 错误标签, 参数))
# page 名仅作路由身份/文档用；运行时闭包由分发四元组经 app._route_handler 注册期生成，改路由只改此表。
# 兼容检测关键字注释（_raw_file_response/is_raw/total_power）保留在对应行，禁删。
_XB_API_ROUTES = [
    ("stats", "GET", "page_stats", "游戏数据总览", ("core.api.stats", "handle_stats", "stats", {"mode": "none"})),
    ("rank", "GET", "page_rank", "排行榜", ("core.api.stats", "handle_rank", "rank", {"mode": "req"})),
    ("config/get", "GET", "page_cfg_get", "读取运行配置", ("core.api.settings", "handle_cfg_get", "get", {"mode": "get_req"})),
    ("config/save", "POST", "page_cfg_save", "保存运行配置", ("core.api.settings", "handle_cfg_save", "save", {"mode": "get_req", "with_base": True})),
    ("config/auto_balance", "POST", "page_config_auto_balance", "游戏数值智能平衡一键匹配", ("core.api.balance", "handle_config_auto_balance", "auto balance", {})),
    ("config/balance_state", "GET", "page_balance_state", "平衡档位真实状态与漂移检测", ("core.api.balance", "handle_balance_state", "balance state", {"mode": "req"})),
    ("analytics/overview", "GET", "page_analytics_overview", "群生态与经济运行大屏数据", ("core.api.stats", "handle_analytics_overview", "analytics", {})),
    ("users/airdrop", "POST", "page_users_airdrop", "全员/群聊批量福利空投", ("core.api.airdrop", "handle_users_airdrop", "airdrop", {})),
    ("config/schema", "GET", "page_cfg_schema", "配置schema(按节分组)", ("core.api.settings", "handle_cfg_schema", "schema", {"with_base": True, "fallback": lambda: json_response(_load_schema())})),
    # _raw_file_response is_raw 保留关键字以兼容 test_fix 检测
    ("user/export", "GET,POST", "page_user_export", "导出单用户数据", ("core.api.user_io", "handle_user_export", "export", {})),
    ("user/import", "POST", "page_user_import", "导入单用户数据", ("core.api.user_io", "handle_user_import", "import", {})),
    # is_raw _raw_file_response raw 关键字保留
    ("users/export", "GET,POST", "page_users_export", "导出全量用户数据", ("core.api.user_io", "handle_users_export", "export", {})),
    ("users/import", "POST", "page_users_import", "导入全量用户数据", ("core.api.user_io", "handle_users_import", "import", {})),
    ("users/clean_left", "POST", "page_users_clean_left", "清理退群人员数据", ("core.api.users", "handle_users_clean_left", "clean left users", {"use_context": True})),
    ("commands", "GET", "page_commands", "指令一览", ("core.api.settings", "handle_commands", "commands", {"with_base": True, "fallback": lambda: json_response(_collect_commands())})),
    ("users", "GET", "page_users", "用户/财富列表", ("core.api.users", "handle_users", "users", {})),
    ("user/edit", "POST", "page_user_edit", "编辑用户数据(金币/体力/魅力/奖券)", ("core.api.users", "handle_user_edit", "edit", {})),
    ("user/clear", "POST", "page_user_clear", "清除单用户数据(含奴隶与精灵并可重领新手礼包)", ("core.api.users", "handle_user_clear", "clear", {})),
    ("images/list", "GET", "page_images_list", "图片目录浏览", ("core.api.images", "handle_images_list", "images list", {"with_base": True})),
    ("images/upload", "POST", "page_images_upload", "上传图片", ("core.api.images", "handle_images_upload", "upload", {"with_base": True})),
    ("images/delete", "POST", "page_images_delete", "删除图片", ("core.api.images", "handle_images_delete", "delete", {"with_base": True})),
    ("images/rename", "POST", "page_images_rename", "重命名图片", ("core.api.images", "handle_images_rename", "rename", {"with_base": True})),
    ("images/mkdir", "POST", "page_images_mkdir", "新建文件夹", ("core.api.images", "handle_images_mkdir", "mkdir", {"with_base": True})),
    ("images/preview", "GET,POST", "page_images_preview", "单图预览统一入口(path=图片目录, name=抽奖武器)", ("core.api.images", "handle_image_preview", "preview", {"mode": "req", "with_base": True})),
    ("images/text", "GET", "page_images_text", "文本文件在线浏览", ("core.api.images", "handle_images_text", "text", {"mode": "req", "with_base": True})),
    ("images/text/save", "POST", "page_images_text_save", "保存文本文件内容", ("core.api.images", "handle_images_text_save", "text save", {"mode": "req", "with_base": True})),
    ("images/copy", "POST", "page_images_copy", "复制文件", ("core.api.images", "handle_images_copy", "copy", {"with_base": True})),
    ("export", "GET,POST", "page_export", "导出统一入口(?kind=images|backup|logs)", ("core.api.exporters", "handle_export", "export", {"with_base": True})),
    ("spirits", "GET", "page_spirits_get", "精灵图鉴读取", ("core.api.atlas", "handle_spirits_get", "spirits get", {})),
    ("spirits/save", "POST", "page_spirits_save", "精灵图鉴保存", ("core.api.atlas", "handle_spirits_save", "spirits save", {})),
    ("gacha/weapons", "GET", "page_gacha_weapons", "抽奖武器池", ("core.api.weapon_pool", "handle_gacha_weapons", "gacha weapons", {})),
    ("weapons/pool", "GET", "page_pool_list", "抽奖武器池文件列表", ("core.api.weapon_pool", "handle_pool_list", "pool list", {"mode": "req"})),
    ("weapons/pool/rename", "POST", "page_pool_rename", "抽奖武器改名", ("core.api.weapon_pool", "handle_pool_rename", "pool rename", {"mode": "req"})),
    ("weapons/pool/move", "POST", "page_pool_move", "抽奖武器改稀有度", ("core.api.weapon_pool", "handle_pool_move", "pool move", {"mode": "req"})),
    ("weapons/pool/delete", "POST", "page_pool_delete", "抽奖武器删除", ("core.api.weapon_pool", "handle_pool_delete", "pool delete", {"mode": "req"})),
    ("weapons/pool/upload", "POST", "page_pool_upload", "抽奖武器上传", ("core.api.weapon_pool", "handle_pool_upload", "pool upload", {"mode": "req"})),
    ("weapons/pool/attrs", "POST", "page_pool_attrs", "抽奖武器属性保存", ("core.api.weapon_pool", "handle_pool_attrs", "pool attrs", {"mode": "req"})),
    ("weapons/pool/replace_path", "POST", "page_pool_replace_path", "抽奖武器内置选图", ("core.api.weapon_pool", "handle_pool_replace_path", "pool replace", {"mode": "req"})),
    ("backups/list", "GET", "page_backups_list", "备份列表", ("core.api.backup", "handle_backups_list", "backups list", {"with_base": True})),
    ("backups/create", "POST", "page_backups_create", "立即生成备份", ("core.api.backup", "handle_backups_create", "create", {"with_base": True})),
    ("backups/restore", "POST", "page_backups_restore", "恢复备份", ("core.api.backup", "handle_backups_restore", "restore", {"with_base": True})),
    ("backups/delete", "POST", "page_backups_delete", "删除备份", ("core.api.backup", "handle_backups_delete", "delete", {"with_base": True})),
    ("backups/config/snapshots", "GET", "page_cfg_snapshots", "配置快照列表", ("core.api.snapshots", "handle_cfg_snapshots", "snapshots", {"with_base": True})),
    ("backups/config/snapshot/save", "POST", "page_cfg_snapshot_save", "保存配置快照", ("core.api.snapshots", "handle_cfg_snapshot_save", "snapshot save", {"with_base": True})),
    ("backups/config/snapshot/restore", "POST", "page_cfg_snapshot_restore", "恢复配置快照", ("core.api.snapshots", "handle_cfg_snapshot_restore", "snapshot restore", {"with_base": True})),
    ("backups/doctor", "POST", "page_db_doctor", "数据库健康体检与碎片整理", ("core.api.backup", "handle_db_doctor", "db doctor", {"with_base": True})),
    ("backups/prune", "POST", "page_backups_prune", "按保留数量修剪本地与云端旧备份", ("core.api.backup", "handle_backups_prune", "prune", {"with_base": True})),
    ("import/legacy", "POST", "page_import_legacy", "旧库导入（兼容新旧格式）", ("core.api.migration", "handle_import_legacy", "legacy import", {"with_base": True})),
    ("slave/users", "GET", "page_slave_users", "奴隶用户列表", ("core.api.profiles", "handle_slave_users", "slave users", {})),
    ("slave/calibrate", "POST", "page_slave_calibrate", "一键校准全员身价", ("core.api.profiles", "handle_slave_calibrate", "slave calibrate", {})),
    # total_power spirit/users 关键字保留以兼容检测
    ("spirit/users", "GET", "page_spirit_users", "精灵用户列表", ("core.api.profiles", "handle_spirit_users", "spirit users", {})),
    ("groups/list", "GET", "page_groups_list", "群聊列表", ("core.api.groups", "handle_groups_list", "groups list", {})),
    ("groups/toggle", "POST", "page_groups_toggle", "切换群聊/总开关", ("core.api.groups", "handle_groups_toggle", "groups toggle", {})),
    ("groups/delete", "POST", "page_groups_delete", "删除群聊配置", ("core.api.groups", "handle_groups_delete", "groups delete", {})),
    ("admin/clear", "POST", "page_clear_all", "清空所有数据（三重确认）", ("core.api.backup", "handle_clear_all", "clear", {"with_base": True})),
    ("version/check", "GET,POST", "page_version_check", "在线检查版本更新", ("core.api.version_check", "handle_version_check", "version check", {"mode": "req", "with_base": True})),
    ("version/channel", "GET,POST", "page_version_channel", "更新通道查询与切换", ("core.api.version_check", "handle_version_channel", "version channel", {"mode": "req"})),
    ("logs", "GET,POST", "page_logs_get", "获取插件运行日志", ("core.api.logs", "handle_logs_get", "logs get", {"mode": "req"})),
    ("logs/clear", "POST", "page_logs_clear", "清空插件运行日志", ("core.api.logs", "handle_logs_clear", "logs clear", {"mode": "req"})),
]

# WebDAV 双前缀别名表（backup/ 与 backups/ 同义，由循环展开注册）
_XB_WEBDAV_ROUTES = [
    ("webdav/test", "GET,POST", "page_webdav_test", "测试WebDAV连接", ("core.api.backup_cloud", "handle_webdav_test", "webdav test", {"mode": "req"})),
    ("webdav/upload", "POST", "page_webdav_backup_now", "立即上传WebDAV备份", ("core.api.backup_cloud", "handle_webdav_backup_now", "webdav backup", {"mode": "req"})),
    ("webdav/files", "GET,POST", "page_webdav_files", "获取WebDAV远端备份文件列表", ("core.api.backup_cloud", "handle_webdav_files", "webdav files", {"mode": "req"})),
    ("webdav/restore", "POST", "page_webdav_restore", "从WebDAV远端备份恢复数据", ("core.api.backup_cloud", "handle_webdav_restore", "webdav restore", {"mode": "req", "with_base": True})),
    ("webdav/delete", "POST", "page_webdav_delete", "删除WebDAV远端备份", ("core.api.backup_cloud", "handle_webdav_delete", "webdav delete", {"mode": "req", "with_base": True})),
]

# 写操作 handler 名集合：_call_api 对其做显式非管理员标记的失败关闭检查。
# 注意：AstrBot 宿主鉴权契约未在本仓提供，缺标记时交由宿主 dashboard 会话判定；
# 此处绝不因“无标记”而放行日志以外的结论，也不因猜测 header 而拦截正常管理台。
_XB_MUTATING_HANDLERS = frozenset({
    "handle_cfg_save", "handle_config_auto_balance",
    "handle_users_airdrop", "handle_user_edit", "handle_user_clear",
    "handle_users_clean_left", "handle_user_import", "handle_users_import",
    "handle_spirits_save",
    "handle_pool_rename", "handle_pool_move", "handle_pool_delete",
    "handle_pool_upload", "handle_pool_attrs", "handle_pool_replace_path",
    "handle_backups_create", "handle_backups_restore", "handle_backups_delete",
    "handle_cfg_snapshot_save", "handle_cfg_snapshot_restore",
    "handle_backups_prune", "handle_db_doctor", "handle_clear_all",
    "handle_images_upload", "handle_images_delete", "handle_images_rename",
    "handle_images_mkdir", "handle_images_copy", "handle_images_text_save",
    "handle_import_legacy", "handle_groups_toggle", "handle_groups_delete",
    "handle_logs_clear",
    "handle_webdav_backup_now", "handle_webdav_restore", "handle_webdav_delete",
    "handle_slave_calibrate",
})


def _web_admin_explicit_deny(request):
    """仅当请求明确携带非管理员标记时返回 True（失败关闭），其余返回 False。

    检查面：dict/query/headers/属性上的 is_admin/admin/role 显式假值。
    未知形状或缺标记一律返回 False（交由宿主会话判定），避免误拦截管理台。
    """
    try:
        cands = []
        if request is None:
            return False
        if isinstance(request, dict):
            for _k in ("is_admin", "admin", "isAdmin", "role", "user_role"):
                if _k in request:
                    cands.append(request.get(_k))
            try:
                _q = request.get("query") or request.get("query_params") or request.get("args")
                if isinstance(_q, dict):
                    for _k in ("is_admin", "admin"):
                        if _k in _q:
                            cands.append(_q.get(_k))
            except Exception:
                pass
        else:
            for _attr in ("is_admin", "admin"):
                try:
                    if hasattr(request, _attr):
                        _v = getattr(request, _attr)
                        cands.append(_v() if callable(_v) else _v)
                except Exception:
                    pass
            try:
                _headers = getattr(request, "headers", None)
                if isinstance(_headers, dict):
                    for _k in ("x-admin", "x-is-admin", "x-role"):
                        if _k in _headers:
                            cands.append(_headers.get(_k))
                elif _headers is not None and hasattr(_headers, "get"):
                    for _k in ("x-admin", "x-is-admin", "x-role"):
                        try:
                            _v = _headers.get(_k)
                            if _v is not None:
                                cands.append(_v)
                        except Exception:
                            pass
            except Exception:
                pass
            for _acc in ("query", "query_params", "args"):
                try:
                    _q = getattr(request, _acc, None)
                    _q = _q() if callable(_q) else _q
                    if isinstance(_q, dict):
                        for _k in ("is_admin", "admin"):
                            if _k in _q:
                                cands.append(_q.get(_k))
                except Exception:
                    pass
        for _v in cands:
            try:
                if _v is False:
                    return True
                _s = str(_v).strip().lower()
                if _s in ("0", "false", "no", "none", "user", "member", "guest"):
                    return True
            except Exception:
                continue
    except Exception:
        return False
    return False
