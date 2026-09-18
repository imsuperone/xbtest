# -*- coding: utf-8 -*-
"""配置 API — schema / commands / get / save / auto_balance (覆盖28大系统全套平衡预设)"""
import asyncio
import math
import os
import json
try:
    from ..adapters import json_response
except ImportError:
    from core.adapters import json_response
from .web_utils import _err, get_req_json, no_cache_response

try:
    from .. import storage as ST
except ImportError:
    from core import storage as ST  # type: ignore

try:
    from .. import config as _cfg_layer
except ImportError:
    import config as _cfg_layer  # type: ignore


def _validate_config(norm, plugin_base=""):
    """校验已归一配置的已知字段；未知字段保留给兼容/专用 sidecar。"""
    base = plugin_base or os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    schema = _cfg_layer._load_schema(base)
    known = {}
    for sec, items in (schema.get("groups") or {}).items():
        for item in items or []:
            if isinstance(item, dict):
                known[(str(sec), str(item.get("key")))] = str(item.get("type", "string"))
    numeric = {}
    for sec, values in norm.items():
        if not isinstance(values, dict):
            continue
        for key, value in values.items():
            if value is None or (sec, str(key)) not in known:
                continue
            typ = known[(sec, str(key))]
            if typ not in ("int", "float"):
                continue
            try:
                number = float(value)
                if not math.isfinite(number):
                    raise ValueError
                if typ == "int" and number != int(number):
                    raise ValueError
            except (TypeError, ValueError):
                return f"{sec}.{key} 必须是{typ}"
            if "概率" in str(key) or "成功率" in str(key):
                if not 0 <= number <= 100:
                    return f"{sec}.{key} 必须在 0 到 100 之间"
            elif "比例" in str(key) or "倍率" in str(key):
                # 工资比例/身价上涨/赎身倍率：超 100 即百倍起步，直接卡掉（防配错印钱）
                if not 0 <= number <= 100:
                    return f"{sec}.{key} 必须在 0 到 100 之间"
            elif number < 0 and "变化下限" not in str(key):
                return f"{sec}.{key} 不能为负数"
            numeric[(sec, str(key))] = number
    for (sec, key), lower in list(numeric.items()):
        if not key.endswith("下限"):
            continue
        upper_key = key[:-2] + "上限"
        upper = numeric.get((sec, upper_key))
        if upper is not None and lower > upper:
            return f"{sec}.{key} 不能大于 {upper_key}"
    for (sec, key), lower in list(numeric.items()):
        if "最小" not in key:
            continue
        upper_key = key.replace("最小", "最大", 1)
        if upper_key == key:
            continue
        upper = numeric.get((sec, upper_key))
        if upper is not None and lower > upper:
            return f"{sec}.{key} 不能大于 {upper_key}"
    return None


async def handle_cfg_schema(request, plugin_base=""):
    try:
        base = plugin_base or os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        data = _cfg_layer._load_schema(base)
        return json_response(data)
    except Exception:
        return json_response({"groups": {}, "defaults": {}})


async def handle_commands(request, plugin_base=""):
    try:
        base = plugin_base or os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        out = _cfg_layer._collect_commands(base, ST)
        return json_response(out)
    except Exception as e:
        return _err(f"commands failed: {e}", 500)


async def handle_cfg_get(request):
    try:
        cfg = dict(getattr(ST, "_CONFIG", {}) or {})
        # 侧车配置（商城/精灵图鉴）合并只读回显：导出与前端 gather 需经 config/get 即见全量，文件优先
        try:
            from ..storage.collections import _coll_load as _c_load, _sidecar_exists as _c_exists
            for _sec in getattr(ST, "_COLL_FILES", {}) or {}:
                try:
                    if _c_exists(_sec):
                        cfg[_sec] = _c_load(_sec)
                except Exception:
                    pass
        except Exception:
            pass
        # WebDAV 密钥回填显示（地址/用户名明文，密码恒空；密钥本体只在独立文件）
        try:
            if hasattr(ST, "wd_secret_load"):
                _sec = dict(ST.wd_secret_load() or {})
                if _sec and isinstance(cfg.get("备份配置"), dict):
                    cfg = {**cfg, "备份配置": {**cfg["备份配置"]}}
                    if _sec.get("WebDAV服务器地址"):
                        cfg["备份配置"]["WebDAV服务器地址"] = _sec["WebDAV服务器地址"]
                    if _sec.get("WebDAV用户名"):
                        cfg["备份配置"]["WebDAV用户名"] = _sec["WebDAV用户名"]
                    cfg["备份配置"]["WebDAV应用密码"] = ""
        except Exception:
            pass
        return no_cache_response(json_response(cfg))
    except Exception as e:
        return _err(f"get failed: {e}", 500)


