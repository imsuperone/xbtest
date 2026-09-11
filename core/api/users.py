# -*- coding: utf-8 -*-
"""用户管理 API — 列表/编辑/单用户导出导入/全量导出导入"""
import asyncio
import base64
import json
import time
from astrbot.api.web import json_response

from .web_utils import _err, get_req_query, get_req_json

try:
    from .. import storage as ST
    from ...games import slave
except ImportError:
    from core import storage as ST
    try:
        from games import slave
    except ImportError:
        import slave  # type: ignore

try:
    from ..version import get_version as _get_version
except ImportError:
    try:
        from core.version import get_version as _get_version  # type: ignore
    except Exception:
        def _get_version(*a, **k):  # type: ignore
            return "2026w0911k"
try:
    PLUGIN_VERSION = _get_version()
except Exception:
    PLUGIN_VERSION = "2026w0911k"


def _extract_param(request, key, default=""):
    """多源参数提取：兼容 query/rel_url/args/match_info"""
    for src in (getattr(request, "query", None), getattr(request, "rel_url", None), getattr(request, "args", None)):
        try:
            if src is not None:
                if hasattr(src, "get"):
                    v = src.get(key, None)
                    if v is not None:
                        return str(v)
                if hasattr(src, "query") and hasattr(src.query, "get"):
                    v = src.query.get(key, None)
                    if v is not None:
                        return str(v)
        except Exception:
            pass
    try:
        if hasattr(request, "match_info") and request.match_info is not None:
            v = request.match_info.get(key, None)
            if v is not None:
                return str(v)
    except Exception:
        pass
    return str(default)


async def handle_users(request):
    nm = getattr(slave, "NOTE_NAMES", {}) or {}
    gid_filter = _extract_param(request, "gid", "").strip()
    try:
        _limit = int(_extract_param(request, "limit", "300") or 300)
    except Exception:
        _limit = 300
    _limit = max(1, min(_limit, 1000))
    try:
        _offset = int(_extract_param(request, "offset", "0") or 0)
    except Exception:
        _offset = 0
    _offset = max(0, _offset)
    if not gid_filter:
        try:
            p0 = await get_req_json(request, default={})
            if isinstance(p0, dict):
                if p0.get("gid"):
                    gid_filter = str(p0.get("gid")).strip()
                if p0.get("limit"):
                    _limit = max(1, min(int(p0.get("limit")), 1000))
                if p0.get("offset") is not None:
                    _offset = max(0, int(p0.get("offset")))
        except Exception:
            pass
    if gid_filter and gid_filter.isdigit():
        _gid_i = int(gid_filter)
    else:
        _gid_i = None
    _lim, _off = _limit, _offset

    def _work():
        _lock = getattr(ST, "_LOCK", None)
        if _lock is not None:
            _lock.acquire()
        try:
            if _gid_i is not None:
                try:
                    rows = ST._DB.execute(
                        "SELECT w.gid, w.qq, w.money, a.data FROM wallet w "
                        "LEFT JOIN accounts a ON a.gid=w.gid AND a.qq=w.qq WHERE w.gid=? "
                        "ORDER BY w.money DESC LIMIT ? OFFSET ?", (_gid_i, _lim, _off)).fetchall() if ST._DB else []
                except Exception:
                    try:
                        rows = ST._DB.execute(
                            "SELECT w.gid, w.qq, w.money, a.data FROM wallet w "
                            "LEFT JOIN accounts a ON a.gid=w.gid AND a.qq=w.qq "
                            "ORDER BY w.money DESC LIMIT ? OFFSET ?", (_lim, _off)).fetchall() if ST._DB else []
                    except Exception:
                        rows = []
            else:
                try:
                    rows = ST._DB.execute(
                        "SELECT w.gid, w.qq, w.money, a.data FROM wallet w "
                        "LEFT JOIN accounts a ON a.gid=w.gid AND a.qq=w.qq "
                        "ORDER BY w.money DESC LIMIT ? OFFSET ?", (_lim, _off)).fetchall() if ST._DB else []
                except Exception:
                    rows = []
            out = []
            for sqm, qq, money, data in rows:
                kv = {}
                try:
                    kv = json.loads(data) if data else {}
                except Exception:
                    kv = {}
                _nm = ""
                try:
                    if hasattr(slave, "get_note_name"):
                        _nm = slave.get_note_name(str(sqm), str(qq)) or ""
                except Exception:
                    _nm = ""
                if not _nm:
                    _nm = nm.get(str(qq), "")
                out.append({
                    "gid": str(sqm), "qq": str(qq),
                    "name": _nm, "money": int(money or 0),
                    "stamina": int(float(kv.get("stamina", "0") or 0)),
                    "charm": int(float(kv.get("charm", "0") or 0)),
                    "lottery_tickets": int(float(kv.get("lottery_tickets", "0") or 0)),
                    "deposit": int(float(kv.get("deposit", "0") or 0)),
                    "sign": int(float(kv.get("sign_count", "0") or 0)),
                })
            return out
        finally:
            if _lock is not None:
                try:
                    _lock.release()
                except Exception:
                    pass
    out = await asyncio.to_thread(_work)
    return json_response(out)


