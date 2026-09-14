# -*- coding: utf-8 -*-
"""games/bank·redpack（原 bank.py 切分，语义不变）。"""
import json
import random
import string
import time
try:
    from ...core import storage as ST
except ImportError:
    from core import storage as ST
from .common import *  # noqa
from .jail import *  # noqa


def cmd_redpack(gid, qq, amount, pwd=None):
    """发红包: 存入口令红包, 群内抢 (对齐原版: 最小金额/消耗体力/冷却间隔)
    pwd 可选: 用户自定义口令(≤10位), 缺省为随机5位数字"""
    a = _acct(gid, qq)
    if _check_jail(a):
        return _show_jail(a)
    min_amt = cfgi("银行配置", "红包_最小金额", 2000)
    max_amt = cfgi("银行配置", "红包_最大金额", getattr(ST, "COIN_CAP", 100000000000))
    cost_tili = cfgi("银行配置", "红包_发体力", 2)
    interval = cfgi("银行配置", "红包_间隔时间", 60)
    if amount < min_amt:
        return f"亲，发红包最小金额为：{min_amt}！请输入正确格式：发红包 金额"
    if amount > max_amt:
        return f"亲，发红包最大金额为：{max_amt}！"
    if pwd:
        pwd = str(pwd).strip()
        if len(pwd) > 10:
            return "亲，红包口令最长只能10位哦~"
    if not pwd:
        pwd = "".join(random.choices(string.digits, k=5))
    last = a.int("redpack_send_time")
    if last and time.time() - last < interval:
        return f"亲，您还需休息{int(interval - (time.time() - last))}秒才能发下一个红包！"
    if ST.coins_get(gid, qq) < amount:
        return "亲，您的账户余额不足，无法发红包！"
    if a.int("stamina") < cost_tili:
        return f"体力不足，发红包需要{cost_tili}体力！"
    # 原子化：钱包+体力+红包表同锁，避免并发互删
    try:
        with ST._LOCK:
            if ST.coins_get(gid, qq) < amount:
                return "亲，您的账户余额不足，无法发红包！"
            if a.int("stamina") < cost_tili:
                return f"体力不足，发红包需要{cost_tili}体力！"
            # 复用 txn_coins_acct 思路：直接操作 DB
            # 扣钱扣体力
            row = ST._DB.execute("SELECT money FROM wallet WHERE gid=? AND qq=?", (int(gid), int(qq))).fetchone()
            cur = int(row[0]) if row else 0
            newv = cur - int(amount)
            if newv < 0:
                newv = 0
            ST._DB.execute("INSERT INTO wallet(gid, qq, money) VALUES(?,?,?) ON CONFLICT(gid, qq) DO UPDATE SET money=excluded.money", (int(gid), int(qq), newv))
            a2 = ST.acct(gid, qq)
            a2.set("stamina", str(a2.int("stamina") - cost_tili))
            a2.set("redpack_send_time", str(int(time.time())))
            ST._DB.execute("INSERT INTO accounts(gid, qq, data) VALUES(?,?,?) ON CONFLICT(gid, qq) DO UPDATE SET data=excluded.data", (int(gid), int(qq), json.dumps(a2.kv, ensure_ascii=False)))
            ST._DB.execute("DELETE FROM redpacks WHERE gid=? AND pwd=?", (int(gid), str(pwd)))
            ST._DB.execute("DELETE FROM redpacks WHERE ts < ?", (int(time.time()) - 86400,))
            ST._DB.execute("INSERT INTO redpacks(gid, qq, pwd, amount, ts) VALUES(?,?,?,?,?)",
                           (int(gid), int(qq), pwd, amount, int(time.time())))
            try:
                ST._DB.commit()
            except Exception:
                ST._safe_rollback()
                raise
            a2.dirty = False
    except Exception:
        # 先回滚 try 内未提交的半截写入；禁止非原子降级，避免双扣/增发。
        try:
            ST._safe_rollback()
        except Exception:
            pass
        # 半截缓存污染：逐出，下一次读取从数据库重载。
        try:
            if ST._DB is not None:
                ST._ACC_CACHE.pop((str(gid), str(qq)), None)
        except Exception:
            pass
        return "红包系统繁忙，红包未创建，未扣除余额和体力，请稍后重试！"
    return (f"发红包啦！发了{amount}{ST.coin_name()}点，大家快抢吧！\r\n"
            f"红包口令为：{pwd}\r\n"
            f"发送【抢红包 {pwd}】即可瓜分！")




