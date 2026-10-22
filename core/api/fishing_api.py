# -*- coding: utf-8 -*-
"""core/api/fishing_api.py — 钓鱼与迷你世界水族馆管理后台 API。
提供 105 种鱼类图鉴读写、增删改查、自定义导入导出、默认恢复、配置调优与实时鱼塘水族馆大屏监控。
"""
import time
import json
import os
try:
    from ..adapters import json_response
except ImportError:
    from core.adapters import json_response
from .web_utils import _err, get_req_query, get_req_json
try:
    from .. import storage as ST
    from ...games.fishing.data_fishes import (
        load_all_fishes, save_all_fishes, reset_default_fishes,
        get_fish_by_id, QUALITY_WEIGHTS, QUALITY_COLORS, WEIGHT_GRADES
    )
    from ...games.fishing.engine import (
        BAITS, DEFAULT_BUCKET_CAP, DEFAULT_AQUARIUM_CAP,
        WATER_CLEAN_COST, BASE_INTEREST_RATE, MAX_DAILY_INTEREST
    )
except (ImportError, ValueError):
    from core import storage as ST
    from games.fishing.data_fishes import (
        load_all_fishes, save_all_fishes, reset_default_fishes,
        get_fish_by_id, QUALITY_WEIGHTS, QUALITY_COLORS, WEIGHT_GRADES
    )
    from games.fishing.engine import (
        BAITS, DEFAULT_BUCKET_CAP, DEFAULT_AQUARIUM_CAP,
        WATER_CLEAN_COST, BASE_INTEREST_RATE, MAX_DAILY_INTEREST
    )


async def handle_fishing_overview(req=None):
    """钓鱼与水族馆系统总览数据"""
    try:
        fishes = load_all_fishes()
        total_sp = len(fishes)

        # 统计区域与品质分布
        zones = {}
        qualities = {}
        for f in fishes:
            z = f.get("zone", "未分类水域")
            zones[z] = zones.get(z, 0) + 1
            q = f.get("quality", "白色普通")
            qualities[q] = qualities.get(q, 0) + 1

        # 扫描 accounts 表中的实时钓鱼状态
        active_ponds = 0
        active_aquariums = 0
        total_bucket_fishes = 0
        total_aquarium_fishes = 0
        now = int(time.time())

        if hasattr(ST, "_DB") and ST._DB is not None:
            try:
                cur = ST._DB.cursor()
                cur.execute("SELECT gid, qq, data FROM accounts WHERE data LIKE '%fishing%'")
                for gid, qq, d_str in cur.fetchall():
                    try:
                        d_all = json.loads(d_str or "{}")
                        f_raw = d_all.get("fishing")
                        if not f_raw:
                            continue
                        f_data = json.loads(f_raw) if isinstance(f_raw, str) else f_raw
                        if not isinstance(f_data, dict):
                            continue

                        # 统计鱼塘
                        pond = f_data.get("pond")
                        if pond and pond.get("is_active") and pond.get("remain_casts", 0) > 0:
                            active_ponds += 1

                        # 统计水桶
                        b = f_data.get("bucket", [])
                        total_bucket_fishes += len(b)

                        # 统计水族馆
                        aq = f_data.get("aquarium", {})
                        aq_f = aq.get("fishes", [])
                        if aq_f:
                            active_aquariums += 1
                            total_aquarium_fishes += len(aq_f)
                    except Exception:
                        pass
            except Exception:
                pass

        data = {
            "code": 0,
            "total_species": total_sp,
            "zones": zones,
            "qualities": qualities,
            "active_ponds": active_ponds,
            "active_aquariums": active_aquariums,
            "total_bucket_fishes": total_bucket_fishes,
            "total_aquarium_fishes": total_aquarium_fishes,
            "baits": BAITS,
            "config": {
                "water_clean_cost": WATER_CLEAN_COST,
                "base_interest_rate": BASE_INTEREST_RATE,
                "max_daily_interest": MAX_DAILY_INTEREST,
                "bucket_cap": DEFAULT_BUCKET_CAP,
                "aquarium_cap": DEFAULT_AQUARIUM_CAP
            }
        }
        return json_response(data)
    except Exception as e:
        return _err(f"获取钓鱼总览失败: {e}", 500)


