# -*- coding: utf-8 -*-
"""图鉴 API — 精灵图鉴读写（读出口径整形 + 入库清洗），图鉴页专属。
由 core/api/profiles.py 独立拆出（零语义差，端点 spirits/spirits/save 不变），
方便图鉴导出导入与自定义；用户画像（slave/spirit users）仍在 profiles.py。"""
import asyncio
import json
import re
try:
    from astrbot.api.web import json_response
except ImportError:
    def json_response(data, status=200):
        return data
from .web_utils import _err, get_req_json
try:
    from .. import storage as ST
except ImportError:
    from core import storage as ST
def _raw_spirit_cfg(key):
    """读精灵图鉴原始配置（未配置/非法返回 {}，不回退内置；回退由引擎 _SPIRITS/_MAPS/_SHOP 负责）"""
    try:
        try:
            from ...games import spirit  # noqa
        except ImportError:
            pass
        v = ST.cfg("精灵图鉴", key, "")
    except Exception:
        return {}
    if isinstance(v, dict):
        return _coerce_atlas_section(key, v)
    if v:
        try:
            d = json.loads(v)
            if isinstance(d, dict):
                return _coerce_atlas_section(key, d)
        except Exception:
            pass
    return {}
def _coerce_atlas_section(key, val):
    """图鉴读出口径整形（与保存清洗同构）：坏条目就地规范化，脏 sidecar 不再卡死前端渲染。
    只整 WebUI 下发口径，引擎 _SPIRITS/_MAPS/_SHOP 语义不动。"""
    try:
        if not isinstance(val, dict):
            return {}
        if key == "maps":
            out = {}
            for n, m in val.items():
                if not isinstance(m, dict):
                    m = {}
                try:
                    lv = int(float(m.get("lv", 1) or 1))
                except Exception:
                    lv = 1
                drops = m.get("drops", [])
                if isinstance(drops, str):
                    drops = [s.strip() for s in re.split(r"[,，]", drops) if s.strip()]
                if not isinstance(drops, list):
                    drops = []
                out[str(n)] = {"lv": lv if lv >= 1 else 1,
                               "drops": [str(x) for x in drops if str(x).strip()]}
            return out
        if key == "spirits":
            out = {}
            for n, it in val.items():
                if not isinstance(it, dict):
                    continue
                o = {"type": str(it.get("type", "") or "")}
                for f in ("hp", "atk", "def", "spa", "spd", "spe", "lv"):
                    try:
                        o[f] = int(float(it.get(f, 0) or 0))
                    except Exception:
                        o[f] = 0
                o["evolve"] = str(it.get("evolve", "") or "")
                o["img"] = str(it.get("img", "") or "")
                out[str(n)] = o
            return out
        if key == "shop":
            out = {}
            for n, it in val.items():
                if not isinstance(it, dict):
                    continue
                try:
                    price = int(float(it.get("price", 0) or 0))
                except Exception:
                    price = 0
                try:
                    effect = int(float(it.get("effect", 0) or 0))
                except Exception:
                    effect = 0
                out[str(n)] = {"price": price if price >= 0 else 0,
                               "attr": str(it.get("attr", "") or ""),
                               "effect": effect if effect >= 0 else 0}
            return out
    except Exception:
        pass
    return val if isinstance(val, dict) else {}
def _load_spirit_data():
    try:
        try:
            from ...games import spirit
        except ImportError:
            from games import spirit  # type: ignore
        sp = dict(spirit._SPIRITS() or {})  # type: ignore
        mp = dict(spirit._MAPS() or {})
        sh = dict(spirit._SHOP() or {})
        return {"spirits": _coerce_atlas_section("spirits", sp),
                "maps": _coerce_atlas_section("maps", mp),
                "shop": _coerce_atlas_section("shop", sh)}
    except Exception:
        try:
            try:
                from ...games.spirit import data_spirit as SD  # type: ignore
            except ImportError:
                from games.spirit import data_spirit as SD  # type: ignore
            return {"spirits": dict(getattr(SD, "SPIRITS", {})), "maps": dict(getattr(SD, "MAPS", {})), "shop": dict(getattr(SD, "SHOP", {}))}
        except Exception:
            return {"spirits": {}, "maps": {}, "shop": {}}
