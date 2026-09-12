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
                                SHIELD_TREASURE, TREASURE_GOURD_KEY, TREASURE_CHARM_KEYS)
except ImportError:
    from games.config.slave import (FIGHT_REFUSE_POWER, FIGHT_STAKE_PCT, FIGHT_STAKE_CAP,  # type: ignore
                                    FIGHT_POOR_LIMIT, FIGHT_CRIT_PER_STAR, FIGHT_CRIT_MULT,
                                    SHIELD_TREASURE, TREASURE_GOURD_KEY, TREASURE_CHARM_KEYS)
from .base import U, _fmt, _safe_int, cd_check, cd_commit, cfg, cfgf, cfgi, cn_fmt, cn_parse, coins_add, coins_get, slaves_of, star_of, treasures_of, uget, uset, weapons_of
from .nick import uname


def _treasure_names():
    """宝物名单：读 设置.宝物（WebUI/图鉴写入口径），兼容旧 设置.treasure，二者合并去重"""
    out = []
    try:
        for key in ("宝物", "treasure"):
            for t in (cfg("设置", key, "") or "").split("|"):
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
    return out


def _treasure_desc(tname):
    try:
        v = _treasure_items().get(str(tname or ""), None)
        if isinstance(v, dict):
            return str(v.get("desc", "") or "").strip()
        return str(v or "").strip()
    except Exception:
        return ""


def _has_treasure_type(owned, ttype, fallbacks=()):
    """持有清单里是否有某型宝物；fallbacks 为内置名单（未自定义时保底生效）"""
    try:
        items = _treasure_items()
        for t in (owned or []):
            t = str(t)
            if t in (fallbacks or ()):
                return True
            v = items.get(t)
            if isinstance(v, dict) and str(v.get("type", "") or "") == str(ttype or ""):
                return True
    except Exception:
        pass
    return False


