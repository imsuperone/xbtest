# -*- coding: utf-8 -*-
"""core/api/pool.py — 抽奖武器池文件管理（原 game.py 池段切分，语义不变）。"""
import asyncio
import json
import os as _os
import re
import shutil as _shutil
from astrbot.api.web import json_response
from .web_utils import _err, get_req_query, get_req_json, plugin_root, read_thumb_uri, read_upload_b64
try:
    from .. import storage as ST
    from ...games import slave
except ImportError:
    from core import storage as ST
    try:
        from games import slave
    except ImportError:
        import slave  # type: ignore


async def handle_gacha_weapons(request):
    """抽奖武器池（img/gacha SSR/SR/R 文件名去扩展名；附精确图片路径供自动匹配预览）"""
    def _work():
        try:
            try:
                from ...games import slave as _sl
            except ImportError:
                import slave as _sl  # type: ignore
            try:
                _base = _pool_base()
            except Exception:
                _base = ""
            out, img = {}, {}
            for rar in ("SSR", "SR", "R"):
                try:
                    names = []
                    for p in (_sl._gacha_pool(rar) or []):
                        try:
                            nm = _os.path.splitext(_os.path.basename(p))[0]
                            names.append(nm)
                            try:
                                rp = _os.path.relpath(p, _base).replace(_os.sep, "/") if _base else ""
                                if rp and not rp.startswith(".."):
                                    img.setdefault(nm, rp)
                            except Exception:
                                pass
                        except Exception:
                            pass
                    out[rar] = sorted(set(names))
                except Exception:
                    out[rar] = []
            return json_response({"ok": True, "pool": out, "img": img})
        except Exception as e:
            return _err(f"gacha weapons failed: {e}", 500)
    return await asyncio.to_thread(_work)




try:
    from ...games.config.shop import POOL_RARS as _POOL_RARS, POOL_IMG_EXTS as _POOL_IMG_EXTS
except ImportError:
    from games.config.shop import POOL_RARS as _POOL_RARS, POOL_IMG_EXTS as _POOL_IMG_EXTS  # type: ignore
_POOL_THUMB_MAX = 200 * 1024




def _pool_slave():
    try:
        from ...games import slave as _sl
        return _sl
    except ImportError:
        import slave as _sl  # type: ignore
        return _sl




def _pool_base():
    try:
        return plugin_root(__file__)
    except Exception:
        return ""




def _pool_dir(rar):
    """生效稀有度目录（与引擎 _gacha_pool 同口径：持久化优先）"""
    _sl = _pool_slave()
    try:
        files = _sl._gacha_pool(rar) or []
        if files:
            return _os.path.dirname(_os.path.abspath(files[0]))
    except Exception:
        pass
    base = _pool_base()
    try:
        pers = ST.get_persistent_data_dir(base) if hasattr(ST, "get_persistent_data_dir") else ""
    except Exception:
        pers = ""
    _seed_pkg = _os.path.join(base, "data", "games", "img", "nuli", rar)
    _seed_old = _os.path.join(pers or _os.path.join(base, "data"), "img", "gacha", rar)
    _seed_new = _os.path.join(pers or _os.path.join(base, "data"), "img", "nuli", rar)
    d = _seed_old if _os.path.isdir(_seed_old) else (_seed_new if _os.path.isdir(_seed_new) else _seed_pkg)
    try:
        _os.makedirs(d, exist_ok=True)
    except Exception:
        pass
    return d




def _pool_bust(rar=""):
    try:
        _sl = _pool_slave()
        if hasattr(_sl, "_GACHA_CACHE"):
            if rar:
                _sl._GACHA_CACHE.pop(rar, None)
                try:
                    _sl._GACHA_CACHE_TS.pop(rar, None)
                except Exception:
                    pass
            else:
                _sl._GACHA_CACHE.clear()
                try:
                    _sl._GACHA_CACHE_TS.clear()
                except Exception:
                    pass
    except Exception:
        pass




