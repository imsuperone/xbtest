# -*- coding: utf-8 -*-
"""Layer 2 — Platform Layer
负责消息链构建、@解析、昵称前缀、平台动作（禁言/踢人）。
隔离 AstrBot / OneBot 适配差异，上层路由无需关心平台细节。
"""
import os
import re
import threading as _threading

# @卡片待落盘池锁：事件循环线程写、后台线程读清，加小锁防交错
_CARDS_LOCK = _threading.Lock()


_CQ_IMG = re.compile(r"\[CQ:image,([^\]]*)\]")

# 由外部（main/slave）注入的 Image 组件与 slave 模块，避免循环导入
_Image = None
_slave = None

def bind(image_cls=None, slave_mod=None):
    global _Image, _slave
    if image_cls is not None:
        _Image = image_cls
    if slave_mod is not None:
        _slave = slave_mod


import urllib.parse
try:
    from .adapters import Plain
except ImportError:
    try:
        from core.adapters import Plain  # type: ignore
    except ImportError:
        try:
            from astrbot.api.message_components import Plain
        except Exception:
            class Plain:
                def __init__(self, text):
                    self.text = text


def _build_chain(reply):
    # 纯文本极速快判（0ms），接龙与绝大多数指令无图片，直接返回避免正则/urllib/文件系统开销
    if isinstance(reply, str):
        if "[CQ:image," not in reply:
            return [Plain(reply)] if reply else []
        text, imgs = reply, []
    elif isinstance(reply, tuple):
        _second = reply[1] if len(reply) > 1 else []
        # 兼容字符串单路径：list("C:/...") 会炸成单字，必须先包一层
        if isinstance(_second, str):
            _second = [_second] if _second.strip() else []
        try:
            text, imgs = (reply[0], list(_second or []))
        except Exception:
            text, imgs = (reply[0] if reply else "", [])
    else:
        s = str(reply) if reply is not None else ""
        if "[CQ:image," not in s:
            return [Plain(s)] if s else []
        text, imgs = s, []

    tt = text or ""
    _tt_orig = tt  # CQ 原样留底：图片全丢时回退原文，防图文全失
    _img_ok = False
    if "[CQ:image," in tt:
        def _repl(m):
            attrs = {}
            for a in m.group(1).split(","):
                if "=" in a:
                    k, v = a.split("=", 1)
                    attrs[k.strip()] = v.strip()
            f = attrs.get("file", "")
            f_dec = urllib.parse.unquote(f)
            if f_dec.startswith("file:///"):
                p = f_dec[8:]
                if len(p) > 3 and p[0] == "/" and p[2] == ":":
                    p = p[1:]
                imgs.append(p)
            elif f_dec.startswith("file://"):
                p = f_dec[len("file://"):]
                if not os.path.isfile(p) and os.path.isfile(f_dec[len("file://")+1:]):
                    p = f_dec[len("file://")+1:]
                imgs.append(p)
            elif f_dec:
                imgs.append(f_dec)
            return ""
        tt = _CQ_IMG.sub(_repl, tt).strip()

    comp = [Plain(tt)] if tt else []
    if imgs:
        try:
            from astrbot.api.message_components import Image as _Img
        except Exception:
            _Img = _Image
        for p in imgs:
            try:
                p_clean = str(p).strip()
                # On Windows: /C:/path -> C:/path
                if len(p_clean) > 3 and p_clean[0] == "/" and p_clean[2] == ":":
                    p_clean = p_clean[1:]
                if _Img is not None and isinstance(p_clean, str) and os.path.isfile(p_clean):
                    comp.append(_Img.fromFileSystem(p_clean))
                    _img_ok = True
            except Exception:
                pass
        if not _img_ok and _tt_orig and _tt_orig != tt:
            # 非文件图静默丢曾致图文全失：无一图可用时转文本 CQ 原样
            return [Plain(_tt_orig)]
    if not comp and tt:
        comp = [Plain(tt)]
    return comp


