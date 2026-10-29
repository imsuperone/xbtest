# -*- coding: utf-8 -*-
"""games/slave/profile.py — 奴隶包·profile（原 base.py 切分，语义不变）。"""
import time as _time
import datetime as _dt
from ...core import storage as ST
store = ST
from . import slave_state as _S
from .base import U, _safe_int, cd_check, cfg, cfgi, cn_parse, coins_get, protected_until, slaves_of, star_of, treasures_of, uget, user_slave_slots, uset, weapons_of
from .nick import uname


def cmd_menu():
    return _S.T.MENU


def _build_status_line(gid, qq, u, acct, slaves):
    """构建个人档案底部的实时冷却与挂机状态栏"""
    import json as _j
    parts = []
    try:
        ok_bz, mins_bz = cd_check(u, "搬砖时间", "搬砖间隔")
        parts.append("搬砖就绪" if ok_bz else f"搬砖({mins_bz})")
    except Exception:
        pass
    try:
        if uget(u, "work_status") == "真":
            started = cn_parse(uget(u, "work_time")) or 0
            dur = cfgi("间隔配置", "打工间隔", 15) * 60
            left = started + dur - _time.time()
            parts.append(f"奴隶打工({max(1, (int(left) + 59) // 60)}分)" if left > 0 else "奴隶可收工!")
        elif slaves:
            parts.append("奴隶空闲")
    except Exception:
        pass
    try:
        sp = _j.loads(acct.get("spirits", "{}") or "{}")
        now_i = int(_time.time())
        tr = sp.get("travel")
        if isinstance(tr, dict) and tr.get("name") and tr.get("ts"):
            left_s = int(tr.get("ts", 0)) + max(60, int(tr.get("dur", 3600) or 3600)) - now_i
            parts.append(f"旅行({max(1, (int(left_s) + 59) // 60)}分)" if left_s > 0 else "旅行可收获!")
        expd = sp.get("expedition")
        if isinstance(expd, dict) and expd.get("names") and expd.get("ts"):
            left_s2 = int(expd.get("ts", 0)) + max(60, int(expd.get("dur", 7200) or 7200)) - now_i
            parts.append(f"远征({max(1, (int(left_s2) + 59) // 60)}分)" if left_s2 > 0 else "远征可收获!")
    except Exception:
        pass
    return f"⏳状态: {' | '.join(parts)}" if parts else ""


def cmd_myinfo(gid, qq, st):
    try:
        import json as _j
        if _S.is_bot_qq(qq):
            return _S.T.BOT_NO_JOIN
        u = U(st, qq)
        acct = store.acct(gid, qq)
        coins = store.coins_get(gid, qq)
        dep = acct.int("deposit")
        price = _safe_int(uget(u, "price"), cfgi("费用配置", "初始身价", 1000))
        owner = uget(u, "owner")
        prot = protected_until(u)
        if prot and prot > _time.time():
            ptxt = f"🛡️{int((prot-_time.time())/60)}分"
        else:
            ptxt = _S.T.NO_PROTECT
        sign_total, sign_streak = _sign_info(gid, qq, st)
        wexp = _safe_int(uget(u, "weapon_exp"), 0)
        slaves = slaves_of(st, qq)
        cap = user_slave_slots(u)
        sl_txt = ", ".join(uname(st, s) for s in slaves) or _S.T.NO_SLAVE
        w_list = weapons_of(u)
        t_list = treasures_of(u)
        tili = min(300, max(0, acct.int("stamina")))
        meili = acct.int("charm")
        jq = acct.int("lottery_tickets")
        t_disp = [f"{t}★{_safe_int(uget(u, t+'升阶', '0'), 0)}" if _safe_int(uget(u, t+'升阶', '0'), 0) > 0 else t for t in t_list]
        lines = [
            f"📋[{uname(st,qq)}]的档案",
            f"💰资产:{store.fmt_coins(coins)}{coin_name()} | 🏦存款:{store.fmt_coins(dep)} | 💎身价:{store.fmt_coins(price)}",
            f"🔋体力:({tili}/300) | 💄魅力:{meili} | 🎫奖券:{jq} | 📖经验:{wexp}",
            f"👑主人:{uname(st, owner) if owner else _S.T.NO_OWNER} | {ptxt} | 📅总签{sign_total}·连签{sign_streak}天",
            f"⚔️武器:{', '.join(f'{w}★{star_of(u,w)}' for w in w_list) if w_list else _S.T.NO_WEAPON}",
            f"🎁宝物:{', '.join(t_disp) if t_disp else _S.T.NO_TREASURE}",
            f"👥奴隶({len(slaves)}/{cap}): {sl_txt}",
        ]
        try:
            from ..ride import active_ride_info
            r_name, r_pct = active_ride_info(gid, qq)
            if r_name:
                from ..ride import _ride_buff_type
                _bmap = {"all": "综合", "atk": "战力", "work": "打工", "travel": "旅行"}
                _bt = _bmap.get(_ride_buff_type(r_name), "综合")
                ride_txt = f"{r_name}({_bt}+{r_pct}%)"
            else:
                ride_txt = "木有坐骑"
        except Exception:
            ride_txt = "木有坐骑"
        try:
            g_d = _j.loads(acct.get("guild", "{}") or "{}")
            g_name = str(g_d.get("name") or "").strip()
            guild_txt = f"{g_name}({g_d.get('pos', '成员')})" if g_name else "木有帮派"
        except Exception:
            guild_txt = "木有帮派"
        lines.append(f"🏎️坐骑:{ride_txt} | 🏰帮派:{guild_txt}")
        st_line = _build_status_line(gid, qq, u, acct, slaves)
        if st_line:
            lines.append(st_line)
        return "\r\n".join(lines)
    except Exception:
        # 兜底防御：发生未预料异常时依然返回完整版档案格式，杜绝退化为简版
        try:
            name = uname(st, qq) if 'st' in locals() else str(qq)
            coins = store.coins_get(gid, qq)
            acct = store.acct(gid, qq)
            init_p = cfgi("费用配置", "初始身价", 1000)
            return ("📋[%s]的档案\r\n"
                    "💰资产:%s%s | 🏦存款:%s | 💎身价:%s\r\n"
                    "🔋体力:(%d/300) | 💄魅力:%d | 🎫奖券:%d | 📖经验:0\r\n"
                    "👑主人:木有主人 | 无人保护 | 📅总签%d·连签%d天\r\n"
                    "⚔️武器:木有武器\r\n"
                    "🎁宝物:木有宝物\r\n"
                    "👥奴隶(0/%d): 木有奴隶" % (
                        name, store.fmt_coins(coins), store.coin_name(), store.fmt_coins(acct.int("deposit")), store.fmt_coins(init_p),
                        min(300, max(0, acct.int("stamina"))), acct.int("charm"), acct.int("lottery_tickets"),
                        acct.int("sign_count"), acct.int("consecutive_days"), max(1, cfgi("设置", "奴隶个数", 5))
                    ))
        except Exception:
            return "个人档案读取异常，请重试。"




