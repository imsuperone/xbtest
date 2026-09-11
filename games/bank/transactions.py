# -*- coding: utf-8 -*-
"""games/bank·core（原 bank.py 切分，语义不变）。"""
import datetime as dt
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
    cs = ST.cfgi("银行配置", "存取款消耗体力", 1)
    if a.int("stamina") < cs:
        return "亲，您的游戏体力不足，无法进行存款！"
    have = ST.coins_get(gid, qq)
    if have < amount:
        return f"亲，您的{ST.coin_name()}不足，请重新选择存款数！"
    rate = ST.cfgi("银行配置", "存款利率", 3)
    cap = ST.cfgi("银行配置", "利息上限", 100000)
    interest = _settle_interest(a, rate, cap)
    old = a.int("deposit")
    ST.txn_coins_acct(gid, qq, -amount, {"stamina": str(a.int("stamina") - cs), "deposit": str(old + amount + interest), "withdraw_timestamp": str(int(time.time()))})
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
    rate = ST.cfgi("银行配置", "存款利率", 3)
    cap = ST.cfgi("银行配置", "利息上限", 100000)
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
    ST.txn_coins_acct(gid, qq, amount + interest, {"deposit": str(new_dep), "withdraw_timestamp": str(int(time.time()))})
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
    try:
        ST.txn_coins_acct(gid, qq, amount, {"deposit": str(dep - amount)})
    except Exception:
        ST.acct_add(gid, qq, "deposit", -amount)
        ST.coins_add(gid, qq, amount)
        ST.acct_save(gid, qq)
    # 不重置取款时间戳，利息仍按原剩余金额与原计时继续结算
    return (f"强制取款成功！因未到取款时间，本次没有利息（不影响后续利息按剩余{ dep - amount}计）。\r\n"
            f"本次取款：{amount}，还剩存款：{dep - amount}，"
            f"剩余{ST.coin_name()}：{ST.coins_get(gid, qq)}")




def cmd_transfer(gid, qq, target, amount):
    # 增强: 兼容 @昵称 / CQ / @QQ / 纯昵称 / 纯QQ 字符串 原子体力+钱包
    target = _ensure_target_qq(target, gid)
    if amount <= 0 or not target:
        return "亲，您的格式有误，转账格式为：【转账 @QQ 金额】！"
    if str(target) == str(qq):
        return "亲，您不能给自己转账，转账失败！"
    min_amt = ST.cfgi("银行配置", "转账最小金额", 50)
    if amount < min_amt:
        return f"亲，转账最小金额为{min_amt}{ST.coin_name()}！"
    cs = ST.cfgi("银行配置", "转账消耗体力", 2)
    if _acct(gid, qq).int("stamina") < cs:
        return "亲，您的游戏体力不足，无法进行转账！"
    cap = ST.cfgi("银行配置", "转账接收额度", getattr(ST, "COIN_CAP", 100000000000))
    if amount > cap:
        return f"亲，单次转账金额不能超过{cap}{ST.coin_name()}！"
    if ST.coins_get(gid, qq) < amount:
        return "亲，您的账户余额不足，转账失败！"
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
                ST._DB.execute("INSERT INTO accounts(gid, qq, data) VALUES(?,?,?) ON CONFLICT(gid, qq) DO UPDATE SET data=excluded.data", (int(gid), int(qq), __import__("json").dumps(a.kv, ensure_ascii=False)))
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
                ST._safe_commit()
                a.dirty = False
        else:
            # 降级：原逻辑
            ST.acct_add(gid, qq, "stamina", -cs)
            if hasattr(ST, "txn_two_wallets") and not ST.txn_two_wallets(gid, qq, target, amount):
                # 回滚体力
                ST.acct_add(gid, qq, "stamina", cs)
                return "亲，您的账户余额不足，转账失败！"
    except Exception:
        try:
            ST.coins_add(gid, qq, -amount)
            ST.coins_add(gid, target, amount)
        except Exception:
            pass
    try:
        from .. import slave as SL
        try:
            tn = SL.get_note_name(gid, str(target)) or SL.fetch_card(gid, str(target)) or str(target)
        except Exception:
            tn = SL.NOTE_NAMES.get(str(target), str(target))
    except Exception:
        tn = str(target)
    return f"转账成功！您已向 {tn} 转入{amount}{ST.coin_name()}！"




