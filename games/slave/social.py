# -*- coding: utf-8 -*-
"""games/slave/social.py — 奴隶包·social（原 slave.py 切分，语义不变）。"""
import time as _time
import random as _random
import datetime as _dt
try:
    from ...core import storage as ST
except ImportError:
    from core import storage as ST
from . import slave_state as _S
try:
    from ..config.slave import (STUDY_FEE_LO, STUDY_FEE_HI, STUDY_EXP_LO, STUDY_EXP_HI,
                                PRAY_LOSE_CHANCE, PRAY_LOSE_LO, PRAY_LOSE_HI, PRAY_NINJA_CHANCE,
                                WORK_BASE_LO, WORK_BASE_HI, WORK_WORTH_DIV, WORK_WAGE_FLOOR,
                                WORK_PCT_CAP,
                                REVOLT_FINE, REVOLT_LOOT_LO, REVOLT_LOOT_HI,
                                TREASURE_GOURD_NAME)
except ImportError:
    from games.config.slave import (STUDY_FEE_LO, STUDY_FEE_HI, STUDY_EXP_LO, STUDY_EXP_HI,  # type: ignore
                                    PRAY_LOSE_CHANCE, PRAY_LOSE_LO, PRAY_LOSE_HI, PRAY_NINJA_CHANCE,
                                    WORK_BASE_LO, WORK_BASE_HI, WORK_WORTH_DIV, WORK_WAGE_FLOOR,
                                    WORK_PCT_CAP,
                                    REVOLT_FINE, REVOLT_LOOT_LO, REVOLT_LOOT_HI,
                                    TREASURE_GOURD_NAME)
from .base import U, _event_delta, _fmt, _safe_int, cd_check, cd_commit, cfgi, cn_fmt, cn_parse, coins_add, coins_get, slaves_of, treasures_of, uget, uset
from .combat import _has_treasure_type, _treasure_names, _treasure_pct_total, battle_power
from .nick import uname
from .profile import coin_name
def cmd_flatter(gid, qq, st):
    u = U(st, qq)
    owner = uget(u, "owner")
    if not owner:
        return _S.T.FLATTER_NO_OWNER
    ok, mins = cd_check(u, "flatter_time", "讨好间隔")
    if not ok:
        return _fmt(mins, "讨好主人")
    if int(uget(u, "price") or 0) > int(U(st, owner).get("price") or 0):
        return _S.T.FLATTER_RICHER
    mc = coins_get(gid, owner)
    if mc <= 0:
        return _S.T.FLATTER_POOR_M
    if _random.randint(1, 100) <= cfgi("概率配置", "讨好概率", 80):
        got = _random.randint(50, max(50, min(mc, 500)))
        got = min(got, mc)
        coins_add(gid, owner, -got)
        cd_commit(u, "flatter_time")
        coins_add(gid, qq, got)
        return _S.T.FLATTER_OK.format(got=got)
    return "你各种撒娇打泼，主人仍不为所动，你什么都没有讨到~"




def _grant_treasure(gid, qq, st):
    treas = _treasure_names()
    if not treas:
        return None
    t = _random.choice(treas)
    u = U(st, qq)
    uset(u, t, str(int(uget(u, t, "0")) + 1))
    # Fix N-C03: maintain 宝物 list
    lst = treasures_of(u)
    if t not in lst:
        lst.append(t)
        uset(u, "treasure", "|".join(lst))
    return t




def cmd_study(gid, qq, st):
    u = U(st, qq)
    owner = uget(u, "owner")
    ok, mins = cd_check(u, "study_time", "学习间隔")
    if not ok:
        return _fmt(mins, "学习")
    fee = _random.randint(STUDY_FEE_LO, STUDY_FEE_HI)
    if owner:
        oc = coins_get(gid, owner)
        if oc < fee:
            return _S.T.STUDY_POOR_MASTER.format(fee=fee)
    # 学费由主人支付(原版机制); 无主者自付
    payer = owner if owner else qq
    coins_add(gid, payer, -fee)
    exp_gain = _random.randint(STUDY_EXP_LO, STUDY_EXP_HI)
    uset(u, "weapon_exp", str(int(uget(u, "weapon_exp", "0") or 0) + exp_gain))
    cd_commit(u, "study_time")
    head = f"缴纳学费 {fee} 后开始学习! 武器经验 +{exp_gain}"
    # 奇遇事件: 学习类剧情 + 概率获得宝物
    evs = [e for e in _S.EVENTS if e.get("type") == "学习"]
    tail = ""
    if evs:
        ev = _random.choice(evs)
        content = ev.get("text", "")
        effect = ev.get("effect", "")
        delta = _event_delta()
        if "上涨" in effect:
            newp = min(_S.MAX_PRICE, int(uget(u, "price") or 0) + delta)
            uset(u, "price", str(newp))
            tail = f"\r\n🍀奇遇: {content}\r\n奴隶身价上涨 {delta}"
        elif "下跌" in effect:
            cur_p = int(uget(u, "price") or 0)
            if cur_p <= cfgi("费用配置", "初始身价", 1000):
                newp = min(_S.MAX_PRICE, cur_p + delta)
                uset(u, "price", str(newp))
                tail = (f"\r\n🍀奇遇: {content}\r\n"
                        f"因为你的身价过低触发系统双倍保护，奴隶身价上涨 {newp - cur_p}")
            else:
                newp = max(100, cur_p - delta)
                uset(u, "price", str(newp))
                tail = f"\r\n🍀奇遇: {content}\r\n奴隶身价下跌 {delta}"
        else:
            tail = f"\r\n🍀奇遇: {content}"
    # 奇遇触发概率 -> 额外获得宝物
    if _random.randint(1, 100) <= cfgi("设置", "奇遇触发概率", 6):
        t = _grant_treasure(gid, qq, st)
        if t:
            tail += f"\r\n🎁 奇遇事件中获得宝物【{t}】!"
    return head + tail




