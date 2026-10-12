"""groups API - 群聊开关/总开关/维修标记（原 stats.py 并入段独立，端点不变）"""
# -*- coding: utf-8 -*-
import asyncio
import time
try:
    from ..adapters import json_response
except ImportError:
    from core.adapters import json_response
from .web_utils import _err, get_req_json, get_req_query
try:
    from .. import storage as ST
except ImportError:
    from core import storage as ST  # type: ignore


_BOT_GROUPS_CACHE = {}
_BOT_GROUPS_TS = 0.0
_BOT_GROUPS_REFRESHING = False


async def _refresh_bot_groups(context=None, timeout=2.5):
    global _BOT_GROUPS_CACHE, _BOT_GROUPS_TS, _BOT_GROUPS_REFRESHING
    if _BOT_GROUPS_REFRESHING:
        return _BOT_GROUPS_CACHE
    _BOT_GROUPS_REFRESHING = True
    try:
        try:
            from .. import messaging as _msg_mod
        except ImportError:
            from core import messaging as _msg_mod  # type: ignore
        fetched = await asyncio.wait_for(_msg_mod.fetch_bot_groups(context=context), timeout=timeout)
        if isinstance(fetched, dict) and fetched:
            _BOT_GROUPS_CACHE = dict(fetched)
        _BOT_GROUPS_TS = time.monotonic()
    except Exception:
        _BOT_GROUPS_TS = time.monotonic()
    finally:
        _BOT_GROUPS_REFRESHING = False
    return _BOT_GROUPS_CACHE


# ==================== 群组开关（原 groups.py 并入） ====================
async def handle_groups_list(request=None, context=None):
    force_refresh = str(get_req_query(request, "refresh", "")).strip().lower() in ("1", "true", "yes")
    now = time.monotonic()
    if force_refresh:
        await _refresh_bot_groups(context=context, timeout=2.5)
    elif not _BOT_GROUPS_CACHE and _BOT_GROUPS_TS == 0.0:
        await _refresh_bot_groups(context=context, timeout=2.0)
    elif (now - _BOT_GROUPS_TS) > 60.0 and not _BOT_GROUPS_REFRESHING:
        try:
            asyncio.create_task(_refresh_bot_groups(context=context, timeout=2.5))
        except Exception:
            pass
    bot_groups = dict(_BOT_GROUPS_CACHE)

    def _work():
        _lock = getattr(ST, "_LOCK", None)
        if _lock is not None:
            _lock.acquire()
        try:
            counts = {}
            try:
                if ST._DB is not None:
                    # 单次聚合替代 3×DISTINCT+逐群COUNT：三表 UNION 去重后按群计数
                    for gid_, cnt in ST._DB.execute(
                        "SELECT gid, COUNT(DISTINCT qq) FROM ("
                        "SELECT gid, qq FROM wallet "
                        "UNION SELECT gid, qq FROM accounts "
                        "UNION SELECT gid, qq FROM groups"
                        ") GROUP BY gid"
                    ).fetchall():
                        if str(gid_).isdigit():
                            counts[str(gid_)] = int(cnt or 0)
            except Exception:
                pass
            gids = set(counts.keys())
            for bgid in (bot_groups or {}).keys():
                if str(bgid).isdigit():
                    gids.add(str(bgid))
            try:
                sec = ST._CONFIG.get("群组开关配置") if hasattr(ST, "_CONFIG") and isinstance(ST._CONFIG, dict) else {}
                if isinstance(sec, dict):
                    for k in sec.keys():
                        if str(k).isdigit():
                            gids.add(str(k))
            except Exception:
                pass

            out = []
            for gid in sorted(gids, key=lambda x: int(x) if str(x).isdigit() else 0):
                enabled = ST.cfg("群组开关配置", str(gid), "真") != "假"
                try:
                    _maint = ST.recall_get("group_maint_%s" % gid, "0") == "1"
                except Exception:
                    _maint = False
                gname = str((bot_groups or {}).get(str(gid)) or "").strip()
                try:
                    k_gn = "group_name_%s" % gid
                    cached_name = str(ST.recall_get(k_gn, "") or "").strip()
                    if gname and gname != cached_name:
                        with ST._KV_CACHE_LOCK:
                            ST._KV_CACHE[k_gn] = gname
                    elif not gname and cached_name:
                        gname = cached_name
                except Exception:
                    pass
                out.append({
                    "gid": str(gid),
                    "group_name": gname,
                    "enabled": enabled,
                    "maintenance": _maint,
                    "member_count": int(counts.get(str(gid), 0)),
                    "is_test": str(gid) == "999999",
                })
            total_enabled = ST.cfg("总开关配置", "总开关", "真") == "真"
            return {"total_enabled": total_enabled, "groups": out}
        finally:
            if _lock is not None:
                try:
                    _lock.release()
                except Exception:
                    pass
    data = await asyncio.to_thread(_work)
    return json_response(data)

