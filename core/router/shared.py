# -*- coding: utf-8 -*-
"""core/router/shared.py — 路由共享态：常量/纯函数/缓存（门面实时委托）。"""
import random
import time as _t_guard
_REPLY_OVERRIDE_SEC = "指令回复配置"
_DEFAULT_MARKERS = ("{回复}", "{默认}", "默认", "默认回复")
_CUSTOM_SEC = "自定义指令配置"
_DISABLE_SEC = "指令启用配置"
_PERM_SEC = "指令权限配置"
_ADMIN_ONLY = "超管"
_SYS_ENG = {'slave': '奴隶', 'sign': '签到', 'bank': '银行', 'ent': '娱乐', 'spirit': '精灵', 'ride': '坐骑', 'guild': '帮派', 'superadmin': '超管', 'chat': '聊天', 'adventure': '冒险'}
_MAIN_MENU = (
    "★ 小白测试版主菜单 ★\r\n"
    "----------------\r\n"
    "| ❤️ 签到系统 | ✨ 精灵系统 |\r\n"
    "| 🎮 娱乐系统 | 🏦 银行系统 |\r\n"
    "| ⛓️ 奴隶系统 | 🏍️ 坐骑系统 |\r\n"
    "| ⚔️ 帮派系统 | 🗺️ 冒险系统 |\r\n"
    "----------------\r\n"
    "发送系统关键词打开菜单，如【签到系统】【精灵系统】"
)
def _resolve_reply(cand, reply):
    if cand in _DEFAULT_MARKERS:
        return reply
    if "{回复}" in cand:
        return cand.replace("{回复}", reply)
    if "{默认}" in cand:
        return cand.replace("{默认}", reply)
    return cand
def _norm_cmd(s):
    """指令规范形：去内部空格（查询坐骑≡查询 坐骑）。仅用于内置开关/回复/引擎匹配；
    用户自定义触发词保持精确匹配，不走此函数（零行为变化）"""
    try:
        return str(s or "").replace(" ", "")
    except Exception:
        return ""
def _multi_reply(reply_tpl):
    """多回复随机（原 template.py 并入）：按 | 切分随机取一"""
    try:
        cands = [c.strip() for c in str(reply_tpl).split("|") if c.strip()]
        return random.choice(cands) if cands else reply_tpl
    except Exception:
        return reply_tpl




def _render_vars(tpl, gid, qq, store):
    """变量渲染（原 template.py 并入）：{name}/{qq}/{gid}/{time}/{coin}/{at} 等"""
    try:
        import datetime as _dt
        name = qq
        try:
            from ...games import slave as _sl  # type: ignore
            name = _sl.NOTE_NAMES.get(str(qq), str(qq))
        except Exception:
            try:
                import slave as _sl2  # type: ignore
                name = _sl2.NOTE_NAMES.get(str(qq), str(qq))
            except Exception:
                pass
        coin = ""
        try:
            coin = store.coin_name() if hasattr(store, "coin_name") else "金币"
        except Exception:
            coin = "金币"
        now = _dt.datetime.now()
        vars_map = {
            "{name}": str(name), "{qq}": str(qq), "{gid}": str(gid),
            "{group}": str(gid), "{time}": now.strftime("%H:%M:%S"),
            "{date}": now.strftime("%Y-%m-%d"), "{datetime}": now.strftime("%Y-%m-%d %H:%M:%S"),
            "{coin}": str(coin), "{金币}": str(coin),
        }
        for k, v in vars_map.items():
            if k in tpl:
                tpl = tpl.replace(k, v)
        # {at} -> @qq
        if "{at}" in tpl:
            tpl = tpl.replace("{at}", f"[CQ:at,qq={qq}]")
        return tpl
    except Exception:
        return tpl
_GUARD_CACHE = {}
_GUARD_CACHE_TTL = 5.0  # 5s 缓存，千群每消息 18次kv/config读→命中后0次DB；由 _bump_config_ver 主动清空
_GUARD_CACHE_MAX = 5000  # 无界增长防护：千群×9系统键超限淘汰最旧一半
_GUARD_BATCH_TTL = 2.0  # 同 gid 批量复用：2s 内9引擎守卫共享一次计算，突发消息0重复计算
_GUARD_BATCH_CACHE = {}  # gid -> (ts, {engine: blocked_msg_or_None})
_ENGINE_CMDS = {}
_ENGINE_CMDS_VER = None
_ENGINE_MT_CACHE = {"t": 0.0, "mt": 0.0}
_ENGINE_MT_TTL = 10.0  # mtime 探测节流：10 秒内复用，避免每消息 10 次 stat
_CUSTOM_IDX = {"ver": -1, "cmds": (), "dis": (), "ovr": (), "adm": (), "_fp": None}