async def handle_spirits_get(request):
    def _work():
        data = _load_spirit_data()
        # 下发原始配置 + 内置基线：前端如实展示“未自定义/已自定义”，空即内置回退
        try:
            raw = {k: _raw_spirit_cfg(k) for k in ("spirits", "maps", "shop")}
            data = dict(data)
            data["_raw"] = raw
            try:
                try:
                    from ...games.spirit import data_spirit as _SDB  # type: ignore
                except ImportError:
                    from games.spirit import data_spirit as _SDB  # type: ignore
                data["_builtin"] = {
                    "spirits": dict(getattr(_SDB, "SPIRITS", {}) or {}),
                    "maps": dict(getattr(_SDB, "MAPS", {}) or {}),
                    "shop": dict(getattr(_SDB, "SHOP", {}) or {}),
                }
            except Exception:
                data["_builtin"] = {"spirits": {}, "maps": {}, "shop": {}}
            data["_meta"] = {
                "configured": {k: bool(raw.get(k)) for k in ("spirits", "maps", "shop")},
                "builtin": {k: len((data.get("_builtin") or {}).get(k) or {}) for k in ("spirits", "maps", "shop")},
            }
        except Exception:
            pass
        return json_response(data)
    return await asyncio.to_thread(_work)
async def handle_spirits_save(request):
    payload = await get_req_json(request, default={})
    if not isinstance(payload, dict):
        return _err("payload must be dict", 400)
    saved = []
    for key in ("spirits", "maps", "shop"):
        if key not in payload:
            continue
        val = payload[key]
        if not isinstance(val, dict):
            return _err(f"{key} must be dict", 400)
        # 入库整形：只保留结构合法的条目，脏数据就地清洗，保证自助添加不炸运行时
        try:
            if key == "spirits":
                _num_fields = ("hp", "atk", "def", "spa", "spd", "spe", "lv")
                _clean = {}
                for _n, _it in val.items():
                    if not isinstance(_it, dict):
                        continue
                    _o = {"type": str(_it.get("type", "") or "")}
                    for _f in _num_fields:
                        try:
                            _o[_f] = int(float(_it.get(_f, 0) or 0))
                        except Exception:
                            _o[_f] = 0
                    _o["evolve"] = str(_it.get("evolve", "") or "")
                    _o["img"] = str(_it.get("img", "") or "")
                    _clean[str(_n)] = _o
                val = _clean
            elif key == "maps":
                _clean = {}
                for _n, _m in val.items():
                    if not isinstance(_m, dict):
                        continue
                    try:
                        _lv = int(float(_m.get("lv", 1) or 1))
                    except Exception:
                        _lv = 1
                    _drops = _m.get("drops", [])
                    if isinstance(_drops, str):
                        _drops = [s.strip() for s in re.split(r"[,，]", _drops) if s.strip()]
                    if not isinstance(_drops, list):
                        _drops = []
                    _clean[str(_n)] = {"lv": _lv if _lv >= 1 else 1,
                                       "drops": [str(x) for x in _drops if str(x).strip()]}
                val = _clean
            elif key == "shop":
                _clean = {}
                for _n, _it in val.items():
                    if not isinstance(_it, dict):
                        continue
                    try:
                        _price = int(float(_it.get("price", 0) or 0))
                    except Exception:
                        _price = 0
                    try:
                        _effect = int(float(_it.get("effect", 0) or 0))
                    except Exception:
                        _effect = 0
                    _clean[str(_n)] = {"price": _price if _price >= 0 else 0,
                                       "attr": str(_it.get("attr", "") or ""),
                                       "effect": _effect if _effect >= 0 else 0}
                val = _clean
        except Exception:
            pass
        ST.set_ini("精灵图鉴", key, json.dumps(val, ensure_ascii=False))
        saved.append(key)
    if not saved:
        return _err("no data (want spirits/maps/shop)", 400)
    try:
        ST.save_config()
        st_cfg = dict(ST._CONFIG or {})
        ST.sync_astrbot_config(st_cfg)
    except Exception:
        pass
    return json_response({"saved": True, "keys": saved})
