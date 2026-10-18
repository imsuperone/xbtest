# -*- coding: utf-8 -*-
"""签到系统引擎(字节对齐原版指令/文案/字段; 数值走配置)"""
import datetime as dt
import random

try:
    from ..core import storage as ST
except ImportError:
    try:
        from . import storage as ST
    except ImportError:
        from core import storage as ST
try:
    from .config.sign import (
        DEFAULTS as _SIGN_DEFAULTS, CHAIN_CAP,
        STAMINA_SOFT_CAP, STAMINA_HARD_CAP, STAMINA_OVERFLOW_COIN, STAMINA_BUY_DAILY_CAP,
        CHARM_SOFT_CAP, CHARM_HARD_CAP, CHARM_OVERFLOW_COIN, CHARM_DECAY_PCT, CHARM_BUY_DAILY_CAP,
    )
except ImportError:
    from games.config.sign import (  # type: ignore
        DEFAULTS as _SIGN_DEFAULTS, CHAIN_CAP,
        STAMINA_SOFT_CAP, STAMINA_HARD_CAP, STAMINA_OVERFLOW_COIN, STAMINA_BUY_DAILY_CAP,
        CHARM_SOFT_CAP, CHARM_HARD_CAP, CHARM_OVERFLOW_COIN, CHARM_DECAY_PCT, CHARM_BUY_DAILY_CAP,
    )


def cfgi(sec, key, default=0):
    # 默认值单源：games/config/sign.py DEFAULTS 表命中即用表值（行内兜底仅动态键时生效）
    try:
        if (sec, key) in _SIGN_DEFAULTS:
            default = _SIGN_DEFAULTS[(sec, key)]
    except Exception:
        pass
    return ST.cfgi(sec, key, default)


def cfg(sec, key, default=""):
    try:
        if (sec, key) in _SIGN_DEFAULTS:
            default = _SIGN_DEFAULTS[(sec, key)]
    except Exception:
        pass
    return ST.cfg(sec, key, default)

DAYS_CN = ("", "一", "二", "三", "四", "五", "六", "日")

# ---- 每日打卡：幸运值 → 当日概率浮动（签到系统归属，第一版） ----
# 规则：每群独立，每人每天限 1 次；幸运值 1-100 随机；
# 加成 = (幸运值-50)/50*0.3（百分点）：50→0，100→+0.3，1→约-0.294
DAILY_LUCK_MAX_BONUS = 0.3


def daily_luck_delta_pp(luck):
    """幸运值 → 当日概率浮动（百分点，如 +0.3 表示 +0.3%）。"""
    try:
        v = int(luck)
    except Exception:
        return 0.0
    try:
        max_b = float(cfg("打卡配置", "最大加成", DAILY_LUCK_MAX_BONUS) or DAILY_LUCK_MAX_BONUS)
    except Exception:
        max_b = DAILY_LUCK_MAX_BONUS
    return (v - 50) / 50.0 * max_b


def get_daily_luck(gid, qq):
    """返回 (幸运值int, 加成float百分点, 日期str)；今日未打卡返回 (None, 0.0, today)。"""
    today = _today().isoformat()
    try:
        a = _acct(gid, qq)
        d = str(a.get("daily_luck_date", "") or "")
        if d == today:
            try:
                luck = int(float(a.get("daily_luck_value", "0") or 0))
            except Exception:
                luck = 0
            return luck, daily_luck_delta_pp(luck), d
    except Exception:
        pass
    return None, 0.0, today


def get_daily_bonus(gid, qq):
    """今日概率加成（百分点）；未打卡=0.0。供各概率玩法调用。"""
    try:
        _luck, delta, _d = get_daily_luck(gid, qq)
        return float(delta or 0.0)
    except Exception:
        return 0.0


def eff_prob(base, gid=None, qq=None, bonus=None):
    """基础概率%(0-100)叠加每日打卡加成，钳制 0-100。"""
    try:
        b = float(base)
    except Exception:
        return base
    try:
        if bonus is None:
            bonus = get_daily_bonus(gid, qq) if gid is not None and qq is not None else 0.0
        return max(0.0, min(100.0, b + float(bonus)))
    except Exception:
        return b


def eff_p01(p, gid=None, qq=None, bonus=None):
    """0-1 概率叠加每日打卡加成（百分点→小数），钳制 0-1。"""
    try:
        v = float(p)
    except Exception:
        return p
    try:
        if bonus is None:
            bonus = get_daily_bonus(gid, qq) if gid is not None and qq is not None else 0.0
        return max(0.0, min(1.0, v + float(bonus) / 100.0))
    except Exception:
        return v


def cmd_daily_checkin(gid, qq):
    """每日打卡：每群独立、每人每天限1次；摇 1-100 幸运值，当日概率玩法按此浮动。"""
    with ST._LOCK:
        a = _acct(gid, qq)
        today = _today().isoformat()
        if str(a.get("daily_luck_date", "") or "") == today:
            try:
                luck = int(float(a.get("daily_luck_value", "0") or 0))
            except Exception:
                luck = 0
            delta = daily_luck_delta_pp(luck)
            sign = "+" if delta >= 0 else ""
            return (f"📅 你今天已经打卡过了！\n"
                    f"🍀 今日幸运值：{luck}\n"
                    f"📈 今日概率加成：{sign}{delta:.2f}%（大部分概率玩法生效，明天再来）")
        l_lo = max(1, min(100, cfgi("打卡配置", "每日幸运下限", 1)))
        l_hi = max(l_lo, min(100, cfgi("打卡配置", "每日幸运上限", 100)))
        luck = random.randint(l_lo, l_hi)
        delta = daily_luck_delta_pp(luck)
        a.set("daily_luck_date", today)
        a.set("daily_luck_value", str(luck))
        if not ST.acct_save(gid, qq):
            return "打卡系统繁忙，本次未记录，请稍后重试！"
    sign = "+" if delta >= 0 else ""
    tip = "鸿运当头" if luck >= 90 else ("好运在线" if luck >= 70 else ("平稳一天" if luck >= 40 else "稳住能赢"))
    return (f"📅 每日打卡成功！\n"
            f"🍀 今日幸运值：{luck}（{tip}）\n"
            f"📈 今日概率加成：{sign}{delta:.2f}%（大部分概率玩法生效）")


