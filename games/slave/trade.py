# -*- coding: utf-8 -*-
"""games/slave/trade.py — 奴隶包·trade（原 slave.py 切分，语义不变）。"""
import time as _time
import random as _random
import datetime as _dt
try:
    from ...core import storage as ST
except ImportError:
    from core import storage as ST
from . import slave_state as _S
try:
    from ..config.slave import (TORTURE_VICTIM_CD, TORTURE_FALLBACK_LO, TORTURE_FALLBACK_HI,
                                TORTURE_FALLBACK_OWNER_DIV, SLOT_GROWTH)
except ImportError:
    from games.config.slave import (TORTURE_VICTIM_CD, TORTURE_FALLBACK_LO, TORTURE_FALLBACK_HI,  # type: ignore
                                    TORTURE_FALLBACK_OWNER_DIV, SLOT_GROWTH)
from .base import U, _event_delta, _fmt, _safe_int, cd_check, cd_commit, cfgf, cfgi, cn_fmt, cn_parse, coins_add, coins_get, protected_until, slaves_of, uget, uset
from .nick import exists_user, uname
from .profile import coin_name


def cmd_buy_slave(gid, qq, target, st):
    if not target:
        return _S.T.BUY_WHO
    tid = str(target)
    if tid == qq:
        return _S.T.SELF_OP_WEIRD
    if _S.BOT_UIN and tid == str(_S.BOT_UIN):
        return _S.T.BOT_NO_TRADE
    if not exists_user(gid, tid):
        return _S.T.NOT_IN_GROUP
    buyer, tgt = U(st, qq), U(st, tid)
    if uget(tgt, "owner") == qq:
        return _S.T.BUY_IS_MINE
    if uget(buyer, "owner") == tid:
        return _S.T.SELF_BUY_SELF
    prev_owner = uget(tgt, "owner")
    if _S.BOT_UIN and prev_owner == str(_S.BOT_UIN):
        return _S.T.BOT_NO_TRADE
    if _time.time() < protected_until(tgt):
        left = int((protected_until(tgt) - _time.time()) / 60) + 1
        prot_qq = uget(tgt, "protector")
        if prot_qq and st.has_section(prot_qq):
            return _S.T.BUY_PROTECTED.format(who=uname(st, prot_qq), min=left)
        return _S.T.PROTECTED_CANNOT_BUY.format(min=left)
    slots = _safe_int(uget(buyer, "slave_slots", str(cfgi("设置", "奴隶个数", 5))), cfgi("设置", "奴隶个数", 5))
    if slots <= 0:
        slots = max(1, cfgi("设置", "奴隶个数", 5))
    mine = slaves_of(st, qq)
    if len(mine) >= slots:
        return _S.T.BUY_SLOT_FULL.format(cap=slots)
    price = int(uget(tgt, "price") or 0)
    if coins_get(gid, qq) < price:
        return _S.T.BUY_COST.format(cost=price) + "\r\n" + _S.T.POOR.format(coin=coin_name())
    # 原版有"刚刚被交易过恢复情绪"判定, 用购买时间近似
    last_trade = cn_parse(uget(tgt, "purchase_time"))
    iv = cfgi("间隔配置", "购买间隔", 1)
    if last_trade and _time.time() - last_trade < iv * 60:
        left = int(iv - (_time.time() - last_trade) / 60) + 1
        return _S.T.BUY_JUST_TRADED.format(min=left)
    profit = price
    if prev_owner and price > 0:
        # 原子双钱包一次提交：失败不改群档、不继续扣款（禁非原子 fallback）
        try:
            _ok = ST.txn_two_wallets(gid, qq, prev_owner, price)
        except Exception:
            _ok = None
        if _ok is None:
            return "数据库繁忙，购买未成功，未扣款，请稍后重试。"
        if _ok is not True:
            return _S.T.BUY_COST.format(cost=price) + "\r\n" + _S.T.POOR.format(coin=coin_name())
        orig = int(uget(tgt, "purchase_price") or price)
    else:
        if price > 0 and coins_add(gid, qq, -price) is None:
            return "数据库繁忙，购买未成功，未扣款，请稍后重试。"
        if not prev_owner:
            profit = 0
        orig = price
    uset(tgt, "owner", qq)
    uset(tgt, "purchase_price", str(price))
    uset(tgt, "purchase_time", _dt.datetime.now().strftime("%Y年%m月%d日%H时%M分%S秒"))
    uset(tgt, "_work_wage", "")
    newp = min(_S.MAX_PRICE, int(price * cfgf("费用配置", "买入身价上涨", _S.PRICE_UP)))
    uset(tgt, "price", str(newp))
    tn = uname(st, tid)
    head = _S.T.BUY_OK_HEAD.format(who=tn)
    lines = [
        _S.T.BUY_COST.format(cost=price),
        _S.T.BUY_PRICE_UP.format(up=newp - price),
        _S.T.BUY_PRICE_NOW.format(now=newp),
    ]
    if prev_owner:
        pon = uname(st, prev_owner)
        lines += [
            _S.T.BUY_PREV_OWNER.format(prev=pon),
            _S.T.BUY_PREV_COST.format(orig=orig),
            _S.T.BUY_PREV_PROFIT.format(profit=profit),
        ]
    return head + "\r\n" + "\r\n".join(lines)