def cmd_recv_red(gid, qq, pwd):
    pwd = str(pwd).strip()
    if not pwd:
        return "口令错误或红包不存在！"
    # 原子化抢红包：同锁内扣减剩余金额，避免通胀（中文文案不变）
    try:
        with ST._LOCK:
            row = ST._DB.execute("SELECT qq, amount FROM redpacks WHERE gid=? AND pwd=?", (int(gid), str(pwd))).fetchone()
            if not row:
                return "口令错误或红包不存在！"
            if int(row[0]) == int(qq):
                return "自己不允许抢自己的红包！"
            a = _acct(gid, qq)
            # 已抢口令多槽位（旧 redpack_code 单槽抢A再抢B后可重抢A；新 redpack_codes 管道并存，旧键同步写兼容回退）
            try:
                _grabbed = [c for c in str(a.get("redpack_codes", "") or "").split("|") if c]
            except Exception:
                _grabbed = []
            if pwd in _grabbed or a.get("redpack_code") == pwd:
                return "你已经抢过这个红包了！"
            cost_tili = cfgi("银行配置", "红包_抢体力", 1)
            gain_meili = cfgi("银行配置", "红包_抢魅力", 10)
            base_meili = cfgi("银行配置", "红包_基本魅力", 1)
            if a.int("stamina") < cost_tili:
                return f"体力不足，抢红包需要{cost_tili}体力！"
            total = int(row[1])
            if total <= 0:
                return "红包已被抢空！"
            # 按剩余金额随机瓜分，避免超过剩余
            lo = max(1, total // REDPACK_MIN_DIV)
            hi = max(1, total // REDPACK_MAX_DIV)
            if lo > total:
                lo = 1
            if hi > total:
                hi = total
            got = random.randint(lo, hi)
            if got > total:
                got = total
            # 扣体力、加金币魅力
            a.set("stamina", str(a.int("stamina") - cost_tili))
            a.set("charm", str(a.int("charm") + gain_meili + base_meili))
            try:
                _grabbed = [c for c in str(a.get("redpack_codes", "") or "").split("|") if c]
            except Exception:
                _grabbed = []
            if pwd not in _grabbed:
                _grabbed.append(pwd)
            a.set("redpack_codes", "|".join(_grabbed[-20:]))
            a.set("redpack_code", pwd)
            ST._DB.execute("INSERT INTO accounts(gid, qq, data) VALUES(?,?,?) ON CONFLICT(gid, qq) DO UPDATE SET data=excluded.data", (int(gid), int(qq), json.dumps(a.kv, ensure_ascii=False)))
            # 钱包
            row_w = ST._DB.execute("SELECT money FROM wallet WHERE gid=? AND qq=?", (int(gid), int(qq))).fetchone()
            cur = int(row_w[0]) if row_w else 0
            newv = cur + int(got)
            if newv > getattr(ST, "COIN_CAP", 100000000000):
                newv = getattr(ST, "COIN_CAP", 100000000000)
            ST._DB.execute("INSERT INTO wallet(gid, qq, money) VALUES(?,?,?) ON CONFLICT(gid, qq) DO UPDATE SET money=excluded.money", (int(gid), int(qq), newv))
            # 更新红包剩余
            remain = total - got
            if remain <= 0:
                ST._DB.execute("DELETE FROM redpacks WHERE gid=? AND pwd=?", (int(gid), str(pwd)))
            else:
                ST._DB.execute("UPDATE redpacks SET amount=? WHERE gid=? AND pwd=?", (remain, int(gid), str(pwd)))
            try:
                ST._DB.commit()
            except Exception:
                ST._safe_rollback()
                raise
            a.dirty = False
            return f"恭喜！你抢到了 {got}{ST.coin_name()}，魅力+{gain_meili + base_meili}！（剩余{remain}）"
    except Exception:
        # 主路径半截写入先回滚，否则同连接 linger＋降级双付
        try:
            ST._safe_rollback()
        except Exception:
            pass
        # 半截缓存污染：逐出，降级自带重载（158 行），防 redpack_code 误判已抢
        try:
            if ST._DB is not None:
                ST._ACC_CACHE.pop((str(gid), str(qq)), None)
        except Exception:
            pass
    return "红包系统繁忙，本次未领取成功，未扣除体力或发放奖励，请稍后重试！"



__all__ = ["cmd_recv_red", "cmd_redpack"]
