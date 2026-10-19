# -*- coding: utf-8 -*-
"""games/slave/combat.py — 奴隶包·combat（原 slave.py 切分，语义不变）。"""
import time as _time
import random as _random
try:
    from ...core import storage as ST
    store = ST
except ImportError:
    from core import storage as ST
    store = ST
from . import slave_state as _S
try:
    from ..config.slave import (FIGHT_REFUSE_POWER, FIGHT_STAKE_PCT, FIGHT_STAKE_CAP,
                                FIGHT_POOR_LIMIT, FIGHT_CRIT_PER_STAR, FIGHT_CRIT_MULT,
                                SHIELD_TREASURE, TREASURE_GOURD_KEY, TREASURE_CHARM_KEYS,
                                WORTH_PCT_CAP)
except ImportError:
    from games.config.slave import (FIGHT_REFUSE_POWER, FIGHT_STAKE_PCT, FIGHT_STAKE_CAP,  # type: ignore
                                    FIGHT_POOR_LIMIT, FIGHT_CRIT_PER_STAR, FIGHT_CRIT_MULT,
                                    SHIELD_TREASURE, TREASURE_GOURD_KEY, TREASURE_CHARM_KEYS,
                                    WORTH_PCT_CAP)
from .base import U, _fmt, _safe_int, cd_check, cd_commit, cfg, cfgf, cfgi, cn_fmt, cn_parse, protected_until, slaves_of, star_of, total_assets, transfer_cash_or_deposit, treasures_of, uget, user_slave_slots, uset, weapons_of
try:
    from ..config.shop import TREASURES as _TREASURES_BUILTIN
except ImportError:
    try:
        from games.config.shop import TREASURES as _TREASURES_BUILTIN  # type: ignore
    except Exception:
        _TREASURES_BUILTIN = {}
from .nick import uname


def _treasure_names():
    """宝物名单：读 设置.宝物（WebUI/图鉴写入口径），兼容旧 设置.treasure，二者合并去重；
    再并入图鉴结构表（商城图鉴.treasures/老 treasure_effects/内置表）中有名但名单漏配的，
    保证图鉴入库即进入获取池与展示（名单>图鉴>内置优先级）；
    全空时回退内置 TREASURES 键，保证宝物可获取/可展示（与 RIDE_SHOP 内置回退同构）"""
    out = []
    try:
        for key in ("宝物", "treasure"):
            for t in (cfg("设置", key, "") or "").split("|"):
                t = str(t or "").strip()
                if t and t not in out:
                    out.append(t)
    except Exception:
        pass
    # 图鉴入库即并入：只进结构表、名单漏配的宝物同样可获取（防名单/结构 desync 导致绝版）
    try:
        _items = _treasure_items() or {}
        for t in _items.keys():
            t = str(t or "").strip()
            if t and t not in out:
                out.append(t)
    except Exception:
        pass
    if not out:
        try:
            for t in (_TREASURES_BUILTIN or {}).keys():
                t = str(t or "").strip()
                if t and t not in out:
                    out.append(t)
        except Exception:
            pass
    return out




def _treasure_effects_raw():
    """宝物自定义效果表（商城图鉴 treasure_effects {名: 效果}）；空=未自定义"""
    return store.cfg_dict("商城图鉴", "treasure_effects")


def _treasure_items():
    """宝物结构表：商城图鉴.treasures（新家 {名: {type, value, desc}}）合并老 treasure_effects，新优先。
    老串/老{effect}统一成 {desc} 形；内置酒神/四象无条目时靠回退名单生效（见 _has_treasure_type）。"""
    out = {}
    try:
        raw = store.cfg_dict("商城图鉴", "treasures") or {}
        if isinstance(raw, dict):
            for k, v in raw.items():
                if isinstance(v, dict):
                    out[str(k)] = v
                elif v is not None and str(v).strip() != "":
                    out[str(k)] = {"desc": str(v)}
    except Exception:
        pass
    try:
        old = _treasure_effects_raw() or {}
        if isinstance(old, dict):
            for k, v in old.items():
                if str(k) not in out:
                    if isinstance(v, dict):
                        out[str(k)] = v
                    elif v is not None and str(v).strip() != "":
                        out[str(k)] = {"desc": str(v)}
    except Exception:
        pass
    # 内置回退：sidecar 为空时类型/数值/描述取 TREASURES 内置表（自定义侧按名覆盖）
    try:
        for k, v in (_TREASURES_BUILTIN or {}).items():
            if str(k) not in out and isinstance(v, dict):
                out[str(k)] = v
    except Exception:
        pass
    return out