def cmd_torture(gid, qq, target, st):
    if not target:
        my_slaves = slaves_of(st, qq)
        if not my_slaves:
            return _S.T.TORTURE_ALL_DONE
        if len(my_slaves) == 1:
            target = my_slaves[0]
        else:
            return _S.T.TORTURE_WHO
    tid = str(target)
    if tid == qq:
        return _S.T.TORTURE_SELF
    s = U(st, tid)
    if uget(s, "owner") != qq:
        return _S.T.TORTURE_NOT_MINE
    last_tor = cn_parse(uget(s, "tortured_time"))
    if last_tor and _time.time() - last_tor < TORTURE_VICTIM_CD:
        return _S.T.TORTURE_JUST
    my_slaves = slaves_of(st, qq)
    ok, mins = cd_check(U(st, qq), "torture_time", "折磨间隔")
    if not ok:
        return _fmt(mins, "折磨")
    if not my_slaves:
        return _S.T.TORTURE_ALL_DONE
    sc = coins_get(gid, tid)
    cd_commit(U(st, qq), "torture_time")
    if _random.randint(1, 100) > cfgi("概率配置", "折磨成功率", 75):
        return _S.T.TORTURE_MERCY
    evs = [e for e in _S.EVENTS if e.get("type", "").startswith("折磨")]
    if not evs:
        take = min(sc, _random.randint(TORTURE_FALLBACK_LO, TORTURE_FALLBACK_HI))
        if take > 0:
            # 先扣奴隶再奖主人：任一步失败即退款回滚并中止，不改时间戳（禁半成功）
            if coins_add(gid, tid, -take) is None:
                return "数据库繁忙，折磨结算未成功，请稍后重试。"
            _share = take // TORTURE_FALLBACK_OWNER_DIV
            if _share > 0 and coins_add(gid, qq, _share) is None:
                try:
                    coins_add(gid, tid, take)
                except Exception:
                    pass
                return "数据库繁忙，折磨结算未成功，已退款，请稍后重试。"
        uset(s, "tortured_time", cn_fmt(_time.time()))
        return f"折磨了 [{uname(st,tid)}], 掠夺 {take}"
    up_pool = [e for e in evs if e.get("effect") == "主人货币上涨"]
    down_pool = [e for e in evs if e.get("effect") == "主人货币下跌"]
    sup_pool = [e for e in evs if e.get("effect") == "奴隶货币上涨"]
    sdown_pool = [e for e in evs if e.get("effect") == "奴隶货币下跌"]
    parts = []
    if up_pool and _random.random() < 0.6:
        ev = _random.choice(up_pool)
        amt = _event_delta()
        if coins_add(gid, qq, amt) is None:
            return "数据库繁忙，折磨结算未成功，请稍后重试。"
        parts.append(_S.T.EVENT_MASTER_UP.format(text=ev.get("text", ""), amt=amt))
    elif down_pool and _random.random() < 0.3:
        ev = _random.choice(down_pool)
        amt = min(coins_get(gid, qq), _random.randint(50, 500))
        if amt > 0:
            if coins_add(gid, qq, -amt) is None:
                return "数据库繁忙，折磨结算未成功，请稍后重试。"
            parts.append(_S.T.EVENT_MASTER_DOWN.format(text=ev.get("text", ""), amt=amt))
    if sup_pool and _random.random() < 0.35:
        ev = _random.choice(sup_pool)
        amt = _random.randint(30, 300)
        if coins_add(gid, tid, amt) is None:
            return "数据库繁忙，折磨结算未成功，请稍后重试。"
        parts.append(_S.T.EVENT_SLAVE_UP.format(text=ev.get("text", ""), amt=amt))
    elif sdown_pool and _random.random() < 0.5:
        ev = _random.choice(sdown_pool)
        amt = min(sc, _random.randint(30, 400))
        if amt > 0:
            if coins_add(gid, tid, -amt) is None:
                return "数据库繁忙，折磨结算未成功，请稍后重试。"
            parts.append(_S.T.EVENT_SLAVE_DOWN.format(text=ev.get("text", ""), amt=amt))
    if not parts:
        return _S.T.TORTURE_MERCY
    uset(s, "tortured_time", cn_fmt(_time.time()))
    sn = uname(st, tid)
    parts.insert(0, f"你对 [{sn}] 实施了折磨...")
    return "\r\n".join(parts)




