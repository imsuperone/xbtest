# -*- coding: utf-8 -*-
"""core/dispatch.py — 消息分发流水线（原 dispatch/ 包 5 文件并入，零语义差）。
card_sync（名片后台同步）/ test_menu（测试testxb八菜单+探针路由，原 probe_route 已并入）/
admin_list（超管列表，30s 缓存）/ respond（业务执行与发送）。main 只留编排。"""
import threading as _threading
import asyncio as _asyncio
import time as _time

__all__ = ["maybe_sync_card", "SYS_LABELS", "handle_test_menu",
           "handle_admin_list", "run_business", "send_reply"]


# ==================== card_sync（原 dispatch/card_sync.py 并入） ====================
_NAME_POOL = None  # 复用2工作线程池（原挂 main.handle，迁入本模块单例）


def _bg_update_user_name(g, q, c, o, slave, ST):
    try:
        ST.register_name(q, c)
    except Exception:
        try:
            ST._register_single(q, c)
        except Exception:
            pass
    if o and g:
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


# ==================== test_menu（原 dispatch/test_menu.py 并入） ====================
SYS_LABELS = ["签到", "精灵", "娱乐", "银行", "奴隶", "坐骑", "帮派", "冒险"]


def _build_test_menus(gid, qq, mods):
    _menus = []
    for mod, label in [(mods["sign"], "签到系统"), (mods["spirit"], "精灵系统"),
                       (mods["ent"], "娱乐系统"), (mods["bank"], "银行系统"),
                       (mods["slave"], "奴隶系统"), (mods["ride"], "坐骑系统"),
                       (mods["guild"], "帮派系统"), (mods["adventure"], "冒险系统")]:
        try:
            m = getattr(mod, "MENU", None)
            if m is None:
                m = getattr(mod, "_MENU", None)
            if callable(m):
                try:
                    m = m()
                except Exception:
                    m = str(m)
            if not m:
                try:
                    m2 = mod.handle(gid, qq, label)
                    m = m2 if m2 else f"【{label}】无菜单"
                except Exception:
                    m = f"【{label}】无菜单"
            m = str(m)
        except Exception as e:
            m = f"【{label}】获取失败: {e}"
        _menus.append(m)
    return _menus


async def handle_test_menu(event, gid, qq, mods, slave):
    """命中测试testxb/1 即处理（必 yield 一条，调用方排空后直接 return）。"""
    menus = await _asyncio.to_thread(_build_test_menus, gid, qq, mods)
    bot = getattr(event, "bot", None)
    if bot:
        try:
            nodes = []
            for idx, m in enumerate(menus):
                txt = str(m)[:4000]
                nodes.append({"type": "node", "data": {
                    "name": f"测试{idx+1}-{SYS_LABELS[idx]}",
                    "uin": str(getattr(slave, "BOT_UIN", "") or qq),
                    "content": [{"type": "text", "data": {"text": txt}}]}})
            await _asyncio.wait_for(
                bot.call_action("send_group_forward_msg", group_id=int(gid), messages=nodes),
                timeout=8)
            try:
                event.stop_event()
            except Exception:
                pass
            yield event.plain_result("已发送合并转发测试（8系统）")
            return
        except Exception as e:
            try:
                try:
                    from .logger import error as _log_err
                except ImportError:
                    from core.logger import error as _log_err  # type: ignore
                _log_err(f"forward failed: {e}")
            except Exception:
                pass
    merged = "\n\n===== 测试testxb =====\n\n".join(menus)
    try:
        event.stop_event()
    except Exception:
        pass
    yield event.plain_result(merged)


# ==================== admin_list（原 dispatch/admin_list.py 并入） ====================
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
            # 经 storage 公共函数前缀扫描，不直访 _LOCK/_DB 私有成员
            try:
                _keys = ST.recall_prefix("admin_") if hasattr(ST, "recall_prefix") else []
            except Exception:
                _keys = []
            for _k in _keys or []:
                try:
                    q = str(_k).split("_", 1)[1]
                    if q.isdigit():
                        admins.append(q)
                except Exception:
                    continue
            admins = sorted(set(admins), key=lambda x: int(x))
            _ADMIN_LIST_CACHE = (_now_a, list(admins))
    except Exception:
        pass
    return admins