def _treasure_desc(tname):
    try:
        v = _treasure_items().get(str(tname or ""), None)
        if isinstance(v, dict):
            return str(v.get("desc", "") or "").strip()
        return str(v or "").strip()
    except Exception:
        return ""


def _treasure_effect_list(tname):
    """单个宝物的实效列表 [(type, value)]：新 effects 数组优先，老单 type+value 回退。

    sidecar 形态（商城图鉴.treasures）：{名: {desc, type, value, effects:[{type,value}]}}；
    老串/老{effect}只有文案无实效。纯收藏返回 []。value 恒为非负数。"""
    try:
        v = (_treasure_items() or {}).get(str(tname or ""))
        if isinstance(v, dict):
            effs = v.get("effects")
            if isinstance(effs, list) and effs:
                out = []
                for e in effs:
                    if not isinstance(e, dict):
                        continue
                    t = str(e.get("type", "") or "")
                    try:
                        val = int(float(e.get("value", 0) or 0))
                    except Exception:
                        val = 0
                    if t and val >= 0:
                        out.append((t, max(0, val)))
                    elif t:
                        out.append((t, 0))
                if out:
                    return out
            t = str(v.get("type", "") or "")
            if t:
                try:
                    val = int(float(v.get("value", 0) or 0))
                except Exception:
                    val = 0
                return [(t, max(0, val))]
    except Exception:
        pass
    return []


def _has_treasure_type(owned, ttype, fallbacks=()):
    """持有清单里是否有某型宝物；fallbacks 为内置名单（未自定义时保底生效）"""
    try:
        for t in (owned or []):
            t = str(t)
            if t in (fallbacks or ()):
                return True
            try:
                if any(tt == str(ttype or "") for tt, _vv in _treasure_effect_list(t)):
                    return True
            except Exception:
                continue
    except Exception:
        pass
    return False


def _treasure_stage_mult(stage):
    """阶数增幅倍率：0阶=1.0, 1阶=1.35, 2阶=1.75, 3阶=2.25, 4阶=2.85, 5阶=3.60"""
    try:
        stg = max(0, min(5, int(stage or 0)))
        return (1.0, 1.35, 1.75, 2.25, 2.85, 3.60)[stg]
    except Exception:
        return 1.0


def _treasure_trigger_prob(u, ttype, default_base=25, fallbacks=()):
    """计算某功能宝物在当前玩家身上的实际触发概率（百分比 0..98）。
    默认初始概率下压（0阶约 25%），随着升阶（★1~★5）逐步大幅提升触发率：
    ★0阶: base (25%)
    ★1阶: base + 15 (40%)
    ★2阶: base + 30 (55%)
    ★3阶: base + 45 (70%)
    ★4阶: base + 60 (85%)
    ★5阶: 98% (极道至尊)
    """
    if u is None:
        return 0
    owned = treasures_of(u)
    if not owned:
        return 0

    best_prob = 0
    for t in owned:
        t_str = str(t)
        matched = False
        val = 0
        if t_str in (fallbacks or ()):
            matched = True
        for tt, vv in _treasure_effect_list(t_str):
            if tt == str(ttype or ""):
                matched = True
                try:
                    val = max(val, int(vv or 0))
                except Exception:
                    pass
        if not matched:
            continue

        base_p = val if val > 0 else default_base
        stage = 0
        try:
            stage = _safe_int(uget(u, t_str + "升阶", "0"), 0)
        except Exception:
            stage = 0
        stage = max(0, min(5, stage))

        stage_cfg_p = cfgi("设置", f"{t_str}_{stage}阶触发率", -1)
        if stage_cfg_p < 0:
            _CH = {0: "零", 1: "一", 2: "二", 3: "三", 4: "四", 5: "五"}
            stage_cfg_p = cfgi("设置", f"{t_str}_{_CH.get(stage, '')}阶触发率", -1)
        if stage_cfg_p >= 0:
            prob = stage_cfg_p
        else:
            base_override = cfgi("设置", f"{t_str}_0阶触发率", -1)
            if base_override < 0:
                base_override = cfgi("设置", f"{t_str}_零阶触发率", -1)
            if base_override < 0:
                base_override = cfgi("设置", f"{t_str}_基础触发率", -1)
            if base_override >= 0:
                base_p = base_override
            if stage == 0:
                prob = base_p
            elif stage == 1:
                prob = base_p + 15
            elif stage == 2:
                prob = base_p + 30
            elif stage == 3:
                prob = base_p + 45
            elif stage == 4:
                prob = base_p + 60
            else:
                prob = 98

        prob = max(1, min(98, prob))
        if prob > best_prob:
            best_prob = prob

    return best_prob


