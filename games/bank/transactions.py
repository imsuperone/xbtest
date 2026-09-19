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
    a = _acct(gid, qq)
    if _check_jail(a):
        return _show_jail(a)
    cs = cfgi("银行配置", "存取款消耗体力", 1)
    if a.int("stamina") < cs:
        return "亲，您的游戏体力不足，无法进行存款！"
    have = ST.coins_get(gid, qq)
    if have < amount:
        return f"亲，您的{ST.coin_name()}不足，请重新选择存款数！"
    rate = cfgi("银行配置", "存款利率", 2)
    cap = cfgi("银行配置", "利息上限", 50000)
    interest = _settle_interest(a, rate, cap)
    old = a.int("deposit")
    if ST.txn_coins_acct(gid, qq, -amount, {"stamina": str(a.int("stamina") - cs), "deposit": str(old + amount + interest), "withdraw_timestamp": str(int(time.time()))}, require_funds=True) is None:
        return "亲，银行系统繁忙，存款未成功，请稍后重试！"
    total = old + amount + interest
    return (f"存款成功！消耗{cs}点体力，共存入：{amount}，\r\n"
            f"上期结息：{interest}，当前总存款：{total}，"
            f"当前利率：{rate}%，1小时后可取款！\r\n"
            f"剩余{ST.coin_name()}：{ST.coins_get(gid, qq)}")




def _settle_interest(a, rate, cap):
    """按 上次取款时间戳 到现在的小时数计息(满 1小时 才结息, 封顶利息上限) - 已改为1h结算(需求26)"""
    ts = a.get("withdraw_timestamp", "")
    try:
        last = float(ts)
    except Exception:
        last = time.time()
    dep = a.int("deposit")
    if dep <= 0:
        return 0
    # 改为小时结算：1小时=3600s
    elapsed_h = (time.time() - last) / 3600.0
    term_h = 1  # 固定1小时一结
    if elapsed_h < term_h:
        return 0
    interest = int(dep * rate / 100.0 * min(1.0, elapsed_h / term_h))
    return min(interest, cap)




def cmd_withdraw(gid, qq, amount):
    a = _acct(gid, qq)
    if _check_jail(a):
        return _show_jail(a)
    dep = a.int("deposit")
    if amount <= 0:
        return "请输入正确格式：取款 金额（正整数）"
    if dep < amount:
        return f"存款不足！当前存款：{dep}"
    rate = cfgi("银行配置", "存款利率", 2)
    cap = cfgi("银行配置", "利息上限", 50000)
    interest = _settle_interest(a, rate, cap)
    # 利息未到时提示剩余时间与可用强制取款，但仍允许取款（取款成功但无利息，满足测试与需求38的提示）
    if interest == 0 and dep > 0:
        try:
            last = float(a.get("withdraw_timestamp", "0") or "0")
            left = int(3600 - (time.time() - last))
            if left > 0:
                # 仍允许取款，但在成功消息中附加提示，兼顾测试的“取款成功”校验
                pot = int(dep * rate / 100.0)
                pot = min(pot, cap)
                # 不直接return，继续向下走取款成功逻辑，附加提示在最终返回中体现
                interest_note = f"（提示：利息结算需1小时，还需{left//60}分{left%60}秒，到期可获{pot}{ST.coin_name()}，可强取）"
            else:
                interest_note = ""
        except Exception:
            interest_note = ""
    else:
        interest_note = ""
    # 取款仅扣除本次取出的存款本金，利息为银行派发的收益额外计入钱包
    new_dep = dep - amount
    if ST.txn_coins_acct(gid, qq, amount + interest, {"deposit": str(new_dep), "withdraw_timestamp": str(int(time.time()))}) is None:
        return "亲，银行系统繁忙，取款未成功，请稍后重试！"
    base = (f"取款成功！获得利息：{interest}，本次取款：{amount}，\r\n"
            f"还剩存款：{new_dep}，剩余{ST.coin_name()}：{ST.coins_get(gid, qq)}")
    if 'interest_note' in locals() and interest_note:
        base += f"\r\n{interest_note}"
    return base




