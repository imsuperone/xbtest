# -*- coding: utf-8 -*-
"""旧库导入 API — 精简重构版，兼容 v0.42 900行逻辑，支持 .db/.ini/.json/.zip（ini 解析已独立至 legacy_ini）"""
import json
import os
import re
import shutil
import tempfile
import zipfile

try:
    from ..adapters import json_response
except ImportError:
    from core.adapters import json_response

from .web_utils import _err, get_req_query, get_req_json, read_upload_b64

try:
    from .. import storage as ST
except ImportError:
    from core import storage as ST  # type: ignore


async def _read_file_bytes_async(f):
    # 与 weapon_pool 对齐：单文件 50M 上限，超限返回 b"" 由调用方判 400（防大包堵 loop＋OOM）
    data = b""
    try:
        if hasattr(f, "read"):
            val = f.read()
            import inspect
            if inspect.isawaitable(val):
                data = await val
            else:
                data = val
        if not data and hasattr(f, "file"):
            try:
                ff = getattr(f, "file")
                if hasattr(ff, "read"):
                    data = ff.read()
                    if hasattr(data, "read"):
                        data = data.read()
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
    data = bytes(data)
    if len(data) > _IMPORT_MAX_BYTES:
        return b""
    return data


# 旧库导入单次上限（与 weapon_pool 50M 对齐，防大包堵 loop＋OOM）
_IMPORT_MAX_BYTES = 50 * 1024 * 1024
# 单次用户列表条数上限（防 JSON 巨包内存峰值；超限请分群/分批导入）
_IMPORT_MAX_USERS = 20000
# SQLite 魔数（备份导出包裹解包判定用）
_SQLITE_MAGIC = b"SQLite format 3\x00"


def _unwrap_backup_export(data):
    """备份导出 JSON 包裹解包：backups/export 返回 {ok,path,data:b64,size,filename}，
    用户把该文件直接当旧库回导时，拆出内层 SQLite bytes。非包裹返回 None（调用方走原分支）。
    判定：顶层 JSON dict 含 data 字段且 base64 解码后具 SQLite 魔数（禁按扩展名猜，避免误拆用户列表 json）。"""
    try:
        if not isinstance(data, (bytes, bytearray)) or len(data) < 2:
            return None
        if bytes(data).lstrip()[:1] != b"{":
            return None
        j = json.loads(bytes(data).decode("utf-8"))
        if not isinstance(j, dict):
            return None
        b64s = j.get("data")
        if not isinstance(b64s, str) or not b64s.strip():
            return None
        import base64 as _b64
        raw = _b64.b64decode(b64s.strip())
        if raw[:len(_SQLITE_MAGIC)] == _SQLITE_MAGIC:
            return raw
    except Exception:
        pass
    return None



# _handle_ini_content 已独立至 legacy_ini（老路径兼容）
try:
    from .legacy_ini import _handle_ini_content  # type: ignore
except ImportError:
    pass

async def _read_raw_body(req):
    """loop 侧读请求原始体（含 awaitable 兼容），返回 bytes"""
    raw_data = b""
    for attr in ("read", "body", "content", "data"):
        try:
            obj = getattr(req, attr, None)
            if obj is None:
                continue
            if callable(obj):
                import inspect
                val = obj()
                if inspect.isawaitable(val):
                    val = await val
                raw_data = val
            else:
                if hasattr(obj, "read"):
                    try:
                        val = obj.read()
                        import inspect as _ins2
                        if _ins2.isawaitable(val):
                            val = await val
                        raw_data = val
                    except Exception:
                        continue
                else:
                    raw_data = obj
            if isinstance(raw_data, (bytes, bytearray)) and len(raw_data) > 0:
                break
            if isinstance(raw_data, str) and raw_data:
                raw_data = raw_data.encode("utf-8", errors="ignore")
                break
        except Exception:
            continue
    return raw_data


