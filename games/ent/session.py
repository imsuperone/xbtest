# -*- coding: utf-8 -*-
"""games/ent·session（原 ent.py 切分，语义不变）。"""
import random
import time
try:
    from ...core import storage as ST
except ImportError:
    from core import storage as ST
from .content import *  # noqa
def _active_game(gid):
    try:
        return ST.recall_get(f"ent_game_{gid}", "") or ""
    except Exception:
        return ""




def _set_active_game(gid, label):
    try:
        ST.recall_set(f"ent_game_{gid}", str(label))
    except Exception:
        pass




def _clear_active_game(gid):
    try:
        ST.recall_set(f"ent_game_{gid}", "")
    except Exception:
        pass




_GAME_KIND_MAP = {
    "接龙": "chain",
    "急转弯": "trick",
    "猜字谜": "miri",
    "字谜": "miri",
    "猜数": "guessnum",
    "答题": "quiz",
    "二四点": "game24",
}




_TIMEOUT_TASKS = {}  # (gid, kind) -> asyncio.Task


def _cancel_timeout_task(gid, kind):
    """取消群内该游戏的后台超时与提醒任务"""
    task = _TIMEOUT_TASKS.pop((str(gid), str(kind)), None)
    if task and not task.done():
        try:
            task.cancel()
        except Exception:
            pass


def _start_timeout_task(gid, kind, label, ans_text=""):
    """开启后台定时监控：40秒无人回答发提醒，60秒自动清理公布答案"""
    _cancel_timeout_task(gid, kind)
    try:
        import asyncio
        loop = asyncio.get_event_loop()
        if loop and loop.is_running():
            task = asyncio.create_task(_async_timeout_monitor(str(gid), str(kind), str(label), str(ans_text)))
            _TIMEOUT_TASKS[(str(gid), str(kind))] = task
    except Exception:
        pass


async def _async_timeout_monitor(gid, kind, label, ans_text):
    """后台监控协程：40s 提醒，60s 超时清理公布答案"""
    import asyncio
    try:
        # 第一阶段：等待 40 秒，发出即将超时提醒
        await asyncio.sleep(40)
        cur_owner = ST.recall_get(f"{kind}_owner_{gid}")
        if not cur_owner:
            return

        try:
            from ...core.messaging import send_proactive_group_msg
        except ImportError:
            try:
                from core.messaging import send_proactive_group_msg
            except ImportError:
                send_proactive_group_msg = None

        if send_proactive_group_msg:
            await send_proactive_group_msg(
                gid,
                f"⏳【{label}】还有 20 秒回答时间，快开动脑筋想想吧！（若放弃可由管理员或开局者发送【结束{label}】）"
            )

        # 第二阶段：再等待 20 秒（累计 60 秒），超时彻底自动清理公布答案
        await asyncio.sleep(20)
        cur_owner = ST.recall_get(f"{kind}_owner_{gid}")
        if not cur_owner:
            return

        ans = ans_text or ST.recall_get(f"{kind}_{gid}_{cur_owner}") or ""
        ans_part = f"\r\n正确答案为：【{ans}】" if ans else ""
        ST.recall_set(f"{kind}_owner_{gid}", "")
        ST.recall_set(f"{kind}_players_{gid}", "")
        ST.recall_set(f"{kind}_ans_{gid}", "")
        for k in (f"{kind}_{gid}_{cur_owner}", f"{kind}_start_{gid}", f"{kind}_last_time_{gid}"):
            ST.recall_set(k, "")
        _clear_active_game(gid)

        if send_proactive_group_msg:
            await send_proactive_group_msg(
                gid,
                f"⌛【{label}】由于长时间无人回答，本轮{label}已自动结束！{ans_part}"
            )
    except asyncio.CancelledError:
        pass
    except Exception:
        pass
    finally:
        _TIMEOUT_TASKS.pop((str(gid), str(kind)), None)


