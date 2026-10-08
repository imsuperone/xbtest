# -*- coding: utf-8 -*-
"""导出统一入口 API — GET/POST /export?kind=images|backup|logs（V13：三导出接口合一）。

三域实现各归各家（images.export_images / backup.export_backup / logs.export_logs），
本模块只做 kind 解析与分发。kind 约定恒走 query（前端统一 apiGet），query 缺失才读
一次 body 兜底（get_req_json 非必缓存，分发层只读这一次，域实现自按 query 优先取参）。"""
from .web_utils import _err, get_req_json, get_req_query


async def handle_export(request, plugin_base=""):
    """/export 统一入口：?kind=images|backup|logs 分派到对应域实现；缺失/未知 kind → 400。"""
    kind = (get_req_query(request, "kind", "") or "").strip().lower()
    if not kind:
        try:
            body = await get_req_json(request, default={})
            if isinstance(body, dict):
                kind = str(body.get("kind") or "").strip().lower()
        except Exception:
            kind = ""
    if kind in ("images", "image", "img"):
        from .images import export_images
        return await export_images(request, plugin_base)
    if kind in ("backup", "backups"):
        from .backup import export_backup
        return await export_backup(request, plugin_base)
    if kind in ("logs", "log"):
        from .logs import export_logs
        return await export_logs(request, plugin_base)
    return _err("kind required (images|backup|logs)", 400)
