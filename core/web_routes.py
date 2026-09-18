# -*- coding: utf-8 -*-
"""core/web_routes - Web API 注册表单源（原 app.py 纯数据段独立，零逻辑）。

改路由只改此表；app.py 以兼容导入取表，老 `from core.app import _XB_API_ROUTES` 仍可用。
"""


# Web API 注册表：(路径后缀, 方法, 处理器属性名, 说明)
# 与下方 page_* 薄包装一一对应；改路由只改此表
_XB_API_ROUTES = [
    ("stats", "GET", "page_stats", "游戏数据总览"),
    ("rank", "GET", "page_rank", "排行榜"),
    ("config/get", "GET", "page_cfg_get", "读取运行配置"),
    ("config/save", "POST", "page_cfg_save", "保存运行配置"),
    ("config/auto_balance", "POST", "page_config_auto_balance", "游戏数值智能平衡一键匹配"),
    ("config/balance_state", "GET", "page_balance_state", "平衡档位真实状态与漂移检测"),
    ("analytics/overview", "GET", "page_analytics_overview", "群生态与经济运行大屏数据"),
    ("users/airdrop", "POST", "page_users_airdrop", "全员/群聊批量福利空投"),
    ("config/schema", "GET", "page_cfg_schema", "配置schema(按节分组)"),
    ("user/export", "GET,POST", "page_user_export", "导出单用户数据"),
    ("user/import", "POST", "page_user_import", "导入单用户数据"),
    ("users/export", "GET,POST", "page_users_export", "导出全量用户数据"),
    ("users/import", "POST", "page_users_import", "导入全量用户数据"),
    ("users/clean_left", "POST", "page_users_clean_left", "清理退群人员数据"),
    ("commands", "GET", "page_commands", "指令一览"),
    ("users", "GET", "page_users", "用户/财富列表"),
    ("user/edit", "POST", "page_user_edit", "编辑用户数据(金币/体力/魅力/奖券)"),
    ("user/clear", "POST", "page_user_clear", "清除单用户数据(含奴隶与精灵并可重领新手礼包)"),
    ("images/list", "GET", "page_images_list", "图片目录浏览"),
    ("images/upload", "POST", "page_images_upload", "上传图片"),
    ("images/delete", "POST", "page_images_delete", "删除图片"),
    ("images/rename", "POST", "page_images_rename", "重命名图片"),
    ("images/mkdir", "POST", "page_images_mkdir", "新建文件夹"),
    ("images/thumb", "GET,POST", "page_images_thumb", "单张图片预览"),
    ("images/text", "GET", "page_images_text", "文本文件在线浏览"),
    ("images/text/save", "POST", "page_images_text_save", "保存文本文件内容"),
    ("images/copy", "POST", "page_images_copy", "复制文件"),
    ("images/export", "GET,POST", "page_images_export", "导出文件"),
    ("spirits", "GET", "page_spirits_get", "精灵图鉴读取"),
    ("spirits/save", "POST", "page_spirits_save", "精灵图鉴保存"),
    ("gacha/weapons", "GET", "page_gacha_weapons", "抽奖武器池"),
    ("weapons/pool", "GET", "page_pool_list", "抽奖武器池文件列表"),
    ("weapons/pool/rename", "POST", "page_pool_rename", "抽奖武器改名"),
    ("weapons/pool/move", "POST", "page_pool_move", "抽奖武器改稀有度"),
    ("weapons/pool/delete", "POST", "page_pool_delete", "抽奖武器删除"),
    ("weapons/pool/upload", "POST", "page_pool_upload", "抽奖武器上传"),
    ("weapons/pool/img", "GET,POST", "page_pool_img", "抽奖武器单张预览"),
    ("weapons/pool/attrs", "POST", "page_pool_attrs", "抽奖武器属性保存"),
    ("weapons/pool/replace_path", "POST", "page_pool_replace_path", "抽奖武器内置选图"),
    ("backups/list", "GET", "page_backups_list", "备份列表"),
    ("backups/restore", "POST", "page_backups_restore", "恢复备份"),
    ("backups/delete", "POST", "page_backups_delete", "删除备份"),
    ("backups/config/snapshots", "GET", "page_cfg_snapshots", "配置快照列表"),
    ("backups/config/snapshot/save", "POST", "page_cfg_snapshot_save", "保存配置快照"),
    ("backups/config/snapshot/restore", "POST", "page_cfg_snapshot_restore", "恢复配置快照"),
    ("backups/export", "GET,POST", "page_backups_export", "导出备份"),
    ("backups/doctor", "POST", "page_db_doctor", "数据库健康体检与碎片整理"),
    ("backups/prune", "POST", "page_backups_prune", "按保留数量修剪本地与云端旧备份"),
    ("import/legacy", "POST", "page_import_legacy", "旧库导入（兼容新旧格式）"),
    ("slave/users", "GET", "page_slave_users", "奴隶用户列表"),
    ("slave/calibrate", "POST", "page_slave_calibrate", "一键校准全员身价"),
    ("spirit/users", "GET", "page_spirit_users", "精灵用户列表"),
    ("groups/list", "GET", "page_groups_list", "群聊列表"),
    ("groups/toggle", "POST", "page_groups_toggle", "切换群聊/总开关"),
    ("groups/delete", "POST", "page_groups_delete", "删除群聊配置"),
    ("admin/clear", "POST", "page_clear_all", "清空所有数据（三重确认）"),
    ("version/check", "GET,POST", "page_version_check", "在线检查版本更新"),
    ("version/channel", "GET,POST", "page_version_channel", "更新通道查询与切换"),
    ("logs", "GET,POST", "page_logs_get", "获取插件运行日志"),
    ("logs/clear", "POST", "page_logs_clear", "清空插件运行日志"),
    ("logs/export", "GET,POST", "page_logs_export", "导出插件运行日志"),
]

