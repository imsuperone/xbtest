# -*- coding: utf-8 -*-
"""games/fishing/engine.py — 钓鱼与迷你世界水族馆核心业务引擎。
涵盖打窝发酵、水桶满额前置拦截、垂钓演出、鱼类回收、水族馆放置生息、
生态水质衰减防通胀、群友偷鱼博弈与奴隶造反偷鱼深度联动。
"""
import time
import math
import random
import re
from .data_fishes import roll_random_fish, load_all_fishes, QUALITY_COLORS

# 鱼饵预设规格：(价格, 发酵培育分钟, 塘主保护分钟, 可钓次数)
BAITS = {
    "蚯蚓": {"id": 1, "price": 100, "mature_min": 30, "protect_min": 15, "casts": 3, "desc": "基础活饵，适合新手起步快速聚鱼。"},
    "面饵": {"id": 2, "price": 500, "mature_min": 60, "protect_min": 30, "casts": 5, "desc": "谷物清香，发酵聚鱼稳定，性价比出众。"},
    "红虫": {"id": 3, "price": 1500, "mature_min": 90, "protect_min": 45, "casts": 8, "desc": "浓腥诱鱼，大幅提升高品质稀有鱼概率。"},
    "虾肉": {"id": 4, "price": 5000, "mature_min": 120, "protect_min": 60, "casts": 12, "desc": "极品生鲜，极大概率吸引珍稀大鱼与双S金冠。"},
}

BAIT_ALIASES = {
    "1": "蚯蚓", "一": "蚯蚓", "蚯蚓": "蚯蚓", "蚯蚓饵": "蚯蚓",
    "2": "面饵", "二": "面饵", "面饵": "面饵", "面团": "面饵", "酒米": "面饵", "颗粒": "面饵", "复合颗粒窝料": "面饵",
    "3": "红虫", "三": "红虫", "红虫": "红虫", "红虫饵": "红虫", "香精": "红虫", "秘制红虫香精": "红虫",
    "4": "虾肉", "四": "虾肉", "虾肉": "虾肉", "虾": "虾肉", "虾饵": "虾肉", "梦幻龙涎诱饵": "虾肉", "龙涎": "虾肉",
}

DEFAULT_BUCKET_CAP = 10
MAX_BUCKET_CAP = 30
DEFAULT_AQUARIUM_CAP = 10
MAX_AQUARIUM_CAP = 30

WATER_CLEAN_COST = 200  # 换水恢复 100 点水质所需金币
BASE_INTEREST_RATE = 0.012  # 水族馆满水质时基准每小时利息 1.2%
MAX_DAILY_INTEREST = 100000  # 每日水族馆利息硬上限 10w 金币

def _calc_diminishing_interest(current_daily, raw_gain, cap=100000):
    """方案 3：软着陆平滑衰减模式 (死上限 10w)
    • 0 ~ 50,000: 100% 全额产生
    • 50,000 ~ 100,000: 50% 折半平滑软衰减
    • 达到 100,000: 硬封顶，当日不再增加
    """
    if current_daily >= cap or raw_gain <= 0:
        return 0
    gain = 0
    remain_raw = raw_gain
    cur = current_daily

    # 阶段 1: 0 ~ 50,000 (100% 全额)
    if cur < 50000:
        span1 = min(remain_raw, 50000 - cur)
        gain += span1
        cur += span1
        remain_raw -= span1

    # 阶段 2: 50,000 ~ 100,000 (50% 软衰减)
    if remain_raw > 0 and cur < cap:
        avail_room = cap - cur
        span2_raw = min(remain_raw, avail_room * 2)
        span2_gain = int(span2_raw * 0.5)
        gain += span2_gain
        cur += span2_gain
        remain_raw -= span2_raw

    if current_daily + gain > cap:
        gain = max(0, cap - current_daily)
    return gain

def _get_st():
    try:
        from ...core import storage as ST
        return ST
    except (ImportError, ValueError):
        pass
    try:
        from ..core import storage as ST
        return ST
    except (ImportError, ValueError):
        pass
    try:
        from core import storage as ST
        return ST
    except ImportError:
        import storage as ST
        return ST

