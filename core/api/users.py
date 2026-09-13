# -*- coding: utf-8 -*-
"""用户管理 API — 列表/编辑/单用户清除/退群清理（导入导出已拆至 user_io.py，空投已拆至 airdrop.py，端点不变）"""
import asyncio
import json
try:
    from ..adapters import json_response
except ImportError:
    from core.adapters import json_response

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
            return "unknown"
try:
    PLUGIN_VERSION = _get_version()
except Exception:
    PLUGIN_VERSION = "unknown"


def _extract_param(request, key, default=""):
    """多源参数提取：统一走 web_utils.get_req_query（query/query_params/args/dict/全局代理全收）。
    旧多源分支已并入，保留函数名兼容 10 余处调用。"""
    try:
        return get_req_query(request, key, default)
    except Exception:
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
                    # 分群查询失败直接空：禁回退无 WHERE 全表（越群泄漏）
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
    money_target = None
    if "money" in p and str(p.get("money", "")).strip() != "":
        try:
            money_target = int(p["money"])
        except Exception:
            return _err("money must be int", 400)
        if money_target < 0:
            return _err("money must be non-negative", 400)
    _map_old = {"tili": "stamina", "meili": "charm", "jiangquan": "lottery_tickets", "cunkuan": "deposit"}
    norm_p = {}
    for k, v in p.items():
        nk = _map_old.get(k, k)
        norm_p[nk] = v
    p = norm_p
    updates = {}
    for fk in ("stamina", "charm", "lottery_tickets", "deposit"):
        if fk not in p:
            continue
        if str(p[fk]).strip() == "":
            continue
        try:
            val = int(p[fk])
        except Exception:
            return _err("%s must be int" % fk, 400)
        if val < 0:
            return _err("%s must be non-negative" % fk, 400)
        updates[fk] = str(val)
        out[fk] = val
    if money_target is None and not updates:
        return _err("no editable fields", 400)
    committed = ST.txn_coins_acct(
        gid, qq, 0, updates, money_target=money_target
    )
    if committed is None:
        return _err("edit failed: storage error", 500)
    if money_target is not None:
        out["money"] = committed
    return json_response({"saved": True, "qq": qq, "gid": gid, **out})


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

        # 活名单归一化 str：整型混入即“全员不在”致误删整群
        if live_qqs is not None:
            try:
                live_qqs = set(str(x).strip() for x in live_qqs)
            except Exception:
                live_qqs = None

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

        cleaned = 0
        for q in left_qqs:
            if not ST.user_clear(g, q):
                continue
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
                    continue
            cleaned += 1

        if st and cleaned:
            try:
                slave.save(g)
            except Exception:
                failed_gids.append(g)

        cleaned_total += cleaned
        if cleaned:
            cleaned_details[g] = cleaned

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
    p = await get_req_json(request, default={})
    gid = str(p.get("gid") or "").strip() if isinstance(p, dict) else ""
    qq = str(p.get("qq") or "").strip() if isinstance(p, dict) else ""

    if not gid or not qq:
        return _err("gid and qq required", 400)
    if not (gid.isdigit() and qq.isdigit()):
        return _err("gid and qq must be digits", 400)

    try:
        # 1. 底层存储与三表数据清除 (wallet, accounts, groups)；失败如实 500，不谎报 ok
        if hasattr(ST, "user_clear"):
            if not ST.user_clear(gid, qq):
                return _err("clear failed: storage error", 500)
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



