# -*- coding: utf-8 -*-
"""games/bank·core（原 bank.py 切分，语义不变）。"""
import datetime as dt
import json
import random
import time
try:
    from ...core import storage as ST
except ImportError:
    from core import storage as ST
from .common import *  # noqa
from .jail import *  # noqa


def cmd_deposit(gid, qq, amount):
    if amount <= 0:
        return "亲，您的格式有误，存款格式为：【存款 金额】！"
    # 读-校验-写全程持 _LOCK（RLock 可重入，txn 内复入无死锁）：防同用户并发双花/丢更新
    with ST._LOCK:
        a = _acct(gid, qq)
        if _check_jail(a):
            return _show_jail(a)
        cs = cfgi("银行配置", "存取款消耗体力", 1)
        if a.int("stamina") < cs:
            return "亲，您的游戏体力不足，无法进行存款！"
        have = ST.coins_get(gid, qq)
        if have < amount:
            return f"亲，您的{ST.coin_name()}不足，请重新选择存款数！"
        rate = cfgi("银行配置", "存款利率", 1)
        cap = cfgi("银行配置", "利息上限", 50000)
        max_daily = cfgi("银行配置", "每日结息次数", 3)
        today_s = str(dt.date.today())
        cur_cnt = int(a.get("interest_count", "0") or 0) if a.get("interest_date", "") == today_s else 0
        interest = _settle_interest(a, rate, cap)
        old = a.int("deposit")
        updates = {
            "stamina": str(a.int("stamina") - cs),
            "deposit": str(old + amount + interest),
            "withdraw_timestamp": str(int(time.time())),
        }
        if interest > 0:
            updates["interest_date"] = today_s
            updates["interest_count"] = str(cur_cnt + 1)
        if ST.txn_coins_acct(gid, qq, -amount, updates, require_funds=True) is None:
            return "亲，银行系统繁忙，存款未成功，请稍后重试！"
        total = old + amount + interest
    cnt_note = f"\r\n💡 今日结息次数：{cur_cnt + 1}/{max_daily}" if (interest > 0 and max_daily > 0) else (
        f"\r\n💡 今日结息已满 {max_daily}/{max_daily} 次，明日可继续结息" if (old > 0 and max_daily > 0 and cur_cnt >= max_daily) else ""
    )
    return (f"存款成功！消耗{cs}点体力，共存入：{amount}，\r\n"
            f"上期结息：{interest}，当前总存款：{total}，"
            f"当前利率：{rate}%，1小时后可取款！\r\n"
            f"剩余{ST.coin_name()}：{ST.coins_get(gid, qq)}{cnt_note}")


def _settle_interest(a, rate, cap):
    """按 上次取款时间戳 到现在的小时数计息(满 1小时 才结息, 封顶利息上限, 每日最多结息 N 次)"""
    ts = a.get("withdraw_timestamp", "")
    try:
        last = float(ts)
    except Exception:
        last = time.time()
    dep = a.int("deposit")
    if dep <= 0:
        return 0
    max_daily = cfgi("银行配置", "每日结息次数", 3)
    if max_daily > 0:
        today_s = str(dt.date.today())
        cur_cnt = int(a.get("interest_count", "0") or 0) if a.get("interest_date", "") == today_s else 0
        if cur_cnt >= max_daily:
            return 0
    # 改为小时结算：1小时=3600s
    elapsed_h = (time.time() - last) / 3600.0
    term_h = 1  # 固定1小时一结
    if elapsed_h < term_h:
        return 0
    interest = int(dep * rate / 100.0 * min(1.0, elapsed_h / term_h))
    return min(interest, cap)


