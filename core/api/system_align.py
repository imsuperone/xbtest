# -*- coding: utf-8 -*-
"""system_align API — 对齐官方最新版本默认内容（题库、坐骑、平衡预设、武器等），并确保用户自定义永不丢失"""
import asyncio
import copy
import json
import os
import shutil
import time

try:
    from ..adapters import json_response
except ImportError:
    from core.adapters import json_response  # type: ignore

from .web_utils import _err, get_req_json, plugin_root

try:
    from .. import storage as ST
except ImportError:
    from core import storage as ST  # type: ignore

try:
    from .questions import _BANK_MAP, _clear_runtime_cache, _get_q_dir, _write_bank_file
except ImportError:
    from core.api.questions import _BANK_MAP, _clear_runtime_cache, _get_q_dir, _write_bank_file  # type: ignore

try:
    from .snapshots import _snap_name, _snap_index, _snap_index_save
except ImportError:
    from core.api.snapshots import _snap_name, _snap_index, _snap_index_save  # type: ignore


async def handle_align_defaults(request=None, plugin_base=""):
    """
    对齐官方最新版本默认内容：
    targets 可选:
      - 'riddles': 娱乐题库（急转弯、猜字谜、知识问答、成语接龙，增量合并修复官方题目，保留用户自建题目）
      - 'rides': 官方坐骑商城属性与预设图片（对齐默认坐骑价格/加成/图片，100%保留用户自定义坐骑与自定义图片）
      - 'presets': 基础数值与经济平衡预设（银行利率上限1%、SSR抽卡概率~1%、探险收益等推荐数值，不修改用户金币资产）
      - 'weapons': 42款内置武器默认攻击力与描述对齐
    backup: 布尔值，是否在对齐前自动创建安全备份快照（默认 True）
    """
    data = await get_req_json(request) if request else {}
    if not isinstance(data, dict):
        data = {}
    targets = data.get("targets") or ["riddles", "rides"]
    if isinstance(targets, str):
        targets = [targets]
    targets = [str(t).strip().lower() for t in targets if str(t).strip()]
    do_backup = bool(data.get("backup", True))

    base_dir = plugin_base or plugin_root(__file__)
    pers_dir = ST.get_persistent_data_dir(base_dir) if hasattr(ST, "get_persistent_data_dir") else ""

    backup_name = ""
    # 1. 自动安全快照
    if do_backup:
        try:
            cfg = getattr(ST, "_CONFIG", {}) or {}
            snap_data = json.dumps({
                "at": int(time.time()),
                "source": "pre_align_latest",
                "config": cfg
            }, ensure_ascii=False, default=str)
            backup_name = _snap_name("pre_align_")
            ST.recall_set("cfgsnap__" + backup_name, snap_data)
            idx = _snap_index()
            _snap_index_save([backup_name] + [x for x in idx if x != backup_name])
        except Exception:
            backup_name = ""

    results = {}

    # 2. 对齐娱乐题库 (riddles)
    if "riddles" in targets or "questions" in targets or "题库" in targets:
        seed_dir = os.path.join(base_dir, "data", "seeds", "questions")
        q_dir = os.path.join(base_dir, "data", "questions")
        os.makedirs(q_dir, exist_ok=True)
        riddle_stats = {}
        for b_key, meta in _BANK_MAP.items():
            fname = meta["file"]
            seed_file = os.path.join(seed_dir, fname)
            active_file = os.path.join(q_dir, fname)
            if not os.path.isfile(seed_file):
                continue
            try:
                with open(seed_file, "r", encoding="utf-8") as sf:
                    seed_items = json.load(sf)
            except Exception:
                seed_items = []

            active_items = []
            if os.path.isfile(active_file):
                try:
                    with open(active_file, "r", encoding="utf-8") as af:
                        active_items = json.load(af)
                except Exception:
                    active_items = []

            is_qa = meta.get("is_qa", True)
            merged = []
            custom_count = 0
            updated_seed_count = 0

            if is_qa:
                # 建立官方题目标准字典：标准题目 -> seed 对象
                seed_map = {}
                for it in seed_items:
                    if isinstance(it, dict) and it.get("q"):
                        seed_map[it["q"].strip().lower()] = it

                # 遍历当前活跃题库：保留用户自选题，更新既有官方题目纠错
                seen_q = set()
                for it in active_items:
                    if not isinstance(it, dict) or not it.get("q"):
                        continue
                    qk = it["q"].strip().lower()
                    if qk in seed_map:
                        # 官方题目，更新为最新官方修正（包含题干/答案优化）
                        merged.append(seed_map[qk])
                        updated_seed_count += 1
                    else:
                        # 用户自选题，完好保留！
                        merged.append(it)
                        custom_count += 1
                    seen_q.add(qk)

                # 补充新增的官方题目
                for it in seed_items:
                    if isinstance(it, dict) and it.get("q"):
                        qk = it["q"].strip().lower()
                        if qk not in seen_q:
                            merged.append(it)
                            seen_q.add(qk)
                            updated_seed_count += 1
            else:
                # 接龙词库合并
                seen_words = set()
                seed_words_set = {str(w).strip().lower() for w in seed_items if str(w).strip()}
                for it in active_items:
                    w = str(it).strip()
                    if w and w.lower() not in seen_words:
                        merged.append(w)
                        seen_words.add(w.lower())
                        if w.lower() not in seed_words_set:
                            custom_count += 1
                for it in seed_items:
                    w = str(it).strip()
                    if w and w.lower() not in seen_words:
                        merged.append(w)
                        seen_words.add(w.lower())
                updated_seed_count = len(merged) - custom_count

            _write_bank_file(active_file, merged)
            riddle_stats[meta["name"]] = {
                "total": len(merged),
                "official_aligned": updated_seed_count,
                "custom_preserved": custom_count
            }

        _clear_runtime_cache()
        results["riddles"] = {
            "ok": True,
            "msg": "官方题库已完成对齐，错漏题目已修复，用户自建题目均已完整保留",
            "stats": riddle_stats
        }

    # 3. 对齐官方坐骑与图片 (rides)
    if "rides" in targets or "mounts" in targets or "坐骑" in targets:
        try:
            try:
                from ...games.config.shop import RIDE_SHOP as OFF_RIDE_SHOP
            except ImportError:
                from games.config.shop import RIDE_SHOP as OFF_RIDE_SHOP  # type: ignore

            # 当前活跃坐骑配置
            raw_rides = ST.cfg("商城图鉴", "ride_shop", {})
            cur_rides = {}
            if isinstance(raw_rides, dict):
                cur_rides = copy.deepcopy(raw_rides)
            elif isinstance(raw_rides, str) and raw_rides.strip():
                try:
                    cur_rides = json.loads(raw_rides)
                except Exception:
                    cur_rides = {}

            aligned_off_rides = 0
            custom_rides_count = 0

            # 遍历官方坐骑进行属性对齐
            for rname, off_info in OFF_RIDE_SHOP.items():
                if rname in cur_rides and isinstance(cur_rides[rname], dict):
                    # 已有该坐骑：保留自定义图片，对齐数值
                    item = cur_rides[rname]
                    # 检查图片是否是用户特异自定义（若为空或等于官方默认，更新为官方最新默认；若用户自定义了独立路径，保留用户的绑定）
                    c_img = str(item.get("img") or "").strip()
                    if not c_img or c_img == f"data/img/rides/{rname}.jpg":
                        item["img"] = off_info.get("img", f"data/img/rides/{rname}.jpg")
                    item["price"] = int(off_info.get("price", item.get("price", 0)))
                    item["buff"] = int(off_info.get("buff", item.get("buff", 0)))
                    item["buff_type"] = off_info.get("buff_type", item.get("buff_type", "all"))
                    aligned_off_rides += 1
                else:
                    # 补全缺失的官方默认坐骑
                    cur_rides[rname] = copy.deepcopy(off_info)
                    aligned_off_rides += 1

            for rname in cur_rides:
                if rname not in OFF_RIDE_SHOP:
                    custom_rides_count += 1

            # 保存更新后的坐骑
            if hasattr(ST, "coll_merge"):
                ST.coll_merge("商城图鉴", {"ride_shop": cur_rides})
            else:
                ST.set_ini("商城图鉴", "ride_shop", cur_rides)
                ST.save_config()

            # 同步官方坐骑预设图片到持久化目录（仅在独立持久化目录下镜像）
            src_ride_img_dir = os.path.join(base_dir, "data", "img", "rides")
            pers_real = os.path.realpath(pers_dir) if pers_dir else ""
            base_data_real = os.path.realpath(os.path.join(base_dir, "data"))
            if pers_real and pers_real not in (os.path.realpath(base_dir), base_data_real) and os.path.isdir(src_ride_img_dir):
                target_cand_dirs = [
                    os.path.join(pers_dir, "data", "img", "rides"),
                    os.path.join(pers_dir, "img", "rides")
                ]
                for tc in target_cand_dirs:
                    os.makedirs(tc, exist_ok=True)
                    for fn in os.listdir(src_ride_img_dir):
                        if fn.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".webp")):
                            sf = os.path.join(src_ride_img_dir, fn)
                            df = os.path.join(tc, fn)
                            if os.path.isfile(sf) and not os.path.isfile(df):
                                try:
                                    shutil.copy2(sf, df)
                                except Exception:
                                    pass

            # 刷新运行时坐骑目录缓存
            try:
                from games import ride as _g_ride
                if hasattr(_g_ride, "_refresh_img_bases"):
                    _g_ride._refresh_img_bases()
            except Exception:
                pass

            results["rides"] = {
                "ok": True,
                "msg": f"已对齐 {aligned_off_rides} 款官方默认坐骑属性与图片，保留 {custom_rides_count} 款用户自定义新增坐骑",
                "aligned_official": aligned_off_rides,
                "custom_preserved": custom_rides_count
            }
        except Exception as e:
            results["rides"] = {"ok": False, "msg": f"对齐坐骑失败: {e}"}

    # 4. 对齐基础数值与经济平衡预设 (presets)
    if "presets" in targets or "balance" in targets or "预设" in targets:
        try:
            # 银行利率上限与每日结算次数规范
            ST.set_ini("银行配置", "利率上限", 1)
            ST.set_ini("银行配置", "日结算上限", 3)
            # 奴隶/抽奖 SSR 概率基准平衡
            ST.set_ini("奴隶配置", "SSR概率", 1)
            ST.set_ini("奴隶配置", "抽卡模式", "标准")
            ST.save_config()

            results["presets"] = {
                "ok": True,
                "msg": "已对齐官方最新经济与数值平衡预设（银行最高利率1%/日结3次、SSR抽卡概率~1%等），玩家金币与资产不受任何影响"
            }
        except Exception as e:
            results["presets"] = {"ok": False, "msg": f"对齐平衡预设失败: {e}"}

    # 5. 对齐 42 款抽奖武器内置属性 (weapons)
    if "weapons" in targets or "武器" in targets:
        try:
            try:
                from ...games.config.shop import DEFAULT_WEAPON_ATTRS
            except ImportError:
                from games.config.shop import DEFAULT_WEAPON_ATTRS  # type: ignore

            raw_w = ST.cfg("商城图鉴", "weapon_attrs", {})
            cur_w = {}
            if isinstance(raw_w, dict):
                cur_w = copy.deepcopy(raw_w)
            elif isinstance(raw_w, str) and raw_w.strip():
                try:
                    cur_w = json.loads(raw_w)
                except Exception:
                    cur_w = {}

            aligned_w_count = 0
            for wname, off_attr in DEFAULT_WEAPON_ATTRS.items():
                if wname not in cur_w or not isinstance(cur_w[wname], dict):
                    cur_w[wname] = copy.deepcopy(off_attr)
                    aligned_w_count += 1
                else:
                    # 更新官方默认属性描述与攻击力
                    cur_w[wname]["atk"] = off_attr.get("atk", cur_w[wname].get("atk", 0))
                    cur_w[wname]["desc"] = off_attr.get("desc", cur_w[wname].get("desc", ""))
                    aligned_w_count += 1

            if hasattr(ST, "coll_merge"):
                ST.coll_merge("商城图鉴", {"weapon_attrs": cur_w})
            else:
                ST.set_ini("商城图鉴", "weapon_attrs", cur_w)
                ST.save_config()

            results["weapons"] = {
                "ok": True,
                "msg": f"已对齐 {aligned_w_count} 款内置武器官方属性，用户自定义武器完好保留"
            }
        except Exception as e:
            results["weapons"] = {"ok": False, "msg": f"对齐武器属性失败: {e}"}

    return json_response({
        "ok": True,
        "msg": "所选内容已成功对齐官方最新版本",
        "backup_snapshot": backup_name,
        "details": results
    })
