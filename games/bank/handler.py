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
    # QQ/Nickname 转账目标解析: CQ -> @QQ数字 -> @昵称 -> 纯QQ
    target = None
    t1, r1 = _extract_transfer_target(text, gid)
    if t1:
        target = t1
        text = r1
    else:
        # 纯QQ/纯昵称字符串兜底 (仅对需要目标的指令)
        if any(text.startswith(p) for p in ("转账", "打劫", "劫狱", "保释")):
            m = re.search(r"\b(\d{5,12})\b", text)
            if m:
                target = m.group(1)
                text = text.replace(m.group(0), "", 1).strip()
            elif "@" in text:
                m_at = re.search(r"@\s*(\S+)", text)
                if m_at:
                    cand = m_at.group(1).strip()
                    t_cand = _find_qq_by_name(gid, cand)
                    if t_cand:
                        target = t_cand
                        text = re.sub(r"@\s*\S+", "", text).strip()

    if target:
        text = re.sub(r"@\s*\S+", "", text).strip()
        text = re.sub(r"\s+", " ", text).strip()

    # 若目标已提取但 text 仍包含“转账”前缀，保留以便后续命令判断
    n = 0
    mms = re.findall(r"(-?\d+)", text)
    if mms:
        try:
            n = int(mms[-1])
        except Exception:
            n = 0

    if text.startswith("存款"):
        if text == "存款" or re.fullmatch(r"存款\s*(-?\d+)\s*(?:金币|元|点)?", text):
            return cmd_deposit(gid, qq, n)
        return "提示：存款指令格式为【存款 金额】，例如：存款 1000"
    if text.startswith("取款"):
        if text == "取款" or re.fullmatch(r"取款\s*(-?\d+)\s*(?:金币|元|点)?", text):
            return cmd_withdraw(gid, qq, n)
        return "提示：取款指令格式为【取款 金额】，例如：取款 1000"
    if text.startswith("跨群转账"):
        _raw_ct = text[4:]
        if not _raw_ct or _raw_ct[:1].isspace() or _raw_ct[:1].isdigit():
            nums = re.findall(r"(\d+)", text)
            if len(nums) < 2:
                return "亲，跨群转账格式为：【跨群转账 群号 金额】！"
            return cmd_cross_transfer(gid, qq, nums[0], int(nums[-1]))
        return None
    if text.startswith("转账"):
        if not target:
            return "提示：转账格式为【转账 @目标 金额】，例如：转账 @某某 100"
        return cmd_transfer(gid, qq, target, n)

    if text.startswith("赌博"):
        if text == "赌博" or re.fullmatch(r"赌博\s*(\d+)", text):
            return cmd_gamble(gid, qq, n)
        return None
    if text == "打劫银行":
        return cmd_rob_zone(gid, qq)
    if text.startswith("打劫"):
        _rest = text[2:].strip()
        _rest_clean = re.sub(r"@\S+", "", _rest).strip()
        if not _rest or _rest.startswith("@") or not _rest_clean:
            return cmd_sell_slave(gid, qq, target)
        return None
    if text.startswith("发红包"):
        rest = text[3:].strip()
        if not rest:
            return "亲，发红包格式为：【发红包 金额】或【发红包 金额 口令】！"
        parts = re.split(r"\s+", rest)
        amt_s = parts[0] if parts else ""
        m_amt = re.fullmatch(r"(\d+)", amt_s)
        pwd = " ".join(parts[1:]) if len(parts) > 1 else None
        if not m_amt:
            return None
        return cmd_redpack(gid, qq, int(m_amt.group(1)), pwd)
    if text.startswith("抢红包"):
        raw_tail = text[3:]
        pwd = raw_tail.strip()
        if not pwd:
            pwd = re.sub(r"^抢红包\s*", "", raw or "").strip()
        elif not raw_tail[:1].isspace():
            return None
        return cmd_recv_red(gid, qq, pwd)
    if text in ("我要进监狱", "进监狱"):
        return cmd_go_jail(gid, qq)
    if text in ("我要出狱", "出狱"):
        return cmd_out_jail(gid, qq)
    if text in ("我要越狱", "越狱"):
        return cmd_jailbreak(gid, qq)
    if text.startswith("劫狱"):
        _rest = text[2:].strip()
        _rest_clean = re.sub(r"@\S+", "", _rest).strip()
        if not _rest or _rest.startswith("@") or not _rest_clean:
            return cmd_bail(gid, qq, target or _rest, kind="劫狱")
        return None
    if text.startswith("保释"):
        _rest = text[2:].strip()
        _rest_clean = re.sub(r"@\S+", "", _rest).strip()
        if not _rest or _rest.startswith("@") or not _rest_clean:
            return cmd_bail(gid, qq, target or _rest)
        return None
    if text == "自我保释":
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

__all__ = ["handle", "COMMANDS"]


COMMANDS = (
    "存款", "取款", "转账", "跨群转账", "赌博", "打劫银行", "打劫",
    "发红包", "抢红包", "劫狱", "保释", "自我保释",
    "进监狱", "出狱", "越狱",
    # V8 并入：原正则刮词域（与 handle 分支对应）
    "我要进监狱", "我要出狱", "我要越狱",
)
