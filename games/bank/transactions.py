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


def _format_countdown(seconds):
    if seconds <= 0:
        return "即将结算"
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h > 0:
        if s > 0:
            return f"{h}小时{m}分{s}秒"
        elif m > 0:
            return f"{h}小时{m}分"
        return f"{h}小时"
    if m > 0:
        if s > 0:
            return f"{m}分{s}秒"
        return f"{m}分"
    return f"{s}秒"


def cmd_deposit(gid, qq, amount):
    if amount <= 0:
        return "提示：存款指令格式为【存款 金额】，例如：存款 1000"
    # 读-校验-写全程持 _LOCK（RLock 可重入，txn 内复入无死锁）：防同用户并发双花/丢更新
    with ST._LOCK:
        a = _acct(gid, qq)
        if _check_jail(a):
            return _show_jail(a)
        cs = cfgi("银行配置", "存取款消耗体力", 1)
        cur_st = a.int("stamina")
        if cur_st < cs:
            return f"提示：您的体力不足，本次存款需消耗 {cs} 点体力（当前体力：{cur_st} 点）。"
        have = ST.coins_get(gid, qq)
        if have < amount:
            return f"提示：您的{ST.coin_name()}不足，当前钱包余额：{ST.fmt_coins(have)} {ST.coin_name()}。"
        rate = cfgi("银行配置", "存款利率", 1)
        cap = cfgi("银行配置", "利息上限", 50000)
        max_daily = cfgi("银行配置", "每日结息次数", 3)
        term_h = max(1, cfgi("银行配置", "存款期限", 1))
        today_s = str(dt.date.today())
        cur_cnt = int(a.get("interest_count", "0") or 0) if a.get("interest_date", "") == today_s else 0
        interest = _settle_interest(a, rate, cap)
        old = a.int("deposit")
        prev_ts = a.int("withdraw_timestamp")
        updates = {
            "stamina": str(cur_st - cs),
            "deposit": str(old + amount + interest),
        }
        if old <= 0 or interest > 0 or prev_ts <= 0:
            updates["withdraw_timestamp"] = str(int(time.time()))
        if interest > 0:
            updates["interest_date"] = today_s
            updates["interest_count"] = str(cur_cnt + 1)
        if ST.txn_coins_acct(gid, qq, -amount, updates, require_funds=True) is None:
            return "提示：银行系统繁忙，存款操作未完成，请稍后重试。"
        total = old + amount + interest
        settle_base_ts = float(updates.get("withdraw_timestamp", prev_ts if prev_ts > 0 else time.time()))
        left_sec = max(0, int(term_h * 3600 - (time.time() - settle_base_ts)))
        countdown_str = _format_countdown(left_sec)
        pot_interest = min(cap, max(1, int(total * rate / 100.0))) if total > 0 and rate > 0 else 0

        if max_daily > 0 and (cur_cnt + (1 if interest > 0 else 0)) >= max_daily:
            settle_info = f"今日结息次数已达上限（{max_daily}次），次日0点重置"
        else:
            settle_info = f"需满{term_h}小时（距下次结息还剩{countdown_str}，满期预计收益{ST.fmt_coins(pot_interest)}{ST.coin_name()}）"

        msg = (f"存款成功！消耗{cs}点体力，共存入：{ST.fmt_coins(amount)}，\r\n"
               f"上期结息：{ST.fmt_coins(interest)}，当前总存款：{ST.fmt_coins(total)}，{settle_info}\r\n"
               f"剩余{ST.coin_name()}：{ST.fmt_coins(ST.coins_get(gid, qq))}")
        return msg


def _settle_interest(a, rate, cap):
    """按 上次取款时间戳 到现在的小时数计息(满 存款期限 小时才结息, 封顶利息上限, 每日最多结息 N 次)"""
    ts = a.get("withdraw_timestamp", "")
    try:
        last = float(ts) if ts else 0.0
    except Exception:
        last = 0.0
    dep = a.int("deposit")
    if dep <= 0 or rate <= 0:
        return 0
    max_daily = cfgi("银行配置", "每日结息次数", 3)
    if max_daily > 0:
        today_s = str(dt.date.today())
        cur_cnt = int(a.get("interest_count", "0") or 0) if a.get("interest_date", "") == today_s else 0
        if cur_cnt >= max_daily:
            return 0
    term_h = max(1, cfgi("银行配置", "存款期限", 1))
    if last > 0:
        elapsed_h = (time.time() - last) / 3600.0
        if elapsed_h < term_h:
            return 0
    raw_interest = int(dep * rate / 100.0)
    interest = max(1, raw_interest) if dep > 0 else 0
    return min(interest, cap)