# WebDAV 双前缀别名表（backup/ 与 backups/ 同义，由循环展开注册）
_XB_WEBDAV_ROUTES = [
    ("webdav/test", "GET,POST", "page_webdav_test", "测试WebDAV连接"),
    ("webdav/upload", "POST", "page_webdav_backup_now", "立即上传WebDAV备份"),
    ("webdav/files", "GET,POST", "page_webdav_files", "获取WebDAV远端备份文件列表"),
    ("webdav/restore", "POST", "page_webdav_restore", "从WebDAV远端备份恢复数据"),
    ("webdav/delete", "POST", "page_webdav_delete", "删除WebDAV远端备份"),
]

# 写操作 handler 名集合：_call_api 对其做显式非管理员标记的失败关闭检查。
# 注意：AstrBot 宿主鉴权契约未在本仓提供，缺标记时交由宿主 dashboard 会话判定；
# 此处绝不因“无标记”而放行日志以外的结论，也不因猜测 header 而拦截正常管理台。
_XB_MUTATING_HANDLERS = frozenset({
    "page_cfg_save", "page_config_auto_balance",
    "page_users_airdrop", "page_user_edit", "page_user_clear",
    "page_users_clean_left", "page_user_import", "page_users_import",
    "page_spirits_save",
    "page_pool_rename", "page_pool_move", "page_pool_delete",
    "page_pool_upload", "page_pool_attrs", "page_pool_replace_path",
    "page_backups_restore", "page_backups_delete",
    "page_cfg_snapshot_save", "page_cfg_snapshot_restore",
    "page_backups_prune", "page_db_doctor", "page_clear_all",
    "page_images_upload", "page_images_delete", "page_images_rename",
    "page_images_mkdir", "page_images_copy", "page_images_text_save",
    "page_import_legacy", "page_groups_toggle", "page_groups_delete",
    "page_logs_clear",
    "page_webdav_backup_now", "page_webdav_restore", "page_webdav_delete",
    "page_slave_calibrate",
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
