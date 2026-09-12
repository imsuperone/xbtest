"""游戏画像 API — 奴隶 / 精灵 用户画像 + 身价校准（图鉴已独立至 core/api/atlas.py，端点不变）"""
import asyncio
import json
try:
    from astrbot.api.web import json_response
except ImportError:
    def json_response(data, status=200):
        return data
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
def _to_int(v, default=0):
    """脏数据安全 int：一条脏 price 禁掀翻整表（画像页 500 根因）"""
    try:
        return int(str(v or 0).strip() or 0)
    except Exception:
        pass
    try:
        return int(float(str(v or 0).strip() or 0))
    except Exception:
        return default


def _slave_all_gids():
    """三表 DISTINCT gid 并集（slave 列表/校准共用，零语义差）"""
    gids = set()
    if ST._DB:
        for (g_id,) in ST._DB.execute("SELECT DISTINCT gid FROM groups").fetchall():
            if str(g_id).isdigit(): gids.add(str(g_id))
        for (g_id,) in ST._DB.execute("SELECT DISTINCT gid FROM wallet").fetchall():
            if str(g_id).isdigit(): gids.add(str(g_id))
        for (g_id,) in ST._DB.execute("SELECT DISTINCT gid FROM accounts").fetchall():
            if str(g_id).isdigit(): gids.add(str(g_id))
    return gids


def _slave_owner_count(st):
    """群主-奴隶计数 {owner: n}（slave 列表单群/全量共用，零语义差）"""
    _owner_cnt = {}
    for _s in [s for s in st.sections() if s.isdigit()]:
        try:
            _o = st[_s].get("owner", "") or ""
        except Exception:
            _o = ""
        if _o:
            _owner_cnt[_o] = _owner_cnt.get(_o, 0) + 1
    return _owner_cnt


async def handle_slave_users(request):    # 请求参数在事件循环上提取（request 对象禁跨线程），重活进线程池，不堵消息循环
    try:
        gid = get_req_query(request, "gid", "").strip()
        if not gid:
            j = await get_req_json(request, default={})
            if isinstance(j, dict) and j.get("gid"):
                gid = str(j.get("gid")).strip()
    except Exception as e:
        return _err(f"slave users failed: {e}", 500)

    def _work():
        try:
            default_init_price = ST.cfgi("费用配置", "初始身价", 500) if hasattr(ST, "cfgi") else 500
            if default_init_price <= 0: default_init_price = 500

            # 从 groups, wallet, accounts 聚合所有玩家
            out = []
            seen = set()

            if gid and gid.isdigit():
                st = slave.state(gid)
                _all_secs = [s for s in st.sections() if s.isdigit()]
                _owner_cnt = _slave_owner_count(st)
                _fixed = False
                for qq in _all_secs:
                    if not qq.isdigit(): continue
                    u = slave.U(st, qq)
                    p = _to_int(u.get("price", "0") or 0)
                    if p <= 0:
                        p = default_init_price
                        u["price"] = str(p)
                        st.mark_dirty(qq)
                        _fixed = True
                    seen.add((gid, str(qq)))
                    out.append({
                        "gid": gid,
                        "qq": str(qq),
                        "name": slave.NOTE_NAMES.get(str(qq), u.get("name", "") or str(qq)),
                        "price": p,
                        "owner": u.get("owner", "") or "",
                        "owner_name": slave.NOTE_NAMES.get(u.get("owner", ""), u.get("owner", "")) if u.get("owner") else "",
                        "protect": u.get("protect_until", ""),
                        "slaves": _owner_cnt.get(str(qq), 0),
                        "weapons": u.get("weapon", ""),
                        "treasures": u.get("treasure", ""),
                    })
                # 补该群 wallet 中有资产但尚未初始化的用户
                if ST._DB:
                    w_rows = ST._DB.execute("SELECT qq FROM wallet WHERE gid=?", (int(gid),)).fetchall()
                    for (w_qq,) in w_rows:
                        w_qq = str(w_qq)
                        if (gid, w_qq) in seen: continue
                        u = slave.U(st, w_qq)
                        p = _to_int(u.get("price", "0") or 0) or default_init_price
                        seen.add((gid, w_qq))
                        out.append({
                            "gid": gid, "qq": w_qq,
                            "name": slave.NOTE_NAMES.get(w_qq, w_qq),
                            "price": p, "owner": "", "owner_name": "",
                            "protect": "", "slaves": 0, "weapons": "", "treasures": ""
                        })
                if _fixed:
                    try:
                        slave.save(gid)
                    except Exception:
                        pass
            else:
                for g in _slave_all_gids():
                    try:
                        st = slave.state(g)
                        _g_fixed = False
                        _all_secs = [s for s in st.sections() if s.isdigit()]
                        _owner_cnt = _slave_owner_count(st)
                        for qq in _all_secs:
                            if not qq.isdigit(): continue
                            u = slave.U(st, qq)
                            p = _to_int(u.get("price", "0") or 0)
                            if p <= 0:
                                p = default_init_price
                                u["price"] = str(p)
                                st.mark_dirty(qq)
                                _g_fixed = True
                            seen.add((g, str(qq)))
                            out.append({
                                "gid": g,
                                "qq": str(qq),
                                "name": slave.NOTE_NAMES.get(str(qq), u.get("name", "") or str(qq)),
                                "price": p,
                                "owner": u.get("owner", "") or "",
                                "owner_name": slave.NOTE_NAMES.get(u.get("owner", ""), u.get("owner", "")) if u.get("owner") else "",
                                "protect": u.get("protect_until", ""),
                                "slaves": _owner_cnt.get(str(qq), 0),
                                "weapons": u.get("weapon", ""),
                                "treasures": u.get("treasure", ""),
                            })
                        if _g_fixed:
                            try:
                                slave.save(g)
                            except Exception:
                                pass
                    except Exception:
                        continue

            out.sort(key=lambda x: -x["price"])
            return json_response(out[:500])
        except Exception as e:
            return _err(f"slave users failed: {e}", 500)

    return await asyncio.to_thread(_work)