async def handle_groups_toggle(request):
    data = await get_req_json(request, default={})
    gid = str(data.get("gid", "") or data.get("group_id", "") or "").strip()
    enabled = data.get("enabled")
    if isinstance(enabled, str):
        enabled = enabled.strip() not in ("假", "false", "False", "0", "off")
    else:
        enabled = bool(enabled) if enabled is not None else True
    # 本群维修开关（WebUI 群聊开关 Tab 可直接切换；聊天内 开启维护/关闭维护 同效）
    maint = data.get("maintenance", None)
    do_enabled = "enabled" in data

    if gid in ("total", "__total__", "总开关"):
        ST._CONFIG.setdefault("总开关配置", {})
        ST._CONFIG["总开关配置"]["总开关"] = "真" if enabled else "假"
        try: ST.save_config()
        except Exception: pass
        return json_response({"ok": True, "total_enabled": enabled})

    if not gid or not gid.isdigit():
        return json_response({"ok": False, "msg": "群号必填且需为纯数字"})

    def _work():
        if do_enabled:
            ST._CONFIG.setdefault("群组开关配置", {})
            ST._CONFIG["群组开关配置"][gid] = "真" if enabled else "假"
            try: ST.save_config()
            except Exception: pass
            try: ST.recall_set(f"group_switch_{gid}", "1" if enabled else "0")
            except Exception: pass
        _maint_now = None
        if maint is not None:
            _maint_now = bool(maint) if not isinstance(maint, str) else maint.strip() not in ("假", "false", "False", "0", "off", "")
            try: ST.recall_set(f"group_maint_{gid}", "1" if _maint_now else "0")
            except Exception: pass

        # 同步初始化 group 实体
        try:
            ST.group(gid)  # 副作用：初始化 group 实体并标脏
            ST.save_group(gid)
        except Exception:
            pass

        _resp = {"ok": True, "gid": gid}
        if do_enabled:
            _resp["enabled"] = enabled
        if _maint_now is not None:
            _resp["maintenance"] = _maint_now
        return json_response(_resp)

    return await asyncio.to_thread(_work)

async def handle_groups_delete(request):
    data = await get_req_json(request, default={})
    gid = str(data.get("gid", "") or data.get("group_id", "") or "").strip()
    if not gid or not gid.isdigit():
        return json_response({"ok": False, "msg": "群号必填且需为纯数字"})

    def _work():
        try:
            sec = ST._CONFIG.get("群组开关配置") if hasattr(ST, "_CONFIG") and isinstance(ST._CONFIG, dict) else {}
            if isinstance(sec, dict) and gid in sec:
                sec.pop(gid, None)
            try: ST.save_config()
            except Exception: pass
            try: ST.recall_set(f"group_switch_{gid}", "1")
            except Exception: pass
            return json_response({"ok": True, "gid": gid, "deleted": True})
        except Exception as e:
            return _err(str(e), 500)

    return await asyncio.to_thread(_work)