def _render_admin_list(gid, qq, admins, slave):
    # 仅展示真实超管：不再强塞请求者 QQ（记录机制 recall_set 保留，hint 文案如实说明）
    admins = sorted(set(str(a) for a in (admins or []) if str(a).isdigit()), key=lambda x: int(x))
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
    if not admins:
        txt += "\r\n暂无记录：超管需至少触发一次超管指令后才会记录"
    elif len(admins) == 1:
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


# ==================== respond（原 dispatch/respond.py 并入） ====================
def _run_handle_and_welcome(gid, qq, raw, is_admin, handle_fn, ride):
    try:
        r = handle_fn(gid, qq, raw, is_admin)
    except Exception:
        r = None
    if not r:
        try:
            r = ride.check_welcome(gid, qq) or None
        except Exception:
            pass
    return r


async def run_business(gid, qq, raw, is_admin, executor, handle_fn, ride):
    loop = _asyncio.get_running_loop()
    if executor is not None:
        return await loop.run_in_executor(
            executor, _run_handle_and_welcome, gid, qq, raw, is_admin,
            handle_fn, ride)
    return _run_handle_and_welcome(gid, qq, raw, is_admin, handle_fn, ride)


def _is_pure_custom(raw, ST):
    try:
        sec = ST._CONFIG.get("自定义指令配置") if hasattr(ST, "_CONFIG") else {}
        if isinstance(sec, dict):
            rt = raw.strip()
            # 最长优先（与 router 索引同序）：重叠触发词时短词不得截胡长词，误判会漏名字前缀
            for t in sorted((str(t) for t in sec.keys() if str(t)), key=len, reverse=True):
                e = sec[t]
                if rt.startswith(t):
                    ev = e if isinstance(e, dict) else {"reply": str(e)}
                    if not str(ev.get("command", "") or "").strip() and str(ev.get("reply", "") or "").strip():
                        return True
                    return False
    except Exception:
        pass
    return False


async def send_reply(event, reply, qq, raw, gid, ST, logger, do_platform,
                     name_prefix, build_chain, message_chain_cls, has_core, cq_img_re):
    """平台动作/前缀/链发送四兼容 + 去图兜底。原逻辑逐行平移。"""
    if logger:
        try:
            summary = str(reply)[:60].replace("\r", " ").replace("\n", " ")
            logger.info(f"[群 {gid}] [{qq}] 指令: {raw.strip()[:40]} -> 响应: {summary}")
        except Exception:
            pass
    if isinstance(reply, str) and reply.startswith("__XB_PLATFORM__"):
        try:
            note = await do_platform(reply, event)
        except Exception as e:
            note = f"平台动作执行失败：{e}"
        reply = note
    # 纯自定义指令不自动带名字（用户要求），带变量渲染后直接返回
    if not _is_pure_custom(raw, ST):
        reply = name_prefix(qq, reply)
    try:
        comp = build_chain(reply)
        event.stop_event()
        if hasattr(event, "chain_result"):
            yield event.chain_result(comp)
        elif hasattr(event, "make_result"):
            res = event.make_result()
            for c in comp:
                if hasattr(c, "text") and c.text:
                    res.message(c.text)
                elif hasattr(c, "path") or hasattr(c, "file"):
                    res.file_image(getattr(c, "path", None) or getattr(c, "file", None))
            yield res
        elif hasattr(event, "message_result"):
            yield event.message_result(message_chain_cls(comp))
        else:
            yield event.plain_result(reply[0] if isinstance(reply, tuple) else reply)
    except Exception:
        try:
            event.stop_event()
            raw_txt = reply[0] if isinstance(reply, tuple) else str(reply)
            cleaned_txt = cq_img_re.sub("", raw_txt).strip() if has_core else raw_txt
            yield event.plain_result(cleaned_txt)
        except Exception:
            pass