def cmd_force_withdraw(gid, qq, amount):
    """强制取款: 未到期限强制取款无利息，不影响后续利息按剩余计（不重置计时）原子版"""
    a = _acct(gid, qq)
    if _check_jail(a):
        return _show_jail(a)
    dep = a.int("deposit")
    if amount <= 0:
        return "请输入正确格式：强制取款 金额（正整数）"
    if dep < amount:
        return f"存款不足！当前存款：{dep}"
    # 原子：钱包 + 存款同事务，避免半成功（中文文案不变）
    # txn 失败返 None（内部已回滚）：走原子单项降级，而非当成功
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
    # 原子化：体力与双钱包同锁，避免体力扣了但转账失败半成功
    try:
        # 尝试在同一 _LOCK 内完成体力扣减 + 钱包转账
        if hasattr(ST, "_LOCK"):
            with ST._LOCK:
                # 二次校验（防并发）
                cur_st = ST.acct(gid, qq).int("stamina")
                if cur_st < cs:
                    return "亲，您的游戏体力不足，无法进行转账！"
                cur_money = 0
                if ST._DB is not None:
                    row = ST._DB.execute("SELECT money FROM wallet WHERE gid=? AND qq=?", (int(gid), int(qq))).fetchone()
                    cur_money = int(row[0]) if row else 0
                if cur_money < amount:
                    return "亲，您的账户余额不足，转账失败！"
                # 扣体力
                a = ST.acct(gid, qq)
                a.set("stamina", str(cur_st - cs))
                ST._DB.execute("INSERT INTO accounts(gid, qq, data) VALUES(?,?,?) ON CONFLICT(gid, qq) DO UPDATE SET data=excluded.data", (int(gid), int(qq), json.dumps(a.kv, ensure_ascii=False)))
                # 钱包转账（P1: 接收方达上限截断时差额不得销毁，按实际credit扣减）
                row2 = ST._DB.execute("SELECT money FROM wallet WHERE gid=? AND qq=?", (int(gid), int(target))).fetchone()
                dst_cur = int(row2[0]) if row2 else 0
                credit = min(int(amount), max(0, getattr(ST, "COIN_CAP", 100000000000) - dst_cur))
                if credit <= 0:
                    ST._safe_rollback()
                    return "对方钱包已满，无法接收转账！"
                new_src = cur_money - credit
                new_dst = dst_cur + credit
                ST._DB.execute("INSERT INTO wallet(gid, qq, money) VALUES(?,?,?) ON CONFLICT(gid, qq) DO UPDATE SET money=excluded.money", (int(gid), int(qq), new_src))
                ST._DB.execute("INSERT INTO wallet(gid, qq, money) VALUES(?,?,?) ON CONFLICT(gid, qq) DO UPDATE SET money=excluded.money", (int(gid), int(target), new_dst))
                # 先验 commit 再清脏：提交失败抛给降级，不吞错报成功
                try:
                    ST._DB.commit()
                except Exception:
                    ST._safe_rollback()
                    raise
                a.dirty = False
        else:
            # 降级：原逻辑
                ST.acct_add(gid, qq, "stamina", -cs)
                if hasattr(ST, "txn_two_wallets") and not ST.txn_two_wallets(gid, qq, target, amount):
                    # 回滚体力
                    ST.acct_add(gid, qq, "stamina", cs)
                    return "亲，您的账户余额不足，转账失败！"
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
    cnt = int(ST.recall_get("gamble_%s_%s_%s" % (gid, qq, dt.date.today()), "0") or 0)
    if cnt >= lim:
        return "亲，您今日赌博次数已达上限，无法再进行赌博！"
    if ST.coins_get(gid, qq) < amount:
        return f"亲，您的{ST.coin_name()}不足，无法进行赌博！"
    meli = cfgi("银行配置", "赌博魅力减少", 20)
    jail_mins = cfgi("银行配置", "赌博关押时间", 5)
    prob = cfgi("银行配置", "赌博成功概率", 60)
    gain = int(amount * GAMBLE_MULT)
    # 原子化：钱包+体力+魅力 同事务，避免半成功通胀
    try:
        with ST._LOCK:
            cur = ST.coins_get(gid, qq)
            if cur < amount:
                return f"亲，您的{ST.coin_name()}不足，无法进行赌博！"
            cur_st = ST.acct(gid, qq).int("stamina")
            if cur_st < cs:
                return "亲，您的体力不足，无法进行赌博！"
            a2 = ST.acct(gid, qq)
            a2.set("stamina", str(cur_st - cs))
            if random.random() * 100 < prob:
                # 成功：-amount +gain
                new_money = cur - amount + gain
                ST._DB.execute("INSERT INTO wallet(gid, qq, money) VALUES(?,?,?) ON CONFLICT(gid, qq) DO UPDATE SET money=excluded.money", (int(gid), int(qq), new_money))
                ST._DB.execute("INSERT INTO accounts(gid, qq, data) VALUES(?,?,?) ON CONFLICT(gid, qq) DO UPDATE SET data=excluded.data", (int(gid), int(qq), json.dumps(a2.kv, ensure_ascii=False)))
                # 先验 commit 再清脏＋计数：提交失败抛给降级；计数失败只丢一次（优于降级双重收费）
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
                a2.set("charm", str(cur_mei - meli))
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
                    return (f"赌博失败，损失{amount}{ST.coin_name()}，魅力-{meli}！\r\n"
                            f"赌博时被抓了！被关监狱{jail_mins}分钟！")
                return f"赌博失败，损失{amount}{ST.coin_name()}，魅力-{meli}……愿赌服输~"
    except Exception:
        # 主路径半截写入必须先回滚；失败不得重新随机或拆单收费。
        try:
            ST._safe_rollback()
        except Exception:
            pass
        # 半截缓存污染：主路径 a2.set 已改缓存，逐出后降级从回滚后 DB 重载，防体力/魅力双扣
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