async def handle_user_edit(request):
    p = await get_req_json(request, default={})
    if not isinstance(p, dict):
        return _err("payload must be dict", 400)
    qq = str(p.get("qq") or "").strip()
    if not qq:
        return _err("qq required", 400)
    gid = str(p.get("gid") or "").strip()
    if not gid:
        return _err("gid required", 400)
    out = {}
    if "money" in p and str(p.get("money", "")).strip() != "":
        try:
            tgt = int(p["money"])
        except Exception:
            return _err("money must be int", 400)
        cur = ST.coins_get(gid, qq)
        out["money"] = ST.coins_add(gid, qq, tgt - cur)
    _map_old = {"tili": "stamina", "meili": "charm", "jiangquan": "lottery_tickets", "cunkuan": "deposit"}
    norm_p = {}
    for k, v in p.items():
        nk = _map_old.get(k, k)
        norm_p[nk] = v
    p = norm_p
    for fk in ("stamina", "charm", "lottery_tickets", "deposit"):
        if fk not in p:
            continue
        if str(p[fk]).strip() == "":
            continue
        try:
            val = int(p[fk])
        except Exception:
            return _err("%s must be int" % fk, 400)
        a = ST.acct(gid, qq)
        a.set(fk, str(val))
        ST.acct_save(gid, qq)
        out[fk] = val
    return json_response({"saved": True, "qq": qq, "gid": gid, **out})


async def handle_user_export(request):
    gid = _extract_param(request, "gid", "").strip()
    qq = _extract_param(request, "qq", "").strip()
    if not gid or not qq:
        try:
            p = await get_req_json(request, default={})
            if isinstance(p, dict):
                if not gid and p.get("gid"):
                    gid = str(p.get("gid")).strip()
                if not qq and p.get("qq"):
                    qq = str(p.get("qq")).strip()
        except Exception:
            pass
    if not gid or not qq:
        return _err("gid and qq required", 400)
    try:
        money = ST.coins_get(gid, qq)
        a = ST.acct(gid, qq)
        kv = dict(a.kv) if hasattr(a, "kv") else {}
        grp = ST.group(gid)
        gdata = {}
        if grp.has_section(qq):
            gdata = dict(grp[qq] or {})
        payload = {
            "gid": gid,
            "qq": qq,
            "name": getattr(slave, "NOTE_NAMES", {}).get(qq, ""),
            "wallet": money,
            "account": kv,
            "group": gdata,
            "export_at": int(time.time()),
            "version": PLUGIN_VERSION,
        }
        data_bytes = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        b64 = base64.b64encode(data_bytes).decode()
        fn = f"xbbot_user_{qq}_{gid}.json"
        return json_response({"ok": True, "data": b64, "filename": fn, "size": len(data_bytes), **payload})
    except Exception as e:
        return _err(f"export failed: {e}", 500)