def _import_users_list(users, typ="json"):
    """用户列表入库（线程池）：钱包差值+账户覆盖+群组覆盖。返成功数（调用方包回执）。

    部分失败只计成功：任一写失败该条不计入 ok（禁部分导入报全成功）。"""
    ok = 0
    for item in users or []:
        if not isinstance(item, dict):
            continue
        gid = str(item.get("gid") or "").strip()
        qq = str(item.get("qq") or "").strip()
        if not gid or not qq:
            continue
        _item_ok = True
        if "wallet" in item:
            try:
                tgt = int(item["wallet"])
                cur = ST.coins_get(gid, qq)
                if tgt != cur and ST.coins_add(gid, qq, tgt - cur) is None:
                    _item_ok = False
            except Exception:
                _item_ok = False
        if "account" in item and isinstance(item["account"], dict):
            try:
                a = ST.acct(gid, qq)
                a.kv.clear()
                a.dirty = True
                for k, v in item["account"].items():
                    a.set(str(k), str(v))
                if not ST.acct_save(gid, qq):
                    _item_ok = False
            except Exception:
                _item_ok = False
        if "group" in item and isinstance(item["group"], dict):
            try:
                g = ST.group(gid)
                g[qq] = {str(k): str(v) for k, v in item["group"].items()}
                if not ST.save_group(gid):
                    _item_ok = False
            except Exception:
                _item_ok = False
        if _item_ok:
            ok += 1
    try:
        ST.flush_all()
    except Exception:
        pass
    return ok


async def handle_import_legacy(request, plugin_base=""):
    """旧库导入：请求解析在事件循环上做，解包/入库等重活进线程池，不堵消息循环"""
    import asyncio as _aio
    # ---- Phase 1（loop）：只碰 request，产出纯数据 ----
    users_payload = None
    filename, data = "", b""
    try:
        form = {}
        try:
            form = await request.files()  # type: ignore
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
            try:
                if hasattr(form, "filename") or hasattr(form, "read"):
                    f = form
            except Exception:
                f = None
        if not f:
            # base64 直传（WebUI postFile 发 {filename, file_base64}，无 multipart）：
            # 先解 base64 拿真实文件，再按扩展名分发；与 weapon_pool 同口径
            try:
                b64_name, b64_data = await read_upload_b64(request)
                if b64_data:
                    if len(b64_data) > _IMPORT_MAX_BYTES:
                        return _err("file too large (50M)", 400)

                    class _B64File:
                        def __init__(self, name, data):
                            self.filename = name or "upload.bin"
                            self._data = data

                        async def read(self):
                            return self._data

                    f = _B64File(b64_name, bytes(b64_data))
            except Exception:
                pass
        if not f:
            try:
                p = await get_req_json(request, default={})
                if isinstance(p, dict) and p:
                    users = p.get("users")
                    if isinstance(users, list):
                        users_payload = users
            except Exception:
                pass
            if users_payload is None:
                # 兜底：读原始体（同样 50M 上限）
                raw_data = await _read_raw_body(request)
                if isinstance(raw_data, (bytes, bytearray)) and len(raw_data) > _IMPORT_MAX_BYTES:
                    return _err("file too large (50M)", 400)
                if isinstance(raw_data, (bytes, bytearray)) and len(raw_data) > 10:
                    # multipart 提取
                    try:
                        if b"Content-Disposition" in raw_data and b"filename=" in raw_data:
                            first_nl = raw_data.find(b"\r\n")
                            if first_nl != -1 and raw_data.startswith(b"--"):
                                bnd = raw_data[2:first_nl].strip()
                                if bnd:
                                    parts = raw_data.split(b"--" + bnd)
                                    for _part in parts:
                                        if b"filename=" in _part:
                                            hdr_end = _part.find(b"\r\n\r\n")
                                            if hdr_end != -1:
                                                _content = _part[hdr_end + 4:]
                                                if _content.endswith(b"\r\n"):
                                                    _content = _content[:-2]
                                                if _content.endswith(b"--"):
                                                    _content = _content[:-2].rstrip(b"\r\n")
                                                raw_data = _content
                                                mfn = re.search(br'filename="([^"]+)"', _part)
                                                if mfn:
                                                    try:
                                                        fname = mfn.group(1).decode("utf-8", errors="ignore")
                                                    except Exception:
                                                        fname = ""
                                                    _fname_from_multipart = fname
                                                break
                    except Exception:
                        pass
                    fname = locals().get("_fname_from_multipart", "") or ""
                    if not fname:
                        try:
                            fname = str(get_req_query(request, "filename", "") or get_req_query(request, "file", "")).strip()
                        except Exception:
                            pass
                    if not fname:
                        if raw_data[:2] == b"PK":
                            fname = "upload.zip"
                        elif raw_data[:6] == b"SQLite":
                            fname = "upload.db"
                        elif raw_data[:1] == b"{":
                            fname = "upload.json"
                        else:
                            try:
                                txt_try = raw_data[:200].decode("gbk", errors="ignore")
                                fname = "upload.ini" if "[" in txt_try and "=" in txt_try else "upload.bin"
                            except Exception:
                                fname = "upload.bin"
                    class _RawFile:
                        def __init__(self, name, data):
                            self.filename = name
                            self._data = data
                        async def read(self):
                            return self._data
                    f = _RawFile(fname, raw_data if isinstance(raw_data, (bytes, bytearray)) else bytes(raw_data))
                else:
                    return _err("no file (field 'file') and not JSON", 400)
            if not f and users_payload is None:
                return _err("no file (field 'file') and not JSON", 400)
        if f is not None:
            filename = str(getattr(f, "filename", None) or getattr(f, "name", None) or getattr(f, "file", None) or "").strip()
            if not filename:
                filename = "upload.bin"
            data = await _read_file_bytes_async(f)
            data = bytes(data or b"")
            if not data:
                return _err("file empty or too large (50M)", 400)
    except Exception as e:
        return _err(f"import failed: {e}", 500)

    def _work():
        try:
            if users_payload is not None:
                if isinstance(users_payload, list) and len(users_payload) > _IMPORT_MAX_USERS:
                    return json_response({"error": "too many users (20000)", "imported": 0})
                return json_response({"imported": _import_users_list(users_payload, "json"), "type": "json"})
            return _import_file_data(filename, data)
        except Exception as e:
            import traceback
            try:
                return json_response({"error": f"import failed: {e}", "trace": traceback.format_exc()[:500], "imported": 0})
            except Exception:
                return _err(f"import failed: {e}", 500)

    return await _aio.to_thread(_work)