async def handle_cfg_save(request, plugin_base=""):
    try:
        p = await get_req_json(request, default={})
        if not isinstance(p, dict) or not p:
            return _err("未能读取到有效配置数据(请求体为空或解析失败)，请重试", 400)
        norm = _cfg_layer._normalize_cfg(p)
        validation_error = _validate_config(norm, plugin_base)
        if validation_error:
            return _err(validation_error, 400)
        # WebDAV 密钥分存：地址/用户名按 payload 落独立文件（含清空语义），密码仅非空更新；
        # 内存/_CONFIG/镜像/快照/备份里一律留空，防泄露。
        _secrets_changed = False
        try:
            _bsec = norm.get("备份配置")
            if isinstance(_bsec, dict) and hasattr(ST, "wd_secret_set"):
                for _k in ("WebDAV服务器地址", "WebDAV用户名"):
                    if _k in _bsec:
                        if ST.wd_secret_set(_k, str(_bsec.get(_k) or "")):
                            _secrets_changed = True
                        _bsec[_k] = ""
                if "WebDAV应用密码" in _bsec:
                    if str(_bsec.get("WebDAV应用密码") or "") != "":
                        if ST.wd_secret_set("WebDAV应用密码", str(_bsec.get("WebDAV应用密码"))):
                            _secrets_changed = True
                    _bsec["WebDAV应用密码"] = ""
        except Exception:
            pass

        def _work():
            # 自定义三节显式删除语义：值为 null 即删键（前端删除/改名后发 {旧触发词:null}，
            # merge 语义下缺键≠删除，不加这段会假成功复活；仅限这三节，其他节 null 照常存）
            try:
                for _sec in ("自定义指令配置", "指令启用配置", "指令回复配置", "指令权限配置"):
                    _d = norm.get(_sec)
                    if isinstance(_d, dict):
                        for _k in [k for k, v in _d.items() if v is None]:
                            _d.pop(_k, None)
                            try:
                                if isinstance(ST._CONFIG.get(_sec), dict):
                                    ST._CONFIG[_sec].pop(_k, None)
                            except Exception:
                                pass
            except Exception:
                pass
            _coll_failed = []
            _mem_saved = False
            for sec, kv in norm.items():
                if sec in getattr(ST, "_COLL_FILES", {}):
                    # 商城/图鉴走独立 sidecar，不进内存/_CONFIG
                    try:
                        if ST.coll_merge(sec, kv) is False:
                            _coll_failed.append(sec)
                    except Exception:
                        _coll_failed.append(sec)
                    continue
                ST._CONFIG.setdefault(sec, {})
                ST._CONFIG[sec].update(kv)
                _mem_saved = True
            try:
                if hasattr(ST, "_bump_config_ver"):
                    ST._bump_config_ver()
            except Exception:
                pass
            # WebDAV 配置 DB 镜像写透（含用户主动清空语义）
            try:
                if hasattr(ST, "wd_cfg_backup"):
                    ST.wd_cfg_backup(norm.get("备份配置"))
            except Exception:
                pass
            # 全量配置自动快照（去重，删改乱可一键恢复）
            try:
                from .snapshots import auto_snapshot_if_changed as _auto_snap
                _auto_snap()
            except Exception:
                try:
                    from core.api.snapshots import auto_snapshot_if_changed as _auto_snap2
                    _auto_snap2()
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
            if _coll_failed and not _mem_saved:
                return _err("save failed: %s" % "、".join(_coll_failed), 500)
            _resp = {"saved": True, "备份配置": ST._CONFIG.get("备份配置", {}), "webdav_secrets": "updated" if _secrets_changed else "kept"}
            if _coll_failed:
                _resp["coll_failed"] = _coll_failed
            return no_cache_response(json_response(_resp))

        import asyncio as _aio
        return await _aio.to_thread(_work)
    except Exception as e:
        return _err(f"save failed: {e}", 500)



# ==================== 拆分门面（balance 已独立，老路径兼容） ====================
try:
    from .balance import PRESETS, _BALANCE_SIG_KEYS, handle_balance_state, handle_config_auto_balance  # type: ignore
except ImportError:
    pass