async def handle_user_import(request):
    p = await get_req_json(request, default={})
    if not isinstance(p, dict):
        return _err("payload must be dict", 400)
    gid = str(p.get("gid") or "").strip()
    qq = str(p.get("qq") or "").strip()
    if not gid or not qq:
        return _err("gid and qq required", 400)
    try:
        if "wallet" in p:
            try:
                tgt = int(p["wallet"])
                cur = ST.coins_get(gid, qq)
                ST.coins_add(gid, qq, tgt - cur)
            except Exception as e:
                return _err(f"wallet invalid: {e}", 400)
        if "account" in p and isinstance(p["account"], dict):
            a = ST.acct(gid, qq)
            a.kv.clear()
            a.dirty = True  # clear() 不标脏：空覆盖也必须落盘，否则内存与库分叉、重启复活
            for k, v in p["account"].items():
                a.set(str(k), str(v))
            ST.acct_save(gid, qq)
        if "group" in p and isinstance(p["group"], dict):
            g = ST.group(gid)
            g[str(qq)] = {str(k): str(v) for k, v in p["group"].items()}
            ST.save_group(gid)
        if p.get("name"):
            slave.NOTE_NAMES[str(qq)] = str(p["name"])
            ST.register_names(slave.NOTE_NAMES)
        return json_response({"imported": True, "gid": gid, "qq": qq})
    except Exception as e:
        return _err(f"import failed: {e}", 500)


async def handle_users_export(request):
    def _q(key, default=""):
        return _extract_param(request, key, default)

    gid = _q("gid", "").strip()
    if not gid:
        for accessor in ("json", "post", "form"):
            try:
                fn = getattr(request, accessor, None)
                if callable(fn):
                    import inspect
                    v = fn()
                    if inspect.isawaitable(v):
                        v = await v
                    if isinstance(v, dict) and v.get("gid"):
                        gid = str(v.get("gid")).strip()
                        if gid:
                            break
            except Exception:
                pass
    gid_valid = gid if (gid and gid.isdigit()) else ""
    try:
        # 先刷写内存缓存到 DB
        try:
            ST.flush_all()
        except Exception:
            pass

        out = []
        if ST._DB is None:
            raise RuntimeError("DB 未初始化")

        # 1) wallet 表
        q = "SELECT gid, qq, money FROM wallet"
        args = ()
        if gid_valid:
            q += " WHERE gid=?"
            args = (int(gid_valid),)
        try:
            wallet_rows = ST._DB.execute(q, args).fetchall()
        except Exception:
            wallet_rows = []

        # 2) 批量预取 accounts 与 groups
        acct_map = {}
        grp_map = {}
        try:
            if gid_valid:
                for gg, qq_, data in ST._DB.execute("SELECT gid, qq, data FROM accounts WHERE gid=?", (int(gid_valid),)).fetchall():
                    acct_map[(str(gg), str(qq_))] = data
                for gg, qq_, data in ST._DB.execute("SELECT gid, qq, data FROM groups WHERE gid=?", (int(gid_valid),)).fetchall():
                    grp_map[(str(gg), str(qq_))] = data
            else:
                for gg, qq_, data in ST._DB.execute("SELECT gid, qq, data FROM accounts").fetchall():
                    acct_map[(str(gg), str(qq_))] = data
                for gg, qq_, data in ST._DB.execute("SELECT gid, qq, data FROM groups").fetchall():
                    grp_map[(str(gg), str(qq_))] = data
        except Exception:
            pass

        nm = getattr(slave, "NOTE_NAMES", {}) or {}
        seen = set()

        # 遍历所有 wallet 记录
        for g, q_, money in wallet_rows:
            g = str(g); q_ = str(q_)
            seen.add((g, q_))
            kv = {}
            try:
                raw = acct_map.get((g, q_))
                if raw:
                    kv = json.loads(raw)
            except Exception:
                kv = {}
            gdata = {}
            try:
                rawg = grp_map.get((g, q_))
                if rawg:
                    gdata = json.loads(rawg)
            except Exception:
                gdata = {}

            out.append({
                "gid": g,
                "qq": q_,
                "name": nm.get(q_, "") or kv.get("name", "") or gdata.get("name", ""),
                "wallet": int(money or 0),
                "account": kv,
                "group": gdata
            })

        # 补全仅在 accounts 或 groups 表中的用户（冷用户/无金币但有奴隶或精灵资产）
        all_other_keys = set(acct_map.keys()) | set(grp_map.keys())
        for (g, q_) in all_other_keys:
            if (g, q_) in seen:
                continue
            seen.add((g, q_))
            kv = {}
            try:
                raw = acct_map.get((g, q_))
                if raw:
                    kv = json.loads(raw)
            except Exception:
                kv = {}
            gdata = {}
            try:
                rawg = grp_map.get((g, q_))
                if rawg:
                    gdata = json.loads(rawg)
            except Exception:
                gdata = {}

            out.append({
                "gid": g,
                "qq": q_,
                "name": nm.get(q_, "") or kv.get("name", "") or gdata.get("name", ""),
                "wallet": 0,
                "account": kv,
                "group": gdata
            })

        payload = {"count": len(out), "users": out, "export_at": int(time.time()), "version": PLUGIN_VERSION}
        data_bytes = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        fn = f"xbbot_users_{'all' if not gid_valid else gid_valid}_{int(time.time())}.json"
        b64 = base64.b64encode(data_bytes).decode()
        return json_response({"ok": True, "data": b64, "filename": fn, "size": len(data_bytes), **payload})
    except Exception as e:
        import traceback
        return _err(f"export failed: {e} {traceback.format_exc()[:300]}", 500)


