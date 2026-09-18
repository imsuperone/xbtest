# -*- coding: utf-8 -*-
"""games/slave/nick.py — 奴隶包·nick（原 base.py 切分，语义不变）。"""
import re as _re
try:
    from ...core import storage as ST
    store = ST
except ImportError:
    from core import storage as ST
    store = ST
from . import slave_state as _S
from .base import U, save, state, uget, uset


def _clean_nm(s):
    """昵称归一化（去括号/空白），反查比对统一口径"""
    try:
        return _re.sub(r"[\[\]【】\(\)\s]", "", str(s or ""))
    except Exception:
        return str(s or "")




def set_note_name(gid, qq, name):
    """写入分群昵称 + 反向索引 + 全局最新兜底（写路径唯一入口，O(1)）"""
    try:
        g = str(gid or "").strip()
        q = str(qq or "").strip()
        n = str(name or "").strip()
        if not q.isdigit() or not n:
            return
        if g:
            old = _S.NOTE_NAMES_BY_GROUP.get((g, q), "")
            if old:
                _oc = _clean_nm(old)
                if _oc and _S.NOTE_NAMES_REV.get((g, _oc)) == q:
                    _S.NOTE_NAMES_REV.pop((g, _oc), None)
            _S.NOTE_NAMES_BY_GROUP[(g, q)] = n
            _nc = _clean_nm(n)
            if _nc:
                _S.NOTE_NAMES_REV[(g, _nc)] = q
            # 双表同生命周期上限防内存无限增长（淘汰最旧 10%）
            if len(_S.NOTE_NAMES_BY_GROUP) > 50000:
                try:
                    for _k in list(_S.NOTE_NAMES_BY_GROUP.keys())[:5000]:
                        _old2 = _S.NOTE_NAMES_BY_GROUP.pop(_k, None)
                        if _old2:
                            _oc2 = _clean_nm(_old2)
                            if _oc2 and _S.NOTE_NAMES_REV.get((_k[0], _oc2)) == _k[1]:
                                _S.NOTE_NAMES_REV.pop((_k[0], _oc2), None)
                except Exception:
                    pass
        # 保留全局最新，供无 gid 的旧展示路径兜底
        _S.NOTE_NAMES[q] = n
    except Exception:
        pass




def get_note_name(gid, qq, fallback_global=False):
    """读取分群昵称。默认不跨群串扰；gid 为空或显式要求时才回退全局。"""
    try:
        g = str(gid or "").strip()
        q = str(qq or "").strip()
        if g:
            n = _S.NOTE_NAMES_BY_GROUP.get((g, q), "")
            if n:
                return n
            if not fallback_global:
                return ""
        return _S.NOTE_NAMES.get(q, "") or ""
    except Exception:
        return ""




def display_name(gid, qq, default=None):
    """分群优先的只读昵称链（无写副作用）：分群昵称 → 本群卡片 → default（缺省为 qq 本身）。

    gid 为空时直接回 default，绝不跨群取全局。散落各引擎的
    `get_note_name(gid,x) or fetch_card(gid,x) or str(x)` 一律收口至此。"""
    try:
        q = str(qq)
    except Exception:
        return default
    try:
        g = str(gid or "").strip()
        if g:
            try:
                n = get_note_name(g, q)
                if n:
                    return n
            except Exception:
                pass
            try:
                n = fetch_card(g, q)
                if n:
                    return n
            except Exception:
                pass
    except Exception:
        pass
    return default if default is not None else q


def clear_note_name(gid, qq):
    """清除单用户分群昵称（WebUI 删除用户/退群清理后调用，防幽灵名）"""
    try:
        g = str(gid or "").strip()
        q = str(qq or "").strip()
        if g and q:
            old = _S.NOTE_NAMES_BY_GROUP.pop((g, q), None)
            if old:
                _oc = _clean_nm(old)
                if _oc and _S.NOTE_NAMES_REV.get((g, _oc)) == q:
                    _S.NOTE_NAMES_REV.pop((g, _oc), None)
    except Exception:
        pass




def find_qq_by_name(gid, name):
    """本群昵称反查 qq：精确 O(1)，模糊仅扫本群已清洗键（不清别群，不逐条正则）"""
    try:
        g = str(gid or "").strip()
        c = _clean_nm(name)
        if not c:
            return None
        if g:
            q = _S.NOTE_NAMES_REV.get((g, c))
            if q:
                return str(q)
            for (g2, cn), q2 in _S.NOTE_NAMES_REV.items():
                if g2 != g or not cn:
                    continue
                if cn == c or c in cn or cn in c:
                    return str(q2)
            return None
        for _q, _n in _S.NOTE_NAMES.items():
            if _clean_nm(_n) == c:
                return str(_q)
    except Exception:
        pass
    return None




