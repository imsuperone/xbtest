# -*- coding: utf-8 -*-
"""games/slave/gacha.py — 奴隶包·gacha（原 slave.py 切分，语义不变）。"""
import os as _os
import time as _time
import random as _random
try:
    from ...core import storage as ST
except ImportError:
    from core import storage as ST
from . import slave_state as _S
from .base import U, _safe_int, cfgi, coins_add, coins_get, star_of, treasures_of, uget, uset, weapons_of
from .combat import _treasure_effect, _treasure_names, _weapon_atk_bonus, _weapon_shop, _weapon_shop_raw
from .nick import uname
from .profile import coin_name

def _gacha_dirs(rar):
    """抽奖池候选目录（持久化旧位优先保用户池 → 持久新位 → 包内 data/games/img/nuli）"""
    cands = []
    try:
        cands.append(_os.path.join(_S.DATA_DIR, "img", "gacha", rar))
        cands.append(_os.path.join(_S.DATA_DIR, "gacha_img", rar))
        cands.append(_os.path.join(_S.DATA_DIR, "img", "nuli", rar))
        cands.append(_os.path.join(_S._BASE, "data", "games", "img", "nuli", rar))
    except Exception:
        pass
    out = []
    for d in cands:
        try:
            if d and d not in out:
                out.append(d)
        except Exception:
            pass
    return out




def _gacha_pool(rar):
    now = _time.time()
    hit = _S._GACHA_CACHE.get(rar)
    ts = _S._GACHA_CACHE_TS.get(rar, 0)
    if hit is not None and now - ts < _S._GACHA_TTL and len(hit) > 0:
        return hit
    # 优先使用持久化数据目录，若无则回退至插件内置图库；新旧目录都认
    lst = []
    try:
        for dd in _gacha_dirs(rar):
            try:
                if _os.path.isdir(dd) and _os.listdir(dd):
                    lst = [_os.path.join(dd, f) for f in sorted(_os.listdir(dd)) if f.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".webp"))]
                    if lst:
                        break
            except Exception:
                continue
    except Exception:
        lst = []
    _S._GACHA_CACHE[rar] = lst
    _S._GACHA_CACHE_TS[rar] = now
    return lst



def cmd_gacha(gid, qq, st, count=1):
    count = count if count in _S._GACHA_LABEL else 1
    n = count
    label = _S._GACHA_LABEL[count]
    cost = cfgi("设置", _S._GACHA_COST_KEY[count], _S._GACHA_COST_DEF[count])
    if not any(_gacha_pool(r) for r in ("SSR", "SR", "R")):
        return "武器图库为空, 请管理员先放入 SSR/SR/R 图鉴后再来抽~"
    u = U(st, qq)
    if coins_get(gid, qq) < cost:
        return f"武器{label}需要消耗{cost}{coin_name()}, " + _S.T.POOR.format(coin=coin_name())
    coins_add(gid, qq, -cost)

    pr = {"R": cfgi("设置", "抽武器R概率", 50),
          "SR": cfgi("设置", "抽武器SR概率", 38),
          "SSR": cfgi("设置", "抽武器SSR概率", 2)}
    exp_map = {"R": cfgi("设置", "R经验", 9),
               "SR": cfgi("设置", "SR经验", 99),
               "SSR": cfgi("设置", "SSR经验", 299)}

    results, imgs, exp_total = [], [], 0
    owned = set(weapons_of(u))
    got_ssr = False
    agg = {}
    for i in range(n):
        roll = _random.uniform(0, 100)
        acc, rar = 0, "R"
        for r in ("SSR", "SR", "R"):
            acc += pr[r]
            if roll <= acc:
                rar = r
                break
        pool = _gacha_pool(rar)
        if not pool:
            for alt in ("R", "SR", "SSR"):
                alt_pool = _gacha_pool(alt)
                if alt_pool:
                    rar = alt
                    pool = alt_pool
                    break
        if not pool:
            continue
        imgpath = _random.choice(pool)
        name = _os.path.splitext(_os.path.basename(imgpath))[0]
        e_gain = exp_map.get(rar, 9)

        if rar == "SSR":
            if name in owned:
                exp_total += e_gain
                cur = int(uget(u, name, "0") or 0) + 1
                uset(u, name, str(cur))
                uset(u, "weapon_exp", str(int(uget(u, "weapon_exp") or 0) + e_gain))
                results.append(f"{name} 重复获得，转化为武器经验：{e_gain}")
            else:
                owned.add(name)
                wl = weapons_of(u)
                wl.append(name)
                uset(u, "weapon", "|".join(wl))
                uset(u, name, "1")
                if not st.has_option(str(qq), name + "升星"):
                    uset(u, name + "升星", "0")
                _pp = _img_path(_os.path.abspath(imgpath))
                if _pp:
                    imgs.append(_pp)
                got_ssr = True
                results.append(f"🌟NEW! {name}")
        else:
            exp_total += e_gain
            uset(u, "weapon_exp", str(int(uget(u, "weapon_exp") or 0) + e_gain))
            if count == 1:
                results.append(f"{rar}·{name} 经验+{e_gain}")
            else:
                a = agg.setdefault(rar, [0, 0])
                a[0] += 1
                a[1] += e_gain
    if count > 1:
        for rar in ("SR", "R"):
            if rar in agg:
                c, e = agg[rar]
                results.append(f"{rar}×{c}，自动转化为经验+{e}")
    head = f"[{uname(st,qq)}] " + (f"武器{label}需要消耗{cost}{coin_name()}" if count > 1 else (f"本次抽武器消耗{cost}{coin_name()}"))

    out = head + "\r\n" + "\r\n".join(results)
    if count >= 10 and not got_ssr:
        out += "\r\n" + _S.T.GACHA_NO_SSR
    out += "\r\n" + (_S.T.GACHA_TOTAL_EXP.format(exp=exp_total))
    out += "\r\n💡 R/SR已自动转为经验; SSR可装备出战"
    if imgs:
        # 十连及以上展示最多10张，单抽展示1张；元组直传（图2路径，不再拼CQ字符串）
        lim = 10 if count >= 10 else 4
        return out, imgs[:lim]
    return out




