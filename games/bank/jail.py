# -*- coding: utf-8 -*-
"""games/bank·jail（原 bank.py 切分，语义不变）。"""
import datetime as dt
import random
import time
try:
    from ... import storage as ST
except ImportError:
    import storage as ST
from .common import *  # noqa
def _jail_stamp(a):
    a.set("jail", "1")
    a.set("jail_start", _now_s())




def _jail_release(a):
    a.set("jail", "0")
    a.set("jail_start", "")
    a.set("release_timestamp", "")
    a.set("escape_attempts", "0")
    a.set("escape_timestamp", "")




def _jail_exp(a):
    try:
        return float(a.get("release_timestamp", "0") or "0")
    except Exception:
        return 0.0




def _check_jail(a):
    """返回是否仍在狱中; 若已到期自动释放"""
    if a.get("jail") != "1":
        return False
    if time.time() >= _jail_exp(a) and _jail_exp(a) > 0:
        _jail_release(a)
        ST.acct_save(a.gid, a.qq)
        return False
    return True




def _jail_left(a):
    left = _jail_exp(a) - time.time()
    return int(left / 60) + 1 if left > 0 else 0




def _jail_put(a, mins):
    """判刑入狱 mins 分钟"""
    _jail_stamp(a)
    a.set("release_timestamp", str(int(time.time()) + int(mins) * 60))
    ST.acct_save(a.gid, a.qq)




def _show_jail(a):
    if not _check_jail(a):
        return "亲，您现在已经是自由身了！什么？还想到监狱里过把瘾？那就去打劫或者赌博吧！"
    left = _jail_left(a)
    return (f"你现在还是好好待监狱里吧！想要出来？发送【我要出狱】试试！\r\n"
            f"距离出狱时间还剩{left}分钟，等不了这么久？\r\n"
            f"你可以铤险越狱，发送【我要越狱】！也可以花钱消灾保释自己，发送【自我保释】！\r\n"
            f"还可以向好友求助！")


# ---- 转账目标解析辅助 ----


def _bail_name(tid, gid=None):
    try:
        from .. import slave as SL
        if gid:
            try:
                nm = SL.get_note_name(gid, str(tid)) or SL.fetch_card(gid, str(tid))
                if nm:
                    return nm
            except Exception:
                pass
        return SL.NOTE_NAMES.get(str(tid), str(tid)) if not gid or gid == "dm" else str(tid)
    except Exception:
        return str(tid)




def cmd_bail(gid, qq, target, self_bail=False, kind="保释"):
    """保释/自我保释/劫狱(替他人出狱) 劫狱免费，保释收费"""
    if self_bail or str(target).strip() in ("自己", str(qq)):
        self_bail = True
        tid = qq
    else:
        tid = target
        if not tid:
            return f"请指定{kind}目标，格式：【{kind} @QQ】"
    a = _acct(gid, qq)
    ta = _acct(gid, tid)
    if not _check_jail(ta):
        return f"对方({_bail_name(tid, gid)})没有入狱，不需要{kind}！"
    if not self_bail and _check_jail(a):
        return "你自己都蹲在监狱里了，拿什么解救别人？？发送【我要出狱】试试！"
    # 劫狱免费，仅需少量体力；保释收费
    if kind == "劫狱":
        fee = 0
        tili = ST.cfgi("银行配置", "劫狱消耗体力", 5)
        meli = ST.cfgi("银行配置", "劫狱魅力减少", 0)
        # 劫狱有独立冷却
        ok, mins = _cd(a, "jailbreak_time", ST.cfgi("银行配置", "劫狱间隔", 5))
        if not ok:
            return f"{mins}分钟后再来劫狱吧！"
        a.set("jailbreak_time", _now_s())
    else:
        fee_lo = ST.cfgi("银行配置", "保释金钱下限", 5000)
        fee_hi = ST.cfgi("银行配置", "保释金钱上限", 10000)
        fee = random.randint(fee_lo, fee_hi) if fee_hi > fee_lo else fee_lo
        tili = ST.cfgi("银行配置", "保释消耗体力", 15)
        meli = ST.cfgi("银行配置", "保释魅力减少", 20)
    if fee and ST.coins_get(gid, qq) < fee:
        return f"亲，您的{ST.coin_name()}不足，无法{kind}！{kind}金需要{fee}{ST.coin_name()}！"
    if tili and a.int("stamina") < tili:
        return f"亲，您的体力不足，无法{kind}！{kind}需要{tili}体力！"
    if fee:
        ST.coins_add(gid, qq, -fee)
    if tili:
        ST.acct_add(gid, qq, "stamina", -tili)
    if meli:
        ST.acct_add(gid, qq, "charm", -meli)
    _jail_release(ta)
    ST.acct_save(gid, qq)
    if self_bail:
        return (f"保释成功！花费{fee}{ST.coin_name()}、{tili}体力，魅力-{meli}。\r\n"
                "你现在可以出狱了！希望你以后能够洗心革面，多做好事别犯罪！")
    if kind == "劫狱":
        cost_txt = f"花费{fee}{ST.coin_name()}、{tili}体力" if fee or tili else "无消耗"
        meli_txt = f"魅力-{meli}" if meli else ""
        return (f"劫狱成功！{cost_txt} {meli_txt}\r\n"
                f"成功救出 <{_bail_name(tid, gid)}>！侠义之举，令人敬佩！")
    return (f"保释成功！花费{fee}{ST.coin_name()}、{tili}体力，魅力-{meli}。\r\n"
            f"<{_bail_name(tid, gid)}> 现在可以出狱了！")