async def handle_fishing_fishes(req=None):
    """获取所有鱼类品种（支持区域、品质过滤与搜索）"""
    try:
        fishes = load_all_fishes()
        zone = get_req_query(req, "zone", "").strip()
        quality = get_req_query(req, "quality", "").strip()
        search = get_req_query(req, "search", "").strip().lower()

        res = []
        for f in fishes:
            if zone and f.get("zone") != zone:
                continue
            if quality and f.get("quality") != quality:
                continue
            if search:
                name = str(f.get("name", "")).lower()
                desc = str(f.get("desc", "")).lower()
                fid = str(f.get("id", "")).lower()
                if search not in name and search not in desc and search not in fid:
                    continue
            res.append(f)

        return json_response({"code": 0, "data": res, "total": len(res)})
    except Exception as e:
        return _err(f"获取鱼类列表失败: {e}", 500)


async def handle_fishing_fish_save(req=None):
    """新增或修改单条鱼类配置"""
    try:
        body = await get_req_json(req)
        fish = body.get("fish")
        if not isinstance(fish, dict):
            return _err("参数 fish 必须为对象", 400)

        name = str(fish.get("name", "")).strip()
        if not name:
            return _err("鱼类名称不能为空", 400)

        fid = str(fish.get("id", "")).strip()
        if not fid:
            fid = f"fish_{int(time.time() * 1000)}"
            fish["id"] = fid

        # 数值清洗
        try:
            fish["min_weight"] = max(0.01, round(float(fish.get("min_weight", 0.5)), 2))
            fish["max_weight"] = max(fish["min_weight"], round(float(fish.get("max_weight", 2.0)), 2))
            fish["base_price"] = max(1, int(float(fish.get("base_price", 50))))
        except Exception:
            fish["min_weight"] = 0.5
            fish["max_weight"] = 2.0
            fish["base_price"] = 50

        fish.setdefault("zone", "淡水湖泊与溪流")
        fish.setdefault("quality", "白色普通")
        fish.setdefault("size", "小型")
        fish.setdefault("icon", "🐟")
        fish.setdefault("desc", "")

        fishes = load_all_fishes()
        found = False
        for idx, item in enumerate(fishes):
            if item.get("id") == fid:
                fishes[idx] = fish
                found = True
                break

        if not found:
            fishes.append(fish)

        save_all_fishes(fishes)
        return json_response({"code": 0, "msg": "保存成功", "fish": fish})
    except Exception as e:
        return _err(f"保存鱼类失败: {e}", 500)


async def handle_fishing_fish_delete(req=None):
    """删除指定鱼类品种"""
    try:
        body = await get_req_json(req)
        fid = str(body.get("id", "")).strip()
        if not fid:
            return _err("缺少鱼类 id 参数", 400)

        fishes = load_all_fishes()
        initial_len = len(fishes)
        fishes = [f for f in fishes if f.get("id") != fid]

        if len(fishes) == initial_len:
            return _err("未找到该鱼类品种", 404)

        save_all_fishes(fishes)
        return json_response({"code": 0, "msg": "删除成功", "remaining": len(fishes)})
    except Exception as e:
        return _err(f"删除鱼类失败: {e}", 500)


async def handle_fishing_reset(req=None):
    """恢复默认 105 种鱼类图鉴"""
    try:
        ok, res = reset_default_fishes()
        if ok:
            return json_response({"code": 0, "msg": f"已成功恢复默认 {res} 种鱼类品种！", "count": res})
        return _err(f"重置失败: {res}", 500)
    except Exception as e:
        return _err(f"重置异常: {e}", 500)


async def handle_fishing_clear_all(req=None):
    """清空全部鱼类品种，方便用户从零自定义自建专属鱼池"""
    try:
        save_all_fishes([])
        return json_response({"code": 0, "msg": "已清空全部鱼类品种，您可以自由从零自制全新鱼类！", "count": 0})
    except Exception as e:
        return _err(f"清空失败: {e}", 500)


