# -*- coding: utf-8 -*-
"""群组开关 API — 总开关 + 按群开关"""
import asyncio
from astrbot.api.web import json_response
from .web_utils import get_req_json

try:
    from ... import storage as ST
except ImportError:
    import storage as ST

async def handle_groups_list(request=None):
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
                out.append({"gid": str(gid), "enabled": enabled, "member_count": int(counts.get(str(gid), 0)), "is_test": str(gid) == "999999"})
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

    if gid in ("total", "__total__", "总开关"):
        ST._CONFIG.setdefault("总开关配置", {})
        ST._CONFIG["总开关配置"]["总开关"] = "真" if enabled else "假"
        try: ST.save_config()
        except Exception: pass
        try: ST.sync_astrbot_config(ST._CONFIG)
        except Exception: pass
        return json_response({"ok": True, "total_enabled": enabled})

    if not gid or not gid.isdigit():
        return json_response({"ok": False, "msg": "群号必填且需为纯数字"})

    def _work():
        ST._CONFIG.setdefault("群组开关配置", {})
        ST._CONFIG["群组开关配置"][gid] = "真" if enabled else "假"
        try: ST.save_config()
        except Exception: pass
        try: ST.sync_astrbot_config(ST._CONFIG)
        except Exception: pass
        try: ST.recall_set(f"group_switch_{gid}", "1" if enabled else "0")
        except Exception: pass

        # 同步初始化 group 实体
        try:
            grp = ST.group(gid)
            ST.save_group(gid)
        except Exception:
            pass

        return json_response({"ok": True, "gid": gid, "enabled": enabled})

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
            try: ST.sync_astrbot_config(ST._CONFIG)
            except Exception: pass
            try: ST.recall_set(f"group_switch_{gid}", "1")
            except Exception: pass
            return json_response({"ok": True, "gid": gid, "deleted": True})
        except Exception as e:
            return json_response({"ok": False, "msg": str(e)}, status=500)

    return await asyncio.to_thread(_work)