def _pool_clean_stem(s):
    s = str(s or "").strip()
    if not s or len(s) > 64 or s in (".", ".."):
        return ""
    if re.search(r'[\/\\:*?"<>|\x00-\x1f]', s):
        return ""
    return s




def _pool_find(stem):
    """按武器名找生效文件，返回 (rar, abspath) 或 (None, None)"""
    _sl = _pool_slave()
    want = str(stem or "")
    for rar in _POOL_RARS:
        try:
            for p in (_sl._gacha_pool(rar) or []):
                try:
                    if _os.path.splitext(_os.path.basename(p))[0] == want and _os.path.isfile(p):
                        return rar, _os.path.abspath(p)
                except Exception:
                    continue
        except Exception:
            continue
    return None, None




def _pool_thumb(p):
    # 与 images 缩略同语义（200KB 上限＋空/错回空串），实现收口 web_utils.read_thumb_uri
    try:
        st, uri = read_thumb_uri(p, _POOL_THUMB_MAX)
        return uri if st == "ok" else ""
    except Exception:
        return ""




def _pool_item(rar, p, base):
    try:
        fn = _os.path.basename(p)
        nm = _os.path.splitext(fn)[0]
        try:
            sz = _os.path.getsize(p)
        except Exception:
            sz = 0
        try:
            rp = _os.path.relpath(p, base).replace(_os.sep, "/") if base else ""
            if rp.startswith(".."):
                rp = ""
        except Exception:
            rp = ""
        return {"name": nm, "file": fn, "rar": rar, "img": rp, "size": sz}
    except Exception:
        return None




def _pool_write_file(rar, stem, data, ext):
    """写池文件：tmp+replace 原子；同茎旧文件（含残留 tmp）成功后清理；返回 abspath"""
    d = _pool_dir(rar)
    dst = _os.path.join(d, stem + ext)
    _tmp = dst + ".tmp"
    with open(_tmp, "wb") as w:
        w.write(data)
    try:
        for fn in _os.listdir(d):
            try:
                _fp = _os.path.join(d, fn)
                if not _os.path.isfile(_fp):
                    continue
                if fn == stem + ext or fn == _os.path.basename(_tmp):
                    continue
                if _os.path.splitext(fn)[0] == stem or (fn.startswith(stem) and fn.endswith(".tmp")):
                    _os.remove(_fp)
            except Exception:
                continue
    except Exception:
        pass
    _os.replace(_tmp, dst)
    _pool_bust(rar)
    return dst




async def handle_pool_list(request):
    """抽奖武器池列表（生效目录，附可配属性；无缩略图，预览按需取）"""
    def _work():
        try:
            _sl = _pool_slave()
            base = _pool_base()
            try:
                _attrs = _sl._weapon_attrs_raw() if hasattr(_sl, "_weapon_attrs_raw") else {}
                if not isinstance(_attrs, dict):
                    _attrs = {}
            except Exception:
                _attrs = {}
            try:
                _legacy = _sl._weapon_shop() if hasattr(_sl, "_weapon_shop") else {}
                if not isinstance(_legacy, dict):
                    _legacy = {}
            except Exception:
                _legacy = {}
            out = {}
            for rar in _POOL_RARS:
                items = []
                try:
                    for p in (_sl._gacha_pool(rar) or []):
                        it = _pool_item(rar, p, base)
                        if not it:
                            continue
                        try:
                            a = _attrs.get(it["name"]) or {}
                            if not isinstance(a, dict):
                                a = {}
                            atk = a.get("atk", "")
                            desc = a.get("desc", "")
                            if (atk in ("", None)) and isinstance(_legacy.get(it["name"]), dict):
                                atk = _legacy[it["name"]].get("atk", "")
                            if (not desc) and isinstance(_legacy.get(it["name"]), dict):
                                desc = _legacy[it["name"]].get("desc", "")
                            try:
                                atk = int(float(atk or 0))
                            except Exception:
                                atk = 0
                            it["attrs"] = {"atk": atk, "desc": str(desc or "")}
                        except Exception:
                            it["attrs"] = {"atk": 0, "desc": ""}
                        items.append(it)
                except Exception:
                    pass
                items.sort(key=lambda x: x["name"])
                out[rar] = items
            return json_response({"ok": True, "pool": out})
        except Exception as e:
            return _err(f"pool list failed: {e}", 500)

    return await asyncio.to_thread(_work)