def _get_data(gid, qq):
    ST = _get_st()
    a = ST.acct(gid, qq)
    raw = a.get("fishing", "{}")
    d = {}
    try:
        import json as _j
        if raw and raw not in ("0", "None"):
            parsed = _j.loads(raw)
            if isinstance(parsed, dict):
                d = parsed
    except Exception:
        d = {}

    # 补齐默认结构
    d.setdefault("bucket", [])
    d.setdefault("bucket_cap", DEFAULT_BUCKET_CAP)
    d.setdefault("aquarium", {
        "name": "水族馆",
        "capacity": DEFAULT_AQUARIUM_CAP,
        "water_quality": 100,
        "fishes": [],
        "last_settle_ts": int(time.time()),
        "daily_earned": 0,
        "daily_date": time.strftime("%Y-%m-%d"),
        "renamed": False
    })
    d.setdefault("pond", None)
    d.setdefault("atlas", {})
    return d

def _save_data(gid, qq, data):
    ST = _get_st()
    a = ST.acct(gid, qq)
    import json as _j
    a.set("fishing", _j.dumps(data, ensure_ascii=False))
    ST.acct_save(gid, qq)

def _get_coins(gid, qq):
    ST = _get_st()
    try:
        return ST.coins_get(gid, qq)
    except Exception:
        return 0

def _add_coins(gid, qq, delta):
    ST = _get_st()
    try:
        return ST.coins_add(gid, qq, delta)
    except Exception:
        return None

def _get_stamina(gid, qq):
    ST = _get_st()
    try:
        a = ST.acct(gid, qq)
        return a.int("stamina")
    except Exception:
        return 100

def _sub_stamina(gid, qq, amt=1):
    ST = _get_st()
    try:
        a = ST.acct(gid, qq)
        cur = a.int("stamina")
        a.set("stamina", str(max(0, cur - amt)))
        ST.acct_save(gid, qq)
    except Exception:
        pass

