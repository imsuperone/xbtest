# -*- coding: utf-8 -*-
"""精灵系统(宝可梦式) - 对齐 open.xb 原版指令/文案/数据
数据源: games/data_spirit.py(从 open.xb.app.dll 字符串池保真提取)
机制: 领养初始精灵 -> 野外精灵冒险遭遇 -> 使用精灵球收服 -> 升级进化 -> 出战/携带 -> 排行
"""
import json
import random
import time

try:
    from ...core import storage as ST
except ImportError:
    from core import storage as ST

SD = ST.dual_attr(__package__, "data_spirit", ".", "games.spirit")
try:
    from ..config.spirit import (POWER_DIV, EXP_FLOOR, CATCH_MIN, CATCH_MAX,
                                 CATCH_LV_STEP, CATCH_MASTER_EFF, CATCH_MASTER_RATE,
                                 PVP_STAKE_CAP, PVP_STAKE_DIV, SHINY_RATE, SHINY_MULT,
                                 SPIRIT_TRAITS, TRAVEL_EVENTS, STAT_GROWTH_RATES)
except ImportError:
    from games.config.spirit import (POWER_DIV, EXP_FLOOR, CATCH_MIN, CATCH_MAX,  # type: ignore
                                     CATCH_LV_STEP, CATCH_MASTER_EFF, CATCH_MASTER_RATE,
                                     PVP_STAKE_CAP, PVP_STAKE_DIV, SHINY_RATE, SHINY_MULT,
                                     SPIRIT_TRAITS, TRAVEL_EVENTS, STAT_GROWTH_RATES)

MENU = (
    "✨ 精灵系统\r\n"
    "━━━━━━━━━━━━━━\r\n"
    "🐣 领养精灵 [名称]　🎁 领取精灵礼包\r\n"
    "📋 我的精灵　　🔍 查看精灵 [名称]\r\n"
    "🛍️ 精灵商城　　🎒 我的背包\r\n"
    "🗺️ 精灵地图　　📍 查看地图 地点\r\n"
    "⚔️ 精灵冒险 地点　🔮 使用精灵球 名称\r\n"
    "💊 使用物品 名称*数量　💖 羁绊\r\n"
    "✨ 闪光觉醒 名称　🎲 洗练 名称\r\n"
    "🧳 旅行精灵　　🚩 精灵远征\r\n"
    "🎽 出战精灵 名称　🕊️ 回收出战精灵\r\n"
    "💠 携带精灵 名称　🗑️ 丢弃精灵 名称\r\n"
    "🧬 进化 [名称]　　🌳 进化路线 [名称/全部]\r\n"
    "⚔️ 精灵对战 @QQ　🏁 挑战 @QQ\r\n"
    "🏆 精灵排行\r\n"
    "━━━━━━━━━━━━━━\r\n"
    "💡 发送对应指令即可游玩"
)


_cfg, _cfgi0 = ST.cfg_scope("精灵配置")
try:
    from ..config.spirit import DEFAULTS as _SP_DEFAULTS
except ImportError:
    try:
        from games.config.spirit import DEFAULTS as _SP_DEFAULTS  # type: ignore
    except Exception:
        _SP_DEFAULTS = {}


def _cfgi(key, default=0):
    # 默认值单源：games/config/spirit.py DEFAULTS 表命中即用表值
    try:
        if key in _SP_DEFAULTS:
            default = _SP_DEFAULTS[key]
    except Exception:
        pass
    return _cfgi0(key, default)


# ---- 精灵图鉴(可在 WebUI 精灵图鉴编辑器修改, 存 精灵图鉴:spirits/maps/shop; 空=未自定义，回退 data_spirit.py 内置) ----
def _spirit_section(key, fallback):
    """图鉴三节唯一实现：dict 直返 / JSON 串解析 / 空回退内置（_SPIRITS/_MAPS/_SHOP 薄委托，零语义差）"""
    return ST.cfg_dict("精灵图鉴", key, fallback)


def _SPIRITS():
    return _spirit_section("spirits", SD.SPIRITS)


def _MAPS():
    return _spirit_section("maps", SD.MAPS)


def _SHOP():
    raw = _spirit_section("shop", SD.SHOP)
    out = dict(raw) if isinstance(raw, dict) else {}
    for _iname, _ckey in (("洗练果实", "洗练果实价格"), ("闪光结晶", "闪光结晶价格")):
        if _iname in out and isinstance(out[_iname], dict):
            _p = _cfgi(_ckey, int(out[_iname].get("price", 0) or 0))
            if _p > 0:
                out[_iname] = dict(out[_iname], price=_p)
    return out


def _u(gid, qq):
    return ST.acct(gid, qq)


def _spirits(gid, qq):
    """返回精灵数据 dict，健壮兼容 dict、JSON 字符串、Python dict 字符串与平铺账户"""
    a = _u(gid, qq)
    try:
        raw = a.get("spirits")
        if isinstance(raw, dict):
            sp = raw
        elif isinstance(raw, str) and raw.strip():
            try:
                sp = json.loads(raw)
            except Exception:
                try:
                    import ast as _ast
                    val = _ast.literal_eval(raw)
                    if isinstance(val, dict):
                        sp = val
                    else:
                        sp = {}
                except Exception:
                    sp = {}
        else:
            sp = {}
        if not sp.get("list") and isinstance(getattr(a, "kv", None), dict) and a.kv.get("list"):
            sp = a.kv
        if isinstance(sp, dict):
            if isinstance(sp.get("list"), str):
                try:
                    sp["list"] = json.loads(sp["list"])
                except Exception:
                    try:
                        import ast as _ast
                        v = _ast.literal_eval(sp["list"])
                        if isinstance(v, list):
                            sp["list"] = v
                    except Exception:
                        pass
            if isinstance(sp.get("bag"), str):
                try:
                    sp["bag"] = json.loads(sp["bag"])
                except Exception:
                    try:
                        import ast as _ast
                        v = _ast.literal_eval(sp["bag"])
                        if isinstance(v, dict):
                            sp["bag"] = v
                    except Exception:
                        pass
            if isinstance(sp.get("list"), list):
                for _spr_it in sp["list"]:
                    _ensure_spirit_stats(_spr_it)
            return sp
        return {}
    except Exception:
        return {}


def _save(gid, qq, sp):
    _u(gid, qq).set("spirits", json.dumps(sp, ensure_ascii=False))
    ST.acct_save(gid, qq)


def _wsp(sp, name):
    """取一只指定名字的精灵个体(第一只)"""
    for it in sp.get("list", []):
        if it.get("name") == name:
            return it
    return None


def _power(it):
    """精灵总战力 = 等级*(生命+攻击+防御+特攻+特防)//5"""
    try:
        lvl = int(it.get("level", 1) or 1)
        hp = int(it.get("hp", 0) or 0)
        atk = int(it.get("atk", 0) or 0)
        defe = int(it.get("def", 0) or 0)
        spa = int(it.get("spa", 0) or 0)
        spd = int(it.get("spd", 0) or 0)
        return lvl * (hp + atk + defe + spa + spd) // POWER_DIV
    except Exception:
        return 0


_TRAIT_MAP = {name: (mults, desc) for name, _, mults, desc in SPIRIT_TRAITS}


def _roll_trait(prefer_rare=False):
    """按权重随机抽取性格词条；洗练时排除平庸词条并提升稀有词条权重"""
    pool = []
    for name, w, _, _ in SPIRIT_TRAITS:
        if prefer_rare and name == "温顺":
            continue
        weight = w * 2 if (prefer_rare and name in ("天选", "神眷", "勇敢", "不朽")) else w
        pool.extend([name] * max(1, int(weight)))
    return random.choice(pool) if pool else "温顺"


def _trait_desc(trait_name):
    info = _TRAIT_MAP.get(str(trait_name or ""))
    return info[1] if info else "均衡稳定"


def _calc_variant_stats(base, shiny=False, trait=""):
    """基于图鉴底表 + 闪光加成(+15%) + 性格词条修正计算六维基础值"""
    s_mult = SHINY_MULT if shiny else 1.0
    t_mults = (_TRAIT_MAP.get(str(trait or "")) or ({}, ""))[0]
    out = {}
    for k in ("hp", "atk", "def", "spa", "spd", "spe"):
        raw = int(base.get(k, 0) or 0)
        m = s_mult * float(t_mults.get(k, 1.0))
        out[k] = max(1, int(round(raw * m))) if raw > 0 else 0
    return out


def _calc_level_growth(base_variant_stats):
    """根据精灵变异初始属性计算每升 1 级的综合全属性成长增量"""
    growth = {}
    growth["hp"] = max(1, int(round(base_variant_stats.get("hp", 40) * STAT_GROWTH_RATES.get("hp", 0.015))))
    growth["atk"] = max(1, int(round(base_variant_stats.get("atk", 40) * STAT_GROWTH_RATES.get("atk", 0.01))))
    growth["def"] = max(1, int(round(base_variant_stats.get("def", 40) * STAT_GROWTH_RATES.get("def", 0.01))))
    growth["spa"] = max(1, int(round(base_variant_stats.get("spa", 40) * STAT_GROWTH_RATES.get("spa", 0.01))))
    growth["spd"] = max(1, int(round(base_variant_stats.get("spd", 40) * STAT_GROWTH_RATES.get("spd", 0.01))))
    growth["spe"] = max(1, int(round(base_variant_stats.get("spe", 40) * STAT_GROWTH_RATES.get("spe", 0.008))))
    return growth


def _calc_stats_at_level(base, level=1, shiny=False, trait=""):
    """计算指定图鉴种族在对应等级下的全套属性（包含闪光/性格加成与等级综合成长）"""
    base_v = _calc_variant_stats(base, shiny=shiny, trait=trait)
    lvl = max(1, int(level or 1))
    if lvl == 1:
        return base_v
    growth = _calc_level_growth(base_v)
    lv_diff = lvl - 1
    out = {}
    for k in ("hp", "atk", "def", "spa", "spd", "spe"):
        out[k] = base_v.get(k, 0) + lv_diff * growth.get(k, 1)
    return out


def _ensure_spirit_stats(it):
    """校准精灵属性：若已有精灵等级 > 1 但数值仍停留在 1 级基础数值，自动补齐对应的等级综合成长（且保留已吃的药品/美食增益）"""
    if not isinstance(it, dict):
        return
    lvl = int(it.get("level", 1) or 1)
    if lvl <= 1:
        return
    name = it.get("name")
    base = _SPIRITS().get(name, {}) or {}
    if not base:
        return
    shiny = bool(it.get("shiny"))
    trait = it.get("trait") or "温顺"
    base_v = _calc_variant_stats(base, shiny=shiny, trait=trait)
    growth = _calc_level_growth(base_v)
    lv_diff = lvl - 1
    for k in ("hp", "atk", "def", "spa", "spd", "spe"):
        cur_val = int(it.get(k, 0) or 0)
        expected_min = base_v.get(k, 0) + lv_diff * growth.get(k, 1)
        if cur_val < expected_min:
            it[k] = cur_val + lv_diff * growth.get(k, 1)


def _fmt_name(it):
    prefix = "✨[闪光]" if it.get("shiny") else ""
    return f"{prefix}{it.get('name', '?')}"


def _desc(it):
    trait = it.get("trait") or "温顺"
    return (f"{_fmt_name(it)} Lv.{it.get('level',1)} 属性:{it.get('type') or '-'} 性格:【{trait}】\r\n"
            f"生命:{it.get('hp',0)} 攻击:{it.get('atk',0)} 防御:{it.get('def',0)}\r\n"
            f"特攻:{it.get('spa',0)} 特防:{it.get('spd',0)} 速度:{it.get('spe',0)} "
            f"战力:{_power(it)}\r\n经验:{it.get('exp',0)}/{_exp_need(it)}")


def _exp_need(it):
    # P0: 配置误设为0时 while exp>=0 恒真无限循环卡死，钳位>=1
    try:
        need = int(it.get("level", 1)) * int(_cfgi("升级经验", 800))
    except Exception:
        need = _SP_DEFAULTS.get("升级经验", 800)
    return need if need >= EXP_FLOOR else EXP_FLOOR


def _shiny_rate():
    return max(1, min(100, _cfgi("闪光基础概率", SHINY_RATE)))