async def handle_users_import(request):
    p = await get_req_json(request, default={})
    users = []
    if isinstance(p, list):
        users = p
    elif isinstance(p, dict):
        if "users" in p and isinstance(p["users"], list):
            users = p["users"]
        elif "data" in p and isinstance(p["data"], list):
            users = p["data"]
        elif "gid" in p and "qq" in p:
            users = [p]
        else:
            return _err("users list or user object required", 400)
    else:
        return _err("invalid payload", 400)

    ok = 0
    try:
        for item in users:
            if not isinstance(item, dict):
                continue
            gid = str(item.get("gid") or "").strip()
            qq = str(item.get("qq") or "").strip()
            if not gid or not qq:
                continue

            # 1. 钱包金币
            val = item.get("wallet", item.get("money"))
            if val is not None:
                try:
                    tgt = int(val)
                    cur = ST.coins_get(gid, qq)
                    ST.coins_add(gid, qq, tgt - cur)
                except Exception:
                    pass

            # 2. account 账户字典（包含武器/法宝/坐骑/精灵/属性）
            a = ST.acct(gid, qq)
            if "account" in item and isinstance(item["account"], dict):
                for k, v in item["account"].items():
                    a.set(str(k), str(v))
            # 兼容扁平字段 (stamina, charm, lottery_tickets, deposit, sign)
            for fk, ak in [("stamina", "stamina"), ("charm", "charm"), ("lottery_tickets", "lottery_tickets"), ("deposit", "deposit"), ("sign", "sign_count")]:
                if fk in item and item[fk] is not None:
                    a.set(ak, str(item[fk]))
            ST.acct_save(gid, qq)

            # 3. group 奴隶系统数据（包含身价/主人/惩罚/工作/保护状态）
            if "group" in item and isinstance(item["group"], dict):
                g = ST.group(gid)
                if not g.has_section(qq):
                    g.add_section(qq)
                for k, v in item["group"].items():
                    g[qq][str(k)] = str(v)
                g._dirty = True
                ST.save_group(gid)

            # 4. 昵称
            n = item.get("name")
            if n:
                slave.NOTE_NAMES[qq] = str(n)
            ok += 1

        ST.register_names(slave.NOTE_NAMES)
        ST.flush_all()
        return json_response({"ok": True, "imported": ok, "total": len(users)})
    except Exception as e:
        return _err(f"import failed: {e}", 500)


