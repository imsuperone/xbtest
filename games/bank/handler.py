# -*- coding: utf-8 -*-
"""games/bank·route（原 bank.py 切分，语义不变）。"""
import re
try:
    from ...core import storage as ST
except ImportError:
    from core import storage as ST
from .common import *  # noqa
from .jail import *  # noqa
from .redpack import *  # noqa
from .transactions import *  # noqa
def handle(gid, qq, raw):
    text = (raw or "").strip()
    if not text:
        return None
    if text in ST.wake("银行系统", "银行系统"):
        return _MENU
    # 鲁棒转账目标解析: 依次尝试 ST.parse_at -> CQ -> @QQ数字 -> @名字 -> 纯QQ
    target = None
    t1, r1 = _extract_transfer_target(text, gid)
    if t1:
        target = t1
        text = r1
    else:
        # 纯QQ字符串兜底 (仅对需要目标的指令)
        if any(text.startswith(p) for p in ("转账", "打劫", "劫狱", "保释")):
            m = re.search(r"\b(\d{5,12})\b", text)
            if m:
                target = m.group(1)
                text = text.replace(m.group(0), "", 1).strip()
        # 同时兼容 @昵称 形式的数字后剩余文本已由 _extract_transfer_target 处理

    # 若目标已提取但 text 仍包含“转账”前缀，保留以便后续命令判断
    n = 0
    mms = re.findall(r"(\d+)", text)
    if mms:
        n = int(mms[-1])

    if text.startswith("存款"):
        return cmd_deposit(gid, qq, n)
    if text.startswith("强制取款"):
        return cmd_force_withdraw(gid, qq, n)
    if text.startswith("取款"):
        return cmd_withdraw(gid, qq, n)
    if text.startswith("转账"):
        if not target:
            return "请指定转账目标，格式：【转账 @QQ 金额】"
        return cmd_transfer(gid, qq, target, n)

    if text.startswith("赌博"):
        return cmd_gamble(gid, qq, n)
    if text.startswith("打劫银行"):
        return cmd_rob_zone(gid, qq)
    if text.startswith("打劫"):
        return cmd_sell_slave(gid, qq, target)
    if text.startswith("发红包"):
        rest = text[3:].strip()
        parts = re.split(r"\s+", rest)
        amt_s = parts[0] if parts else ""
        m_amt = re.search(r"(\d+)", amt_s)
        pwd = " ".join(parts[1:]) if len(parts) > 1 else None
        if not m_amt:
            return "亲，发红包格式为：【发红包 金额】或【发红包 金额 口令】！"
        return cmd_redpack(gid, qq, int(m_amt.group(1)), pwd)
    if text.startswith("抢红包"):
        pwd = text[3:].strip()
        if not pwd:
            # 兼容 “抢红包 口令” 中间多空格
            pwd = re.sub(r"^抢红包\s*", "", raw or "").strip()
        return cmd_recv_red(gid, qq, pwd)
    if text in ("我要进监狱", "进监狱"):
        return cmd_go_jail(gid, qq)
    if text in ("我要出狱", "出狱"):
        return cmd_out_jail(gid, qq)
    if text in ("我要越狱", "越狱"):
        return cmd_jailbreak(gid, qq)
    if text.startswith("劫狱"):
        return cmd_bail(gid, qq, target or text[2:].strip(), kind="劫狱")
    if text.startswith("保释"):
        return cmd_bail(gid, qq, target or text[2:].strip())
    if text.startswith("自我保释"):
        return cmd_bail(gid, qq, qq, self_bail=True)
    # 隐式红包口令再兜底(处理 raw 中无前缀但包含口令的情况)
    try:
        if raw and ST._DB is not None:
            cand = (raw or "").strip()
            # 去除可能的 CQ 码后剩余纯口令
            cand = re.sub(r"\[CQ:[^\]]+\]", "", cand).strip()
            if cand and len(cand) <= 10 and not (cand.isdigit() and len(cand) <= 2):
                with ST._LOCK:
                    row = ST._DB.execute("SELECT pwd FROM redpacks WHERE gid=? AND pwd=?", (int(gid), cand)).fetchone()
                if row:
                    return cmd_recv_red(gid, qq, cand)
    except Exception:
        pass
    return None

__all__ = ["handle", "COMMANDS", "WAKE", "can_handle"]


COMMANDS = (
    "存款", "强制取款", "取款", "转账", "赌博", "打劫银行", "打劫",
    "发红包", "抢红包", "劫狱", "保释", "自我保释",
    "进监狱", "出狱", "越狱",
)
WAKE = "银行系统"


def can_handle(gid, qq, raw):
    try:
        rt_n = str(raw or "").strip().replace(" ", "")
        for c in COMMANDS:
            if c and rt_n.startswith(str(c).replace(" ", "")):
                return True
    except Exception:
        pass
    return False