def _ymd(d):
    return "%d年%d月%d日" % (d.year, d.month, d.day)


def _today():
    return dt.date.today()


def _acct(gid, qq):
    return ST.acct(gid, qq)


def _today_sign_order(gid):
    """本群今日签到顺序: 按 群+日期 累计(第N个签到者)。返回本次是第几个。"""
    date_key = dt.datetime.now().strftime("%Y%m%d")
    k = "signorder_%s_%s" % (str(gid), date_key)
    try:
        n = int(ST.recall_get(k, "0") or 0) + 1
        ST.recall_set(k, str(n))
        # 轻量GC：每次顺手清理7天前的旧签到顺序键，避免 kv 无限膨胀（中文显示不受影响）
        try:
            if n == 1:
                # 仅首签时触发一次清理，降低开销
                cutoff = (dt.date.today() - dt.timedelta(days=7)).strftime("%Y%m%d")
                with ST._LOCK:
                    if ST._DB is not None:
                        rows = ST._DB.execute("SELECT k FROM kv WHERE k LIKE 'signorder_%'").fetchall()
                        for (kk,) in rows:
                            try:
                                dpart = kk.rsplit("_", 1)[-1]
                                if dpart.isdigit() and len(dpart) == 8 and dpart < cutoff:
                                    ST._DB.execute("DELETE FROM kv WHERE k=?", (kk,))
                            except Exception:
                                continue
                        if rows:
                            ST._safe_commit()
        except Exception:
            pass
        return n
    except Exception:
        return 0


