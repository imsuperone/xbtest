# -*- coding: utf-8 -*-
"""core/dispatch/admin_list.py — 超管列表（原 main._dispatch 603-680，30s 缓存）。"""
import asyncio as _asyncio
import time as _time

_ADMIN_LIST_CACHE = None


def _fetch_admins(qq, ST):
    global _ADMIN_LIST_CACHE
    try:
        ST.recall_set(f"admin_{qq}", str(int(_time.time())))
    except Exception:
        pass
    admins = []
    try:
        _now_a = _time.time()
        _ac = _ADMIN_LIST_CACHE
        # 30 秒缓存：超管列表低频指令，命中缓存免 DB 扫描
        if _ac and (_now_a - _ac[0] < 30):
            admins = list(_ac[1])
        else:
            with ST._LOCK:
                rows = ST._DB.execute("SELECT k FROM kv WHERE k LIKE 'admin_%'").fetchall() if ST._DB else []
            for r in rows:
                try:
                    q = str(r[0]).split("_", 1)[1]
                    if q.isdigit():
                        admins.append(q)
                except Exception:
                    pass
            admins = sorted(set(admins), key=lambda x: int(x))
            _ADMIN_LIST_CACHE = (_now_a, list(admins))
    except Exception:
        pass
    return admins


def _render_admin_list(gid, qq, admins, slave):
    admins = list(admins)
    if str(qq) not in admins:
        admins.append(str(qq))
    admins = sorted(set(admins), key=lambda x: int(x))
    if not admins:
        admins = [str(qq)]
    lines = ["🔧 超管列表（AstrBot 管理员）"]
    for q in admins:
        try:
            try:
                nm = slave.get_note_name(gid, q) if hasattr(slave, "get_note_name") else slave.NOTE_NAMES.get(q, "")
            except Exception:
                nm = ""
            if not nm:
                nm = slave.NOTE_NAMES.get(q, "") or ""
            if not nm:
                try:
                    nm = slave.fetch_card(gid, q) or ""
                except Exception:
                    pass
            if nm:
                lines.append(f"- {q} ({nm})")
            else:
                lines.append(f"- {q}")
        except Exception:
            lines.append(f"- {q}")
    txt = "\r\n".join(lines)
    if len(admins) == 1:
        txt += "\r\n提示：其他超管需至少触发一次超管指令后才会记录"
    return txt


async def handle_admin_list(event, gid, qq, slave, ST):
    """超管列表已鉴权分支（必 yield 一条，调用方排空后直接 return）。"""
    try:
        admins = await _asyncio.to_thread(_fetch_admins, qq, ST)
        txt = _render_admin_list(gid, qq, admins, slave)
        try:
            event.stop_event()
        except Exception:
            pass
        yield event.plain_result(txt)
    except Exception as e:
        try:
            event.stop_event()
        except Exception:
            pass
        yield event.plain_result(f"超管列表异常: {e}")