async def handle_pool_attrs(request):
    """抽奖武器属性保存（{attrs: {名: {atk, desc}}, full: 0/1}，只写 weapon_attrs，不碰文件；
    默认合并：只更新 payload 出现的名；full=1 时全量替换（恢复默认用））"""
    try:
        data = await get_req_json(request, default={})
    except Exception as e:
        return _err(f"pool attrs failed: {e}", 500)
    if not isinstance(data, dict):
        return _err("bad payload", 400)
    raw = data.get("attrs", data)
    if not isinstance(raw, dict):
        return _err("attrs must be dict", 400)
    full = bool(data.get("full", False))

    def _work():
        try:
            try:
                _sl0 = _pool_slave()
                base0 = _sl0._weapon_attrs_raw() if hasattr(_sl0, "_weapon_attrs_raw") else {}
                merged = dict(base0) if isinstance(base0, dict) else {}
            except Exception:
                merged = {}
            if full:
                merged = {}
            for name, v in raw.items():
                name = str(name or "").strip()
                if not name:
                    continue
                if not isinstance(v, dict):
                    continue
                try:
                    atk = int(float(v.get("atk", 0) or 0))
                except Exception:
                    atk = 0
                if atk < 0:
                    atk = 0
                desc = str(v.get("desc", "") or "").strip()
                if atk or desc:
                    merged[name] = {"atk": atk, "desc": desc}
                elif name in merged:
                    merged.pop(name, None)
            clean = {k: v for k, v in merged.items() if isinstance(v, dict)}
            ST.set_ini("商城图鉴", "weapon_attrs", json.dumps(clean, ensure_ascii=False))
            try:
                ST.save_config()
            except Exception:
                pass
            try:
                st_cfg = dict(ST._CONFIG or {})
                ST.sync_astrbot_config(st_cfg)
            except Exception:
                pass
            return json_response({"ok": True, "count": len(clean)})
        except Exception as e:
            return _err(f"pool attrs failed: {e}", 500)

    return await asyncio.to_thread(_work)




async def handle_pool_replace_path(request):
    """内置选图：用服务器已有图片文件覆盖池武器图（{name, src}，src 须在插件/数据目录内）"""
    try:
        try:
            from .images import _safe_path as _img_safe
        except ImportError:
            from images import _safe_path as _img_safe  # type: ignore
        data = await get_req_json(request, default={})
    except Exception as e:
        return _err(f"pool replace failed: {e}", 500)
    if not isinstance(data, dict):
        return _err("bad payload", 400)
    name = str(data.get("name", "") or "").strip()
    src = str(data.get("src", "") or data.get("path", "") or "").strip()
    if not name or not src:
        return _err("name/src required", 400)
    name = _pool_clean_stem(name)
    if not name:
        return _err("name invalid", 400)
    rar = str(data.get("rar", "") or "").strip().upper()

    def _work():
        try:
            _rar, _old = _pool_find(name)
            if not _old:
                # 新建模式（添加武器用内置图）：rar 必传
                if rar not in _POOL_RARS:
                    return _err("not found, rar required to create", 404)
                use_rar = rar
            else:
                use_rar = _rar
            fp = _img_safe(src, _pool_base())
            if not fp or not _os.path.isfile(fp):
                return _err("源文件不存在或越界", 400)
            try:
                from .images import _is_blocked as _img_blocked
            except ImportError:
                from images import _is_blocked as _img_blocked  # type: ignore
            if _img_blocked(fp):
                return _err("源文件越界", 400)
            ext = _os.path.splitext(fp)[1].lower()
            if ext not in _POOL_IMG_EXTS:
                return _err("源文件非图片", 400)
            if _os.path.getsize(fp) > 5 * 1024 * 1024:
                return _err("源文件过大（限5MB）", 400)
            with open(fp, "rb") as f:
                blob = f.read()
            if not blob:
                return _err("源文件为空", 400)
            _pool_write_file(use_rar, name, blob, ext)
            return json_response({"ok": True, "name": name})
        except Exception as e:
            return _err(f"pool replace failed: {e}", 500)

    return await asyncio.to_thread(_work)