def _clean_expired_game(gid, max_seconds=60):
    """自动清理超时闲置或异常遗留的会话游戏锁，避免单群永久卡死（默认60秒无响应自动结束）"""
    cur = _active_game(gid)
    if not cur:
        # 清理可能残留的孤儿键值，避免影响后续判断
        try:
            for k in ("chain_owner_", "trick_owner_", "miri_owner_", "guessnum_owner_", "quiz_owner_", "game24_owner_"):
                if ST.recall_get(f"{k}{gid}"):
                    ST.recall_set(f"{k}{gid}", "")
            if ST.recall_get(f"chain_{gid}"):
                ST.recall_set(f"chain_{gid}", "")
                ST.recall_set(f"chain_start_{gid}", "")
                ST.recall_set(f"chain_players_{gid}", "")
                ST.recall_set(f"chain_used_{gid}", "")
                ST.recall_set(f"chain_last_qq_{gid}", "")
                ST.recall_set(f"chain_last_time_{gid}", "")
        except Exception:
            pass
        return False
    kind = _GAME_KIND_MAP.get(cur)
    if not kind:
        _clear_active_game(gid)
        return True
    try:
        start_val = ST.recall_get(f"{kind}_start_{gid}", "0")
        try:
            start_ts = int(start_val or "0")
        except Exception:
            start_ts = 0
        now = int(time.time())
        last_time = 0
        if kind == "chain":
            try:
                last_time = int(ST.recall_get(f"chain_last_time_{gid}", "0") or 0)
            except Exception:
                last_time = 0
        else:
            try:
                last_time = int(ST.recall_get(f"{kind}_last_time_{gid}", "0") or 0)
            except Exception:
                last_time = 0
        effective_ts = max(start_ts, last_time)
        # effective_ts <= 0 属于脏数据/孤儿锁，或者距离开局/最后互动超过 max_seconds，均清理
        if effective_ts <= 0 or (now - effective_ts) > max_seconds:
            _cancel_timeout_task(gid, kind)
            owner = ST.recall_get(f"{kind}_owner_{gid}", "")
            ST.recall_set(f"{kind}_owner_{gid}", "")
            ST.recall_set(f"{kind}_players_{gid}", "")
            ST.recall_set(f"{kind}_start_{gid}", "")
            ST.recall_set(f"{kind}_last_time_{gid}", "")
            if owner:
                ST.recall_set(f"{kind}_{gid}_{owner}", "")
            if kind == "chain":
                ST.recall_set(f"chain_{gid}", "")
                ST.recall_set(f"chain_used_{gid}", "")
                ST.recall_set(f"chain_last_qq_{gid}", "")
                ST.recall_set(f"chain_last_time_{gid}", "")
                ST.recall_set(f"chain_owner_{gid}", "")
                ST.recall_set(f"chain_players_{gid}", "")
                ST.recall_set(f"chain_start_{gid}", "")
            elif kind == "game24":
                ST.recall_set(f"game24_{gid}_{owner}", "")
                ST.recall_set(f"game24_players_{gid}", "")
                ST.recall_set(f"game24_start_{gid}", "")
                ST.recall_set(f"game24_owner_{gid}", "")
                ST.recall_set(f"game24_ans_{gid}", "")
            _clear_active_game(gid)
            return True
    except Exception:
        pass
    return False




def _check_single_game(gid, new_label, sender_qq=None):
    _clean_expired_game(gid)
    cur = _active_game(gid)
    if cur and cur != new_label:
        return f"已有进行中的【{cur}】游戏，请先结束当前游戏再开新局！（发送【退出{cur}】结束）"
    # 同类型已在进行中：检查是否开局者重开，或已无互动超过 60 秒，若符合则自动刷新重开
    if cur == new_label:
        kind = _GAME_KIND_MAP.get(cur, "")
        if kind:
            now = int(time.time())
            owner = ST.recall_get(f"{kind}_owner_{gid}", "")
            start_val = ST.recall_get(f"{kind}_start_{gid}", "0")
            try:
                start_ts = int(start_val or "0")
            except Exception:
                start_ts = 0
            last_time = 0
            if kind == "chain":
                try:
                    last_time = int(ST.recall_get(f"chain_last_time_{gid}", "0") or 0)
                except Exception:
                    last_time = 0
            else:
                try:
                    last_time = int(ST.recall_get(f"{kind}_last_time_{gid}", "0") or 0)
                except Exception:
                    last_time = 0
            # 开局者重开、或者超过60秒无互动、或者无有效owner残留，均直接瞬时刷新重开
            try:
                idle = now - max(start_ts, last_time) if max(start_ts, last_time) > 0 else 999
            except Exception:
                idle = 999
            if (not owner) or (sender_qq and str(owner) == str(sender_qq)) or idle > 60:
                _clean_expired_game(gid, max_seconds=0)
                return None
        return f"已有进行中的【{cur}】游戏，请先完成或退出后再开新局！（发送【退出{cur}】可重新开局）"
    return None