def cmd_withdraw(gid, qq, amount):
    # 读-校验-写全程持 _LOCK：防并发双取（同一存款被两个线程同时取走）
    with ST._LOCK:
        a = _acct(gid, qq)
        if _check_jail(a):
            return _show_jail(a)
        dep = a.int("deposit")
        if amount <= 0:
            return "提示：取款指令格式为【取款 金额】，例如：取款 1000"
        if dep < amount:
            return f"提示：存款余额不足，当前银行存款总额为 {ST.fmt_coins(dep)} {ST.coin_name()}。"
        rate = cfgi("银行配置", "存款利率", 1)
        cap = cfgi("银行配置", "利息上限", 50000)
        max_daily = cfgi("银行配置", "每日结息次数", 3)
        term_h = max(1, cfgi("银行配置", "存款期限", 1))
        today_s = str(dt.date.today())
        cur_cnt = int(a.get("interest_count", "0") or 0) if a.get("interest_date", "") == today_s else 0
        interest = _settle_interest(a, rate, cap)

        # 结算前计算未满期剩余时间
        last_ts = float(a.get("withdraw_timestamp", "0") or "0")
        left_sec = max(0, int(term_h * 3600 - (time.time() - last_ts))) if last_ts > 0 else 0
        countdown_str = _format_countdown(left_sec)

        # 取款仅扣除本次取出的存款本金，利息为银行派发的收益额外计入钱包
        new_dep = dep - amount
        updates = {"deposit": str(new_dep)}
        if interest > 0 or new_dep <= 0:
            updates["withdraw_timestamp"] = str(int(time.time()))
        if interest > 0:
            updates["interest_date"] = today_s
            updates["interest_count"] = str(cur_cnt + 1)
        if ST.txn_coins_acct(gid, qq, amount + interest, updates) is None:
            return "提示：银行系统繁忙，取款操作未完成，请稍后重试。"

        pot_interest = min(cap, max(1, int(new_dep * rate / 100.0))) if new_dep > 0 and rate > 0 else 0

        msg = (f"取款成功！获得利息：{ST.fmt_coins(interest)}，本次取款：{ST.fmt_coins(amount)}，\r\n"
               f"还剩存款：{ST.fmt_coins(new_dep)}，剩余{ST.coin_name()}：{ST.fmt_coins(ST.coins_get(gid, qq))}")
        if interest > 0:
            if new_dep > 0:
                msg += f"\r\n（提示：本期利息已到账，剩余存款开启新一轮结息，满{term_h}小时后结算）"
            else:
                msg += "\r\n（提示：存款已全部取出，本期结息已完成）"
        else:
            if max_daily > 0 and cur_cnt >= max_daily:
                msg += f"\r\n（提示：今日结息次数已达上限{max_daily}次，次日0点重置）"
            elif new_dep > 0:
                msg += f"\r\n（提示：利息结算需满{term_h}小时，还需{countdown_str}，到期可获{ST.fmt_coins(pot_interest)}{ST.coin_name()}，不影响剩余存款计息）"
            else:
                msg += f"\r\n（提示：提前支取未获利息，原距结息还需{countdown_str}，存款已清空）"
        return msg


