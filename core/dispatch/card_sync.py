# -*- coding: utf-8 -*-
"""core/dispatch/card_sync.py — 群名片后台同步（原 main._dispatch 468-512）。"""
import threading as _threading

_NAME_POOL = None  # 复用2工作线程池（原挂 main.handle，迁入本模块单例）


def _bg_update_user_name(g, q, c, o, slave, ST):
    try:
        ST.register_name(q, c)
    except Exception:
        try:
            ST._register_single(q, c)
        except Exception:
            pass
    if o and g and g != "dm":
        try:
            st = slave.state(g)
            if st.has_section(q):
                u = st[q]
                if u.get("name", "") != c:
                    u["name"] = c
                    slave.save(g)
        except Exception:
            pass


def maybe_sync_card(gid, qq, card, slave, ST):
    """名片变化即落盘 + 扔后台池同步账户。原逻辑逐行平移。"""
    global _NAME_POOL
    if not card:
        return
    old = slave.get_note_name(gid, qq) if hasattr(slave, "get_note_name") else slave.NOTE_NAMES.get(qq, "")
    if old != card:
        try:
            if hasattr(slave, "set_note_name"):
                slave.set_note_name(gid, qq, card)
            else:
                slave.NOTE_NAMES[qq] = card
        except Exception:
            slave.NOTE_NAMES[qq] = card
        try:
            if _NAME_POOL is None:
                from concurrent.futures import ThreadPoolExecutor as _TPE
                _NAME_POOL = _TPE(max_workers=2, thread_name_prefix="xbb-name")
            _NAME_POOL.submit(_bg_update_user_name, gid, qq, card, old, slave, ST)
        except Exception:
            _threading.Thread(target=_bg_update_user_name, args=(gid, qq, card, old, slave, ST),
                              daemon=True).start()