def cmd_out_jail(gid, qq):
    """我要出狱: 到期自动释放 → 自由身; 未到期 → 提示剩余刑期/越狱/保释"""
    a = _acct(gid, qq)
    if not _check_jail(a):
        return "恭喜！您的刑期已满，现在是自由身了，希望你以后能够洗心革面，多做好事别犯罪！\r\n什么？还想到监狱里过把瘾？那就去打劫或者赌博吧！"
    left = _jail_left(a)
    return (f"距离出狱时间还剩{left}分钟，等不了这么久？\r\n"
            f"你可以铤险越狱，发送【我要越狱】！也可以花钱消灾保释自己，发送【自我保释】！\r\n"
            f"还可以向好友求助(【劫狱 @QQ】)！")




def cmd_jailbreak(gid, qq):
    """我要越狱: 15秒间隔，单次牢狱最多10次，失败不加刑期"""
    a = _acct(gid, qq)
    if not _check_jail(a):
        return "您现在已经是自由身了，无需越狱！"
    # 15秒间隔
    last = a.get("escape_timestamp", "")
    try:
        if last and time.time() - float(last) < 15:
            left = int(15 - (time.time() - float(last))) + 1
            return f"越狱操作太频繁，请{left}秒后再试！"
    except Exception:
        pass
    # 单次牢狱最多10次
    cnt = int(a.get("escape_attempts", "0") or "0")
    if cnt >= 10:
        return "本轮牢狱越狱次数已达10次上限，请等待刑满或寻求保释/劫狱！"
    tili = ST.cfgi("银行配置", "越狱消耗体力", 5)
    meli = ST.cfgi("银行配置", "越狱魅力减少", 5)
    prob = ST.cfgi("银行配置", "越狱成功概率", 25)
    if a.int("stamina") < tili:
        return f"亲，您的体力不足，无法越狱！越狱需要{tili}体力！"
    ST.acct_add(gid, qq, "stamina", -tili)
    a.set("escape_timestamp", str(time.time()))
    a.set("escape_attempts", str(cnt + 1))
    if random.random() * 100 < prob:
        _jail_release(a)
        a.set("escape_attempts", "0")
        ST.acct_save(gid, qq)
        return f"越狱成功！扣除{tili}体力，你重获自由~"
    ST.acct_add(gid, qq, "charm", -meli)
    # 失败不加刑期（需求33）
    ST.acct_save(gid, qq)
    return f"越狱失败！扣除{tili}体力，魅力-{meli}，未增加刑期，再接再厉！"




def cmd_go_jail(gid, qq):
    """我要进监狱: 主动入狱10分钟，增加体力，每日限N次（银行配置.进监狱次数）"""
    a = _acct(gid, qq)
    if _check_jail(a):
        return "您已在监狱中，无需再次入狱！"
    key = f"jailgo_{gid}_{qq}_{dt.date.today()}"
    cnt = int(ST.recall_get(key, "0") or 0)
    lim = ST.cfgi("银行配置", "进监狱次数", 8)
    if lim <= 0:
        lim = 8
    if cnt >= lim:
        return f"亲，您今日主动入狱次数已达上限({lim}次)！"
    add_stam = ST.cfgi("银行配置", "进监狱增加体力", 10)
    if add_stam <= 0:
        add_stam = 10
    _jail_put(a, 10)
    ST.acct_add(gid, qq, "stamina", add_stam)
    ST.recall_set(key, str(cnt + 1))
    ST.acct_save(gid, qq)
    left = 10
    return f"成功入狱{left}分钟！获得{add_stam}点体力，今日已入狱{cnt+1}/{lim}次，好好反省吧！"



__all__ = ["_bail_name", "_check_jail", "_jail_exp", "_jail_left", "_jail_put", "_jail_release", "_jail_stamp", "_show_jail", "cmd_bail", "cmd_go_jail", "cmd_jailbreak", "cmd_out_jail"]