def cmd_transfer(gid, qq, target, amount):
    # QQ-only: 兼容 CQ / @QQ / 纯QQ 字符串，不认昵称
    target = _ensure_target_qq(target, gid)
    if amount <= 0 or not target:
        return "提示：转账格式为【转账 @目标 金额】，例如：转账 @某某 100"
    if str(target) == str(qq):
        return "提示：无法对自己进行转账。"
    try:
        from ..slave.slave_state import is_bot_qq
        if is_bot_qq(target):
            return "提示：机器人不参与经济流通，无法接收转账哦~"
    except Exception:
        pass
    min_amt = cfgi("银行配置", "转账最小金额", 50)
    if amount < min_amt:
        return f"提示：转账最小金额为 {min_amt} {ST.coin_name()}。"
    cs = cfgi("银行配置", "转账消耗体力", 2)
    cur_st = _acct(gid, qq).int("stamina")
    if cur_st < cs:
        return f"提示：您的体力不足，本次转账需消耗 {cs} 点体力（当前体力：{cur_st} 点）。"
    cap = cfgi("银行配置", "转账接收额度", getattr(ST, "COIN_CAP", 100000000000))
    if amount > cap:
        return f"提示：单次转账金额不能超过 {cap} {ST.coin_name()}。"
    if ST.coins_get(gid, qq) < amount:
        return f"提示：钱包余额不足，当前持有 {ST.fmt_coins(ST.coins_get(gid, qq))} {ST.coin_name()}。"
    credit = int(amount)
    # 单事务原子转账：体力+双钱包同锁，避免体力扣了但转账失败半成功
    try:
        with ST._LOCK:
            # 二次校验（防并发）
            cur_st = ST.acct(gid, qq).int("stamina")
            if cur_st < cs:
                return "提示：您的体力不足，本次转账需消耗 {cs} 点体力。"
            cur_money = ST.coins_get(gid, qq)
            if cur_money < amount:
                return "提示：账户余额不足，转账失败。"
            # 对方余额与上限（锁内读）
            dst_cur = ST.coins_get(gid, target)
            credit = min(int(amount), max(0, cap - dst_cur))
            if credit <= 0:
                return "提示：对方钱包已达存储上限，无法接收转账。"
            updates = {"stamina": str(max(0, cur_st - cs))}
            # 用 txn_two_wallets_acct 一并提交：转出方扣体力+扣款，转入方加款
            if ST.txn_two_wallets_acct(gid, qq, target, credit, acct_updates=updates, acct_qq=qq) is None:
                return "提示：银行系统繁忙，转账操作未完成，请稍后重试。"
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
        return "提示：银行系统繁忙，转账操作未完成，请稍后重试。"
    try:
        from .. import slave as SL
        try:
            tn = SL.display_name(gid, str(target))
        except Exception:
            tn = SL.NOTE_NAMES.get(str(target), str(target))
    except Exception:
        tn = str(target)
    return f"转账成功！您已向 {tn} 转入{ST.fmt_coins(credit)}{ST.coin_name()}！消耗{cs}点体力，剩余{ST.coin_name()}：{ST.fmt_coins(ST.coins_get(gid, qq))}"


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
        return "提示：跨群转账格式为【跨群转账 群号 金额】"
    if str(dest_gid) == str(gid):
        return "提示：目标群不能是当前群，同群转账请直接使用【转账】。"
    if not _gid_known(dest_gid):
        return "提示：目标群不存在或机器人未加入该群，请核对群号。"
    min_amt = cfgi("银行配置", "转账最小金额", 50)
    if amount < min_amt:
        return f"提示：跨群转账最小金额为 {min_amt} {ST.coin_name()}。"
    pct = cfgi("银行配置", "跨群转账手续费", 20)
    try:
        pct = max(0, min(int(pct), 100))
    except Exception:
        pct = 20
    fee = int(amount) * pct // 100
    credit = int(amount) - fee
    if credit <= 0:
        return f"提示：手续费为 {pct}%，扣除后到账为 0，请提高转账金额。"
    cap = cfgi("银行配置", "转账接收额度", getattr(ST, "COIN_CAP", 100000000000))
    if ST.coins_get(gid, qq) < amount:
        return "提示：当前账户余额不足，跨群转账失败。"
    # 源群扣全款 + 目标群入 credit，差额（手续费）销毁：单事务原子，无半成功
    try:
        with ST._LOCK:
            if ST.coins_get(gid, qq) < amount:
                return "提示：当前账户余额不足，跨群转账失败。"
            dst_cur = ST.coins_get(dest_gid, qq)
            if dst_cur + credit > cap:
                return "提示：目标群钱包已达额度上限，无法继续转入。"
            ok = ST.txn_cross_group(gid, dest_gid, qq, amount, credit)
            if ok is None:
                return "提示：银行系统繁忙，跨群转账操作未完成，请稍后重试。"
            if not ok:
                return "提示：账户余额不足或目标钱包已达上限，跨群转账失败。"
    except Exception:
        try:
            ST._safe_rollback()
        except Exception:
            pass
        return "提示：银行系统繁忙，跨群转账操作未完成，请稍后重试。"
    return (f"跨群转账成功！\r\n"
            f"目标群：{dest_gid}，支出{ST.fmt_coins(amount)}{ST.coin_name()}，到账{ST.fmt_coins(credit)}{ST.coin_name()}，\r\n"
            f"手续费{ST.fmt_coins(fee)}{ST.coin_name()}（{pct}%）已由系统回收，剩余{ST.coin_name()}：{ST.fmt_coins(ST.coins_get(gid, qq))}")


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
    # 总资产保底 10000：现金+存款 <= 10000 拒绝；下注后总资产 < 10000 拒绝
    cur_cash_pre = ST.coins_get(gid, qq)
    cur_dep_pre = a.int("deposit")
    total_pre = cur_cash_pre + cur_dep_pre
    if total_pre <= 10000:
        return f"亲，您的总资产（现金+存款）不足10000{ST.coin_name()}，无法参与赌博！必须保留至少10000保底生活费！"
    if total_pre - amount < 10000:
        max_bet = max(0, total_pre - 10000)
        return (f"亲，赌博后总资产必须保有至少{ST.fmt_coins(10000)}{ST.coin_name()}保底生活费！"
                f"您当前总资产为{ST.fmt_coins(total_pre)}{ST.coin_name()}，本次最多可下注{ST.fmt_coins(max_bet)}{ST.coin_name()}！")
    if cur_cash_pre < amount:
        return "亲，您的现金不足，无法进行赌博（不可直接透支银行存款下注，请先前往银行取款）！"
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
    # 原子化：钱包+体力+魅力+日计数 统归事务处理，避免半成功/脏读
    try:
        with ST._LOCK:
            cur = ST.coins_get(gid, qq)
            a2 = ST.acct(gid, qq)
            cur_dep = a2.int("deposit")
            total_assets = cur + cur_dep
            if total_assets <= 10000:
                return f"亲，您的总资产（现金+存款）不足{ST.fmt_coins(10000)}{ST.coin_name()}，无法参与赌博！必须保留至少{ST.fmt_coins(10000)}保底生活费！"
            if total_assets - amount < 10000:
                max_bet = max(0, total_assets - 10000)
                return (f"亲，赌博后总资产必须保有至少{ST.fmt_coins(10000)}{ST.coin_name()}保底生活费！"
                        f"您当前总资产为{ST.fmt_coins(total_assets)}{ST.coin_name()}，本次最多可下注{ST.fmt_coins(max_bet)}{ST.coin_name()}！")
            if cur < amount:
                return "亲，您的现金不足，无法进行赌博（不可直接透支银行存款下注，请先前往银行取款）！"
            cur_st = a2.int("stamina")
            if cur_st < cs:
                return "亲，您的体力不足，无法进行赌博！"
            # 锁内重读日计数：防锁外读到旧值绕过当日上限
            cnt = int(ST.recall_get("gamble_%s_%s_%s" % (gid, qq, dt.date.today()), "0") or 0)
            if cnt >= lim:
                return "亲，您今日赌博次数已达上限，无法再进行赌博！"

            if random.random() * 100 < prob:
                # 成功：净赚 gain - amount
                updates = {"stamina": str(cur_st - cs)}
                if ST.txn_coins_acct(gid, qq, gain - amount, updates, require_funds=True) is None:
                    return "赌博系统繁忙，本次未结算，未扣除资金和体力，请稍后重试！"
                try:
                    ST.recall_set("gamble_%s_%s_%s" % (gid, qq, dt.date.today()), str(cnt + 1))
                except Exception:
                    pass
                return f"赌博成功！你获得了{ST.fmt_coins(gain)}{ST.coin_name()}，净赚{ST.fmt_coins(gain - amount)}！"
            else:
                # 失败：-amount 魅力 -meli
                cur_mei = a2.int("charm")
                meli_eff = max(0, min(int(meli), cur_mei))
                updates = {
                    "stamina": str(cur_st - cs),
                    "charm": str(cur_mei - meli_eff),
                }
                jail = random.random() < 0.5
                if jail:
                    updates["jail"] = "1"
                    updates["jail_start"] = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    updates["release_timestamp"] = str(int(time.time()) + int(jail_mins) * 60)
                if ST.txn_coins_acct(gid, qq, -amount, updates, require_funds=True) is None:
                    return "赌博系统繁忙，本次未结算，未扣除资金和体力，请稍后重试！"
                try:
                    ST.recall_set("gamble_%s_%s_%s" % (gid, qq, dt.date.today()), str(cnt + 1))
                except Exception:
                    pass
                if jail:
                    return (f"赌博失败，损失{ST.fmt_coins(amount)}{ST.coin_name()}，魅力-{meli_eff}！\r\n"
                            f"赌博时被抓了！被关监狱{jail_mins}分钟！")
                return f"赌博失败，损失{ST.fmt_coins(amount)}{ST.coin_name()}，魅力-{meli_eff}……愿赌服输~"
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
        cd_str = str(mins) if str(mins).endswith(("秒", "分", "分钟", "小时")) else f"{mins}分钟"
        return f"{cd_str}后再来打劫银行吧！"
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
        want_fine = max(0, cfgi("银行配置", "打劫失败罚金", 500))
        cur_cash = ST.coins_get(gid, qq)
        fine = min(cur_cash, want_fine)
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
                f"罚款{ST.fmt_coins(fine)}{ST.coin_name()}，魅力-{meli}！")
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
        if ST.txn_coins_acct(gid, qq, loot,
                             {"stamina": str(max(0, a.int("stamina") - cs)), "rob_bank_time": now_s}) is None:
            return "银行系统繁忙，本次打劫未结算，请稍后重试！"
        _vault_stage_commit_cache(gid, staged)
    return f"打劫银行成功！从金库劫走{ST.fmt_coins(loot)}{ST.coin_name()}！"


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
        st_mod = getattr(ST, "_state", None)
        _kvc = getattr(ST, "_KV_CACHE", getattr(st_mod, "_KV_CACHE", None))
        _lock = getattr(ST, "_KV_CACHE_LOCK", getattr(st_mod, "_KV_CACHE_LOCK", None))
        if _kvc is not None and _lock is not None:
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
    try:
        from ..slave.slave_state import is_bot_qq
        if is_bot_qq(target):
            return "亲，机器人是系统执法者与管理员，不可被打劫哦~"
    except Exception:
        pass
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
        return f"亲，您的现金不足500{ST.coin_name()}，无法实施打劫！"
    if ST.coins_get(gid, target) < 100:
        return "亲，对方是个穷光蛋，无法对他实施打劫！"
    ok, mins = _cd(a, "rob_time", cfgi("银行配置", "打劫关押时间", 5))
    if not ok:
        cd_str = str(mins) if str(mins).endswith(("秒", "分", "分钟", "小时")) else f"{mins}分钟"
        return f"{cd_str}后再来打劫吧！"
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
        if victim_money < 100:
            return "亲，对方是个穷光蛋，无法对他实施打劫！"
        max_cut = max(100, int(victim_money * 0.20))
        roll_loot = random.randint(lo, hi)
        loot = min(victim_money, max_cut, roll_loot)
        loot = max(1, loot)
        if victim_money - loot < 100 and victim_money > 100:
            loot = max(1, victim_money - 100)
        if loot <= 0:
            return "亲，对方是个穷光蛋，无法对他实施打劫！"
        result = ST.txn_two_wallets_acct(
            gid, target, qq, loot,
            {"stamina": str(max(0, cur_st - cs)), "rob_time": now_s},
            acct_qq=qq,
        )
        if result is not True:
            return "银行系统繁忙，本次打劫未结算，未扣除体力和资金，请稍后重试！" if result is None else "亲，对方是个穷光蛋，无法对他实施打劫！"
        tn = _disp_name(target, gid)
        return f"打劫成功！你从 {tn} 处劫走{ST.fmt_coins(loot)}{ST.coin_name()}！"

    cur_cash = ST.coins_get(gid, qq)
    want_fine = max(0, cfgi("银行配置", "打劫失败罚金", 1000))
    fine = min(cur_cash, want_fine)
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
            f"罚款{ST.fmt_coins(fine)}{ST.coin_name()}，魅力-{meli}！")


# ---- 统一入口 ----

__all__ = [
    "_settle_interest",
    "cmd_cross_transfer",
    "cmd_deposit",
    "cmd_gamble",
    "cmd_rob_zone",
    "cmd_sell_slave",
    "cmd_transfer",
    "cmd_withdraw",
]
