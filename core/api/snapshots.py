# -*- coding: utf-8 -*-
"""配置快照 API — 快照列表/保存/恢复（由 backup.py 独立拆出，端点不变）。"""
import json as _json
import time
try:
    from ..adapters import json_response
except ImportError:
    from core.adapters import json_response

from .web_utils import _err, get_req_query, get_req_json

try:
    from .. import storage as ST
except ImportError:
    from core import storage as ST


# ---------- 全量配置快照（一键恢复）：存 kv/DB，独立于 AstrBot 配置体系 ----------
_CFG_SNAP_MAX = 5


def _snap_index():
    try:
        raw = ST.recall_get("cfgsnap__index", "[]")
        idx = _json.loads(raw or "[]")
        return [str(x) for x in idx] if isinstance(idx, list) else []
    except Exception:
        return []


def _snap_name(prefix=""):
    """毫秒精度快照名，同毫秒连存自动加 -1/-2 后缀，防同名覆盖"""
    base = time.strftime("%Y%m%d_%H%M%S", time.localtime()) + "_%03d" % (int(time.time() * 1000) % 1000)
    name = (prefix + base) if prefix else base
    try:
        idx = set(_snap_index())
        i = 1
        cand = name
        while cand in idx or ST.recall_get("cfgsnap__" + cand, ""):
            cand = "%s-%d" % (name, i)
            i += 1
        return cand
    except Exception:
        return name


def _snap_index_save(idx):
    """按时间序截断到 _CFG_SNAP_MAX，手动快照优先占位（自动快照挤不掉它们）。
    返回实际保留的索引列表，供调用方按同一口径清理被挤出的行。"""
    try:
        idx = [str(x) for x in (idx or [])]
        manset = set(_snap_manual())
        auto_quota = max(0, _CFG_SNAP_MAX - min(sum(1 for x in idx if x in manset), _CFG_SNAP_MAX))
        keep, man_used, auto_used = [], 0, 0
        for x in idx:
            if x in manset:
                if man_used < _CFG_SNAP_MAX:
                    keep.append(x)
                    man_used += 1
            elif auto_used < auto_quota:
                keep.append(x)
                auto_used += 1
        ST.recall_set("cfgsnap__index", _json.dumps(keep, ensure_ascii=False))
        # 手动名单与保留集对齐（被 5 份上限挤出的手动快照同步摘除）
        _snap_manual_save([x for x in keep if x in manset])
        # 清理被挤出索引的孤儿快照行 + 扶正 latest（防 kv 无限堆积，旧库一次自愈）
        try:
            if ST._DB is not None:
                with ST._LOCK:
                    if keep:
                        _ph = ",".join("?" * len(keep))
                        _sql = ("DELETE FROM kv WHERE k LIKE 'cfgsnap\\_\\_%' ESCAPE '\\' "
                                "AND k NOT IN ('cfgsnap__index','cfgsnap__latest','cfgsnap__manual') "
                                "AND k NOT IN (" + _ph + ")")
                        ST._DB.execute(
                            _sql,
                            ["cfgsnap__" + k for k in keep])
                    if not ST._safe_commit():
                        raise RuntimeError("snapshot cleanup commit failed")
            try:
                _latest = str(ST.recall_get("cfgsnap__latest", "") or "")
                if _latest and _latest not in keep:
                    ST.recall_set("cfgsnap__latest", keep[0] if keep else "")
            except Exception:
                pass
            try:
                if hasattr(ST, "_KV_CACHE_LOCK"):
                    with ST._KV_CACHE_LOCK:
                        for k in list(ST._KV_CACHE.keys()):
                            if (k.startswith("cfgsnap__") and k not in ("cfgsnap__index", "cfgsnap__latest", "cfgsnap__manual")
                                    and k[9:] not in keep):
                                ST._KV_CACHE.pop(k, None)
            except Exception:
                pass
        except Exception:
            pass
        return keep
    except Exception:
        return [str(x) for x in (idx or [])]


def _snap_manual():
    """手动（用户点「保存快照」）快照名单——自动快照不得挤掉它们。"""
    try:
        raw = ST.recall_get("cfgsnap__manual", "[]")
        v = _json.loads(raw or "[]")
        return [str(x) for x in v] if isinstance(v, list) else []
    except Exception:
        return []


def _snap_manual_save(names):
    try:
        ST.recall_set("cfgsnap__manual", _json.dumps([str(x) for x in names], ensure_ascii=False))
    except Exception:
        pass


