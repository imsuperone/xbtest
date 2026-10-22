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
    "🔁 转账 @QQ 金额\r\n"
    "🌍 跨群转账 群号 金额（手续费20%）\r\n"
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
                return False, ST.format_cd_time(left)
        except Exception:
            pass
    return True, 0


# ---- 监狱(入狱/出狱) ----
def _clean_user_nick(s):
    s = str(s or "").strip()
    s = re.sub(r"<%.*?%>", "", s)
    s = re.sub(r"<[^>]+>", "", s)
    s = s.lstrip("@").strip()
    return s


def _find_qq_by_name(gid, name):
    name = str(name or "").strip()
    if not name:
        return None
    clean = _clean_user_nick(name)
    targets = [n for n in (name, clean) if n]

    # 1. 尝试从 slave_state 的分群昵称与全局反查表匹配
    try:
        from ..slave import slave_state as _sl_S
        for (g, q), n in getattr(_sl_S, "NOTE_NAMES_BY_GROUP", {}).items():
            if gid is None or str(g) == str(gid):
                n_clean = _clean_user_nick(n)
                if any(t == n or t == n_clean for t in targets):
                    return str(q)
        for q, n in getattr(_sl_S, "NOTE_NAMES", {}).items():
            n_clean = _clean_user_nick(n)
            if any(t == n or t == n_clean for t in targets):
                return str(q)
    except Exception:
        pass

    # 2. 尝试从 slave ini 配置匹配
    try:
        from ..slave.nick import state as _sl_state
        if gid:
            st = _sl_state(str(gid))
            for q in st.sections():
                n = st[q].get("name", "").strip()
                n_clean = _clean_user_nick(n)
                if any(t == n or t == n_clean for t in targets):
                    return str(q)
    except Exception:
        pass

    # 3. 尝试从 storage 内存 @ 反查表匹配
    try:
        with ST._AT_NAMES_LOCK:
            for t in targets:
                q = ST._AT_NAMES.get(t)
                if q:
                    return str(q)
            for k, q in ST._AT_NAMES.items():
                if _clean_user_nick(k) == clean:
                    return str(q)
    except Exception:
        pass

    # 4. 尝试从 SQLite accounts / groups 数据库精确匹配
    try:
        import json as _json
        db = ST._ensure_db() if hasattr(ST, "_ensure_db") else getattr(ST, "_DB", None)
        if db is not None:
            cur = db.cursor()
            if gid:
                cur.execute("SELECT qq, data FROM accounts WHERE gid=?", (int(gid),))
                for row in cur.fetchall():
                    try:
                        d = _json.loads(row[1]) if isinstance(row[1], str) else (row[1] or {})
                        un = _clean_user_nick(d.get("name") or d.get("card") or d.get("nickname") or "")
                        if un and un == clean:
                            return str(row[0])
                    except Exception:
                        pass
                cur.execute("SELECT qq, data FROM groups WHERE gid=?", (int(gid),))
                for row in cur.fetchall():
                    try:
                        d = _json.loads(row[1]) if isinstance(row[1], str) else (row[1] or {})
                        un = _clean_user_nick(d.get("name") or d.get("card") or "")
                        if un and un == clean:
                            return str(row[0])
                    except Exception:
                        pass
            # 全局 accounts 检索兜底
            cur.execute("SELECT qq, data FROM accounts WHERE data LIKE ? LIMIT 50", (f"%{clean}%",))
            for row in cur.fetchall():
                try:
                    d = _json.loads(row[1]) if isinstance(row[1], str) else (row[1] or {})
                    un = _clean_user_nick(d.get("name") or d.get("card") or d.get("nickname") or "")
                    if un and un == clean:
                        return str(row[0])
                except Exception:
                    pass
    except Exception:
        pass
    return None


def _extract_transfer_target(raw, gid=None):
    """解析 @目标: 优先认 CQ码 / [At:QQ] -> @QQ数字，若未匹配尝试群内 @昵称 反查。返回 (target_qq_or_None, remaining_text)。"""
    raw = str(raw or "")
    target = None
    m = re.search(r"(?:\[CQ:at,qq=(\d+)[^\]]*\]|\[At:\s*(\d+)\])", raw)
    if m:
        target = m.group(1) or m.group(2)
    else:
        m = re.search(r"@\s*(\d{5,12})", raw)
        if m:
            target = m.group(1)
        elif gid:
            m_at = re.search(r"@\s*(\S+)", raw)
            if m_at:
                cand = m_at.group(1).strip()
                t_cand = _find_qq_by_name(gid, cand)
                if t_cand:
                    target = t_cand

    if target:
        # 清除 CQ 码 / [At:QQ] 与残留的 @昵称/@QQ 标记，返回纯净的正文指令与金额
        rem = re.sub(r"(?:\[CQ:at,qq=\d+[^\]]*\]|\[At:\s*\d+\])", "", raw)
        rem = re.sub(r"@\s*\S+", "", rem).strip()
        rem = re.sub(r"\s+", " ", rem)
        return target, rem.strip()
    return None, raw.strip()


def _ensure_target_qq(target, gid=None):
    """cmd_transfer 内部兜底: QQ-only，只认纯QQ / CQ码 / [At:QQ] / @QQ数字 / 独立数字串，不认昵称"""
    if target is None:
        return None
    s = str(target).strip()
    s = re.sub(r"(?:金币|金|币|元|点)$", "", s).strip()
    if re.fullmatch(r"\d{5,12}", s):
        return s
    m = (
        re.search(r"(?:\[CQ:at,qq=(\d+)[^\]]*\]|\[At:\s*(\d+)\])", s)
        or re.search(r"@\s*(\d{5,12})", s)
        or re.search(r"(\d{5,12})", s)
    )
    if m:
        return m.group(1) or m.group(2)
    if gid:
        cand = _find_qq_by_name(gid, s.lstrip("@").strip())
        if cand:
            return cand
    return None



__all__ = ["_MENU", "_acct", "_cd", "_disp_name", "_ensure_target_qq", "_extract_transfer_target", "_find_qq_by_name", "_now_s", "cfgi", "GAMBLE_MULT", "REDPACK_MIN_DIV", "REDPACK_MAX_DIV"]
