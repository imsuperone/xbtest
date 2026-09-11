# -*- coding: utf-8 -*-
"""API helpers — _err / _raw_file_response / get_req_query / get_req_json 统一出口"""
import inspect
import json
import os
try:
    from ..adapters import json_response, _orig_error_response
except ImportError:
    try:
        from core.adapters import json_response, _orig_error_response  # type: ignore
    except ImportError:
        try:
            from astrbot.api.web import json_response, error_response as _orig_error_response
        except Exception:
            def json_response(data, *args, **kwargs):
                return data

            def _orig_error_response(msg, code=500):
                return {"error": msg, "code": code}


def _err(msg, code=500):
    try:
        return _orig_error_response(msg, code)
    except TypeError:
        try:
            return _orig_error_response(msg)
        except Exception:
            return json_response({"error": msg, "code": code})


def no_cache_response(resp):
    """为 Response 对象注入禁用缓存响应头，杜绝浏览器与中间代理缓存 GET API"""
    try:
        if hasattr(resp, "headers"):
            resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            resp.headers["Pragma"] = "no-cache"
            resp.headers["Expires"] = "0"
    except Exception:
        pass
    return resp


def _raw_file_response(data_bytes, filename):
    try:
        from aiohttp.web import Response as AioResponse  # type: ignore
        return AioResponse(body=data_bytes, headers={"Content-Disposition": f'attachment; filename="{filename}"', "Content-Type": "application/octet-stream"})
    except Exception:
        pass
    try:
        from quart import Response as QuartResponse  # type: ignore
        return QuartResponse(data_bytes, headers={"Content-Disposition": f'attachment; filename="{filename}"'}, mimetype="application/octet-stream")
    except Exception:
        pass
    try:
        from starlette.responses import Response as StarResponse  # type: ignore
        return StarResponse(content=data_bytes, headers={"Content-Disposition": f'attachment; filename="{filename}"'}, media_type="application/octet-stream")
    except Exception:
        pass
    return None


def get_req_query(request, key, default=""):
    """跨框架安全提取 URL 查询参数 (支持 aiohttp / quart / starlette / dict / None)"""
    req = request
    if req is None:
        try:
            from astrbot.api.web import request as _web_req
            req = _web_req
        except Exception:
            try:
                from quart import request as _quart_req
                req = _quart_req
            except Exception:
                pass
    if req is None:
        return default
    try:
        if hasattr(req, "args") and req.args is not None:
            v = req.args.get(key, default)
            return str(v) if v is not None else default
    except Exception:
        pass
    try:
        if hasattr(req, "query") and req.query is not None:
            v = req.query.get(key, default)
            return str(v) if v is not None else default
    except Exception:
        pass
    try:
        if hasattr(req, "query_params") and req.query_params is not None:
            v = req.query_params.get(key, default)
            return str(v) if v is not None else default
    except Exception:
        pass
    try:
        if isinstance(req, dict):
            v = req.get(key, default)
            return str(v) if v is not None else default
    except Exception:
        pass
    return default


