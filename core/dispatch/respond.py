# -*- coding: utf-8 -*-
"""core/dispatch/respond.py — 业务执行与消息发送（原 main._dispatch 681-747）。"""
import asyncio as _asyncio


def _run_handle_and_welcome(gid, qq, raw, is_private, is_admin, handle_fn, ride):
    try:
        r = handle_fn(gid, qq, raw, is_private, is_admin)
    except Exception:
        r = None
    if not r and not is_private:
        try:
            r = ride.check_welcome(gid, qq) or None
        except Exception:
            pass
    return r


async def run_business(gid, qq, raw, is_private, is_admin, executor, handle_fn, ride):
    loop = _asyncio.get_running_loop()
    if executor is not None:
        return await loop.run_in_executor(
            executor, _run_handle_and_welcome, gid, qq, raw, is_private, is_admin,
            handle_fn, ride)
    return _run_handle_and_welcome(gid, qq, raw, is_private, is_admin, handle_fn, ride)


def _is_pure_custom(raw, ST):
    try:
        sec = ST._CONFIG.get("自定义指令配置") if hasattr(ST, "_CONFIG") else {}
        if isinstance(sec, dict):
            rt = raw.strip()
            for t, e in sec.items():
                t = str(t)
                if t and rt.startswith(t):
                    ev = e if isinstance(e, dict) else {"reply": str(e)}
                    if not str(ev.get("command", "") or "").strip() and str(ev.get("reply", "") or "").strip():
                        return True
    except Exception:
        pass
    return False


async def send_reply(event, reply, qq, raw, gid, is_private, ST, logger, do_platform,
                     name_prefix, build_chain, message_chain_cls, has_core, cq_img_re):
    """平台动作/前缀/链发送四兼容 + 去图兜底。原逻辑逐行平移。"""
    if logger:
        try:
            summary = str(reply)[:60].replace("\r", " ").replace("\n", " ")
            logger.info(f"[{'私聊' if is_private else f'群 {gid}'}] [{qq}] 指令: {raw.strip()[:40]} -> 响应: {summary}")
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
