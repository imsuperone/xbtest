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
    from .config.sign import DEFAULTS as _SIGN_DEFAULTS, CHAIN_CAP
except ImportError:
    from games.config.sign import DEFAULTS as _SIGN_DEFAULTS, CHAIN_CAP  # type: ignore


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


def cmd_sign(gid, qq):
    """签到: 基础奖励 + 连签加成 + 身价/资产联动(财富=现金+存款)"""
    a = _acct(gid, qq)
    today = _today().isoformat()
    if a.get("sign_date") == today:
        return cfg("签到配置", "重复签到文案",
                      "亲，您今天已经签到过了，请明天继续吧！")
    total = int(float(a.get("sign_count", "0")))
    chain = int(float(a.get("consecutive_days", "0")))
    prev = str(a.get("last_sign_date", ""))
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
    tili = _rng("体力", "stamina", 50, 100)
    meili = _rng("魅力", "charm", 15, 30)
    juan = _rng("奖券", "lottery_tickets", 3, 8)
    bonus = cfgi("签到配置", "连签加成", 100)
    chain_bonus = bonus * min(chain, CHAIN_CAP)
    total += 1
    # 预取当前额外属性旧值，用于一次事务内计算新值（避免 3次 acct_add+acct_save 的 3锁3提交）
    cur_stam = int(float(a.get("stamina", "0") or 0))
    cur_charm = int(float(a.get("charm", "0") or 0))
    cur_juan = int(float(a.get("lottery_tickets", "0") or 0))
    # 单事务：钱包 delta + 账户批量字段（原5次提交→1次，持锁 1次）
    # txn 失败返 None（内部已回滚）：走旧路径补，而非当成功
    if ST.txn_coins_acct(gid, qq, base + chain_bonus, {
        "sign_count": str(total),
        "total_sign_days": str(total),
        "consecutive_days": str(chain),
        "sign_date": today,
        "last_sign_date": today,
        "account_created": a.get("account_created") or dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "stamina": str(cur_stam + tili),
        "charm": str(cur_charm + meili),
        "lottery_tickets": str(cur_juan + juan),
    }) is None:
        # 回退旧路径（兼容）
        a.set("sign_count", str(total))
        a.set("total_sign_days", str(total))
        a.set("consecutive_days", str(chain))
        a.set("sign_date", today)
        a.set("last_sign_date", today)
        if not a.get("account_created"):
            a.set("account_created", dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        ST.coins_add(gid, qq, base + chain_bonus)
        ST.acct_add(gid, qq, "stamina", tili)
        ST.acct_add(gid, qq, "charm", meili)
        ST.acct_add(gid, qq, "lottery_tickets", juan)
        ST.acct_save(gid, qq)
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
    return ("🏅 恭喜你签到成功！\r\n"
            "　奖励详情：\r\n"
            f"　　　💵 {coin} +{base}\r\n"
            f"　　　⚡ 体力 +{tili}\r\n"
            f"　　　💄 魅力 +{meili}\r\n"
            f"　　　🎫 奖券 +{juan}\r\n"
            f"　　　🔥 第{days_cn(chain)}天连签 +{chain_bonus}\r\n"
            f"当前{coin}：{ST.coins_get(gid, qq)}\r\n"
            f"您是今天第{order}个签到者！")


def days_cn(chain):
    try:
        c = int(chain)
    except Exception:
        c = 1
    if 1 <= c <= 7:
        return DAYS_CN[c]
    return str(c)


def cmd_personal(gid, qq):
    """个人信息: 优先委派 slave 引擎返回全量档案；兜底返回美化版个人档案"""
    try:
        from . import slave as _sl
        return _sl.cmd_myinfo(gid, qq, _sl.state(gid))
    except Exception:
        pass
    try:
        import slave as _sl2
        return _sl2.cmd_myinfo(gid, qq, _sl2.state(gid))
    except Exception:
        pass
    a = _acct(gid, qq)
    money = ST.coins_get(gid, qq)
    dep = a.int("deposit")
    tili = a.int("stamina")
    meili = a.int("charm")
    jq = a.int("lottery_tickets")
    sign_c = a.int("sign_count")
    coin = ST.coin_name()
    disp = str(qq)
    try:
        from . import slave as _sl_name
        try:
            disp = _sl_name.get_note_name(gid, str(qq)) or _sl_name.fetch_card(gid, str(qq)) or str(qq)
        except Exception:
            disp = _sl_name.NOTE_NAMES.get(str(qq), str(qq)) or str(qq)
    except Exception:
        pass
    lines = [
        f"📋【{disp}】的档案",
        f"💰资产：{money}{coin}｜🏦存款：{dep}｜💎身价：500",
        f"🔋体力：{tili}｜💄魅力：{meili}｜🎫奖券：{jq}｜📖经验：0",
        f"👑主人：木有主人｜无人保护｜📅总签{sign_c}·连签{a.int('consecutive_days')}天",
        "⚔️武器：木有武器",
        "🎁宝物：木有宝物",
        "👥奴隶(0/2)：木有奴隶",
    ]
    return "\r\n".join(lines)


def cmd_draw(gid, qq, amount=1):
    """抽奖: 消耗奖券(默认1张), 支持多连抽（如抽奖52），每抽独立判定，保底5连不中必中；不限制每日次数"""
    if amount <= 0:
        amount = 1
    if amount > 999:
        return "单次抽奖上限999张！"
    a = _acct(gid, qq)
    with ST._LOCK:
        tickets = a.int("lottery_tickets")
        if tickets < amount:
            return f"奖券不足，需{amount}张，当前{tickets}张！"
        # 扣除（持锁：防同用户并发双花）
        a.set("lottery_tickets", str(tickets - amount))
    # 多连抽循环
    wins = 0
    total_coin = 0
    total_tili = 0
    total_meili = 0
    lose_streak = int(a.get("lottery_lose_streak", "0") or "0")
    out_lines = []
    for i in range(amount):
        must_win = lose_streak >= 5
        win = must_win or (random.randint(1, 100) <= cfgi("抽奖配置", "中奖率", 70))
        if win:
            pool = [
                (ST.coin_name(), "coin", cfgi("抽奖配置", "现金奖", 2000)),
                ("体力", "stamina", cfgi("抽奖配置", "体力奖", 60)),
                ("魅力", "charm", cfgi("抽奖配置", "魅力奖", 40)),
            ]
            name_cn, kind, val = random.choice(pool)
            if kind == "coin":
                ST.coins_add(gid, qq, val)
                total_coin += val
            elif kind == "stamina":
                ST.acct_add(gid, qq, "stamina", val)
                total_tili += val
            else:
                ST.acct_add(gid, qq, "charm", val)
                total_meili += val
            lose_streak = 0
            wins += 1
            if amount == 1:
                a.set("lottery_lose_streak", "0")
                ST.acct_save(gid, qq)
                return f"恭喜，抽奖成功！获得{name_cn}+{val}"
            else:
                out_lines.append(f"第{i+1}抽：恭喜 获得{name_cn}+{val}")
        else:
            lose_streak += 1
            if amount == 1:
                a.set("lottery_lose_streak", str(lose_streak))
                ST.acct_save(gid, qq)
                return "很遗憾，本次未中奖，再接再厉！"
            else:
                out_lines.append(f"第{i+1}抽：很遗憾 未中奖")
    a.set("lottery_lose_streak", str(lose_streak))
    ST.acct_save(gid, qq)
    # 多连抽汇总
    summary = f"抽奖{amount}连抽完成：中奖{wins}/{amount}"
    if total_coin:
        summary += f" {ST.coin_name()}+{total_coin}"
    if total_tili:
        summary += f" 体力+{total_tili}"
    if total_meili:
        summary += f" 魅力+{total_meili}"
    if wins == 0:
        summary += "，很遗憾全未中，下次保底必中！"
    return summary + ("\r\n" + "\r\n".join(out_lines) if amount <= 10 else "")


def cmd_gift(gid, qq, kind, amount):
    """购买体力/魅力(单次上限999, 对齐原版; 价格从 签到配置 读取) 支持存款抵扣（需求39）"""
    kind_cn = "体力" if kind == "stamina" else "魅力"
    if amount <= 0:
        amount = 1
    if amount > 999:
        return f"亲，{kind_cn}单次购买数量上限为999！"
    key = "stamina" if kind == "stamina" else "charm"
    price = cfgi("签到配置", "体力价格" if kind == "stamina" else "魅力价格", 30 if kind == "stamina" else 3)
    total = price * amount
    have = ST.coins_get(gid, qq)
    dep = ST.acct(gid, qq).int("deposit")
    if have < total:
        need = total - have
        if dep >= need:
            if have:
                ST.coins_add(gid, qq, -have)
            ST.acct_add(gid, qq, "deposit", -need)
            total_paid = f"{have}{ST.coin_name()}+存款{need}"
        else:
            return f"亲，您的账户{ST.coin_name()}不足，无法购买！需要{total}{ST.coin_name()}（现金{have}+存款{dep}）"
    else:
        ST.coins_add(gid, qq, -total)
        total_paid = f"{total}{ST.coin_name()}"
    cur = ST.acct_add(gid, qq, key, amount)
    return f"恭喜您花费{total_paid}，购买了{amount}点{kind_cn}，您的{kind_cn}提升到{cur}点！"


def cmd_newbie(gid, qq):
    a = _acct(gid, qq)
    if a.get("novice_gift", "") == "1":
        return "亲，您已经领取过新手礼包了，无法再次领取！"
    money = cfgi("新手配置", "现金", cfgi("新手配置", "新手金币", cfgi("新手配置", "money", 10000)))
    tili = cfgi("新手配置", "体力", cfgi("新手配置", "新手体力", cfgi("新手配置", "stamina", 300)))
    meili = cfgi("新手配置", "魅力", cfgi("新手配置", "新手魅力", cfgi("新手配置", "charm", 100)))
    jq = cfgi("新手配置", "奖券", cfgi("新手配置", "新手奖券", cfgi("新手配置", "lottery_tickets", 15)))
    # 单事务原子领取：钱包+账户同锁一次提交，避免签到并发时 database is locked
    # txn 失败返 None（内部已回滚）：走单项补发，而非当成功
    cur_stam = int(float(a.get("stamina", "0") or 0))
    cur_charm = int(float(a.get("charm", "0") or 0))
    cur_juan = int(float(a.get("lottery_tickets", "0") or 0))
    if ST.txn_coins_acct(gid, qq, money, {
        "novice_gift": "1",
        "stamina": str(cur_stam + tili),
        "charm": str(cur_charm + meili),
        "lottery_tickets": str(cur_juan + jq),
    }) is None:
        a.set("novice_gift", "1")
        ST.coins_add(gid, qq, money)
        ST.acct_add(gid, qq, "stamina", tili)
        ST.acct_add(gid, qq, "charm", meili)
        ST.acct_add(gid, qq, "lottery_tickets", jq)
        ST.acct_save(gid, qq)
    else:
        # txn 内已覆盖 novice 标记，刷新内存避免旧对象覆盖
        try:
            a.set("novice_gift", "1")
            a.set("stamina", str(cur_stam + tili))
            a.set("charm", str(cur_charm + meili))
            a.set("lottery_tickets", str(cur_juan + jq))
            a.dirty = False
        except Exception:
            pass
    return (f"恭喜您获得新手礼包一份！\r\n"
            f"{ST.coin_name()}+{money}\r\n体力+{tili}\r\n魅力+{meili}\r\n奖券+{jq}")


def cmd_like(gid, qq):
    a = _acct(gid, qq)
    today = _today().isoformat()
    if a.get("like_date", "") == today:
        return "您今日已经点过赞，明天再来~"
    a.set("like_date", today)
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
    if kind == "stamina":
        return _rank_by(gid, lambda g, q: ST.acct(g, q).int("stamina"), "体力")
    if kind == "charm":
        return _rank_by(gid, lambda g, q: ST.acct(g, q).int("charm"), "魅力")
    if kind == "talk":
        return _rank_by(gid, lambda g, q: ST.acct(g, q).int("发言数"), "发言")
    return "未知排行类型"


def _rank_by(gid, fn, name, topn=10):
    """排行来源: 统一委托 store.rank_batch 去重，行数 40→12"""
    field_map = {"财富": "cash", "签到": "sign", "体力": "stamina", "魅力": "charm"}
    fld = field_map.get(name)
    if fld and hasattr(ST, "rank_batch"):
        try:
            lst = ST.rank_batch(gid, fld, topn=500)[:topn]
            # 快速渲染
            try:
                from . import slave as SL
            except Exception:
                try:
                    import slave as SL
                except Exception:
                    SL = None
            out = [f"【{name}排行榜】"]
            for i, (v, q) in enumerate(lst[:topn], 1):
                nm = ""
                if SL is not None:
                    try:
                        try:
                            nm = SL.get_note_name(gid, q) or "" if hasattr(SL, "get_note_name") else ""
                        except Exception:
                            nm = ""
                        if not nm:
                            nm = SL.fetch_card(gid, q) or ""
                        if not nm:
                            st = SL.state(gid)
                            if st.has_section(q):
                                nm = st[q].get("name", "") or ""
                    except Exception:
                        pass
                if not nm:
                    try:
                        nm = ST.acct(gid, q).get("name", "") or ""
                    except Exception:
                        pass
                display = f"{nm}({q})" if nm else q
                if name == "财富":
                    out.append(f"{i}. {display}  💰 {v} {ST.coin_name()}")
                elif name == "签到":
                    out.append(f"{i}. {display}  📅 {v} 次")
                elif name == "体力":
                    out.append(f"{i}. {display}  ⚡ {v} 点")
                elif name == "魅力":
                    out.append(f"{i}. {display}  💄 {v} 点")
                else:
                    out.append(f"{i}. {display}  ━ {v}")
            return "\r\n".join(out)
        except Exception:
            pass
    lst = []
    try:
        if ST._DB is not None and name in ("财富", "签到", "体力", "魅力", "发言"):
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
                    elif name == "体力":
                        v = int(float(kv.get("stamina", 0) or 0))
                    elif name == "魅力":
                        v = int(float(kv.get("charm", 0) or 0))
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
    # 尝试获取昵称
    try:
        from . import slave as SL
    except Exception:
        try:
            import slave as SL
        except Exception:
            SL = None
    out = [f"【{name}排行榜】"]
    for i, (v, q) in enumerate(lst[:topn], 1):
        nm = ""
        if SL is not None:
            try:
                try:
                    nm = SL.get_note_name(gid, q) or "" if hasattr(SL, "get_note_name") else ""
                except Exception:
                    nm = ""
                if not nm:
                    nm = SL.fetch_card(gid, q) or ""
                if not nm:
                    st = SL.state(gid)
                    if st.has_section(q):
                        nm = st[q].get("name", "") or ""
            except Exception:
                pass
        if not nm:
            try:
                nm = ST.acct(gid, q).get("name", "") or ""
            except Exception:
                pass
        display = f"{nm}({q})" if nm else q
        # 加单位/emoji 隔开，避免 QQ 与数值连在一起像两个 QQ
        if name == "财富":
            out.append(f"{i}. {display}  💰 {v} {ST.coin_name()}")
        elif name == "签到":
            out.append(f"{i}. {display}  📅 {v} 次")
        elif name == "体力":
            out.append(f"{i}. {display}  ⚡ {v} 点")
        elif name == "魅力":
            out.append(f"{i}. {display}  💄 {v} 点")
        elif name == "发言":
            out.append(f"{i}. {display}  💬 {v} 条")
        else:
            out.append(f"{i}. {display}  ━ {v}")
    return "\r\n".join(out)


_MENU = (
    "❤️ 签到系统\r\n"
    "━━━━━━━━━━━━━━━━\r\n"
    "📅 签到　　　　　🎁 抽奖 数量\r\n"
    "💪 购买体力 数量　购买魅力 数量\r\n"
    "🎁 领取新手礼包　👤 我的信息\r\n"
    "👍 赞我　　📋 打卡\r\n"
    "🏆 个人排行　财富榜　签到榜　体力榜　魅力榜\r\n"
    "━━━━━━━━━━━━━━━━\r\n"
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
        # 批量算四列
        vals_cash = {}
        vals_sign = {}
        vals_stam = {}
        vals_charm = {}
        for q in qqs:
            kv = acct_data.get(q, {})
            vals_cash[q] = wallet_map.get(q, 0) + int(float(kv.get("deposit", kv.get("cunkuan", 0)) or 0))
            vals_sign[q] = int(float(kv.get("sign_count", 0) or 0))
            vals_stam[q] = int(float(kv.get("stamina", 0) or 0))
            vals_charm[q] = int(float(kv.get("charm", 0) or 0))
        def _pos(d):
            sorted_q = sorted(d.items(), key=lambda x: -x[1])
            for i, (q_, v) in enumerate(sorted_q, 1):
                if q_ == str(qq):
                    return i, int(v)
            return len(sorted_q), 0
        rc, vc = _pos(vals_cash)
        rs, vs = _pos(vals_sign)
        rt, vt = _pos(vals_stam)
        rm, vm = _pos(vals_charm)
        return ("📊 个人排行\r\n"
                f"财富：第{rc}名（{vc}{ST.coin_name()}）\r\n"
                f"签到：第{rs}名（{vs}次）\r\n"
                f"体力：第{rt}名（{vt}）\r\n"
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
        def kt(g, q): return ST.acct(g, q).int("stamina")
        def km(g, q): return ST.acct(g, q).int("charm")
        rc, vc, _ = _rank_pos(kc)
        rs, vs, _ = _rank_pos(ks)
        rt, vt, _ = _rank_pos(kt)
        rm, vm, _ = _rank_pos(km)
        return ("📊 个人排行\r\n"
                f"财富：第{rc}名（{vc}{ST.coin_name()}）\r\n"
                f"签到：第{rs}名（{vs}次）\r\n"
                f"体力：第{rt}名（{vt}）\r\n"
                f"魅力：第{rm}名（{vm}）")


# ---- 统一入口 ----
def handle(gid, qq, raw):
    import re as _r
    text = (raw or "").strip()
    if not text:
        return None
    if text in ST.wake("签到系统", "签到系统"):
        return _MENU
    # 排行优先于签到，避免 “签到榜” 误判为签到
    if text.startswith("个人财富榜") or text.startswith("财富榜"):
        return cmd_rank(gid, "cash", None)
    if text.startswith("签到排行榜") or text.startswith("签到榜"):
        return cmd_rank(gid, "sign", None)
    if text.startswith("体力排行榜") or text.startswith("体力榜"):
        return cmd_rank(gid, "stamina", None)
    if text.startswith("魅力排行榜") or text.startswith("魅力榜"):
        return cmd_rank(gid, "charm", None)
    if text == "签到" or text.startswith("签到 ") or text == "打卡" or text.startswith("打卡 "):
        return cmd_sign(gid, qq)
    if text == "我的信息" or text.startswith("我的信息 "):
        # 支持 我的信息 @QQ 查询他人（走 slave 档案更全，故此处仅返回自身；跨引擎查询由 slave 处理）
        return cmd_personal(gid, qq)
    if text in ("个人排行", "我的排行"):
        return cmd_mine_rank(gid, qq)
    if text.startswith("抽奖"):
        m = _r.search(r"(\d+)", text)
        return cmd_draw(gid, qq, int(m.group(1)) if m else 1)
    if text.startswith("领取新手礼包") or text.startswith("领取新人礼包"):
        return cmd_newbie(gid, qq)
    if text == "赞我" or text.startswith("赞我 "):
        return cmd_like(gid, qq)
    if text.startswith("购买体力"):
        m = _r.search(r"(\d+)", text)
        return cmd_gift(gid, qq, "stamina", int(m.group(1)) if m else 1)
    if text.startswith("购买魅力"):
        m = _r.search(r"(\d+)", text)
        return cmd_gift(gid, qq, "charm", int(m.group(1)) if m else 1)
    return None