def _mk_spr(name, level=1, shiny=None, trait=None):
    """按图鉴生成一只精灵实例(含等级综合属性成长、闪光变异与性格词条)"""
    base = _SPIRITS().get(name, {}) or {}
    if shiny is None:
        shiny = random.randint(1, 100) <= _shiny_rate()
    if not trait:
        trait = _roll_trait(prefer_rare=bool(shiny))
    lvl = max(1, int(level or 1))
    stats = _calc_stats_at_level(base, level=lvl, shiny=bool(shiny), trait=trait)
    return {
        "name": name,
        "level": lvl,
        "exp": 0,
        "type": base.get("type", ""),
        "shiny": 1 if shiny else 0,
        "trait": trait,
        **stats,
    }


def _apply_new_species(it, new_name):
    """进化或重算时保留已吃药培养的额外属性增量，并套用新种族底表+闪光/性格倍率+等级综合成长"""
    old_base = _SPIRITS().get(it.get("name"), {}) or {}
    new_base = _SPIRITS().get(new_name, {}) or {}
    shiny = bool(it.get("shiny"))
    trait = it.get("trait") or "温顺"
    lvl = max(1, int(it.get("level", 1) or 1))
    old_calc = _calc_stats_at_level(old_base, level=lvl, shiny=shiny, trait=trait)
    new_calc = _calc_stats_at_level(new_base, level=lvl, shiny=shiny, trait=trait)
    it["name"] = new_name
    if new_base:
        it["type"] = new_base.get("type", it.get("type", ""))
        for k in ("hp", "atk", "def", "spa", "spd", "spe"):
            bonus = max(0, int(it.get(k, 0)) - old_calc.get(k, 0))
            it[k] = new_calc.get(k, it.get(k, 0)) + bonus


def _starters():
    """初始精灵列表(配置 初始精灵 1/2/3)"""
    lst = []
    for k in ("1", "2", "3"):
        v = _cfg("初始精灵_" + k, "")
        if v:
            lst.append(v)
    if not lst:
        lst = [_SPIRITS().get("叶子", {}).get("name", "叶子"),
               _SPIRITS().get("火苗", {}).get("name", "火苗"),
               _SPIRITS().get("水滴", {}).get("name", "水滴")]
    return lst


def _add_exp(gid, qq, sp, it, amount, save_now=True):
    """加经验与升级（升级全方位综合加六维属性与战力，达到进化等级时给出提示）"""
    it["exp"] = int(it.get("exp", 0)) + int(amount)
    evolved = ""
    levels_gained = 0
    max_lv = _cfgi("最大等级", 100)

    base = _SPIRITS().get(it.get("name"), {}) or {}
    shiny = bool(it.get("shiny"))
    trait = it.get("trait") or "温顺"
    base_v = _calc_variant_stats(base, shiny=shiny, trait=trait)
    growth = _calc_level_growth(base_v)

    while it["exp"] >= _exp_need(it) and it["level"] < max_lv:
        it["exp"] -= _exp_need(it)
        it["level"] = int(it.get("level", 1)) + 1
        levels_gained += 1

        # 升级综合加全六维属性！
        for k in ("hp", "atk", "def", "spa", "spd", "spe"):
            it[k] = int(it.get(k, 0)) + growth.get(k, 1)

        old_name = it.get("name")
        evo = base.get("evolve", "否")
        if evo and evo != "否" and it["level"] >= int(base.get("lv", 0) or 0):
            evolved = f"💡 【{old_name}】已达进化等级 Lv.{base.get('lv', 0)}，可使用【进化液】发送【进化 {old_name}】进化为「{evo}」！\r\n"

    if levels_gained > 0:
        stat_up_summary = f"生命+{growth['hp']*levels_gained} 攻防各+{growth['atk']*levels_gained} 速度+{growth['spe']*levels_gained}"
        lvl_msg = f"🎉【等级提升】出战精灵【{_fmt_name(it)}】升至 Lv.{it['level']}（+{levels_gained}级）！综合属性成长（{stat_up_summary}，总战力 {_power(it)}）！\r\n"
        evolved = lvl_msg + evolved

    if save_now:
        _save(gid, qq, sp)
    return evolved


def _need_switch():
    return _cfg("开关", "真") != "真"


def cmd_adopt(gid, qq, arg=""):
    sp = _spirits(gid, qq)
    # 兼容旧库导入：已有 list 即视为已领养，避免重复领养覆盖
    if sp.get("adopted") or (isinstance(sp.get("list"), list) and len(sp.get("list")) > 0):
        return "亲，您已经领养精灵了，想要其它精灵请到野外冒险捕获！"
    starters = _starters()
    arg = (arg or "").strip()
    if arg and arg in starters:
        starter = arg
    else:
        starter = random.choice(starters)
    sp["adopted"] = 1
    sp["active"] = starter
    new_it = _mk_spr(starter, 1)
    sp.setdefault("list", []).append(new_it)
    sp.setdefault("bag", {})
    _save(gid, qq, sp)
    shiny_tip = "\r\n🌟 天降祥瑞！你领养到了万中无一的【✨闪光变异】初始精灵（全属性+15%）！" if new_it.get("shiny") else ""
    return (f"恭喜您获得精灵「{_fmt_name(new_it)}」！{shiny_tip}\r\n" + _desc(new_it) +
            "\r\n您可发送【领取精灵礼包】领取精美礼包一份！")


def cmd_gift(gid, qq):
    sp = _spirits(gid, qq)
    if not sp.get("adopted"):
        return "亲，您还没有精灵，请领养精灵后再来领取礼包吧！"
    if sp.get("gift"):
        return "亲，您已经领取过精灵礼包了，如果需要其他物品请到商城购买！"
    sp["gift"] = 1
    bag = sp.setdefault("bag", {})
    # 礼包来自 精灵配置: 精灵球/大师球/奇异甜食
    defaults = {"精灵球": 5, "大师球": 1, "奇异甜食": 3}
    got_counts = {}
    for k, d in defaults.items():
        n = max(0, _cfgi(k, d))
        got_counts[k] = n
        if n:
            bag[k] = int(bag.get(k, 0)) + n
    _save(gid, qq, sp)
    return ("恭喜您获得精灵礼包一份！\r\n精灵球+%s 大师球+%s 奇异甜食+%s"
            % (got_counts["精灵球"], got_counts["大师球"], got_counts["奇异甜食"]))


def cmd_my(gid, qq, target=None):
    t_qq = str(target or qq).strip()
    is_self = (t_qq == str(qq).strip())
    sp = _spirits(gid, t_qq)
    # 兼容旧库：仅 list 判定，已有精灵但 adopted 缺失时自动补齐
    if not sp.get("list"):
        if is_self:
            return "亲，您还没有精灵，请先领养精灵吧！"
        else:
            try:
                from ..slave.handler import display_name
                t_name = display_name(gid, t_qq, t_qq)
            except Exception:
                t_name = t_qq
            return f"亲，【{t_name}】还没有精灵哦！"
    if is_self and not sp.get("adopted"):
        sp["adopted"] = 1
        _save(gid, qq, sp)
    if is_self:
        lines = ["以下是您拥有的精灵："]
    else:
        try:
            from ..slave.handler import display_name
            t_name = display_name(gid, t_qq, t_qq)
        except Exception:
            t_name = t_qq
        lines = [f"以下是【{t_name}】拥有的精灵："]
    all_sp = _SPIRITS()
    for it in sp["list"]:
        if not isinstance(it, dict):
            continue
        mark = "【出战】" if it.get("name") == sp.get("active") else ""
        trait = it.get("trait") or "温顺"
        nm = it.get("name")
        base = all_sp.get(nm, {}) or {}
        evo = base.get("evolve", "否")
        evo_lv = int(base.get("lv", 0) or 0)
        cur_lvl = int(it.get("level", 1) or 1)
        evo_badge = " ✨[可进化]" if (evo and evo != "否" and cur_lvl >= evo_lv) else ""
        lines.append(f"{mark}{_fmt_name(it)} Lv.{cur_lvl} [{trait}] 战力:{_power(it)}{evo_badge}")
    lines.append("发送【查看精灵 名称】查看详细属性；发送【进化路线】查看进化树")
    if sp.get("active"):
        lines.append(f"当前出战精灵：【{sp['active']}】")
    if sp.get("ride"):
        lines.append(f"携带欢迎精灵：【{sp['ride']}】")
    tr = sp.get("travel")
    if isinstance(tr, dict) and tr.get("name"):
        lines.append(f"🧳 漫游精灵：【{tr['name']}】（发送【旅行精灵】查看/收获）")
    expd = sp.get("expedition")
    if isinstance(expd, dict) and expd.get("names"):
        lines.append(f"🚩 远征小队：{'、'.join(expd['names'])}（发送【精灵远征】查看/收获）")
    return "\r\n".join(lines)


def cmd_view(gid, qq, name):
    sp = _spirits(gid, qq)
    name = (name or "").strip()
    if not name:
        name = sp.get("active") or ""
    it = _wsp(sp, name)
    if not it:
        if not name:
            return "亲，您还没有设置出战精灵，发送【出战精灵 名称】或【查看精灵 名称】进行查看！"
        return f"亲，您没有「{name}」，请到野外冒险捕获吧！"
    _pp = ""
    try:
        _base = _SPIRITS().get(it.get("name"), {}) or {}
        _imgp = str(_base.get("img", "") or "").strip()
        if _imgp:
            _pp = _img_path(_imgp)
    except Exception:
        _pp = ""
    trait = it.get("trait") or "温顺"
    bond = int(it.get("bond", 0) or 0)

    base = _SPIRITS().get(it.get("name"), {}) or {}
    evo = base.get("evolve", "否")
    evo_lv = int(base.get("lv", 0) or 0)
    cur_lv = int(it.get("level", 1) or 1)

    if evo and evo != "否":
        bag_evo = int((sp.get("bag") or {}).get("进化液", 0) or 0)
        if cur_lv >= evo_lv:
            evo_line = f"🧬 进化状态：✨已达进化等级 Lv.{evo_lv}！可进化为「{evo}」（持有进化液×{bag_evo}，发送【进化 {it.get('name')}】即可突破）"
        else:
            diff_lv = evo_lv - cur_lv
            evo_line = f"🧬 进化路线：Lv.{evo_lv} 可进化为「{evo}」（还差 {diff_lv} 级，需消耗【进化液】）"
    else:
        evo_line = "🧬 进化状态：👑已达终极形态（无法再次进化）"

    _txt = (f"您的精灵【{_fmt_name(it)}】\r\n"
            f"属性：{it.get('type') or '-'}　性格：【{trait}】（{_trait_desc(trait)}）\r\n"
            f"等级：Lv.{cur_lv}　经验：{it.get('exp',0)}/{_exp_need(it)}　羁绊：{bond}\r\n"
            f"生命：{it.get('hp',0)}　攻击：{it.get('atk',0)}　防御：{it.get('def',0)}\r\n"
            f"特攻：{it.get('spa',0)}　特防：{it.get('spd',0)}　速度：{it.get('spe',0)}\r\n"
            f"{evo_line}\r\n"
            f"总战力：{_power(it)}")
    if _pp:
        return _txt, [_pp]
    return _txt


def _img_path(path):
    """元组图片路径：支持 data/ 相对与绝对，缺失返回空（图2路径）"""
    try:
        import os as _os2
        p = str(path or "").strip()
        if not p:
            return ""
        if not _os2.path.isabs(p):
            _base = ""
            try:
                _base = ST.get_persistent_data_dir()
            except Exception:
                _base = ""
            _cands = []
            if _base:
                _cands.append(_os2.path.join(_base, p))
            try:
                _cands.append(_os2.path.join(_os2.path.dirname(_os2.path.dirname(_os2.path.dirname(_os2.path.abspath(__file__)))), p))
            except Exception:
                pass
            _hit = ""
            for _c in _cands:
                try:
                    if _c and _os2.path.isfile(_c):
                        _hit = _c
                        break
                except Exception:
                    pass
            if not _hit:
                return ""
            p = _hit
        if not _os2.path.isfile(p):
            return ""
        return _os2.path.abspath(p)
    except Exception:
        return ""