def _treasure_atk_total(owned):
    """持有宝物攻击加成之和（战斗力外挂项）"""
    s = 0
    try:
        items = _treasure_items()
        for t in (owned or []):
            v = items.get(str(t))
            if isinstance(v, dict) and str(v.get("type", "") or "") == "atk":
                try:
                    s += max(0, int(float(v.get("value", 0) or 0)))
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
        if hasattr(_S.T, "TREASURE_EFFECT_GENERIC") and _S.T.TREASURE_EFFECT_GENERIC:
            return _S.T.TREASURE_EFFECT_GENERIC
        return _S.T.T_COMMON_EFFECT if hasattr(_S.T, "T_COMMON_EFFECT") else ""
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
    """战斗力 = 主人奴隶身价之和 + 武器攻击力 + 宝物攻击加成"""
    u = U(st, qq)
    p = int(uget(u, "price") or 0)
    for s in slaves_of(st, qq):
        p += int(uget(U(st, s), "price") or 0)
    return p + atk_of(st, qq) + _treasure_atk_total(treasures_of(u))




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

    ca, cdd = coins_get(gid, qq), coins_get(gid, tid)
    stake = min(int(ca * FIGHT_STAKE_PCT), int(cdd * FIGHT_STAKE_PCT), FIGHT_STAKE_CAP)
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
    if five and _random.randint(1, 100) <= five * FIGHT_CRIT_PER_STAR:
        crit = True
        my_p *= FIGHT_CRIT_MULT

    lines = [_S.T.FIGHT_HEAD,
             _S.T.FIGHT_CALL_UP.format(who="[" + (U(st, tid).get("name") or str(tid)) + "]"),
             _S.T.FIGHT_MY_TEAM.format(team=", ".join(uname(st, s) for s in a_slaves))]
    if crit:
        lines.append(_S.T.FIGHT_CRIT)
    lines.append(_S.T.FIGHT_ENEMY_TEAM.format(team=", ".join(uname(st, s) for s in d_slaves)))
    pwin = my_p / (my_p + ta_p) if (my_p + ta_p) > 0 else 0.5
    lines.append(_S.T.FIGHT_WINRATE.format(pct=int(pwin * 100)))
    win = _random.random() < pwin

    def _shield(owner_q):
        return _has_treasure_type(treasures_of(U(st, owner_q)), "shield", (SHIELD_TREASURE,))

    if win:
        lines.append(_S.T.FIGHT_WIN)
        free_slot = len(slaves_of(st, qq)) < _safe_int(uget(U(st, qq), "slave_slots",
                                                  str(cfgi("设置", "奴隶个数", 5))), cfgi("设置", "奴隶个数", 5))
        stealable = [s for s in d_slaves]
        if stealable and free_slot:
            if _shield(tid):
                victim = _random.choice(stealable)
                lines.append(_S.T.FIGHT_TA_TREASURE)
                lines.append("[" + uname(st, victim) + "]" + _S.T.FIGHT_TA_SHIELD)
            else:
                victim = _random.choice(stealable)
                uset(U(st, victim), "owner", qq)
                uset(U(st, victim), "purchase_price", str(int(uget(U(st, victim), "price") or 0)))
                uset(U(st, victim), "purchase_time", cn_fmt(_time.time()))
                uset(U(st, victim), "_work_wage", "")
                newp = min(_S.MAX_PRICE, int(int(uget(U(st, victim), "price") or 0) * cfgf("费用配置", "买入身价上涨", _S.PRICE_UP)))
                uset(U(st, victim), "price", str(newp))
                lines.append(_S.T.FIGHT_GET_SLAVE.format(slave="[" + uname(st, victim) + "]"))
        elif stealable:
            ransom = min(cdd, stake)
            coins_add(gid, tid, -ransom)
            coins_add(gid, qq, ransom)
            lines.append(_S.T.FIGHT_SLOT_FULL.format(money=ransom))
    else:
        lines.append(_S.T.FIGHT_LOSE)
        shield = _shield(qq)
        stealable = [s for s in a_slaves]
        if stealable and not shield:
            free_t = len(slaves_of(st, tid)) < _safe_int(uget(U(st, tid), "slave_slots",
                                                   str(cfgi("设置", "奴隶个数", 5))), cfgi("设置", "奴隶个数", 5))
            if free_t:
                victim = _random.choice(stealable)
                uset(U(st, victim), "owner", tid)
                uset(U(st, victim), "purchase_price", str(int(uget(U(st, victim), "price") or 0)))
                uset(U(st, victim), "purchase_time", cn_fmt(_time.time()))
                uset(U(st, victim), "_work_wage", "")
                newp = min(_S.MAX_PRICE, int(int(uget(U(st, victim), "price") or 0) * cfgf("费用配置", "买入身价上涨", _S.PRICE_UP)))
                uset(U(st, victim), "price", str(newp))
                lines.append(_S.T.FIGHT_LOSE_SLAVE.format(slave="[" + uname(st, victim) + "]"))
            else:
                ransom = min(ca, stake)
                coins_add(gid, qq, -ransom)
                coins_add(gid, tid, ransom)
                lines.append(_S.T.FIGHT_PAY_MONEY.format(money=ransom))
        elif shield:
            victim = _random.choice(stealable)
            lines.append(_S.T.FIGHT_MY_TREASURE)
            lines.append("[" + uname(st, victim) + "]" + _S.T.FIGHT_MY_SHIELD)
    return "\r\n".join(lines)




def _weapon_shop_raw():
    """返回原始 weapon_shop 配置对象(可能含 {price,atk,desc,img})，供取图/数值用；空=未自定义"""
    return store.cfg_dict("商城图鉴", "weapon_shop")



# 旧商城只读兼容别名（v0.7.16起改抽奖池直管；与 _weapon_shop_raw 同一对象，零语义差）
_weapon_shop = _weapon_shop_raw




__all__ = ["atk_of", "battle_power", "cmd_fight"]