def mark_known(gid, qq):
    """记录 qq 是本群已知成员(出现过/被@/开过户)"""
    try:
        gid = str(gid); qq = str(qq)
        if qq.isdigit():
            _s = _S._KNOWN.get(gid)
            if _s is None:
                # 群数上限防内存无限增长
                if len(_S._KNOWN) >= 5000:
                    try:
                        _S._KNOWN.pop(next(iter(_S._KNOWN)))
                    except Exception:
                        pass
                _s = _S._KNOWN.setdefault(gid, set())
            if len(_s) < 20000:
                _s.add(qq)
    except Exception:
        pass




def exists_user(gid, qq):
    """判断 qq 是否为该群真实存在的成员。
    判定依据(任一命中即存在): 已在本群出现过 / 在 NOTE_NAMES(事件名片) /
    真正开户(有主人/名字/签到/货币等实质数据)。
    只读, 不创建任何档案; 忽略 U() 自动补的空壳(仅默认 身价/主人=""/武器"" 等)。"""
    gid = str(gid); qq = str(qq)
    if not qq.isdigit():
        return False
    if qq == str(_S.BOT_UIN):
        return True
    if _S._KNOWN.get(gid) and qq in _S._KNOWN[gid]:
        return True
    # 分群昵称优先：同 QQ 在别群发言不得算作本群存在（防跨群串扰）
    if (gid, qq) in _S.NOTE_NAMES_BY_GROUP:
        return True
    try:
        st = state(gid)
        if st is not None and st.has_section(qq):
            raw = dict(st[qq] or {})
            # 兼顾中英文键：落库已英文化，显示保持中文，故同时检查英文键
            for k in ("name", "owner", "sign_date", "total_sign_days", "cash_total", "stamina", "charm", "message_count", "protect_until", "purchase_time"):
                v = str(raw.get(k, "")).strip()
                if v:
                    # 对 price 单独不算存在，避免 U() 默认 1000 误判
                    if k in ("cash_total", "stamina", "charm", "message_count"):
                        try:
                            if float(v) > 0:
                                return True
                        except Exception:
                            return True
                    else:
                        return True
        # 再查 DB 钱包/账户是否存在实质数据（持锁读，避免跨线程 database is locked）。
        # 注意：必须与档案检查同级（曾误缩进进 has_section 分支，致有钱包无档案者恒 False）
        try:
            if store._DB is not None:
                with store._LOCK:
                    row = store._DB.execute("SELECT 1 FROM wallet WHERE gid=? AND qq=?", (int(gid), int(qq))).fetchone()
                    row2 = store._DB.execute("SELECT 1 FROM accounts WHERE gid=? AND qq=?", (int(gid), int(qq))).fetchone() if not row else None
                if row:
                    return True
                if row2:
                    return True
        except Exception:
            pass
    except Exception:
        pass
    return bool(fetch_card(gid, qq))




def fetch_card(gid, qq):
    """分群优先的昵称读取（AstrBot 事件注入），已移除 NapCat 直连"""
    qq = str(qq)
    gid = str(gid or "")
    # 1. 分群昵称（本群最新卡片，绝不串到别群）
    if gid:
        return _S.NOTE_NAMES_BY_GROUP.get((gid, qq), "") or ""
    # 空 gid：全局最新兜底；无记录返回空，由 uname 回退本群档案
    return _S.NOTE_NAMES.get(qq) or ""




def uname(st, qq):
    u = U(st, qq)
    # 优先本群分群昵称(由 _dispatch 实时同步)，并回写到本群档案以持久化（绝不写别群）
    try:
        gid0 = str(getattr(st, "_gid", "") or "")
        nm = get_note_name(gid0, str(qq)) if gid0 else _S.NOTE_NAMES.get(str(qq), "")
        if nm and _re.sub(r"[\u3000\u3164\u200b\ufeff\u2800-\u28ff\s]", "", nm):
            if u.get("name", "") != nm:
                uset(u, "name", nm)
                try:
                    save(getattr(st, "_gid", "") or "")
                except Exception:
                    pass
            return nm
    except Exception:
        pass
    n = uget(u, "name")
    # 不可见字符昵称(空白/零宽)视为无名字
    if n and _re.sub(r"[\u3000\u3164\u200b\ufeff\u2800-\u28ff\s]", "", n):
        return n
    gid = getattr(st, "_gid", None) or ""
    if gid:
        card = fetch_card(gid, qq)
        if card and _re.sub(r"[\u3000\u3164\u200b\ufeff\u2800-\u28ff\s]", "", card):
            uset(u, "name", card)
            try:
                save(getattr(st, "_gid", gid))
            except Exception:
                pass
            return card
    return str(qq)



__all__ = ["clear_note_name", "display_name", "exists_user", "fetch_card", "find_qq_by_name", "get_note_name", "mark_known", "set_note_name", "uname"]