def auto_snapshot_if_changed():
    """配置保存后自动留快照：与最新一份一致则跳过，防内部保存刷屏"""
    try:
        cfg = getattr(ST, "_CONFIG", {}) or {}
        data = _json.dumps({"at": int(time.time()), "config": cfg}, ensure_ascii=False, default=str)
        idx = _snap_index()
        if idx:
            try:
                latest = ST.recall_get("cfgsnap__" + idx[0], "")
                if latest and _json.loads(latest).get("config") == _json.loads(data).get("config"):
                    return
            except Exception:
                pass
        name = _snap_name()
        ST.recall_set("cfgsnap__" + name, data)
        ST.recall_set("cfgsnap__latest", name)
        _snap_index_save([name] + [x for x in idx if x != name])
    except Exception:
        pass


async def handle_cfg_snapshots(request, plugin_base=""):
    """列出配置快照"""
    try:
        idx = _snap_index()
        out = []
        for name in idx:
            try:
                raw = ST.recall_get("cfgsnap__" + name, "")
                d = _json.loads(raw) if raw else {}
                secs = sorted((d.get("config") or {}).keys()) if isinstance(d, dict) else []
            except Exception:
                secs = []
            out.append({"name": name, "sections": secs})
        return json_response({"ok": True, "snapshots": out})
    except Exception as e:
        return _err(f"snapshots failed: {e}", 500)


async def handle_cfg_snapshot_save(request, plugin_base=""):
    """立即快照当前全量配置（含必要配置与用户全部自定义）——用户手动触发，标记为手动快照"""
    try:
        cfg = getattr(ST, "_CONFIG", {}) or {}
        data = _json.dumps({"at": int(time.time()), "config": cfg}, ensure_ascii=False, default=str)
        name = _snap_name()
        ST.recall_set("cfgsnap__" + name, data)
        ST.recall_set("cfgsnap__latest", name)
        idx = [name] + [x for x in _snap_index() if x != name]
        # 手动快照进名单：之后的自动快照（换肤/平衡等高频保存）挤不掉它
        _snap_manual_save([name] + [x for x in _snap_manual() if x != name])
        keep = _snap_index_save(idx)
        # 清理被挤出保留集的行（口径与 _snap_index_save 一致，避免误删受保护的手动快照）
        keepset = set(keep or [])
        for old in [x for x in idx if x not in keepset]:
            try:
                if hasattr(ST, "_KV_CACHE_LOCK"):
                    with ST._KV_CACHE_LOCK:
                        ST._KV_CACHE.pop("cfgsnap__" + old, None)
                if ST._DB is not None:
                    with ST._LOCK:
                        ST._DB.execute("DELETE FROM kv WHERE k=?", ("cfgsnap__" + old,))
                        if not ST._safe_commit():
                            raise RuntimeError("snapshot delete commit failed")
            except Exception:
                pass
        return json_response({"ok": True, "name": name})
    except Exception as e:
        return _err(f"snapshot save failed: {e}", 500)


async def handle_cfg_snapshot_restore(request, plugin_base=""):
    """一键恢复指定（或最新）配置快照"""
    try:
        p = await get_req_json(request, default={})
        name = str((p.get("name") or "") if isinstance(p, dict) else "").strip()
        if not name:
            name = get_req_query(request, "name", "").strip()
        if not name:
            name = str(ST.recall_get("cfgsnap__latest", "") or "").strip()
        if not name:
            return _err("no snapshot (name required)", 404)
        raw = ST.recall_get("cfgsnap__" + name, "")
        if not raw:
            return _err("snapshot not found", 404)
        d = _json.loads(raw)
        cfg = d.get("config") if isinstance(d, dict) else None
        if not isinstance(cfg, dict):
            return _err("snapshot broken", 500)
        if hasattr(ST, "_CONFIG"):
            ST._CONFIG.clear()
            for sec, kv in cfg.items():
                if isinstance(kv, dict):
                    if sec in getattr(ST, "_COLL_FILES", {}):
                        # 旧快照可能含商城/图鉴：收编进 sidecar，不进内存
                        try:
                            ST.coll_merge(sec, kv)
                        except Exception:
                            pass
                        continue
                    ST._CONFIG[str(sec)] = {str(k): v for k, v in kv.items()}
        try:
            if hasattr(ST, "_bump_config_ver"):
                ST._bump_config_ver()
        except Exception:
            pass
        try:
            ST.save_config()
        except Exception:
            pass
        try:
            ST.sync_astrbot_config(ST._CONFIG)
        except Exception:
            pass
        try:
            if hasattr(ST, "wd_cfg_backup"):
                ST.wd_cfg_backup((ST._CONFIG.get("备份配置") or {}) if isinstance(ST._CONFIG.get("备份配置"), dict) else None)
        except Exception:
            pass
        return json_response({"ok": True, "name": name})
    except Exception as e:
        return _err(f"snapshot restore failed: {e}", 500)

