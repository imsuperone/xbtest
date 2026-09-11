# -*- coding: utf-8 -*-
"""精灵系统(宝可梦式) - 对齐 open.xb 原版指令/文案/数据
数据源: games/data_spirit.py(从 open.xb.app.dll 字符串池保真提取)
机制: 领养初始精灵 -> 野外精灵冒险遭遇 -> 使用精灵球收服 -> 升级进化 -> 出战/携带 -> 排行
"""
import json
import random
import time

try:
    from ..core import storage as ST
except ImportError:
    try:
        from . import storage as ST
    except ImportError:
        from core import storage as ST

try:
    from . import data_spirit as SD
except ImportError:
    import data_spirit as SD

MENU = (
    "✨ 精灵系统\r\n"
    "━━━━━━━━━━━━━━\r\n"
    "🐣 领养精灵　　🎁 领取精灵礼包\r\n"
    "📋 我的精灵　　🔍 查看精灵 名称\r\n"
    "🛍️ 精灵商城　　🎒 我的背包\r\n"
    "🗺️ 精灵地图　　📍 查看地图 地点\r\n"
    "⚔️ 精灵冒险 地点　　🔮 使用精灵球 名称\r\n"
    "🎽 出战精灵 名称　🕊️ 回收出战精灵\r\n"
    "💠 携带精灵 名称　🗑️ 丢弃精灵 名称\r\n"
    "🧬 进化 名称　　⚔️ 精灵对战 @QQ　🏁 挑战 名称\r\n"
    "🏆 精灵排行\r\n"
    "━━━━━━━━━━━━━━\r\n"
    "💡 发送对应指令即可游玩"
)


_cfg, _cfgi = ST.cfg_scope("精灵配置")


# ---- 精灵图鉴(可在 WebUI 精灵图鉴编辑器修改, 存 精灵图鉴:spirits/maps/shop; 空=未自定义，回退 data_spirit.py 内置) ----
def _spirit_section(key, fallback):
    """图鉴三节唯一实现：dict 直返 / JSON 串解析 / 空回退内置（_SPIRITS/_MAPS/_SHOP 薄委托，零语义差）"""
    return ST.cfg_dict("精灵图鉴", key, fallback)


def _SPIRITS():
    return _spirit_section("spirits", SD.SPIRITS)


def _MAPS():
    return _spirit_section("maps", SD.MAPS)


def _SHOP():
    return _spirit_section("shop", SD.SHOP)


def _u(gid, qq):
    return ST.acct(gid, qq)


def _spirits(gid, qq):
    """返回精灵数据 dict"""
    a = _u(gid, qq)
    try:
        return json.loads(a.get("spirits", "{}") or "{}")
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
    return int(it.get("level", 1)) * (int(it.get("hp", 0)) + int(it.get("atk", 0))
                                      + int(it.get("def", 0)) + int(it.get("spa", 0))
                                      + int(it.get("spd", 0))) // 5


def _desc(it):
    return (f"{it.get('name','?')} Lv.{it.get('level',1)} 属性:{it.get('type') or '-'}\r\n"
            f"生命:{it.get('hp',0)} 攻击:{it.get('atk',0)} 防御:{it.get('def',0)}\r\n"
            f"特攻:{it.get('spa',0)} 特防:{it.get('spd',0)} 速度:{it.get('spe',0)} "
            f"战力:{_power(it)}\r\n经验:{it.get('exp',0)}/{_exp_need(it)}")


def _exp_need(it):
    # P0: 配置误设为0时 while exp>=0 恒真无限循环卡死，钳位>=1
    try:
        need = int(it.get("level", 1)) * int(_cfgi("升级经验", 300))
    except Exception:
        need = 300
    return need if need >= 1 else 1


def _mk_spr(name, level=1):
    """按图鉴生成一只精灵实例(含速度)"""
    base = _SPIRITS().get(name, {}) or {}
    return {"name": name, "level": int(level), "exp": 0,
            "type": base.get("type", ""),
            "hp": base.get("hp", 0), "atk": base.get("atk", 0), "def": base.get("def", 0),
            "spa": base.get("spa", 0), "spd": base.get("spd", 0), "spe": base.get("spe", 0)}


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