# ---- 24点可解性求解器 ----
# 缓存千群并发下重复 4 数判定（最多 13^4=28561 种），避免每局递归 43k 次


def cmd_bomb(gid, qq, arg):
    """扔炸弹: 花费+体力掷炸弹, 按概率命中目标(命中则禁言目标，需平台支持)"""
    import re as _re2
    a = ST.acct(gid, qq)
    cost = cfgi("娱乐配置", "扔炸弹_需要金钱", 2000)
    tili = cfgi("娱乐配置", "扔炸弹_消耗体力", 5)
    meli = cfgi("娱乐配置", "扔炸弹_魅力减少", 2)
    nmin = cfgi("娱乐配置", "扔炸弹_个数下限", 1)
    nmax = cfgi("娱乐配置", "扔炸弹_个数上限", 2)
    prob = cfgi("娱乐配置", "扔炸弹_成功概率", 75)
    try:
        from ..sign import eff_prob as _luck_eff
        prob = _luck_eff(prob, gid, qq)
    except Exception:
        pass
    mute_lo = cfgi("娱乐配置", "扔炸弹_禁言下限", 1)
    mute_hi = cfgi("娱乐配置", "扔炸弹_禁言上限", 5)
    # 解析目标：支持 CQ 码、@QQ号、纯数字、@群昵称
    arg = (arg or "").strip()
    if not arg:
        return "请指定扔炸弹目标，格式：扔炸弹 @QQ"
    target = None

    # 1. CQ 码 / [At:QQ] 提取（优先从文本任意位置提取中的 qq 号）
    m_cq = _re2.search(r"(?:\[CQ:at,qq=(\d+)[^\]]*\]|\[At:\s*(\d+)\])", arg)
    if m_cq:
        target = m_cq.group(1) or m_cq.group(2)

    # 2. @QQ数字 / 纯QQ数字提取（5-12位数字）
    if not target:
        m_num = _re2.search(r"(?:^|@|\s)(\d{5,12})(?:\s|$)", arg)
        if m_num:
            target = m_num.group(1)

    # 3. parse_at 别名/群昵称反查（兼容 @群昵称）
    if not target:
        t, _ = ST.parse_at(arg)
        if t and str(t).isdigit():
            target = str(t)

    # 4. 尝试从群内昵称/奴隶系统反查
    if not target and arg.startswith("@"):
        cand_name = arg.lstrip("@").strip()
        try:
            from ..slave.handler import _find_slave_qq_by_name
            t_cand = _find_slave_qq_by_name(gid, cand_name, ST)
            if t_cand:
                target = str(t_cand)
        except Exception:
            pass

    if not target:
        return "请指定扔炸弹目标，格式：扔炸弹 @QQ"

    if str(target) == str(qq):
        return "亲，不能对自己扔炸弹哦！"
    if ST.coins_get(gid, qq) < cost:
        return "笑~你没有那么多%s（扔炸弹需%d）" % (ST.coin_name(), cost)
    if a.int("stamina") < tili:
        return "体力不足，扔炸弹需要%d体力！" % tili
    # 单事务扣钱+扣体力（锁内复检，禁半成功开奖）
    with ST._LOCK:
        if ST.coins_get(gid, qq) < cost:
            return "笑~你没有那么多%s（扔炸弹需%d）" % (ST.coin_name(), cost)
        if a.int("stamina") < tili:
            return "体力不足，扔炸弹需要%d体力！" % tili
        updates = {"stamina": str(max(0, a.int("stamina") - tili))}
        if ST.txn_coins_acct(gid, qq, -cost, updates, require_funds=True) is None:
            return "数据库繁忙，扔炸弹扣费未成功，请稍后重试。"
    t_name = str(target)
    try:
        from ..bank.common import _disp_name
        tn = _disp_name(target, gid)
        if tn and tn != target:
            t_name = tn
    except Exception:
        pass
    if t_name == str(target):
        try:
            from ...core.messaging import resolve_display_name
            tn = resolve_display_name(target, gid=gid)
            if tn and tn != target:
                t_name = tn
        except Exception:
            pass

    n = random.randint(nmin, nmax)
    if random.randint(1, 100) <= prob:
        mute = random.randint(mute_lo, mute_hi)
        # 已接入 OneBot 禁言
        return f"__XB_PLATFORM__|mute|{target}|{mute*60}__TEXT__💣 轰！你扔出{n}颗炸弹命中【{t_name}】！\r\n【{t_name}】被禁言{mute}分钟！花费{cost}{ST.coin_name()}、{tili}体力"
    ST.acct_add(gid, qq, "charm", -meli)
    return (f"💣 你向【{t_name}】扔出{n}颗炸弹，可惜被躲开了！\r\n"
            f"魅力-{meli}，花费{cost}{ST.coin_name()}、{tili}体力")