async def handle_fishing_import(req=None):
    """批量导入鱼类品种 JSON"""
    try:
        body = await get_req_json(req)
        f_list = body.get("fishes")
        mode = body.get("mode", "replace")  # 'replace' 或 'append'

        if not isinstance(f_list, list) or len(f_list) == 0:
            return _err("导入列表不能为空", 400)

        cleaned = []
        for it in f_list:
            if not isinstance(it, dict):
                continue
            name = str(it.get("name", "")).strip()
            if not name:
                continue
            fid = str(it.get("id", "")).strip() or f"f_{int(time.time()*1000)}_{len(cleaned)}"
            cleaned.append({
                "id": fid,
                "name": name,
                "zone": str(it.get("zone", "淡水湖泊与溪流")),
                "quality": str(it.get("quality", "白色普通")),
                "size": str(it.get("size", "小型")),
                "min_weight": max(0.01, round(float(it.get("min_weight", 0.5)), 2)),
                "max_weight": max(0.02, round(float(it.get("max_weight", 2.0)), 2)),
                "base_price": max(1, int(float(it.get("base_price", 50)))),
                "icon": str(it.get("icon", "🐟")),
                "desc": str(it.get("desc", ""))
            })

        if not cleaned:
            return _err("未解析到有效的鱼类数据", 400)

        if mode == "append":
            cur_fishes = load_all_fishes()
            existing_ids = {f.get("id") for f in cur_fishes}
            for c in cleaned:
                if c["id"] not in existing_ids:
                    cur_fishes.append(c)
                    existing_ids.add(c["id"])
            save_all_fishes(cur_fishes)
            return json_response({"code": 0, "msg": f"已成功追加导入 {len(cleaned)} 种鱼类！", "total": len(cur_fishes)})
        else:
            save_all_fishes(cleaned)
            return json_response({"code": 0, "msg": f"已成功覆盖导入 {len(cleaned)} 种鱼类！", "total": len(cleaned)})
    except Exception as e:
        return _err(f"导入失败: {e}", 500)


async def handle_fishing_export(req=None):
    """导出全部鱼类图鉴 JSON"""
    try:
        fishes = load_all_fishes()
        return json_response({"code": 0, "data": fishes, "total": len(fishes)})
    except Exception as e:
        return _err(f"导出失败: {e}", 500)


async def handle_fishing_runtime_list(req=None):
    """查询群友实时鱼塘与水族馆运行监测列表"""
    try:
        now = int(time.time())
        res = []
        if hasattr(ST, "_DB") and ST._DB is not None:
            cur = ST._DB.cursor()
            cur.execute("SELECT gid, qq, data FROM accounts WHERE data LIKE '%fishing%' LIMIT 300")
            for gid, qq, d_str in cur.fetchall():
                try:
                    d_all = json.loads(d_str or "{}")
                    f_raw = d_all.get("fishing")
                    if not f_raw:
                        continue
                    f_data = json.loads(f_raw) if isinstance(f_raw, str) else f_raw
                    if not isinstance(f_data, dict):
                        continue

                    pond = f_data.get("pond")
                    aq = f_data.get("aquarium", {})
                    bucket = f_data.get("bucket", [])
                    atlas = f_data.get("atlas", {})

                    pond_desc = "无活跃鱼塘"
                    if pond and pond.get("is_active"):
                        m_ts = pond.get("mature_ts", 0)
                        p_ts = pond.get("protect_end_ts", 0)
                        rem = pond.get("remain_casts", 0)
                        if now < m_ts:
                            pond_desc = f"发酵中(还剩{max(1, (m_ts - now)//60)}分)"
                        elif now < p_ts:
                            pond_desc = f"保护期(余{rem}次)"
                        elif rem > 0:
                            pond_desc = f"公开可偷(余{rem}次)"
                        else:
                            pond_desc = "已钓尽"

                    res.append({
                        "gid": str(gid),
                        "qq": str(qq),
                        "pond_bait": pond.get("bait", "-") if pond else "-",
                        "pond_status": pond_desc,
                        "bucket_count": len(bucket),
                        "bucket_cap": f_data.get("bucket_cap", DEFAULT_BUCKET_CAP),
                        "aquarium_name": aq.get("name", "水族馆"),
                        "aquarium_fishes": len(aq.get("fishes", [])),
                        "aquarium_cap": aq.get("capacity", DEFAULT_AQUARIUM_CAP),
                        "water_quality": aq.get("water_quality", 100),
                        "atlas_count": len(atlas)
                    })
                except Exception:
                    pass

        return json_response({"code": 0, "data": res, "total": len(res)})
    except Exception as e:
        return _err(f"获取运行时列表失败: {e}", 500)
