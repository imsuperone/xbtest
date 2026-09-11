# -*- coding: utf-8 -*-
"""games/slave/profile.py — 奴隶包·profile（原 base.py 切分，语义不变）。"""
import time as _time
import datetime as _dt
try:
    from ...core import storage as ST
    store = ST
except ImportError:
    from core import storage as ST
    store = ST
from . import slave_state as _S
from .base import U, _safe_int, cfg, cfgi, coins_get, protected_until, slaves_of, star_of, treasures_of, uget, uset, weapons_of
from .nick import uname


def cmd_menu():
    return _S.T.MENU




def cmd_myinfo(gid, qq, st):
    try:
        if _S.BOT_UIN and str(qq) == str(_S.BOT_UIN):
            return _S.T.BOT_NO_JOIN
        u = U(st, qq)
        coins = coins_get(gid, qq)
        price = _safe_int(uget(u, "price"), 500)
        owner = uget(u, "owner")
        prot = protected_until(u)
        if prot and prot > _time.time():
            ptxt = f"🛡️{int((prot-_time.time())/60)}分"
        else:
            ptxt = _S.T.NO_PROTECT
        sign_total, sign_streak = _sign_info(gid, qq, st)
        wexp = _safe_int(uget(u, "weapon_exp"), 0)
        slaves = slaves_of(st, qq)
        cap = _safe_int(uget(u, "slave_slots"), cfgi("设置", "奴隶个数", 5))
        if cap <= 0:
            cap = 2
        sl_txt = ", ".join(uname(st, s) for s in slaves) or _S.T.NO_SLAVE
        w_list = weapons_of(u)
        t_list = treasures_of(u)
        acct = store.acct(gid, qq)
        dep = acct.int("deposit")
        tili = acct.int("stamina")
        meili = acct.int("charm")
        jq = acct.int("lottery_tickets")
        lines = [
            f"📋【{uname(st,qq)}】的档案",
            f"💰资产：{coins}{coin_name()}｜🏦存款：{dep}｜💎身价：{price}",
            f"🔋体力：{tili}｜💄魅力：{meili}｜🎫奖券：{jq}｜📖经验：{wexp}",
            f"👑主人：{uname(st, owner) if owner else _S.T.NO_OWNER}｜{ptxt}｜📅总签{sign_total}·连签{sign_streak}天",
            f"⚔️武器：{', '.join(f'{w}★{star_of(u,w)}' for w in w_list) if w_list else _S.T.NO_WEAPON}",
            f"🎁宝物：{', '.join(t_list) if t_list else _S.T.NO_TREASURE}",
            f"👥奴隶({len(slaves)}/{cap})：{sl_txt}",
        ]
        return "\r\n".join(lines)
    except Exception as e:
        # 兜底防御：发生未预料异常时依然返回完整版档案格式，杜绝退化为简版
        try:
            name = uname(st, qq) if 'st' in locals() else str(qq)
            coins = store.coins_get(gid, qq)
            acct = store.acct(gid, qq)
            return ("📋【%s】的档案\r\n"
                    "💰资产：%d%s｜🏦存款：%d｜💎身价：500\r\n"
                    "🔋体力：%d｜💄魅力：%d｜🎫奖券：%d｜📖经验：0\r\n"
                    "👑主人：木有主人｜无人保护｜📅总签%d·连签%d天\r\n"
                    "⚔️武器：木有武器\r\n"
                    "🎁宝物：木有宝物\r\n"
                    "👥奴隶(0/2)：木有奴隶" % (
                        name, coins, store.coin_name(), acct.int("deposit"),
                        acct.int("stamina"), acct.int("charm"), acct.int("lottery_tickets"),
                        acct.int("sign_count"), acct.int("consecutive_days")
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
    if _S.BOT_UIN and str(target) == str(_S.BOT_UIN):
        return _S.T.BOT_NO_JOIN
    # 只要 target 存在即自动建档并展示，不再拦截“还没加入游戏”
    return cmd_myinfo(gid, target, st)



def cmd_rank_price(gid, st):
    lst = sorted(((int(uget(st[s], "price") or 0), s)
                  for s in st.sections()
                  if s.isdigit() and not (_S.BOT_UIN and s == str(_S.BOT_UIN))),
                 reverse=True)[:10]
    out = ["🏆 身价排行榜"]
    for i, (p, q) in enumerate(lst, 1):
        out.append(f"{i}. [{uname(st, q)}] {p}")
    return "\r\n".join(out)
def cmd_rank_sign(gid, st):
    """签到次数来自本地档案(总签天数), 不再依赖 drea"""
    lst = []
    for q in st.sections():
        if not q.isdigit():
            continue
        if _S.BOT_UIN and q == str(_S.BOT_UIN):
            continue
        try:
            dcount = int(uget(st[q], "total_sign_days", "0") or 0)
        except Exception:
            dcount = 0
        lst.append((dcount, q))
    lst.sort(reverse=True)
    out = ["📅 签到排行榜"]
    for i, (dcount, q) in enumerate(lst[:10], 1):
        nm = uget(st[q], "name") if st.has_section(q) else ""
        out.append(f"{i}. [{nm or q}] {dcount}天")
    return "\r\n".join(out)
def cmd_rank(gid, st):
    return cmd_rank_price(gid, st) + "\r\n\r\n" + cmd_rank_sign(gid, st)

__all__ = ["cmd_menu", "cmd_myinfo", "cmd_query", "cmd_rank", "cmd_rank_price", "cmd_rank_sign", "coin_name"]
