# -*- coding: utf-8 -*-
"""旧库导入 API — 精简重构版，兼容 v0.42 900行逻辑，支持 .db/.ini/.json/.zip"""
import configparser
import json
import os
import re
import shutil
import tempfile
import zipfile

from astrbot.api.web import json_response

from .web_utils import _err, get_req_query, get_req_json

try:
    from ... import storage as ST
    from ...core.keymap import cn_to_en as _cn2en
except ImportError:
    import storage as ST
    try:
        from core.keymap import cn_to_en as _cn2en
    except Exception:
        def _cn2en(k): return k


async def _read_file_bytes_async(f):
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
    return bytes(data)


def _handle_ini_content(content, rel_path=""):
    imported = 0
    try:
        cp = configparser.ConfigParser(interpolation=None)
        cp.optionxform = str
        cp.read_string(content)
    except Exception:
        return 0
    secs = cp.sections()
    digit_secs = [s for s in secs if s.isdigit()]
    # 推断 gid/qq（兼容 文件夹/文件名 双层）
    gid = None
    qq_from_file = None
    try:
        parent = os.path.basename(os.path.dirname(rel_path)) if rel_path else ""
        if parent.isdigit() and 5 <= len(parent) <= 12:
            gid = parent
        # 文件名 qq
        base = os.path.basename(rel_path) if rel_path else ""
        name_no_ext = os.path.splitext(base)[0]
        if name_no_ext.isdigit() and 5 <= len(name_no_ext) <= 12:
            qq_from_file = name_no_ext
            if not gid:
                # 目录可能是 gid
                gid = parent if parent.isdigit() else None
    except Exception:
        pass
    if not gid:
        m = re.search(r"(\d{5,12})", rel_path or "")
        if m:
            all_nums = re.findall(r"\d{5,12}", rel_path or "")
            gid = all_nums[-2] if len(all_nums) >= 2 else m.group(1)
    # 群共享 ini（digit Secs 为 QQ 列表）：如 <gid>.ini / nuli_slave/*.ini
    if digit_secs:
        if not gid:
            gid = "1000"
        # 分流：钱包/账户 vs 群档案（奴隶）
        _GROUP_EN = {"price","owner","purchase_price","purchase_time","protect_until","slave_slots","study_time","torture_time","fight_time","tip_time","flatter_time","revolt_time","free_time","coin_time","work_time","work_wage","work_status","weapon","weapon_exp","treasure","consecutive_days","ransom_time","name","protector","_work_wage"}
        for sec in digit_secs:
            qq = sec.strip()
            try:
                wallet_keys = ["现金总数", "现金", "金币", "货币", "金钱", "money", "cash_total"]
                hit = False
                for key in wallet_keys:
                    if cp.has_option(sec, key):
                        try:
                            val = int(float(cp.get(sec, key)))
                            cur = ST.coins_get(gid, qq)
                            if val != cur:
                                ST.coins_add(gid, qq, val - cur)
                            else:
                                if ST._DB.execute("SELECT 1 FROM wallet WHERE gid=? AND qq=?", (int(gid), int(qq))).fetchone() is None:
                                    ST.coins_add(gid, qq, 0)
                        except Exception:
                            pass
                        hit = True
                        break
                if not hit:
                    try:
                        if ST._DB.execute("SELECT 1 FROM wallet WHERE gid=? AND qq=?", (int(gid), int(qq))).fetchone() is None:
                            ST.coins_add(gid, qq, 0)
                    except Exception:
                        pass
                a = ST.acct(gid, qq)
                g = ST.group(gid)
                # 确保 DirtyDict
                gu = g[qq]
                for k in cp.options(sec):
                    if k in wallet_keys:
                        continue
                    nk = _cn2en(k)
                    v = cp.get(sec, k)
                    # 路由到群档案 vs 账户
                    if nk in _GROUP_EN or k in ["身价","主人","买入价格","购买时间","保护时间","奴隶位","武器","宝物","武器经验","身价","主人"]:
                        gu[nk] = v
                    else:
                        a.set(nk, v)
                # legacy English deposit_total -> deposit etc
                try:
                    if cp.has_option(sec, "deposit_total"):
                        a.set("deposit", cp.get(sec, "deposit_total"))
                    if cp.has_option(sec, "stamina_total"):
                        a.set("stamina", cp.get(sec, "stamina_total"))
                    if cp.has_option(sec, "charm_total"):
                        a.set("charm", cp.get(sec, "charm_total"))
                    if cp.has_option(sec, "lottery_total"):
                        a.set("lottery_tickets", cp.get(sec, "lottery_total"))
                    if cp.has_option(sec, "sign_count"):
                        a.set("sign_count", cp.get(sec, "sign_count"))
                except Exception:
                    pass
                ST.acct_save(gid, qq)
                # 签到次数同步到群档案
                try:
                    if cp.has_option(sec, "签到次数"):
                        gu["total_sign_days"] = cp.get(sec, "签到次数")
                        if cp.has_option(sec, "连签天数"):
                            gu["shadow_streak"] = cp.get(sec, "连签天数")
                except Exception:
                    pass
                ST.save_group(gid)
                imported += 1
            except Exception:
                pass
        return imported
    # 单用户 ini（文件名=QQ，父目录=gid）：如 精灵系统/游戏账户/<gid>/<qq>.ini
    # 若 rel_path 仅为文件名导致 gid==qq 或 gid 缺失，则尝试从 DB 推断真实 gid
    if qq_from_file and qq_from_file.isdigit() and (not gid or gid == qq_from_file):
        # 文件名为 QQ 且父目录丢失（单文件上传），尝试用库中最大群推断
        try:
            cand_gids = []
            if ST._DB is not None:
                for (cg,) in ST._DB.execute("SELECT DISTINCT gid FROM wallet").fetchall():
                    cand_gids.append(str(cg))
                for (cg,) in ST._DB.execute("SELECT DISTINCT gid FROM groups").fetchall():
                    if str(cg) not in cand_gids:
                        cand_gids.append(str(cg))
            # 优先成员最多的群
            if cand_gids:
                # 选成员最多的
                best = None; best_cnt = -1
                for cg in cand_gids:
                    try:
                        cnt = ST._DB.execute("SELECT COUNT(DISTINCT qq) FROM wallet WHERE gid=?", (int(cg),)).fetchone()[0] or 0
                    except Exception:
                        cnt = 0
                    if cnt > best_cnt:
                        best_cnt = cnt; best = cg
                if best and best_cnt>0:
                    gid = best
                else:
                    gid = cand_gids[0]
            # 若仍无，尝试从配置中取群组开关已配置的 gid
            if not gid or gid == qq_from_file:
                try:
                    sec = ST._CONFIG.get("群组开关配置") if hasattr(ST, "_CONFIG") else {}
                    if isinstance(sec, dict):
                        for k in sec.keys():
                            if str(k).isdigit() and str(k) != qq_from_file:
                                gid = str(k); break
                except Exception:
                    pass
        except Exception:
            pass
        # 仍无法推断则回退中性 gid（用 qq 作 gid 会导致显示异常；与上游 1000 约定一致）
        if gid == qq_from_file:
            gid = "1000"
    if qq_from_file and gid and qq_from_file.isdigit():
        qq = qq_from_file
        try:
            # 精灵系统单用户
            if any(s in secs for s in ["我的精灵","精灵列表","我的背包","精灵冒险"]):
                a = ST.acct(gid, qq)
                sp = {}
                try:
                    sp = json.loads(a.get("spirits", "{}") or "{}")
                    if not isinstance(sp, dict):
                        sp = {}
                except Exception:
                    sp = {}
                # 精灵列表
                lst = []
                if cp.has_section("精灵列表"):
                    for name, val in cp.items("精灵列表"):
                        name = name.strip()
                        if not name or val.strip() != "1":
                            continue
                        it = {"name": name}
                        if cp.has_section(name):
                            # LV/EXP/HP/攻击/防御/特攻/特防/速度
                            sec_items = dict(cp.items(name))
                            try:
                                it["level"] = int(float(sec_items.get("LV", "1") or "1"))
                            except Exception:
                                it["level"] = 1
                            try:
                                it["exp"] = int(float(sec_items.get("EXP", "0") or "0"))
                            except Exception:
                                it["exp"] = 0
                            for cn_key, en_key in [("HP","hp"),("攻击","atk"),("防御","def"),("特攻","spa"),("特防","spd"),("速度","spe")]:
                                try:
                                    if cn_key in sec_items:
                                        it[en_key] = int(float(sec_items[cn_key] or "0"))
                                except Exception:
                                    pass
                            # 额外保留收服信息
                            for k in ["收服地点","收服时间"]:
                                if k in sec_items:
                                    it[k] = sec_items[k]
                        else:
                            it["level"] = 1
                        lst.append(it)
                # 背包
                bag = {}
                if cp.has_section("我的背包"):
                    for k, v in cp.items("我的背包"):
                        try:
                            nk = _cn2en(k.strip())
                            # bag 存英文键
                            bag[nk] = int(float(v or "0"))
                        except Exception:
                            pass
                # 出战精灵
                active = ""
                if cp.has_section("精灵冒险") and cp.has_option("精灵冒险", "出战精灵"):
                    active = cp.get("精灵冒险", "出战精灵").strip()
                # 组装
                if lst or bag or active:
                    sp["list"] = lst
                    sp["active"] = active
                    sp["bag"] = bag
                    sp["adopted"] = 1
                    a.set("spirits", json.dumps(sp, ensure_ascii=False))
                    ST.acct_save(gid, qq)
                    # 确保钱包占位
                    try:
                        if ST._DB.execute("SELECT 1 FROM wallet WHERE gid=? AND qq=?", (int(gid), int(qq))).fetchone() is None:
                            ST.coins_add(gid, qq, 0)
                    except Exception:
                        pass
                    imported = 1
                    return imported
            # 通用单用户：所有节直接写入账户/群档案
            a = ST.acct(gid, qq)
            g = ST.group(gid)
            gu = g[qq]
            for sec in secs:
                for k, v in cp.items(sec):
                    nk = _cn2en(k)
                    # 启发式：奴隶相关进 group，其余进 acct
                    if nk in {"price","owner","weapon","treasure","weapon_exp","slave_slots","protect_until"} or k in ["身价","主人","武器","宝物"]:
                        gu[nk] = v
                    else:
                        a.set(nk, v)
            ST.acct_save(gid, qq)
            ST.save_group(gid)
            try:
                if ST._DB.execute("SELECT 1 FROM wallet WHERE gid=? AND qq=?", (int(gid), int(qq))).fetchone() is None:
                    ST.coins_add(gid, qq, 0)
            except Exception:
                pass
            imported = 1
        except Exception:
            pass
        return imported
    return imported


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
    """用户列表入库（线程池）：钱包差值+账户覆盖+群组覆盖"""
    ok = 0
    for item in users or []:
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
            for k, v in item["account"].items():
                a.set(str(k), str(v))
            ST.acct_save(gid, qq)
        if "group" in item and isinstance(item["group"], dict):
            g = ST.group(gid)
            g[qq] = {str(k): str(v) for k, v in item["group"].items()}
            ST.save_group(gid)
        ok += 1
    ST.flush_all()
    return json_response({"imported": ok, "type": typ})


