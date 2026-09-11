# -*- coding: utf-8 -*-
"""帮派系统 - 对齐 open.xb 原版帮派指令
存储: 成员 acct"帮派"={name,pos,gong,build}; 帮派列表/排行由各成员帮派字段聚合
指令: 创建/加入/邀请/退出/我的帮派/成员列表/贡献/我的贡献/我的修筑/领取福利/帮派管理(宣言/护法/移出/出让/升级/解散/删除)/发起帮战/帮派排行
"""
import json
import re
import time

try:
    from ..core import storage as ST
except ImportError:
    try:
        from . import storage as ST
    except ImportError:
        from core import storage as ST

# 缓存：gid -> {gname -> [ (qq,g) ] }  15秒 TTL，避免每次全表扫
# （成员变更经 _save_member 主动失效；精灵战力本就按 TTL 快照，15 秒 stale 可接受）
_GUILD_MEMBERS_CACHE = {}
_GUILD_MEMBERS_TS = {}
_GUILD_TTL = 15.0

def _invalidate_guild_cache(gid):
    try:
        gid = str(gid)
        _GUILD_MEMBERS_CACHE.pop(gid, None)
        _GUILD_MEMBERS_TS.pop(gid, None)
    except Exception:
        pass


_cfg, _cfgi0 = ST.cfg_scope("帮派配置")
try:
    from .config.guild import DEFAULTS as _GUILD_DEFAULTS, CONTRIBUTE_DIV, WELFARE_PER_GONG
except ImportError:
    from games.config.guild import DEFAULTS as _GUILD_DEFAULTS, CONTRIBUTE_DIV, WELFARE_PER_GONG  # type: ignore


def _cfgi(key, default=0):
    # 默认值单源：games/config/guild.py DEFAULTS 表命中即用表值
    try:
        if key in _GUILD_DEFAULTS:
            default = _GUILD_DEFAULTS[key]
    except Exception:
        pass
    return _cfgi0(key, default)


def _acct(gid, qq):
    return ST.acct(gid, qq)


def _my(gid, qq):
    a = _acct(gid, qq)
    try:
        return json.loads(a.get("guild", "{}") or "{}")
    except Exception:
        return {}


def _save_member(gid, qq, g):
    _acct(gid, qq).set("guild", json.dumps(g, ensure_ascii=False))
    ST.acct_save(gid, qq)
    _invalidate_guild_cache(gid)


def _members(gid, gname):
    """返回 群内加入该帮派的 qq 列表(含各自 帮派字段) — 15秒缓存避免全表扫"""
    gid_s = str(gid)
    now = time.time()
    # 尝试缓存：gid -> 全量 (qq, guild) 列表
    cached = _GUILD_MEMBERS_CACHE.get(gid_s)
    ts = _GUILD_MEMBERS_TS.get(gid_s, 0)
    if cached is not None and now - ts < _GUILD_TTL:
        # 从缓存过滤
        return [(qq, g) for qq, g in cached if g.get("name") == gname]
    with ST._LOCK:
        rows = ST._DB.execute("SELECT qq, data FROM accounts WHERE gid=?",
                              (int(gid),)).fetchall() if ST._DB else []
    all_members = []
    for qqdb, data in rows:
        try:
            raw = json.loads(data)
            g = json.loads(raw.get("guild", "{}") or "{}")
        except Exception:
            continue
        if g.get("name"):
            all_members.append((str(qqdb), g))
    # 写入缓存
    _GUILD_MEMBERS_CACHE[gid_s] = all_members
    _GUILD_MEMBERS_TS[gid_s] = now
    out = [(qq, g) for qq, g in all_members if g.get("name") == gname]
    return out