def cmd_withdraw(gid, qq, amount):
    # 读-校验-写全程持 _LOCK：防并发双取（同一存款被两个线程同时取走）
    with ST._LOCK:
        a = _acct(gid, qq)
        if _check_jail(a):
            return _show_jail(a)
        dep = a.int("deposit")
        if amount <= 0:
            return "请输入正确格式：取款 金额（正整数）"
        if dep < amount:
            return f"存款不足！当前存款：{dep}"
        rate = cfgi("银行配置", "存款利率", 1)
        cap = cfgi("银行配置", "利息上限", 50000)
        max_daily = cfgi("银行配置", "每日结息次数", 3)
        today_s = str(dt.date.today())
        cur_cnt = int(a.get("interest_count", "0") or 0) if a.get("interest_date", "") == today_s else 0
        interest = _settle_interest(a, rate, cap)
        # 利息未到或今日结息次数已满时提示剩余时间与可用强制取款，但仍允许取款
        if interest == 0 and dep > 0:
            if max_daily > 0 and cur_cnt >= max_daily:
                interest_note = f"（提示：今日结息已满 {max_daily}/{max_daily} 次，本次仅取回本金，明日可继续结息）"
            else:
                try:
                    last = float(a.get("withdraw_timestamp", "0") or "0")
                    left = int(3600 - (time.time() - last))
                    if left > 0:
                        pot = int(dep * rate / 100.0)
                        pot = min(pot, cap)
                        interest_note = f"（提示：利息结算需1小时，还需{left//60}分{left%60}秒，到期可获{pot}{ST.coin_name()}，可强取）"
                    else:
                        interest_note = ""
                except Exception:
                    interest_note = ""
        elif interest > 0 and max_daily > 0:
            interest_note = f"💡 今日结息次数：{cur_cnt + 1}/{max_daily}"
        else:
            interest_note = ""
        # 取款仅扣除本次取出的存款本金，利息为银行派发的收益额外计入钱包
        new_dep = dep - amount
        updates = {"deposit": str(new_dep), "withdraw_timestamp": str(int(time.time()))}
        if interest > 0:
            updates["interest_date"] = today_s
            updates["interest_count"] = str(cur_cnt + 1)
        if ST.txn_coins_acct(gid, qq, amount + interest, updates) is None:
            return "亲，银行系统繁忙，取款未成功，请稍后重试！"
        base = (f"取款成功！获得利息：{interest}，本次取款：{amount}，\r\n"
                f"还剩存款：{new_dep}，剩余{ST.coin_name()}：{ST.coins_get(gid, qq)}")
    if 'interest_note' in locals() and interest_note:
        base += f"\r\n{interest_note}"
    return base


def cmd_force_withdraw(gid, qq, amount):
    """强制取款: 未到期限强制取款无利息，不影响后续利息按剩余计（不重置计时）原子版"""
    # 读-校验-写全程持 _LOCK：防并发双取
    with ST._LOCK:
        a = _acct(gid, qq)
        if _check_jail(a):
            return _show_jail(a)
        dep = a.int("deposit")
        if amount <= 0:
            return "请输入正确格式：强制取款 金额（正整数）"
        if dep < amount:
            return f"存款不足！当前存款：{dep}"
        # 原子：钱包 + 存款同事务，避免半成功（中文文案不变）
        if ST.txn_coins_acct(gid, qq, amount, {"deposit": str(dep - amount)}) is None:
            return "亲，银行系统繁忙，强制取款未成功，请稍后重试！"
        # 不重置取款时间戳，利息仍按原剩余金额与原计时继续结算
        return (f"强制取款成功！因未到取款时间，本次没有利息（不影响后续利息按剩余{ dep - amount}计）。\r\n"
                f"本次取款：{amount}，还剩存款：{dep - amount}，"
                f"剩余{ST.coin_name()}：{ST.coins_get(gid, qq)}")


def cmd_transfer(gid, qq, target, amount):
    # QQ-only: 兼容 CQ / @QQ / 纯QQ 字符串，不认昵称
    target = _ensure_target_qq(target, gid)
    if amount <= 0 or not target:
        return "亲，您的格式有误，转账格式为：【转账 @QQ 金额】！"
    if str(target) == str(qq):
        return "亲，您不能给自己转账，转账失败！"
    min_amt = cfgi("银行配置", "转账最小金额", 50)
    if amount < min_amt:
        return f"亲，转账最小金额为{min_amt}{ST.coin_name()}！"
    cs = cfgi("银行配置", "转账消耗体力", 2)
    if _acct(gid, qq).int("stamina") < cs:
        return "亲，您的游戏体力不足，无法进行转账！"
    cap = cfgi("银行配置", "转账接收额度", getattr(ST, "COIN_CAP", 100000000000))
    if amount > cap:
        return f"亲，单次转账金额不能超过{cap}{ST.coin_name()}！"
    if ST.coins_get(gid, qq) < amount:
        return "亲，您的账户余额不足，转账失败！"
    credit = int(amount)
    # 单事务原子转账：体力+双钱包同锁，避免体力扣了但转账失败半成功
    try:
        with ST._LOCK:
            # 二次校验（防并发）
            cur_st = ST.acct(gid, qq).int("stamina")
            if cur_st < cs:
                return "亲，您的游戏体力不足，无法进行转账！"
            cur_money = ST.coins_get(gid, qq)
            if cur_money < amount:
                return "亲，您的账户余额不足，转账失败！"
            # 对方余额与上限（锁内读）
            dst_cur = ST.coins_get(gid, target)
            credit = min(int(amount), max(0, cap - dst_cur))
            if credit <= 0:
                return "对方钱包已满，无法接收转账！"
            updates = {"stamina": str(max(0, cur_st - cs))}
            # 用 txn_two_wallets_acct 一并提交：转出方扣体力+扣款，转入方加款
            if ST.txn_two_wallets_acct(gid, qq, target, credit, acct_updates=updates, acct_qq=qq) is None:
                return "亲，银行系统繁忙，转账未成功，请稍后重试！"
    except Exception:
        # 主路径失败只回滚并返回；禁止拆成多个独立写入补偿。
        try:
            ST._safe_rollback()
        except Exception:
            pass
        try:
            if ST._DB is not None:
                ST._ACC_CACHE.pop((str(gid), str(qq)), None)
        except Exception:
            pass
        return "亲，银行系统繁忙，转账未成功，请稍后重试！"
    try:
        from .. import slave as SL
        try:
            tn = SL.display_name(gid, str(target))
        except Exception:
            tn = SL.NOTE_NAMES.get(str(target), str(target))
    except Exception:
        tn = str(target)
    return f"转账成功！您已向 {tn} 转入{credit}{ST.coin_name()}！"