async def handle_pool_rename(request):
    """抽奖武器改名（仅改文件名主干，扩展名保留）"""
    try:
        data = await get_req_json(request, default={})
    except Exception as e:
        return _err(f"pool rename failed: {e}", 500)
    if not isinstance(data, dict):
        return _err("bad payload", 400)
    old = str(data.get("old", "") or data.get("name", "") or "").strip()
    new = _pool_clean_stem(data.get("new", ""))
    if not old or not new:
        return _err("old/new required", 400)

    def _work():
        try:
            rar, src = _pool_find(old)
            if not src:
                return _err("not found", 404)
            if new == old:
                return json_response({"ok": True, "name": new})
            dst = _os.path.join(_os.path.dirname(src), new + _os.path.splitext(src)[1])
            if _os.path.exists(dst):
                return _err("同名文件已存在", 400)
            _os.rename(src, dst)
            _pool_bust(rar)
            return json_response({"ok": True, "name": new})
        except Exception as e:
            return _err(f"pool rename failed: {e}", 500)

    return await asyncio.to_thread(_work)




async def handle_pool_move(request):
    """抽奖武器改稀有度（跨目录移动文件）"""
    try:
        data = await get_req_json(request, default={})
    except Exception as e:
        return _err(f"pool move failed: {e}", 500)
    if not isinstance(data, dict):
        return _err("bad payload", 400)
    name = str(data.get("name", "") or "").strip()
    to = str(data.get("to", "") or data.get("rar", "") or "").strip().upper()
    if not name or to not in _POOL_RARS:
        return _err("name/to required", 400)

    def _work():
        try:
            rar, src = _pool_find(name)
            if not src:
                return _err("not found", 404)
            if rar == to:
                return json_response({"ok": True, "rar": to})
            d = _pool_dir(to)
            dst = _os.path.join(d, _os.path.basename(src))
            if _os.path.exists(dst):
                return _err("目标稀有度已存在同名文件", 400)
            _shutil.move(src, dst)
            _pool_bust(rar)
            _pool_bust(to)
            return json_response({"ok": True, "rar": to})
        except Exception as e:
            return _err(f"pool move failed: {e}", 500)

    return await asyncio.to_thread(_work)




async def handle_pool_delete(request):
    """抽奖武器删除（删文件，需前端二次确认）"""
    try:
        data = await get_req_json(request, default={})
    except Exception as e:
        return _err(f"pool delete failed: {e}", 500)
    if not isinstance(data, dict):
        return _err("bad payload", 400)
    name = str(data.get("name", "") or "").strip()
    if not name:
        return _err("name required", 400)

    def _work():
        try:
            rar, src = _pool_find(name)
            if not src:
                return _err("not found", 404)
            _os.remove(src)
            _pool_bust(rar)
            return json_response({"ok": True})
        except Exception as e:
            return _err(f"pool delete failed: {e}", 500)

    return await asyncio.to_thread(_work)




