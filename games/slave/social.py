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
                                WORK_BASE_LO, WORK_BASE_HI, WORK_WORTH_DIV, WORK_WORTH_CAP, WORK_WAGE_FLOOR,
                                WORK_PCT_CAP, WORK_CRIT_CHANCE, WORK_CRIT_LO, WORK_CRIT_HI,
                                SELF_WORK_LO, SELF_WORK_HI, SELF_WORK_BONUS_CAP, SELF_WORK_CRIT_CHANCE,
                                REVOLT_LOOT_LO, REVOLT_LOOT_HI,
                                TREASURE_GOURD_NAME,
                                CHARM_PROB_STEP, CHARM_PROB_BONUS, CHARM_PROB_CAP)
except ImportError:
    from games.config.slave import (STUDY_FEE_LO, STUDY_FEE_HI, STUDY_EXP_LO, STUDY_EXP_HI,  # type: ignore
                                    PRAY_LOSE_CHANCE, PRAY_LOSE_LO, PRAY_LOSE_HI, PRAY_NINJA_CHANCE,
                                    WORK_BASE_LO, WORK_BASE_HI, WORK_WORTH_DIV, WORK_WORTH_CAP, WORK_WAGE_FLOOR,
                                    WORK_PCT_CAP, WORK_CRIT_CHANCE, WORK_CRIT_LO, WORK_CRIT_HI,
                                    SELF_WORK_LO, SELF_WORK_HI, SELF_WORK_BONUS_CAP, SELF_WORK_CRIT_CHANCE,
                                    REVOLT_LOOT_LO, REVOLT_LOOT_HI,
                                    TREASURE_GOURD_NAME,
                                    CHARM_PROB_STEP, CHARM_PROB_BONUS, CHARM_PROB_CAP)