def _shop_item_desc(name, info):
    """取精灵商城道具简明说明（支持内置道具及用户自定义新增道具自动推导，绝不留空）"""
    desc = str((info or {}).get("desc") or "").strip()
    if desc:
        return desc
    builtin_descs = {
        "精灵球": "收服率+10%",
        "时间球": "收服率+30%",
        "狩猎球": "收服率+40%",
        "极速球": "收服率+70%",
        "大师球": "100%必中",
        "起司": "喂食精灵：加亲密/经验/全属性",
        "吐司": "喂食精灵：加亲密/经验/全属性",
        "奇异甜食": "出战精灵直接升1级",
        "攻击之源": "永久攻击+2",
        "防御之源": "永久防御+2",
        "特防之源": "永久特防+2",
        "特攻之源": "永久特攻+2",
        "进化液": "达标精灵完成形态进化",
        "洗练果实": "重置性格与天赋词条",
        "闪光结晶": "觉醒变异闪光形态",
    }
    if name in builtin_descs:
        return builtin_descs[name]
    attr = str((info or {}).get("attr") or "").strip()
    eff = str((info or {}).get("effect") or "").strip()
    if attr == "精灵球":
        return f"收服率+{eff}%" if eff else "抓捕野生精灵道具"
    elif attr == "等级":
        return f"出战精灵升{eff}级" if eff else "精灵升级道具"
    elif attr in ("生命", "HP"):
        return f"出战生命+{eff}" if eff else "出战生命强化"
    elif attr in ("攻击", "防御", "特攻", "特防", "速度"):
        return f"出战{attr}+{eff}" if eff else f"出战{attr}强化"
    elif attr == "美食":
        return "喂食增加亲密、经验与属性"
    elif attr == "进化":
        return "精灵形态进化道具"
    elif attr == "洗练":
        return "洗练重置性格与天赋"
    elif attr == "闪光":
        return f"觉醒闪光形态({eff}%)" if eff else "觉醒闪光形态"
    elif attr:
        return f"{attr}+{eff}" if eff else attr
    return "专属道具"


def cmd_shop():
    lines = ["🛒 精灵商城", "━━━━━━━━━━━━━━"]
    shop = _SHOP()

    lines.append("【精灵球】野生精灵抓捕")
    for b in ("精灵球", "时间球", "狩猎球", "极速球", "大师球"):
        if b in shop:
            p_str = ST.fmt_coins(shop[b].get("price", 0))
            d_str = _shop_item_desc(b, shop[b])
            lines.append(f"· {b}: {p_str}{ST.coin_name()} ({d_str})")

    lines.append("\r\n【食物与升级】")
    for f_name in ("起司", "吐司", "奇异甜食"):
        if f_name in shop:
            p_str = ST.fmt_coins(shop[f_name].get("price", 0))
            d_str = _shop_item_desc(f_name, shop[f_name])
            lines.append(f"· {f_name}: {p_str}{ST.coin_name()} ({d_str})")

    lines.append("\r\n【属性强化】出战精灵永久加成")
    src_3 = [s for s in ("攻击之源", "防御之源", "特防之源") if s in shop]
    if src_3 and len(src_3) == 3 and shop[src_3[0]].get("price") == shop[src_3[1]].get("price") == shop[src_3[2]].get("price"):
        p_str = ST.fmt_coins(shop[src_3[0]].get("price", 6000))
        lines.append(f"· 攻击之源 / 防御之源 / 特防之源: 各{p_str}{ST.coin_name()} (对应属性+2)")
    else:
        for s in ("攻击之源", "防御之源", "特防之源"):
            if s in shop:
                p_str = ST.fmt_coins(shop[s].get("price", 0))
                lines.append(f"· {s}: {p_str}{ST.coin_name()} ({_shop_item_desc(s, shop[s])})")
    if "特攻之源" in shop:
        p_str = ST.fmt_coins(shop["特攻之源"].get("price", 0))
        lines.append(f"· 特攻之源: {p_str}{ST.coin_name()} ({_shop_item_desc('特攻之源', shop['特攻之源'])})")

    lines.append("\r\n【进阶洗练】")
    for e_name in ("进化液", "洗练果实", "闪光结晶"):
        if e_name in shop:
            p_str = ST.fmt_coins(shop[e_name].get("price", 0))
            d_str = _shop_item_desc(e_name, shop[e_name])
            lines.append(f"· {e_name}: {p_str}{ST.coin_name()} ({d_str})")

    # 自定义拓展物品兼容
    known = {"精灵球", "时间球", "狩猎球", "极速球", "大师球", "奇异甜食", "起司", "吐司",
             "攻击之源", "防御之源", "特防之源", "特攻之源", "进化液", "洗练果实", "闪光结晶"}
    customs = [k for k in shop.keys() if k not in known]
    if customs:
        lines.append("\r\n【自定义道具】")
        for k in customs:
            p_str = ST.fmt_coins(shop[k].get("price", 0))
            d_str = _shop_item_desc(k, shop[k])
            lines.append(f"· {k}: {p_str}{ST.coin_name()} ({d_str})")

    lines.append("━━━━━━━━━━━━━━")
    lines.append("购买：【购买 物品名*数量】（如：购买 起司*5）")
    return "\r\n".join(lines)


def cmd_buy(gid, qq, name):
    raw_arg = (name or "").strip()
    if not raw_arg:
        return f"亲，请指定要购买的商品名称：【购买 商品名称*数量】（如：购买 奇异甜食*5、购买 起司）！"
    import re as _re_buy
    m = _re_buy.match(r"^([^*\s×xX]+)(?:[\s*×xX]+(\d+))?$", raw_arg)
    if not m:
        item_name = raw_arg
        cnt = 1
    else:
        item_name = m.group(1).strip()
        cnt = max(1, min(999, int(m.group(2) or 1)))

    shop = _SHOP()
    if item_name not in shop:
        return f"亲，商城中不存在「{item_name}」，发送【精灵商城】查看在售商品吧！"
    d = shop[item_name]
    unit_price = int(d.get("price", 0) or 0)
    total_price = unit_price * cnt
    if total_price > 0 and ST.coins_get(gid, qq) < total_price:
        return f"笑~你没有那么多{ST.coin_name()}（购买 {item_name}×{cnt} 需要 {ST.fmt_coins(total_price)}）"
    sp = _spirits(gid, qq)
    bag = sp.setdefault("bag", {})
    bag[item_name] = int(bag.get(item_name, 0)) + cnt
    if total_price > 0:
        if ST.txn_coins_acct(gid, qq, -total_price, {"spirits": json.dumps(sp, ensure_ascii=False)}, require_funds=True) is None:
            return "精灵商城繁忙，购买未成功，请稍后重试！"
    else:
        _save(gid, qq, sp)
    return f"🛒 购买成功！消耗 {ST.fmt_coins(total_price)} {ST.coin_name()}，获得「{item_name}」×{cnt}（背包现有：{bag[item_name]} 个）。"


def _map_indexed():
    """返回 [(idx, name, data)] 序号从1开始，按 _MAPS() 插入顺序"""
    return list(enumerate(_MAPS().items(), 1))

def _resolve_map(place):
    """place 可为 地点名 或 序号(1-based)，返回真实地点名或 None"""
    if not place:
        return None
    place = str(place).strip()
    maps = _MAPS()
    if place == "原神":
        return "常青森林" if "常青森林" in maps else place
    if place in maps:
        return place
    # 纯数字序号
    if place.isdigit():
        idx = int(place)
        lst = list(maps.keys())
        if 1 <= idx <= len(lst):
            return lst[idx - 1]
        # 也支持带括号如 [2] 2.
        return None
    # 支持 [2] 或 2. 形式
    import re as _re2
    m = _re2.match(r"^\[(\d+)\]$", place)
    if m:
        idx = int(m.group(1))
        lst = list(maps.keys())
        if 1 <= idx <= len(lst):
            return lst[idx - 1]
    return None

def cmd_map():
    lines = ["🗺️ 精灵地图", "━━━━━━━━━━━━━━"]
    for idx, (name, d) in _map_indexed():
        drops = "/".join(d.get("drops", []))
        lines.append(f"[{idx}] {name}（Lv.{d.get('lv',1)}）　{drops}")
    lines.append("发送【精灵冒险 地点/序号】前往冒险，如【精灵冒险 1】")
    return "\r\n".join(lines)


def cmd_map_detail(gid, qq, place):
    place = _resolve_map((place or "").strip())
    if not place or place not in _MAPS():
        return "亲，查无此图或您的输入格式有误，查看地图格式为：【查看地图 地点/序号】！"
    d = _MAPS()[place]
    drops = "、".join(d.get("drops", []))
    return (f"🗺️【{place}】　可抓以下精灵：\r\n"
            f"{drops}\r\n"
            f"推荐等级：Lv.{d.get('lv',1)}\r\n"
            f"发送【精灵冒险 {place}】可进行精灵冒险")


def cmd_backpack(gid, qq):
    sp = _spirits(gid, qq)
    bag = sp.get("bag", {})
    if not bag:
        return "亲，您的背包为空，请到精灵商城购买需要的物品吧！"
    lines = ["🎒 我的背包", "━━━━━━━━━━━━━━"]
    shop = _SHOP()
    _effects_desc = {
        "精灵球": "基础捕捉道具，收服率+10%",
        "时间球": "高级捕捉道具，收服率+30%",
        "狩猎球": "稀有捕捉道具，收服率+40%",
        "极速球": "强力捕捉道具，收服率+70%",
        "大师球": "终极捕捉道具，100%必中",
        "奇异甜食": "出战精灵等级提升1级",
        "起司": "提升亲密羁绊与远足属性",
        "吐司": "提升亲密羁绊与远足属性",
        "攻击之源": "出战精灵永久攻击+2",
        "防御之源": "出战精灵永久防御+2",
        "特防之源": "出战精灵永久特防+2",
        "特攻之源": "出战精灵永久特攻+2",
        "进化液": "激发潜能助精灵形态进化",
        "洗练果实": "洗练重置精灵性格与词条",
        "闪光结晶": "觉醒闪光变异形态",
    }
    for name, cnt in bag.items():
        desc = _effects_desc.get(name)
        if not desc:
            info = shop.get(name, {})
            if info:
                desc = f"{info.get('attr', '')}+{info.get('effect', '')}"
            else:
                desc = "珍稀道具"
        lines.append(f"· {name} ×{cnt}（{desc}）")
    lines.append("━━━━━━━━━━━━━━")
    lines.append("使用精灵球：【使用精灵球 名称】\r\n使用道具：【使用物品 名称*数量】（如：使用物品 起司*1）")
    return "\r\n".join(lines)


