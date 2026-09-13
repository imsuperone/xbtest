# -*- coding: utf-8 -*-
"""图片/文件库 API — 浏览/上传/删除/重命名/新建/复制/导出"""
import asyncio
import base64
import os
import time
try:
    from ..adapters import json_response
except ImportError:
    from core.adapters import json_response

from .web_utils import _err, get_req_query, get_req_json, plugin_root, read_thumb_uri, read_upload_b64

try:
    from .. import storage as ST
except ImportError:
    from core import storage as ST

def _img_base(plugin_base=""):
    if plugin_base:
        return plugin_base
    return plugin_root(__file__)


def _inside(path, root, allow_root=True):
    """真实路径边界判断，拒绝同前缀目录和指向外部的符号链接。"""
    try:
        target = os.path.realpath(path)
        base = os.path.realpath(root)
        if not allow_root and target == base:
            return False
        return os.path.commonpath((target, base)) == base
    except (OSError, ValueError):
        return False


def _safe_path(rel, base=""):
    b = base or _img_base()
    p = os.path.join(b, str(rel or "").strip().lstrip("/\\"))
    if _inside(p, b):
        return os.path.realpath(p)
    data_base = os.path.join(b, "data")
    try:
        pers_base = ST.get_persistent_data_dir(b) if hasattr(ST, "get_persistent_data_dir") else data_base
    except Exception:
        pers_base = data_base
    if _inside(p, data_base) or _inside(p, pers_base):
        return os.path.realpath(p)
    return None


_BLOCKED_NAMES = {"webdav_secret.json", ".xb_last_backup.json", ".xb_backup.busy",
                  "xb_backup.lock", ".xb_backup.lock", "config.json"}
_BLOCKED_EXTS = (".db", ".db-wal", ".db-shm", ".db-journal")


def _is_blocked(fp):
    """敏感文件保护：密钥/数据库/运行配置禁读禁写删（备份走 backup.py，不走文件库）"""
    try:
        bn = os.path.basename(str(fp or ""))
        if bn in _BLOCKED_NAMES:
            return True
        return bn.lower().endswith(_BLOCKED_EXTS)
    except Exception:
        return True


def _in_data_roots(fp, base=""):
    """写操作域：只许 data/ 与 persistent 数据目录，禁插件根直写（防覆盖 core/*.py 提权）"""
    try:
        b = base or _img_base()
        data_base = os.path.join(b, "data")
        try:
            pers_base = ST.get_persistent_data_dir(b) if hasattr(ST, "get_persistent_data_dir") else ""
        except Exception:
            pers_base = ""
        for r in (data_base, pers_base):
            if r and _inside(fp, r):
                return True
    except Exception:
        pass
    return False


def _in_data_strict(fp, base=""):
    """严格内部：是 data/ 子项而非根自身（防删库/搬库级误操作）"""
    try:
        b = base or _img_base()
        data_base = os.path.join(b, "data")
        try:
            pers_base = ST.get_persistent_data_dir(b) if hasattr(ST, "get_persistent_data_dir") else ""
        except Exception:
            pers_base = ""
        for r in (data_base, pers_base):
            if r and fp and _inside(fp, r, allow_root=False):
                return True
    except Exception:
        pass
    return False