async def handle_users_clean_left(request, context=None):
    """清理已退群人员的全部数据（钱包、账户、奴隶、精灵）"""
    p = await get_req_json(request, default={})

    gid = str(p.get("gid") or _extract_param(request, "gid", "") or "").strip()
    gids = []
    if gid and gid.isdigit():
        gids = [gid]
    else:
        try:
            if ST._DB is not None:
                for (g_,) in ST._DB.execute("SELECT DISTINCT gid FROM wallet").fetchall():
                    if str(g_).isdigit() and str(g_) not in gids:
                        gids.append(str(g_))
                for (g_,) in ST._DB.execute("SELECT DISTINCT gid FROM groups").fetchall():
                    if str(g_).isdigit() and str(g_) not in gids:
                        gids.append(str(g_))
        except Exception:
            pass

    if not gids:
        return json_response({"ok": True, "cleaned_count": 0, "msg": "未找到群聊数据"})

    fetch_qqs = None
    try:
        from .. import messaging as _plat
        fetch_qqs = _plat.fetch_group_member_qqs
    except Exception:
        pass

    cleaned_total = 0
    cleaned_details = {}
    failed_gids = []

    try:
        ST.flush_all()
    except Exception:
        pass

    for g in gids:
        live_qqs = None
        if fetch_qqs:
            try:
                live_qqs = await fetch_qqs(g, context=context)
            except Exception:
                live_qqs = None

        if live_qqs is None and "valid_qqs" in p and isinstance(p["valid_qqs"], list):
            live_qqs = set(str(x).strip() for x in p["valid_qqs"] if str(x).strip().isdigit())

        if live_qqs is None:
            failed_gids.append(g)
            continue

        db_qqs = set()
        try:
            for (q_,) in ST._DB.execute("SELECT qq FROM wallet WHERE gid=?", (int(g),)).fetchall():
                db_qqs.add(str(q_))
            for (q_,) in ST._DB.execute("SELECT qq FROM accounts WHERE gid=?", (int(g),)).fetchall():
                db_qqs.add(str(q_))
            for (q_,) in ST._DB.execute("SELECT qq FROM groups WHERE gid=?", (int(g),)).fetchall():
                db_qqs.add(str(q_))
        except Exception:
            pass

        left_qqs = [q for q in db_qqs if q.isdigit() and int(q) > 10000 and q not in live_qqs]
        if not left_qqs:
            continue

        st = None
        try:
            st = slave.state(g)
        except Exception:
            pass

        for q in left_qqs:
            try:
                # 1. 彻底清除账户内存缓存并清除脏标记
                if hasattr(ST, "_ACC_CACHE") and isinstance(ST._ACC_CACHE, dict):
                    for k in ((str(g), str(q)), (int(g), int(q)), (str(g), int(q)), (int(g), str(q))):
                        a_obj = ST._ACC_CACHE.pop(k, None)
                        if a_obj is not None:
                            a_obj.dirty = False
                            a_obj.kv.clear()

                # 2. 彻底删除数据库三表数据
                ST._DB.execute("DELETE FROM wallet WHERE gid=? AND qq=?", (int(g), int(q)))
                ST._DB.execute("DELETE FROM accounts WHERE gid=? AND qq=?", (int(g), int(q)))
                ST._DB.execute("DELETE FROM groups WHERE gid=? AND qq=?", (int(g), int(q)))
            except Exception:
                pass

            # 清理 store group 内存缓存
            try:
                if hasattr(ST, "_GROUP_CACHE") and isinstance(ST._GROUP_CACHE, dict):
                    for g_key in (str(g), int(g)):
                        g_obj = ST._GROUP_CACHE.get(g_key)
                        if g_obj is not None:
                            g_obj._users.pop(str(q), None)
                            g_obj._users.pop(int(q), None)
                            if hasattr(g_obj, "_dirty_qqs") and isinstance(g_obj._dirty_qqs, set):
                                g_obj._dirty_qqs.discard(str(q))
                                g_obj._dirty_qqs.discard(int(q))
            except Exception:
                pass

            if st:
                try:
                    if st.has_section(q):
                        st.remove_section(q)
                    for sec in st.sections():
                        if st[sec].get("owner") == q:
                            st[sec]["owner"] = ""
                            st[sec]["purchase_price"] = "0"
                            st[sec]["purchase_time"] = ""
                except Exception:
                    pass

        if st:
            try:
                slave.save(g)
            except Exception:
                pass

        cleaned_total += len(left_qqs)
        cleaned_details[g] = len(left_qqs)

    ST.flush_all()
    if not cleaned_details and failed_gids:
        return json_response({"ok": False, "msg": f"无法连接机器人获取群 {','.join(failed_gids[:3])} 的实时成员列表，请确保 Bot 在线且在群内"}, status=400)
    return json_response({
        "ok": True,
        "cleaned_count": cleaned_total,
        "details": cleaned_details,
        "failed_gids": failed_gids,
        "gid": gid or "all"
    })