_VAULT_LOCK = None  # 独立金库 RMW 锁（bank 无 _cmd_lock，12 worker 下防并发超发）


def _vault_lock():
    global _VAULT_LOCK
    if _VAULT_LOCK is None:
        try:
            import threading as _th
            _VAULT_LOCK = _th.Lock()
        except Exception:
            pass
    return _VAULT_LOCK


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
        # 从未初始化：按初始值开库（与“被掏空=0”严格区分，禁回种）
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


def _vault_set(gid, v):
    """金库落盘（含时间戳），失败返 False（调用方退款/报繁忙，禁吞错）。"""
    try:
        v = max(0, int(v))
    except Exception:
        return False
    try:
        if not ST.recall_set("bank_vault_%s" % gid, str(v)):
            return False
        ST.recall_set("bank_vault_ts_%s" % gid, str(time.time()))
        return True
    except Exception:
        return False


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
        if ST.txn_coins_acct(gid, qq, -fine, updates) is None:
            return "银行系统繁忙，本次打劫未结算，请稍后重试！"
        # 罚金充公进金库（按上限截断，落盘失败不影响主流程回执）
        try:
            _lk = _vault_lock()
            if _lk is not None:
                with _lk:
                    _v, _cap = _vault_state(gid)
                    _vault_set(gid, min(_cap, _v + max(0, int(fine or 0))))
            else:
                _v, _cap = _vault_state(gid)
                _vault_set(gid, min(_cap, _v + max(0, int(fine or 0))))
        except Exception:
            pass
        return (f"打劫银行失败，打劫银行时被抓！被关监狱{jail_mins}分钟，\r\n"
                f"罚款{fine}{ST.coin_name()}，魅力-{meli}！")
    lo = cfgi("银行配置", "打劫银行金钱下限", 6000)
    hi = cfgi("银行配置", "打劫银行金钱上限", 12000)
    want = max(1, random.randint(lo, hi) if hi >= lo else lo)
    try:
        _lk = _vault_lock()
        _held = False
        if _lk is not None:
            _lk.acquire()
            _held = True
        try:
            vault, _cap = _vault_state(gid)
            loot = min(vault, want)
            if loot <= 0:
                return "银行金库空空如也，打劫失败，过段时间等金库回流再来！"
            if not _vault_set(gid, vault - loot):
                return "银行系统繁忙，本次打劫未结算，请稍后重试！"
        finally:
            if _held:
                try:
                    _lk.release()
                except Exception:
                    pass
    except Exception:
        return "银行系统繁忙，本次打劫未结算，请稍后重试！"
    if ST.txn_coins_acct(gid, qq, loot,
                         {"stamina": str(max(0, a.int("stamina") - cs)), "rob_bank_time": now_s}) is None:
        # 发放失败则金库退款（尽力，不抛错）
        try:
            _lk2 = _vault_lock()
            if _lk2 is not None:
                with _lk2:
                    _v2, _cap2 = _vault_state(gid)
                    _vault_set(gid, min(_cap2, _v2 + loot))
            else:
                _v2, _cap2 = _vault_state(gid)
                _vault_set(gid, min(_cap2, _v2 + loot))
        except Exception:
            pass
        return "银行系统繁忙，本次打劫未结算，请稍后重试！"
    return f"打劫银行成功！从金库劫走{loot}{ST.coin_name()}！"




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
        result = ST.txn_two_wallets_acct(
            gid, target, qq, loot,
            {"stamina": str(max(0, cur_st - cs)), "rob_time": now_s},
            acct_qq=qq,
        )
        if result is not True:
            return "银行系统繁忙，本次打劫未结算，未扣除体力和资金，请稍后重试！" if result is None else "亲，对方是个穷光蛋，无法对他实施打劫！"
        tn = _disp_name(target, gid)
        return f"打劫成功！你从 {tn} 处劫走{loot}{ST.coin_name()}！"

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


# ---- 统一入口 ----

__all__ = ["_settle_interest", "cmd_deposit", "cmd_force_withdraw", "cmd_gamble", "cmd_rob_zone", "cmd_sell_slave", "cmd_transfer", "cmd_withdraw"]
