# -*- coding: utf-8 -*-
"""games/fishing/data_fishes.py — 鱼类图鉴数据库与抽样算法。
支持 105 种预设鱼类、JSON 持久化、后台自定义增删改、导入导出与重置。
"""
import os
import json
import random

_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data")
_FISH_JSON_PATH = os.path.join(_DATA_DIR, "fishing_fishes.json")
_FISH_DEFAULT_JSON_PATH = os.path.join(_DATA_DIR, "fishing_fishes_default.json")

_CACHED_FISHES = None

QUALITY_WEIGHTS = {
    "白色普通": 520,
    "绿色优秀": 260,
    "蓝色稀有": 130,
    "紫色史诗": 60,
    "橙色传说": 26,
    "幻彩神话": 4,
}

QUALITY_COLORS = {
    "白色普通": "⚪普通",
    "绿色优秀": "🟢优秀",
    "蓝色稀有": "🔵稀有",
    "紫色史诗": "🟣史诗",
    "橙色传说": "🟠传说",
    "幻彩神话": "🌈神话",
}

WEIGHT_GRADES = [
    ("D级", 0.8, (0.0, 0.25)),
    ("C级", 1.0, (0.25, 0.50)),
    ("B级", 1.25, (0.50, 0.75)),
    ("A级", 1.6, (0.75, 0.90)),
    ("S级", 2.2, (0.90, 0.98)),
    ("SS级", 3.2, (0.98, 1.00)),
]

def load_all_fishes():
    global _CACHED_FISHES
    if _CACHED_FISHES is not None and len(_CACHED_FISHES) > 0:
        return _CACHED_FISHES

    # 1. 优先读取已持久化的自定义或运行中 JSON
    if os.path.isfile(_FISH_JSON_PATH):
        try:
            with open(_FISH_JSON_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list) and len(data) > 0:
                    _CACHED_FISHES = data
                    return _CACHED_FISHES
        except Exception:
            pass

    # 2. 若 fishing_fishes.json 缺失或为空，自动从默认 105 种预设兜底并持久化
    if os.path.isfile(_FISH_DEFAULT_JSON_PATH):
        try:
            with open(_FISH_DEFAULT_JSON_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list) and len(data) > 0:
                    _CACHED_FISHES = data
                    save_all_fishes(data)
                    return _CACHED_FISHES
        except Exception:
            pass

    _CACHED_FISHES = []
    return _CACHED_FISHES

def save_all_fishes(fishes_list):
    global _CACHED_FISHES
    if not isinstance(fishes_list, list):
        return False
    try:
        os.makedirs(_DATA_DIR, exist_ok=True)
        with open(_FISH_JSON_PATH, "w", encoding="utf-8") as f:
            json.dump(fishes_list, f, ensure_ascii=False, indent=2)
        _CACHED_FISHES = fishes_list
        return True
    except Exception:
        return False

def reset_default_fishes():
    """从 fishing_fishes_default.json 恢复初始 105 种鱼类"""
    global _CACHED_FISHES
    if os.path.isfile(_FISH_DEFAULT_JSON_PATH):
        try:
            with open(_FISH_DEFAULT_JSON_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list) and len(data) > 0:
                    save_all_fishes(data)
                    return True, len(data)
        except Exception as e:
            return False, str(e)
    return False, "默认鱼类配置文件不存在"

def get_fish_by_id(fish_id):
    fishes = load_all_fishes()
    for f in fishes:
        if f.get("id") == fish_id:
            return f
    return None

def roll_random_fish(bonus_luck=0.0):
    """根据品质权重与幸运值随机抽取一条鱼"""
    fishes = load_all_fishes()
    if not fishes:
        return {
            "id": "f_default",
            "name": "野生鲫鱼",
            "zone": "淡水湖泊与溪流",
            "quality": "白色普通",
            "size": "小型",
            "min_weight": 0.2,
            "max_weight": 0.8,
            "base_price": 40,
            "icon": "🐟",
            "desc": "一条活蹦乱跳的野生鲫鱼。"
        }

    # 1. 计算品质抽取概率 (幸运值提升高品质权重)
    weights = {}
    luck_factor = 1.0 + max(0.0, min(1.0, bonus_luck))
    for q, w in QUALITY_WEIGHTS.items():
        if q in ("紫色史诗", "橙色传说", "幻彩神话"):
            weights[q] = int(w * luck_factor)
        else:
            weights[q] = w

    # 按品质分组鱼类
    by_quality = {}
    for f in fishes:
        q = f.get("quality", "白色普通")
        by_quality.setdefault(q, []).append(f)

    # 抽取品质
    qualities = list(weights.keys())
    w_list = [weights[q] for q in qualities]
    chosen_quality = random.choices(qualities, weights=w_list, k=1)[0]

    cand_list = by_quality.get(chosen_quality) or fishes
    fish = random.choice(cand_list)

    # 2. 抽取重量与评级
    # 评级概率分布：D:20%, C:35%, B:25%, A:12%, S:6%, SS:2%
    grade_weights = [200, 350, 250, 120, 60, 20]
    if bonus_luck > 0:
        grade_weights[4] = int(grade_weights[4] * (1.0 + bonus_luck))
        grade_weights[5] = int(grade_weights[5] * (1.0 + bonus_luck * 1.5))

    chosen_grade_info = random.choices(WEIGHT_GRADES, weights=grade_weights, k=1)[0]
    grade_name, price_mult, (pct_lo, pct_hi) = chosen_grade_info

    min_w = float(fish.get("min_weight", 0.5))
    max_w = float(fish.get("max_weight", 2.0))
    w_span = max(0.05, max_w - min_w)

    rand_pct = pct_lo + random.random() * (pct_hi - pct_lo)
    actual_weight = round(min_w + w_span * rand_pct, 2)
    is_gold_crown = (grade_name == "SS级")

    base_p = int(fish.get("base_price", 50))
    final_val = max(1, int(base_p * price_mult))

    return {
        "fish_id": fish.get("id", "f001"),
        "name": fish.get("name", "未知鱼类"),
        "zone": fish.get("zone", "淡水湖泊与溪流"),
        "quality": fish.get("quality", "白色普通"),
        "quality_label": QUALITY_COLORS.get(fish.get("quality"), "⚪普通"),
        "size": fish.get("size", "小型"),
        "weight": actual_weight,
        "grade": grade_name,
        "is_gold_crown": is_gold_crown,
        "price": final_val,
        "icon": fish.get("icon", "🐟"),
        "desc": fish.get("desc", ""),
    }