def cmd_pray(gid, qq, st):
    """祭拜忍神: 每天12点后可祈福一次"""
    u = U(st, qq)
    now = _dt.datetime.now()
    today = now.strftime("%Y-%m-%d")
    if now.hour < 12:
        return _S.T.PRAY_TIME_NOTYET
    if uget(u, "pray_date") == today:
        return "今天已经祭拜过忍神了, 明天中午12点再来~"
    ok, mins = cd_check(u, "pray_time", "祈福间隔")
    if not ok:
        return _fmt(mins, "祈福")
    uset(u, "pray_date", today)
    cd_commit(u, "pray_time")
    name = uname(st, qq)
    cn = coin_name()
    if _random.randint(1, 100) <= cfgi("祈福配置", "人品爆发概率", 15):
        amt = cfgi("祈福配置", "人品爆发奖励", 30000)
        coins_add(gid, qq, amt)
        return _S.T.PRAY_BIG.format(amt=f"{amt}{cn}") + f"\r\n[{name}] 获得 {amt} {cn}!!"
    if _random.randint(1, 100) <= PRAY_LOSE_CHANCE:
        lose = min(coins_get(gid, qq), _random.randint(PRAY_LOSE_LO, PRAY_LOSE_HI))
        coins_add(gid, qq, -lose)
        return (_S.T.PRAY_PITY_HEAD.format(who=f"[{name}]")
                + f"\r\n被顺走了 {lose} {cn}...")
    lo = cfgi("祈福配置", "祈福奖励下限", 1000)
    hi = cfgi("祈福配置", "祈福奖励上限", 6000)
    if _random.randint(1, 100) <= PRAY_NINJA_CHANCE:
        amt = _random.randint(lo, hi)
        coins_add(gid, qq, amt)
        return _S.T.PRAY_NINJA.format(who=f"[{name}]", amt=f"{amt}{cn}")
    amt = _random.randint(max(lo // 2, 10), max(hi // 4, 100))
    coins_add(gid, qq, amt)
    return _S.T.PRAY_NORMAL.format(who=f"[{name}]", amt=f"{amt}{cn}")


# ============================================================
# 逻辑层 · 第5块: 打工两段式 / 造反剧情线
# ============================================================
def cmd_work_dispatch(gid, qq, st):
    u = U(st, qq)
    my = slaves_of(st, qq)
    if not my:
        return _S.T.WORK_NO_SLAVE
    if uget(u, "work_status") == "真":
        started = cn_parse(uget(u, "work_time")) or 0
        duration = cfgi("间隔配置", "打工间隔", 1) * 60
        left = started + duration - _time.time()
        if left > 0:
            return _S.T.WORK_WORKING.format(min=int(left / 60) + 1)
        # 超时先结算旧轮工资，防重派覆盖快照致上轮收益丢失
        _old_wage = _safe_int(uget(u, "work_wage"), 0)
        if _old_wage > 0:
            try:
                cmd_work_collect(gid, qq, st)
            except Exception:
                pass
        uset(u, "work_status", "")   # 超时自动收工
    duration = cfgi("间隔配置", "打工间隔", 1)
    target = 0
    for s in my:
        su = U(st, s)
        w = _random.randint(WORK_BASE_LO, WORK_BASE_HI) + int(uget(su, "price") or 0) // WORK_WORTH_DIV
        uset(su, "_work_wage", str(w))
        target += w
    uset(u, "work_status", "真")
    uset(u, "work_time", cn_fmt(_time.time()))
    uset(u, "work_wage", str(target))
    return _S.T.WORK_DISPATCH.format(target=target, min=duration)




def cmd_work_collect(gid, qq, st):
    u = U(st, qq)
    my = slaves_of(st, qq)
    if not my:
        return _S.T.WORK_NO_SLAVE
    if uget(u, "work_status") != "真":
        return _S.T.WORK_NOT_STARTED
    started = cn_parse(uget(u, "work_time")) or 0
    duration = cfgi("间隔配置", "打工间隔", 1) * 60
    left = started + duration - _time.time()
    if left > 0:
        return _S.T.WORK_WAIT.format(min=int(left / 60) + 1)

    ratio = cfgi("费用配置", "工资比例", 50)
    try:
        _work_bonus = _treasure_pct_total(treasures_of(u), "work", WORK_PCT_CAP)
    except Exception:
        _work_bonus = 0
    total = _safe_int(uget(u, "work_wage"), 0)
    lines = [_S.T.WORK_COLLECT.format(total=total)]
    wage_paid = 0
    for s in my:
        su = U(st, s)
        # 打工后新买入的奴隶无本轮工资快照，不参与结算（防0工资误导与快照脱节）
        if not str(uget(su, "_work_wage", "") or "").strip():
            lines.append(f"[{uname(st,s)}]新加入未参与本次打工，无工资")
            continue
        wage = _safe_int(uget(su, "_work_wage"), 0)
        if _safe_int(uget(su, "price"), 0) < WORK_WAGE_FLOOR:
            lines.append(f"[{uname(st,s)}]{_S.T.WORK_NO_WAGE}")
            continue
        got = wage * ratio // 100
        if _work_bonus > 0:
            got += got * _work_bonus // 100
        coins_add(gid, s, got)
        wage_paid += got
        lines.append(f"[{uname(st,s)}]{_S.T.WORK_GOT_WAGE.format(wage=got)}")
        uset(su, "_work_wage", "")
    master_net = total - wage_paid
    if master_net > 0:
        coins_add(gid, qq, master_net)
    uset(u, "work_status", "")
    uset(u, "work_time", "")
    lines.append(_S.T.WORK_WAGE_TOTAL.format(wage=wage_paid))
    lines.append(_S.T.WORK_MASTER_GET.format(got=max(0, master_net)))
    return "\r\n".join(lines)




def cmd_revolt(gid, qq, st):
    u = U(st, qq)
    owner = uget(u, "owner")
    if not owner:
        return _S.T.REVOLT_NO_OWNER
    ok, mins = cd_check(u, "造反时间", "造反间隔")
    if not ok:
        return _fmt(mins, "造反")
    need = max(500, int(uget(u, "price") or 0) // 10)
    if coins_get(gid, qq) < need:
        return _S.T.REVOLT_TOO_POOR.format(need=need)
    cd_commit(u, "造反时间")
    # 主人奴隶数量是我方两倍 -> 镇压
    m_slaves = len(slaves_of(st, owner))
    my_power = battle_power(st, qq)
    om_power = battle_power(st, owner)
    if m_slaves >= 2 * max(1, len(slaves_of(st, qq))) and om_power > my_power:
        fine = min(coins_get(gid, qq), REVOLT_FINE)
        coins_add(gid, qq, -fine)
        coins_add(gid, owner, fine)
        return _S.T.REVOLT_CRUSHED + f"(被罚{fine})"
    sn = uget(u, "name") or (str(qq))
    loot = min(coins_get(gid, owner), _random.randint(REVOLT_LOOT_LO, REVOLT_LOOT_HI))

    i_have_gourd = _has_treasure_type(treasures_of(u), "pardon", (TREASURE_GOURD_NAME,))
    master_has_gourd = _has_treasure_type(treasures_of(U(st, owner)), "pardon", (TREASURE_GOURD_NAME,))

    if i_have_gourd:
        uset(u, "owner", "")
        uset(u, "protect_until", "")
        uset(u, "protector", "")
        coins_add(gid, owner, -loot)
        coins_add(gid, qq, loot)
        return (_S.T.RV_GOURD_WIN + "\r\n" + _S.T.RV_LOOT.format(loot=loot, coin=coin_name())
                + "\r\n" + _S.T.REVOLT_FREE.replace("，", ""))
    if master_has_gourd:
        pay = min(coins_get(gid, qq), loot)
        coins_add(gid, qq, -pay)
        coins_add(gid, owner, pay)
        return _S.T.RV_GOURD_LOSE + f"({pay}{coin_name()})\r\n" + _S.T.REVOLT_FAIL_STAY
    if _random.randint(1, 100) <= cfgi("概率配置", "造反概率", 20):
        uset(u, "owner", "")
        uset(u, "protect_until", "")
        uset(u, "protector", "")
        coins_add(gid, owner, -loot)
        coins_add(gid, qq, loot)
        return (_S.T.RV_NORMAL_WIN + f"\r\n[{sn}] " + _S.T.RV_LOOT.format(loot=loot, coin=coin_name())
                + "\r\n" + _S.T.REVOLT_FREE.replace("，", ""))
    pay = min(coins_get(gid, qq), 500)
    coins_add(gid, qq, -pay)
    coins_add(gid, owner, pay)
    return (_S.T.RV_NORMAL_LOSE + f"(罚{pay}{coin_name()})\r\n"
            + f"[{sn}]" + _S.T.REVOLT_FAIL_STAY)


# ============================================================
# 逻辑层 · 第6块: 奴隶群战 / 抽卡 / 升星 / 升阶
# ============================================================


__all__ = ["cmd_flatter", "cmd_pray", "cmd_revolt", "cmd_study", "cmd_work_collect", "cmd_work_dispatch"]