# ==================== 水族馆离线利息与水质结算 ====================
def _settle_aquarium(data):
    """自动结算水族馆挂机利息与水质健康度衰减"""
    aq = data.get("aquarium", {})
    now = int(time.time())
    last = int(aq.get("last_settle_ts") or now)
    cur_water = int(aq.get("water_quality", 100))
    elapsed_hours = min(72, max(0, (now - last) // 3600))
    if elapsed_hours <= 0:
        return 0, cur_water

    today = time.strftime("%Y-%m-%d")
    if aq.get("daily_date") != today:
        aq["daily_date"] = today
        aq["daily_earned"] = 0

    fishes = aq.get("fishes", [])
    total_val = sum(int(f.get("price", 0)) for f in fishes)
    cur_water = int(aq.get("water_quality", 100))

    earned_gold = 0
    decay_per_hour = 2.0
    # 若有神话/超大鱼，略微加速衰减
    for f in fishes:
        if f.get("quality") == "幻彩神话" or f.get("size") == "超大型":
            decay_per_hour += 0.5

    for _ in range(int(elapsed_hours)):
        # 水质效率档位
        if cur_water >= 80:
            eff = 1.05  # 全额加 5% 小费
        elif cur_water >= 50:
            eff = 0.70
        elif cur_water >= 20:
            eff = 0.30
        else:
            eff = 0.0  # 暂停产出

        raw_gold = int(total_val * BASE_INTEREST_RATE * eff)
        h_gold = _calc_diminishing_interest(aq.get("daily_earned", 0), raw_gold, MAX_DAILY_INTEREST)

        earned_gold += h_gold
        aq["daily_earned"] = aq.get("daily_earned", 0) + h_gold
        cur_water = max(0, int(cur_water - decay_per_hour))

    aq["water_quality"] = cur_water
    aq["last_settle_ts"] = now
    return earned_gold, cur_water

# ==================== 指令 1：打窝培育 ====================
def cmd_bait(gid, qq, bait_name):
    ST = _get_st()
    b_raw = str(bait_name or "").strip()
    if not b_raw:
        lines = [
            "🌾 鱼饵与打窝配方清单",
            "━━━━━━━━━━━━",
        ]
        num_emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣"]
        for idx, (k, v) in enumerate(BAITS.items()):
            emoji = num_emojis[idx] if idx < len(num_emojis) else f"{idx+1}."
            lines.append(
                f"{emoji}【{k}】 售价: {v['price']} {ST.coin_name()}\n"
                f"• 培育: {v['mature_min']}分钟 | 保护: {v['protect_min']}分钟 | 垂钓: {v['casts']}次\n"
                f"• 简介: {v['desc']}"
            )
            if idx < len(BAITS) - 1:
                lines.append("")
        lines.append("━━━━━━━━━━━━")
        lines.append("💡 发送数字或名称快捷打窝：")
        lines.append("👉 发送【打窝 1】或【打窝 蚯蚓】")
        lines.append("👉 发送【打窝 2】或【打窝 面饵】")
        lines.append("👉 发送【打窝 3】或【打窝 红虫】")
        lines.append("👉 发送【打窝 4】或【打窝 虾肉】")
        return "\n".join(lines)

    # 规范化名称与数字别名映射
    b_name = BAIT_ALIASES.get(b_raw)
    if not b_name:
        for ak, av in BAIT_ALIASES.items():
            if b_raw in ak:
                b_name = av
                break
    if not b_name or b_name not in BAITS:
        return (
            f"❌ 未找到鱼饵【{bait_name}】哦！\n"
            "━━━━━━━━━━━━\n"
            "💡 可用鱼饵：1.蚯蚓 / 2.面饵 / 3.红虫 / 4.虾肉\n"
            "👉 请直接发送【打窝 1】至【打窝 4】挑选打窝！"
        )

    spec = BAITS[b_name]
    cost = spec["price"]

    d = _get_data(gid, qq)
    now = int(time.time())
    old_pond = d.get("pond")
    if old_pond and old_pond.get("is_active"):
        m_ts = old_pond.get("mature_ts", 0)
        p_ts = old_pond.get("protect_end_ts", 0)
        rem = old_pond.get("remain_casts", 0)
        if rem > 0 and now < p_ts + 7200:
            return f"⚠️ 您当前已有一个正在生效的鱼塘（尚余 {rem} 次垂钓机会）！\n请先发送【钓鱼】将现有鱼塘收完，或等待鱼塘自然干涸后再打新窝哦~"

    coins = _get_coins(gid, qq)
    if coins < cost:
        return f"❌ 金币不足！购买【{b_name}】需要 {cost} {ST.coin_name()}，您当前仅有 {coins} {ST.coin_name()}。"

    if _add_coins(gid, qq, -cost) is None:
        return "❌ 扣除金币失败，请稍后重试。"

    mature_sec = spec["mature_min"] * 60
    protect_sec = spec["protect_min"] * 60
    d["pond"] = {
        "bait": b_name,
        "start_ts": now,
        "mature_ts": now + mature_sec,
        "protect_end_ts": now + mature_sec + protect_sec,
        "remain_casts": spec["casts"],
        "total_casts": spec["casts"],
        "is_active": True,
    }
    _save_data(gid, qq, data=d)

    return (
        f"🌾【打窝培育成功】\n"
        f"━━━━━━━━━━━━\n"
        f"• 投放鱼饵：【{b_name}】（花费 {cost} {ST.coin_name()}）\n"
        f"• 培育发酵：{spec['mature_min']} 分钟（预计 {time.strftime('%H:%M', time.localtime(now + mature_sec))} 成熟）\n"
        f"• 塘主保护：{spec['protect_min']} 分钟（成熟后专享独占）\n"
        f"• 预估渔获：可供垂钓 {spec['casts']} 次\n"
        f"━━━━━━━━━━━━\n"
        f"💡 发送【鱼塘】可随时查看水域成熟与保护期倒计时"
    )

# ==================== 指令 2：查看鱼塘状态 ====================
def cmd_pond(gid, qq):
    ST = _get_st()
    d = _get_data(gid, qq)
    now = int(time.time())
    pond = d.get("pond")
    if not pond or not pond.get("is_active"):
        return "🌊 您当前还没有打窝建立鱼塘哦~ 发送【打窝】挑选鱼饵开始培育吧！"

    b_name = pond.get("bait", "普通窝料")
    m_ts = pond.get("mature_ts", 0)
    p_ts = pond.get("protect_end_ts", 0)
    rem = pond.get("remain_casts", 0)
    tot = pond.get("total_casts", 0)
    stolen_by = pond.get("stolen_by", [])
    stolen_tip = f"\n• 遭窃记录：已被群友偷取 {len(stolen_by)} 次" if stolen_by else ""

    if now < m_ts:
        diff_min = max(1, math.ceil((m_ts - now) / 60))
        status_txt = f"⏳ 深度发酵中（还需约 {diff_min} 分钟成熟，鱼群聚拢中）"
    elif now < p_ts:
        diff_min = max(1, math.ceil((p_ts - now) / 60))
        status_txt = f"🌟 已成熟 · 塘主独享保护期（还剩 {diff_min} 分钟保护，群友无法偷鱼）"
    elif rem > 0:
        status_txt = "🔓 公共偷鱼期（保护期已结束，群友可发送【偷鱼】偷取剩余渔获！）"
    else:
        status_txt = "🍂 鱼群已完全被钓完，水质清澈干涸"

    return (
        "🏞️ 专属鱼塘实时状态\n"
        "━━━━━━━━━━━━\n"
        f"• 投放鱼饵：【{b_name}】\n"
        f"• 鱼塘阶段：{status_txt}\n"
        f"• 剩余渔获：{rem} / {tot} 次{stolen_tip}\n"
        "━━━━━━━━━━━━\n"
        "💡 成熟后发送【钓鱼】挥竿起鱼，谨防群友偷鱼"
    )

# ==================== 指令 3：即时垂钓 (含水桶满仓前置拦截) ====================
def cmd_fish(gid, qq):
    ST = _get_st()
    d = _get_data(gid, qq)
    now = int(time.time())

    # ★★★ 硬核需求：垂钓前强制检测水桶容量，满仓前置拦截，绝不扣体力与次数 ★★★
    bucket = d.get("bucket", [])
    bucket_cap = int(d.get("bucket_cap", DEFAULT_BUCKET_CAP))
    if len(bucket) >= bucket_cap:
        return (
            f"⚠️ 您的水桶已经装满啦（{len(bucket)}/{bucket_cap} 条）！\n"
            f"已经装不下更多的大鱼了哦~ 竿梢已被阻断！\n"
            f"━━━━━━━━━━━━\n"
            f"💡 请先发送【出售】清空卖出渔获换取金币，\n"
            f"   或发送【存鱼 <序号>】放入水族馆展出腾出空间后再来垂钓吧！"
        )

    pond = d.get("pond")
    if not pond or not pond.get("is_active") or pond.get("remain_casts", 0) <= 0:
        return "🌊 您当前没有已成熟的鱼塘哦！请先发送【打窝】使用鱼饵建立属于您的鱼塘~"

    m_ts = pond.get("mature_ts", 0)
    if now < m_ts:
        diff_min = max(1, math.ceil((m_ts - now) / 60))
        return f"⏳ 鱼塘仍在发酵聚鱼中（还剩约 {diff_min} 分钟）！浮漂纹丝不动，请稍后再来挥竿哦~"

    # 体力判定
    sta = _get_stamina(gid, qq)
    if sta < 1:
        return "😫 您的体力不足啦（需要 1 点体力挥竿）！请稍事休息恢复体力后再来垂钓~"

    _sub_stamina(gid, qq, 1)

    # 消耗一次钓鱼机会
    pond["remain_casts"] = max(0, pond.get("remain_casts", 1) - 1)
    if pond["remain_casts"] == 0:
        pond["is_active"] = False

    # 计算图鉴与幸运加成
    atlas = d.get("atlas", {})
    atlas_count = len(atlas)
    bonus_luck = 0.0
    if atlas_count >= 60:
        bonus_luck = 0.35  # 图鉴解锁60种以上大增益
    elif atlas_count >= 30:
        bonus_luck = 0.15

    # 抽取渔获
    caught = roll_random_fish(bonus_luck=bonus_luck)
    caught["catch_ts"] = now
    bucket.append(caught)

    # 更新图鉴数据
    f_id = caught.get("fish_id")
    rec = atlas.get(f_id, {"count": 0, "max_weight": 0.0, "has_crown": False})
    rec["count"] = rec.get("count", 0) + 1
    if caught.get("weight", 0) > rec.get("max_weight", 0):
        rec["max_weight"] = caught.get("weight", 0)
    if caught.get("is_gold_crown"):
        rec["has_crown"] = True
    atlas[f_id] = rec

    _save_data(gid, qq, d)

    crown_tag = " 👑【双S金冠】" if caught.get("is_gold_crown") else ""
    return (
        f"🎣 嗖——竿梢剧烈下弯！用力提竿，水花四溅！\n"
        f"━━━━━━━━━━━━\n"
        f"{caught.get('icon', '🐟')} 捕获渔获：[{caught.get('quality_label')}] 【{caught.get('name')}】{crown_tag}\n"
        f"📏 体型规格：{caught.get('size')} | ⚖️ 重量：{caught.get('weight')} kg ({caught.get('grade')})\n"
        f"💰 预估身价：{caught.get('price')} {ST.coin_name()}\n"
        f"📦 已放入水桶：{len(bucket)} / {bucket_cap} 条（鱼塘尚余 {pond.get('remain_casts')} 次）\n"
        f"━━━━━━━━━━━━\n"
        f"💡 简介：{caught.get('desc')}\n"
        f"👉 发送【水桶】查看全部渔获，发送【出售】变现金币，或【存鱼】入住水族馆！"
    )

# ==================== 指令 4：水桶查看 ====================
def cmd_bucket(gid, qq):
    ST = _get_st()
    d = _get_data(gid, qq)
    bucket = d.get("bucket", [])
    bucket_cap = int(d.get("bucket_cap", DEFAULT_BUCKET_CAP))

    if not bucket:
        return f"🪣 您的水桶空空如也（0/{bucket_cap}）！快去专属鱼塘【钓鱼】吧~"

    total_val = sum(int(f.get("price", 0)) for f in bucket)
    lines = [
        f"🪣 渔获水桶 (存量: {len(bucket)}/{bucket_cap} · 总估值: {total_val:,} {ST.coin_name()})",
        "━━━━━━━━━━━━",
    ]
    for idx, f in enumerate(bucket, 1):
        crown = " 👑" if f.get("is_gold_crown") else ""
        lines.append(f"{idx}. [{f.get('quality_label')}] {f.get('name')}{crown} ({f.get('weight')}kg · {f.get('price')}金币)")
    lines.append("━━━━━━━━━━━━")
    lines.append("【出售 <序号>】卖出单条鱼")
    lines.append("【存鱼 <序号>】将鱼存入水族馆")
    lines.append("【一键出售】卖出所有鱼")
    return "\n".join(lines)

# ==================== 指令 5：出售渔获 ====================
def cmd_sell(gid, qq, arg=""):
    ST = _get_st()
    d = _get_data(gid, qq)
    bucket = d.get("bucket", [])
    if not bucket:
        return "🪣 您的水桶里没有鱼可以出售哦！"

    arg = (arg or "").strip()
    if arg.isdigit():
        idx = int(arg) - 1
        if idx < 0 or idx >= len(bucket):
            return f"❌ 序号无效！水桶内目前仅有 1 ~ {len(bucket)} 号渔获。"
        fish = bucket.pop(idx)
        val = int(fish.get("price", 0))
        ST.coins_add(gid, qq, val)
        _save_data(gid, qq, d)
        return f"💰【单条出售成功】您成功卖出了 [{fish.get('quality_label')}] 【{fish.get('name')}】，获得 {val:,} {ST.coin_name()}！"
    elif arg in ("全部", "all", "所有", "一键", "一键出售"):
        count = len(bucket)
        total_val = sum(int(f.get("price", 0)) for f in bucket)
        bucket.clear()
        ST.coins_add(gid, qq, total_val)
        _save_data(gid, qq, d)
        return f"💰【一键出售成功】成功出售水桶中全部 {count} 条渔获，共获得 {total_val:,} {ST.coin_name()}！"
    else:
        return (
            "💡 出售渔获提示：\n"
            "• 发送【出售 <序号>】卖出单条指定鱼，例如：出售 1\n"
            "• 发送【一键出售】卖出水桶中的所有鱼"
        )

# ==================== 指令 6：水族馆展示与改名 ====================
def cmd_aquarium(gid, qq):
    ST = _get_st()
    d = _get_data(gid, qq)
    earned, cur_water = _settle_aquarium(d)
    _save_data(gid, qq, d)

    if earned > 0:
        ST.coins_add(gid, qq, earned)

    aq = d.get("aquarium", {})
    name = aq.get("name", "水族馆")
    fishes = aq.get("fishes", [])
    cap = int(aq.get("capacity", DEFAULT_AQUARIUM_CAP))
    total_val = sum(int(f.get("price", 0)) for f in fishes)

    # 计算当前每小时预期利息
    eff = 1.05 if cur_water >= 80 else (0.7 if cur_water >= 50 else (0.3 if cur_water >= 20 else 0.0))
    expected_interest = int(total_val * BASE_INTEREST_RATE * eff)

    settle_tip = f"\n🎉 刚刚为您结算了离线利息 +{earned:,} {ST.coin_name()}！" if earned > 0 else ""
    water_tip = "✨ 纯净(+5%加成)" if cur_water >= 80 else ("⚠️ 微浊(70%产出)" if cur_water >= 50 else "🚨 浑浊(产出低下)")

    lines = [
        f"🏛️ 展馆：【{name}】 (展出: {len(fishes)}/{cap}){settle_tip}",
        "━━━━━━━━━━━━",
        f"• 水质健康：{cur_water}/100 ({water_tip})",
        f"• 馆藏估值：{total_val:,} {ST.coin_name()}",
        f"• 门票时息：+{expected_interest:,} {ST.coin_name()}/时 (今日: {aq.get('daily_earned', 0):,}/{MAX_DAILY_INTEREST:,})",
        "━━━━━━━━━━━━",
    ]
    if not fishes:
        lines.append("🪹 展馆内暂无名鱼展出~ 发送【存鱼 <序号>】可将水桶大鱼转移放入！")
    else:
        for idx, f in enumerate(fishes, 1):
            crown = " 👑" if f.get("is_gold_crown") else ""
            h_int = max(1, int(int(f.get("price", 0)) * BASE_INTEREST_RATE * eff))
            lines.append(f"{idx}. [{f.get('quality_label')}] {f.get('name')}{crown} (时息 +{h_int})")
    lines.append("━━━━━━━━━━━━")
    lines.append("【取鱼 <序号>】取出单条鱼")
    lines.append("【换水】将水质恢复至满状态")
    lines.append("【水族馆改名 <名称>】自定义招牌！")
    return "\n".join(lines)

def cmd_rename_aquarium(gid, qq, new_name):
    ST = _get_st()
    n = new_name.strip()
    if not n or len(n) < 2 or len(n) > 12:
        return "❌ 水族馆名字长度必须在 2 ~ 12 个字之间哦！"

    d = _get_data(gid, qq)
    aq = d.get("aquarium", {})
    is_renamed = aq.get("renamed", False)

    if is_renamed:
        cost = 5000
        coins = _get_coins(gid, qq)
        if coins < cost:
            return f"❌ 再次改名需要花费 {cost} {ST.coin_name()}，您当前仅有 {coins} {ST.coin_name()}。"
        _add_coins(gid, qq, -cost)

    aq["name"] = n
    aq["renamed"] = True
    _save_data(gid, qq, d)
    return f"✨【水族馆改名成功】您的水族馆专属名称已更新为：【{n}】！"

def cmd_store_fish(gid, qq, arg):
    d = _get_data(gid, qq)
    bucket = d.get("bucket", [])
    aq = d.get("aquarium", {})
    fishes = aq.get("fishes", [])
    cap = int(aq.get("capacity", DEFAULT_AQUARIUM_CAP))

    if not arg or not arg.strip().isdigit():
        return "❌ 请输入要存放的水桶鱼序号，例如：【存鱼 1】。"

    idx = int(arg.strip()) - 1
    if idx < 0 or idx >= len(bucket):
        return f"❌ 序号无效！水桶内目前仅有 1 ~ {len(bucket)} 号渔获。"

    if len(fishes) >= cap:
        return f"⚠️ 水族馆展位已满（{len(fishes)}/{cap}）！放不下更多展鱼啦。"

    fish = bucket.pop(idx)
    fishes.append(fish)
    _save_data(gid, qq, d)
    return f"🏛️ 成功将 [{fish.get('quality_label')}] 【{fish.get('name')}】转移至水族馆展出！每小时都将为您产生门票利息~"

def cmd_take_fish(gid, qq, arg):
    d = _get_data(gid, qq)
    bucket = d.get("bucket", [])
    bucket_cap = int(d.get("bucket_cap", DEFAULT_BUCKET_CAP))
    aq = d.get("aquarium", {})
    fishes = aq.get("fishes", [])

    if not arg or not arg.strip().isdigit():
        return "❌ 请输入要取出的水族馆展鱼序号，例如：【取鱼 1】。"

    idx = int(arg.strip()) - 1
    if idx < 0 or idx >= len(fishes):
        return f"❌ 序号无效！水族馆内目前仅有 1 ~ {len(fishes)} 号展鱼。"

    if len(bucket) >= bucket_cap:
        return f"⚠️ 您的水桶已满（{len(bucket)}/{bucket_cap}）！请先【出售】腾出水桶空位后再取出。"

    fish = fishes.pop(idx)
    bucket.append(fish)
    _save_data(gid, qq, d)
    return f"🪣 已将 [{fish.get('quality_label')}] 【{fish.get('name')}】从水族馆取出并放回水桶，现在可以发送【出售】变现啦！"

def cmd_clean_water(gid, qq):
    ST = _get_st()
    d = _get_data(gid, qq)
    earned, cur_water = _settle_aquarium(d)
    if earned > 0:
        ST.coins_add(gid, qq, earned)
    aq = d.get("aquarium", {})
    cur_water = int(aq.get("water_quality", 100))
    if cur_water >= 100:
        if earned > 0:
            _save_data(gid, qq, d)
        return "💧 您的水族馆水质清澈纯净（100/100），暂时无需换水哦！"

    coins = _get_coins(gid, qq)
    if coins < WATER_CLEAN_COST:
        return f"❌ 金币不足！清洁换水需要 {WATER_CLEAN_COST} {ST.coin_name()}，您当前仅有 {coins}。"

    if _add_coins(gid, qq, -WATER_CLEAN_COST) is None:
        return "❌ 扣费失败，请稍后重试。"

    aq["water_quality"] = 100
    _save_data(gid, qq, d)
    return f"✨【换水保洁完成】花费 {WATER_CLEAN_COST} {ST.coin_name()}，水质恢复至 100 点纯净状态！享受全额门票利息 +5% 小费加成~"

# ==================== 指令 7：社交偷鱼与奴隶造反 ====================
def cmd_steal_fish(gid, qq, target_qq):
    ST = _get_st()
    try:
        from ..slave.nick import display_name
        from ..bank.common import _find_qq_by_name
    except (ImportError, ValueError):
        from games.slave.nick import display_name
        from games.bank.common import _find_qq_by_name

    raw_t = str(target_qq or "").strip()
    if not raw_t:
        return "❌ 请指定要偷取的群友，例如：【偷鱼 @张三】或【偷鱼 123456】。"

    # 1. 尝试从 CQ 码、[At:QQ]、@数字、纯数字或群昵称反查真实 QQ 号
    t_qq = None
    cq_m = re.search(r"(?:\[CQ:at,qq=(\d+)[^\]]*\]|\[At:\s*(\d+)\])", raw_t)
    if cq_m:
        t_qq = cq_m.group(1) or cq_m.group(2)
    else:
        clean = re.sub(r"<%.*?%>", "", raw_t)
        clean = re.sub(r"<[^>]+>", "", clean).lstrip("@").strip()
        num_m = re.search(r"(\d{5,12})", clean)
        if clean.isdigit() and 5 <= len(clean) <= 12:
            t_qq = clean
        elif num_m and len(clean) <= 12 and clean.isdigit():
            t_qq = clean
        else:
            t_cand = _find_qq_by_name(gid, raw_t) or _find_qq_by_name(gid, clean)
            if t_cand:
                t_qq = t_cand
            elif num_m:
                t_qq = num_m.group(1)

    if not t_qq or not str(t_qq).isdigit():
        return "❌ 未找到该群友或格式有误，请发送【偷鱼 @某人】或【偷鱼 QQ号】。"

    if str(t_qq) == str(qq):
        return "😅 不能偷自己的鱼塘哦！"

    target_name = display_name(gid, t_qq) or str(t_qq)
    t_data = _get_data(gid, t_qq)
    t_pond = t_data.get("pond")
    now = int(time.time())

    if not t_pond or not t_pond.get("is_active") or t_pond.get("remain_casts", 0) <= 0:
        return f"🍂 【{target_name}】当前没有可用或有剩余渔获的鱼塘哦~"

    m_ts = t_pond.get("mature_ts", 0)
    p_ts = t_pond.get("protect_end_ts", 0)

    if now < m_ts:
        return f"⏳ 【{target_name}】的鱼塘还在发酵培育中，连鱼影都没有呢，偷不到！"

    if now < p_ts:
        diff_min = max(1, math.ceil((p_ts - now) / 60))
        return f"🛡️ 【{target_name}】的鱼塘处于【塘主专属保护期】（还剩 {diff_min} 分钟），戒备森严，无法偷鱼！"

    # ★★★ 单人单轮打窝限偷 1 次 ★★★
    stolen_by = t_pond.setdefault("stolen_by", [])
    if str(qq) in stolen_by:
        return f"⚠️ 您在【{target_name}】的本轮鱼塘中已经偷过 1 次啦！每次打窝每人限偷 1 次，请给其他群友留点机会吧~"

    # 塘主防护坐骑判定 (30%~50% 概率防盗抓贼)
    try:
        try:
            from .. import ride as _ride_mod
        except (ImportError, ValueError):
            from games import ride as _ride_mod
        t_ride_info = _ride_mod._rides(gid, t_qq) if hasattr(_ride_mod, "_rides") else {}
        active_mount = t_ride_info.get("active", "")
        if active_mount:
            # 拥有坐骑有概率触发抓捕
            if random.random() < 0.40:
                fine = 200
                _add_coins(gid, qq, -fine)
                ST.coins_add(gid, t_qq, fine)
                return f"🚨【偷鱼被当场逮捕】目标塘主【{target_name}】养有神兽【{active_mount}】！您刚踩进鱼塘就被一口咬住，罚款 {fine} {ST.coin_name()}赔偿给塘主！"
    except Exception:
        pass

    # 偷鱼成功
    my_data = _get_data(gid, qq)
    my_bucket = my_data.get("bucket", [])
    my_cap = int(my_data.get("bucket_cap", DEFAULT_BUCKET_CAP))
    if len(my_bucket) >= my_cap:
        return f"⚠️ 您的水桶已满（{len(my_bucket)}/{my_cap}），偷来的鱼没地方装啦！请先清理水桶。"

    t_pond["remain_casts"] = max(0, t_pond.get("remain_casts", 1) - 1)
    if t_pond["remain_casts"] == 0:
        t_pond["is_active"] = False
    stolen_by.append(str(qq))
    _save_data(gid, t_qq, t_data)

    caught = roll_random_fish(bonus_luck=0.0)
    caught["catch_ts"] = now
    my_bucket.append(caught)
    _save_data(gid, qq, my_data)

    crown = " 👑" if caught.get("is_gold_crown") else ""
    return (
        f"🥷【偷鱼成功】趁着保护期结束，您悄悄潜入【{target_name}】的鱼塘！\n"
        f"捞起了一条 [{caught.get('quality_label')}] 【{caught.get('name')}】{crown} (身价 {caught.get('price')} {ST.coin_name()})！\n"
        f"对方鱼塘剩余渔获已被您消耗 1 次！"
    )

# ==================== 指令 8：图鉴查看 ====================
def cmd_atlas(gid, qq):
    d = _get_data(gid, qq)
    atlas = d.get("atlas", {})
    all_fishes = load_all_fishes()
    total_sp = len(all_fishes)
    unlocked = len(atlas)

    pct = round(unlocked / max(1, total_sp) * 100, 1)
    buff = "暂无加成"
    if pct >= 100:
        buff = "🌟 钓鱼大宗师：高品质概率 +50%，双S金冠概率翻倍！"
    elif pct >= 60:
        buff = "✨ 垂钓大师：高品质鱼概率 +35%，双S金冠概率 +50%！"
    elif pct >= 30:
        buff = "🌿 熟练钓手：高品质鱼概率 +15%！"

    crown_count = sum(1 for it in atlas.values() if it.get("has_crown"))

    return (
        f"📖【全水域鱼类收集图鉴】\n"
        f"━━━━━━━━━━━━\n"
        f"收集进度：{unlocked} / {total_sp} 种 ({pct}%)\n"
        f"👑 金冠收集：已捕获 {crown_count} 种双S金冠鱼\n"
        f"🔮 图鉴增益：{buff}\n"
        f"━━━━━━━━━━━━\n"
        f"💡 解锁更多图鉴即可永久提升垂钓极品大鱼概率！"
    )

def cmd_menu():
    return (
        "🎣 钓鱼与水族馆系统\n"
        "━━━━━━━━━━━━\n"
        "• 打窝 [1-4/饵名] 投放鱼饵聚鱼（发送【打窝】查配方）\n"
        "• 鱼塘 查看发酵进度、保护期与剩余次数\n"
        "• 钓鱼 / 抛竿 挥竿起鱼（智能水桶满仓拦截）\n"
        "• 水桶 查看渔获水桶（支持出售、一键出售与存鱼）\n"
        "• 水族馆 查看展馆名鱼与利息（支持取鱼、换水与改名）\n"
        "• 偷鱼 @群友 偷取已成熟且过保护期的鱼塘\n"
        "• 钓鱼图鉴 查看鱼类图鉴解锁进度与概率加成\n"
        "━━━━━━━━━━━━\n"
        "💡 发送【钓鱼系统】或【钓鱼菜单】可唤醒本菜单"
    )