def _append_at_segments(raw, event, gid="", slave_mod=None):
    sm = slave_mod or _slave
    try:
        if gid:
            mark_known = getattr(sm, "mark_known", None) if sm else None
        else:
            mark_known = None
        chain = event.message_obj.message or []
        ats = []
        for comp in chain:
            comp_type = getattr(comp, "type", "") or getattr(comp, "component_type", "") or comp.__class__.__name__
            # @判定收紧：仅类型名含 at 的真@段，防 hasattr(qq/target) 过度匹配
            is_at = "at" in str(comp_type).lower()
            if not is_at:
                continue
            q = getattr(comp, "qq", None)
            if q is None:
                q = getattr(comp, "target", None)
            q = str(q or "").strip()
            if q.isdigit() and q not in ats:
                ats.append(q)
                if mark_known:
                    try:
                        mark_known(gid, q)
                    except Exception:
                        pass
                try:
                    nm = (getattr(comp, "name", None) or getattr(comp, "display", None) or getattr(comp, "card", None) or getattr(comp, "nickname", None) or "")
                    nm = str(nm).strip()
                    if nm and q:
                        if sm is not None:
                            try:
                                if hasattr(sm, "set_note_name"):
                                    sm.set_note_name(gid, q, nm)
                                elif hasattr(sm, "NOTE_NAMES_BY_GROUP"):
                                    # 无 set_note_name 旧门面时仍写分群表，绝不只写全局
                                    try:
                                        sm.NOTE_NAMES_BY_GROUP[(str(gid), str(q))] = nm
                                    except Exception:
                                        pass
                                    try:
                                        sm.NOTE_NAMES[str(q)] = nm
                                    except Exception:
                                        pass
                                else:
                                    old = sm.NOTE_NAMES.get(q, "")
                                    sm.NOTE_NAMES[q] = nm
                            except Exception:
                                pass
                            try:
                                with _CARDS_LOCK:
                                    _cards = getattr(_append_at_segments, "_pending_cards", None)
                                    if _cards is None:
                                        _cards = {}
                                        _append_at_segments._pending_cards = _cards
                                    _cards[(str(gid), str(q))] = nm
                            except Exception:
                                pass
                except Exception:
                    pass
        if ats:
            raw = (raw or "").rstrip()
            if raw and not raw.endswith(" "):
                raw += " "
            raw += " ".join("@" + q for q in ats)
        # @卡片落盘合并为单后台任务（@轰炸不再每 @ 起一个线程），复用分群写入
        try:
            with _CARDS_LOCK:
                _cards = getattr(_append_at_segments, "_pending_cards", None)
                if _cards:
                    _jobs = list(_cards.items())
                    _cards.clear()
                else:
                    _jobs = []
            if _jobs:
                def _bg_save_cards(_jobs, _sm=sm):
                    try:
                        for (_g, _tq), _tn in _jobs:
                            try:
                                if _sm is not None and _g:
                                    st = _sm.state(_g)
                                    if st.has_section(_tq):
                                        u = st[_tq]
                                        if u.get("name", "") != _tn:
                                            u["name"] = _tn
                                            _sm.save(_g)
                            except Exception:
                                pass
                            try:
                                from core import storage as _st_reg
                                _st_reg.register_name(_tq, _tn)
                            except Exception:
                                pass
                    except Exception:
                        pass
                try:
                    import concurrent.futures as _cf
                    _pool = getattr(_append_at_segments, "_pool", None)
                    if _pool is None:
                        _pool = _cf.ThreadPoolExecutor(max_workers=1, thread_name_prefix="xb-atcard")
                        _append_at_segments._pool = _pool
                    _pool.submit(_bg_save_cards, _jobs)
                except Exception:
                    import threading
                    threading.Thread(target=_bg_save_cards, args=(_jobs,), daemon=True).start()
        except Exception:
            pass
    except Exception:
        pass
    return raw