def _gid_known(dest_gid):
    """目标群是否为本机器人已知群（groups/wallet/accounts 三表并集，与超管群列表同口径）。
    防群号打错把钱搬进黑洞；异常按未知处理，不裸抛。"""
    try:
        if ST._DB is None:
            return False
        with ST._LOCK:
            for _t in ("groups", "wallet", "accounts"):
                if ST._DB.execute(
                        "SELECT 1 FROM %s WHERE gid=? LIMIT 1" % _t,
                        (int(dest_gid),)).fetchone():
                    return True
    except Exception:
        return False
    return False


def cmd_cross_transfer(gid, qq, dest_gid, amount):
    """跨群转账：把自己的余额从本群搬进自己在目标群的钱包，手续费销毁（回收通胀）。"""
    if not str(dest_gid).isdigit() or int(dest_gid) <= 0 or amount <= 0:
        return "亲，跨群转账格式为：【跨群转账 群号 金额】！"
    if str(dest_gid) == str(gid):
        return "亲，目标群不能是当前群，同群请直接使用【转账】！"
    if not _gid_known(dest_gid):
        return "亲，目标群不存在或本机器人不在该群，请核对群号！"
    min_amt = cfgi("银行配置", "转账最小金额", 50)
    if amount < min_amt:
        return f"亲，跨群转账最小金额为{min_amt}{ST.coin_name()}！"
    pct = cfgi("银行配置", "跨群转账手续费", 20)
    try:
        pct = max(0, min(int(pct), 100))
    except Exception:
        pct = 20
    fee = int(amount) * pct // 100
    credit = int(amount) - fee
    if credit <= 0:
        return f"亲，手续费{pct}%后到账为0，请提高转账金额或降低手续费！"
    cap = cfgi("银行配置", "转账接收额度", getattr(ST, "COIN_CAP", 100000000000))
    if ST.coins_get(gid, qq) < amount:
        return "亲，您的账户余额不足，跨群转账失败！"
    # 源群扣全款 + 目标群入 credit，差额（手续费）销毁：单事务原子，无半成功
    try:
        with ST._LOCK:
            if ST.coins_get(gid, qq) < amount:
                return "亲，您的账户余额不足，跨群转账失败！"
            dst_cur = ST.coins_get(dest_gid, qq)
            if dst_cur + credit > cap:
                return "亲，对方钱包已达接收额度上限，无法转入！"
            ok = ST.txn_cross_group(gid, dest_gid, qq, amount, credit)
            if ok is None:
                return "亲，银行系统繁忙，跨群转账未成功，请稍后重试！"
            if not ok:
                return "亲，您的账户余额不足或目标钱包已达上限，跨群转账失败！"
    except Exception:
        try:
            ST._safe_rollback()
        except Exception:
            pass
        return "亲，银行系统繁忙，跨群转账未成功，请稍后重试！"
    return (f"跨群转账成功！\r\n本群支出{amount}{ST.coin_name()}，"
            f"目标群到账{credit}{ST.coin_name()}\r\n"
            f"手续费{fee}{ST.coin_name()}（{pct}%）已由系统回收")