def _heal_spirits_adopted():
    """存量精灵 adopted 自愈唯一实现：有 list 无 adopted 补 1（zip/db 双调用，零语义差）"""
    migrated = 0
    try:
        if ST._DB is None:
            return 0
        for gid_m, qq_m, data_m in ST._DB.execute("SELECT gid, qq, data FROM accounts").fetchall():
            try:
                kv_m = json.loads(data_m or "{}")
                sp_raw_m = kv_m.get("spirits", "")
                if isinstance(sp_raw_m, dict):
                    sp_m = sp_raw_m
                elif isinstance(sp_raw_m, str) and sp_raw_m.strip():
                    sp_m = json.loads(sp_raw_m)
                else:
                    sp_m = {}
                if isinstance(sp_m, dict) and sp_m.get("list") and not sp_m.get("adopted"):
                    sp_m["adopted"] = 1
                    a_m = ST.acct(str(gid_m), str(qq_m))
                    a_m.set("spirits", json.dumps(sp_m, ensure_ascii=False))
                    ST.acct_save(str(gid_m), str(qq_m))
                    migrated += 1
            except Exception:
                continue
        if migrated:
            ST.flush_all()
    except Exception:
        pass
    return migrated


def _import_file_data(filename, data):
    """重活（线程池）：落临时文件 → 按 zip/db/ini/json 分发入库"""
    try:
        # 备份导出回导：backups/export 落盘的 {ok,path,data:b64} JSON 常被改名 .db 直接回导，
        # 先拆出内层 SQLite（仅魔数命中才拆，用户列表 json 不受影响），扩展名同步归 .db。
        try:
            _uw = _unwrap_backup_export(data)
            if _uw is not None:
                data = _uw
                if not str(filename or "").lower().endswith(".db"):
                    filename = (os.path.splitext(str(filename or "upload"))[0] or "upload") + ".db"
        except Exception:
            pass
        fd_tmp, tmp = tempfile.mkstemp(prefix="xbbot_legacy_", suffix="_" + os.path.basename(filename).replace("/", "_").replace("\\", "_"))
        os.close(fd_tmp)
        try:
            with open(tmp, "wb") as w:
                w.write(data)
        except Exception as e:
            return json_response({"error": f"write tmp failed: {e}", "imported": 0})
        lower = filename.lower()
        if lower.endswith(".zip"):
            def _safe_extract(zf, dest):
                # ZipSlip 防护：跳过绝对路径与 .. 逃逸条目
                for info in zf.infolist():
                    try:
                        if info.flag_bits & 0x800 == 0:
                            info.filename = info.filename.encode("cp437").decode("gbk", errors="replace")
                    except Exception:
                        pass
                    _name = str(info.filename or "").replace("\\", "/")
                    if not _name or _name.startswith("/") or ".." in _name.split("/"):
                        continue
                    try:
                        zf.extract(info, dest)
                    except Exception:
                        pass
            try:
                ztmp = tempfile.mkdtemp(prefix="xbbot_legacy_")
                try:
                    with zipfile.ZipFile(tmp, "r") as zf:
                        _safe_extract(zf, ztmp)
                except Exception as ze:
                    raise ze
                total = 0
                for root2, _, files2 in os.walk(ztmp):
                    for fn in files2:
                        fp = os.path.join(root2, fn)
                        fl = fn.lower()
                        rel = os.path.relpath(fp, ztmp).replace(os.sep, "/")
                        if fl.endswith(".db"):
                            try:
                                # zip 内备份导出 JSON 同样先拆包（仅魔数命中改写）
                                try:
                                    with open(fp, "rb") as _rf:
                                        _zraw = _rf.read()
                                    _zuw = _unwrap_backup_export(_zraw)
                                    if _zuw is not None:
                                        with open(fp, "wb") as _wf:
                                            _wf.write(_zuw)
                                except Exception:
                                    pass
                                total += ST.merge_from(fp)
                            except Exception:
                                pass
                        elif fl.endswith(".ini"):
                            try:
                                content = None
                                for enc in ("gbk", "utf-8", "utf-8-sig"):
                                    try:
                                        with open(fp, encoding=enc) as rf:
                                            content = rf.read()
                                        break
                                    except Exception:
                                        continue
                                if content is not None:
                                    total += _handle_ini_content(content, rel)
                            except Exception:
                                pass
                        elif fl.endswith(".json"):
                            try:
                                with open(fp, encoding="utf-8") as _jf:
                                    j = json.load(_jf)
                                # 与单文件 json 同口径（三表），禁再手写双表分裂
                                if isinstance(j, dict) and isinstance(j.get("users"), list):
                                    total += _import_users_list(j["users"], "json")
                            except Exception:
                                pass
                try:
                    shutil.rmtree(ztmp)
                except Exception:
                    pass
                try:
                    os.remove(tmp)
                except Exception:
                    pass
                ST.flush_all()
                # 存量精灵 adopted 自愈：已有 list 但无 adopted 的老数据补齐
                _migrated = _heal_spirits_adopted()
                return json_response({"imported": total, "type": "zip", "migrated": locals().get("_migrated", 0)})
            except Exception as e:
                return json_response({"error": f"zip failed: {e}", "imported": 0})
        if lower.endswith(".db"):
            try:
                cnt = ST.merge_from(tmp)
                ST.flush_all()
                # 同步精灵 adopted 自愈
                _heal_spirits_adopted()
                try:
                    os.remove(tmp)
                except Exception:
                    pass
                return json_response({"imported": cnt, "type": "db"})
            except Exception as e:
                return _err(f"db import failed: {e}", 500)
        if lower.endswith(".ini"):
            try:
                content = None
                for enc in ("gbk", "utf-8", "utf-8-sig"):
                    try:
                        with open(tmp, encoding=enc) as rf:
                            content = rf.read()
                        break
                    except Exception:
                        continue
                if content is None:
                    return _err("ini decode failed", 400)
                cnt = _handle_ini_content(content, filename)
                ST.flush_all()
                try:
                    os.remove(tmp)
                except Exception:
                    pass
                return json_response({"imported": cnt, "type": "ini"})
            except Exception as e:
                return _err(f"ini import failed: {e}", 500)
        if lower.endswith(".json"):
            try:
                j = json.loads(data.decode("utf-8", errors="ignore"))
                if isinstance(j, dict) and isinstance(j.get("users"), list):
                    ok = 0
                    for item in j["users"]:
                        if not isinstance(item, dict):
                            continue
                        gid = str(item.get("gid") or "").strip()
                        qq = str(item.get("qq") or "").strip()
                        if not gid or not qq:
                            continue
                        if "wallet" in item:
                            try:
                                tgt = int(item["wallet"])
                                cur = ST.coins_get(gid, qq)
                                ST.coins_add(gid, qq, tgt - cur)
                            except Exception:
                                pass
                        if "account" in item and isinstance(item["account"], dict):
                            a = ST.acct(gid, qq)
                            a.kv.clear()
                            a.dirty = True
                            for k, v in item["account"].items():
                                a.set(str(k), str(v))
                            ST.acct_save(gid, qq)
                        ok += 1
                    ST.flush_all()
                    try:
                        os.remove(tmp)
                    except Exception:
                        pass
                    return json_response({"imported": ok, "type": "json"})
                return _err("json must contain users list", 400)
            except Exception as e:
                return _err(f"json import failed: {e}", 500)
        return _err(f"unsupported file type: {filename}", 400)
    except Exception as e:
        import traceback
        try:
            return json_response({"error": f"import failed: {e}", "trace": traceback.format_exc()[:500], "imported": 0})
        except Exception:
            return _err(f"import failed: {e}", 500)
