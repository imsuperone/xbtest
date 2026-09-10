# -*- coding: utf-8 -*-
"""English mapping for legacy CN keys (INI → DB) and prop pinyin.
道具键 pinyin 化，文案保持中文显示。
"""
# 基础账户/档案英文化（子层 JSON keys）
BASE_CN_TO_EN = {
    # 账户通用
    "发言总数": "message_count",
    "开户时间": "register_time",
    "现金总数": "cash_total",
    "体力总数": "stamina",
    "魅力总数": "charm",
    "奖券总数": "lottery_tickets",
    "签到次数": "sign_count",
    "签到日期": "sign_date",
    "新手礼包": "novice_gift",
    "存款总数": "deposit",
    "坐骑": "rides",
    "坐骑属性": "ride_type",
    # 奴隶档案
    "身价": "price",
    "主人": "owner",
    "买入价格": "purchase_price",
    "购买时间": "purchase_time",
    "保护时间": "protect_until",
    "保护时长": "protect_until",
    "奴隶位": "slave_slots",
    "学习时间": "study_time",
    "折磨时间": "torture_time",
    "打架时间": "fight_time",
    "打赏时间": "tip_time",
    "讨好时间": "flatter_time",
    "造反时间": "revolt_time",
    "自由时间": "free_time",
    "货币时间": "coin_time",
    "打工时间": "work_time",
    "打工工资": "work_wage",
    "打工状态": "work_status",
    "武器": "weapon",
    "武器经验": "weapon_exp",
    "宝物": "treasure",
    "连签天数": "consecutive_days",
    "赎身时间": "ransom_time",
    # 签到/娱乐扩展
    "上次签到日期": "last_sign_date",
    "抽奖连败": "lottery_lose_streak",
    "点赞日期": "like_date",
    "点赞数": "like_count",
    # 内部临时
    "_work_wage": "_work_wage",
    "name": "name",
    "pray_date": "pray_date",
    # 兼容旧键
    "现金": "cash_total",
    "金币": "cash_total",
    "货币": "cash_total",
    "金钱": "cash_total",
    "存款": "deposit",
    "体力": "stamina",
    "魅力": "charm",
    "奖券": "lottery_tickets",
    # 帮派/精灵顶层
    "帮派": "guild",
    "精灵": "spirits",
    # 坐骑已在上方
    # 旧版 pinyin 兼容（测试脚本使用）
    "tili": "stamina",
    "meili": "charm",
    "cunkuan": "deposit",
    "jiangquan": "lottery_tickets",
    "监狱": "jail",
    "劫时间": "rob_bank_time",
    "打劫时间": "rob_time",
    "赌博时间": "gamble_time",
}

# 道具名（中文 → pinyin）键英文化，文案中文显示
PROP_CN_TO_EN = {
    # 武器（SSR）
    "鬼泪村正": "guileicunzheng",
    "雷鸣剑": "leimingjian",
    "神使沧溟": "shenshicangming",
    "炎宿朱雀": "yanshuzhuque",
    "祝融": "zhurong",
    "钻石剑": "zuanshijian",
    "老八脑!": "laobanao",
    "老八脑！": "laobanao",
    # 宝物
    "酒神葫芦": "jiushenhulu",
    "四象护符": "sixianghufu",
    # 坐骑
    "企鹅": "qie",
    "伞兵": "sanbing",
    "宝驴": "baolv",
    "保时捷": "baoshijie",
    "法拉利": "falali",
    "玛莎拉蒂": "mashaladi",
    "劳斯莱斯": "laosisilaisi",
    "布加迪威龙": "bugadiweilong",
    "私人航空": "sirenhangkong",
    "老八": "laoba",
    "摩托车": "motuoche",
    # 精灵商店道具
    "精灵球": "jinglingqiu",
    "时间球": "shijianqiu",
    "狩猎球": "shoulieqiu",
    "极速球": "jisuqiu",
    "大师球": "dashiqiu",
    "奇异甜食": "qiyitianshi",
    "吐司": "tusi",
    "攻击之源": "gongjizhiyuan",
    "防御之源": "fangyuzhiyuan",
    "特防之源": "tefangzhiyuan",
    "特攻之源": "tegongzhiyuan",
    "进化液": "jinhuaye",
}

# 反向（英文 → 中文）已退役：显示层直接存中文，无任何调用，删除防误用

def _strip_suffix(key: str):
    """处理 升星/升阶 后缀，返回 (base, suffix)"""
    if key.endswith("升星"):
        return key[:-2], "_star"
    if key.endswith("升阶"):
        return key[:-2], "_stage"
    return key, ""

# 千群千人热点：cn_to_en 被 Acct.get/set 每操作调用数次，16k/2k=8次/消息，缓存可降 0.07s
try:
    from functools import lru_cache as _lru
except Exception:
    def _lru(*a, **k):
        def d(f): return f
        return d

@_lru(maxsize=4096)
def _cn_to_en_cached(key: str) -> str:
    # 内层无缓存逻辑，供 lru 包裹
    if not key:
        return key
    if key in BASE_CN_TO_EN:
        return BASE_CN_TO_EN[key]
    if key in PROP_CN_TO_EN:
        return PROP_CN_TO_EN[key]
    base, suf = _strip_suffix(key)
    if suf and base in PROP_CN_TO_EN:
        return PROP_CN_TO_EN[base] + suf
    has_cn = any('\u4e00' <= c <= '\u9fff' for c in key)
    if has_cn:
        for cn, en in PROP_CN_TO_EN.items():
            if cn in key:
                key = key.replace(cn, en)
        out = []
        for ch in key:
            if '\u4e00' <= ch <= '\u9fff':
                out.append(f"u{ord(ch):04x}")
            else:
                if ch in ("!", "！", " ", "|", "/"):
                    out.append("_")
                else:
                    out.append(ch)
        res = "".join(out)
        import re
        res = re.sub(r"_+", "_", res).strip("_")
        return res.lower()
    return key

def cn_to_en(key: str) -> str:
    """中文键 → 英文键；带 LRU 缓存，千群高频热点"""
    return _cn_to_en_cached(key)

def translate_dict(cn_dict: dict) -> dict:
    """批量翻译 dict 的 keys（中文 → 英文），值保持中文文案不变"""
    out = {}
    for k, v in (cn_dict or {}).items():
        nk = cn_to_en(str(k))
        out[nk] = v
    return out
