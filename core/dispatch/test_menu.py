# -*- coding: utf-8 -*-
"""core/dispatch/test_menu.py — 测试testxb/1 八系统菜单 + 测试testxb* 探针路由（原 probe_route.py 已并入，原 main._dispatch 522-601）。"""
import asyncio as _asyncio

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


async def handle_test_menu(event, gid, qq, is_private, mods, slave):
    """命中测试testxb/1 即处理（必 yield 一条，调用方排空后直接 return）。"""
    menus = await _asyncio.to_thread(_build_test_menus, gid, qq, mods)
    bot = getattr(event, "bot", None)
    if bot and not is_private:
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
                print(f"forward failed: {e}")
            except Exception:
                pass
    merged = "\n\n===== 测试testxb =====\n\n".join(menus)
    try:
        event.stop_event()
    except Exception:
        pass
    yield event.plain_result(merged)


async def run_probes(event, raw, gid, qq, is_admin, is_private):
    """命中探针即 yield 一条；未命中零产出（调用方以“有无产出”判定是否已处理，原 probe_route.py 并入）。"""
    try:
        try:
            from ...games.selftest.runner import handle_test_probes as _ext_test
        except ImportError:
            from games.selftest.runner import handle_test_probes as _ext_test  # type: ignore
        ext = await _ext_test(raw, gid, qq, is_admin, event, is_private)
        if ext is not None:
            if ext.startswith("__HANDLED__"):
                yield event.plain_result(ext[11:])
            else:
                yield event.plain_result(ext)
    except Exception:
        pass