def _add_exp(gid, qq, sp, it, amount):
    """加经验, 处理升级与进化"""
    it["exp"] = int(it.get("exp", 0)) + int(amount)
    evolved = ""
    while it["exp"] >= _exp_need(it) and it["level"] < _cfgi("最大等级", 100):
        it["exp"] -= _exp_need(it)
        it["level"] = int(it.get("level", 1)) + 1
        base = _SPIRITS().get(it.get("name"), {})
        evo = base.get("evolve", "否")
        if evo and evo != "否" and it["level"] >= base.get("lv", 0):
            it["name"] = evo
            evo_base = _SPIRITS().get(evo, {})
            if evo_base:
                it["type"] = evo_base.get("type", it.get("type", ""))
                it["hp"] = evo_base.get("hp", it.get("hp", 0))
                it["atk"] = evo_base.get("atk", it.get("atk", 0))
                it["def"] = evo_base.get("def", it.get("def", 0))
                it["spa"] = evo_base.get("spa", it.get("spa", 0))
                it["spd"] = evo_base.get("spd", it.get("spd", 0))
                it["spe"] = evo_base.get("spe", it.get("spe", 0))
            evolved = f"   进化成 {evo}！\r\n"
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
    return (f"恭喜您获得精灵「{starter}」！\r\n" + _desc(new_it) +
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
    for k in ("精灵球", "大师球", "奇异甜食"):
        n = int(_cfg(k, 0) or 0)
        if n:
            bag[k] = int(bag.get(k, 0)) + n
    _save(gid, qq, sp)
    return ("恭喜您获得精灵礼包一份！\r\n精灵球+%s 大师球+%s 奇异甜食+%s"
            % (_cfg("精灵球", 0), _cfg("大师球", 0), _cfg("奇异甜食", 0)))


def cmd_my(gid, qq):
    sp = _spirits(gid, qq)
    # 兼容旧库：仅 list 判定，已有精灵但 adopted 缺失时自动补齐
    if not sp.get("list"):
        return "亲，您还没有精灵，请先领养精灵吧！"
    if not sp.get("adopted"):
        sp["adopted"] = 1
        _save(gid, qq, sp)
    lines = ["以下是您拥有的精灵："]
    for it in sp["list"]:
        mark = "【出战】" if it.get("name") == sp.get("active") else ""
        lines.append(f"{mark}{it.get('name','?')} Lv.{it.get('level',1)} 战力:{_power(it)}")
    lines.append("发送【查看精灵 名称】查看精灵状态")
    if sp.get("active"):
        lines.append(f"当前出战精灵：【{sp['active']}】")
    if sp.get("ride"):
        lines.append(f"携带欢迎精灵：【{sp['ride']}】")
    return "\r\n".join(lines)


def cmd_view(gid, qq, name):
    sp = _spirits(gid, qq)
    it = _wsp(sp, name)
    if not it:
        return "亲，您没有该精灵，请到野外冒险捕获吧！"
    _pp = ""
    try:
        _base = _SPIRITS().get(it.get("name"), {}) or {}
        _imgp = str(_base.get("img", "") or "").strip()
        if _imgp:
            _pp = _img_path(_imgp)
    except Exception:
        _pp = ""
    _txt = (f"您的精灵【{it.get('name','?')}】\r\n"
            f"属性：{it.get('type') or '-'}\r\n"
            f"等级：Lv.{it.get('level',1)}　经验：{it.get('exp',0)}/{_exp_need(it)}\r\n"
            f"生命：{it.get('hp',0)}　攻击：{it.get('atk',0)}　防御：{it.get('def',0)}\r\n"
            f"特攻：{it.get('spa',0)}　特防：{it.get('spd',0)}　速度：{it.get('spe',0)}\r\n"
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
                _cands.append(_os2.path.join(_os2.path.dirname(_os2.path.dirname(_os2.path.abspath(__file__))), p))
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


def cmd_shop():
    lines = ["欢迎来到精灵商城！", "━━━━━━━━━━━━━━"]
    for name, d in _SHOP().items():
        lines.append(f"{name}　价格:{d.get('price',0)}{ST.coin_name()}"
                     f"　效果:{d.get('attr','') or d.get('effect','')}")
    lines.append("发送【购买 物品名称】进行购买")
    return "\r\n".join(lines)


def cmd_buy(gid, qq, name):
    if name not in _SHOP():
        return "亲，商城中不存在该物品，发送【精灵商城】查看商城吧！"
    d = _SHOP()[name]
    price = int(d.get("price", 0) or 0)
    if price > 0 and ST.coins_get(gid, qq) < price:
        return f"笑~你没有那么多{ST.coin_name()}（需要{price}）"
    if price > 0:
        ST.coins_add(gid, qq, -price)
    sp = _spirits(gid, qq)
    bag = sp.setdefault("bag", {})
    bag[name] = int(bag.get(name, 0)) + 1
    _save(gid, qq, sp)
    return f"购买成功！获得「{name}」，已放入背包。"


def _map_indexed():
    """返回 [(idx, name, data)] 序号从1开始，按 _MAPS() 插入顺序"""
    return list(enumerate(_MAPS().items(), 1))

def _resolve_map(place):
    """place 可为 地点名 或 序号(1-based)，返回真实地点名或 None"""
    if not place:
        return None
    place = str(place).strip()
    maps = _MAPS()
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
    lines = ["🎒 我的背包　您的背包信息如下："]
    for name, cnt in bag.items():
        lines.append(f"{name} ×{cnt}")
    lines.append("使用精灵球格式为：【使用精灵球 精灵球名称】")
    lines.append("使用物品格式为：【使用物品 物品名称*数量】")
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
    gap = _cfgi("冒险间隔", 2) * 60
    if last and time.time() - float(last) < gap:
        left = int((gap - (time.time() - float(last))) / 60) + 1
        return f"{left}分钟再来冒险吧！"
    _recall_set(key, str(time.time()))
    # 随机遭遇
    wild = random.choice(md.get("drops", []) or ["绿毛虫"])
    lb = _cfgi("等级加成下限", 3); ub = _cfgi("等级加成上限", 5)
    wl = int(md.get("lv", 1)) + random.randint(lb, ub)
    sp["wild"] = {"name": wild, "level": wl}
    # 冒险历练奖励(挑战奖励配置): 经验 + 金币
    exp_lo = _cfgi("挑战奖励_经验下限", 200); exp_hi = _cfgi("挑战奖励_经验上限", 300)
    gold_hi = _cfgi("挑战奖励_金钱上限", 250)
    exp = random.randint(max(1, exp_lo), max(exp_lo, exp_hi))
    gold = random.randint(0, max(0, gold_hi))
    if act_it.get("level") < _cfgi("最大等级", 100):
        _add_exp(gid, qq, sp, act_it, exp)
    if gold > 0:
        ST.coins_add(gid, qq, gold)
    # H: 挑战扣除（fallback全0，没配行为不变；有配则扣钱扣体力并在文案明示）
    d_lo = _cfgi("挑战扣除_金钱下限", 0)
    d_hi = _cfgi("挑战扣除_金钱上限", 0)
    d_tili = _cfgi("挑战扣除_消耗体力", 0)
    d_gold = 0
    d_stam = 0
    if d_hi > 0 or d_lo > 0:
        _dlo, _dhi = (d_lo, d_hi) if d_lo <= d_hi else (d_hi, d_lo)
        _dlo = max(0, _dlo)
        _dhi = max(0, _dhi)
        if _dhi > 0:
            d_gold = random.randint(_dlo, _dhi)
            if d_gold > 0:
                _real = min(d_gold, ST.coins_get(gid, qq))
                if _real > 0:
                    ST.coins_add(gid, qq, -_real)
                d_gold = _real
    if d_tili > 0:
        try:
            _cur_st = ST.acct(gid, qq).int("stamina")
        except Exception:
            _cur_st = int(d_tili)
        d_stam = min(int(d_tili), max(0, _cur_st))
        if d_stam > 0:
            ST.acct_add(gid, qq, "stamina", -d_stam)
    _save(gid, qq, sp)
    _deduct_msg = ""
    if d_gold or d_stam:
        _parts = []
        if d_gold:
            _parts.append(f"{ST.coin_name()}-{d_gold}")
        if d_stam:
            _parts.append(f"体力-{d_stam}")
        _deduct_msg = "挑战扣除：" + " ".join(_parts) + "\r\n"
    return (f"【精灵冒险】来到{place}，遭遇了野生的 Lv.{wl}「{wild}」！\r\n"
            f"历练奖励：经验+{exp} {ST.coin_name()}+{gold}\r\n"
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
    bag[ball] = int(bag.get(ball, 0)) - 1
    if int(bag.get(ball, 0)) <= 0:
        del bag[ball]
    # 抓取概率 = 球效果 / 100 + 等级修正
    eff = int(_SHOP()[ball].get("effect", 0) or 0)
    lv = int(wild.get("level", 1))
    p = max(5, min(95, eff - (lv - 10) // 2)) if eff < 90 else 100
    sp.pop("wild", None)
    if random.randint(1, 100) <= p:
        if len(sp.get("list", [])) >= _cfgi("精灵数量", 8):
            _save(gid, qq, sp)
            return "亲，您的精灵数量已达上限，无法收服，可丢弃后再来！"
        sp.setdefault("list", []).append(_mk_spr(wild["name"], lv))
        _save(gid, qq, sp)
        return f"恭喜！成功收服 Lv.{lv}「{wild['name']}」！"
    _save(gid, qq, sp)
    return "很遗憾，野生精灵挣脱了，飞走了……"


def cmd_set_active(gid, qq, name):
    sp = _spirits(gid, qq)
    if not _wsp(sp, name):
        return "亲，您没有该精灵，无法出战！"
    sp["active"] = name
    _save(gid, qq, sp)
    return f"已将【{name}】设为出战精灵！"


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
    if sp.get("active") == name:
        sp["active"] = ""
    if sp.get("ride") == name:
        sp["ride"] = ""
    # P0: 同名多只时仅删首只，误删全部是资损
    _lst = list(sp.get("list", []))
    for _i, _x in enumerate(_lst):
        if _x.get("name") == name:
            del _lst[_i]
            break
    sp["list"] = _lst
    red = _cfgi("魅力减少", 10)
    ST.acct_add(gid, qq, "charm", -red)
    _save(gid, qq, sp)
    return f"已丢弃精灵【{name}】，魅力 -{red}"


def cmd_evolve(gid, qq, name):
    sp = _spirits(gid, qq)
    it = _wsp(sp, name)
    if not it:
        return "亲，您没有该精灵，无法进化！"
    base = _SPIRITS().get(name, {})
    evo = base.get("evolve", "否")
    if not evo or evo == "否":
        return "亲，该精灵无法再次进化！"
    if int(it.get("level", 1)) < base.get("lv", 0):
        return f"亲，需要达到 Lv.{base.get('lv',0)} 才能进化，当前 Lv.{it.get('level',1)}！"
    bag = sp.setdefault("bag", {})
    if int(bag.get("进化液", 0)) <= 0:
        return "亲，需要【进化液】才能进化，请到商城购买！"
    bag["进化液"] = int(bag.get("进化液", 0)) - 1
    if int(bag.get("进化液", 0)) <= 0:
        del bag["进化液"]
    it["name"] = evo
    evo_base = _SPIRITS().get(evo, {})
    if evo_base:
        it["type"] = evo_base.get("type", it.get("type", ""))
        it["hp"] = evo_base.get("hp", it.get("hp", 0))
        it["atk"] = evo_base.get("atk", it.get("atk", 0))
        it["def"] = evo_base.get("def", it.get("def", 0))
        it["spa"] = evo_base.get("spa", it.get("spa", 0))
        it["spd"] = evo_base.get("spd", it.get("spd", 0))
        it["spe"] = evo_base.get("spe", it.get("spe", 0))
    _save(gid, qq, sp)
    return f"恭喜！「{name}」进化成「{evo}」！"


# ---- 精灵PVP(总战力对打) ----
def cmd_pvp(gid, qq, target):
    target = (target or "").strip()
    if target:
        t_at, _ = ST.parse_at(target)
        if t_at:
            target = t_at
        else:
            import re as _re_pvp
            m_qq = _re_pvp.search(r"(\d{5,12})", target)
            if m_qq:
                target = m_qq.group(1)
    if not target or target == str(qq):
        return "亲，请输入对方QQ：精灵对战 对方QQ"
    sp = _spirits(gid, qq)
    mine = _wsp(sp, sp.get("active")) if sp.get("active") else None
    tsp = _spirits(gid, target)
    theirs = _wsp(tsp, tsp.get("active")) if tsp.get("active") else None
    if mine is None:
        return "亲，您还没有出战的精灵，无法对战！"
    if theirs is None:
        return "对方没有出战的精灵，无法对战！"
    myp, tap = _power(mine), _power(theirs)
    stake = min(2000, ST.coins_get(gid, qq) // 10, ST.coins_get(gid, target) // 10)
    if stake <= 0:
        stake = 200
    pwin = myp / (myp + tap) if (myp + tap) else 0.5
    win = random.random() < pwin
    if win:
        # 零和: 从对手实扣(对手余额不足时按其真实扣除额为准), 等额给赢家
        before = ST.coins_get(gid, target)
        ST.coins_add(gid, target, -stake)
        after = ST.coins_get(gid, target)
        real = before - after
        ST.coins_add(gid, qq, real)
        return (f"⚔️ 精灵对战\r\n你(战力{myp}) vs {target}(战力{tap})\r\n"
                f"【你赢！】获得 {real}{ST.coin_name()}！")
    before = ST.coins_get(gid, qq)
    ST.coins_add(gid, qq, -stake)
    after = ST.coins_get(gid, qq)
    real = before - after
    ST.coins_add(gid, target, real)
    return (f"⚔️ 精灵对战\r\n你(战力{myp}) vs {target}(战力{tap})\r\n"
            f"【你输…】损失 {real}{ST.coin_name()}！")


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
            lst.append((bestv, str(qq), best.get("name", "?")))
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
        from . import slave as S
        if gid:
            try:
                nm = S.get_note_name(gid, q) or S.fetch_card(gid, q)
                if nm:
                    return nm
            except Exception:
                pass
        return q
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
    text = (raw or "").strip()
    if not text:
        return None
    m = text
    if not m:
        return None
    _wake = ST.wake("精灵系统", "精灵系统")
    # 开关
    if _need_switch() and m not in _wake:
        return "【精灵系统】已经被关闭了，无法使用该功能！\r\n如需开启，请机器人管理发送【精灵开关】进行开启！"
    # 指令分发
    if m in _wake:
        return MENU
    if m.startswith("领养精灵"):
        return cmd_adopt(gid, qq, m[4:].strip())
    if m == "领取精灵礼包":
        return cmd_gift(gid, qq)
    if m in ("我的精灵", "精灵列表"):
        return cmd_my(gid, qq)
    if m == "精灵商城":
        return cmd_shop()
    if m == "我的背包":
        return cmd_backpack(gid, qq)
    if m == "精灵地图":
        return cmd_map()
    if m.startswith("查看地图"):
        return cmd_map_detail(gid, qq, m[4:].strip())
    if m in ("查看出战精灵", "出战状态"):
        return cmd_active(gid, qq)
    if m == "回收出战精灵":
        return cmd_cancel_active(gid, qq)
    # 带参数
    if m.startswith("查看精灵"):
        return cmd_view(gid, qq, m[4:].strip())
    if m.startswith("购买"):
        # 坐骑系统的 购买坐骑 由坐骑引擎接管, 此处放行
        if m.startswith("购买坐骑"):
            return None
        return cmd_buy(gid, qq, m[2:].strip())
    if m.startswith("精灵冒险"):
        return cmd_adventure(gid, qq, m[4:].strip())
    if m.startswith("使用精灵球"):
        return cmd_catch(gid, qq, m[5:].strip())
    if m.startswith("出战精灵"):
        return cmd_set_active(gid, qq, m[4:].strip())
    if m.startswith("携带精灵"):
        return cmd_ride(gid, qq, m[4:].strip())
    if m.startswith("丢弃精灵"):
        return cmd_discard(gid, qq, m[4:].strip())
    if m.startswith("进化"):
        return cmd_evolve(gid, qq, m[2:].strip())
    if m.startswith("精灵对战"):
        return cmd_pvp(gid, qq, m[4:].strip())
    if m.startswith("挑战"):
        return cmd_pvp(gid, qq, m[2:].strip())
    if m.startswith("羁绊"):
        return "羁绊系统：与你的精灵共同冒险提升亲密度（待实装）。"
    if m.startswith("精灵排行"):
        return cmd_rank(gid, m[4:].strip())
    return None