def _name_prefix(qq, reply, slave_mod=None, gid=""):
    sm = slave_mod or _slave
    try:
        nm = ""
        if sm is not None:
            try:
                # 分群链优先，全局仅兜底（防B群沿用A群昵称）
                nm = sm.display_name(gid, str(qq), "") or sm.NOTE_NAMES.get(str(qq), "") or str(qq)
            except Exception:
                try:
                    nm = sm.NOTE_NAMES.get(str(qq), "") or str(qq)
                except Exception:
                    nm = str(qq)
        else:
            nm = str(qq)
        prefix = f"[{nm}]"
        def _already_has_name(s):
            head = s[:120]
            ts = head.lstrip()
            if ts.startswith(f"[{nm}]") or ts.startswith(f"【{nm}】"):
                return True
            if ts.startswith("[") and "]" in ts[:40]:
                try:
                    inner = ts[1:ts.index("]")]
                    if inner == nm:
                        return True
                    # 非本人前缀不算已有，需补本人前缀
                    return False
                except Exception:
                    return False
            if f"【{nm}】" in head[:60]:
                return True
            return False
        if isinstance(reply, tuple):
            t = (reply[0] or "") if reply else ""
            imgs = list(reply[1] or []) if len(reply) > 1 else []
            if _already_has_name(t):
                return (t, imgs)
            return (f"{prefix}{t}", imgs)
        s = str(reply) if reply is not None else ""
        if _already_has_name(s):
            return s
        return f"{prefix}{s}"
    except Exception:
        return reply


async def _do_platform(marker, event, slave_mod=None):
    sm = slave_mod or _slave
    extra_text = ""
    if "__TEXT__" in marker:
        marker, extra_text = marker.split("__TEXT__", 1)
    parts = marker.split("|")
    if len(parts) < 3:
        return "平台动作参数错误。"
    act = parts[1]
    target = parts[2]
    dur_raw = parts[3] if len(parts) > 3 else "0"
    try:
        dur = int(''.join(c for c in str(dur_raw) if c.isdigit()) or "0")
    except Exception:
        dur = 0
    gid = event.get_group_id()
    bot = getattr(event, "bot", None)
    if bot is None:
        if act == "like" and extra_text:
            return extra_text  # 无适配器时降级为虚拟计数，不吞回复
        return "平台动作需要适配器 Bot 实例支持（当前未连接）。"
    # 所有 OneBot 动作 8 秒超时熔断，防事件循环被挂起的适配器拖死
    import asyncio as _aio

    async def _call(action, **kw):
        return await _aio.wait_for(bot.call_action(action, **kw), timeout=8)
    # 点赞无需任何权限预检（mute/kick 才需要）；预检仅对 mute/kick 跑
    if act in ("mute", "kick"):
        try:
            bot_uin = getattr(sm, "BOT_UIN", "") if sm else ""
            if not bot_uin:
                try:
                    info0 = await _call("get_login_info")
                    d0 = (info0.get("data") if isinstance(info0, dict) else None) or info0 or {}
                    bot_uin = str(d0.get("user_id") or d0.get("uin") or d0.get("self_id") or "")
                except Exception:
                    bot_uin = ""
            if bot_uin:
                try:
                    info_bot = await _call("get_group_member_info", group_id=int(gid), user_id=int(bot_uin))
                    d_bot = (info_bot.get("data") if isinstance(info_bot, dict) else None) or info_bot or {}
                    role_bot = str(d_bot.get("role", "")).lower()
                    if role_bot not in ("owner", "admin", "administrator"):
                        return "机器人不是管理员，无法执行禁言/踢人！"
                except Exception:
                    pass
            try:
                info_t = await _call("get_group_member_info", group_id=int(gid), user_id=int(target))
                d_t = (info_t.get("data") if isinstance(info_t, dict) else None) or info_t or {}
                role_t = str(d_t.get("role", "")).lower()
                if role_t in ("owner", "admin", "administrator"):
                    return "对方是管理员，无法禁言/踢人！"
            except Exception:
                pass
        except Exception:
            pass
    try:
        if act == "like":
            times = max(1, min(dur or 1, 10))  # OneBot send_like 单次上限 10
            # 非好友短路：陌生人赞风控率极高，连调都不调；查不到好友表时才放行尝试
            try:
                _fl = await _call("get_friend_list")
                _fd = (_fl.get("data") if isinstance(_fl, dict) else _fl) or []
                if isinstance(_fd, list) and len(_fd) > 0:
                    _ids = set()
                    for _f in _fd:
                        try:
                            if isinstance(_f, dict) and _f.get("user_id") is not None:
                                _ids.add(str(_f.get("user_id")))
                        except Exception:
                            continue
                    if str(target) not in _ids:
                        # 非好友直回失败注记：不带成功前缀，否则先报成功再报失败自相矛盾
                        return "（非好友点赞失败，请先加为好友）"
            except Exception:
                pass
            try:
                res = await _call("send_like", user_id=int(target), times=times)
                # 适配器常以 resolved 失败体代替抛错（如非好友/风控）：必须验 status/retcode，
                # 否则显示成功实则没点上
                if isinstance(res, dict):
                    _st = str(res.get("status") or "").lower()
                    _rc = res.get("retcode", res.get("ret_code", None))
                    if _st == "failed" or (_rc is not None and str(_rc) != "0"):
                        raise RuntimeError(f"send_like failed retcode={_rc}")
            except Exception as e1:
                if extra_text:
                    return extra_text + "（名片实赞未成功：需互为好友或对方设置限制）"
                return f"名片点赞失败：{e1}"
            base = f"成功点赞{times}次"
            # 成功文案与虚拟计数同文时只发一条，防“成功点赞5次\r\n成功点赞5次”复读
            if extra_text and extra_text != base:
                return extra_text + "\r\n" + base
            return base
        if act == "mute":
            try:
                await _call("set_group_ban", group_id=int(gid), user_id=int(target), duration=dur)
            except Exception as e1:
                if "不支持" in str(e1) or "not" in str(e1).lower():
                    await _call("set_group_mute", group_id=int(gid), user_id=int(target), duration=dur)
                else:
                    raise
            base = f"已将成员 <{target}> 禁言 {dur // 60} 分钟。"
            return (extra_text + "\r\n" + base) if extra_text else base
        if act == "kick":
            await _call("set_group_kick", group_id=int(gid), user_id=int(target))
            base = f"已将成员 <{target}> 移出本群。"
            return (extra_text + "\r\n" + base) if extra_text else base
    except Exception as e:
        if extra_text:
            return extra_text + f"\r\n平台动作执行失败：{e}"
        return f"平台动作执行失败：{e}"
    if extra_text:
        return extra_text
    return "未知平台动作。"