def cmd_protect(gid, qq, target, st):
    if not target:
        return _S.T.PROTECT_WHO
    tid = str(target)
    if tid == str(qq):
        return _S.T.SELF_OP_WEIRD
    if _S.BOT_UIN and tid == str(_S.BOT_UIN):
        return _S.T.BOT_NO_TRADE
    u = U(st, tid)
    if uget(u, "owner") != qq:
        return _S.T.PROTECT_NOT_YOURS
    if _time.time() < protected_until(u):
        left = int((protected_until(u) - _time.time())/60)+1
        return _S.T.ALREADY_PROTECTED_BY_YOU.format(min=left)
    ok, mins = cd_check(U(st, qq), "protect_time", "保护间隔")
    if not ok:
        return _fmt(mins, "保护")
    hours = cfgf("设置", "保护时长小时", 12)
    fee = cfgi("设置", "保护费用", 1000)
    if coins_get(gid, qq) < fee:
        return _S.T.PROTECT_POOR.format(coin=coin_name())
    if coins_add(gid, qq, -fee) is None:
        return "数据库繁忙，保护未成功，未扣款，请稍后重试。"
    until = _time.time() + hours * 3600
    uset(u, "protect_until", _dt.datetime.fromtimestamp(until).strftime("%Y年%m月%d日%H时%M分%S秒"))
    uset(u, "protector", qq)
    cd_commit(U(st, qq), "protect_time")
    mins = int(hours * 60)
    who = uname(st, tid)
    return _S.T.PROTECT_OK.format(cost=fee, coin=coin_name(), who=who, min=mins)




def cmd_release(gid, qq, target, st):
    if not target:
        return _S.T.RELEASE_WHO
    tid = str(target)
    if tid == qq:
        return _S.T.SELF_RELEASE
    s = U(st, tid)
    if uget(s, "owner") != qq:
        return "不是你的奴隶，你无法释放Ta！"
    ok, mins = cd_check(U(st, qq), "release_time", "释放间隔")
    if not ok:
        return _fmt(mins, "释放")
    uset(s, "owner", "")
    uset(s, "protect_until", "")
    uset(s, "protector", "")
    cd_commit(U(st, qq), "release_time")
    return _S.T.RELEASE_OK.format(who=uname(st, tid))