async def handle_slave_calibrate(request):
    """一键校准全员奴隶身价：将全库所有 <=0 的身价批量修复为最新初始身价"""
    try:
        data = await get_req_json(request, default={})
    except Exception as e:
        return _err(f"slave calibrate failed: {e}", 500)

    def _work():
        try:
            init_price = _to_int(data.get("price", 0) or 0)
            if init_price <= 0:
                init_price = ST.cfgi("费用配置", "初始身价", 500) if hasattr(ST, "cfgi") else 500
            if init_price <= 0:
                init_price = 500

            fixed_count = 0
            for g in _slave_all_gids():
                try:
                    st = slave.state(g)
                    # 检查已开户用户
                    for qq in list(st.sections()):
                        if not qq.isdigit(): continue
                        u = st[qq]
                        p = _to_int(u.get("price", "0") or 0)
                        if p <= 0:
                            u["price"] = str(init_price)
                            st.mark_dirty(qq)
                            fixed_count += 1
                    # 检查该群 wallet 玩家
                    if ST._DB:
                        w_rows = ST._DB.execute("SELECT qq FROM wallet WHERE gid=?", (int(g),)).fetchall()
                        for (w_qq,) in w_rows:
                            w_qq = str(w_qq)
                            if not st.has_section(w_qq):
                                u = slave.U(st, w_qq)
                                u["price"] = str(init_price)
                                st.mark_dirty(w_qq)
                                fixed_count += 1
                    slave.save(g)
                except Exception:
                    continue

            ST.flush_all()
            return json_response({
                "ok": True,
                "fixed_count": fixed_count,
                "initial_price": init_price,
                "msg": f"已成功校准 {fixed_count} 名用户的奴隶身价为 {init_price} {ST.coin_name() if hasattr(ST, 'coin_name') else '金币'}！"
            })
        except Exception as e:
            return _err(f"slave calibrate failed: {e}", 500)

    return await asyncio.to_thread(_work)
async def handle_spirit_users(request):
    try:
        gid = get_req_query(request, "gid", "").strip()
        if not gid:
            j = await get_req_json(request, default={})
            if isinstance(j, dict) and j.get("gid"):
                gid = str(j.get("gid")).strip()
    except Exception as e:
        return _err(f"spirit users failed: {e}", 500)

    def _work():
        try:
            out = []
            q = "SELECT gid, qq, data FROM accounts"
            args = ()
            if gid and gid.isdigit():
                q += " WHERE gid=?"
                args = (int(gid),)
            elif gid and not gid.isdigit():
                rows = []
                return json_response([])
            rows = ST._DB.execute(q, args).fetchall() if ST._DB else []
            for g, qq, data in rows:
                g = str(g); qq = str(qq)
                try:
                    kv = json.loads(data or "{}")
                except Exception:
                    kv = {}
                sp_raw = kv.get("spirits", "")
                sp = {}
                if isinstance(sp_raw, dict):
                    sp = sp_raw
                elif isinstance(sp_raw, str) and sp_raw.strip():
                    try:
                        sp = json.loads(sp_raw)
                    except Exception:
                        sp = {}
                if not isinstance(sp, dict) or not sp.get("list"):
                    continue
                lst = sp.get("list") if isinstance(sp.get("list"), list) else []
                if not lst:
                    continue

                def _power(it):
                    try:
                        return int(it.get("level", 1)) * (int(it.get("hp", 0)) + int(it.get("atk", 0)) + int(it.get("def", 0)) + int(it.get("spa", 0)) + int(it.get("spd", 0))) // 5
                    except Exception:
                        return 0

                active = str(sp.get("active", "") or "")
                bag = sp.get("bag", {}) if isinstance(sp.get("bag"), dict) else {}
                total_power = sum(_power(it) for it in lst)
                best = max(lst, key=_power) if lst else {}
                best_name = best.get("name", "") if isinstance(best, dict) else ""
                max_lv = max((int(it.get("level", 1)) for it in lst), default=1)
                out.append({
                    "gid": g,
                    "qq": qq,
                    "name": getattr(slave, "NOTE_NAMES", {}).get(qq, kv.get("name", "") or qq),
                    "count": len(lst),
                    "active": active,
                    "best": best_name,
                    "max_level": max_lv,
                    "total_power": total_power,
                    "bag_count": len(bag),
                })
            out.sort(key=lambda x: -x["total_power"])
            return json_response(out[:300])
        except Exception as e:
            return _err(f"spirit users failed: {e}", 500)

    return await asyncio.to_thread(_work)
# 图鉴 API 已独立至 core/api/atlas.py（_raw_spirit_cfg/_coerce_atlas_section/_load_spirit_data/handle_spirits_get/handle_spirits_save，端点不变）。