def cmd_adventure(gid, qq, place):
    sp = _spirits(gid, qq)
    if not sp.get("adopted") or not sp.get("list"):
        return "亲，您没有精灵，请先领养精灵吧！"
    place = _resolve_map(place)
    if not place or place not in _MAPS():
        return "亲，不存在该地点，发送【精灵地图】查看地图吧！可输入序号如【精灵冒险 1】"
    md = _MAPS()[place]
    act = sp.get("active")
    act_it = _wsp(sp, act) if act else None
    if act_it is None:
        return "请先【出战精灵 名称】指定出战的精灵！"
    if act_it["level"] < int(md.get("lv", 1)):
        return "亲，您的精灵等级过低，无法在此地图冒险！"
    # 间隔
    key = f"spadv_{gid}_{qq}"
    last = _recall_get(key)
    gap = _cfgi("冒险间隔", 5) * 60
    if last and time.time() - float(last) < gap:
        rem_s = gap - (time.time() - float(last))
        return f"{ST.format_cd_time(rem_s)}再来冒险吧！"

    # 体力消耗与防脚本校验
    d_tili = max(2, _cfgi("挑战扣除_消耗体力", 2))
    cur_st = ST.acct(gid, qq).int("stamina")
    if cur_st < d_tili:
        return f"亲，精灵冒险需要消耗 {d_tili} 点体力，您当前体力（{cur_st}）不足！"

    # 随机遭遇（含野生闪光变异判定）
    wild = random.choice(md.get("drops", []) or ["绿毛虫"])
    lb = _cfgi("等级加成下限", 3); ub = _cfgi("等级加成上限", 5)
    wl = int(md.get("lv", 1)) + random.randint(lb, ub)
    is_shiny = random.randint(1, 100) <= _shiny_rate()
    sp["wild"] = {"name": wild, "level": wl, "shiny": 1 if is_shiny else 0}
    # 冒险历练奖励(挑战奖励配置): 经验 + 金币（调低至符合零门槛休闲玩法期望）
    exp_lo = _cfgi("挑战奖励_经验下限", 50); exp_hi = _cfgi("挑战奖励_经验上限", 120)
    gold_lo = max(0, _cfgi("挑战奖励_金钱下限", 200))
    gold_hi = max(gold_lo, _cfgi("挑战奖励_金钱上限", 500))
    exp = random.randint(max(1, exp_lo), max(exp_lo, exp_hi))
    gold = random.randint(gold_lo, gold_hi)
    evo_hint = ""
    if act_it.get("level") < _cfgi("最大等级", 100):
        evo_hint = _add_exp(gid, qq, sp, act_it, exp, save_now=False) or ""
    # H: 挑战扣除
    d_lo = _cfgi("挑战扣除_金钱下限", 50)
    d_hi = _cfgi("挑战扣除_金钱上限", 120)
    d_gold = 0
    d_stam = d_tili
    if d_hi > 0 or d_lo > 0:
        _dlo, _dhi = (d_lo, d_hi) if d_lo <= d_hi else (d_hi, d_lo)
        _dlo = max(0, _dlo)
        _dhi = max(0, _dhi)
        if _dhi > 0:
            d_gold = random.randint(_dlo, _dhi)
            if d_gold > 0:
                _real = min(d_gold, ST.coins_get(gid, qq))
                d_gold = _real
    updates = {
        "spirits": json.dumps(sp, ensure_ascii=False),
        "stamina": str(max(0, cur_st - d_stam)),
    }
    if ST.txn_coins_acct(gid, qq, gold - d_gold, updates) is None:
        return "精灵冒险结算繁忙，本次奖励和扣除均未生效，请稍后重试！"
    _recall_set(key, str(time.time()))
    _deduct_msg = ""
    if d_gold or d_stam:
        _parts = []
        if d_gold:
            _parts.append(f"{ST.coin_name()}-{d_gold}")
        if d_stam:
            _parts.append(f"体力-{d_stam}")
        _deduct_msg = "挑战扣除：" + " ".join(_parts) + "\r\n"
    shiny_banner = f"🌟 罕见异象！这是一只通体发亮的【✨闪光·{wild}】（全属性+15%）！\r\n" if is_shiny else ""
    wild_label = f"✨[闪光]{wild}" if is_shiny else wild
    return (f"【精灵冒险】来到{place}，遭遇了野生的 Lv.{wl}「{wild_label}」！\r\n"
            f"{shiny_banner}"
            f"历练奖励：经验+{exp} {ST.coin_name()}+{ST.fmt_coins(gold)}\r\n"
            f"{evo_hint}"
            f"{_deduct_msg}"
            "如需收服请发【使用精灵球 精灵球名称】")