_IMG_UPLOAD_EXTS = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".ico")


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
        try:
            with os.scandir(root) as it:
                for entry in it:
                    try:
                        name = entry.name
                        r = os.path.relpath(entry.path, base).replace(os.sep, "/")
                        if entry.is_dir(follow_symlinks=False):
                            st = entry.stat(follow_symlinks=False)
                            mtime = time.strftime("%Y-%m-%d %H:%M", time.localtime(st.st_mtime))
                            dirs.append({"name": name, "path": r, "mtime": mtime})
                        elif entry.is_file(follow_symlinks=False):
                            st = entry.stat(follow_symlinks=False)
                            sz = f"{st.st_size // 1024}KB"
                            mtime = time.strftime("%Y-%m-%d %H:%M", time.localtime(st.st_mtime))
                            files.append({"name": name, "path": r, "size": sz, "mtime": mtime})
                    except Exception:
                        pass
        except Exception:
            pass
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
    # base64 直传（iframe 桥 postMessage 无法克隆 FormData 时用，见 web_utils.read_upload_b64）
    b64_name, b64_data = "", b""
    if not f:
        b64_name, b64_data = await read_upload_b64(request)
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
    if not _in_data_roots(dst_dir, base):
        return _err("dir out of scope (only data/ allowed)", 400)
    if b64_data:
        filename = os.path.basename(b64_name or "upload.bin")
        if _is_blocked(filename) or not filename.lower().endswith(_IMG_UPLOAD_EXTS):
            return _err("file type not allowed (images only)", 400)
        data = bytes(b64_data)
    else:
        filename = str(getattr(f, "filename", None) or getattr(f, "name", None) or "upload.bin").strip()
        filename = os.path.basename(filename)
        if _is_blocked(filename) or not filename.lower().endswith(_IMG_UPLOAD_EXTS):
            return _err("file type not allowed (images only)", 400)
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
    # 与 base64 直传对齐：multipart 同样 50M 上限（防大包堵 loop＋OOM）
    if len(data or b"") > 50 * 1024 * 1024:
        return _err("file too large (50M)", 400)

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
    if _is_blocked(fp) or not _in_data_strict(fp, base):
        return _err("path out of scope", 400)

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
    if _is_blocked(fp) or not _in_data_strict(fp, base):
        return _err("path out of scope", 400)
    # dst 可能是新文件名或新路径
    if "/" in dst or "\\" in dst:
        np = _safe_path(dst, base)
    else:
        np = os.path.join(os.path.dirname(fp), dst)
        np = _safe_path(os.path.relpath(np, base), base)
    if not np or _is_blocked(np) or not _in_data_roots(np, base):
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
        # 兼容旧路径与层级差异：data/img/ <-> data/games/img/
        candidates = []
        clean_rel = rel.replace("\\", "/")
        if clean_rel.startswith("data/img/"):
            candidates.append(clean_rel.replace("data/img/", "data/games/img/"))
        elif clean_rel.startswith("data/games/img/"):
            candidates.append(clean_rel.replace("data/games/img/", "data/img/"))
        # 纯文件名回退探测
        base_name = os.path.basename(clean_rel)
        if base_name:
            candidates.append(f"data/games/img/rides/{base_name}")
            candidates.append(f"data/games/img/nuli/SSR/{base_name}")
            candidates.append(f"data/games/img/nuli/SR/{base_name}")
            candidates.append(f"data/games/img/nuli/R/{base_name}")
        for c in candidates:
            cfp = _safe_path(c, base)
            if cfp and os.path.isfile(cfp):
                fp = cfp
                rel = c
                break
    if not fp or not os.path.isfile(fp):
        return _err(f"file not found: {rel}", 404)
    if _is_blocked(fp) or not _in_data_strict(fp, base):
        return _err("path out of scope", 400)

    def _work():
        try:
            st, payload = read_thumb_uri(fp)
            if st == "too large":
                return _err("too large", 400)
            if st == "empty":
                return _err("empty file", 400)
            if st != "ok":
                return _err(f"thumb failed: {payload}", 500)
            return json_response({"ok": True, "path": rel, "thumb": payload})
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
    if _is_blocked(fp) or not _in_data_roots(fp, base):
        return _err("path out of scope (only data/ allowed)", 400)

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
    if _is_blocked(sp) or _is_blocked(dp) or not _in_data_strict(sp, base) or not _in_data_roots(dp, base):
        return _err("path out of scope", 400)

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
        # 坏路径直接 404：禁 fallback 打包插件根（拼错即全仓源码 dump）
        return _err("file not found", 404)
    if not _in_data_strict(fp, base):
        return _err("export only supports data files", 400)

    def _work():
        if os.path.isdir(fp):
            import zipfile, io
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
                for root, dirs, files in os.walk(fp, followlinks=False):
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
            if _is_blocked(fp):
                raise ValueError("file out of scope")
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