_LATEST_BOT = None

def set_latest_bot(bot):
    global _LATEST_BOT
    if bot is not None:
        _LATEST_BOT = bot

async def fetch_group_member_qqs(gid, bot=None, context=None):
    """通过 OneBot / AstrBot 适配器拉取指定群聊的实时在线成员 QQ 集合"""
    b = bot or _LATEST_BOT
    if b is None and context is not None:
        for attr in ("platform_adapters", "_platform_adapters", "get_platform_adapters", "get_bots", "bots"):
            try:
                val = getattr(context, attr, None)
                if callable(val):
                    val = val()
                if isinstance(val, (list, tuple, set)) and len(val) > 0:
                    for cand in val:
                        if cand is not None:
                            b = cand
                            break
                elif isinstance(val, dict) and len(val) > 0:
                    b = next(iter(val.values()))
                if b is not None:
                    break
            except Exception:
                pass

    if b is None:
        return None

    actions = ["get_group_member_list", "getGroupMemberList", "get_group_members"]
    cands = [b]
    for sub in ("bot", "client", "api", "_bot", "_client"):
        sub_obj = getattr(b, sub, None)
        if sub_obj is not None and sub_obj not in cands:
            cands.append(sub_obj)

    for cand in cands:
        for act in actions:
            try:
                info = None
                if hasattr(cand, "call_action") and callable(cand.call_action):
                    info = await cand.call_action(act, group_id=int(gid), no_cache=True)
                elif hasattr(cand, "call_api") and callable(cand.call_api):
                    info = await cand.call_api(act, group_id=int(gid), no_cache=True)
                elif hasattr(cand, act) and callable(getattr(cand, act)):
                    fn = getattr(cand, act)
                    info = await fn(group_id=int(gid), no_cache=True)

                if info is not None:
                    data = (info.get("data") if isinstance(info, dict) else None) or info or []
                    if isinstance(data, list) and len(data) > 0:
                        res = set()
                        for m in data:
                            if isinstance(m, dict):
                                q = str(m.get("user_id") or m.get("qq") or "").strip()
                                if q.isdigit():
                                    res.add(q)
                            elif isinstance(m, (int, str)) and str(m).isdigit():
                                res.add(str(m).strip())
                        if len(res) > 0:
                            return res
            except Exception:
                pass
    return None
