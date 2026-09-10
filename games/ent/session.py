# -*- coding: utf-8 -*-
"""games/ent·session（原 ent.py 切分，语义不变）。"""
import random
import time
try:
    from ... import storage as ST
except ImportError:
    import storage as ST
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




def _clean_expired_game(gid, max_seconds=30):
    """自动清理超时闲置或异常遗留的会话游戏锁，避免单群永久卡死（30秒无响应自动结束）"""
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
    # 同类型已在进行中：检查是否开局者重开，或已无互动超过 30 秒，若符合则自动刷新重开
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
            # 开局者重开、或者超过30秒无互动、或者无有效owner残留，均直接瞬时刷新重开
            try:
                idle = now - max(start_ts, last_time) if max(start_ts, last_time) > 0 else 999
            except Exception:
                idle = 999
            if (not owner) or (sender_qq and str(owner) == str(sender_qq)) or idle > 30:
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
    cost = ST.cfgi("娱乐配置", "扔炸弹_需要金钱", 30000)
    tili = ST.cfgi("娱乐配置", "扔炸弹_消耗体力", 20)
    meli = ST.cfgi("娱乐配置", "扔炸弹_魅力减少", 5)
    nmin = ST.cfgi("娱乐配置", "扔炸弹_个数下限", 1)
    nmax = ST.cfgi("娱乐配置", "扔炸弹_个数上限", 2)
    prob = ST.cfgi("娱乐配置", "扔炸弹_成功概率", 70)
    mute_lo = ST.cfgi("娱乐配置", "扔炸弹_禁言下限", 5)
    mute_hi = ST.cfgi("娱乐配置", "扔炸弹_禁言上限", 10)
    # 解析目标（必须指定 @QQ / @昵称 / CQ码）
    target = None
    if arg:
        m = _re2.search(r"\[CQ:at,qq=(\d+)[^\]]*\]", arg)
        if m:
            target = m.group(1)
        else:
            t, _ = ST.parse_at(arg)
            if t:
                target = t
            else:
                # 纯数字 QQ
                mm = _re2.search(r"(\d{5,12})", arg)
                if mm:
                    target = mm.group(1)
    if not target:
        return "请指定扔炸弹目标，格式：扔炸弹 @QQ"
    if ST.coins_get(gid, qq) < cost:
        return "笑~你没有那么多%s（扔炸弹需%d）" % (ST.coin_name(), cost)
    if a.int("stamina") < tili:
        return "体力不足，扔炸弹需要%d体力！" % tili
    ST.coins_add(gid, qq, -cost)
    ST.acct_add(gid, qq, "stamina", -tili)
    n = random.randint(nmin, nmax)
    if random.randint(1, 100) <= prob:
        mute = random.randint(mute_lo, mute_hi)
        # 已接入 OneBot 禁言
        return f"__XB_PLATFORM__|mute|{target}|{mute*60}__TEXT__💣 轰！你扔出{n}颗炸弹命中目标！\r\n目标被禁言{mute}分钟！花费{cost}{ST.coin_name()}、{tili}体力"
    ST.acct_add(gid, qq, "charm", -meli)
    return (f"💣 你扔出{n}颗炸弹，可惜被躲开了！\r\n"
            f"魅力-{meli}，花费{cost}{ST.coin_name()}、{tili}体力")










def _start_24(gid, qq):
    # 二四点开局消耗（可配，默认 0/2 兼容旧版）
    err = _ent_cost(gid, qq, "二四点")
    if err:
        return err
    nums = _generate_solvable_24()
    ST.recall_set(f"game24_{gid}_{qq}", "|".join(map(str, nums)))
    ST.recall_set(f"game24_owner_{gid}", str(qq))
    ST.recall_set(f"game24_start_{gid}", str(int(time.time())))
    ST.recall_set(f"game24_last_time_{gid}", str(int(time.time())))
    ST.recall_set(f"game24_players_{gid}", "")
    _set_active_game(gid, "二四点")
    return ("🃏 二四点开始！用 + - * / 和括号把下面 4 个数算出 24：\r\n"
            "【%s】\r\n回复你的算式即可！（其他玩家30秒内发送【加入二四点】加入，发送【退出二四点】结束）"
            % " ".join(map(str, nums)))




def _get_players(gid, key_prefix):
    v = ST.recall_get(key_prefix + gid, "")
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




def _quit_game(gid, qq, kind, label):
    owner = ST.recall_get(f"{kind}_owner_{gid}")
    if not owner:
        return f"当前没有进行中的{label}对局！"
    players = _get_players(gid, f"{kind}_players_")
    if str(owner) == str(qq):
        # 开局者退出=结束整局
        ST.recall_set(f"{kind}_owner_{gid}", "")
        ST.recall_set(f"{kind}_players_{gid}", "")
        for k in (f"{kind}_{gid}_{qq}", f"{kind}_start_{gid}", f"{kind}_last_time_{gid}"):
            ST.recall_set(k, "")
        return f"你已退出{label}，对局结束！"
    if str(qq) in players:
        players.remove(str(qq))
        ST.recall_set(f"{kind}_players_{gid}", ",".join(players))
    return f"你已退出{label}！"






def _is_player(gid, qq, kind):
    """判断是否对局参与者(开局者或已加入者)"""
    owner = ST.recall_get(f"{kind}_owner_{gid}")
    if owner and str(owner) == str(qq):
        return True
    players = _get_players(gid, f"{kind}_players_")
    return str(qq) in players



__all__ = ["_GAME_KIND_MAP", "_active_game", "_check_single_game", "_clean_expired_game", "_clear_active_game", "_get_players", "_is_player", "_join_game", "_quit_game", "_set_active_game", "_start_24", "cmd_bomb"]