def cmd_catch(gid, qq, ball):
    sp = _spirits(gid, qq)
    wild = sp.get("wild")
    if not wild:
        return "现在没有可以收服的野生精灵，请先【精灵冒险 地点】！"
    if ball not in _SHOP() or _SHOP()[ball].get("attr") != "精灵球":
        return "亲，不存在该精灵球，使用精灵球格式为：【使用精灵球 精灵球名称】！"
    bag = sp.setdefault("bag", {})
    if int(bag.get(ball, 0)) <= 0:
        return "亲，您的背包中没有该精灵球，请到商城购买吧！"
    if len(sp.get("list", [])) >= _cfgi("精灵数量", 8):
        return "亲，您的精灵数量已达上限，无法收服，可丢弃后再来！"
    bag[ball] = int(bag.get(ball, 0)) - 1
    if int(bag.get(ball, 0)) <= 0:
        del bag[ball]
    # 抓取概率 = 球效果 / 100 + 等级修正
    eff = int(_SHOP()[ball].get("effect", 0) or 0)
    lv = int(wild.get("level", 1))
    p = max(CATCH_MIN, min(CATCH_MAX, eff - (lv - 10) // CATCH_LV_STEP)) if eff < CATCH_MASTER_EFF else CATCH_MASTER_RATE
    try:
        from ..sign import eff_prob as _LP
        p = _LP(p, gid, qq)
    except Exception:
        pass
    sp.pop("wild", None)
    # 预摇奖（纯随机）：失败路径不再重摇
    _caught = random.randint(1, 100) <= p
    new_spr = None
    if _caught:
        w_shiny = bool(wild.get("shiny"))
        if not w_shiny and eff >= CATCH_MASTER_EFF:
            # 大师球额外一次闪光激发判定
            w_shiny = random.randint(1, 100) <= _shiny_rate()
        new_spr = _mk_spr(wild["name"], lv, shiny=w_shiny)
        sp.setdefault("list", []).append(new_spr)
    # 单事务原子结算：扣球+清遭遇+入队一次提交；失败则球未扣、精灵未变（禁半成功）
    if ST.txn_coins_acct(gid, qq, 0, {"spirits": json.dumps(sp, ensure_ascii=False)}) is None:
        return "精灵球系统繁忙，本次收服未结算（精灵球未消耗），请稍后重试！"
    if _caught and new_spr:
        trait = new_spr.get("trait") or "温顺"
        return (f"恭喜！成功收服 Lv.{lv}「{_fmt_name(new_spr)}」！\r\n"
                f"觉醒性格：【{trait}】（{_trait_desc(trait)}）　总战力：{_power(new_spr)}")
    return "很遗憾，野生精灵挣脱了，飞走了……"


def cmd_set_active(gid, qq, name):
    sp = _spirits(gid, qq)
    clean_name = str(name or "").strip()
    if not clean_name:
        act = sp.get("active")
        if act:
            return f"当前出战精灵：【{act}】\r\n发送【出战精灵 名称】（如：【出战精灵 叶子】）可更换出战精灵！"
        return "亲，您还没有设置出战精灵，发送【出战精灵 名称】（如：【出战精灵 叶子】）进行设置！"
    if not _wsp(sp, clean_name):
        return f"亲，您没有名为「{clean_name}」的精灵，无法出战！"
    sp["active"] = clean_name
    _save(gid, qq, sp)
    return f"已将【{clean_name}】设为出战精灵！"


def cmd_active(gid, qq):
    sp = _spirits(gid, qq)
    it = _wsp(sp, sp.get("active")) if sp.get("active") else None
    if not it:
        return "亲，您还没有设置出战精灵，发送【出战精灵 名称】进行设置！"
    return "当前出战精灵：\r\n" + _desc(it)


def cmd_cancel_active(gid, qq):
    sp = _spirits(gid, qq)
    if not sp.get("active"):
        return "亲，您没有出战的精灵，无需回收！"
    sp["active"] = ""
    _save(gid, qq, sp)
    return "已回收出战精灵！"


def cmd_ride(gid, qq, name):
    sp = _spirits(gid, qq)
    if not str(name or "").strip():
        # 空名分支：查现状而非误报“没有该精灵”（对齐 cmd_active 用法提示）
        if sp.get("ride"):
            return f"当前携带精灵：【{sp['ride']}】\r\n发送【携带精灵 名称】更换！"
        return "亲，您还没有设置携带精灵，发送【携带精灵 名称】进行设置！"
    if not _wsp(sp, name):
        return "亲，您没有该精灵，无法携带！"
    sp["ride"] = name
    _save(gid, qq, sp)
    return f"已将【{name}】设为携带欢迎精灵！"


def cmd_discard(gid, qq, name):
    sp = _spirits(gid, qq)
    it = _wsp(sp, name)
    if not it:
        return "亲，您没有该精灵，无需丢弃！"
    if len(sp.get("list", [])) <= 1:
        return "亲，您至少需要保留一只精灵，无法丢弃最后一只！"
    same_cnt = sum(1 for _x in sp.get("list", []) if _x.get("name") == name)
    tr = sp.get("travel")
    if same_cnt <= 1 and isinstance(tr, dict) and tr.get("name") == name and tr.get("ts"):
        return f"亲，精灵【{name}】正在外出旅行中，请先收获旅行后再丢弃！"
    expd = sp.get("expedition")
    if isinstance(expd, dict) and expd.get("names") and expd.get("ts"):
        in_exp_cnt = sum(1 for _n in (expd.get("names") or []) if _n == name)
        if same_cnt <= in_exp_cnt:
            return f"亲，精灵【{name}】正在组队远征中，请先收获远征后再丢弃！"
    # P0: 同名多只时仅删首只，误删全部是资损
    _lst = list(sp.get("list", []))
    for _i, _x in enumerate(_lst):
        if _x.get("name") == name:
            del _lst[_i]
            break
    sp["list"] = _lst
    if same_cnt <= 1:
        if sp.get("active") == name:
            sp["active"] = _lst[0]["name"] if _lst else ""
        if sp.get("ride") == name:
            sp["ride"] = ""
    red = _cfgi("魅力减少", 10)
    # 单事务原子结算：扣魅力+移除精灵一次提交；失败则精灵保留、魅力不扣（禁半成功）
    try:
        _cur_charm = ST.acct(gid, qq).int("charm")
    except Exception:
        _cur_charm = red
    if ST.txn_coins_acct(gid, qq, 0, {
        "charm": str(max(0, _cur_charm - red)),
        "spirits": json.dumps(sp, ensure_ascii=False),
    }) is None:
        return "数据库繁忙，丢弃精灵未成功，请稍后重试。"
    return f"已丢弃精灵【{name}】，魅力 -{red}"


def _get_spirit_chains(name):
    """查询指定精灵的完整进化链，包含从根基础形态到终极形态的所有路径"""
    all_sp = _SPIRITS()
    if name not in all_sp:
        return None
    prev_map = {}
    for k, v in all_sp.items():
        ev = v.get("evolve")
        if ev and ev != "否":
            prev_map.setdefault(ev, []).append((k, int(v.get("lv", 0) or 0)))

    def find_roots(node):
        if node not in prev_map:
            return [node]
        roots = []
        for parent, _ in prev_map[node]:
            roots.extend(find_roots(parent))
        return list(dict.fromkeys(roots))

    roots = find_roots(name)
    chains = []
    for r in roots:
        chain = [r]
        curr = r
        while True:
            info = all_sp.get(curr, {})
            nxt = info.get("evolve")
            lv = int(info.get("lv", 0) or 0)
            if not nxt or nxt == "否" or nxt not in all_sp:
                break
            chain.append((lv, nxt))
            curr = nxt
        chains.append(chain)
    return chains


def cmd_evolution_route(gid, qq, arg=""):
    """查看精灵进化路线 / 图谱（支持查询个人精灵、指定精灵家族或全服核心进化图谱）"""
    arg = (arg or "").strip()
    sp = _spirits(gid, qq)
    all_sp = _SPIRITS()

    # 1. 查询全服核心进化图谱
    if arg in ("全部", "图谱", "列表", "全", "all"):
        return (
            "🧬【全服核心精灵进化图谱】\r\n"
            "━━━━━━━━━━━━━━\r\n"
            "🌿【木系家族】\r\n"
            "  • 叶子 / 冬冬 ➔ Lv.50 小竹笋 ➔ Lv.90 开阳\r\n"
            "  • 落樱 / 小瑶 ➔ Lv.50 小翠 ➔ Lv.90 开阳\r\n"
            "🔥【火系家族】\r\n"
            "  • 火苗 / 小火猪 / 小火灵 ➔ Lv.50 小火花 ➔ Lv.90 朱雀\r\n"
            "  • 小火鸟 ➔ Lv.50 朱雀\r\n"
            "💧【水系家族】\r\n"
            "  • 水滴 / 库巴 ➔ Lv.50 小泉水 ➔ Lv.90 共工\r\n"
            "  • 艾斯 / 贝小壳 ➔ Lv.50 咚咚 ➔ Lv.90 共工\r\n"
            "❄️【冰雪·龙神·暗系】\r\n"
            "  • 雪仔 ➔ Lv.50 寒王子 ➔ Lv.130 御·星寒\r\n"
            "  • 冰公主 ➔ Lv.130 霜燚\r\n"
            "  • 烛 ➔ Lv.130 审判·宿　• 源 ➔ Lv.130 命运·狄\r\n"
            "  • 小幽 ➔ Lv.90 御·星寒　• 小黑 ➔ Lv.90 阿凯\r\n"
            "🪽【飞翼·金系·土系】\r\n"
            "  • 翼仔 ➔ Lv.50 毛绒绒 ➔ Lv.50 天玑\r\n"
            "  • 风仔 ➔ Lv.50 小空 ➔ Lv.50 紫辰\r\n"
            "  • 小酷 / 小落 / 小狼 ➔ Lv.50 玉衡\r\n"
            "  • 石灵 / 亚斯 ➔ Lv.50 玄武　• 岩兵 ➔ Lv.50 天璇\r\n"
            "🐾【灵幻·智系·圣光】\r\n"
            "  • 小沫沫 / 小彩 ➔ Lv.90 耀凌　• 梦蝶 ➔ Lv.90 御·星殊\r\n"
            "  • 文姬 / 小临 ➔ Lv.90 天权　• 药丸子 ➔ Lv.90 天枢\r\n"
            "  • 阿泠 ➔ Lv.90 御·星痕　• 光明 ➔ Lv.90 阴阳圣护\r\n"
            "  • 傻狗 ➔ Lv.90 傻狗光明　• 皮皮 ➔ Lv.50 阿雨\r\n"
            "━━━━━━━━━━━━━━\r\n"
            "💡 进化消耗：每次进化需消耗 1 个【进化液】（可在精灵商城购买）\r\n"
            "💡 发送【进化路线 精灵名】即可查询该精灵的专属进化分支！"
        )

    # 2. 查询指定精灵名字的进化路线
    if arg and arg not in ("我的", "状态", "自己"):
        chains = _get_spirit_chains(arg)
        if not chains:
            return f"亲，图鉴中未收录名为「{arg}」的精灵，发送【进化路线 全部】可查看图谱！"
        sp_info = all_sp.get(arg, {})
        sp_type = sp_info.get("type") or "普"
        lines = [f"🧬【精灵进化图鉴】·「{arg}」家族", "━━━━━━━━━━━━━━"]

        # 独立无法进化的精灵
        if len(chains) == 1 and len(chains[0]) == 1:
            lines.append(f"✨【{arg}】（属性：{sp_type}系）")
            lines.append("👑 形态：独有原生形态（无法进化）")
            lines.append("💡 说明：该精灵天生战力强悍，可通过升级综合成长、使用起司/美食、洗练极品性格与闪光觉醒培养至超高战力！")
            lines.append("━━━━━━━━━━━━━━")
            return "\r\n".join(lines)

        lines.append(f"属性归属：【{sp_type}系】　相关进化分支：")
        for idx, ch in enumerate(chains, 1):
            branch_str = []
            for item in ch:
                if isinstance(item, str):
                    branch_str.append(f"【{item}】")
                elif isinstance(item, (tuple, list)):
                    branch_str.append(f" ➔ (Lv.{item[0]}需进化液) ➔ 【{item[1]}】")
            prefix = f"分支{idx}：" if len(chains) > 1 else "路线："
            lines.append(f"  {prefix}{''.join(branch_str)}")

        lines.append("━━━━━━━━━━━━━━")
        lines.append("💡 进化说明：")
        lines.append("• 精灵达到指定等级后，携带 1 个【进化液】，发送【进化 精灵名】即可完成形态突破！")
        lines.append("• 突破后种族底表、六维数值与总战力将获得大幅质的飞跃！")
        return "\r\n".join(lines)

    # 3. 默认查询自己当前拥有的精灵进化进度
    lst = sp.get("list") or []
    if not lst:
        return "亲，您还没有领养精灵，请先发送【领养精灵】吧！发送【进化路线 全部】可查看全服图鉴。"

    bag = sp.get("bag") or {}
    evo_liquid_cnt = int(bag.get("进化液", 0) or 0)
    lines = ["🧬【我的精灵进化路线】", "━━━━━━━━━━━━━━"]

    act_name = sp.get("active")
    ready_count = 0
    for it in lst:
        if not isinstance(it, dict):
            continue
        nm = it.get("name")
        lvl = int(it.get("level", 1) or 1)
        base = all_sp.get(nm, {})
        evo = base.get("evolve", "否")
        evo_lv = int(base.get("lv", 0) or 0)
        mark = "【出战】" if nm == act_name else "【队伍】"

        if evo and evo != "否":
            if lvl >= evo_lv:
                ready_count += 1
                lines.append(f"{mark}{nm} Lv.{lvl} ➔ Lv.{evo_lv}「{evo}」✨【已达标！可进化】")
            else:
                lines.append(f"{mark}{nm} Lv.{lvl} ➔ Lv.{evo_lv}「{evo}」（还差 {evo_lv - lvl} 级）")
        else:
            lines.append(f"{mark}{nm} Lv.{lvl} 👑【已达终极形态】")

    lines.append("━━━━━━━━━━━━━━")
    lines.append(f"🎒 背包持有【进化液】：{evo_liquid_cnt} 个（可在【精灵商城】购买）")
    if ready_count > 0:
        lines.append(f"🎉 您当前有 {ready_count} 只精灵已满足进化等级！发送【进化 精灵名】即可突破！")
    else:
        lines.append("💡 发送【进化路线 精灵名】可查询任意图鉴进化树（如：【进化路线 火苗】）")
        lines.append("💡 发送【进化路线 全部】可浏览全服核心进化图谱")
    return "\r\n".join(lines)


def cmd_evolve(gid, qq, name=""):
    sp = _spirits(gid, qq)
    name = (name or "").strip()
    if not name:
        name = sp.get("active") or ""
    if not name:
        return "亲，请指定要进化的精灵名称：【进化 精灵名】（如：【进化 叶子】），也可发送【进化路线】查看进化进度！"
    it = _wsp(sp, name)
    if not it:
        return f"亲，您没有名为「{name}」的精灵，无法进化！"
    base = _SPIRITS().get(name, {})
    evo = base.get("evolve", "否")
    if not evo or evo == "否":
        return f"亲，【{name}】已经是终极形态了，无法再次进化！"
    evo_lv = int(base.get("lv", 0) or 0)
    cur_lv = int(it.get("level", 1) or 1)
    if cur_lv < evo_lv:
        return f"亲，【{name}】需要达到 Lv.{evo_lv} 才能进化，当前为 Lv.{cur_lv}（还差 {evo_lv - cur_lv} 级）！可先去【精灵冒险】或享用【起司/奇异甜食】升级哦~"
    bag = sp.setdefault("bag", {})
    if int(bag.get("进化液", 0) or 0) <= 0:
        return f"亲，【{name}】已达到进化等级 Lv.{evo_lv}，但还需要 1 个【进化液】才能激发潜能！请前往【精灵商城】购买吧！"
    bag["进化液"] = int(bag.get("进化液", 0)) - 1
    if int(bag.get("进化液", 0)) <= 0:
        del bag["进化液"]

    old_p = _power(it)
    _apply_new_species(it, evo)
    new_p = _power(it)

    if sp.get("active") == name and not _wsp(sp, name):
        sp["active"] = evo
    if sp.get("ride") == name and not _wsp(sp, name):
        sp["ride"] = evo
    tr = sp.get("travel")
    if isinstance(tr, dict) and tr.get("name") == name and not _wsp(sp, name):
        tr["name"] = evo
    expd = sp.get("expedition")
    if isinstance(expd, dict) and isinstance(expd.get("names"), list):
        for _idx_n, _en in enumerate(expd["names"]):
            if _en == name:
                expd["names"][_idx_n] = evo
                break
    _save(gid, qq, sp)

    new_base = _SPIRITS().get(evo, {}) or {}
    nxt_evo = new_base.get("evolve", "否")
    nxt_lv = int(new_base.get("lv", 0) or 0)
    nxt_tip = f"（下一阶段：Lv.{nxt_lv} 可进化为「{nxt_evo}」）" if (nxt_evo and nxt_evo != "否") else "（👑 已达成终极形态！）"

    trait = it.get("trait") or "温顺"
    return (f"🧬【形态突破·华丽进化】\r\n"
            f"恭喜！您的精灵「{name}」成功突破进化为「{_fmt_name(it)}」！\r\n"
            f"✨ 种族进阶：属性【{it.get('type')}系】 | 性格【{trait}】\r\n"
            f"📈 属性飞跃：生命 {it.get('hp')} | 攻击 {it.get('atk')} | 防御 {it.get('def')} | 特攻 {it.get('spa')} | 特防 {it.get('spd')} | 速度 {it.get('spe')}\r\n"
            f"💥 总战力大幅跃升：{old_p} ➔ {new_p}！\r\n"
            f"💡 {nxt_tip}")


def cmd_recast(gid, qq, name=""):
    """洗练性格天赋词条：消耗 1 个【洗练果实】，重置精灵性格词条并重算六维（按当前等级保留综合成长）"""
    sp = _spirits(gid, qq)
    target_name = (name or "").strip() or sp.get("active")
    it = _wsp(sp, target_name) if target_name else None
    if it is None:
        return "亲，请指定要洗练的精灵名称（如【洗练 叶子】）或先设置出战精灵！"
    bag = sp.setdefault("bag", {})
    if int(bag.get("洗练果实", 0) or 0) <= 0:
        return "亲，洗练性格需要消耗 1 个【洗练果实】，请先前往【精灵商城】购买！"
    old_trait = it.get("trait") or "温顺"
    base = _SPIRITS().get(it.get("name"), {}) or {}
    shiny = bool(it.get("shiny"))
    lvl = max(1, int(it.get("level", 1) or 1))
    old_calc = _calc_stats_at_level(base, level=lvl, shiny=shiny, trait=old_trait)
    new_trait = _roll_trait(prefer_rare=True)
    # 避免连续洗出同一个词条
    for _ in range(4):
        if new_trait != old_trait:
            break
        new_trait = _roll_trait(prefer_rare=True)
    new_calc = _calc_stats_at_level(base, level=lvl, shiny=shiny, trait=new_trait)
    for k in ("hp", "atk", "def", "spa", "spd", "spe"):
        bonus = max(0, int(it.get(k, 0)) - old_calc.get(k, 0))
        it[k] = new_calc.get(k, it.get(k, 0)) + bonus
    it["trait"] = new_trait
    bag["洗练果实"] = int(bag.get("洗练果实", 0)) - 1
    if bag["洗练果实"] <= 0:
        bag.pop("洗练果实", None)
    _save(gid, qq, sp)
    return (f"🎲 洗练成功！消耗「洗练果实」×1\r\n"
            f"精灵【{_fmt_name(it)}】性格由【{old_trait}】蜕变为【{new_trait}】（{_trait_desc(new_trait)}）！\r\n"
            f"当前总战力：{_power(it)}")


def cmd_awaken_shiny(gid, qq, name=""):
    """闪光觉醒：消耗 1 个【闪光结晶】，35% 概率觉醒为 ✨闪光 变异形态（全属性+15%），未命中也保底全属性+2"""
    sp = _spirits(gid, qq)
    target_name = (name or "").strip() or sp.get("active")
    it = _wsp(sp, target_name) if target_name else None
    if it is None:
        return "亲，请指定要觉醒的精灵名称（如【闪光觉醒 叶子】）或先设置出战精灵！"
    if it.get("shiny"):
        return f"亲，您的【{_fmt_name(it)}】已经是尊贵的 ✨闪光变异形态 了，无需重复觉醒！"
    bag = sp.setdefault("bag", {})
    if int(bag.get("闪光结晶", 0) or 0) <= 0:
        return "亲，闪光觉醒需要消耗 1 个【闪光结晶】，请先前往【精灵商城】购买！"
    bag["闪光结晶"] = int(bag.get("闪光结晶", 0)) - 1
    if bag["闪光结晶"] <= 0:
        bag.pop("闪光结晶", None)
    rate = int((_SHOP().get("闪光结晶") or {}).get("effect", 35) or 35)
    lvl = max(1, int(it.get("level", 1) or 1))
    if random.randint(1, 100) <= rate:
        base = _SPIRITS().get(it.get("name"), {}) or {}
        trait = it.get("trait") or "温顺"
        old_calc = _calc_stats_at_level(base, level=lvl, shiny=False, trait=trait)
        new_calc = _calc_stats_at_level(base, level=lvl, shiny=True, trait=trait)
        for k in ("hp", "atk", "def", "spa", "spd", "spe"):
            bonus = max(0, int(it.get(k, 0)) - old_calc.get(k, 0))
            it[k] = new_calc.get(k, it.get(k, 0)) + bonus
        it["shiny"] = 1
        _save(gid, qq, sp)
        return (f"🌟 奇迹降临！消耗「闪光结晶」×1\r\n"
                f"您的精灵成功突破基因枷锁，觉醒为【{_fmt_name(it)}】（全六维+15%）！\r\n"
                f"当前总战力：{_power(it)}")
    for k in ("hp", "atk", "def", "spa", "spd", "spe"):
        it[k] = int(it.get(k, 0)) + 2
    _save(gid, qq, sp)
    return (f"✨ 消耗「闪光结晶」×1，虽未完全觉醒闪光形态，但结晶能量浸润全身：\r\n"
            f"【{it.get('name')}】全六维属性保底 +2（当前总战力：{_power(it)}）！")


def cmd_use_item(gid, qq, raw_arg):
    """使用背包道具（奇异甜食/吐司/攻击之源/防御之源/特防之源/特攻之源/进化液/洗练果实/闪光结晶），默认作用于当前出战精灵"""
    raw_arg = (raw_arg or "").strip()
    if not raw_arg:
        return "亲，使用物品格式为：【使用物品 物品名称*数量】（如：使用物品 奇异甜食*1）！"
    import re as _re_item
    m = _re_item.match(r"^([^*\s×xX]+)(?:[\s*×xX]+(\d+))?$", raw_arg)
    if not m:
        return "亲，使用物品格式为：【使用物品 物品名称*数量】！"
    item_name = m.group(1).strip()
    cnt = max(1, min(999, int(m.group(2) or 1)))
    sp = _spirits(gid, qq)
    bag = sp.setdefault("bag", {})
    have = int(bag.get(item_name, 0) or 0)
    if have <= 0:
        return f"亲，您的背包中没有「{item_name}」，请先前往【精灵商城】购买！"
    if have < cnt:
        return f"亲，您的背包中「{item_name}」仅有 {have} 个，不足 {cnt} 个！"
    act_name = sp.get("active")
    it = _wsp(sp, act_name) if act_name else None
    if it is None:
        return "亲，请先发送【出战精灵 名称】指定要培养的出战精灵！"
    shop = _SHOP()
    info = shop.get(item_name, {}) or {}
    attr = str(info.get("attr", "")).strip()
    eff = int(info.get("effect", 1) or 1)
    if attr == "精灵球":
        return f"亲，「{item_name}」是精灵球，请发送【使用精灵球 {item_name}】收服野生精灵！"
    if attr == "进化" or item_name == "进化液":
        return cmd_evolve(gid, qq, act_name)
    if attr == "洗练" or item_name == "洗练果实":
        return cmd_recast(gid, qq, act_name)
    if attr == "闪光" or item_name == "闪光结晶":
        return cmd_awaken_shiny(gid, qq, act_name)
    if attr == "美食" or item_name in ("起司", "吐司"):
        gain_bond = 15 * cnt
        gain_exp = 300 * cnt
        cur_bond = int(it.get("bond", 0) or 0) + gain_bond
        it["bond"] = cur_bond
        hp_add = 10 * cnt
        atk_add = 2 * cnt
        def_add = 2 * cnt
        spa_add = 2 * cnt
        spd_add = 2 * cnt
        spe_add = 1 * cnt
        it["hp"] = int(it.get("hp", 0) or 0) + hp_add
        it["atk"] = int(it.get("atk", 0) or 0) + atk_add
        it["def"] = int(it.get("def", 0) or 0) + def_add
        it["spa"] = int(it.get("spa", 0) or 0) + spa_add
        it["spd"] = int(it.get("spd", 0) or 0) + spd_add
        it["spe"] = int(it.get("spe", 0) or 0) + spe_add
        it["buff_stamina"] = True
        bag[item_name] = have - cnt
        if bag[item_name] <= 0:
            bag.pop(item_name, None)
        evo_hint = ""
        if int(it.get("level", 1)) < _cfgi("最大等级", 100):
            evo_hint = _add_exp(gid, qq, sp, it, gain_exp, save_now=False) or ""
        _save(gid, qq, sp)
        return (f"🧀 美味享用！出战精灵【{_fmt_name(it)}】美美地享用了「{item_name}」×{cnt}！\r\n"
                f"💖 亲密羁绊 +{gain_bond}（当前羁绊值：{cur_bond}）\r\n"
                f"✨ 经验 +{gain_exp}，体质大增：生命+{hp_add}、攻防各+{atk_add}、速度+{spe_add}\r\n"
                f"⚡ 充满活力！精灵进入【精力充沛】状态（总战力：{_power(it)}）"
                + (f"\r\n{evo_hint.strip()}" if evo_hint else ""))
    field_map = {
        "等级": "level",
        "HP": "hp",
        "生命": "hp",
        "攻击": "atk",
        "防御": "def",
        "特攻": "spa",
        "特防": "spd",
        "速度": "spe",
    }
    field = field_map.get(attr)
    if not field:
        return f"亲，「{item_name}」暂无法直接使用！"
    if field == "level":
        max_lv = _cfgi("最大等级", 100)
        cur_lv = int(it.get("level", 1))
        if cur_lv >= max_lv:
            return f"亲，您的精灵【{act_name}】已达最高等级 Lv.{max_lv}！"
        cnt = min(cnt, max_lv - cur_lv)
        it["level"] = cur_lv + cnt

        # 升级综合加全六维属性！
        base = _SPIRITS().get(it.get("name"), {}) or {}
        shiny = bool(it.get("shiny"))
        trait = it.get("trait") or "温顺"
        base_v = _calc_variant_stats(base, shiny=shiny, trait=trait)
        growth = _calc_level_growth(base_v)
        for k in ("hp", "atk", "def", "spa", "spd", "spe"):
            it[k] = int(it.get(k, 0)) + growth.get(k, 1) * cnt

        evo_hint = ""
        evo = base.get("evolve", "否")
        if evo and evo != "否" and it["level"] >= int(base.get("lv", 0) or 0):
            evo_hint = f"\r\n💡 【{act_name}】已达进化等级 Lv.{base.get('lv', 0)}，可发送【进化 {act_name}】完成形态突破！"

        bag[item_name] = have - cnt
        if bag[item_name] <= 0:
            bag.pop(item_name, None)
        _save(gid, qq, sp)
        return (f"✨ 使用成功！消耗「{item_name}」×{cnt}\r\n"
                f"出战精灵【{_fmt_name(it)}】等级升至 Lv.{it['level']}（+{cnt}级）！\r\n"
                f"📈 综合属性提升：生命+{growth['hp']*cnt}、攻击+{growth['atk']*cnt}、防御+{growth['def']*cnt}、特攻+{growth['spa']*cnt}、特防+{growth['spd']*cnt}、速度+{growth['spe']*cnt}！\r\n"
                f"💥 当前总战力：{_power(it)}{evo_hint}")
    delta = eff * cnt
    it[field] = int(it.get(field, 0)) + delta
    bag[item_name] = have - cnt
    if bag[item_name] <= 0:
        bag.pop(item_name, None)
    _save(gid, qq, sp)
    return (f"✨ 使用成功！消耗「{item_name}」×{cnt}\r\n"
            f"出战精灵【{_fmt_name(it)}】{attr}+{delta}（当前 {it[field]}，总战力 {_power(it)}）")


def cmd_bond(gid, qq, arg=""):
    """羁绊互动：每日与出战精灵互动可提升羁绊亲密度并获得全维属性与经验加成"""
    sp = _spirits(gid, qq)
    act_name = (arg or "").strip() or sp.get("active")
    it = _wsp(sp, act_name) if act_name else None
    if it is None:
        return "亲，请先【出战精灵 名称】或发送【羁绊 精灵名称】与精灵互动！"
    bond_val = int(it.get("bond", 0) or 0)
    today = time.strftime("%Y%m%d")
    last_day = str(it.get("bond_day", "") or "")
    if last_day != today:
        gain = random.randint(5, 12)
        bond_val += gain
        it["bond"] = bond_val
        it["bond_day"] = today
        stat_key, stat_label = random.choice([
            ("hp", "生命"), ("atk", "攻击"), ("def", "防御"), ("spa", "特攻"), ("spd", "特防")
        ])
        it[stat_key] = int(it.get(stat_key, 0)) + 1
        _add_exp(gid, qq, sp, it, 120)
        return (f"💖 羁绊互动｜与【{it.get('name', act_name)}】亲密互动成功！\r\n"
                f"亲密度 +{gain}（当前羁绊值：{bond_val}）\r\n"
                f"羁绊回馈：{stat_label}+1、经验+120（当前总战力：{_power(it)}）")
    return (f"💖 【{it.get('name', act_name)}】当前羁绊值：{bond_val}\r\n"
            f"今日已完成亲密互动，明天再来陪伴它吧！（总战力：{_power(it)}）")


def _pick_shop_drop(charm_val=0, high_tier_bonus=0):
    """从现有 _SHOP() 商城池抽取战利品：三阶分层，顶级极品严格限制在 0.5%~0.8% 超低欧皇概率"""
    shop = _SHOP()
    if not shop:
        return "精灵球"
    # 极品池：商城售价极高的顶级奢侈品（洗练果实1.5w/闪光结晶8.8w/进化液10w），严格控制在 ≤ 0.8%
    top_pool = [k for k in ("洗练果实", "闪光结晶", "进化液") if k in shop] or ["洗练果实"]
    # 进阶池：中高阶消耗品（约 8%~12%）
    rare_pool = [k for k in ("极速球", "大师球", "特攻之源", "奇异甜食") if k in shop] or ["极速球"]
    # 普通池：日常基础消耗品（约 88%~91%）
    common_pool = [k for k in ("精灵球", "时间球", "狩猎球", "吐司", "攻击之源", "防御之源", "特防之源") if k in shop] or list(shop.keys())

    # 极品概率：基础 0.5%，满魅力/满远征最多微调到 0.8%（真正欧皇大奖）
    top_rate = min(0.8, 0.5 + max(0, int(charm_val or 0)) / 2000.0 + int(high_tier_bonus or 0) * 0.05)
    # 稀有概率：基础 8%，最高 12%
    rare_rate = min(12.0, 8.0 + max(0, int(charm_val or 0)) / 100.0 + int(high_tier_bonus or 0) * 0.5)

    roll = random.uniform(0, 100)
    if roll <= top_rate:
        return random.choice(top_pool)
    if roll <= top_rate + rare_rate:
        return random.choice(rare_pool)
    return random.choice(common_pool)


def cmd_travel(gid, qq, arg=""):
    """旅行精灵 / 外出漫游：消耗体力+魅力派携带/出战精灵外出旅行，归来带回现有商城伴手礼、金币、经验与羁绊"""
    sp = _spirits(gid, qq)
    if not sp.get("list"):
        return "亲，您还没有精灵，请先【领养精灵】吧！"
    now = int(time.time())
    tr = sp.get("travel")
    if isinstance(tr, dict) and tr.get("name") and tr.get("ts"):
        t_name = tr.get("name")
        dur_s = max(60, int(tr.get("dur", 3600) or 3600))
        left_s = int(tr.get("ts", 0)) + dur_s - now
        if left_s > 0:
            left_m = max(1, (int(left_s) + 59) // 60)
            return (f"🧳 您的精灵【{t_name}】正在外出漫游中~\r\n"
                    f"⏳ 距离归来还需约 {ST.format_cd_time(left_s)}，届时发送【旅行精灵】即可迎接并拆开伴手礼！")
        # 已完成旅行，结算伴手礼
        it = _wsp(sp, t_name) or (sp["list"][0] if sp.get("list") else None)
        charm_val = _u(gid, qq).int("charm")
        drop_item = _pick_shop_drop(charm_val=charm_val, high_tier_bonus=5)
        t_lo = max(0, _cfgi("旅行金币下限", 180))
        t_hi = max(t_lo, _cfgi("旅行金币上限", 450))
        gold_gain = random.randint(t_lo, t_hi)
        try:
            try:
                from ..ride import active_ride_info
            except ImportError:
                from games.ride import active_ride_info  # type: ignore
            _, _r_pct = active_ride_info(gid, qq)
            if _r_pct > 0:
                gold_gain += gold_gain * int(_r_pct) // 100
        except Exception:
            pass
        exp_gain = random.randint(60, 120)
        cheese_bonus_tip = ""
        if it is not None and it.pop("buff_stamina", None):
            gold_gain = int(gold_gain * 1.5)
            exp_gain = int(exp_gain * 1.5)
            cheese_bonus_tip = "\r\n⚡ 触发【精力充沛】饱腹增益：本次旅行收益额外提升50%！"
        bag = sp.setdefault("bag", {})
        bag[drop_item] = int(bag.get(drop_item, 0) or 0) + 1
        sp.pop("travel", None)
        evo_note = ""
        if it is not None:
            it["bond"] = int(it.get("bond", 0) or 0) + 5
            if int(it.get("level", 1)) < _cfgi("最大等级", 100):
                evo_note = _add_exp(gid, qq, sp, it, exp_gain, save_now=False)
        if ST.txn_coins_acct(gid, qq, gold_gain, {"spirits": json.dumps(sp, ensure_ascii=False)}) is None:
            return "旅行结算系统繁忙，请稍后重试！"
        story = random.choice(TRAVEL_EVENTS)
        spr_disp = _fmt_name(it) if it else t_name
        return (f"💌【旅行归来】您的精灵「{spr_disp}」漫游归来啦！\r\n"
                f"📖 旅途见闻：{story}。\r\n"
                f"🎁 伴手礼：「{drop_item}」×1（已放入背包）\r\n"
                f"✨ 旅途收获：{ST.coin_name()}+{ST.fmt_coins(gold_gain)}、经验+{exp_gain}、羁绊+5"
                + cheese_bonus_tip
                + (f"\r\n{evo_note.strip()}" if evo_note else ""))

    expd = sp.get("expedition")
    expd_rem = list(expd.get("names") or []) if (isinstance(expd, dict) and expd.get("names") and expd.get("ts")) else []
    free_for_travel = []
    for x in sp.get("list", []):
        nm = x.get("name")
        if nm in expd_rem:
            expd_rem.remove(nm)
        else:
            free_for_travel.append(x)
    if not free_for_travel:
        return "亲，您的精灵目前都在远征途中，请等【精灵远征】归来后再派精灵外出漫游吧！"
    arg_name = (arg or "").strip()
    if arg_name:
        it = next((x for x in free_for_travel if x.get("name") == arg_name), None)
        if it is None:
            if _wsp(sp, arg_name) is not None:
                return f"亲，精灵「{arg_name}」正在远征途中，暂时无法外出漫游！"
            return "亲，您未拥有该精灵，请检查名称或发送【我的精灵】查看！"
    else:
        pref_name = sp.get("ride") or sp.get("active")
        it = next((x for x in free_for_travel if x.get("name") == pref_name), None) if pref_name else None
        if it is None:
            it = free_for_travel[0]
    cost_stam = max(1, _cfgi("旅行消耗体力", 10))
    cost_charm = max(0, _cfgi("旅行消耗魅力", 5))
    dur_min = max(1, _cfgi("旅行时长分钟", 60))
    with ST._LOCK:
        a = _u(gid, qq)
        cur_st = a.int("stamina")
        cur_ch = a.int("charm")
        if cur_st < cost_stam:
            return f"亲，派精灵外出漫游需要消耗 {cost_stam} 点体力，当前体力（{cur_st}）不足！"
        if cur_ch < cost_charm:
            return f"亲，派精灵外出漫游需要消耗 {cost_charm} 点魅力，当前魅力（{cur_ch}）不足！"
        sp["travel"] = {"name": it.get("name"), "ts": now, "dur": dur_min * 60}
        updates = {
            "stamina": str(max(0, cur_st - cost_stam)),
            "charm": str(max(0, cur_ch - cost_charm)),
            "spirits": json.dumps(sp, ensure_ascii=False),
        }
        if ST.txn_coins_acct(gid, qq, 0, updates) is None:
            return "旅行系统繁忙，本次出发未成功，请稍后重试！"
    return (f"🧳 精灵「{_fmt_name(it)}」背起小行囊外出漫游啦！\r\n"
            f"⚡ 消耗体力 -{cost_stam}　💄 消耗魅力 -{cost_charm}\r\n"
            f"⏳ 预计 {dur_min} 分钟后归来，届时再次发送【旅行精灵】即可领取伴手礼！")


def cmd_expedition(gid, qq, arg=""):
    """闲置精灵远征队：消耗少量体力派遣仓库闲置精灵远征，收获金币、全员经验与现有商城道具"""
    sp = _spirits(gid, qq)
    lst = sp.get("list") or []
    if not lst:
        return "亲，您还没有精灵，请先【领养精灵】吧！"
    now = int(time.time())
    expd = sp.get("expedition")
    if isinstance(expd, dict) and expd.get("names") and expd.get("ts"):
        names = list(expd.get("names") or [])
        dur_s = max(60, int(expd.get("dur", 7200) or 7200))
        left_s = int(expd.get("ts", 0)) + dur_s - now
        if left_s > 0:
            left_m = max(1, (int(left_s) + 59) // 60)
            return (f"🚩【远征进行中】远征小队（{'、'.join(names)}）正在探索秘境深处！\r\n"
                    f"⏳ 距离远征完成还需约 {ST.format_cd_time(left_s)}，完成后发送【精灵远征】即可收获战利品！")
        # 远征完成，结算全队经验 + 金币 + 现有商城道具池掉落
        charm_val = _u(gid, qq).int("charm")
        rem_names = list(names)
        team_its = []
        for x in lst:
            nm = x.get("name")
            if nm in rem_names:
                team_its.append(x)
                rem_names.remove(nm)
        if not team_its:
            team_its = lst[:min(3, len(lst))]
        cnt = max(1, len(team_its))
        total_p = sum(_power(x) for x in team_its)
        e_lo = max(0, _cfgi("远征单只金币下限", 180))
        e_hi = max(e_lo, _cfgi("远征单只金币上限", 360))
        gold_gain = random.randint(e_lo * cnt, e_hi * cnt) + min(500, total_p // 40)
        try:
            try:
                from ..ride import active_ride_info
            except ImportError:
                from games.ride import active_ride_info  # type: ignore
            _, _r_pct2 = active_ride_info(gid, qq, aspect="travel")
            if _r_pct2 > 0:
                gold_gain += gold_gain * int(_r_pct2) // 100
        except Exception:
            pass
        exp_gain = random.randint(80, 160)
        bag = sp.setdefault("bag", {})
        drops = []
        # 远征产出调优：保底 1 件道具，队伍≥2只且高战力大成功时有 25% 概率额外带回第2件，杜绝无限批发
        drop_count = 1
        if cnt >= 2 and random.randint(1, 100) <= min(25, 10 + cnt * 5):
            drop_count = 2
        for _ in range(drop_count):
            d_item = _pick_shop_drop(charm_val=charm_val, high_tier_bonus=cnt)
            bag[d_item] = int(bag.get(d_item, 0) or 0) + 1
            drops.append(d_item)
        sp.pop("expedition", None)
        evo_msgs = []
        for x in team_its:
            if int(x.get("level", 1)) < _cfgi("最大等级", 100):
                ev = _add_exp(gid, qq, sp, x, exp_gain, save_now=False)
                if ev:
                    evo_msgs.append(f"{x.get('name')}:{ev.strip()}")
        if ST.txn_coins_acct(gid, qq, gold_gain, {"spirits": json.dumps(sp, ensure_ascii=False)}) is None:
            return "远征结算系统繁忙，请稍后重试！"
        drop_summary = "、".join(f"「{d}」" for d in drops)
        evo_txt = ("\r\n🧬 进化喜讯：" + "；".join(evo_msgs)) if evo_msgs else ""
        return (f"🚩【远征凯旋】远征小队（{'、'.join(_fmt_name(x) for x in team_its)}）满载而归！\r\n"
                f"💰 远征赏金：{ST.coin_name()}+{ST.fmt_coins(gold_gain)}\r\n"
                f"📈 全员历练：参战精灵经验各 +{exp_gain}\r\n"
                f"🎁 战利品：{drop_summary}（已放入背包）"
                f"{evo_txt}")

    # 开启新远征：排除正在外出旅行的精灵，并优先选非出战闲置精灵
    tr = sp.get("travel")
    tr_it = _wsp(sp, tr.get("name")) if (isinstance(tr, dict) and tr.get("name") and tr.get("ts")) else None
    avail_lst = [x for x in lst if x is not tr_it]
    if not avail_lst:
        return "亲，您的精灵正在外出漫游中，暂时没有空闲精灵可派遣远征！"
    act_name = sp.get("active")
    act_it = _wsp(sp, act_name) if act_name else None
    idle_pool = [x for x in avail_lst if x is not act_it] if len(avail_lst) > 1 else list(avail_lst)
    if not idle_pool:
        idle_pool = list(avail_lst)
    idle_pool.sort(key=lambda x: _power(x), reverse=True)
    max_team = max(1, _cfgi("远征最大精灵数", 3))
    unit_stam = max(1, _cfgi("远征单只体力", _cfgi("远征单只消耗体力", 8)))
    dur_min = max(1, _cfgi("远征时长分钟", 120))

    with ST._LOCK:
        a = _u(gid, qq)
        cur_st = a.int("stamina")
        if cur_st < unit_stam:
            return f"亲，派遣精灵远征每只精灵需消耗 {unit_stam} 点体力，您当前体力（{cur_st}）不足！"
        afford_cnt = max(1, cur_st // unit_stam)
        chosen = idle_pool[:min(max_team, len(idle_pool), afford_cnt)]
        cost_stam = len(chosen) * unit_stam
        chosen_names = [x.get("name") for x in chosen if x.get("name")]
        sp["expedition"] = {"names": chosen_names, "ts": now, "dur": dur_min * 60}
        updates = {
            "stamina": str(max(0, cur_st - cost_stam)),
            "spirits": json.dumps(sp, ensure_ascii=False),
        }
        if ST.txn_coins_acct(gid, qq, 0, updates) is None:
            return "远征系统繁忙，本次派遣未成功，请稍后重试！"
    return (f"🚩【远征出发】已派遣 {len(chosen)} 只精灵（{'、'.join(_fmt_name(x) for x in chosen)}）组成远征队！\r\n"
            f"⚡ 消耗体力：{cost_stam} 点（{unit_stam}×{len(chosen)}）\r\n"
            f"⏳ 远征时长：{dur_min} 分钟，归来后发送【精灵远征】即可收获全队经验与商城道具战利品！")


# ---- 精灵PVP(总战力对打) ----
def cmd_pvp(gid, qq, target):
    raw_arg = (target or "").strip()
    if not raw_arg:
        return "亲，请指定对战目标：【精灵对战 @对方】！"
    t = None
    import re as _re_pvp
    # 1. 优先提取 CQ 码中的 QQ
    m_cq = _re_pvp.search(r"\[CQ:at,qq=(\d+)[^\]]*\]", raw_arg)
    if m_cq:
        t = m_cq.group(1)
    # 2. 匹配 @数字 格式（含 AstrBot 追加的 @QQ）
    if not t:
        m_at_qq = _re_pvp.search(r"@\s*(\d{4,12})\b", raw_arg)
        if m_at_qq:
            t = m_at_qq.group(1)
    # 3. 匹配独立纯数字 QQ 串
    if not t:
        m_qq = _re_pvp.search(r"(?:^|\s)(\d{4,12})(?:\s|$)", raw_arg)
        if m_qq:
            t = m_qq.group(1)
    # 4. 尝试 parse_at 提取
    if not t:
        t_at, _ = ST.parse_at(raw_arg)
        if t_at and str(t_at).isdigit():
            t = str(t_at).strip()
    # 5. 尝试按群名片/昵称反查 QQ
    if not t:
        clean_name = raw_arg.lstrip("@").strip()
        if clean_name:
            try:
                from ..slave.handler import _find_slave_qq_by_name
                found_q = _find_slave_qq_by_name(gid, clean_name)
                if found_q and str(found_q).isdigit():
                    t = str(found_q).strip()
            except Exception:
                pass
    if not t or not t.isdigit():
        return "亲，请指定对战目标：【精灵对战 @对方】！"
    target = t
    if target == str(qq):
        return "亲，不能与自己进行精灵对战！"
    sp = _spirits(gid, qq)
    mine = _wsp(sp, sp.get("active")) if sp.get("active") else None
    tsp = _spirits(gid, target)
    theirs = _wsp(tsp, tsp.get("active")) if tsp.get("active") else None
    if mine is None:
        return "亲，您还没有出战的精灵，无法对战！"
    if theirs is None:
        return "对方没有出战的精灵，无法对战！"
    cd_key = f"sp_pvp_{gid}_{qq}"
    last_ts = float(_recall_get(cd_key, "0") or 0)
    cd_s = max(1, _cfgi("对战间隔", 1)) * 60
    if last_ts and time.time() - last_ts < cd_s:
        rem_s = cd_s - (time.time() - last_ts)
        return f"亲，您的精灵刚经历过激战，请休息 {ST.format_cd_time(rem_s)}后再发起对战吧！"
    myp, tap = _power(mine), _power(theirs)
    my_cash, ta_cash = ST.coins_get(gid, qq), ST.coins_get(gid, target)
    stake = min(PVP_STAKE_CAP, max(200, my_cash // PVP_STAKE_DIV), max(200, ta_cash // PVP_STAKE_DIV))
    pwin = myp / (myp + tap) if (myp + tap) else 0.5
    try:
        from ..sign import eff_p01 as _LP01
        pwin = _LP01(pwin, gid, qq)
    except Exception:
        pass
    win = random.random() < pwin
    _recall_set(cd_key, str(time.time()))
    # 零和原子转账：若败方现金不足则按其实有现金划转（避免固定报0金币）
    if win:
        real_stake = min(stake, ta_cash)
        if real_stake > 0:
            try:
                _ok = ST.txn_two_wallets(gid, target, qq, real_stake)
            except Exception:
                _ok = None
            if _ok is None:
                return "精灵对战结算繁忙，本次结果未生效，请稍后重试！"
            real = real_stake if _ok is True else 0
        else:
            real = 0
        reward_txt = f"获得 {ST.fmt_coins(real)} {ST.coin_name()}！" if real > 0 else "（对方现金为0，本次为荣誉切磋）"
        return (f"⚔️ 精灵对战\r\n你(战力{myp}) vs {lstr(target, gid)}(战力{tap})\r\n"
                f"【你赢！】{reward_txt}")
    real_stake = min(stake, my_cash)
    if real_stake > 0:
        try:
            _ok = ST.txn_two_wallets(gid, qq, target, real_stake)
        except Exception:
            _ok = None
        if _ok is None:
            return "精灵对战结算繁忙，本次结果未生效，请稍后重试！"
        real = real_stake if _ok is True else 0
    else:
        real = 0
    lose_txt = f"损失 {ST.fmt_coins(real)} {ST.coin_name()}！" if real > 0 else "（现金为0，未损失金币）"
    return (f"⚔️ 精灵对战\r\n你(战力{myp}) vs {lstr(target, gid)}(战力{tap})\r\n"
            f"【你输…】{lose_txt}")


def cmd_rank(gid, kind):
    kind = kind or "总战力"
    label = {"等级": "等级", "生命": "生命", "攻击": "攻击", "防御": "防御",
             "特攻": "特攻", "特防": "特防", "总战力": "总战力", "战力": "总战力"}.get(kind, "总战力")
    # 批量单次查询+内存解析（原每行2次json.loads+list遍历，500人~35ms→8ms）
    with ST._LOCK:
        rows = ST._DB.execute("SELECT qq, data FROM accounts WHERE gid=?",
                              (int(gid),)).fetchall() if ST._DB else []
    keymap = {"等级": "level", "生命": "hp", "攻击": "atk", "防御": "def",
              "特攻": "spa", "特防": "spd"}
    kfield = keymap.get(kind, "level")
    lst = []
    for qq, data in rows:
        try:
            outer = json.loads(data) if data else {}
        except Exception:
            continue
        # 兼容：spirits 可能是 dict 或 json 字符串，或直接在 outer
        inner = outer.get("spirits", {}) if isinstance(outer, dict) else {}
        if isinstance(inner, str):
            try:
                inner = json.loads(inner or "{}")
            except Exception:
                inner = {}
        if isinstance(outer, dict) and isinstance(inner, dict) and not inner.get("list") and outer.get("list"):
            inner = outer
        if not isinstance(inner, dict):
            inner = {}
        best = None; bestv = -1
        # 单次遍历取最强一只
        for it in inner.get("list", []) if isinstance(inner, dict) else []:
            try:
                v = _power(it) if label == "总战力" else int(it.get(kfield, 0))
            except Exception:
                v = 0
            if v > bestv:
                bestv = v; best = it
        if best:
            lst.append((bestv, str(qq), _fmt_name(best)))
    lst.sort(reverse=True)
    lines = [f"---精灵{label}排行---"]
    for i, (v, q, nm) in enumerate(lst[:10], 1):
        # 加 emoji/单位 隔开，避免 QQ 与战力数值粘连
        if label == "总战力":
            lines.append(f"{i}. {nm}　{lstr(q, gid)}　💥 {v} 战力")
        elif label == "等级":
            lines.append(f"{i}. {nm}　{lstr(q, gid)}　⭐ Lv.{v}")
        else:
            lines.append(f"{i}. {nm}　{lstr(q, gid)}　✨ {v}")
    lines.append("温馨提示：精灵总战力是结合精灵等级、血量、攻击、防御、特攻、特防计算出来的总属性！")
    return "\r\n".join(lines)


def lstr(q, gid=None):
    try:
        try:
            from .. import slave as S
        except ImportError:
            from games import slave as S
        return S.display_name(gid, q, q)
    except Exception:
        return q


def _recall_set(k, v):
    ST.recall_set(k, v)


def _recall_get(k, d=None):
    return ST.recall_get(k, d)


# ---- 统一入口 ----
def handle(gid, qq, raw):
    try:
        return _handle_inner(gid, qq, raw)
    except Exception:
        return "精灵系统繁忙，请稍后重试~"


def _handle_inner(gid, qq, raw):
    raw_str = (raw or "").strip()
    if not raw_str:
        return None

    import re as _re_inner
    target = None
    t_parsed, clean = ST.parse_at(raw_str)
    if t_parsed and str(t_parsed).isdigit():
        target = str(t_parsed).strip()

    bot_uin = ""
    try:
        from games import slave as _slv
        bot_uin = str(getattr(_slv, "BOT_UIN", "") or "")
    except Exception:
        try:
            from .. import slave as _slv
            bot_uin = str(getattr(_slv, "BOT_UIN", "") or "")
        except Exception:
            pass

    if target in (str(qq), bot_uin):
        target = None

    # 将 clean 文本中残留的 @数字、[CQ:at,qq=数字]、[At:数字] 彻底清除，得到干净指令词
    clean = _re_inner.sub(r"(?:\[CQ:at,qq=\d+[^\]]*\]|\[At:\s*\d+\])", "", clean)
    clean = _re_inner.sub(r"@\s*\S+", "", clean).strip()

    m = clean
    if not m:
        return None
    _wake = ST.wake("精灵系统", "精灵系统")
    # 开关
    if _need_switch() and m not in _wake:
        return "【精灵系统】已经被关闭了，无法使用该功能！\r\n如需开启，请机器人管理发送【精灵开关】进行开启！"
    # 指令分发
    if m in _wake or m in ("精灵系统", "精灵菜单", "精灵帮助", "精灵玩法", "精灵"):
        return MENU
    if m.startswith(("领养精灵", "领养")):
        _pfx = "领养精灵" if m.startswith("领养精灵") else "领养"
        return cmd_adopt(gid, qq, m[len(_pfx):].strip())
    if m == "领取精灵礼包":
        return cmd_gift(gid, qq)
    if m.startswith(("我的精灵", "精灵列表")):
        _pfx = "我的精灵" if m.startswith("我的精灵") else "精灵列表"
        rest = m[len(_pfx):].strip()
        if not target and rest.isdigit() and 4 <= len(rest) <= 12:
            target = rest
            rest = ""
        if not rest:
            return cmd_my(gid, qq, target=target)
        return None
    m_trim = m.rstrip("!！。?？~ ").strip()
    if m_trim in ("精灵商城", "精灵商店"):
        return cmd_shop()
    if m.startswith(("我的背包", "精灵背包")):
        _pfx = "我的背包" if m.startswith("我的背包") else "精灵背包"
        rest = m[len(_pfx):].strip()
        if not rest:
            return cmd_backpack(gid, qq)
        return None
    if m == "精灵地图":
        return cmd_map()
    if m.startswith("查看地图"):
        return cmd_map_detail(gid, qq, m[4:].strip())
    if m in ("查看出战精灵", "出战状态"):
        return cmd_active(gid, qq)
    if m == "回收出战精灵":
        return cmd_cancel_active(gid, qq)
    # 带参数
    if m.startswith(("查看精灵", "查询精灵")):
        _pfx = "查看精灵" if m.startswith("查看精灵") else "查询精灵"
        return cmd_view(gid, qq, m[len(_pfx):].strip())
    if m.startswith("购买"):
        # 坐骑系统的 购买坐骑 由坐骑引擎接管, 此处放行
        if m.startswith(("购买坐骑", "购买体力", "购买魅力", "购买奴隶位")):
            return None
        _raw_b = m[2:]
        _barg = _raw_b.strip()
        return cmd_buy(gid, qq, _barg)
    if m.startswith("精灵冒险"):
        return cmd_adventure(gid, qq, m[4:].strip())
    if m.startswith("使用精灵球"):
        return cmd_catch(gid, qq, m[5:].strip())
    if m.startswith(("使用物品", "使用道具", "使用", "吃")):
        _pfx = "使用物品" if m.startswith("使用物品") else ("使用道具" if m.startswith("使用道具") else ("使用" if m.startswith("使用") else "吃"))
        _uarg = m[len(_pfx):].strip()
        if _uarg:
            shop = _SHOP()
            sp_bag = _spirits(gid, qq).get("bag", {})
            if any(_uarg.startswith(k) for k in shop) or any(_uarg.startswith(k) for k in sp_bag):
                return cmd_use_item(gid, qq, _uarg)
    if m.startswith(("出战精灵", "出战")):
        _pfx = "出战精灵" if m.startswith("出战精灵") else "出战"
        return cmd_set_active(gid, qq, m[len(_pfx):].strip())
    if m.startswith("携带精灵"):
        return cmd_ride(gid, qq, m[4:].strip())
    if m.startswith("丢弃精灵"):
        return cmd_discard(gid, qq, m[4:].strip())
    if m.startswith(("进化路线", "精灵进化路线", "进化图鉴", "进化链", "进化树")):
        _pfx = next(p for p in ("精灵进化路线", "进化路线", "进化图鉴", "进化链", "进化树") if m.startswith(p))
        return cmd_evolution_route(gid, qq, m[len(_pfx):].strip())
    if m.startswith("进化"):
        _raw_e = m[2:]
        _earg = _raw_e.strip()
        return cmd_evolve(gid, qq, _earg)
    if m.startswith("洗练"):
        _raw_r = m[2:]
        _rarg = _raw_r.strip()
        if not _rarg or _rarg in _SPIRITS() or _raw_r[:1].isspace():
            return cmd_recast(gid, qq, _rarg)
        return None
    if m.startswith(("闪光觉醒", "精灵变异")):
        return cmd_awaken_shiny(gid, qq, m[4:].strip())
    for _tp in ("旅行精灵", "外出漫游", "精灵旅行", "召回旅行"):
        if m.startswith(_tp):
            return cmd_travel(gid, qq, m[len(_tp):].strip())
    for _ep in ("精灵远征", "派遣远征", "收获远征", "远征状态"):
        if m.startswith(_ep):
            return cmd_expedition(gid, qq, m[len(_ep):].strip())
    if m.startswith("精灵对战"):
        _carg = m[4:].strip() or (target or "")
        return cmd_pvp(gid, qq, _carg)
    if m.startswith("挑战"):
        _raw_c = m[2:]
        _carg = _raw_c.strip() or (target or "")
        if not _carg or _carg.startswith(("@", "[CQ:at")) or _carg[:1].isdigit():
            return cmd_pvp(gid, qq, _carg)
        return None
    if m.startswith("羁绊"):
        _raw_bd = m[2:]
        _bdarg = _raw_bd.strip()
        if not _bdarg or _bdarg in _SPIRITS() or _raw_bd[:1].isspace():
            return cmd_bond(gid, qq, _bdarg)
        return None
    if m.startswith("精灵排行"):
        return cmd_rank(gid, m[4:].strip())
    return None


COMMANDS = (
    "领养精灵", "查看地图", "查看精灵", "购买", "精灵冒险",
    "使用精灵球", "使用物品", "洗练", "闪光觉醒", "精灵变异",
    "旅行精灵", "外出漫游", "精灵旅行", "召回旅行",
    "精灵远征", "派遣远征", "收获远征", "远征状态",
    "出战精灵", "携带精灵", "丢弃精灵",
    "我的精灵", "精灵商城", "精灵商店", "精灵背包", "精灵对战", "精灵排行", "羁绊",
    # V8 并入：原正则刮词域（与 handle 分支对应）
    "出战状态", "回收出战精灵", "我的背包", "挑战", "查看出战精灵",
    "精灵列表", "精灵地图", "进化", "领取精灵礼包",
    "进化路线", "精灵进化路线", "进化图鉴", "进化链", "进化树",
    "领养", "出战",
)