from .base import U, _event_delta, _fmt, _safe_int, cd_check, cd_commit, cfgi, cn_fmt, cn_parse, coins_add, coins_get, deduct_cash_or_deposit, slaves_of, total_assets, transfer_cash_or_deposit, treasures_of, uget, uset
from .combat import _has_treasure_type, _treasure_names, _treasure_pct_total, _treasure_trigger_prob, battle_power
from .nick import uname
from .profile import coin_name
def _charm_bonus(gid, qq):
    """魅力→成功率加成：每满 CHARM_PROB_STEP 点 +CHARM_PROB_BONUS%，封顶 CHARM_PROB_CAP%。"""
    try:
        charm = int(ST.acct(gid, qq).int("charm") or 0)
    except Exception:
        return 0
    if charm <= 0:
        return 0
    try:
        return int(min(CHARM_PROB_CAP, (charm // CHARM_PROB_STEP) * CHARM_PROB_BONUS))
    except Exception:
        return 0


def _charm_note(paid):
    return f"\r\n魅力-{paid}" if paid > 0 else ""


def _charge_charm(gid, qq, cost):
    """结算讨好魅力消耗（成败都扣，魅力=讨好燃料）。
    在结果已定的结算点扣费：DB 忙走重试路径时不双扣；扣费失败降级为未扣（奖励已定，禁倒挂）。"""
    if cost <= 0:
        return 0
    try:
        paid = min(int(cost), max(0, ST.acct(gid, qq).int("charm")))
        if paid <= 0:
            return 0
        if ST.acct_add(gid, qq, "charm", -paid) is None:
            return 0
        return paid
    except Exception:
        return 0


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
    mc = total_assets(gid, owner)
    if mc < 100:
        return _S.T.FLATTER_POOR_M
    charm_cost = cfgi("费用配置", "讨好消耗魅力", 5)
    try:
        charm_cost = int(charm_cost)
    except Exception:
        charm_cost = 5
    _flatter_p = cfgi("概率配置", "讨好概率", 80)
    try:
        from ..sign import eff_prob as _LP
        _flatter_p = _LP(_flatter_p, gid, qq)
    except Exception:
        pass
    # 魅力加成进成功率（w1004c：魅力=奴隶玩法硬通货）
    _flatter_p = max(0, min(100, _flatter_p + _charm_bonus(gid, qq)))
    if _random.randint(1, 100) <= _flatter_p:
        f_lo = max(1, cfgi("费用配置", "讨好收益下限", 50))
        f_hi = max(f_lo, cfgi("费用配置", "讨好收益上限", 500))
        got = _random.randint(min(f_lo, mc), max(min(f_lo, mc), min(mc, f_hi)))
        got = min(got, mc)
        if got <= 0:
            cd_commit(u, "flatter_time")
            return ("你各种撒娇打泼，主人仍不为所动，你什么都没有讨到~"
                    + _charm_note(_charge_charm(gid, qq, charm_cost)))
        paid_got = transfer_cash_or_deposit(gid, owner, qq, got)
        if paid_got is None:
            return "数据库繁忙，讨好结算未成功，请稍后重试。"
        if paid_got <= 0:
            return _S.T.FLATTER_POOR_M
        cd_commit(u, "flatter_time")
        return _S.T.FLATTER_OK.format(got=paid_got) + _charm_note(_charge_charm(gid, qq, charm_cost))
    cd_commit(u, "flatter_time")
    return ("你各种撒娇打泼，主人仍不为所动，你什么都没有讨到~"
            + _charm_note(_charge_charm(gid, qq, charm_cost)))




def _grant_treasure(gid, qq, st):
    """发放宝物：终身唯一机制。
    1. 候选池严格排除玩家已持有的宝物，绝对不重复获得；
    2. 若已集齐所有宝物，返回 (None, reward_coins, reward_exp) 转换为大额奇遇大奖；
    3. 成功获取新宝物，返回 (t, 0, 0)。
    """
    treas = _treasure_names()
    if not treas:
        return None
    u = U(st, qq)
    lst = treasures_of(u)
    unowned = [t for t in treas if t not in lst]
    if unowned:
        t = _random.choice(unowned)
        uset(u, t, "1")
        lst.append(t)
        uset(u, "treasure", "|".join(lst))
        return (t, 0, 0)
    # 全部集齐：转换为大额奇遇大奖（金币 + 经验）
    bonus_coins = cfgi("费用配置", "宝物集齐金币奖励", 8888)
    bonus_exp = cfgi("费用配置", "宝物集齐经验奖励", 500)
    try:
        coins_add(gid, qq, bonus_coins)
        cur_wexp = int(uget(u, "weapon_exp", "0") or 0)
        uset(u, "weapon_exp", str(cur_wexp + bonus_exp))
    except Exception:
        pass
    return (None, bonus_coins, bonus_exp)


def cmd_study(gid, qq, st):
    u = U(st, qq)
    ok, mins = cd_check(u, "study_time", "学习间隔")
    if not ok:
        return _fmt(mins, "学习")
    fee_lo = max(0, cfgi("费用配置", "学习学费下限", STUDY_FEE_LO))
    fee_hi = max(fee_lo, cfgi("费用配置", "学习学费上限", STUDY_FEE_HI))
    fee = _random.randint(fee_lo, fee_hi)
    if total_assets(gid, qq) < fee:
        return f"学费不足（需要 {fee} {coin_name()}），无法开始学习！"
    paid_fee = deduct_cash_or_deposit(gid, qq, fee, require_full=True)
    if paid_fee is None:
        return "数据库繁忙，学费扣款未成功，学习未开始，请稍后重试。"
    if paid_fee < fee:
        return f"学费不足（需要 {fee} {coin_name()}），无法开始学习！"
    exp_lo = max(1, cfgi("费用配置", "学习经验下限", STUDY_EXP_LO))
    exp_hi = max(exp_lo, cfgi("费用配置", "学习经验上限", STUDY_EXP_HI))
    exp_gain = _random.randint(exp_lo, exp_hi)
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
    # 奇遇触发概率 -> 额外获得宝物（叠每日打卡幸运加成）
    _qiyu_p = cfgi("设置", "奇遇触发概率", 6)
    try:
        from ..sign import eff_prob as _LP2
        _qiyu_p = _LP2(_qiyu_p, gid, qq)
    except Exception:
        pass
    if _random.randint(1, 100) <= _qiyu_p:
        res = _grant_treasure(gid, qq, st)
        if res:
            t, b_coins, b_exp = res
            if t:
                tail += f"\r\n🎁 奇遇事件中获得稀世宝物【{t}】!"
            elif b_coins or b_exp:
                tail += f"\r\n🌟 奇遇大吉！您已集齐全部稀世宝物，通晓天地之道，额外斩获：{coin_name()}+{ST.fmt_coins(b_coins)}、武器经验+{b_exp}！"
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
    _pray_big = cfgi("祈福配置", "人品爆发概率", 15)
    _pray_ninja = PRAY_NINJA_CHANCE
    try:
        from ..sign import eff_prob as _LP3
        _pray_big = _LP3(_pray_big, gid, qq)
        _pray_ninja = _LP3(_pray_ninja, gid, qq)
    except Exception:
        pass
    if _random.randint(1, 100) <= _pray_big:
        amt = cfgi("祈福配置", "人品爆发奖励", 30000)
        if coins_add(gid, qq, amt) is None:
            return "数据库繁忙，祈福奖励未到账，请稍后重试。"
        return _S.T.PRAY_BIG.format(amt=f"{amt}{cn}") + f"\r\n[{name}] 获得 {amt} {cn}!!"
    if _random.randint(1, 100) <= PRAY_LOSE_CHANCE:
        want_lose = _random.randint(PRAY_LOSE_LO, PRAY_LOSE_HI)
        cur_cash = coins_get(gid, qq)
        cur_dep = ST.acct(gid, qq).int("deposit")
        cash_lose = min(cur_cash, want_lose)
        dep_lose = min(cur_dep, max(0, want_lose - cash_lose))
        lose = cash_lose + dep_lose
        if lose > 0:
            updates = {"deposit": str(max(0, cur_dep - dep_lose))} if dep_lose > 0 else None
            if ST.txn_coins_acct(gid, qq, -cash_lose, updates) is None:
                return "数据库繁忙，祈福结算未成功，请稍后重试。"
        return (_S.T.PRAY_PITY_HEAD.format(who=f"[{name}]")
                + f"\r\n被顺走了 {lose} {cn}...")
    lo = cfgi("祈福配置", "祈福奖励下限", 1000)
    hi = cfgi("祈福配置", "祈福奖励上限", 6000)
    if _random.randint(1, 100) <= _pray_ninja:
        amt = _random.randint(lo, hi)
        if coins_add(gid, qq, amt) is None:
            return "数据库繁忙，祈福奖励未到账，请稍后重试。"
        return _S.T.PRAY_NINJA.format(who=f"[{name}]", amt=f"{amt}{cn}")
    amt = _random.randint(max(lo // 2, 10), max(hi // 4, 100))
    if coins_add(gid, qq, amt) is None:
        return "数据库繁忙，祈福奖励未到账，请稍后重试。"
    return _S.T.PRAY_NORMAL.format(who=f"[{name}]", amt=f"{amt}{cn}")


# ============================================================
# 逻辑层 · 第5块: 打工两段式 / 造反剧情线
# ============================================================
def cmd_work_dispatch(gid, qq, st):
    u = U(st, qq)
    my = slaves_of(st, qq)
    if not my:
        return _S.T.WORK_NO_SLAVE + "\r\n💡 发送【搬砖】可亲自打工赚取金币！"
    _prev_msg = ""
    if uget(u, "work_status") == "真":
        started = cn_parse(uget(u, "work_time")) or 0
        duration = cfgi("间隔配置", "打工间隔", 15) * 60
        left = started + duration - _time.time()
        if left > 0:
            return _S.T.WORK_WORKING.format(min=max(1, (int(left) + 59) // 60))
        # 超时先结算旧轮工资，防重派覆盖快照致上轮收益丢失
        _old_wage = _safe_int(uget(u, "work_wage"), 0)
        if _old_wage > 0:
            try:
                _prev_msg = cmd_work_collect(gid, qq, st) or ""
            except Exception:
                _prev_msg = ""
        uset(u, "work_status", "")   # 超时自动收工
    duration = cfgi("间隔配置", "打工间隔", 15)
    target = 0
    w_lo = max(0, cfgi("费用配置", "打工收益下限", WORK_BASE_LO))
    w_hi = max(w_lo, cfgi("费用配置", "打工收益上限", WORK_BASE_HI))
    for s in my:
        su = U(st, s)
        worth_bonus = min(WORK_WORTH_CAP, max(0, int(uget(su, "price") or 0)) // max(1, WORK_WORTH_DIV))
        w = _random.randint(w_lo, w_hi) + worth_bonus
        uset(su, "_work_wage", str(w))
        target += w
    uset(u, "work_status", "真")
    uset(u, "work_time", cn_fmt(_time.time()))
    uset(u, "work_wage", str(target))
    disp_msg = _S.T.WORK_DISPATCH.format(target=target, min=duration)
    return f"{_prev_msg}\r\n━━━━━━━━━━━━━━\r\n{disp_msg}" if _prev_msg else disp_msg


def cmd_work_collect(gid, qq, st):
    u = U(st, qq)
    my = slaves_of(st, qq)
    if not my:
        return _S.T.WORK_NO_SLAVE + "\r\n💡 发送【搬砖】可亲自打工赚取金币！"
    if uget(u, "work_status") != "真":
        return _S.T.WORK_NOT_STARTED
    started = cn_parse(uget(u, "work_time")) or 0
    duration = cfgi("间隔配置", "打工间隔", 15) * 60
    left = started + duration - _time.time()
    if left > 0:
        return _S.T.WORK_WAIT.format(min=max(1, (int(left) + 59) // 60))

    ratio = cfgi("费用配置", "工资比例", 50)
    try:
        _work_bonus = _treasure_pct_total(treasures_of(u), "work", WORK_PCT_CAP, u=u)
    except Exception:
        _work_bonus = 0
    try:
        try:
            from ..ride import active_ride_info
        except ImportError:
            from games.ride import active_ride_info  # type: ignore
        _, _r_pct = active_ride_info(gid, qq, aspect="work")
        _work_bonus += int(_r_pct or 0)
    except Exception:
        pass
    total = _safe_int(uget(u, "work_wage"), 0)
    lines = [_S.T.WORK_COLLECT.format(total=total)]
    wage_paid = 0
    _failed_names = []
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
        if got <= 0:
            uset(su, "_work_wage", "")
            continue
        # 系统增发：失败保留该奴隶快照（不清 _work_wage），如实告知而非冒领成功
        if coins_add(gid, s, got) is None:
            _failed_names.append(uname(st, s))
            continue
        wage_paid += got
        lines.append(f"[{uname(st,s)}]{_S.T.WORK_GOT_WAGE.format(wage=got)}")
        uset(su, "_work_wage", "")
    if _failed_names:
        lines.append("以下奴隶工资到账失败（系统繁忙，快照已保留，下轮收工可重结）："
                     + "、".join(f"[{n}]" for n in _failed_names))
    master_net = max(0, total - wage_paid)
    if _work_bonus > 0 and master_net > 0:
        master_net += master_net * _work_bonus // 100
    crit_bonus = 0
    if master_net > 0 and not _failed_names and _random.randint(1, 100) <= WORK_CRIT_CHANCE:
        crit_bonus = _random.randint(WORK_CRIT_LO, WORK_CRIT_HI)
        master_net += crit_bonus
    if master_net > 0:
        if coins_add(gid, qq, master_net) is None:
            lines.append("主人收益到账失败（系统繁忙），本轮收工状态已保留，可稍后重发送工。")
            return "\r\n".join(lines)
    if _failed_names:
        # 保留收工状态与剩余快照，允许下轮重结；已到账部分不重复发（快照已清）
        lines.append(_S.T.WORK_WAGE_TOTAL.format(wage=wage_paid))
        return "\r\n".join(lines)
    uset(u, "work_status", "")
    uset(u, "work_time", "")
    lines.append(_S.T.WORK_WAGE_TOTAL.format(wage=wage_paid))
    lines.append(_S.T.WORK_MASTER_GET.format(got=max(0, master_net)))
    if crit_bonus > 0:
        lines.append(f"🎉【打工大单】奴隶们超额完成商业订单，主人额外进账 +{crit_bonus}{coin_name()}！")
    return "\r\n".join(lines)


_SELF_WORK_JOBS = (
    ("去工地扛水泥砌墙", "工头直夸你手脚麻利"),
    ("跑腿闪送连送十单", "客户五星好评连连"),
    ("在夜市支摊猛火炒粉", "食客排起长龙一抢而空"),
    ("去漫展兼职特邀NPC", "互动人气爆棚收获打赏"),
    ("深夜代驾护送富豪回家", "老板随手甩下一笔小费"),
    ("帮豪门富婆溜三只哈士奇", "富婆对你十分满意"),
    ("通宵接单帮人紧急修Bug", "甲方当场爽快结清尾款"),
    ("去商业街发传单带货", "业绩全场第一拿下提成"),
)


def cmd_self_work(gid, qq, st):
    """自己打工（搬砖）：无需拥有奴隶，默认30分钟冷却、消耗15体力，收益与自身身价和魅力适度挂钩。"""
    u = U(st, qq)
    ok, mins = cd_check(u, "搬砖时间", "搬砖间隔")
    if not ok:
        return _fmt(mins, "搬砖")
    cs = max(1, cfgi("费用配置", "搬砖消耗体力", 15))
    acct = ST.acct(gid, qq)
    if acct.int("stamina") < cs:
        return f"亲，您的体力不足（需要 {cs} 点体力），无法出门搬砖！"
    price = max(500, _safe_int(uget(u, "price"), cfgi("费用配置", "初始身价", 1000)))
    charm = max(0, acct.int("charm"))
    sw_lo = max(0, cfgi("费用配置", "搬砖收益下限", SELF_WORK_LO))
    sw_hi = max(sw_lo, cfgi("费用配置", "搬砖收益上限", SELF_WORK_HI))
    base_pay = _random.randint(sw_lo, sw_hi)
    stat_bonus = min(SELF_WORK_BONUS_CAP, price // 30 + charm * 3)
    pay = base_pay + stat_bonus
    try:
        _wb = _treasure_pct_total(treasures_of(u), "work", WORK_PCT_CAP, u=u)
    except Exception:
        _wb = 0
    try:
        try:
            from ..ride import active_ride_info
        except ImportError:
            from games.ride import active_ride_info  # type: ignore
        _, _r_pct = active_ride_info(gid, qq, aspect="work")
        _wb += int(_r_pct or 0)
    except Exception:
        pass
    if _wb > 0:
        pay += pay * _wb // 100
    is_crit = _random.randint(1, 100) <= SELF_WORK_CRIT_CHANCE
    worth_up = 0
    if is_crit:
        pay = int(pay * 1.5)
        worth_up = _random.randint(30, 100)
    with ST._LOCK:
        cur_st = ST.acct(gid, qq).int("stamina")
        if cur_st < cs:
            return f"亲，您的体力不足（需要 {cs} 点体力），无法出门搬砖！"
        if ST.txn_coins_acct(gid, qq, pay, {"stamina": str(max(0, cur_st - cs))}) is None:
            return "数据库繁忙，搬砖结算未成功，请稍后重试。"
    cd_commit(u, "搬砖时间")
    if worth_up > 0:
        new_p = min(_S.MAX_PRICE, price + worth_up)
        uset(u, "price", str(new_p))
    job_act, job_tail = _random.choice(_SELF_WORK_JOBS)
    cn = coin_name()
    extra_bonus = max(0, pay - base_pay - stat_bonus)
    extra_str = f" + 额外加成 {extra_bonus}" if extra_bonus > 0 else ""
    lines = [
        f"🧱 {job_act}，{job_tail}！",
        f"💰 本次工钱：+{ST.fmt_coins(pay)}{cn}（基础 {ST.fmt_coins(base_pay)} + 身价/魅力加成 {ST.fmt_coins(stat_bonus)}{extra_str}）｜🔋 体力 -{cs}",
    ]
    if is_crit:
        lines.append(f"✨【工头重赏】触发大单暴击（收益 ×1.5），身价额外上涨 +{worth_up}！")
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
    if total_assets(gid, qq) < need:
        return _S.T.REVOLT_TOO_POOR.format(need=need)
    charm_cost = cfgi("费用配置", "造反消耗魅力", 15)
    try:
        charm_cost = max(0, int(charm_cost))
    except Exception:
        charm_cost = 15
    cd_commit(u, "造反时间")
    revolt_fine = max(0, cfgi("费用配置", "造反失败罚金", 500))
    loot_lo = max(0, cfgi("费用配置", "造反掠夺下限", REVOLT_LOOT_LO))
    loot_hi = max(loot_lo, cfgi("费用配置", "造反掠夺上限", REVOLT_LOOT_HI))
    # 主人奴隶数量是我方两倍 -> 镇压
    m_slaves = len(slaves_of(st, owner))
    my_power = battle_power(st, qq)
    om_power = battle_power(st, owner)
    if m_slaves >= 2 * max(1, len(slaves_of(st, qq))) and om_power > my_power:
        fine = transfer_cash_or_deposit(gid, qq, owner, max(100, revolt_fine))
        if fine is None:
            return "数据库繁忙，造反结算未成功，请稍后重试。"
        fine = max(0, int(fine or 0))
        return _S.T.REVOLT_CRUSHED + f"(被罚{fine})" + _charm_note(_charge_charm(gid, qq, charm_cost))
    sn = uget(u, "name") or (str(qq))
    loot_want = _random.randint(loot_lo, loot_hi)

    i_gourd_prob = _treasure_trigger_prob(u, "pardon", default_base=25, fallbacks=(TREASURE_GOURD_NAME,))
    master_gourd_prob = _treasure_trigger_prob(U(st, owner), "pardon", default_base=25, fallbacks=(TREASURE_GOURD_NAME,))

    i_have_gourd = (i_gourd_prob > 0) and (_random.randint(1, 100) <= i_gourd_prob)
    master_has_gourd = (master_gourd_prob > 0) and (_random.randint(1, 100) <= master_gourd_prob)

    if i_have_gourd:
        loot = transfer_cash_or_deposit(gid, owner, qq, loot_want)
        if loot is None:
            return "数据库繁忙，造反结算未成功，请稍后重试。"
        loot = max(0, int(loot or 0))
        uset(u, "owner", "")
        uset(u, "protect_until", "")
        uset(u, "protector", "")
        uset(u, "_work_wage", "")
        return (_S.T.RV_GOURD_WIN + f"（【酒神葫芦】{i_gourd_prob}%概率触发免罪显灵）\r\n"
                + _S.T.RV_LOOT.format(loot=loot, coin=coin_name())
                + "\r\n" + _S.T.REVOLT_FREE.replace("，", "")
                + _charm_note(_charge_charm(gid, qq, charm_cost)))
    if master_has_gourd:
        pay = transfer_cash_or_deposit(gid, qq, owner, loot_want)
        if pay is None:
            return "数据库繁忙，造反结算未成功，请稍后重试。"
        pay = max(0, int(pay or 0))
        return (_S.T.RV_GOURD_LOSE + f"（主人【酒神葫芦】{master_gourd_prob}%概率触发镇压）({pay}{coin_name()})\r\n"
                + _S.T.REVOLT_FAIL_STAY
                + _charm_note(_charge_charm(gid, qq, charm_cost)))
    _revolt_p = cfgi("概率配置", "造反概率", 20)
    try:
        from ..sign import eff_prob as _LP4
        _revolt_p = _LP4(_revolt_p, gid, qq)
    except Exception:
        pass
    # 魅力加成进成功率（w1004c）
    _revolt_p = max(0, min(100, _revolt_p + _charm_bonus(gid, qq)))
    if _random.randint(1, 100) <= _revolt_p:
        loot = transfer_cash_or_deposit(gid, owner, qq, loot_want)
        if loot is None:
            return "数据库繁忙，造反结算未成功，请稍后重试。"
        loot = max(0, int(loot or 0))
        uset(u, "owner", "")
        uset(u, "protect_until", "")
        uset(u, "protector", "")
        uset(u, "_work_wage", "")
        return (_S.T.RV_NORMAL_WIN + f"\r\n[{sn}] " + _S.T.RV_LOOT.format(loot=loot, coin=coin_name())
                + "\r\n" + _S.T.REVOLT_FREE.replace("，", "")
                + _charm_note(_charge_charm(gid, qq, charm_cost)))
    pay = transfer_cash_or_deposit(gid, qq, owner, revolt_fine)
    if pay is None:
        return "数据库繁忙，造反结算未成功，请稍后重试。"
    pay = max(0, int(pay or 0))
    return (_S.T.RV_NORMAL_LOSE + f"(罚{pay}{coin_name()})\r\n"
            + f"[{sn}]" + _S.T.REVOLT_FAIL_STAY
            + _charm_note(_charge_charm(gid, qq, charm_cost)))


# ============================================================
# 逻辑层 · 第6块: 奴隶群战 / 抽卡 / 升星 / 升阶
# ============================================================


__all__ = ["cmd_flatter", "cmd_pray", "cmd_revolt", "cmd_self_work", "cmd_study", "cmd_work_collect", "cmd_work_dispatch"]