def _start_24(gid, qq):
    # 二四点开局消耗（可配，默认 0/2 兼容旧版）
    err = _ent_cost(gid, qq, "二四点")
    if err:
        return err
    nums = _generate_solvable_24()
    ans_expr = _solve_24_expr(nums)
    ST.recall_set(f"game24_{gid}_{qq}", "|".join(map(str, nums)))
    ST.recall_set(f"game24_ans_{gid}", ans_expr)
    ST.recall_set(f"game24_owner_{gid}", str(qq))
    ST.recall_set(f"game24_start_{gid}", str(int(time.time())))
    ST.recall_set(f"game24_last_time_{gid}", str(int(time.time())))
    ST.recall_set(f"game24_players_{gid}", "")
    _set_active_game(gid, "二四点")
    _start_timeout_task(gid, "game24", "二四点", f"参考算式：{ans_expr} = 24")
    return ("🃏 二四点开始！用 + - * / 和括号把下面 4 个数算出 24：\r\n"
            "【%s】\r\n回复你的算式即可！（其他玩家可发送【加入二四点】加入，管理员或开局者发送【结束二四点】）"
            % " ".join(map(str, nums)))




def _get_players(gid, key_prefix):
    v = ST.recall_get(f"{key_prefix}{gid}", "")
    return [x for x in str(v).split(",") if x]




def _join_game(gid, qq, kind, label):
    owner = ST.recall_get(f"{kind}_owner_{gid}")
    if not owner:
        return f"当前没有进行中的{label}对局！"
    if str(owner) == str(qq):
        return "您是开局者，无需加入！"
    start = ST.recall_get(f"{kind}_start_{gid}", "0")
    try:
        try:
            _lt = int(ST.recall_get(f"{kind}_last_time_{gid}", "0") or 0)
        except Exception:
            _lt = 0
        try:
            _st = int(start or "0")
        except Exception:
            _st = 0
        if int(time.time()) - max(_st, _lt) >= 30:
            return "开局已超过30秒，无法加入，请等待下一局！"
    except Exception:
        pass
    players = _get_players(gid, f"{kind}_players_")
    if str(qq) not in players:
        players.append(str(qq))
        ST.recall_set(f"{kind}_players_{gid}", ",".join(players))
    return f"你已加入{label}！发送你的答案参与吧~"




