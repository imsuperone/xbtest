# -*- coding: utf-8 -*-
"""图片/文件库 API — 浏览/上传/删除/重命名/新建/复制/导出"""
import asyncio
import base64
import os
import time
from astrbot.api.web import json_response

from .web_utils import _err, get_req_query, get_req_json

try:
    from .. import storage as ST
except ImportError:
    from core import storage as ST

def _img_base(plugin_base=""):
    if plugin_base:
        return plugin_base
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _safe_path(rel, base=""):
    b = base or _img_base()
    p = os.path.abspath(os.path.join(b, str(rel or "").strip().lstrip("/\\")))
    # 允许访问插件根及其子目录
    if p != b and not p.startswith(b + os.sep):
        # 也允许 data 与 persistent 目录
        data_base = os.path.join(b, "data")
        pers_base = ST.get_persistent_data_dir(b) if hasattr(ST, "get_persistent_data_dir") else data_base
        if (p != data_base and not p.startswith(data_base + os.sep)) and (p != pers_base and not p.startswith(pers_base + os.sep)):
            # 宽松：只要在插件根下即可
            if not p.startswith(b):
                return None
    return p


async def handle_images_list(request, plugin_base=""):
    rel = get_req_query(request, "dir", "") or get_req_query(request, "path", "")
    base = _img_base(plugin_base)
    root = _safe_path(rel, base)
    if not root:
        return _err("bad dir", 400)

    def _work():
        if not os.path.exists(root):
            return {"dir": str(rel or ""), "dirs": [], "files": []}
        if os.path.isfile(root):
            # 单文件
            try:
                sz = f"{os.path.getsize(root)//1024}KB"
                mtime = time.strftime("%Y-%m-%d %H:%M", time.localtime(os.path.getmtime(root)))
            except Exception:
                sz = ""; mtime = ""
            return {"dir": str(rel or ""), "dirs": [], "files": [{"name": os.path.basename(root), "path": rel, "size": sz, "mtime": mtime}]}
        dirs, files = [], []
        for name in sorted(os.listdir(root)):
            f = os.path.join(root, name)
            r = os.path.relpath(f, base).replace(os.sep, "/")
            if os.path.isdir(f):
                try:
                    mtime = time.strftime("%Y-%m-%d %H:%M", time.localtime(os.path.getmtime(f)))
                except Exception:
                    mtime = ""
                dirs.append({"name": name, "path": r, "mtime": mtime})
            elif os.path.isfile(f):
                try:
                    sz = f"{os.path.getsize(f)//1024}KB"
                    mtime = time.strftime("%Y-%m-%d %H:%M", time.localtime(os.path.getmtime(f)))
                except Exception:
                    sz = ""; mtime = ""
                files.append({"name": name, "path": r, "size": sz, "mtime": mtime})
        dirs.sort(key=lambda x: x["name"])
        files.sort(key=lambda x: x["name"])
        return {"dir": str(rel or ""), "dirs": dirs, "files": files}
    data = await asyncio.to_thread(_work)
    return json_response(data)