async def handle_pool_img(request):
    """抽奖武器单张预览（按需取缩略图，列表不再批量下发）"""
    try:
        data = await get_req_json(request, default={})
    except Exception:
        data = {}
    name = ""
    if isinstance(data, dict):
        name = str(data.get("name", "") or "").strip()
    if not name:
        try:
            name = (get_req_query(request, "name", "") or "").strip()
        except Exception:
            name = ""
    if not name:
        return _err("name required", 400)

    def _work():
        try:
            _, src = _pool_find(name)
            if not src:
                return _err("not found", 404)
            thumb = _pool_thumb(src)
            if not thumb:
                return _err("too large or unreadable", 400)
            return json_response({"ok": True, "name": name, "thumb": thumb})
        except Exception as e:
            return _err(f"pool img failed: {e}", 500)

    return await asyncio.to_thread(_work)




async def handle_pool_upload(request):
    """抽奖武器上传（multipart file + ?rar=SSR&replace=0&name=，存生效目录；replace=1 时覆盖同名）"""
    try:
        rar = (get_req_query(request, "rar", "") or "").strip().upper()
        replace = (get_req_query(request, "replace", "") or "").strip().lower() in ("1", "true")
        fixname = (get_req_query(request, "name", "") or "").strip()
        if rar not in _POOL_RARS:
            try:
                p = await get_req_json(request, default={})
                if isinstance(p, dict):
                    rar = str(p.get("rar", "") or "").strip().upper()
            except Exception:
                pass
        if rar not in _POOL_RARS:
            return _err("rar required (SSR/SR/R)", 400)
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
        elif hasattr(form, "filename") or hasattr(form, "read"):
            f = form
        # base64 直传（iframe 桥 postMessage 无法克隆 FormData 时用，见 web_utils.read_upload_b64）
        b64_name, b64_data = "", b""
        if not f:
            b64_name, b64_data = await read_upload_b64(request)
        if not f and not b64_data:
            return _err("no file", 400)
        if b64_data:
            filename = _os.path.basename(b64_name or "upload.bin")
            stem, ext = _os.path.splitext(filename)
            stem = _pool_clean_stem(stem)
            ext = ext.lower()
            if not stem or ext not in _POOL_IMG_EXTS:
                return _err("仅支持图片文件", 400)
            data = bytes(b64_data)
            if not data:
                return _err("empty file", 400)
        else:
            filename = str(getattr(f, "filename", None) or getattr(f, "name", None) or "").strip()
            filename = _os.path.basename(filename)
            stem, ext = _os.path.splitext(filename)
            stem = _pool_clean_stem(stem)
            ext = ext.lower()
            if not stem or ext not in _POOL_IMG_EXTS:
                return _err("仅支持图片文件", 400)
            data = b""
            try:
                val = f.read() if hasattr(f, "read") else None
                if val is not None:
                    import inspect
                    data = await val if inspect.isawaitable(val) else val
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
            if not data:
                return _err("empty file", 400)
            # 与 base64 直传对齐：multipart 同样 50M 上限（防大包堵 loop＋OOM）
            if len(data or b"") > 50 * 1024 * 1024:
                return _err("file too large (50M)", 400)
        if fixname:
            stem = _pool_clean_stem(fixname) or stem
        if not stem:
            return _err("文件名无效", 400)
    except Exception as e:
        return _err(f"pool upload failed: {e}", 500)

    def _work():
        try:
            if replace:
                _pool_write_file(rar, stem, data, ext)
                return json_response({"ok": True, "name": stem, "rar": rar})
            # 非覆盖：同stem任意扩展名视为已存在，防同名异扩展孤儿堆积
            try:
                _d = _pool_dir(rar)
                for _fn in _os.listdir(_d):
                    try:
                        if _os.path.splitext(_fn)[0] == stem and _os.path.isfile(_os.path.join(_d, _fn)):
                            return _err("同名文件已存在", 400)
                    except Exception:
                        continue
            except Exception:
                pass
            _pool_write_file(rar, stem, data, ext)
            return json_response({"ok": True, "name": stem, "rar": rar})
        except Exception as e:
            return _err(f"pool upload failed: {e}", 500)

    return await asyncio.to_thread(_work)
