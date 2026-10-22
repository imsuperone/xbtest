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

# 预编译高频正则模式
_RE_QQ_DIGITS = re.compile(r"(?:@)?(\d{5,12})")
_RE_AT_NAME = re.compile(r"@\s*(\S+)")
_RE_AT_CLEAN = re.compile(r"@\s*\S+")
_RE_MULTI_SPACE = re.compile(r"\s+")
_RE_NUMS = re.compile(r"(-?\d+)")
_RE_DIGITS = re.compile(r"(\d+)")
_RE_DEPOSIT_CMD = re.compile(r"存款\s*(-?\d+)\s*(?:金币|元|点)?")
_RE_WITHDRAW_CMD = re.compile(r"取款\s*(-?\d+)\s*(?:金币|元|点)?")
_RE_GAMBLE_CMD = re.compile(r"赌博\s*(\d+)")
_RE_RECV_RED_PREFIX = re.compile(r"^抢红包\s*")
_RE_CQ_AT = re.compile(r"(?:\[CQ:at,qq=(\d+)[^\]]*\]|\[At:\s*(\d+)\])")
_RE_COIN_SUFFIX = r"(?:金币|金|币|元|点)"


def _parse_transfer_cmd(text, raw, gid):
    """
    全面兼容用户转账指令语法：
    1. 转账QQ号 金额 / 转账 QQ号 金额（指令与QQ号之间可无空格）
    2. 转账QQ号金 金额 / 转账 QQ号金 金额（QQ号后带金/币后缀）
    3. 转账@QQ 金额 / 转账 @QQ 金额（指令与@之间可无空格）
    4. 转账 金额 @QQ / 转账 金额 QQ号（金额在前、目标在后）
    5. 金额后可带金/币后缀（如 100金、100金币、100元）
    6. 支持群内 @昵称 反查
    返回 (target_qq, amount, error_msg_or_None)
    """
    s = (raw or text or "").strip()
    if not s.startswith("转账"):
        return None, None, None
    tail = s[2:].strip()
    if not tail or tail in ("?", "？", "帮助", "help"):
        return None, 0, "提示：转账格式为【转账 @目标 金额】或【转账 QQ号 金额】，例如：转账 123456789 100"

    target = None
    amt = None

    # 1. 尝试匹配 CQ 码 / [At:QQ]
    m_cq = _RE_CQ_AT.search(tail)
    if m_cq:
        target = m_cq.group(1) or m_cq.group(2)
        tail = _RE_CQ_AT.sub(" ", tail).strip()

    # 2. 优先尝试提取末尾金额（支持带任意 @昵称、富文本标记 <%...%> 或尖括号的目标）
    # 例如："@A-◣fax小翠◥.Tcui<%ĀĀÖ> 1" 或 "@某人 100"
    m_end_amt = re.search(r"\s+(-?\d+)\s*(?:金币|金|币|元|点)?$", tail)
    if m_end_amt:
        try:
            cand_amt = int(m_end_amt.group(1))
        except Exception:
            cand_amt = 0
        target_part = tail[:m_end_amt.start()].strip()
        if not target and target_part:
            cq_in = _RE_CQ_AT.search(target_part)
            if cq_in:
                target = cq_in.group(1) or cq_in.group(2)
            else:
                clean_target = re.sub(r"<%.*?%>", "", target_part)
                clean_target = re.sub(r"<[^>]+>", "", clean_target).lstrip("@").strip()
                clean_target = re.sub(r"(?:" + _RE_COIN_SUFFIX + r")$", "", clean_target).strip()
                if clean_target.isdigit() and 5 <= len(clean_target) <= 12:
                    target = clean_target
                else:
                    t_cand = _find_qq_by_name(gid, target_part) or _find_qq_by_name(gid, clean_target)
                    if t_cand:
                        target = t_cand
        if target:
            return target, cand_amt, None

    # 3. 尝试匹配 @QQ 或 @昵称
    if not target and "@" in tail:
        m_at_qq = re.search(r"@\s*(\d{5,12})(?:" + _RE_COIN_SUFFIX + r")?", tail)
        if m_at_qq:
            target = m_at_qq.group(1)
            tail = re.sub(r"@\s*\d{5,12}(?:" + _RE_COIN_SUFFIX + r")?", " ", tail, count=1).strip()
        else:
            m_at_nick = re.search(r"@\s*(\S+)", tail)
            if m_at_nick:
                cand = m_at_nick.group(1).strip()
                cand_clean = re.sub(r"<%.*?%>", "", cand)
                cand_clean = re.sub(r"<[^>]+>", "", cand_clean).strip()
                t_cand = _find_qq_by_name(gid, cand) or _find_qq_by_name(gid, cand_clean)
                if t_cand:
                    target = t_cand
                    tail = re.sub(r"@\s*\S+", " ", tail, count=1).strip()

    # 如果此时已提取 target，tail 剩余部分提取金额
    if target:
        tail = re.sub(r"\s+", " ", tail).strip()
        m_amt = re.search(r"(-?\d+)", tail)
        if m_amt:
            try:
                amt = int(m_amt.group(1))
            except Exception:
                amt = 0
            return target, amt, None
        return target, 0, f"提示：请输入转账金额，例如：转账 {target} 100"

    # 3. 纯文本模式：目标在前，金额在后
    # 例如："123456789 100", "123456789金 100", "123456789 100金", "123456789金100"
    m_front = re.match(r"^(\d{5,12})(?:" + _RE_COIN_SUFFIX + r")?\s*(-?\d+)(?:" + _RE_COIN_SUFFIX + r")?$", tail)
    if m_front:
        target = m_front.group(1)
        try:
            amt = int(m_front.group(2))
        except Exception:
            amt = 0
        return target, amt, None

    # 模式B: 金额在前，目标在后
    # 例如："100 123456789", "100金 123456789", "100 123456789金"
    m_back = re.match(r"^(-?\d+)(?:" + _RE_COIN_SUFFIX + r")?\s+(\d{5,12})(?:" + _RE_COIN_SUFFIX + r")?$", tail)
    if m_back:
        try:
            amt = int(m_back.group(1))
        except Exception:
            amt = 0
        target = m_back.group(2)
        return target, amt, None

    # 模式C: 两个数字或群昵称
    parts = re.split(r"\s+", tail)
    if len(parts) >= 2:
        p0_clean = re.sub(r"^@|(?:" + _RE_COIN_SUFFIX + r")$", "", parts[0]).strip()
        p1_clean = re.sub(r"^@|(?:" + _RE_COIN_SUFFIX + r")$", "", parts[-1]).strip()
        if re.fullmatch(r"\d{5,12}", p0_clean) and re.fullmatch(r"-?\d+", p1_clean):
            return p0_clean, int(p1_clean), None
        if re.fullmatch(r"-?\d+", p0_clean) and re.fullmatch(r"\d{5,12}", p1_clean):
            return p1_clean, int(p0_clean), None
        t_cand = _find_qq_by_name(gid, parts[0])
        if t_cand and re.fullmatch(r"-?\d+", p1_clean):
            return t_cand, int(p1_clean), None

    nums = re.findall(r"(\d+)", tail)
    if len(nums) == 1:
        val = nums[0]
        if len(val) >= 5:
            return val, 0, f"提示：请输入转账金额，例如：转账 {val} 100"
        return None, int(val), f"提示：请指定转账目标QQ，例如：转账 123456789 {val}"

    return None, 0, "提示：转账格式为【转账 @目标 金额】或【转账 QQ号 金额】，例如：转账 123456789 100"