def settle_stat_gain(cur_val, gain, soft_cap, hard_cap, coin_rate, daily_decay_pct=0):
    """体力/魅力软硬上限与溢出折算单源（折算收益已下调为原值的 25%）：
    1. 历史超硬上限(hard_cap)部分强制压回 hard_cap，超额点按 coin_rate 折算金币（单次折算上限 75 点）
    2. 若启用每日高值衰减(daily_decay_pct>0)，超出 soft_cap 部分按比例自然衰减
    3. 本次新增 gain 若使数值超过 soft_cap，超出部分不累加，自动按 coin_rate(原值25%) 折算为金币
    返回: (new_val, eff_gain, overflow_pts, overflow_coins, decayed_pts)
    """
    cur = max(0, int(cur_val or 0))
    g = max(0, int(gain or 0))
    s_cap = max(1, int(soft_cap or 300))
    h_cap = max(s_cap, int(hard_cap or 500))
    rate = max(0, int(coin_rate or 0))

    hard_ov = 0
    if cur > h_cap:
        hard_ov = cur - h_cap
        cur = h_cap

    decayed = 0
    if daily_decay_pct > 0 and cur > s_cap:
        decayed = max(1, int((cur - s_cap) * int(daily_decay_pct) // 100))
        cur = max(s_cap, cur - decayed)

    if cur < s_cap:
        room = s_cap - cur
        eff_gain = min(g, room)
        soft_ov = g - eff_gain
        new_val = cur + eff_gain
    else:
        eff_gain = 0
        soft_ov = g
        new_val = cur

    conv_pts = soft_ov + min(hard_ov, 75)
    ov_coins = conv_pts * rate
    return new_val, eff_gain, soft_ov + hard_ov, ov_coins, decayed


def cmd_sign(gid, qq):
    """签到: 基础奖励 + 连签加成 + 软硬上限折算 + 身价/资产联动(财富=现金+存款)"""
    # 判重+读-算-写全程持 _LOCK（RLock 可重入，txn 内复入无死锁）：防并发双签双领
    with ST._LOCK:
        a = _acct(gid, qq)
        today = _today().isoformat()
        stam_soft = cfgi("签到配置", "体力软上限", STAMINA_SOFT_CAP)
        stam_hard = cfgi("签到配置", "体力硬上限", STAMINA_HARD_CAP)
        charm_soft = cfgi("签到配置", "魅力软上限", CHARM_SOFT_CAP)
        charm_hard = cfgi("签到配置", "魅力硬上限", CHARM_HARD_CAP)
        # 重复签到看两个日期键（旧数据可能只写其一，任一是今天都算已签，禁错位双签）
        if a.get("sign_date") == today or a.get("last_sign_date") == today:
            # 重复签到时顺带自愈压制超标体力/魅力
            try:
                _cs = int(float(a.get("stamina", "0") or 0))
                _cc = int(float(a.get("charm", "0") or 0))
                if _cs > stam_hard or _cc > charm_hard:
                    a.set("stamina", str(min(stam_hard, _cs)))
                    a.set("charm", str(min(charm_hard, _cc)))
                    ST.acct_save(gid, qq)
            except Exception:
                pass
            return cfg("签到配置", "重复签到文案",
                          "亲，您今天已经签到过了，请明天继续吧！")
        # 脏值自愈：计数坏串按 0 起（禁整单抛错锁死签到）
        try:
            total = int(float(a.get("sign_count", "0")))
        except Exception:
            total = 0
        try:
            chain = int(float(a.get("consecutive_days", "0")))
        except Exception:
            chain = 0
        prev = str(a.get("last_sign_date", "") or a.get("sign_date", ""))
        yest = (dt.date.today() - dt.timedelta(days=1)).isoformat()
        chain = chain + 1 if prev == yest else 1
        # 签到奖励按区间(优先支持中英双向键与休闲高福利默认值)
        def _rng(cn_k, en_k, d_lo, d_hi):
            lo = cfgi("签到配置", cn_k + "下限", cfgi("签到配置", en_k + "下限", d_lo))
            hi = cfgi("签到配置", cn_k + "上限", cfgi("签到配置", en_k + "上限", d_hi))
            if lo > hi: lo, hi = hi, lo
            return random.randint(lo, hi)
        base_cfg = cfgi("签到配置", "基础奖励", 0)
        if base_cfg:
            base = base_cfg
        else:
            base = _rng("金钱", "money", 800, 2000)
        tili = _rng("体力", "stamina", 40, 80)
        meili = _rng("魅力", "charm", 15, 30)
        juan = _rng("奖券", "lottery_tickets", 3, 8)
        bonus = cfgi("签到配置", "连签加成", 100)
        chain_bonus = bonus * min(chain, CHAIN_CAP)
        total += 1
        # 预取当前额外属性旧值，用于一次事务内计算新值（避免 3次 acct_add+acct_save 的 3锁3提交）
        # 脏值自愈同上，坏串按 0 起
        try:
            cur_stam = int(float(a.get("stamina", "0") or 0))
        except Exception:
            cur_stam = 0
        try:
            cur_charm = int(float(a.get("charm", "0") or 0))
        except Exception:
            cur_charm = 0
        try:
            cur_juan = int(float(a.get("lottery_tickets", "0") or 0))
        except Exception:
            cur_juan = 0

        # 软硬上限与溢出自动折算金币
        stam_rate = cfgi("签到配置", "溢出体力折算金币", STAMINA_OVERFLOW_COIN)
        charm_rate = cfgi("签到配置", "溢出魅力折算金币", CHARM_OVERFLOW_COIN)
        charm_decay = cfgi("签到配置", "高魅力日衰减比例", CHARM_DECAY_PCT)

        new_stam, eff_tili, ov_tili, coin_tili, dec_tili = settle_stat_gain(
            cur_stam, tili, stam_soft, stam_hard, stam_rate, daily_decay_pct=charm_decay
        )
        new_charm, eff_meili, ov_meili, coin_meili, dec_meili = settle_stat_gain(
            cur_charm, meili, charm_soft, charm_hard, charm_rate, daily_decay_pct=charm_decay
        )
        ov_total_coin = coin_tili + coin_meili

        # 单事务：钱包 delta + 账户批量字段（原5次提交→1次，持锁 1次）
        # txn 失败返 None：禁止拆成多次独立写入补偿，避免签到奖励半成功。
        if ST.txn_coins_acct(gid, qq, base + chain_bonus + ov_total_coin, {
            "sign_count": str(total),
            "total_sign_days": str(total),
            "consecutive_days": str(chain),
            "sign_date": today,
            "last_sign_date": today,
            "account_created": a.get("account_created") or dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "stamina": str(new_stam),
            "charm": str(new_charm),
            "lottery_tickets": str(cur_juan + juan),
        }) is None:
            return "签到系统繁忙，本次未结算，请稍后重试！"
    # 同步更新奴隶系统的 Group 存储，保证两边完全一致（走 DirtyDict 增量，持锁防单群并发崩溃）
    try:
        with ST._LOCK:
            g = ST.group(gid)
            u = g[qq]  # __getitem__ 自动 DirtyDict+标脏
            u["total_sign_days"] = str(total)
            u["shadow_streak"] = str(chain)
            u["consecutive_days"] = str(chain)
            u["last_sign"] = today
            u["shadow_date"] = _ymd(_today())
        ST.save_group(gid)
    except Exception:
        pass
    order = _today_sign_order(gid)
    coin = ST.coin_name()
    stam_note = f"（溢出{ov_tili}→+{coin_tili}{coin}）" if ov_tili > 0 else ""
    charm_notes = []
    if dec_meili > 0:
        charm_notes.append(f"名流衰减-{dec_meili}")
    if ov_meili > 0:
        charm_notes.append(f"溢出{ov_meili}→+{coin_meili}{coin}")
    charm_note = f"（{'，'.join(charm_notes)}）" if charm_notes else ""
    return ("🏅 恭喜你签到成功！\r\n"
            "　奖励详情：\r\n"
            f"　　　💵 {coin} +{ST.fmt_coins(base)}\r\n"
            f"　　　⚡ 体力 +{eff_tili}{stam_note}\r\n"
            f"　　　💄 魅力 +{eff_meili}{charm_note}\r\n"
            f"　　　🎫 奖券 +{juan}\r\n"
            f"　　　🔥 第{days_cn(chain)}天连签 +{ST.fmt_coins(chain_bonus)}\r\n"
            f"当前{coin}：{ST.fmt_coins(ST.coins_get(gid, qq))}\r\n"
            f"您是今天第{order}个签到者！")


def days_cn(chain):
    try:
        c = int(chain)
    except Exception:
        c = 1
    if 1 <= c <= 7:
        return DAYS_CN[c]
    return str(c)


def cmd_draw(gid, qq, amount=1):
    """抽奖: 消耗奖券(默认1张), 支持多连抽（如抽奖52）；先全量预摇奖，再一次事务
    扣券+发奖+写连败 streak（禁逐抽部分结算、禁失败后重摇）"""
    if amount <= 0:
        amount = 1
    if amount > 999:
        return "单次抽奖上限999张！"
    a = _acct(gid, qq)
    # 读券→摇奖→结算全程持 _LOCK（RLock 可重入，txn 内复入无死锁）：防同用户并发双花；
    # 摇奖为纯内存随机（≤999 次），持锁窗口可忽略
    with ST._LOCK:
        tickets = a.int("lottery_tickets")
        if tickets < amount:
            return f"奖券不足，需{amount}张，当前{tickets}张！"
        cur_stam = a.int("stamina")
        cur_charm = a.int("charm")
        lose_streak = int(a.get("lottery_lose_streak", "0") or "0")
        # 预摇奖（纯随机，无 IO）：失败路径不再重摇，结果幂等
        _coin_name = ST.coin_name()
        _rate = cfgi("抽奖配置", "中奖率", 45)
        try:
            _rate = eff_prob(_rate, gid, qq)
        except Exception:
            pass
        _coin_v = cfgi("抽奖配置", "现金奖", 500)
        _stam_v = cfgi("抽奖配置", "体力奖", 10)
        _charm_v = cfgi("抽奖配置", "魅力奖", 10)
        _user_total_money = ST.coins_get(gid, qq) + a.int("deposit")
        _is_whale = _user_total_money >= 1000000

        _outcomes = []
        _streak = lose_streak
        _refund_tickets = 0
        _items_won = {}
        for _i in range(amount):
            _must = _streak >= 10
            _win = _must or (random.randint(1, 100) <= _rate)
            if _win:
                _roll_type = random.randint(1, 100)
                if _roll_type <= 65:
                    _cand = random.choice(["coin", "stamina", "charm"])
                    if _cand == "coin":
                        if _is_whale:
                            # 巨鲸防通胀：大户抽中现金自动替换为基础道具或体力，杜绝继续向全服印钞
                            _name_cn, _kind, _val = ("吐司", "item", 1)
                            _items_won["吐司"] = _items_won.get("吐司", 0) + 1
                        else:
                            _name_cn, _kind, _val = (_coin_name, "coin", _coin_v)
                    elif _cand == "stamina":
                        _name_cn, _kind, _val = ("体力", "stamina", _stam_v)
                    else:
                        _name_cn, _kind, _val = ("魅力", "charm", _charm_v)
                elif _roll_type <= 95:
                    # 基础道具奖励（奖券获取极容易，只出日常基础消耗品，保住商城高级道具价值）
                    _it_name = random.choice(["精灵球", "时间球", "吐司", "攻击之源", "防御之源"])
                    _items_won[_it_name] = _items_won.get(_it_name, 0) + 1
                    _name_cn, _kind, _val = (_it_name, "item", 1)
                else:
                    # 奖券返还（再来一次：大幅压低概率至 5%，且固定仅返还 1 张，杜绝无限套娃）
                    _t_cnt = 1
                    _refund_tickets += _t_cnt
                    _name_cn, _kind, _val = ("奖券", "ticket", _t_cnt)

                _outcomes.append((_kind, _name_cn, int(_val)))
                _streak = 0
            else:
                _outcomes.append(None)
                _streak += 1
        total_coin = sum(_o[2] for _o in _outcomes if _o is not None and _o[0] == "coin") if _outcomes else 0
        total_tili = sum(_o[2] for _o in _outcomes if _o is not None and _o[0] == "stamina") if _outcomes else 0
        total_meili = sum(_o[2] for _o in _outcomes if _o is not None and _o[0] == "charm") if _outcomes else 0
        wins = sum(1 for _o in _outcomes if _o is not None)

        stam_soft = cfgi("签到配置", "体力软上限", STAMINA_SOFT_CAP)
        stam_hard = cfgi("签到配置", "体力硬上限", STAMINA_HARD_CAP)
        stam_rate = cfgi("签到配置", "溢出体力折算金币", STAMINA_OVERFLOW_COIN)
        charm_soft = cfgi("签到配置", "魅力软上限", CHARM_SOFT_CAP)
        charm_hard = cfgi("签到配置", "魅力硬上限", CHARM_HARD_CAP)
        charm_rate = cfgi("签到配置", "溢出魅力折算金币", CHARM_OVERFLOW_COIN)

        new_stam, eff_tili, ov_tili, coin_tili, _ = settle_stat_gain(
            cur_stam, total_tili, stam_soft, stam_hard, stam_rate
        )
        new_charm, eff_meili, ov_meili, coin_meili, _ = settle_stat_gain(
            cur_charm, total_meili, charm_soft, charm_hard, charm_rate
        )
        ov_coins = coin_tili + coin_meili

        _updates = {
            "lottery_tickets": str(max(0, tickets - amount + _refund_tickets)),
            "stamina": str(new_stam),
            "charm": str(new_charm),
            "lottery_lose_streak": str(_streak),
        }
        if _items_won:
            try:
                import json as _json
                _sp_raw = a.get("spirits", "{}") or "{}"
                _sp = _json.loads(_sp_raw) if _sp_raw else {}
                _bag = _sp.setdefault("bag", {})
                for _ik, _iv in _items_won.items():
                    _bag[_ik] = int(_bag.get(_ik, 0) or 0) + _iv
                _updates["spirits"] = _json.dumps(_sp, ensure_ascii=False)
            except Exception:
                pass

        # 单事务原子结算：钱包 delta + 奖券/体力/魅力/streak/背包 一次提交
        _res = ST.txn_coins_acct(gid, qq, total_coin + ov_coins, _updates)
        if _res is None:
            return "抽奖系统繁忙，本次抽奖未结算（奖券未扣除），请稍后重试！"
        try:
            a.set("lottery_lose_streak", str(_streak))
            a.dirty = False
        except Exception:
            pass
    if amount == 1:
        _o = _outcomes[0]
        if _o is None:
            return "很遗憾，本次未中奖，再接再厉！"
        _kind, _name_cn, _val = _o
        if _kind == "ticket":
            return f"恭喜，欧气爆发！获得 奖券+{_val}（再来一次！）"
        if _kind == "item":
            return f"恭喜，欧皇附体！获得珍稀道具「{_name_cn}」×{_val}（已存入背包）"
        ov_tip = f"（满额溢出折算+{ov_coins}{_coin_name}）" if ov_coins > 0 else ""
        return f"恭喜，抽奖成功！获得{_name_cn}+{_val}{ov_tip}"
    # 多连抽汇总（明细仅 amount<=10 时展开，避免刷屏）
    out_lines = []
    if amount <= 10:
        for _i, _o in enumerate(_outcomes):
            if _o is None:
                out_lines.append(f"第{_i+1}抽：很遗憾 未中奖")
            else:
                out_lines.append(f"第{_i+1}抽：恭喜 获得{_o[1]}+{_o[2]}")
    summary = f"抽奖{amount}连抽完成：中奖{wins}/{amount}"
    if total_coin:
        summary += f" {_coin_name}+{total_coin}"
    if total_tili:
        summary += f" 体力+{eff_tili}" + (f"(溢出折算+{coin_tili}{_coin_name})" if coin_tili else "")
    if total_meili:
        summary += f" 魅力+{eff_meili}" + (f"(溢出折算+{coin_meili}{_coin_name})" if coin_meili else "")
    if _refund_tickets:
        summary += f" 奖券返还+{_refund_tickets}"
    if _items_won:
        _it_str = "、".join(f"「{k}」×{v}" for k, v in _items_won.items())
        summary += f" 道具：{_it_str}"
    if wins == 0:
        summary += "，很遗憾全未中，下次保底必中！"
    return summary + ("\r\n" + "\r\n".join(out_lines) if amount <= 10 else "")


def cmd_gift(gid, qq, kind, amount):
    """购买体力/魅力(购体力上限1000, 购魅力上限300; 价格从 签到配置 读取) 支持存款抵扣（需求39）"""
    kind_cn = "体力" if kind == "stamina" else "魅力"
    if amount <= 0:
        amount = 1
    max_single = 1000 if kind == "stamina" else 999
    if amount > max_single:
        return f"亲，{kind_cn}单次购买数量上限为{max_single}！"
    key = "stamina" if kind == "stamina" else "charm"
    buy_cap = cfgi("签到配置", "购买体力上限" if kind == "stamina" else "魅力软上限",
                   STAMINA_HARD_CAP if kind == "stamina" else CHARM_SOFT_CAP)
    daily_cap = cfgi("签到配置", "每日购买体力上限" if kind == "stamina" else "每日购买魅力上限",
                     STAMINA_BUY_DAILY_CAP if kind == "stamina" else CHARM_BUY_DAILY_CAP)
    price = cfgi("签到配置", "体力价格" if kind == "stamina" else "魅力价格", 60 if kind == "stamina" else 30)
    total = price * amount
    # 读-校验-写全程持 _LOCK（RLock 可重入）：防锁外读余额/存款/属性绝对值回写造成丢更新
    with ST._LOCK:
        a = ST.acct(gid, qq)
        have = ST.coins_get(gid, qq)
        dep = a.int("deposit")
        current_value = a.int(key)
        if current_value >= buy_cap:
            return f"亲，您的{kind_cn}已达购买上限（{buy_cap}点），无法继续直接购买，请先消耗后再来！"
        if current_value + amount > buy_cap:
            return f"亲，购买后将超出{kind_cn}上限（{buy_cap}点），您当前最多还可购买 {buy_cap - current_value} 点！"
        buy_key = f"buy_{key}_{gid}_{qq}_{_today().isoformat()}"
        bought_today = int(ST.recall_get(buy_key, "0") or 0)
        if daily_cap > 0 and bought_today + amount > daily_cap:
            left_buy = max(0, daily_cap - bought_today)
            return f"亲，每日最多限购 {daily_cap} 点{kind_cn}（今日已购 {bought_today} 点，剩余可购 {left_buy} 点）！"
        if have < total:
            need = total - have
            if dep >= need:
                updates = {key: str(current_value + amount), "deposit": str(dep - need)}
                if ST.txn_coins_acct(gid, qq, 0, updates, money_target=0) is None:
                    return "购买系统繁忙，本次购买未成功，请稍后重试！"
                total_paid = f"{have}{ST.coin_name()}+存款{need}"
            else:
                return f"亲，您的账户{ST.coin_name()}不足，无法购买！需要{total}{ST.coin_name()}（现金{have}+存款{dep}）"
        else:
            if ST.txn_coins_acct(
                gid, qq, -total, {key: str(current_value + amount)}, require_funds=True
            ) is None:
                return "购买系统繁忙，本次购买未成功，请稍后重试！"
            total_paid = f"{total}{ST.coin_name()}"
        cur = current_value + amount
        try:
            ST.recall_set(buy_key, str(bought_today + amount))
        except Exception:
            pass
    return f"恭喜您花费{total_paid}，购买了{amount}点{kind_cn}，您的{kind_cn}提升到{cur}点！"


def cmd_newbie(gid, qq):
    # 判重+读-写全程持 _LOCK（RLock 可重入）：防并发双领新手礼包
    with ST._LOCK:
        a = _acct(gid, qq)
        if a.get("novice_gift", "") == "1":
            return "亲，您已经领取过新手礼包了，无法再次领取！"
        money = cfgi("新手配置", "现金", cfgi("新手配置", "新手金币", cfgi("新手配置", "money", 20000)))
        meili = cfgi("新手配置", "魅力", cfgi("新手配置", "新手魅力", cfgi("新手配置", "charm", 150)))
        jq = cfgi("新手配置", "奖券", cfgi("新手配置", "新手奖券", cfgi("新手配置", "lottery_tickets", 30)))
        stam_hard = cfgi("签到配置", "体力硬上限", STAMINA_HARD_CAP)
        charm_soft = cfgi("签到配置", "魅力软上限", CHARM_SOFT_CAP)
        charm_hard = cfgi("签到配置", "魅力硬上限", CHARM_HARD_CAP)
        charm_rate = cfgi("签到配置", "溢出魅力折算金币", CHARM_OVERFLOW_COIN)
        # 单事务原子领取：钱包+账户同锁一次提交，避免签到并发时 database is locked
        cur_stam = int(float(a.get("stamina", "0") or 0))
        cur_charm = int(float(a.get("charm", "0") or 0))
        cur_juan = int(float(a.get("lottery_tickets", "0") or 0))
        # 体力已由每日重置机制保障（新用户已满 300）；若此前有消耗则补满至 300，避免满体力时输出 +0
        eff_stam = 0
        new_stam = cur_stam
        if cur_stam < stam_hard:
            eff_stam = stam_hard - cur_stam
            new_stam = stam_hard
        new_charm, eff_charm, _, ov_charm_c, _ = settle_stat_gain(cur_charm, meili, charm_soft, charm_hard, charm_rate)
        ov_coins = ov_charm_c
        total_money = money + ov_coins
        if ST.txn_coins_acct(gid, qq, total_money, {
            "novice_gift": "1",
            "stamina": str(new_stam),
            "charm": str(new_charm),
            "lottery_tickets": str(cur_juan + jq),
        }) is None:
            return "新手礼包系统繁忙，本次未领取成功，请稍后重试！"
        else:
            try:
                a.set("novice_gift", "1")
                a.set("stamina", str(new_stam))
                a.set("charm", str(new_charm))
                a.set("lottery_tickets", str(cur_juan + jq))
                a.dirty = False
            except Exception:
                pass
    ov_tip = f"（含溢出属性折算+{ov_coins}{ST.coin_name()}）" if ov_coins > 0 else ""
    lines = [
        "🎁 恭喜您获得新手礼包一份！",
        f"💵 {ST.coin_name()} +{total_money}{ov_tip}",
    ]
    if eff_stam > 0:
        lines.append(f"⚡ 体力 +{eff_stam}（已补满{stam_hard}）")
    lines.append(f"💄 魅力 +{eff_charm}")
    lines.append(f"🎫 奖券 +{jq}")
    return "\r\n".join(lines)


def cmd_like(gid, qq):
    a = _acct(gid, qq)
    today = _today().isoformat()
    # 全局每日一次：名片赞是 QQ 资料卡全局动作，日期闸门跨群共享（kv 按 QQ 存）；
    # A 群赞过后 B 群当天直接提示已赞，不再二次触发。旧行仍读本群 like_date 兼容当日旧档。
    gkey = "like_date_%s" % qq
    if ST.recall_get(gkey, "") == today or a.get("like_date", "") == today:
        return "您今日已经点过赞，明天再来~"
    a.set("like_date", today)
    ST.recall_set(gkey, today)
    n = cfgi("点赞配置", "点赞数", 5)
    try:
        n = max(1, min(int(n), 10))  # OneBot send_like 单次上限 10
    except Exception:
        n = 5
    cur_like = a.int("like_count")
    a.set("like_count", str(cur_like + n))
    ST.acct_save(gid, qq)
    text = f"成功点赞{n}次"
    # 真实名片赞走平台动作（mute/kick 同机制）；失败/无适配器时降级只保留虚拟计数
    try:
        return "__XB_PLATFORM__|like|%s|%d__TEXT__%s" % (qq, n, text)
    except Exception:
        return text


def cmd_rank(gid, kind, st):
    """排行榜: 财富=现金+存款"""
    if kind == "cash":
        return _rank_by(gid, lambda g, q: ST.coins_get(g, q) + ST.acct(g, q).int("deposit"), "财富")
    if kind == "sign":
        return _rank_by(gid, lambda g, q: ST.acct(g, q).int("sign_count"), "签到")
    if kind == "charm":
        return _rank_by(gid, lambda g, q: ST.acct(g, q).int("charm"), "魅力")
    if kind == "talk":
        return _rank_by(gid, lambda g, q: ST.acct(g, q).int("发言数"), "发言")
    return "未知排行类型"


def _rank_name(SL, gid, q):
    """排行昵称链（只读本群，绝不串群）：分群昵称→本群卡片→群档案→账户名"""
    try:
        if SL is not None:
            nm = SL.display_name(gid, q, "")
            if nm:
                return nm
            try:
                st = SL.state(gid)
                if st.has_section(q):
                    return st[q].get("name", "") or ""
            except Exception:
                pass
    except Exception:
        pass
    try:
        return ST.acct(gid, q).get("name", "") or ""
    except Exception:
        return ""


def _render_rank(lst, name, gid, topn=10):
    """排行渲染单源（快/慢两路径共用）：昵称＋单位 emoji，防 QQ 与数值粘连误读"""
    try:
        from . import slave as SL
    except Exception:
        try:
            import slave as SL
        except Exception:
            SL = None
    out = [f"【{name}排行榜】"]
    for i, (v, q) in enumerate(lst[:topn], 1):
        nm = _rank_name(SL, gid, q)
        display = f"{nm}({q})" if nm else q
        # 加单位/emoji 隔开，避免 QQ 与数值连在一起像两个 QQ
        if name == "财富":
            out.append(f"{i}. {display}  💰 {ST.fmt_coins(v)} {ST.coin_name()}")
        elif name == "签到":
            out.append(f"{i}. {display}  📅 {v} 次")
        elif name == "魅力":
            out.append(f"{i}. {display}  💄 {v} 点")
        elif name == "发言":
            out.append(f"{i}. {display}  💬 {v} 条")
        else:
            out.append(f"{i}. {display}  ━ {v}")
    return "\r\n".join(out)


def _rank_by(gid, fn, name, topn=10):
    """排行来源: 统一委托 store.rank_batch 去重，行数 40→12"""
    field_map = {"财富": "cash", "签到": "sign", "魅力": "charm"}
    fld = field_map.get(name)
    if fld and hasattr(ST, "rank_batch"):
        try:
            lst = ST.rank_batch(gid, fld, topn=500)[:topn]
            return _render_rank(lst, name, gid, topn)
        except Exception:
            pass
    lst = []
    try:
        if ST._DB is not None and name in ("财富", "签到", "魅力", "发言"):
            import json as _js
            with ST._LOCK:
                wallet_rows = ST._DB.execute("SELECT qq, money FROM wallet WHERE gid=?", (int(gid),)).fetchall()
                acct_rows = ST._DB.execute("SELECT qq, data FROM accounts WHERE gid=?", (int(gid),)).fetchall()
            wallet_map = {str(qq): int(money or 0) for qq, money in wallet_rows}
            acct_data = {}
            for qq, data in acct_rows:
                try:
                    kv = _js.loads(data) if data else {}
                except Exception:
                    kv = {}
                acct_data[str(qq)] = kv
            qqs_set = set(wallet_map.keys()) | set(acct_data.keys())
            if not qqs_set:
                lst = []
            else:
                for q in qqs_set:
                    kv = acct_data.get(q, {})
                    if name == "财富":
                        v = wallet_map.get(q, 0) + int(float(kv.get("deposit", kv.get("cunkuan", 0)) or 0))
                    elif name == "签到":
                        v = int(float(kv.get("sign_count", 0) or 0))
                    elif name == "魅力":
                        v = max(0, min(500, int(float(kv.get("charm", kv.get("meili", 0)) or 0))))
                    elif name == "发言":
                        v = int(float(kv.get("message_count", kv.get("发言数", 0)) or 0))
                    else:
                        v = fn(gid, q)
                    lst.append((v, q))
            lst.sort(reverse=True)
        else:
            with ST._LOCK:
                rows = ST._DB.execute("SELECT DISTINCT qq FROM accounts WHERE gid=?",
                                      (int(gid),)).fetchall() if ST._DB else []
            qqs = [str(r[0]) for r in rows]
            for q in qqs:
                lst.append((fn(gid, q), q))
            lst.sort(reverse=True)
    except Exception:
        # 回退旧逻辑
        try:
            with ST._LOCK:
                rows = ST._DB.execute("SELECT DISTINCT qq FROM accounts WHERE gid=?",
                                      (int(gid),)).fetchall() if ST._DB else []
            qqs = [str(r[0]) for r in rows]
            for q in qqs:
                lst.append((fn(gid, q), q))
            lst.sort(reverse=True)
        except Exception:
            lst = []
    return _render_rank(lst, name, gid, topn)


_MENU = (
    "❤️ 签到系统\r\n"
    "━━━━━━━━━━━━━━\r\n"
    "📅 签到　　　　　🎁 抽奖 数量\r\n"
    "📅 每日打卡　　　👍 赞我\r\n"
    "💪 购买体力 数量　购买魅力 数量\r\n"
    "🎁 领取新手礼包　👤 我的信息\r\n"
    "📋 打卡\r\n"
    "🏆 个人排行　财富榜　签到榜　魅力榜\r\n"
    "━━━━━━━━━━━━━━\r\n"
    "💡 发送对应指令即可游玩"
)


def cmd_mine_rank(gid, qq):
    """个人排行: 单次批量取所有人4项，避免4×N+1"""
    try:
        import json as _js2
        with ST._LOCK:
            wallet_rows = ST._DB.execute("SELECT qq, money FROM wallet WHERE gid=?", (int(gid),)).fetchall() if ST._DB else []
            acct_rows = ST._DB.execute("SELECT qq, data FROM accounts WHERE gid=?", (int(gid),)).fetchall() if ST._DB else []
        wallet_map = {str(q): int(m or 0) for q, m in wallet_rows}
        acct_data = {}
        for q_, data in acct_rows:
            try:
                kv = _js2.loads(data) if data else {}
            except Exception:
                kv = {}
            acct_data[str(q_)] = kv
        qqs_set = set(wallet_map.keys()) | set(acct_data.keys())
        if str(qq) not in qqs_set:
            qqs_set.add(str(qq))
        qqs = list(qqs_set)
        # 批量算三列
        vals_cash = {}
        vals_sign = {}
        vals_charm = {}
        for q in qqs:
            kv = acct_data.get(q, {})
            vals_cash[q] = wallet_map.get(q, 0) + int(float(kv.get("deposit", kv.get("cunkuan", 0)) or 0))
            vals_sign[q] = int(float(kv.get("sign_count", 0) or 0))
            vals_charm[q] = max(0, min(800, int(float(kv.get("charm", kv.get("meili", 0)) or 0))))
        def _pos(d):
            sorted_q = sorted(d.items(), key=lambda x: -x[1])
            for i, (q_, v) in enumerate(sorted_q, 1):
                if q_ == str(qq):
                    return i, int(v)
            return len(sorted_q), 0
        rc, vc = _pos(vals_cash)
        rs, vs = _pos(vals_sign)
        rm, vm = _pos(vals_charm)
        return ("📊 个人排行\r\n"
                f"财富：第{rc}名（{ST.fmt_coins(vc)}{ST.coin_name()}）\r\n"
                f"签到：第{rs}名（{vs}次）\r\n"
                f"魅力：第{rm}名（{vm}）")
    except Exception:
        # 回退旧逻辑
        def _rank_pos(keyfn, order="desc"):
            with ST._LOCK:
                rows = ST._DB.execute("SELECT DISTINCT qq FROM accounts WHERE gid=?",
                                      (int(gid),)).fetchall() if ST._DB else []
            qqs = [str(r[0]) for r in rows]
            if str(qq) not in qqs:
                qqs.append(str(qq))
            lst = [keyfn(gid, q) for q in qqs]
            paired = sorted(zip(lst, qqs), key=lambda x: -x[0])
            for i, (v, q) in enumerate(paired, 1):
                if q == str(qq):
                    return i, int(v), v
            return len(paired), 0, 0
        def kc(g, q): return ST.coins_get(g, q) + ST.acct(g, q).int("deposit")
        def ks(g, q): return ST.acct(g, q).int("sign_count")
        def km(g, q): return ST.acct(g, q).int("charm")
        rc, vc, _ = _rank_pos(kc)
        rs, vs, _ = _rank_pos(ks)
        rm, vm, _ = _rank_pos(km)
        return ("📊 个人排行\r\n"
                f"财富：第{rc}名（{ST.fmt_coins(vc)}{ST.coin_name()}）\r\n"
                f"签到：第{rs}名（{vs}次）\r\n"
                f"魅力：第{rm}名（{vm}）")


# ---- 统一入口 ----
def handle(gid, qq, raw):
    import re as _r
    text = (raw or "").strip()
    if not text:
        return None
    if text in ST.wake("签到系统", "签到系统"):
        return _MENU
    # 每日打卡：精确指令，无模糊词（前后空格已 strip，禁 startswith/禁带参）
    if text == "每日打卡":
        return cmd_daily_checkin(gid, qq)
    # 排行优先于签到，避免 “签到榜” 误判为签到
    if text in ("个人财富榜", "财富榜"):
        return cmd_rank(gid, "cash", None)
    if text == "签到榜":
        return cmd_rank(gid, "sign", None)
    if text in ("魅力排行榜", "魅力榜"):
        return cmd_rank(gid, "charm", None)
    if text in ("签到", "打卡"):
        return cmd_sign(gid, qq)
    if text in ("个人排行", "我的排行"):
        return cmd_mine_rank(gid, qq)
    if text.startswith("抽奖"):
        if text == "抽奖":
            return cmd_draw(gid, qq, 1)
        m = _r.fullmatch(r"抽奖\s*\+?\s*(\d+)", text)
        if m:
            return cmd_draw(gid, qq, int(m.group(1)))
        return None
    if text in ("领取新手礼包", "领取新人礼包"):
        return cmd_newbie(gid, qq)
    if text == "赞我":
        return cmd_like(gid, qq)
    if text.startswith("购买体力"):
        if text == "购买体力":
            return cmd_gift(gid, qq, "stamina", 1)
        m = _r.fullmatch(r"购买体力\s*\+?\s*(\d+)", text)
        if m:
            return cmd_gift(gid, qq, "stamina", int(m.group(1)))
        return None
    if text.startswith("购买魅力"):
        if text == "购买魅力":
            return cmd_gift(gid, qq, "charm", 1)
        m = _r.fullmatch(r"购买魅力\s*\+?\s*(\d+)", text)
        if m:
            return cmd_gift(gid, qq, "charm", int(m.group(1)))
        return None
    return None


# 显式指令注册表（V8 起为唯一词表来源：engine_commands 与 _collect_commands 同读此表）。
# 与 handle 内分支逐字对应，增删指令时两处同改。
COMMANDS = (
    "个人财富榜", "财富榜",
    "签到榜",
    "魅力排行榜", "魅力榜",
    "每日打卡",
    "签到", "打卡",
    "个人排行", "我的排行",
    "抽奖",
    "领取新手礼包", "领取新人礼包",
    "赞我", "购买体力", "购买魅力",
)
