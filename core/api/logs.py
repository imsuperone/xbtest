"""logs API - 运行日志查看/清空/导出（原 stats.py 并入段独立，端点不变）"""
# -*- coding: utf-8 -*-
import asyncio
import datetime
import functools
import os
try:
    from ..adapters import json_response
except ImportError:
    from core.adapters import json_response
from .web_utils import _err, get_req_query, get_req_json
try:
    from .. import storage as ST
except ImportError:
    from core import storage as ST  # type: ignore
logger = ST.dual_attr(__package__, "logger", "..", "core")


# ==================== 日志（原 logs.py 并入） ====================

async def handle_logs_get(request=None):
    try:
        from .web_utils import get_req_json
        body = await get_req_json(request, {})
        limit_str = get_req_query(request, "limit", "") or (body.get("limit") if isinstance(body, dict) else "") or "200"
        level = get_req_query(request, "level", "") or (body.get("level") if isinstance(body, dict) else "") or ""
        if str(level).strip().upper() == "ALL":
            level = ""
        keyword = get_req_query(request, "keyword", "") or (body.get("keyword") if isinstance(body, dict) else "") or ""

        try:
            limit = int(limit_str)
        except Exception:
            limit = 200
        limit = max(1, min(limit, 1000))  # API 层钳制：防传百万读爆（底层另有 1000 硬上限）

        # 日志文件读 + 正则过滤走线程池，不堵消息循环
        data = await asyncio.to_thread(
            functools.partial(logger.get_logs, limit=limit, level=level, keyword=keyword))
        return json_response({
            "status": "ok",
            "result": data,
            "logs": data.get("logs", []),
            "count": data.get("count", 0),
            "total_lines": data.get("total_lines", 0),
            "file_size_kb": data.get("file_size_kb", 0),
            "max_file_mb": data.get("max_file_mb", 2.0),
        })
    except Exception as e:
        return _err(f"获取日志失败: {e}", 500)


async def handle_logs_clear(request=None):
    try:
        ok = await asyncio.to_thread(logger.clear_logs)
        if ok:
            return json_response({"status": "ok", "message": "插件日志已清空"})
        else:
            return _err("清空日志失败", 500)
    except Exception as e:
        return _err(f"清空日志异常: {e}", 500)


async def handle_logs_export(request=None):
    try:
        log_path = logger.get_log_file_path()

        def _work():
            if os.path.isfile(log_path):
                with open(log_path, "r", encoding="utf-8", errors="replace") as f:
                    return f.read()
            return ""

        content_str = await asyncio.to_thread(_work)

        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"xb_logs_{ts}.log"

        return json_response({
            "status": "ok",
            "filename": filename,
            "content": content_str
        })
    except Exception as e:
        return _err(f"导出日志失败: {e}", 500)