def _treasure_pct_total(owned, ttype, cap=100, u=None):
    """持有宝物某百分比型加成之和（支持按星阶倍率放大，钳位 0..cap；多效果宝物按行累加）"""
    s = 0
    try:
        for t in (owned or []):
            stg = 0
            if u is not None:
                try:
                    stg = _safe_int(uget(u, str(t) + "升阶", "0"), 0)
                except Exception:
                    stg = 0
            mult = _treasure_stage_mult(stg)
            for tt, vv in _treasure_effect_list(str(t)):
                if tt == str(ttype or ""):
                    try:
                        base_v = max(0, int(vv or 0))
                        s += int(round(base_v * mult))
                    except Exception:
                        pass
    except Exception:
        pass
    try:
        cap = max(0, int(cap))
    except Exception:
        cap = 100
    return max(0, min(s, cap))


def _treasure_atk_total(owned, u=None):
    """持有宝物攻击加成之和（战斗力外挂项，支持按星阶倍率放大，不钳位；多效果宝物按行累加）"""
    s = 0
    try:
        for t in (owned or []):
            stg = 0
            if u is not None:
                try:
                    stg = _safe_int(uget(u, str(t) + "升阶", "0"), 0)
                except Exception:
                    stg = 0
            mult = _treasure_stage_mult(stg)
            for tt, vv in _treasure_effect_list(str(t)):
                if tt == "atk":
                    try:
                        base_v = max(0, int(vv or 0))
                        s += int(round(base_v * mult))
                    except Exception:
                        pass
    except Exception:
        pass
    return s




def _treasure_effect(tname):
    """宝物效果文案统一口径：结构表 desc > 老自定义效果 > 酒神/四象专属 > 通用收藏（获取/升阶/详情三处共用）"""
    try:
        t = str(tname or "")
        _d = _treasure_desc(t)
        if _d:
            return _d
        try:
            _custom = _treasure_effects_raw().get(t, "")
            if isinstance(_custom, dict):
                _custom = str(_custom.get("effect", "") or "")
            _custom = str(_custom or "").strip()
            if _custom:
                return _custom
        except Exception:
            pass
        if TREASURE_GOURD_KEY in t:
            return _S.T.GOURD_EFFECT
        if any(k in t for k in TREASURE_CHARM_KEYS):
            return _S.T.CHARM_EFFECT
        # 通用收藏兜底（text_slave.T_COMMON_EFFECT 经 _tmap 去前缀后为 COMMON_EFFECT，
        # 旧 TREASURE_EFFECT_GENERIC/T_COMMON_EFFECT 属性名不存在，走不到这里即空白）
        try:
            _g = getattr(_S.T, "COMMON_EFFECT", "")
            if _g:
                return _g
        except Exception:
            pass
        return ""
    except Exception:
        return ""




def _weapon_attrs_raw():
    """武器可配属性表（商城图鉴 weapon_attrs {名: {atk, desc}}）；空=未自定义"""
    return store.cfg_dict("商城图鉴", "weapon_attrs")




def _weapon_attr(name, field, default=0):
    try:
        v = (_weapon_attrs_raw().get(str(name)) or {})
        if not isinstance(v, dict):
            return default
        # 兼容旧 weapon_shop 残留的 atk/desc（商城已删，仅读）
        if field not in v or v.get(field) in ("", None):
            try:
                old = (_weapon_shop().get(str(name)) or {})
                if isinstance(old, dict) and old.get(field) not in ("", None):
                    return old.get(field)
            except Exception:
                pass
            # 回退内置默认属性库
            try:
                from ..config.shop import DEFAULT_WEAPON_ATTRS
                def_w = DEFAULT_WEAPON_ATTRS.get(str(name)) or {}
                if isinstance(def_w, dict) and def_w.get(field) not in ("", None):
                    return def_w.get(field)
            except Exception:
                pass
            return default
        return v.get(field)
    except Exception:
        return default




def _weapon_atk_bonus(name):
    try:
        return max(0, int(float(_weapon_attr(name, "atk", 0) or 0)))
    except Exception:
        return 0




def _weapon_desc(name):
    try:
        return str(_weapon_attr(name, "desc", "") or "").strip()
    except Exception:
        return ""




def atk_of(st, qq):
    """武器攻击力: 星级成长表 + 单武器可配加成"""
    u = U(st, qq)
    table = _S.STAR_ATK
    total = 0
    for w in weapons_of(u):
        s = min(star_of(u, w), 5)
        total += table[s] + _weapon_atk_bonus(w)
    return total