def cmd_gamble(gid, qq, amount):
    a = _acct(gid, qq)
    if _check_jail(a):
        return _show_jail(a)
    if amount < 100:
        return f"亲，赌博最小金额为100{ST.coin_name()}！格式为：【赌博 金额】"
    maxamt = cfgi("银行配置", "赌博最大金额", 100000)
    if amount > maxamt:
        return f"亲，预赌金额不得超过{maxamt}{ST.coin_name()}！"
    cs = cfgi("银行配置", "赌博消耗体力", 10)
    if a.int("stamina") < cs:
        return "亲，您的体力不足，无法进行赌博！"
    lim = cfgi("银行配置", "赌博限定次数", 5)
    meli = cfgi("银行配置", "赌博魅力减少", 20)
    jail_mins = cfgi("银行配置", "赌博关押时间", 5)
    prob = cfgi("银行配置", "赌博成功概率", 60)
    try:
        from ..sign import eff_prob as _luck_eff
        prob = _luck_eff(prob, gid, qq)
    except Exception:
        pass
    gain = int(amount * GAMBLE_MULT)
    # 原子化：钱包+体力+魅力+日计数 同锁，避免半成功通胀/并发双花次数
    try:
        with ST._LOCK:
            cur = ST.coins_get(gid, qq)
            if cur < amount:
                return f"亲，您的{ST.coin_name()}不足，无法进行赌博！"
            cur_st = ST.acct(gid, qq).int("stamina")
            if cur_st < cs:
                return "亲，您的体力不足，无法进行赌博！"
            # 锁内重读日计数：防锁外读到旧值绕过当日上限
            cnt = int(ST.recall_get("gamble_%s_%s_%s" % (gid, qq, dt.date.today()), "0") or 0)
            if cnt >= lim:
                return "亲，您今日赌博次数已达上限，无法再进行赌博！"
            a2 = ST.acct(gid, qq)
            a2.set("stamina", str(cur_st - cs))
            if random.random() * 100 < prob:
                # 成功：-amount +gain
                new_money = cur - amount + gain
                ST._DB.execute("INSERT INTO wallet(gid, qq, money) VALUES(?,?,?) ON CONFLICT(gid, qq) DO UPDATE SET money=excluded.money", (int(gid), int(qq), new_money))
                ST._DB.execute("INSERT INTO accounts(gid, qq, data) VALUES(?,?,?) ON CONFLICT(gid, qq) DO UPDATE SET data=excluded.data", (int(gid), int(qq), json.dumps(a2.kv, ensure_ascii=False)))
                try:
                    ST._DB.commit()
                except Exception:
                    ST._safe_rollback()
                    raise
                a2.dirty = False
                try:
                    ST.recall_set("gamble_%s_%s_%s" % (gid, qq, dt.date.today()), str(cnt + 1))
                except Exception:
                    pass
                return f"赌博成功！你获得了{gain}{ST.coin_name()}，净赚{gain - amount}！"
            else:
                # 失败：-amount 魅力 -meli
                new_money = cur - amount
                cur_mei = a2.int("charm")
                meli_eff = max(0, min(int(meli), cur_mei))
                a2.set("charm", str(cur_mei - meli_eff))
                ST._DB.execute("INSERT INTO wallet(gid, qq, money) VALUES(?,?,?) ON CONFLICT(gid, qq) DO UPDATE SET money=excluded.money", (int(gid), int(qq), new_money))
                ST._DB.execute("INSERT INTO accounts(gid, qq, data) VALUES(?,?,?) ON CONFLICT(gid, qq) DO UPDATE SET data=excluded.data", (int(gid), int(qq), json.dumps(a2.kv, ensure_ascii=False)))
                jail = random.random() < 0.5
                if jail:
                    a2.set("jail", "1")
                    a2.set("jail_start", dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                    a2.set("release_timestamp", str(int(time.time()) + int(jail_mins) * 60))
                    ST._DB.execute("INSERT INTO accounts(gid, qq, data) VALUES(?,?,?) ON CONFLICT(gid, qq) DO UPDATE SET data=excluded.data", (int(gid), int(qq), json.dumps(a2.kv, ensure_ascii=False)))
                try:
                    ST._DB.commit()
                except Exception:
                    ST._safe_rollback()
                    raise
                a2.dirty = False
                try:
                    ST.recall_set("gamble_%s_%s_%s" % (gid, qq, dt.date.today()), str(cnt + 1))
                except Exception:
                    pass
                if jail:
                    return (f"赌博失败，损失{amount}{ST.coin_name()}，魅力-{meli_eff}！\r\n"
                            f"赌博时被抓了！被关监狱{jail_mins}分钟！")
                return f"赌博失败，损失{amount}{ST.coin_name()}，魅力-{meli_eff}……愿赌服输~"
    except Exception:
        try:
            ST._safe_rollback()
        except Exception:
            pass
        try:
            if ST._DB is not None:
                ST._ACC_CACHE.pop((str(gid), str(qq)), None)
        except Exception:
            pass
        try:
            a = ST.acct(gid, qq)
        except Exception:
            pass
    return "赌博系统繁忙，本次未结算，未扣除资金和体力，请稍后重试！"


def _vault_state(gid):
    """独立金库读+时间回流：seed/cap/每小时回流均走银行配置（代码缺省，无需 schema）。
    返回 (vault, cap)。只读不写，写走 _vault_set。"""
    try:
        seed = cfgi("银行配置", "打劫银行金库初始", 50000)
        cap = cfgi("银行配置", "打劫银行金库上限", 500000)
        flow = cfgi("银行配置", "打劫银行金库回流", 5000)
    except Exception:
        seed, cap, flow = 50000, 500000, 5000
    if seed <= 0:
        seed = 50000
    if cap <= 0:
        cap = 500000
    if flow < 0:
        flow = 0
    try:
        _raw = ST.recall_get("bank_vault_%s" % gid, None)
    except Exception:
        _raw = None
    if _raw is None or str(_raw).strip() == "":
        return min(seed, cap), cap
    try:
        v = max(0, int(_raw))
    except Exception:
        v = min(seed, cap)
    try:
        ts = float(ST.recall_get("bank_vault_ts_%s" % gid, "0") or 0)
    except Exception:
        ts = 0.0
    if ts > 0 and flow > 0 and v < cap:
        try:
            v = min(cap, v + int(flow * (time.time() - ts) / 3600.0))
        except Exception:
            pass
    return v, cap


def cmd_rob_zone(gid, qq):
    """打劫银行：只动独立金库，不碰任何用户存款。成功从金库提款，失败罚金充公进金库。"""
    a = _acct(gid, qq)
    if _check_jail(a):
        return _show_jail(a)
    cs = cfgi("银行配置", "打劫银行消耗体力", 5)
    if a.int("stamina") < cs:
        return "亲，您的体力不足，无法实施银行打劫！"
    ok, mins = _cd(a, "rob_bank_time", cfgi("银行配置", "打劫银行间隔", 10))
    if not ok:
        return f"{mins}分钟后再来打劫银行吧！"
    prob = cfgi("银行配置", "打劫银行成功概率", 70)
    try:
        from ..sign import eff_prob as _luck_eff2
        prob = _luck_eff2(prob, gid, qq)
    except Exception:
        pass
    meli = cfgi("银行配置", "打劫银行魅力减少", 3)
    jail_mins = cfgi("银行配置", "打劫银行关押时间", 5)
    now_s = _now_s()
    if random.random() * 100 > prob:
        cur_st = a.int("stamina")
        cur_charm = a.int("charm")
        fine = min(cfgi("银行配置", "打劫失败罚金", 500), ST.coins_get(gid, qq))
        updates = {
            "stamina": str(max(0, cur_st - cs)),
            "charm": str(max(0, cur_charm - meli)),
            "jail": "1",
            "jail_start": now_s,
            "release_timestamp": str(int(time.time()) + int(jail_mins) * 60),
            "rob_bank_time": now_s,
        }
        with ST._LOCK:
            staged = _vault_stage_delta(gid, max(0, int(fine or 0)))
            if staged is None:
                return "银行系统繁忙，本次打劫未结算，请稍后重试！"
            if ST.txn_coins_acct(gid, qq, -fine, updates) is None:
                return "银行系统繁忙，本次打劫未结算，请稍后重试！"
            _vault_stage_commit_cache(gid, staged)
        return (f"打劫银行失败，打劫银行时被抓！被关监狱{jail_mins}分钟，\r\n"
                f"罚款{fine}{ST.coin_name()}，魅力-{meli}！")
    lo = cfgi("银行配置", "打劫银行金钱下限", 6000)
    hi = cfgi("银行配置", "打劫银行金钱上限", 12000)
    want = max(1, random.randint(lo, hi) if hi >= lo else lo)
    with ST._LOCK:
        try:
            vault, _cap = _vault_state(gid)
            loot = min(vault, want)
            if loot <= 0:
                return "银行金库空空如也，打劫失败，过段时间等金库回流再来！"
            staged = _vault_stage_delta(gid, -loot)
            if staged is None:
                return "银行系统繁忙，本次打劫未结算，请稍后重试！"
        except Exception:
            try:
                ST._safe_rollback()
            except Exception:
                pass
            return "银行系统繁忙，本次打劫未结算，请稍后重试！"
        bounty = min(15000, max(1000, loot // 3))
        if ST.txn_coins_acct(gid, qq, loot, {
            "stamina": str(max(0, a.int("stamina") - cs)),
            "rob_bank_time": now_s,
            "wanted_until": str(int(time.time()) + 1800),
            "wanted_bounty": str(bounty),
        }) is None:
            return "银行系统繁忙，本次打劫未结算，请稍后重试！"
        _vault_stage_commit_cache(gid, staged)
        try:
            ST.recall_set("wanted_last_%s" % gid, str(qq))
        except Exception:
            pass
    return f"打劫银行成功！从金库劫走{loot}{ST.coin_name()}！（已进入30分钟治安通缉，悬赏{bounty}{ST.coin_name()}）"


def _vault_stage_delta(gid, delta):
    """金库增减 stage 进当前事务（不单独 commit；调用方随后 txn_coins_acct 统一提交）。"""
    try:
        v, cap = _vault_state(gid)
        new_v = max(0, min(cap, int(v) + int(delta)))
        if ST._DB is None:
            return None
        ST._DB.execute("INSERT INTO kv(k, v) VALUES(?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v",
                       ("bank_vault_%s" % gid, str(new_v)))
        ST._DB.execute("INSERT INTO kv(k, v) VALUES(?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v",
                       ("bank_vault_ts_%s" % gid, str(time.time())))
        return (new_v, cap)
    except Exception:
        try:
            ST._safe_rollback()
        except Exception:
            pass
        return None


def _vault_stage_commit_cache(gid, staged):
    """txn 成功后把已提交的金库值写进 _KV_CACHE（DB 已正确，仅防缓存读旧值）。"""
    if not staged:
        return
    new_v, _cap = staged
    try:
        _kvc = getattr(ST, "_KV_CACHE", None)
        _lock = getattr(ST, "_KV_CACHE_LOCK", None)
        if _kvc is None or _lock is None:
            from core.storage import state as _st_state  # type: ignore
            _kvc, _lock = _st_state._KV_CACHE, _st_state._KV_CACHE_LOCK
        with _lock:
            _kvc["bank_vault_%s" % gid] = str(new_v)
            _kvc["bank_vault_ts_%s" % gid] = str(time.time())
    except Exception:
        pass


def cmd_sell_slave(gid, qq, target):
    """打劫个人: 按配置概率/体力/金额, 失败扣魅力+入狱"""
    if not target:
        return "亲，您的格式有误，打劫格式为：【打劫 @QQ】！"
    if str(target) == str(qq):
        return "亲，无法对自己实施打劫！"
    a = _acct(gid, qq)
    if _check_jail(a):
        return _show_jail(a)
    ta = _acct(gid, target)
    if _check_jail(ta):
        return "对方还在监狱中，无法对他实行打劫！"
    cs = cfgi("银行配置", "打劫消耗体力", 20)
    if a.int("stamina") < cs:
        return "亲，您的体力不足，无法实施打劫！"
    if ST.coins_get(gid, qq) < 500:
        return f"亲，您的{ST.coin_name()}不足，无法实施打劫！"
    if ST.coins_get(gid, target) < 100:
        return "亲，对方是个穷光蛋，无法对他实施打劫！"
    ok, mins = _cd(a, "rob_time", cfgi("银行配置", "打劫关押时间", 5))
    if not ok:
        return f"{mins}分钟后再来打劫吧！"
    prob = cfgi("银行配置", "打劫成功概率", 65)
    try:
        from ..sign import eff_prob as _luck_eff3
        prob = _luck_eff3(prob, gid, qq)
    except Exception:
        pass
    lo = cfgi("银行配置", "打劫金钱下限", 1000)
    hi = cfgi("银行配置", "打劫金钱上限", 100000)
    meli = cfgi("银行配置", "打劫魅力减少", 3)
    jail_mins = cfgi("银行配置", "打劫关押时间", 5)
    now_s = _now_s()
    cur_st = a.int("stamina")
    if random.random() * 100 < prob:
        victim_money = ST.coins_get(gid, target)
        loot = min(victim_money, random.randint(lo, hi))
        if loot <= 0:
            return "亲，对方是个穷光蛋，无法对他实施打劫！"
        bounty = min(15000, max(1000, loot // 3))
        result = ST.txn_two_wallets_acct(
            gid, target, qq, loot,
            {
                "stamina": str(max(0, cur_st - cs)),
                "rob_time": now_s,
                "wanted_until": str(int(time.time()) + 1800),
                "wanted_bounty": str(bounty),
            },
            acct_qq=qq,
        )
        if result is not True:
            return "银行系统繁忙，本次打劫未结算，未扣除体力和资金，请稍后重试！" if result is None else "亲，对方是个穷光蛋，无法对他实施打劫！"
        try:
            ST.recall_set("wanted_last_%s" % gid, str(qq))
        except Exception:
            pass
        tn = _disp_name(target, gid)
        return f"打劫成功！你从 {tn} 处劫走{loot}{ST.coin_name()}！（已进入30分钟通缉，悬赏{bounty}{ST.coin_name()}）"

    cur_money = ST.coins_get(gid, qq)
    fine = min(1000, cur_money)
    updates = {
        "stamina": str(max(0, cur_st - cs)),
        "charm": str(max(0, a.int("charm") - meli)),
        "jail": "1",
        "jail_start": now_s,
        "release_timestamp": str(int(time.time()) + int(jail_mins) * 60),
        "rob_time": now_s,
    }
    if ST.txn_coins_acct(gid, qq, -fine, updates) is None:
        return "银行系统繁忙，本次打劫未结算，未扣除体力和资金，请稍后重试！"
    return (f"打劫失败！实施打劫时被抓！被关监狱{jail_mins}分钟，\r\n"
            f"罚款{fine}{ST.coin_name()}，魅力-{meli}！")


def cmd_patrol(gid, qq):
    """治安巡逻：白道稳定赚钱玩法，协助银行巡视金库与群聊治安，领取津贴与魅力奖励"""
    a = _acct(gid, qq)
    if _check_jail(a):
        return _show_jail(a)
    cs = cfgi("银行配置", "巡逻消耗体力", 8)
    if a.int("stamina") < cs:
        return f"亲，治安巡逻需要 {cs} 点体力，您的体力不足！"
    cd_mins = cfgi("银行配置", "巡逻间隔", 5)
    ok, mins = _cd(a, "patrol_time", cd_mins)
    if not ok:
        return f"巡逻小队正在休整，请 {mins} 分钟后再来巡逻！"
    lo = cfgi("银行配置", "巡逻金钱下限", 1800)
    hi = cfgi("银行配置", "巡逻金钱上限", 4800)
    base_pay = random.randint(lo, max(lo, hi))
    charm = max(0, a.int("charm"))
    charm_bonus = min(2000, charm * 4)
    extra = 0
    charm_gain = 1
    event_desc = random.choice([
        "沿街护送运钞车平安抵达银行",
        "排查金库周边可疑人员，维护群内治安",
        "协助走失群友找回遗失钱包",
        "在商业街值守巡查，吓退潜伏扒手",
    ])
    if random.randint(1, 100) <= 25:
        extra = random.randint(1500, 3500)
        charm_gain = 2
        event_desc = "巡逻途中当场截获一名流窜惯偷，追回赃款获银行通报表扬"
    total_pay = base_pay + charm_bonus + extra
    now_s = _now_s()
    with ST._LOCK:
        cur_st = a.int("stamina")
        if cur_st < cs:
            return f"亲，治安巡逻需要 {cs} 点体力，您的体力不足！"
        cur_ch = a.int("charm")
        try:
            from ..sign import settle_stat_gain as _settle_stat
            new_ch, real_c, _, ov_c, _ = _settle_stat(cur_ch, charm_gain, 300, 500, 2)
        except Exception:
            new_ch, real_c, ov_c = min(500, cur_ch + charm_gain), charm_gain, 0
        if ST.txn_coins_acct(gid, qq, total_pay + ov_c, {
            "stamina": str(max(0, cur_st - cs)),
            "charm": str(new_ch),
            "patrol_time": now_s,
        }) is None:
            return "银行系统繁忙，巡逻补贴结算未成功，请稍后重试！"
    wanted_tip = ""
    try:
        w_qq = str(ST.recall_get("wanted_last_%s" % gid, "") or "").strip()
        if w_qq and w_qq != str(qq):
            wa = _acct(gid, w_qq)
            w_until = int(wa.get("wanted_until", "0") or 0)
            if w_until > int(time.time()) and not _check_jail(wa):
                w_bounty = int(wa.get("wanted_bounty", "1000") or 1000)
                w_name = _disp_name(w_qq, gid)
                wanted_tip = f"\r\n🚨 通缉线索：{w_name}({w_qq}) 正在通缉中（悬赏{w_bounty}{ST.coin_name()}），发送【抓捕 @{w_qq}】可缉拿领赏！"
    except Exception:
        pass
    extra_line = f"\r\n🏅 立功嘉奖：+{extra}{ST.coin_name()}" if extra > 0 else ""
    ov_note = f"（魅力软上限折算+{ov_c}{ST.coin_name()}）" if ov_c > 0 else ""
    return (
        f"🚓 治安巡逻完成！{event_desc}！\r\n"
        f"💰 巡逻津贴：{base_pay}{ST.coin_name()}"
        + (f"（含魅力加成+{charm_bonus}）" if charm_bonus > 0 else "")
        + extra_line
        + f"\r\n✨ 共获收益：{total_pay + ov_c}{ST.coin_name()}，魅力+{real_c}{ov_note}，体力-{cs}"
        + wanted_tip
    )


def cmd_arrest(gid, qq, target=None):
    """抓捕通缉犯：对打劫成功后30分钟内处于通缉状态的劫匪实施抓捕，缴获悬赏金并送入监狱"""
    target = _ensure_target_qq(target, gid)
    if not target:
        try:
            cand = str(ST.recall_get("wanted_last_%s" % gid, "") or "").strip()
            if cand and cand != str(qq):
                target = cand
        except Exception:
            pass
    if not target:
        return "请指定抓捕目标，格式：【抓捕 @QQ】（当前群暂无最新通缉犯）"
    if str(target) == str(qq):
        return "亲，不能自己抓捕自己！想体验铁窗泪请发送【我要进监狱】~"
    a = _acct(gid, qq)
    if _check_jail(a):
        return _show_jail(a)
    ta = _acct(gid, target)
    if _check_jail(ta):
        return "对方已经在监狱里服刑了，无需重复抓捕！"
    now_ts = int(time.time())
    wanted_until = int(ta.get("wanted_until", "0") or 0)
    if wanted_until <= now_ts:
        return "对方当前安分守己，不在通缉期内（打劫银行或打劫群友成功后30分钟内可被抓捕）！"
    cs = cfgi("银行配置", "巡逻消耗体力", 8)
    if a.int("stamina") < cs:
        return f"亲，执行抓捕需要 {cs} 点体力，您的体力不足！"
    ok, mins = _cd(a, "arrest_time", 3)
    if not ok:
        return f"抓捕行动刚结束，请 {mins} 分钟后再出警！"
    prob = cfgi("银行配置", "抓捕成功概率", 65)
    try:
        from ..sign import eff_prob as _luck_eff_ar
        prob = _luck_eff_ar(prob, gid, qq)
    except Exception:
        pass
    now_s = _now_s()
    tn = _disp_name(target, gid)
    if random.randint(1, 100) <= prob:
        bounty = max(1000, int(ta.get("wanted_bounty", "2000") or 2000))
        bank_bonus = max(800, bounty // 2)
        jail_mins = cfgi("银行配置", "打劫关押时间", 5)
        with ST._LOCK:
            cur_st = a.int("stamina")
            if cur_st < cs:
                return f"亲，执行抓捕需要 {cs} 点体力，您的体力不足！"
            cur_ch = a.int("charm")
            try:
                from ..sign import settle_stat_gain as _settle_stat2
                new_ch, real_c, _, ov_c, _ = _settle_stat2(cur_ch, 3, 300, 500, 2)
            except Exception:
                new_ch, real_c, ov_c = min(500, cur_ch + 3), 3, 0
            robber_coins = ST.coins_get(gid, target)
            seized = min(robber_coins, bounty)
            acct_upd = {
                "stamina": str(max(0, cur_st - cs)),
                "charm": str(new_ch),
                "arrest_time": now_s,
            }
            if seized > 0:
                res = ST.txn_two_wallets_acct(
                    gid, target, qq, seized,
                    acct_upd,
                    acct_qq=qq,
                )
                if res is None:
                    return "银行系统繁忙，抓捕结算未成功，请稍后重试！"
            else:
                if ST.txn_coins_acct(gid, qq, 0, acct_upd) is None:
                    return "银行系统繁忙，抓捕结算未成功，请稍后重试！"
            ST.coins_add(gid, qq, bank_bonus + ov_c)
            ta2 = _acct(gid, target)
            ta2.set("jail", "1")
            ta2.set("jail_start", now_s)
            ta2.set("release_timestamp", str(now_ts + int(jail_mins) * 60))
            ta2.set("wanted_until", "0")
            ta2.set("wanted_bounty", "0")
            ST.acct_save(gid, target)
            try:
                if str(ST.recall_get("wanted_last_%s" % gid, "")) == str(target):
                    ST.recall_set("wanted_last_%s" % gid, "")
            except Exception:
                pass
        total_gain = seized + bank_bonus + ov_c
        return (
            f"🚨 抓捕成功！你将通缉犯 {tn} 缉拿归案，关押入狱 {jail_mins} 分钟！\r\n"
            f"💰 追缴赃款：{seized}{ST.coin_name()} + 银行悬赏：{bank_bonus}{ST.coin_name()}（共获 {total_gain}{ST.coin_name()}）\r\n"
            f"✨ 魅力+{real_c}，体力-{cs}"
        )
    consolation = 300
    with ST._LOCK:
        cur_st = a.int("stamina")
        if ST.txn_coins_acct(gid, qq, consolation, {
            "stamina": str(max(0, cur_st - cs)),
            "arrest_time": now_s,
        }) is None:
            return "银行系统繁忙，抓捕结算未成功，请稍后重试！"
    return f"💨 抓捕未果！通缉犯 {tn} 负隅顽抗侥幸逃脱，银行发放 {consolation}{ST.coin_name()} 出警补贴（体力-{cs}）！"


# ---- 统一入口 ----

__all__ = [
    "_settle_interest",
    "cmd_arrest",
    "cmd_cross_transfer",
    "cmd_deposit",
    "cmd_force_withdraw",
    "cmd_gamble",
    "cmd_patrol",
    "cmd_rob_zone",
    "cmd_sell_slave",
    "cmd_transfer",
    "cmd_withdraw",
]