async def handle_images_upload(request, plugin_base=""):
    form = {}
    try:
        form = await request.files()
    except Exception:
        form = {}
    f = None
    if isinstance(form, dict):
        f = form.get("file")
        if not f:
            for _k in ("files", "fileUpload", "upload", "data"):
                if _k in form:
                    f = form.get(_k)
                    if f:
                        break
    else:
        if hasattr(form, "filename") or hasattr(form, "read"):
            f = form
    # base64 直传（iframe 桥 postMessage 无法克隆 FormData 时用）
    b64_name, b64_data = "", b""
    if not f:
        try:
            pj = await get_req_json(request, default={})
            if isinstance(pj, dict):
                b64_name = str(pj.get("filename", "") or "").strip()
                _b64s = str(pj.get("file_base64", "") or pj.get("data", "") or "")
                if "," in _b64s:
                    _b64s = _b64s.split(",", 1)[1]
                if _b64s.strip():
                    b64_data = base64.b64decode(_b64s.strip())
        except Exception:
            b64_data = b""
    if not f and not b64_data:
        return _err("no file", 400)
    # 目标目录
    target_dir = get_req_query(request, "dir", "") or get_req_query(request, "path", "")
    if not target_dir:
        try:
            p = await get_req_json(request, default={})
            if isinstance(p, dict):
                target_dir = str(p.get("dir", "") or p.get("path", "") or "").strip()
        except Exception:
            pass
    base = _img_base(plugin_base)
    # 默认上传到 data/img/gacha
    if not target_dir:
        target_dir = "data/img/gacha"
    dst_dir = _safe_path(target_dir, base)
    if not dst_dir:
        return _err("bad dir", 400)
    if b64_data:
        filename = os.path.basename(b64_name or "upload.bin")
        data = bytes(b64_data)
    else:
        filename = str(getattr(f, "filename", None) or getattr(f, "name", None) or "upload.bin").strip()
        filename = os.path.basename(filename)
        # 文件内容在事件循环上读出（ plc 适配器 read 可能是 awaitable），落盘进线程池
        data = b""
        try:
            val = f.read() if hasattr(f, "read") else None
            if val is not None:
                import inspect
                if inspect.isawaitable(val):
                    data = await val
                elif callable(getattr(f, "read", None)):
                    data = val
                else:
                    data = val
            if not data and hasattr(f, "file"):
                try:
                    ff = getattr(f, "file")
                    if hasattr(ff, "read"):
                        data = ff.read()
                except Exception:
                    pass
        except Exception:
            data = b""
        if isinstance(data, str):
            data = data.encode("utf-8", errors="ignore")
        if not isinstance(data, (bytes, bytearray)):
            try:
                data = bytes(data)
            except Exception:
                data = b""

    def _work():
        try:
            os.makedirs(dst_dir, exist_ok=True)
            dst = os.path.join(dst_dir, filename)
            with open(dst, "wb") as w:
                w.write(data)
            return json_response({"ok": True, "path": os.path.relpath(dst, base).replace(os.sep, "/"), "size": len(data)})
        except Exception as e:
            return _err(f"upload failed: {e}", 500)

    return await asyncio.to_thread(_work)


async def handle_images_delete(request, plugin_base=""):
    p = await get_req_json(request, default={})
    rel = str((p.get("path") or p.get("file") or "") if isinstance(p, dict) else "").strip()
    if not rel:
        rel = get_req_query(request, "path", "") or get_req_query(request, "file", "")
    rel = str(rel).strip()
    if not rel:
        return _err("path required", 400)
    base = _img_base(plugin_base)
    fp = _safe_path(rel, base)
    if not fp or not os.path.exists(fp):
        return _err("file not found", 404)

    def _work():
        try:
            import shutil
            if os.path.isfile(fp):
                os.remove(fp)
            elif os.path.isdir(fp):
                shutil.rmtree(fp)
            return json_response({"ok": True, "path": rel})
        except Exception as e:
            return _err(f"delete failed: {e}", 500)

    return await asyncio.to_thread(_work)


async def handle_images_rename(request, plugin_base=""):
    p = await get_req_json(request, default={})
    src = str((p.get("path") or p.get("src") or p.get("file") or "") if isinstance(p, dict) else "").strip()
    dst = str((p.get("new") or p.get("dst") or p.get("name") or "") if isinstance(p, dict) else "").strip()
    if not src or not dst:
        return _err("path and new required", 400)
    base = _img_base(plugin_base)
    fp = _safe_path(src, base)
    if not fp or not os.path.exists(fp):
        return _err("src not found", 404)
    # dst 可能是新文件名或新路径
    if "/" in dst or "\\" in dst:
        np = _safe_path(dst, base)
    else:
        np = os.path.join(os.path.dirname(fp), dst)
        np = _safe_path(os.path.relpath(np, base), base)
    if not np:
        return _err("bad dst", 400)

    def _work():
        try:
            os.rename(fp, np)
            return json_response({"ok": True, "path": os.path.relpath(np, base).replace(os.sep, "/")})
        except Exception as e:
            return _err(f"rename failed: {e}", 500)

    return await asyncio.to_thread(_work)


async def handle_images_thumb(request, plugin_base=""):
    """单张图片缩略图（base64 data URI，≤200KB，用于管理页预览，列表不批量下发）"""
    p = await get_req_json(request, default={})
    rel = str((p.get("path") or p.get("file") or "") if isinstance(p, dict) else "").strip()
    if not rel:
        rel = get_req_query(request, "path", "") or get_req_query(request, "file", "")
    rel = str(rel).strip()
    if not rel:
        return _err("path required", 400)
    base = _img_base(plugin_base)
    fp = _safe_path(rel, base)
    if not fp or not os.path.isfile(fp):
        return _err("file not found", 404)

    def _work():
        try:
            if os.path.getsize(fp) > 200 * 1024:
                return _err("too large", 400)
            with open(fp, "rb") as f:
                raw = f.read()
            if not raw:
                return _err("empty file", 400)
            ext = os.path.splitext(fp)[1].lower().lstrip(".") or "png"
            if ext == "jpg":
                ext = "jpeg"
            return json_response({"ok": True, "path": rel,
                                  "thumb": "data:image/%s;base64,%s" % (ext, base64.b64encode(raw).decode("ascii"))})
        except Exception as e:
            return _err(f"thumb failed: {e}", 500)

    return await asyncio.to_thread(_work)