def battle_power(st, qq):
    """战斗力 = 主人身价*(1+身价加成) + 武器攻击力 + 宝物攻击加成 + 坐骑加成"""
    u = U(st, qq)
    p = int(uget(u, "price") or 0)
    for s in slaves_of(st, qq):
        p += int(uget(U(st, s), "price") or 0)
    try:
        _wb = _treasure_pct_total(treasures_of(u), "worth", WORTH_PCT_CAP, u=u)
    except Exception:
        _wb = 0
    base_bp = p + p * _wb // 100 + atk_of(st, qq) + _treasure_atk_total(treasures_of(u), u=u)
    try:
        gid = getattr(st, "_gid", "")
        if gid:
            try:
                from ..ride import active_ride_info
            except ImportError:
                from games.ride import active_ride_info  # type: ignore
            _, r_pct = active_ride_info(gid, qq, aspect="atk")
            if r_pct > 0:
                base_bp += base_bp * r_pct // 100
    except Exception:
        pass
    return base_bp




def cmd_fight(gid, qq, target, st):
    if not target:
        return _S.T.FIGHT_WHO
    tid = str(target)
    if tid == str(qq):
        return _S.T.SELF_FIGHT if hasattr(_S.T, "SELF_FIGHT") else "\u4e0d\u80fd\u548c\u81ea\u5df1\u6253\u67b6\u54e6\uff5e"
    a_slaves = slaves_of(st, qq)
    d_slaves = slaves_of(st, tid)

    if tid == uget(U(st, qq), "owner"):
        return _S.T.FIGHT_MASTER
    if tid in a_slaves:
        return _S.T.FIGHT_OWN_SLAVE
    if not a_slaves:
        return _S.T.FIGHT_NO_SLAVE
    if not d_slaves:
        return _S.T.FIGHT_ENEMY_NO_S
    rest = cn_parse(uget(U(st, tid), "战斗恢复时间"))
    iv_rest = cfgi("间隔配置", "打架间隔", 1)
    if rest and _time.time() - rest < iv_rest * 60:
        left = int((iv_rest * 60 - (_time.time() - rest)) / 60) + 1
        return _S.T.FIGHT_RESTING.format(min=left)

    my_p = battle_power(st, qq)
    ta_p = battle_power(st, tid)
    if my_p >= ta_p * FIGHT_REFUSE_POWER:
        return _S.T.FIGHT_TOO_STRONG

    ca, cdd = total_assets(gid, qq), total_assets(gid, tid)
    stake_cap = max(100, cfgi("费用配置", "打架掠夺上限", FIGHT_STAKE_CAP))
    stake = min(int(ca * FIGHT_STAKE_PCT), int(cdd * FIGHT_STAKE_PCT), stake_cap)
    if stake <= 0:
        if ca < FIGHT_POOR_LIMIT:
            return _S.T.FIGHT_I_AM_POOR.replace("@", "")
        return _S.T.FIGHT_TA_IS_POOR

    ok, mins = cd_check(U(st, qq), "打架时间", "打架间隔")
    if not ok:
        return _fmt(mins, "打架")
    cd_commit(U(st, qq), "打架时间")
    now_fmt = cn_fmt(_time.time())
    uset(U(st, qq), "战斗恢复时间", now_fmt)
    uset(U(st, tid), "战斗恢复时间", now_fmt)

    # 5星武器狂热: 每把5星+N%概率战力翻倍
    crit = False
    five = sum(1 for w in weapons_of(U(st, qq)) if star_of(U(st, qq), w) >= 5)
    _crit_p = five * FIGHT_CRIT_PER_STAR
    try:
        from ..sign import eff_prob as _LP
        _crit_p = _LP(_crit_p, gid, qq)
    except Exception:
        pass
    if five and _random.randint(1, 100) <= _crit_p:
        crit = True
        my_p *= FIGHT_CRIT_MULT

    lines = [_S.T.FIGHT_HEAD,
             _S.T.FIGHT_CALL_UP.format(who="[" + (U(st, tid).get("name") or str(tid)) + "]"),
             _S.T.FIGHT_MY_TEAM.format(team=", ".join(uname(st, s) for s in a_slaves))]
    if crit:
        lines.append(_S.T.FIGHT_CRIT)
    lines.append(_S.T.FIGHT_ENEMY_TEAM.format(team=", ".join(uname(st, s) for s in d_slaves)))
    pwin = my_p / (my_p + ta_p) if (my_p + ta_p) > 0 else 0.5
    try:
        from ..sign import eff_p01 as _LP01
        pwin = _LP01(pwin, gid, qq)
    except Exception:
        pass
    lines.append(_S.T.FIGHT_WINRATE.format(pct=int(pwin * 100)))
    win = _random.random() < pwin

    def _shield(owner_q):
        prob = _treasure_trigger_prob(U(st, owner_q), "shield", default_base=25, fallbacks=(SHIELD_TREASURE,))
        if prob <= 0:
            return False, 0
        return (_random.randint(1, 100) <= prob), prob

    now_ts = _time.time()
    if win:
        lines.append(_S.T.FIGHT_WIN)
        free_slot = len(slaves_of(st, qq)) < user_slave_slots(U(st, qq))
        stealable = [s for s in d_slaves if now_ts >= protected_until(U(st, s))]
        if stealable and free_slot:
            shield_on, shield_prob = _shield(tid)
            if shield_on:
                victim = _random.choice(stealable)
                lines.append(_S.T.FIGHT_TA_TREASURE)
                lines.append(f"[{uname(st, victim)}]{_S.T.FIGHT_TA_SHIELD}（【四象护符】{shield_prob}%概率触发圣盾）")
            else:
                victim = _random.choice(stealable)
                uset(U(st, victim), "owner", qq)
                uset(U(st, victim), "purchase_price", str(int(uget(U(st, victim), "price") or 0)))
                uset(U(st, victim), "purchase_time", cn_fmt(now_ts))
                uset(U(st, victim), "protect_until", "")
                uset(U(st, victim), "protector", "")
                uset(U(st, victim), "_work_wage", "")
                newp = min(_S.MAX_PRICE, int(int(uget(U(st, victim), "price") or 0) * cfgf("费用配置", "买入身价上涨", _S.PRICE_UP)))
                uset(U(st, victim), "price", str(newp))
                lines.append(_S.T.FIGHT_GET_SLAVE.format(slave="[" + uname(st, victim) + "]"))
        else:
            ransom = transfer_cash_or_deposit(gid, tid, qq, stake)
            if ransom is None:
                return "\r\n".join(lines) + "\r\n赎金结算繁忙，请稍后重试。"
            ransom = max(0, int(ransom or 0))
            lines.append(_S.T.FIGHT_SLOT_FULL.format(money=ransom))
    else:
        lines.append(_S.T.FIGHT_LOSE)
        shield_on, shield_prob = _shield(qq)
        stealable = [s for s in a_slaves if now_ts >= protected_until(U(st, s))]
        free_t = len(slaves_of(st, tid)) < user_slave_slots(U(st, tid))
        if stealable and not shield_on and free_t:
            victim = _random.choice(stealable)
            uset(U(st, victim), "owner", tid)
            uset(U(st, victim), "purchase_price", str(int(uget(U(st, victim), "price") or 0)))
            uset(U(st, victim), "purchase_time", cn_fmt(now_ts))
            uset(U(st, victim), "protect_until", "")
            uset(U(st, victim), "protector", "")
            uset(U(st, victim), "_work_wage", "")
            newp = min(_S.MAX_PRICE, int(int(uget(U(st, victim), "price") or 0) * cfgf("费用配置", "买入身价上涨", _S.PRICE_UP)))
            uset(U(st, victim), "price", str(newp))
            lines.append(_S.T.FIGHT_LOSE_SLAVE.format(slave="[" + uname(st, victim) + "]"))
        elif shield_on and stealable:
            victim = _random.choice(stealable)
            lines.append(_S.T.FIGHT_MY_TREASURE)
            lines.append(f"[{uname(st, victim)}]{_S.T.FIGHT_MY_SHIELD}（【四象护符】{shield_prob}%概率触发圣盾）")
        else:
            ransom = transfer_cash_or_deposit(gid, qq, tid, stake)
            if ransom is None:
                return "\r\n".join(lines) + "\r\n赎金结算繁忙，请稍后重试。"
            ransom = max(0, int(ransom or 0))
            lines.append(_S.T.FIGHT_PAY_MONEY.format(money=ransom))
    return "\r\n".join(lines)




def _weapon_shop_raw():
    """返回原始 weapon_shop 配置对象(可能含 {price,atk,desc,img})，供取图/数值用；空=未自定义"""
    return store.cfg_dict("商城图鉴", "weapon_shop")



# 旧商城只读兼容别名（v0.7.16起改抽奖池直管；与 _weapon_shop_raw 同一对象，零语义差）
_weapon_shop = _weapon_shop_raw




__all__ = ["atk_of", "battle_power", "cmd_fight"]