async def get_req_json(request, default=None):
    """跨框架安全提取 JSON Body (支持 Quart / aiohttp / starlette / FastAPI / dict / None)"""
    if default is None:
        default = {}
    req = request
    if req is None:
        try:
            from astrbot.api.web import request as _web_req
            req = _web_req
        except Exception:
            try:
                from quart import request as _quart_req
                req = _quart_req
            except Exception:
                pass
    if req is None:
        return default
    if isinstance(req, dict):
        return req

    # 1. Quart 优先: request.get_json() (官方异步方法)
    try:
        if hasattr(req, "get_json") and callable(req.get_json):
            res = req.get_json()
            if inspect.isawaitable(res):
                res = await res
            if isinstance(res, dict):
                return res
            elif isinstance(res, str) and res.strip():
                try:
                    p = json.loads(res)
                    if isinstance(p, dict):
                        return p
                except Exception:
                    pass
    except Exception:
        pass

    # 2. 检查 request.json 属性 (Quart 下为 async property，访问时返回 coroutine；其它框架为 dict 或 callable)
    try:
        j = getattr(req, "json", None)
        if j is not None:
            if inspect.isawaitable(j):
                res = await j
                if isinstance(res, dict):
                    return res
                elif isinstance(res, str) and res.strip():
                    try:
                        p = json.loads(res)
                        if isinstance(p, dict):
                            return p
                    except Exception:
                        pass
            elif callable(j):
                res = j()
                if inspect.isawaitable(res):
                    res = await res
                if isinstance(res, dict):
                    return res
                elif isinstance(res, str) and res.strip():
                    try:
                        p = json.loads(res)
                        if isinstance(p, dict):
                            return p
                    except Exception:
                        pass
            elif isinstance(j, dict):
                return j
    except Exception:
        pass

    # 3. 尝试 request.get_data() (Quart 获取原始 bytes)
    try:
        if hasattr(req, "get_data") and callable(req.get_data):
            raw = req.get_data()
            if inspect.isawaitable(raw):
                raw = await raw
            if raw:
                if isinstance(raw, (bytes, bytearray)):
                    raw = raw.decode("utf-8", errors="ignore")
                if isinstance(raw, str) and raw.strip():
                    parsed = json.loads(raw)
                    if isinstance(parsed, dict):
                        return parsed
    except Exception:
        pass

    # 4. 尝试 request.read() (aiohttp / starlette)
    try:
        if hasattr(req, "read") and callable(req.read):
            raw = req.read()
            if inspect.isawaitable(raw):
                raw = await raw
            if raw:
                parsed = json.loads(raw.decode("utf-8", errors="ignore"))
                if isinstance(parsed, dict):
                    return parsed
    except Exception:
        pass

    # 5. 尝试 request.body (FastAPI / Starlette)
    try:
        if hasattr(req, "body"):
            raw = req.body
            if inspect.isawaitable(raw):
                raw = await raw
            elif callable(raw):
                raw = raw()
                if inspect.isawaitable(raw):
                    raw = await raw
            if isinstance(raw, (bytes, bytearray)):
                raw = raw.decode("utf-8", errors="ignore")
            if isinstance(raw, str) and raw.strip():
                parsed = json.loads(raw)
                if isinstance(parsed, dict):
                    return parsed
    except Exception:
        pass

    # 6. 尝试 request.form (表单兼容)
    try:
        f = getattr(req, "form", None)
        if f is not None:
            if inspect.isawaitable(f):
                f = await f
            elif callable(f):
                f = f()
                if inspect.isawaitable(f):
                    f = await f
            if f and isinstance(f, dict):
                return dict(f)
    except Exception:
        pass

    # 7. 尝试 request.post() (aiohttp 表单兼容)
    try:
        if hasattr(req, "post") and callable(req.post):
            res = req.post()
            if inspect.isawaitable(res):
                res = await res
            if res:
                return dict(res)
    except Exception:
        pass

    return default


def plugin_root(anchor_file):
    """插件根目录单源（core/api/* 深度固定 dirname×3；images/weapon_pool/gacha 三处同值收口）"""
    try:
        p = os.path.abspath(anchor_file)
        for _ in range(3):
            p = os.path.dirname(p)
        return p
    except Exception:
        return ""


async def read_upload_b64(request):
    """base64 直传提取（iframe 桥 postMessage 无法克隆 FormData 时用）：返回 (filename, bytes)。
    与旧 images/weapon_pool 内联 14 行逐行等价，抽取后零语义差。"""
    try:
        pj = await get_req_json(request, default={})
        if isinstance(pj, dict):
            b64_name = str(pj.get("filename", "") or "").strip()
            _b64s = str(pj.get("file_base64", "") or pj.get("data", "") or "")
            if "," in _b64s:
                _b64s = _b64s.split(",", 1)[1]
            if _b64s.strip():
                import base64
                return b64_name, base64.b64decode(_b64s.strip())
    except Exception:
        pass
    return "", b""