async def handle_user_clear(request):
    """清除指定单用户的全部数据（钱包、账户、奴隶、精灵、新手礼包资格）"""
    gid = _extract_param(request, "gid", "").strip()
    qq = _extract_param(request, "qq", "").strip()
    # 兼容 Bridge GET query（get_req_query 跨框架）与 POST JSON Body
    if not gid:
        try:
            gid = str(get_req_query(request, "gid", "") or "").strip()
        except Exception:
            pass
    if not qq:
        try:
            qq = str(get_req_query(request, "qq", "") or "").strip()
        except Exception:
            pass
    if not gid or not qq:
        try:
            p = await get_req_json(request, default={})
            if isinstance(p, dict):
                if not gid and p.get("gid"):
                    gid = str(p.get("gid")).strip()
                if not qq and p.get("qq"):
                    qq = str(p.get("qq")).strip()
        except Exception:
            pass

    if not gid or not qq:
        return _err("gid and qq required", 400)
    if not (gid.isdigit() and qq.isdigit()):
        return _err("gid and qq must be digits", 400)

    try:
        # 1. 底层存储与三表数据清除 (wallet, accounts, groups)
        if hasattr(ST, "user_clear"):
            ST.user_clear(gid, qq)
        else:
            if ST._DB is not None:
                ST._DB.execute("DELETE FROM wallet WHERE gid=? AND qq=?", (int(gid), int(qq)))
                ST._DB.execute("DELETE FROM accounts WHERE gid=? AND qq=?", (int(gid), int(qq)))
                ST._DB.execute("DELETE FROM groups WHERE gid=? AND qq=?", (int(gid), int(qq)))

        # 2. 奴隶系统清理：解除奴隶身份并释放名下奴隶
        try:
            if hasattr(slave, "clear_user_slave"):
                slave.clear_user_slave(gid, qq)
            else:
                st = slave.state(gid)
                if hasattr(st, "remove_section"):
                    st.remove_section(qq)
                for sec in st.sections():
                    if str(sec) == qq:
                        continue
                    u = st[sec]
                    if str(u.get("owner", "")) == qq:
                        u["owner"] = ""
                        u["purchase_price"] = "0"
                        u["purchase_time"] = ""
                slave.save(gid)
        except Exception:
            pass

        # 2b. 清除分群昵称内存（防清除后列表仍显示幽灵名）
        try:
            if hasattr(slave, "clear_note_name"):
                slave.clear_note_name(gid, qq)
            else:
                try:
                    slave.NOTE_NAMES_BY_GROUP.pop((str(gid), str(qq)), None)
                except Exception:
                    pass
        except Exception:
            pass

        # 3. 强制刷写保证落盘
        ST.flush_all()
        return json_response({
            "ok": True,
            "gid": gid,
            "qq": qq,
            "msg": f"用户 {qq} 数据已彻底清除（包含奴隶、精灵与新手礼包）"
        })
    except Exception as e:
        return _err(f"clear failed: {e}", 500)