def coin_name():
    return cfg("设置", "货币名称", "金币")




def _ymd(dtobj):
    return f"{dtobj.year}年{dtobj.month}月{dtobj.day}日"




def _sign_info(gid, qq, st):
    """总签/连签: 完全本地(不依赖drea) —— 总签与连签双向打通 sign 与 slave 存储"""
    try:
        u = U(st, qq)
        acct = ST.acct(gid, qq)
        today = _dt.date.today()
        today_s = _ymd(today)
        
        # 优先从 Acct(sign 引擎) 和 Group(slave 引擎) 取最大值，兼容新旧库
        total = max(
            _safe_int(uget(u, "total_sign_days", "0")),
            acct.int("sign_count"),
            acct.int("total_sign_days")
        )
        streak = max(
            _safe_int(uget(u, "shadow_streak", "0")),
            acct.int("consecutive_days"),
            _safe_int(uget(u, "consecutive_days", "0"))
        )
        seen = uget(u, "shadow_date") or acct.get("last_sign_date")
        
        # 检查是否今日已签到
        is_signed_today = (
            uget(u, "last_sign") == today.isoformat() or
            acct.get("sign_date") == today.isoformat() or
            acct.get("last_sign_date") == today.isoformat()
        )
        
        if is_signed_today:
            if seen != today_s and seen != today.isoformat():
                yest_s = _ymd(today - _dt.timedelta(days=1))
                yest_iso = (today - _dt.timedelta(days=1)).isoformat()
                streak = (streak + 1) if (seen == yest_s or seen == yest_iso) else max(streak, 1)
                uset(u, "shadow_streak", str(streak))
                uset(u, "shadow_date", today_s)
                acct.set("consecutive_days", str(streak))
                acct.set("last_sign_date", today.isoformat())
                ST.acct_save(gid, qq)
            return total, max(streak, 1)
        
        # 非今日签到
        return total, streak
    except Exception:
        return 0, 0




def cmd_query(gid, qq, target, st):
    if not target:
        return _S.T.QUERY_WHO
    if _S.is_bot_qq(target):
        return _S.T.BOT_NO_JOIN
    # 只要 target 存在即自动建档并展示，不再拦截“还没加入游戏”
    return cmd_myinfo(gid, target, st)



def cmd_rank_price(gid, st):
    lst = sorted(((int(uget(st[s], "price") or 0), s)
                  for s in st.sections()
                  if s.isdigit() and not _S.is_bot_qq(s)),
                 reverse=True)[:10]
    out = ["🏆 身价排行榜"]
    for i, (p, q) in enumerate(lst, 1):
        out.append(f"{i}. [{uname(st, q)}] {store.fmt_coins(p)}")
    return "\r\n".join(out)


def cmd_rank(gid, st):
    """奴隶系统排行榜：仅展示奴隶身价排行"""
    return cmd_rank_price(gid, st)


__all__ = ["cmd_menu", "cmd_myinfo", "cmd_query", "cmd_rank", "cmd_rank_price", "coin_name"]