async def handle_images_mkdir(request, plugin_base=""):
    p = await get_req_json(request, default={})
    rel = str((p.get("path") or p.get("dir") or p.get("name") or "") if isinstance(p, dict) else "").strip()
    if not rel:
        rel = get_req_query(request, "path", "") or get_req_query(request, "dir", "")
    rel = str(rel).strip()
    if not rel:
        return _err("path required", 400)
    base = _img_base(plugin_base)
    fp = _safe_path(rel, base)
    if not fp:
        return _err("bad path", 400)

    def _work():
        try:
            os.makedirs(fp, exist_ok=True)
            return json_response({"ok": True, "path": rel})
        except Exception as e:
            return _err(f"mkdir failed: {e}", 500)

    return await asyncio.to_thread(_work)


async def handle_images_copy(request, plugin_base=""):
    p = await get_req_json(request, default={})
    src = str((p.get("src") or p.get("path") or "") if isinstance(p, dict) else "").strip()
    dst = str((p.get("dst") or p.get("new") or "") if isinstance(p, dict) else "").strip()
    if not src or not dst:
        return _err("src and dst required", 400)
    base = _img_base(plugin_base)
    sp = _safe_path(src, base)
    dp = _safe_path(dst, base)
    if not sp or not dp or not os.path.exists(sp):
        return _err("src not found", 404)

    def _work():
        try:
            import shutil
            if os.path.isdir(sp):
                shutil.copytree(sp, dp)
            else:
                os.makedirs(os.path.dirname(dp), exist_ok=True)
                shutil.copy2(sp, dp)
            return json_response({"ok": True, "src": src, "dst": dst})
        except Exception as e:
            return _err(f"copy failed: {e}", 500)

    return await asyncio.to_thread(_work)


async def handle_images_export(request, plugin_base=""):
    rel = get_req_query(request, "path", "") or get_req_query(request, "file", "")
    if not rel:
        try:
            p = await get_req_json(request, default={})
            if isinstance(p, dict):
                rel = str(p.get("path") or p.get("file") or "").strip()
        except Exception:
            pass
    if rel in ("0", "/", "\\"):
        rel = ""
    base = _img_base(plugin_base)
    fp = _safe_path(rel, base)
    if not fp or not os.path.exists(fp):
        # 兜底：如果指定路径不存在，尝试 fallback 到根目录
        fp = base
        rel = ""

    def _work():
        if os.path.isdir(fp):
            import zipfile, io
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
                for root, dirs, files in os.walk(fp):
                    dirs[:] = [d for d in dirs if d not in ("__pycache__", ".git") and not (os.path.relpath(os.path.join(root, d), fp).replace("\\", "/").startswith("data/backups"))]
                    for fn in files:
                        if fn.endswith((".db-wal", ".db-shm", ".db-journal", ".pyc", ".tmp", ".lock", ".log", ".db")):
                            continue
                        if fn in ("webdav_secret.json", "config.json"):
                            continue
                        full_p = os.path.join(root, fn)
                        rel_p = os.path.relpath(full_p, fp)
                        if rel_p.replace("\\", "/").startswith("data/backups/"):
                            continue
                        try:
                            z.write(full_p, rel_p)
                        except Exception:
                            pass
            buf.seek(0)
            data = buf.read()
            b64 = base64.b64encode(data).decode()
            dirname = os.path.basename(fp) or "root"
            fn = f"{dirname}_{int(time.time())}.zip"
            return {"ok": True, "path": rel, "data": b64, "size": len(data), "filename": fn}
        else:
            if os.path.getsize(fp) > 50 * 1024 * 1024:
                raise ValueError("file too large")
            with open(fp, "rb") as f:
                data = f.read()
            b64 = base64.b64encode(data).decode()
            return {"ok": True, "path": rel, "data": b64, "size": len(data), "filename": os.path.basename(fp)}
    try:
        res = await asyncio.to_thread(_work)
        return json_response(res)
    except ValueError as e:
        return _err(str(e), 400)
    except Exception as e:
        return _err(f"export failed: {e}", 500)
