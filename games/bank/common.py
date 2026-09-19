# -*- coding: utf-8 -*-
"""games/bank·ctx（原 bank.py 切分，语义不变）。"""
import datetime as dt
import re
import time
try:
    from ...core import storage as ST
except ImportError:
    from core import storage as ST
try:
    from ..config.bank import DEFAULTS as _BANK_DEFAULTS
except ImportError:
    try:
        from games.config.bank import DEFAULTS as _BANK_DEFAULTS  # type: ignore
    except Exception:
        _BANK_DEFAULTS = {}


try:
    from ..config.bank import (GAMBLE_MULT, REDPACK_MIN_DIV, REDPACK_MAX_DIV)
except ImportError:
    from games.config.bank import (GAMBLE_MULT, REDPACK_MIN_DIV, REDPACK_MAX_DIV)  # type: ignore


def cfgi(sec, key, default=0):
    # 默认值单源：games/config/bank.py DEFAULTS 表命中即用表值（行内兜底仅动态键时生效）
    try:
        if (sec, key) in _BANK_DEFAULTS:
            default = _BANK_DEFAULTS[(sec, key)]
    except Exception:
        pass
    return ST.cfgi(sec, key, default)


def _disp_name(qq, gid=None):
    """取群昵称显示(优先本群分群昵称，其次本群档案 name)，失败回退 QQ（绝不串别群）"""
    qq = str(qq)
    # 本群分群昵称
    try:
        from .. import slave as SL
        try:
            nm = SL.get_note_name(gid, qq) if gid and hasattr(SL, "get_note_name") else ""
        except Exception:
            nm = ""
        if nm and nm.strip():
            return nm
        if gid:
            try:
                nm2 = SL.fetch_card(str(gid), qq) or ""
                if nm2 and nm2.strip():
                    return nm2
            except Exception:
                pass
        if gid:
            try:
                st = SL.state(str(gid))
                if st.has_section(qq):
                    n2 = SL.uname(st, qq)
                    if n2 and n2 != qq:
                        return n2
            except Exception:
                pass
    except Exception:
        pass
    try:
        import slave as SL2
        try:
            nm = SL2.get_note_name(gid, qq) if gid and hasattr(SL2, "get_note_name") else ""
        except Exception:
            nm = ""
        if nm and nm.strip():
            return nm
        if gid:
            try:
                st = SL2.state(str(gid))
                if st.has_section(qq):
                    n2 = SL2.uname(st, qq)
                    if n2 and n2 != qq:
                        return n2
            except Exception:
                pass
    except Exception:
        pass
    return qq




def _acct(gid, qq):
    return ST.acct(gid, qq)




_MENU = (
    "🏦 银行系统\r\n"
    "━━━━━━━━━━━━━━\r\n"
    "💵 存款 金额　　　　取款 金额\r\n"
    "⏰ 强制取款 金额\r\n"
    "🔁 转账 @QQ 金额\r\n"
    "🧧 发红包 金额　　　抢红包 口令\r\n"
    "🎰 赌博 金额　　　　打劫 @QQ\r\n"
    "🏦 打劫银行\r\n"
    "⛓️ 我要出狱　我要越狱　自我保释\r\n"
    "🤝 劫狱 @QQ　💸 保释 @QQ\r\n"
    "⛓️ 我要进监狱\r\n"
    "━━━━━━━━━━━━━━\r\n"
    "💡 发送对应指令即可游玩"
)




def _now_s():
    return dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")




def _cd(a, key, mins):
    last = a.get(key)
    if last:
        try:
            # 快路：epoch整数或手动拆分，避免 strptime 正则开销
            ts = None
            if last.isdigit():
                ts = int(last)
            else:
                try:
                    # "YYYY-MM-DD HH:MM:SS" 手动解析
                    dpart, tpart = last.split(" ")
                    y, mo, d = dpart.split("-")
                    h, mi, s = tpart.split(":")
                    ts = time.mktime((int(y), int(mo), int(d), int(h), int(mi), int(s), 0, 0, -1))
                except Exception:
                    t = dt.datetime.strptime(last, "%Y-%m-%d %H:%M:%S")
                    ts = t.timestamp()
            left = mins * 60 - (time.time() - ts)
            if left > 0:
                return False, int(left / 60) + 1
        except Exception:
            pass
    return True, 0


# ---- 监狱(入狱/出狱) ----
def _extract_transfer_target(raw, gid=None):
    """QQ-only 解析 @目标: 顺序 ST.parse_at(仅认 CQ/@数字/独立数字) -> CQ码 -> @QQ数字。
    @昵称一律不认（防撞名串人）。返回 (target_qq_or_None, remaining_text)。"""
    raw = str(raw or "")
    # 1) ST.parse_at（命中后必须过 QQ-only 校验，否则视为未命中继续直解）
    try:
        t, rem = ST.parse_at(raw)
        if t:
            try:
                _ok = ST.is_qq_mention(t, raw) if hasattr(ST, "is_qq_mention") else True
            except Exception:
                _ok = True
            if _ok:
                return str(t), rem.strip()
    except Exception:
        pass
    # 2) CQ code
    m = re.search(r"\[CQ:at,qq=(\d+)[^\]]*\]", raw)
    if m:
        rem = re.sub(r"\[CQ:at,qq=\d+[^\]]*\]", "", raw).strip()
        return m.group(1), rem
    # 3) @QQ number
    m = re.search(r"@\s*(\d{5,12})", raw)
    if m:
        rem = re.sub(r"@\s*\d{5,12}", "", raw, count=1).strip()
        return m.group(1), rem
    # 4) 纯QQ字符串兜底由调用方按指令启用（防金额误判），此处不解
    return None, raw.strip()




def _ensure_target_qq(target, gid=None):
    """cmd_transfer 内部兜底: QQ-only，只认纯QQ / CQ码 / @QQ数字 / 独立数字串，不认昵称"""
    if target is None:
        return None
    s = str(target).strip()
    if re.fullmatch(r"\d{5,12}", s):
        return s
    # 尝试 ST.parse_at（命中须过 QQ-only 校验）
    try:
        t, _ = ST.parse_at(s)
        if t and re.fullmatch(r"\d{5,12}", str(t)):
            try:
                _ok = ST.is_qq_mention(t, s) if hasattr(ST, "is_qq_mention") else True
            except Exception:
                _ok = True
            if _ok:
                return str(t)
    except Exception:
        pass
    # CQ
    m = re.search(r"\[CQ:at,qq=(\d+)[^\]]*\]", s)
    if m:
        return m.group(1)
    # @QQ
    m = re.search(r"@\s*(\d{5,12})", s)
    if m:
        return m.group(1)
    # 纯QQ字符串
    m2 = re.search(r"\b(\d{5,12})\b", s)
    if m2:
        return m2.group(1)
    # 解不出返 None（调用方均判空）：禁返原文，否则按 QQ 建幻影账户吞钱
    return None



__all__ = ["_MENU", "_acct", "_cd", "_disp_name", "_ensure_target_qq", "_extract_transfer_target", "_now_s", "cfgi", "GAMBLE_MULT", "REDPACK_MIN_DIV", "REDPACK_MAX_DIV"]