def handle(gid, qq, raw):
    text = (raw or "").strip()
    if not text:
        return None
    if text in ST.wake("银行系统", "银行系统"):
        return _MENU

    # 优先精确解析跨群转账与普通转账，全面兼容有无空格、@前缀、金/币后缀
    if text.startswith("跨群转账"):
        _raw_ct = text[4:]
        if not _raw_ct or _raw_ct[:1].isspace() or _raw_ct[:1].isdigit():
            nums = _RE_DIGITS.findall(text)
            if len(nums) < 2:
                return "亲，跨群转账格式为：【跨群转账 群号 金额】！"
            return cmd_cross_transfer(gid, qq, nums[0], int(nums[-1]))
        return None

    if text.startswith("转账"):
        target_t, amt_t, err_t = _parse_transfer_cmd(text, raw, gid)
        if err_t:
            return err_t
        if not target_t:
            return "提示：转账格式为【转账 @目标 金额】或【转账 QQ号 金额】，例如：转账 123456789 100"
        return cmd_transfer(gid, qq, target_t, amt_t)

    # QQ/Nickname 目标解析: CQ -> @QQ数字 -> @昵称 -> 纯QQ (供存款/取款/打劫/劫狱/保释使用)
    target = None
    t1, r1 = _extract_transfer_target(text, gid)
    if t1:
        target = t1
        text = r1
    else:
        # 纯QQ/纯昵称字符串兜底 (仅对需要目标的指令)
        if any(text.startswith(p) for p in ("打劫", "劫狱", "保释")):
            m = _RE_QQ_DIGITS.search(text)
            if m:
                target = m.group(1)
                text = text.replace(m.group(0), "", 1).strip()
            elif "@" in text:
                m_at = _RE_AT_NAME.search(text)
                if m_at:
                    cand = m_at.group(1).strip()
                    t_cand = _find_qq_by_name(gid, cand)
                    if t_cand:
                        target = t_cand
                        text = _RE_AT_CLEAN.sub("", text).strip()

    if target:
        text = _RE_AT_CLEAN.sub("", text).strip()
        text = _RE_MULTI_SPACE.sub(" ", text).strip()

    n = 0
    mms = _RE_NUMS.findall(text)
    if mms:
        try:
            n = int(mms[-1])
        except Exception:
            n = 0

    if text.startswith("存款"):
        if text in ("存款全部", "存款所有"):
            return cmd_deposit(gid, qq, ST.coins_get(gid, qq))
        if text == "存款" or _RE_DEPOSIT_CMD.fullmatch(text):
            return cmd_deposit(gid, qq, n)
        return "提示：存款指令格式为【存款 金额】，例如：存款 1000"
    if text.startswith("取款"):
        if text in ("取款全部", "取款所有"):
            return cmd_withdraw(gid, qq, _acct(gid, qq).int("deposit"))
        if text == "取款" or _RE_WITHDRAW_CMD.fullmatch(text):
            return cmd_withdraw(gid, qq, n)
        return "提示：取款指令格式为【取款 金额】，例如：取款 1000"

    if text.startswith("赌博"):
        if text == "赌博" or _RE_GAMBLE_CMD.fullmatch(text):
            return cmd_gamble(gid, qq, n)
        return None
    if text == "打劫银行":
        return cmd_rob_zone(gid, qq)
    if text.startswith("打劫"):
        _rest = text[2:].strip()
        _rest_clean = _RE_AT_CLEAN.sub("", _rest).strip()
        if not _rest or _rest.startswith("@") or not _rest_clean:
            return cmd_sell_slave(gid, qq, target)
        return None
    if text.startswith("发红包"):
        rest = text[3:].strip()
        if not rest:
            return "亲，发红包格式为：【发红包 金额】或【发红包 金额 口令】！"
        parts = _RE_MULTI_SPACE.split(rest)
        amt_s = parts[0] if parts else ""
        m_amt = _RE_DIGITS.fullmatch(amt_s)
        pwd = " ".join(parts[1:]) if len(parts) > 1 else None
        if not m_amt:
            return None
        return cmd_redpack(gid, qq, int(m_amt.group(1)), pwd)
    if text.startswith("抢红包"):
        raw_tail = text[3:]
        pwd = raw_tail.strip()
        if not pwd:
            pwd = _RE_RECV_RED_PREFIX.sub("", raw or "").strip()
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