async def handle_import_legacy(req, plugin_base=""):
    """旧库导入：请求解析在事件循环上做，解包/入库等重活进线程池，不堵消息循环"""
    import asyncio as _aio
    # ---- Phase 1（loop）：只碰 request，产出纯数据 ----
    users_payload = None
    filename, data = "", b""
    try:
        form = {}
        try:
            form = await req.files()  # type: ignore
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
            try:
                p = await get_req_json(req, default={})
                if isinstance(p, dict) and p:
                    users = p.get("users")
                    if isinstance(users, list):
                        users_payload = users
            except Exception:
                pass
            if users_payload is None:
                # 兜底：读原始体
                raw_data = await _read_raw_body(req)
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
                            fname = str(get_req_query(req, "filename", "") or get_req_query(req, "file", "")).strip()
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
    except Exception as e:
        return _err(f"import failed: {e}", 500)

    def _work():
        try:
            if users_payload is not None:
                return _import_users_list(users_payload, "json")
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
        fd_tmp, tmp = tempfile.mkstemp(prefix="xbbot_legacy_", suffix="_" + os.path.basename(filename).replace("/", "_").replace("\\", "_"))
        os.close(fd_tmp)
        try:
            with open(tmp, "wb") as w:
                w.write(data)
        except Exception as e:
            return json_response({"error": f"write tmp failed: {e}", "imported": 0})
        lower = filename.lower()
        if lower.endswith(".zip"):
            try:
                ztmp = tempfile.mkdtemp(prefix="xbbot_legacy_")
                try:
                    with zipfile.ZipFile(tmp, "r") as zf:
                        zf.extractall(ztmp)
                except Exception as ze:
                    try:
                        with zipfile.ZipFile(tmp, "r") as zf:
                            for info in zf.infolist():
                                try:
                                    if info.flag_bits & 0x800 == 0:
                                        info.filename = info.filename.encode("cp437").decode("gbk", errors="replace")
                                except Exception:
                                    pass
                                zf.extract(info, ztmp)
                    except Exception:
                        raise ze
                total = 0
                for root2, _, files2 in os.walk(ztmp):
                    for fn in files2:
                        fp = os.path.join(root2, fn)
                        fl = fn.lower()
                        rel = os.path.relpath(fp, ztmp).replace(os.sep, "/")
                        if fl.endswith(".db"):
                            try:
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
                                j = json.load(open(fp, encoding="utf-8"))
                                if isinstance(j, dict) and isinstance(j.get("users"), list):
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
                                            for k, v in item["account"].items():
                                                a.set(str(k), str(v))
                                            ST.acct_save(gid, qq)
                                        total += 1
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