def _quit_game(gid, qq, kind, label, is_admin=False):
    """只退出发送者自己（普通成员与管理员发送【退出XX】行为严格一致：只退自己，绝不结束全群游戏）。"""
    owner = ST.recall_get(f"{kind}_owner_{gid}")
    if not owner:
        _clear_active_game(gid)
        return f"当前没有进行中的【{label}】对局！"
    if kind == "game24":
        ans = ST.recall_get(f"game24_ans_{gid}")
        ans_part = f"\r\n参考算式为：【{ans} = 24】" if ans else ""
    else:
        ans = ST.recall_get(f"{kind}_{gid}_{owner}")
        ans_part = f"\r\n本题正确答案为：【{ans}】" if ans else ""
    players = _get_players(gid, f"{kind}_players_")

    # 1. 如果发送者是普通参与者（在 players 列表中）
    if str(qq) in players:
        players.remove(str(qq))
        ST.recall_set(f"{kind}_players_{gid}", ",".join(players))
        return f"你已退出【{label}】！"

    # 2. 如果发送者是开局者 owner
    if str(owner) == str(qq):
        # 若还有其他已加入的参与者，将对局所有权移交给下一位继续进行，不影响其他人玩！
        if players:
            new_owner = players.pop(0)
            ST.recall_set(f"{kind}_owner_{gid}", str(new_owner))
            ST.recall_set(f"{kind}_players_{gid}", ",".join(players))
            if ans and kind != "game24":
                ST.recall_set(f"{kind}_{gid}_{new_owner}", ans)
                ST.recall_set(f"{kind}_{gid}_{qq}", "")
            return f"你已退出【{label}】！对局已转交其他参与者继续进行~"
        else:
            # 只有自己一人在玩，自己退出则对局自然结束
            _cancel_timeout_task(gid, kind)
            ST.recall_set(f"{kind}_owner_{gid}", "")
            ST.recall_set(f"{kind}_players_{gid}", "")
            ST.recall_set(f"{kind}_ans_{gid}", "")
            for k in (f"{kind}_{gid}_{owner}", f"{kind}_{gid}_{qq}", f"{kind}_start_{gid}", f"{kind}_last_time_{gid}"):
                ST.recall_set(k, "")
            _clear_active_game(gid)
            return f"你已退出【{label}】，因无其他参与者，对局结束！{ans_part}"

    # 3. 发送者根本不在对局中
    return f"你并未参与当前的【{label}】对局哦~（发送【加入{label}】即可加入作答）"


def _end_game(gid, qq, kind, label, is_admin=False):
    """结束当前群内的游戏对局（权限：机器人管理员 或 当前开局者）。"""
    owner = ST.recall_get(f"{kind}_owner_{gid}")
    if not owner:
        _clear_active_game(gid)
        return f"当前没有进行中的【{label}】对局！"
    if kind == "game24":
        ans = ST.recall_get(f"game24_ans_{gid}")
        ans_part = f"\r\n参考算式为：【{ans} = 24】" if ans else ""
    else:
        ans = ST.recall_get(f"{kind}_{gid}_{owner}")
        ans_part = f"\r\n本题正确答案为：【{ans}】" if ans else ""

    # 权限校验：必须是管理员或者当前开局者
    if not is_admin and str(owner) != str(qq):
        return f"只有开局者或管理员可以提前结束【{label}】对局哦！（参与者如需退出请发送【退出{label}】）"

    # 执行清理并公布答案
    _cancel_timeout_task(gid, kind)
    ST.recall_set(f"{kind}_owner_{gid}", "")
    ST.recall_set(f"{kind}_players_{gid}", "")
    ST.recall_set(f"{kind}_ans_{gid}", "")
    for k in (f"{kind}_{gid}_{owner}", f"{kind}_{gid}_{qq}", f"{kind}_start_{gid}", f"{kind}_last_time_{gid}"):
        ST.recall_set(k, "")
    _clear_active_game(gid)

    if is_admin and str(owner) != str(qq):
        prefix = f"【{label}】对局已由管理员结束！"
    else:
        prefix = f"【{label}】对局已由开局者结束！"
    return f"{prefix}{ans_part}"


def _is_player(gid, qq, kind):
    """判断是否对局参与者(开局者或已加入者)"""
    owner = ST.recall_get(f"{kind}_owner_{gid}")
    if owner and str(owner) == str(qq):
        return True
    players = _get_players(gid, f"{kind}_players_")
    return str(qq) in players



__all__ = [
    "_GAME_KIND_MAP", "_active_game", "_check_single_game", "_clean_expired_game",
    "_clear_active_game", "_get_players", "_is_player", "_join_game", "_quit_game",
    "_end_game", "_start_timeout_task", "_cancel_timeout_task", "_set_active_game",
    "_start_24", "cmd_bomb"
]
