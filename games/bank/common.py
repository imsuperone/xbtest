# -*- coding: utf-8 -*-
"""games/bank·ctx（原 bank.py 切分，语义不变）。"""
import datetime as dt
import re
import time
try:
    from ...core import storage as ST
except ImportError:
    from core import storage as ST


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
        nm = ""
        if nm and nm.strip():
            return nm
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
def _resolve_qq_from_name(name, gid=None):
    """通过分群昵称反查 qq (name -> qq)，优先本群（防跨群串扰）"""
    name = str(name).strip()
    if not name:
        return None
    # 优先本群分群昵称反向索引（精确 O(1)，模糊限本群）
    if gid:
        try:
            from .. import slave as SL0
            if hasattr(SL0, "find_qq_by_name"):
                _q0 = SL0.find_qq_by_name(gid, name)
                if _q0:
                    return str(_q0)
        except Exception:
            pass
    # via ST._AT_NAMES
    try:
        qq = ST._AT_NAMES.get(name)
        if qq:
            return str(qq)
    except Exception:
        pass
    # via slave module
    try:
        from .. import slave as SL
        for qq_, nm_ in getattr(SL, "NOTE_NAMES", {}).items():
            if str(nm_).strip() == name:
                return str(qq_)
    except Exception:
        pass
    try:
        import slave as SL2
        for qq_, nm_ in getattr(SL2, "NOTE_NAMES", {}).items():
            if str(nm_).strip() == name:
                return str(qq_)
    except Exception:
        pass
    return None




def _extract_transfer_target(raw, gid=None):
    """鲁棒解析 @目标: 顺序: ST.parse_at -> CQ码 -> @QQ数字 -> @名字查 slave.NOTE_NAMES -> 纯QQ字符串
    返回 (target_qq_or_None, remaining_text)
    """
    raw = str(raw or "")
    # 1) ST.parse_at
    try:
        t, rem = ST.parse_at(raw)
        if t:
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
    # 4) @name via slave.NOTE_NAMES
    m = re.search(r"@\s*([^@\s，,]+)", raw)
    if m:
        name = m.group(1).strip()
        qq = _resolve_qq_from_name(name, gid)
        if qq:
            rem = re.sub(r"@\s*[^@\s，,]+", "", raw, count=1).strip()
            return str(qq), rem
    # 5) 纯QQ字符串兜底 (由调用方决定是否使用，这里也尝试返回以兼容)
    # 仅当 raw 中包含独立的 5-12位数字且没有@时，视为候选
    m = re.search(r"\b(\d{5,12})\b", raw)
    if m:
        # 调用方会在 handle 中对转账等指令再启用此兜底；这里返回供 cmd_transfer 内部使用
        # 保持返回但不强制去除，避免误伤金额；只在明确需要时使用
        pass
    return None, raw.strip()




def _ensure_target_qq(target, gid=None):
    """cmd_transfer 内部兜底: 将各种形式的 target 转为纯QQ号"""
    if target is None:
        return None
    s = str(target).strip()
    if re.fullmatch(r"\d{5,12}", s):
        return s
    # 尝试 ST.parse_at
    try:
        t, _ = ST.parse_at(s)
        if t and re.fullmatch(r"\d{5,12}", str(t)):
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
    # @name
    m = re.search(r"@\s*([^@\s，,]+)", s)
    if m:
        qq = _resolve_qq_from_name(m.group(1).strip(), gid)
        if qq:
            return qq
        # also try direct name without @
        qq = _resolve_qq_from_name(s.lstrip("@").strip(), gid)
        if qq:
            return qq
    else:
        # 直接名字 (无@)
        qq = _resolve_qq_from_name(s, gid)
        if qq:
            return qq
        # 纯QQ字符串
        m2 = re.search(r"\b(\d{5,12})\b", s)
        if m2:
            return m2.group(1)
    return s



__all__ = ["_MENU", "_acct", "_cd", "_disp_name", "_ensure_target_qq", "_extract_transfer_target", "_now_s", "_resolve_qq_from_name"]