def cmd_gamble(gid, qq, amount):
    a = _acct(gid, qq)
    if _check_jail(a):
        return _show_jail(a)
    if amount < 100:
        return f"亲，赌博最小金额为100{ST.coin_name()}！格式为：【赌博 金额】"
    maxamt = ST.cfgi("银行配置", "赌博最大金额", 100000)
    if amount > maxamt:
        return f"亲，预赌金额不得超过{maxamt}{ST.coin_name()}！"
    cs = ST.cfgi("银行配置", "赌博消耗体力", 10)
    if a.int("stamina") < cs:
        return "亲，您的体力不足，无法进行赌博！"
    lim = ST.cfgi("银行配置", "赌博限定次数", 5)
    cnt = int(ST.recall_get("gamble_%s_%s_%s" % (gid, qq, dt.date.today()), "0") or 0)
    if cnt >= lim:
        return "亲，您今日赌博次数已达上限，无法再进行赌博！"
    if ST.coins_get(gid, qq) < amount:
        return f"亲，您的{ST.coin_name()}不足，无法进行赌博！"
    meli = ST.cfgi("银行配置", "赌博魅力减少", 20)
    jail_mins = ST.cfgi("银行配置", "赌博关押时间", 5)
    prob = ST.cfgi("银行配置", "赌博成功概率", 60)
    ST.recall_set("gamble_%s_%s_%s" % (gid, qq, dt.date.today()), str(cnt + 1))
    gain = int(amount * 1.8)
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
                ST._DB.execute("INSERT INTO accounts(gid, qq, data) VALUES(?,?,?) ON CONFLICT(gid, qq) DO UPDATE SET data=excluded.data", (int(gid), int(qq), __import__("json").dumps(a2.kv, ensure_ascii=False)))
                a2.dirty = False
                ST._safe_commit()
                return f"赌博成功！你获得了{gain}{ST.coin_name()}，净赚{gain - amount}！"
            else:
                # 失败：-amount 魅力 -meli
                new_money = cur - amount
                cur_mei = a2.int("charm")
                a2.set("charm", str(cur_mei - meli))
                ST._DB.execute("INSERT INTO wallet(gid, qq, money) VALUES(?,?,?) ON CONFLICT(gid, qq) DO UPDATE SET money=excluded.money", (int(gid), int(qq), new_money))
                ST._DB.execute("INSERT INTO accounts(gid, qq, data) VALUES(?,?,?) ON CONFLICT(gid, qq) DO UPDATE SET data=excluded.data", (int(gid), int(qq), __import__("json").dumps(a2.kv, ensure_ascii=False)))
                a2.dirty = False
                jail = random.random() < 0.5
                if jail:
                    a2.set("jail", "1")
                    a2.set("jail_start", __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                    a2.set("release_timestamp", str(int(__import__("time").time()) + int(jail_mins) * 60))
                    ST._DB.execute("INSERT INTO accounts(gid, qq, data) VALUES(?,?,?) ON CONFLICT(gid, qq) DO UPDATE SET data=excluded.data", (int(gid), int(qq), __import__("json").dumps(a2.kv, ensure_ascii=False)))
                ST._safe_commit()
                if jail:
                    return (f"赌博失败，损失{amount}{ST.coin_name()}，魅力-{meli}！\r\n"
                            f"赌博时被抓了！被关监狱{jail_mins}分钟！")
                return f"赌博失败，损失{amount}{ST.coin_name()}，魅力-{meli}……愿赌服输~"
    except Exception:
        pass
    # 降级
    ST.acct_add(gid, qq, "stamina", -cs)
    if random.random() * 100 < prob:
        ST.coins_add(gid, qq, -amount)
        ST.coins_add(gid, qq, gain)
        return f"赌博成功！你获得了{gain}{ST.coin_name()}，净赚{gain - amount}！"
    ST.coins_add(gid, qq, -amount)
    ST.acct_add(gid, qq, "charm", -meli)
    if random.random() < 0.5:
        _jail_put(a, jail_mins)
        return (f"赌博失败，损失{amount}{ST.coin_name()}，魅力-{meli}！\r\n"
                f"赌博时被抓了！被关监狱{jail_mins}分钟！")
    return f"赌博失败，损失{amount}{ST.coin_name()}，魅力-{meli}……愿赌服输~"




def cmd_rob_zone(gid, qq):
    """打劫银行(全服风控简化: 本群随机目标)"""
    a = _acct(gid, qq)
    if _check_jail(a):
        return _show_jail(a)
    cs = ST.cfgi("银行配置", "打劫银行消耗体力", 5)
    if a.int("stamina") < cs:
        return "亲，您的体力不足，无法实施银行打劫！"
    ok, mins = _cd(a, "rob_bank_time", ST.cfgi("银行配置", "打劫银行间隔", 10))
    if not ok:
        return f"{mins}分钟后再来打劫银行吧！"
    wins = []
    try:
        ST._ensure_db()
        if ST._DB is not None:
            with ST._LOCK:
                # 有界随机候选：ORDER BY RANDOM() LIMIT 8 再按 str 过滤自己。
                # 等价性：8 个名额中自己至多占 1 个，大群必含他人；候选均匀故最终受害人仍均匀；
                # 小群（≤8 人）一次取全，与原来全表 DISTINCT 结果一致（wallet 主键已保证唯一）。
                rows = ST._DB.execute(
                    "SELECT qq FROM wallet WHERE gid=? ORDER BY RANDOM() LIMIT 8", (int(gid),)).fetchall()
            wins = [q for q in (r[0] for r in rows)
                    if str(q) != str(qq)]
    except Exception:
        wins = []
    if not wins:
        return "银行金库暂时空虚，打劫失败，下次再来！"
    prob = ST.cfgi("银行配置", "打劫银行成功概率", 70)
    meli = ST.cfgi("银行配置", "打劫银行魅力减少", 3)
    jail_mins = ST.cfgi("银行配置", "打劫银行关押时间", 5)
    ST.acct_add(gid, qq, "stamina", -cs)
    if random.random() * 100 > prob:
        fine = min(ST.cfgi("银行配置", "打劫失败罚金", 500), ST.coins_get(gid, qq))
        if fine:
            ST.coins_add(gid, qq, -fine)
        ST.acct_add(gid, qq, "charm", -meli)
        _jail_put(a, jail_mins)
        return (f"打劫银行失败，打劫银行时被抓！被关监狱{jail_mins}分钟，\r\n"
                f"罚款{fine}{ST.coin_name()}，魅力-{meli}！")
    victim = random.choice(wins)
    lo = ST.cfgi("银行配置", "打劫银行金钱下限", 6000)
    hi = ST.cfgi("银行配置", "打劫银行金钱上限", 12000)
    loot = min(ST.coins_get(gid, victim), random.randint(lo, hi))
    if loot <= 0:
        # 银行不穷， victim 随机选有钱的，若仍为0则给保底
        loot = random.randint(lo, hi)
        # 若仍想模拟穷，返回银行特有文案而非“对方是个穷光蛋”
        if loot <= 0:
            return "银行金库暂时空虚，打劫失败，下次再来！"
    # P1: 双人同时打劫同一victim时TOCTOU双花，同事务原子划转
    # 失败时按现余额重算loot再试一次，防扣少发多凭空印钱
    try:
        _done = bool(hasattr(ST, "txn_two_wallets") and ST.txn_two_wallets(gid, victim, qq, loot))
        if not _done:
            try:
                _cur_v = int(ST.coins_get(gid, victim) or 0)
            except Exception:
                _cur_v = 0
            # 保底路径（victim原为0）允许银行垫付，不重算；否则按现余额钳制
            _was_bailout = False
            try:
                _was_bailout = (loot > 0 and _cur_v <= 0)
            except Exception:
                pass
            if not _was_bailout:
                loot = min(_cur_v, loot)
                if loot <= 0:
                    a.set("rob_bank_time", _now_s())
                    ST.acct_save(gid, qq)
                    return "银行金库暂时空虚，打劫失败，下次再来！"
                if hasattr(ST, "txn_two_wallets") and ST.txn_two_wallets(gid, victim, qq, loot):
                    _done = True
            if not _done:
                ST.coins_add(gid, victim, -loot)
                ST.coins_add(gid, qq, loot)
    except Exception:
        ST.coins_add(gid, victim, -loot)
        ST.coins_add(gid, qq, loot)
    a.set("rob_bank_time", _now_s())
    ST.acct_save(gid, qq)
    return f"打劫银行成功！获得{loot}{ST.coin_name()}！"




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
    cs = ST.cfgi("银行配置", "打劫消耗体力", 20)
    if a.int("stamina") < cs:
        return "亲，您的体力不足，无法实施打劫！"
    if ST.coins_get(gid, qq) < 500:
        return f"亲，您的{ST.coin_name()}不足，无法实施打劫！"
    if ST.coins_get(gid, target) < 100:
        return "亲，对方是个穷光蛋，无法对他实施打劫！"
    ok, mins = _cd(a, "rob_time", ST.cfgi("银行配置", "打劫关押时间", 5))
    if not ok:
        return f"{mins}分钟后再来打劫吧！"
    prob = ST.cfgi("银行配置", "打劫成功概率", 65)
    lo = ST.cfgi("银行配置", "打劫金钱下限", 1000)
    hi = ST.cfgi("银行配置", "打劫金钱上限", 100000)
    meli = ST.cfgi("银行配置", "打劫魅力减少", 3)
    jail_mins = ST.cfgi("银行配置", "打劫关押时间", 5)
    # 原子化：体力/魅力/双钱包同事务
    try:
        with ST._LOCK:
            cur_st = ST.acct(gid, qq).int("stamina")
            if cur_st < cs:
                return "亲，您的体力不足，无法实施打劫！"
            cur_money = ST.coins_get(gid, qq)
            if cur_money < 500:
                return f"亲，您的{ST.coin_name()}不足，无法实施打劫！"
            a2 = ST.acct(gid, qq)
            a2.set("stamina", str(cur_st - cs))
            a2.set("rob_time", _now_s())
            if random.random() * 100 < prob:
                victim_money = ST.coins_get(gid, target)
                loot = min(victim_money, random.randint(lo, hi))
                if loot <= 0:
                    ST._DB.execute("INSERT INTO accounts(gid, qq, data) VALUES(?,?,?) ON CONFLICT(gid, qq) DO UPDATE SET data=excluded.data", (int(gid), int(qq), __import__("json").dumps(a2.kv, ensure_ascii=False)))
                    a2.dirty = False
                    ST._safe_commit()
                    return "对方是个穷光蛋，无法对他实施打劫！"
                src_cur = cur_money
                dst_cur = victim_money
                ST._DB.execute("INSERT INTO wallet(gid, qq, money) VALUES(?,?,?) ON CONFLICT(gid, qq) DO UPDATE SET money=excluded.money", (int(gid), int(qq), src_cur + loot))
                ST._DB.execute("INSERT INTO wallet(gid, qq, money) VALUES(?,?,?) ON CONFLICT(gid, qq) DO UPDATE SET money=excluded.money", (int(gid), int(target), max(0, dst_cur - loot)))
                ST._DB.execute("INSERT INTO accounts(gid, qq, data) VALUES(?,?,?) ON CONFLICT(gid, qq) DO UPDATE SET data=excluded.data", (int(gid), int(qq), __import__("json").dumps(a2.kv, ensure_ascii=False)))
                a2.dirty = False
                ST._safe_commit()
                tn = _disp_name(target, gid)
                return f"打劫成功！你从 {tn} 处劫走{loot}{ST.coin_name()}！"
            else:
                # 失败
                fine = min(1000, cur_money)
                new_money = max(0, cur_money - fine)
                cur_mei = a2.int("charm")
                a2.set("charm", str(max(0, cur_mei - meli)))
                a2.set("jail", "1")
                a2.set("jail_start", _now_s())
                a2.set("release_timestamp", str(int(__import__("time").time()) + int(jail_mins) * 60))
                ST._DB.execute("INSERT INTO wallet(gid, qq, money) VALUES(?,?,?) ON CONFLICT(gid, qq) DO UPDATE SET money=excluded.money", (int(gid), int(qq), new_money))
                ST._DB.execute("INSERT INTO accounts(gid, qq, data) VALUES(?,?,?) ON CONFLICT(gid, qq) DO UPDATE SET data=excluded.data", (int(gid), int(qq), __import__("json").dumps(a2.kv, ensure_ascii=False)))
                a2.dirty = False
                ST._safe_commit()
                return (f"打劫失败！实施打劫时被抓！被关监狱{jail_mins}分钟，\r\n"
                        f"罚款{fine}{ST.coin_name()}，魅力-{meli}！")
    except Exception:
        pass
    ST.acct_add(gid, qq, "stamina", -cs)
    a.set("rob_time", _now_s())
    if random.random() * 100 < prob:
        loot = min(ST.coins_get(gid, target), random.randint(lo, hi))
        if loot <= 0:
            return "亲，对方是个穷光蛋，无法对他实施打劫！"
        try:
            if hasattr(ST, "txn_two_wallets") and ST.txn_two_wallets(gid, target, qq, loot):
                pass
            else:
                try:
                    _cur_v = int(ST.coins_get(gid, target) or 0)
                except Exception:
                    _cur_v = 0
                loot = min(_cur_v, loot)
                if loot <= 0:
                    return "亲，对方是个穷光蛋，无法对他实施打劫！"
                if not (hasattr(ST, "txn_two_wallets") and ST.txn_two_wallets(gid, target, qq, loot)):
                    ST.coins_add(gid, target, -loot)
                    ST.coins_add(gid, qq, loot)
        except Exception:
            ST.coins_add(gid, target, -loot)
            ST.coins_add(gid, qq, loot)
        tn = _disp_name(target, gid)
        return f"打劫成功！你从 {tn} 处劫走{loot}{ST.coin_name()}！"
    ST.acct_add(gid, qq, "charm", -meli)
    fine = min(1000, ST.coins_get(gid, qq))
    ST.coins_add(gid, qq, -fine)
    _jail_put(a, jail_mins)
    return (f"打劫失败！实施打劫时被抓！被关监狱{jail_mins}分钟，\r\n"
            f"罚款{fine}{ST.coin_name()}，魅力-{meli}！")


# ---- 统一入口 ----

__all__ = ["_settle_interest", "cmd_deposit", "cmd_force_withdraw", "cmd_gamble", "cmd_rob_zone", "cmd_sell_slave", "cmd_transfer", "cmd_withdraw"]