async def handle_users_airdrop(request):
    """批量全员/定向群福利空投分发"""
    try:
        data = await get_req_json(request, default={})
        if not isinstance(data, dict):
            return _err("invalid json body", 400)

        target_gid = str(data.get("gid") or "").strip()
        add_money = int(data.get("money") or 0)
        add_stamina = int(data.get("stamina") or 0)
        add_tickets = int(data.get("tickets") or 0)
        reason = str(data.get("reason") or "全员福利空投").strip()

        if add_money <= 0 and add_stamina <= 0 and add_tickets <= 0:
            return _err("请至少输入一项大于 0 的发放数值", 400)

        try:
            ST.flush_all()
        except Exception:
            pass

        def _collect_targets():
            _lock = getattr(ST, "_LOCK", None)
            if _lock is not None:
                _lock.acquire()
            try:
                cur = ST._DB.cursor()
                targets = set() # set of (gid, qq)

                if target_gid:
                    gid_arg = int(target_gid) if target_gid.isdigit() else str(target_gid)
                    cur.execute("SELECT gid, qq FROM wallet WHERE gid = ?", (gid_arg,))
                    for r in cur.fetchall():
                        targets.add((str(r[0]), str(r[1])))
                    cur.execute("SELECT gid, qq FROM accounts WHERE gid = ?", (gid_arg,))
                    for r in cur.fetchall():
                        targets.add((str(r[0]), str(r[1])))
                else:
                    cur.execute("SELECT gid, qq FROM wallet")
                    for r in cur.fetchall():
                        targets.add((str(r[0]), str(r[1])))
                    cur.execute("SELECT gid, qq FROM accounts")
                    for r in cur.fetchall():
                        targets.add((str(r[0]), str(r[1])))
                return targets
            finally:
                if _lock is not None:
                    try:
                        _lock.release()
                    except Exception:
                        pass

        targets = await asyncio.to_thread(_collect_targets)

        if not targets:
            return _err("未找到符合发放条件的目标用户", 404)

        def _do_airdrop():
            try:
                return _airdrop_batch(targets, add_money, add_stamina, add_tickets)
            except Exception:
                # 批量失败降级为逐用户老路径，保证发放不中断
                success_count = 0
                for g, q in targets:
                    try:
                        if add_money > 0:
                            ST.coins_add(g, q, add_money)
                        if add_stamina > 0:
                            ST.acct_add(g, q, "stamina", add_stamina)
                        if add_tickets > 0:
                            ST.acct_add(g, q, "lottery_tickets", add_tickets)
                        if add_stamina > 0 or add_tickets > 0:
                            ST.acct_save(g, q)
                        success_count += 1
                    except Exception:
                        pass
                return success_count

        success_count = await asyncio.to_thread(_do_airdrop)

        try:
            ST.flush_all()
        except Exception:
            pass

        return json_response({
            "ok": True,
            "target_count": success_count,
            "gid": target_gid or "all",
            "rewards": {
                "money": add_money,
                "stamina": add_stamina,
                "tickets": add_tickets
            },
            "reason": reason
        })
    except Exception as e:
        return _err(f"airdrop error: {e}", 500)