def cmd_starup(gid, qq, wname, st):
    wname = wname.strip("+ ").strip()
    u = U(st, qq)
    wl = weapons_of(u)
    if wname not in wl:
        return _S.T.WUP_NOT_EXIST
    lv = star_of(u, wname)
    if lv >= 5:
        return _S.T.WUP_MAX
    cn = ["一", "二", "三", "四", "五"][lv]
    need_cnt = cfgi("设置", f"{cn}星武器消耗同武器数量", lv + 1)
    cost = cfgi("设置", f"{cn}星武器花费", 5555)
    prob = cfgi("设置", f"{cn}星武器概率", 50)
    need_exp = cfgi("设置", f"{cn}星武器经验", 999)

    mat = int(uget(u, wname, "0"))
    curexp = int(uget(u, "weapon_exp") or 0)
    if mat < need_cnt:
        return (_S.T.WUP_USE_WEAPON.format(items=f"{wname}x{need_cnt}")) + "\r\n" + \
               _S.T.NOT_ENOUGH + f"(现有同名{mat})"
    if curexp < need_exp:
        return _S.T.WUP_NO_EXP + f"(需{need_exp}, 现有{curexp})"
    if coins_get(gid, qq) < cost:
        return _S.T.WUP_USE_COIN.format(coin=cost) + "\r\n" + _S.T.POOR.format(coin=coin_name())

    coins_add(gid, qq, -cost)
    if _random.randint(1, 100) > prob:
        uset(u, wname, str(mat - need_cnt))
        uset(u, "weapon_exp", str(curexp - need_exp))
        return (_S.T.WUP_FAIL + "\r\n" + _S.T.WUP_USE_WEAPON.format(items=f"{wname}x{need_cnt}")
                + "\r\n" + _S.T.WUP_USE_EXP.format(exp=need_exp)
                + "\r\n" + _S.T.WUP_PROB.format(prob=prob))
    uset(u, wname, str(mat - need_cnt))
    uset(u, "weapon_exp", str(curexp - need_exp))
    uset(u, wname + "升星", str(lv + 1))
    return _S.T.WUP_OK.format(name=wname) + f" 当前{lv+1}星!"




def cmd_treasure_up(gid, qq, tname, st):
    tname = tname.strip("+＋ ").strip()
    treas = _treasure_names()
    if tname not in treas:
        return _S.T.TUP_NOT_EXIST
    u = U(st, qq)
    if not treasures_of(u):
        return _S.T.TUP_HAVE_NONE
    stage = int(uget(u, tname + "升阶", "0"))
    if stage >= 3:
        return _S.T.TUP_MAX
    idx = ["一", "二", "三"][stage]
    need = cfgi("设置", f"{idx}阶宝物消耗宝物数量", stage + 1)
    cost = cfgi("设置", f"{idx}阶宝物花费", 77777)
    prob = cfgi("设置", f"{idx}阶宝物概率", 50)
    have = _safe_int(uget(u, tname, "0"), 0)
    if have < need:
        return _S.T.TUP_NO_ITEM + f"(需{tname}x{need}, 现有{have})"
    if coins_get(gid, qq) < cost:
        return f"升阶需要{cost}{coin_name()}，哦，攒够了再来吧~"

    coins_add(gid, qq, -cost)
    if _random.randint(1, 100) > prob:
        uset(u, tname, str(have - need))
        return (_S.T.TUP_FAIL + "\r\n" + _S.T.TUP_USED.format(items=f"{tname}x{need}")
                + "\r\n" + _S.T.TUP_COST.format(cost=cost)
                + "\r\n" + _S.T.TUP_PROB.format(prob=prob)
                + "\r\n升阶失败只扣除材料，宝物不会消失哦~")
    uset(u, tname, str(have - need))
    uset(u, tname + "升阶", str(stage + 1))
    eff = _treasure_effect(tname)
    return (f"✨ [{tname}] 升至{stage+1}阶!\r\n{_S.T.T_STAGE.format(n=stage+1)} "
            + eff)