def _guild_info(gid, gname):
    mem = _members(gid, gname)
    if not mem:
        return None
    owner = next((q for q, g in mem if g.get("pos") == "帮主"), None)
    gong = sum(int(g.get("gong", 0) or 0) for _, g in mem)
    build = sum(int(g.get("build", 0) or 0) for _, g in mem)
    # 战力=帮主/护法出战精灵总战力之和(简化: 帮主+护法的 精灵战力)
    fight = sum(_spirit_power(gid, q) for (q, g) in mem if g.get("pos") in ("帮主", "护法"))
    # 等级: 帮主已升等级优先, 否则按帮贡推算
    owner_g = _my(gid, owner) if owner else {}
    lv = int(owner_g.get("lv", 0) or 0)
    if lv < 1:
        lv = 1 + (gong // max(1, _cfgi("升级需要帮贡", 20000)))
    return {"name": gname, "owner": owner, "count": len(mem), "gong": gong,
            "build": build, "fight": fight, "level": lv,
            "intro": _my(gid, owner).get("intro", "") if owner else ""}


def _spirit_power(gid, qq):
    try:
        a = _acct(gid, qq)
        sp = json.loads(a.get("spirits", "{}") or "{}")
        act = sp.get("active")
        for it in sp.get("list", []):
            if it.get("name") == act:
                return int(it.get("level", 1)) * (
                    int(it.get("hp", 0)) + int(it.get("atk", 0)) +
                    int(it.get("def", 0)) + int(it.get("spa", 0)) + int(it.get("spd", 0))) // 5
    except Exception:
        pass
    return 0


MENU = (
    "🏰 帮派系统\r\n"
    "━━━━━━━━━━━━━━\r\n"
    "📇 帮派列表　　🏆 帮派排行　　📋 我的帮派\r\n"
    "🛠️ 创建帮派 名称　🤝 加入帮派 名称\r\n"
    "📨 帮派邀请 对方QQ　👥 成员列表\r\n"
    "💸 帮派贡献 金额　📈 我的贡献　🧱 我的修筑\r\n"
    "🎁 领取帮派福利　🚪 退出帮派\r\n"
    "🧱 修筑城墙 数量\r\n"
    "⚔️ 发起帮战 帮派名\r\n"
    "🔧 管理帮派(帮主/护法)：修改宣言/添加护法/取消护法/移出帮派/出让帮派/帮派升级/解散帮派\r\n"
    "━━━━━━━━━━━━━━\r\n"
    "💡 发送对应指令即可游玩"
)


def _need_switch(gid):
    return _cfg("开关", "真") != "真"


def cmd_list(gid, qq):
    if ST._DB is None:
        return "暂无帮派数据。"
    # 批量单次JOIN+缓存复用，避免 DISTINCT+N次 _my(acct) N+1
    gid_s = str(gid)
    now = time.time()
    cached = _GUILD_MEMBERS_CACHE.get(gid_s)
    ts = _GUILD_MEMBERS_TS.get(gid_s, 0)
    if cached is not None and now - ts < _GUILD_TTL:
        all_members = cached
    else:
        with ST._LOCK:
            rows = ST._DB.execute("SELECT qq, data FROM accounts WHERE gid=?", (int(gid),)).fetchall() if ST._DB else []
        all_members = []
        for qqdb, data in rows:
            try:
                raw = json.loads(data)
                g = json.loads(raw.get("guild", "{}") or "{}")
            except Exception:
                continue
            if g.get("name"):
                all_members.append((str(qqdb), g))
        _GUILD_MEMBERS_CACHE[gid_s] = all_members
        _GUILD_MEMBERS_TS[gid_s] = now
    gnames = {}
    for q, g in all_members:
        gnames.setdefault(g["name"], set()).add(q)
    if not gnames:
        return "本群还没有帮派，发送【创建帮派 名称】创建第一个帮派吧！"
    lines = ["📇 帮派列表"]
    for name in gnames:
        info = _guild_info(gid, name)
        lines.append(f"{name}　人数:{info['count'] if info else 0}　等级:{info['level'] if info else 1}")
    return "\r\n".join(lines)


def cmd_my(gid, qq):
    g = _my(gid, qq)
    if not g.get("name"):
        return "亲，您还没有加入任何帮派，发送【创建帮派 名称】或【加入帮派 名称】！"
    info = _guild_info(gid, g["name"])
    return (f"【{g['name']}】　职务:{g.get('pos','成员')}\r\n"
            f"宣言:{info['intro'] if info else '（空）'}\r\n"
            f"人数:{info['count'] if info else 0}　等级:{info['level'] if info else 1}\r\n"
            f"帮贡:{info['gong'] if info else 0}　修筑:{info['build'] if info else 0}　战力:{info['fight'] if info else 0}\r\n"
            f"我的贡献:{g.get('gong',0)}　我的修筑:{g.get('build',0)}")


def cmd_create(gid, qq, name):
    name = (name or "").strip()
    if not name:
        return "亲，创建帮派格式为【创建帮派 帮派名】，帮派名不能为空！"
    if len(name) > 12:
        return "亲，帮派名超长，请重新创建！"
    g = _my(gid, qq)
    if g.get("name"):
        return f"亲，您已经加入了帮派「{g['name']}」，如需创建帮派，请先退出此帮派！"
    if _guild_info(gid, name):
        return "亲，该帮派名称已被使用，请使用其他名称进行创建！"
    cost = _cfgi("创建消耗金钱", 20000)
    ctili = _cfgi("创建消耗体力", 50)
    need_meili = _cfgi("创建需要魅力", 100)
    if ST.coins_get(gid, qq) < cost:
        return f"亲，创建帮派需要{cost}{ST.coin_name()}，您的{ST.coin_name()}不足！"
    if _acct(gid, qq).int("stamina") < ctili:
        return f"亲，创建帮派需要消耗{ctili}点体力，您的体力不足！"
    if _acct(gid, qq).int("charm") < need_meili:
        return f"亲，创建帮派需要具备{need_meili}点魅力，您的魅力值不足！"
    ST.coins_add(gid, qq, -cost)
    ST.acct_add(gid, qq, "stamina", -ctili)
    _save_member(gid, qq, {"name": name, "pos": "帮主", "gong": 0, "build": 0, "intro": ""})
    return f"帮派「{name}」创建成功！您成为帮主！\r\n欢迎大家加入「{name}」！We Are 伐木累！"


def cmd_join(gid, qq, name):
    name = (name or "").strip()
    if not name:
        return "亲，加入帮派格式为【加入帮派 帮派名】！"
    g = _my(gid, qq)
    if g.get("name"):
        return f"亲，你已经加入了帮派「{g['name']}」，如需加入其他请先退出！"
    info = _guild_info(gid, name)
    if not info:
        return "亲，该帮派不存在，发送【帮派列表】查看本群帮派！"
    limit = _cfgi("人数上限", 30)
    if info["count"] >= limit:
        return "亲，该帮派人数已满，无法加入！"
    join_tili = _cfgi("加入消耗体力", 0)
    join_meili = _cfgi("加入需要魅力", 0)
    if _acct(gid, qq).int("stamina") < join_tili:
        return f"亲，加入帮派需要消耗{join_tili}点体力，您的体力不足！"
    if _acct(gid, qq).int("charm") < join_meili:
        return f"亲，加入帮派需要具备{join_meili}点魅力，您的魅力值不足！"
    if join_tili:
        ST.acct_add(gid, qq, "stamina", -join_tili)
    _save_member(gid, qq, {"name": name, "pos": "成员", "gong": 0, "build": 0})
    return f"欢迎加入「{name}」！"


def cmd_invite(gid, qq, target):
    raw = (target or "").strip()
    # 兼容 @QQ 与纯 QQ 号，文案仅 @QQ
    m = re.search(r"(\d{5,12})", raw)
    if m:
        target = m.group(1)
    else:
        t, _ = ST.parse_at(raw)
        if t:
            target = t
    target = (target or "").strip()
    g = _my(gid, qq)
    if not g.get("name"):
        return "亲，您还没有加入任何帮派！"
    if not target or not target.isdigit():
        return "亲，帮派邀请格式为：【帮派邀请 @QQ】！"
    try:
        from . import slave as SL
        if not SL.exists_user(gid, target):
            return "Ta不是本群的小伙伴，无法邀请！"
    except Exception:
        pass
    tg = _my(gid, target)
    if tg.get("name"):
        return "对方已经加入帮派，无需邀请！"
    info = _guild_info(gid, g["name"])
    limit = _cfgi("人数上限", 30)
    if info and info["count"] >= limit:
        return "亲，该帮派人数已满，无法再邀请！"
    _acct(gid, target).set("guild_invite", g["name"])
    ST.acct_save(gid, target)
    return f"已向 <{target}> 发出「{g['name']}」邀请！对方发送【同意加入帮派】即可加入！"


def cmd_accept_invite(gid, qq):
    g = _my(gid, qq)
    if g.get("name"):
        return f"亲，你已经加入了帮派「{g['name']}」，如需加入其他请先退出！"
    inv = _acct(gid, qq).get("guild_invite", "")
    if not inv:
        return "亲，您当前没有收到任何帮派邀请！"
    info = _guild_info(gid, inv)
    if not info:
        _acct(gid, qq).set("guild_invite", "")
        ST.acct_save(gid, qq)
        return "亲，该帮派已不存在，邀请失效！"
    limit = _cfgi("人数上限", 30)
    if info["count"] >= limit:
        return "亲，该帮派人数已满，无法加入！"
    _save_member(gid, qq, {"name": inv, "pos": "成员", "gong": 0, "build": 0})
    _acct(gid, qq).set("guild_invite", "")
    ST.acct_save(gid, qq)
    return f"欢迎加入「{inv}」！"


def cmd_exit(gid, qq):
    g = _my(gid, qq)
    if not g.get("name"):
        return "亲，您还没有加入任何帮派！"
    if g.get("pos") == "帮主":
        return "亲，您是该帮派帮主，请先【解散帮派】或【出让帮派】再退出！"
    exit_tili = _cfgi("退出消耗体力", 0)
    exit_meili = _cfgi("退出扣除魅力", 0)
    if _acct(gid, qq).int("stamina") < exit_tili:
        return f"亲，退出帮派需要消耗{exit_tili}点体力，您的体力不足！"
    if _acct(gid, qq).int("charm") < exit_meili:
        return f"亲，退出帮派需要扣除{exit_meili}点魅力，您的魅力不足！"
    if exit_tili:
        ST.acct_add(gid, qq, "stamina", -exit_tili)
    if exit_meili:
        ST.acct_add(gid, qq, "charm", -exit_meili)
    name = g["name"]
    _save_member(gid, qq, {})
    return f"您已退出帮派「{name}」！"


def _gname(gid, qq):
    try:
        from . import slave as SL
        try:
            nm = SL.get_note_name(gid, str(qq)) or SL.fetch_card(gid, str(qq))
            if nm:
                return nm
        except Exception:
            pass
        return str(qq)
    except Exception:
        return str(qq)


def cmd_members(gid, qq):
    g = _my(gid, qq)
    if not g.get("name"):
        return "亲，您还没有加入任何帮派！"
    mem = _members(gid, g["name"])
    if not mem:
        return "亲，该帮派暂无成员！"
    # 排序: 帮主 -> 护法 -> 其余按 帮贡 降序
    order = {"帮主": 0, "护法": 1, "成员": 2}
    mem.sort(key=lambda x: (order.get(x[1].get("pos", "成员"), 2),
                            -int(x[1].get("gong", 0) or 0)))
    lines = [f"【{g['name']}】成员列表"]
    for q, mg in mem:
        lines.append(f"{mg.get('pos','成员')}｜{_gname(gid, q)}｜帮贡{mg.get('gong',0)}")
    return "\r\n".join(lines)


def cmd_contribute(gid, qq, amt):
    g = _my(gid, qq)
    if not g.get("name"):
        return "亲，您还没有加入任何帮派！"
    amt = int(amt or 0)
    if amt <= 0:
        return "亲，帮派贡献格式为：【帮派贡献 金额】！"
    min_amt = _cfgi("贡献下限", 100)
    if amt < min_amt:
        return f"亲，单次帮派贡献至少需要{min_amt}{ST.coin_name()}（每100{ST.coin_name()}加1帮贡）！"
    if ST.coins_get(gid, qq) < amt:
        return f"笑~你没有那么多{ST.coin_name()}！"
    ST.coins_add(gid, qq, -amt)
    g["gong"] = int(g.get("gong", 0)) + amt // CONTRIBUTE_DIV
    _save_member(gid, qq, g)
    return f"贡献成功！帮派帮贡 +{amt // CONTRIBUTE_DIV}，你的贡献 {g['gong']}"


def cmd_mine(gid, qq):
    g = _my(gid, qq)
    if not g.get("name"):
        return "亲，您还没有加入任何帮派！"
    return f"我的贡献:{g.get('gong',0)}　我的修筑:{g.get('build',0)}"


def cmd_build(gid, qq, amt):
    """修筑城墙: 帮派强化-修筑价格/修筑上限"""
    g = _my(gid, qq)
    if not g.get("name"):
        return "亲，您还没有加入任何帮派！"
    amt = int(amt or 1)
    price = _cfgi("修筑价格", 10000)
    cap = _cfgi("修筑上限", 50)
    cur = int(g.get("build", 0) or 0)
    if cur + amt > cap:
        return f"帮派城墙修筑已达上限（{cap}），无法继续修筑！"
    cost = price * amt
    if ST.coins_get(gid, qq) < cost:
        return f"笑~你没有那么多{ST.coin_name()}（修筑城墙需要{cost}）"
    ST.coins_add(gid, qq, -cost)
    g["build"] = cur + amt
    _save_member(gid, qq, g)
    return f"修筑城墙成功！当前城墙长度{g['build']}/{cap}，花费{cost}{ST.coin_name()}"


def cmd_welfare(gid, qq):
    g = _my(gid, qq)
    if not g.get("name"):
        return "亲，您还没有加入任何帮派！"
    key = f"guild_welfare_{gid}_{qq}_{time.strftime('%Y%m%d')}"
    if ST.recall_get(key, ""):
        return "亲，您今天已经领取过帮派福利了，明天再来吧！"
    base = _cfgi("福利基数", 4000)
    got = base + int(g.get("gong", 0)) * WELFARE_PER_GONG
    ST.coins_add(gid, qq, got)
    ST.recall_set(key, "1")
    return f"领取帮派福利成功！获得 {got}{ST.coin_name()}（基础{base}+帮贡奖励）"


def cmd_battle(gid, qq, gname):
    my = _my(gid, qq)
    if not my.get("name"):
        return "亲，您还没有创建或加入任何帮派！"
    if my.get("pos") not in ("帮主", "护法"):
        return "亲，您不是帮主或护法，没有权力发起帮战！"
    if not gname:
        return "亲，您的指令有误，发起帮战格式为【发起帮战 帮派名】！"
    if gname == my["name"]:
        return "对不起，内战无效，请对其他帮派发起帮战！"
    foe = _guild_info(gid, gname)
    if not foe:
        return "对不起，您挑战的帮派并不存在！"
    mine = _guild_info(gid, my["name"])
    if not mine:
        return "对不起，您所在的帮派数据异常！"
    limit = _cfgi("帮战次数上限", 5)
    key = f"guildwar_{gid}_{qq}_{time.strftime('%Y%m%d')}"
    if int(ST.recall_get(key, "0") or 0) >= limit:
        return "对不起，您所在的帮派今日帮战次数已达上限！"
    ST.recall_set(key, str(int(ST.recall_get(key, "0") or 0) + 1))
    mp, fp = mine["fight"], foe["fight"]
    if mp >= fp:
        win = True
    else:
        win = random_bool(mp / (mp + fp)) if (mp + fp) else False
    if win:
        import random as _rr
        lo = _cfgi("帮战获贡下限", 0)
        hi = _cfgi("帮战获贡上限", 0)
        gain = 0
        if hi > 0 or lo > 0:
            _lo, _hi = (lo, hi) if lo <= hi else (hi, lo)
            _lo = max(0, _lo)
            _hi = max(0, _hi)
            if _hi > 0:
                gain = _rr.randint(_lo, _hi)
        if gain > 0:
            my["gong"] = int(my.get("gong", 0) or 0) + gain
            _save_member(gid, qq, my)
            return (f"恭喜，您的帮派在此次帮战中大获全胜，收缴敌方帮贡！+{gain}帮贡\r\n"
                    f"{my['name']}(战力{mp}) 击败 {gname}(战力{fp})")
        return (f"恭喜，您的帮派在此次帮战中大获全胜，收缴敌方帮贡！\r\n"
                f"{my['name']}(战力{mp}) 击败 {gname}(战力{fp})")
    return (f"很抱歉，您的帮派在此次帮战中惨败，损失帮贡！\r\n"
            f"{my['name']}(战力{mp}) 不敌 {gname}(战力{fp})")


def random_bool(p):
    import random as _r
    return _r.random() < p


def cmd_manage(gid, qq, arg):
    my = _my(gid, qq)
    if not my.get("name"):
        return "亲，您还没有加入任何帮派！"
    if my.get("pos") not in ("帮主", "护法"):
        return "亲，您不是帮主或护法，无管理权限！"
    name = my["name"]
    if arg.startswith("修改宣言"):
        intro = arg[4:].strip()
        my["intro"] = intro
        _save_member(gid, qq, my)
        return "帮派宣言已更新！"
    m = None
    if arg.startswith("添加护法"):
        m = re.search(r"(\d{5,12})", arg)
        if m and _is_member(gid, name, m.group(1)):
            tg = _my(gid, m.group(1)); tg["pos"] = "护法"; _save_member(gid, m.group(1), tg)
            return f"已将 <{_gname(gid, m.group(1))}> 设为护法！"
        return "无法添加该护法（需是同帮成员）！"
    if arg.startswith("取消护法"):
        m = re.search(r"(\d{5,12})", arg)
        if m and _is_member(gid, name, m.group(1)):
            if _my(gid, m.group(1)).get("pos") == "帮主":
                return "不能对帮主使用该操作！"
            tg = _my(gid, m.group(1)); tg["pos"] = "成员"; _save_member(gid, m.group(1), tg)
            return f"已取消 <{_gname(gid, m.group(1))}> 护法！"
        return "无法取消（需是同帮护法）！"
    if arg.startswith("移出帮派"):
        m = re.search(r"(\d{5,12})", arg)
        if m and _is_member(gid, name, m.group(1)):
            if _my(gid, m.group(1)).get("pos") == "帮主":
                return "不能对帮主使用该操作！"
            _save_member(gid, m.group(1), {})
            return f"已将 <{_gname(gid, m.group(1))}> 移出帮派！"
        return "无法移出（需是同帮成员）！"
    if arg.startswith("出让帮派"):
        m = re.search(r"(\d{5,12})", arg)
        if m and my.get("pos") == "帮主" and _is_member(gid, name, m.group(1)):
            tg = _my(gid, m.group(1)); tg["pos"] = "帮主"; _save_member(gid, m.group(1), tg)
            my["pos"] = "护法"; _save_member(gid, qq, my)
            return f"已将帮主出让给 <{_gname(gid, m.group(1))}>！"
        return "仅帮主可出让给同帮成员！"
    if arg.startswith("帮派升级"):
        cost = _cfgi("升级需要帮贡", 20000)
        info = _guild_info(gid, name)
        if not info:
            return "帮派数据异常！"
        if info["gong"] < cost:
            return f"帮贡不足，升级需要{cost}帮贡！"
        owner_g = _my(gid, info["owner"])
        owner_g["lv"] = int(owner_g.get("lv", 0) or 0) + 1
        owner_g["gong"] = max(0, int(owner_g.get("gong", 0) or 0) - cost)
        _save_member(gid, info["owner"], owner_g)
        return f"帮派升至 Lv.{owner_g['lv']}！（消耗{cost}帮贡）"
    if arg.startswith("解散帮派"):
        dis_tili = _cfgi("解散消耗体力", 0)
        dis_meili = _cfgi("解散扣除魅力", 0)
        if _acct(gid, qq).int("stamina") < dis_tili:
            return f"亲，解散帮派需要消耗{dis_tili}点体力，您的体力不足！"
        if _acct(gid, qq).int("charm") < dis_meili:
            return f"亲，解散帮派需要扣除{dis_meili}点魅力，您的魅力不足！"
        if dis_tili:
            ST.acct_add(gid, qq, "stamina", -dis_tili)
        if dis_meili:
            ST.acct_add(gid, qq, "charm", -dis_meili)
        mem = _members(gid, name)
        for q, _ in mem:
            _save_member(gid, q, {})
        return f"帮派「{name}」已解散！"
    return MEMU_MANAGE


def _is_member(gid, name, qq):
    g = _my(gid, qq)
    return g.get("name") == name


def cmd_rank(gid, kind):
    kind = kind or "总战力"
    if ST._DB is None:
        return "暂无数据。"
    # 复用同一批量缓存，避免 DISTINCT+N次 acct
    gid_s = str(gid)
    now = time.time()
    cached = _GUILD_MEMBERS_CACHE.get(gid_s)
    ts = _GUILD_MEMBERS_TS.get(gid_s, 0)
    if cached is not None and now - ts < _GUILD_TTL:
        all_members = cached
    else:
        with ST._LOCK:
            rows = ST._DB.execute("SELECT qq, data FROM accounts WHERE gid=?", (int(gid),)).fetchall() if ST._DB else []
        all_members = []
        for qqdb, data in rows:
            try:
                raw = json.loads(data)
                g = json.loads(raw.get("guild", "{}") or "{}")
            except Exception:
                continue
            if g.get("name"):
                all_members.append((str(qqdb), g))
        _GUILD_MEMBERS_CACHE[gid_s] = all_members
        _GUILD_MEMBERS_TS[gid_s] = now
    gnames = {}
    for q, g in all_members:
        gnames.setdefault(g["name"], set()).add(q)
    entries = []
    for name in gnames:
        info = _guild_info(gid, name)
        if not info:
            continue
        val = {"等级": info["level"], "人数": info["count"], "战斗": info["fight"],
               "防御": info["build"], "总战力": info["fight"], "帮贡": info["gong"]}.get(kind, info["fight"])
        entries.append((val, name, info["count"]))
    entries.sort(key=lambda x: -x[0])
    lines = [f"---帮派{kind}排行---"]
    for i, (v, n, c) in enumerate(entries[:10], 1):
        lines.append(f"{i}. {n}　{v}")
    return "\r\n".join(lines) if lines[1:] else "本群暂无帮派~"


MEMU_MANAGE = (
    "帮派管理(帮主/护法)：\r\n修改宣言 内容　添加护法 QQ　取消护法 QQ\r\n"
    "移出帮派 QQ　出让帮派 QQ　帮派升级　解散帮派"
)


def handle(gid, qq, raw):
    text = (raw or "").strip()
    if not text:
        return None
    if text in ST.wake("帮派系统", "帮派系统"):
        if _need_switch(gid):
            return "【帮派系统】已经被关闭了，无法使用该功能！\r\n如需开启，请机器人管理发送【帮派开关】进行开启！"
        return MENU
    if _need_switch(gid):
        return "【帮派系统】已经被关闭了，无法使用该功能！"
    if text == "帮派列表":
        return cmd_list(gid, qq)
    if text == "我的帮派":
        return cmd_my(gid, qq)
    if text == "成员列表":
        return cmd_members(gid, qq)
    if text == "帮派排行":
        return cmd_rank(gid, "总战力")
    if text == "退出帮派":
        return cmd_exit(gid, qq)
    if text in ("我的贡献", "我的修筑"):
        return cmd_mine(gid, qq)
    if text == "领取帮派福利":
        return cmd_welfare(gid, qq)
    if text.startswith("创建帮派"):
        return cmd_create(gid, qq, text[4:].strip())
    if text.startswith("加入帮派"):
        return cmd_join(gid, qq, text[4:].strip())
    if text in ("同意加入帮派", "接受邀请", "同意邀请"):
        return cmd_accept_invite(gid, qq)
    if text.startswith("帮派邀请"):
        return cmd_invite(gid, qq, text[4:].strip())
    if text.startswith("帮派贡献"):
        m = re.search(r"(\d+)", text)
        return cmd_contribute(gid, qq, int(m.group(1)) if m else 0)
    if text.startswith("修筑城墙"):
        m = re.search(r"(\d+)", text)
        return cmd_build(gid, qq, int(m.group(1)) if m else 1)
    if text.startswith("发起帮战"):
        return cmd_battle(gid, qq, text[4:].strip())
    if text.startswith("管理帮派") or text.startswith("帮派管理"):
        if text in ("管理帮派", "帮派管理"):
            return MEMU_MANAGE
        return cmd_manage(gid, qq, text[4:].strip())
    if text.startswith("帮派升级") or text.startswith("解散帮派") \
            or text.startswith("修改宣言") or text.startswith("添加护法") or text.startswith("取消护法") \
            or text.startswith("移出帮派") or text.startswith("出让帮派"):
        return cmd_manage(gid, qq, text)
    return None