def _airdrop_batch(targets, add_money, add_stamina, add_tickets):
    """批量空投：缺失行补齐 + 条件更新 + 单事务一次提交（原 N 用户 × 3 事务）。

    语义与逐用户老路径一致：金币钳位 [0, 1e11]，体力/奖券下限 0；
    脏缓存用户走老路径保语义，其余批量后清缓存按需重载。返回成功数。
    """
    pairs = []
    for g, q in targets or []:
        try:
            pairs.append((int(g), int(q)))
        except Exception:
            continue
    if not pairs:
        return 0
    legacy, batched = [], []
    for gi, qi in pairs:
        _dirty = False
        try:
            for _k in ((str(gi), str(qi)), (gi, qi), (str(gi), qi), (gi, str(qi))):
                _a = ST._ACC_CACHE.get(_k)
                if _a is not None and getattr(_a, "dirty", False):
                    _dirty = True
                    break
        except Exception:
            _dirty = True
        (legacy if _dirty else batched).append((gi, qi))
    done = 0
    for g, q in legacy:
        try:
            if add_money > 0:
                ST.coins_add(g, q, add_money)
            if add_stamina > 0:
                ST.acct_add(g, q, "stamina", add_stamina)
            if add_tickets > 0:
                ST.acct_add(g, q, "lottery_tickets", add_tickets)
            if add_stamina > 0 or add_tickets > 0:
                ST.acct_save(g, q)
            done += 1
        except Exception:
            pass
    if not batched:
        return done
    with ST._LOCK:
        if ST._DB is None:
            raise RuntimeError("DB未初始化")
        try:
            if add_money > 0:
                ST._DB.executemany(
                    "INSERT OR IGNORE INTO wallet(gid, qq, money) VALUES(?, ?, 0)", batched)
                _cap = int(getattr(ST, "COIN_CAP", 100000000000))
                _sql_air = ("UPDATE wallet SET money = CASE WHEN money + ? < 0 THEN 0 "
                            "WHEN money + ? > " + str(_cap) + " THEN " + str(_cap) + " "
                            "ELSE money + ? END WHERE gid = ? AND qq = ?")
                ST._DB.executemany(
                    _sql_air,
                    [(add_money, add_money, add_money, g, q) for g, q in batched])
            if add_stamina > 0 or add_tickets > 0:
                ST._DB.executemany(
                    "INSERT OR IGNORE INTO accounts(gid, qq, data) VALUES(?, ?, '{}')", batched)
                if add_stamina > 0:
                    ST._DB.executemany(
                        "UPDATE accounts SET data = json_set(data, '$.stamina', CAST("
                        "CASE WHEN CAST(COALESCE(json_extract(data, '$.stamina'), '0') AS INTEGER) + ? < 0 THEN 0 "
                        "ELSE CAST(COALESCE(json_extract(data, '$.stamina'), '0') AS INTEGER) + ? END "
                        "AS TEXT)) WHERE gid = ? AND qq = ?",
                        [(add_stamina, add_stamina, g, q) for g, q in batched])
                if add_tickets > 0:
                    ST._DB.executemany(
                        "UPDATE accounts SET data = json_set(data, '$.lottery_tickets', CAST("
                        "CASE WHEN CAST(COALESCE(json_extract(data, '$.lottery_tickets'), '0') AS INTEGER) + ? < 0 THEN 0 "
                        "ELSE CAST(COALESCE(json_extract(data, '$.lottery_tickets'), '0') AS INTEGER) + ? END "
                        "AS TEXT)) WHERE gid = ? AND qq = ?",
                        [(add_tickets, add_tickets, g, q) for g, q in batched])
            ST._DB.commit()
        except Exception:
            try:
                ST._safe_rollback()
            except Exception:
                pass
            raise
    try:
        for g, q in batched:
            for _k in ((str(g), str(q)), (g, q), (str(g), q), (g, str(q))):
                _a = ST._ACC_CACHE.pop(_k, None)
                if _a is not None:
                    try:
                        _a.dirty = False
                        _a.kv.clear()
                    except Exception:
                        pass
    except Exception:
        pass
    return done + len(batched)
