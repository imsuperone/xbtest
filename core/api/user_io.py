# -*- coding: utf-8 -*-
"""用户导入导出 API — 单用户/全量导出导入（由 users.py 独立拆出，端点不变）。"""
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
            return "2026w0912a"
try:
    PLUGIN_VERSION = _get_version()
except Exception:
    PLUGIN_VERSION = "2026w0912a"


def _extract_param(request, key, default=""):
    """多源参数提取：统一走 web_utils.get_req_query（query/query_params/args/dict/全局代理全收）。
    旧多源分支已并入，保留函数名兼容 10 余处调用。"""
    try:
        return get_req_query(request, key, default)
    except Exception:
        return str(default)


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

        # 打包（JSON 序列化 + base64，大库时上 MB 级，走线程池不冻消息循环）
        def _pack():
            payload = {"count": len(out), "users": out, "export_at": int(time.time()), "version": PLUGIN_VERSION}
            data_bytes = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
            fn = f"xbbot_users_{'all' if not gid_valid else gid_valid}_{int(time.time())}.json"
            b64 = base64.b64encode(data_bytes).decode()
            return payload, data_bytes, b64, fn
        payload, data_bytes, b64, fn = await asyncio.to_thread(_pack)
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