def cmd_ransom(gid, qq, target, st):
    """赎身@QQ: 帮别人的奴隶向其主人支付身价, 让TA自由; 未指定目标或为自己时自动执行赎身自由"""
    if not target or str(target) == str(qq):
        return cmd_freedom(gid, qq, st)
    tid = str(target)
    s = U(st, tid)
    owner = uget(s, "owner")
    if not owner:
        return _S.T.RANSOM_TA_FREE
    if owner == qq:
        return _S.T.RANSOM_OWN_SLAVE
    last_r = cn_parse(uget(s, "赎身时间"))
    iv_r = cfgi("间隔配置", "赎身间隔", 30)
    if last_r and _time.time() - last_r < iv_r * 60:
        left = int((iv_r * 60 - (_time.time() - last_r)) / 60) + 1
        return _S.T.RANSOM_CD.format(min=left)
    price = int(int(uget(s, "price") or 0) * cfgf("费用配置", "赎身花费倍率", 1.5))
    if coins_get(gid, qq) < price:
        return _S.T.POOR.format(coin=coin_name()) + f"(需{price})"
    # 原子双钱包一次提交：失败不改群档（禁非原子 fallback）
    try:
        _ok = ST.txn_two_wallets(gid, qq, owner, price) if price > 0 else True
    except Exception:
        _ok = None
    if _ok is None:
        return "数据库繁忙，赎身未成功，未扣款，请稍后重试。"
    if _ok is not True:
        return _S.T.POOR.format(coin=coin_name()) + f"(需{price})"
    uset(s, "owner", "")
    uset(s, "赎身时间", cn_fmt(_time.time()))
    return f"[{uname(st,qq)}] 大发善心，花费{price}为 [{uname(st,tid)}] 赎身，Ta已恢复自由！"




def cmd_freedom(gid, qq, st):
    u = U(st, qq)
    owner = uget(u, "owner")
    if not owner:
        return _S.T.RANSOM_NO_OWNER
    last_f = cn_parse(uget(u, "自由时间"))
    iv_f = cfgi("间隔配置", "自由间隔", 30)
    if last_f and _time.time() - last_f < iv_f * 60:
        left = int((iv_f * 60 - (_time.time() - last_f)) / 60) + 1
        return _S.T.FREE_CD.format(min=left)
    price = int(int(uget(u, "price") or 0) * cfgf("费用配置", "赎身花费倍率", 1.5))
    have = coins_get(gid, qq)
    if have < price:
        return (_S.T.FREE_BY_TORTURE.format(cost=price) + "\r\n" + _S.T.FREE_FAIL_PAY
                + f"\r\n(还差 {price - have} {coin_name()})")
    # 原子双钱包一次提交：失败不改群档（禁非原子 fallback）
    try:
        _ok = ST.txn_two_wallets(gid, qq, owner, price) if price > 0 else True
    except Exception:
        _ok = None
    if _ok is None:
        return "数据库繁忙，赎身未成功，未扣款，请稍后重试。"
    if _ok is not True:
        return (_S.T.FREE_BY_TORTURE.format(cost=price) + "\r\n" + _S.T.FREE_FAIL_PAY
                + f"\r\n(还差 {price - have} {coin_name()})")
    uset(u, "owner", "")
    uset(u, "自由时间", cn_fmt(_time.time()))
    return _S.T.FREE_KIND.format(cost=price) + "\r\n换取自由！"




def cmd_buyslot(gid, qq, st):
    u = U(st, qq)
    cur = _safe_int(uget(u, "slave_slots", str(cfgi("设置", "奴隶个数", 5))), cfgi("设置", "奴隶个数", 5))
    cap = cfgi("设置", "奴隶个数上限", 15)
    if cur >= cap:
        return _S.T.SLOT_SYS_MAX
    base_price = cfgi("设置", "奴隶位价格", 5000)
    base_cap = cfgi("设置", "奴隶个数", 5)
    price = int(base_price * (SLOT_GROWTH ** max(0, cur - base_cap)))
    if coins_get(gid, qq) < price:
        return (_S.T.SLOT_NEED.format(price=price) + "\r\n" +
                _S.T.SLOT_POOR.format(coin=coin_name()))
    if coins_add(gid, qq, -price) is None:
        return "数据库繁忙，购买奴隶位未成功，未扣款，请稍后重试。"
    uset(u, "slave_slots", str(cur + 1))
    return ("\r\n".join([
        f"恭喜您花费{price}{coin_name()}",
        _S.T.SLOT_BUY_ONE,
        _S.T.SLOT_NOW_CAP.format(cap=cur + 1),
        _S.T.SLOT_NEXT_PRICE.format(price=int(price * SLOT_GROWTH)),
    ]))




__all__ = ["cmd_buy_slave", "cmd_buyslot", "cmd_freedom", "cmd_protect", "cmd_ransom", "cmd_release", "cmd_torture"]