def _weapon_img_path(name):
    """取武器绑定图片路径(优先配置的 img)，否则回退抽奖池文件；空即无图"""
    try:
        raw = _weapon_shop_raw()
        if raw and isinstance(raw, dict):
            v = raw.get(name)
            if isinstance(v, dict) and str(v.get("img") or "").strip():
                p = str(v.get("img")).strip()
                if _os.path.isabs(p):
                    if _os.path.isfile(p):
                        return [_os.path.abspath(p)]
                else:
                    try:
                        base = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
                        cand = _os.path.join(base, p)
                        if _os.path.isfile(cand):
                            return [_os.path.abspath(cand)]
                    except Exception:
                        pass
                    if _os.path.isfile(p):
                        return [_os.path.abspath(p)]
                # 配置了但文件缺失则继续回退抽奖池，避免黑图
    except Exception:
        pass
    try:
        for rar in ("SSR", "SR", "R"):
            for p in _gacha_pool(rar):
                try:
                    if _os.path.splitext(_os.path.basename(p))[0] == name and _os.path.isfile(p):
                        return [_os.path.abspath(p)]
                except Exception:
                    continue
    except Exception:
        pass
    return []




def cmd_weapon_menu(gid, qq, st):
    # 复用 gacha 缓存，避免每消息 listdir
    try:
        names = [_os.path.splitext(_os.path.basename(p))[0] for p in _gacha_pool("SSR")]
    except Exception:
        names = []
    # 合并商城武器与抽奖武器，去重
    try:
        ws = _weapon_shop()
        for k in ws.keys():
            if k not in names:
                names.append(k)
    except Exception:
        pass
    u = U(st, qq)
    owned = set(weapons_of(u))
    ws = _weapon_shop()
    lines = ["⚔️ 武器图鉴", "━━━━━━━━━━━━━━"]
    for n in names:
        star = star_of(u, n)
        own = f"✔已持有 ★{star}" if n in owned else "未持有"
        price = ws.get(n, {}).get("price", "") if isinstance(ws.get(n), dict) else ws.get(n, "")
        price_txt = f" 价格:{price}{coin_name()}" if price else ""
        # 检查图片是否存在，缺失则不显示黑图
        img_missing = ""
        try:
            # 尝试在 SSD/R 池中找对应文件
            found = False
            for rar in ("SSR","SR","R"):
                for p in _gacha_pool(rar):
                    if _os.path.splitext(_os.path.basename(p))[0] == n and _os.path.isfile(p):
                        found = True
                        break
                if found:
                    break
            if not found:
                img_missing = " (图缺)"
        except Exception:
            pass
        _bonus = _weapon_atk_bonus(n)
        _b_txt = f"(+{_bonus}配装)" if _bonus else ""
        lines.append(f"◆ {n}　攻击+{_S.STAR_ATK[min(5, star)] + _bonus}{_b_txt}　{own}{price_txt}{img_missing}")
    lines.append("━━━━━━━━━━━━━━")
    lines.append("成长: ★0+100 → ★3+600 → ★5+1600")
    lines.append("🎁 获取: 【抽武器】【十连抽】【三十连抽】【五十连抽】")
    lines.append("💡 R/SR抽到即转经验, SSR才能装备出战")
    lines.append("⭐ 升星: 【升星+武器名】如【升星雷鸣剑】")
    lines.append("🔍 详情: 直接发【武器名】如【鬼泪村正】")
    return "\r\n".join(lines)




def cmd_treasure_menu(gid, qq, st):
    treas = _treasure_names()
    u = U(st, qq)

    def eff(t):
        return _treasure_effect(t)

    lines = ["🎁 宝物图鉴", "━━━━━━━━━━━━━━"]
    for t in treas:
        cnt = _safe_int(uget(u, t, "0"), 0)
        stage = _safe_int(uget(u, t + "升阶", "0"), 0)
        own = f"✔已持有{cnt}个" if cnt > 0 else "未持有"
        lines.append(f"◆ {t}　{own}")
        e = eff(t)
        if e:
            lines.append(f"　└ {e}")
            if stage:
                lines[-1] += f"(当前{stage}阶)"
    lines.append("━━━━━━━━━━━━━━")
    lines.append("🍀 获取: 【我要学习】概率奇遇(获取即生效)")
    lines.append("🔺 升阶: 【升阶+宝物名】如【升阶酒神葫芦】")
    lines.append("🔍 详情: 直接发【宝物名】如【酒神葫芦】")
    return "\r\n".join(lines)



def _img_path(path):
    """元组图片路径: 返回绝对路径供 (text, [path]) 元组直传（图2路径，生产验证有效）"""
    try:
        p = _os.path.abspath(path)
        if not _os.path.isfile(p):
            return ""
        return p
    except Exception:
        return ""




__all__ = ["cmd_gacha", "cmd_starup", "cmd_treasure_menu", "cmd_treasure_up", "cmd_weapon_menu"]
