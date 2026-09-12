# -*- coding: utf-8 -*-
"""全员空投 API — 批量福利空投（由 users.py 独立拆出，端点不变）。"""
import asyncio
from astrbot.api.web import json_response

from .web_utils import _err, get_req_json

try:
    from .. import storage as ST
except ImportError:
    from core import storage as ST

try:
    from ..version import get_version as _get_version
except ImportError:
    try:
        from core.version import get_version as _get_version  # type: ignore
    except Exception:
        def _get_version(*a, **k):  # type: ignore
            return "2026w0912a"
try:
    PLUGIN_VERSION = _get_version()
except Exception:
    PLUGIN_VERSION = "2026w0912a"


async def handle_users_airdrop(request):
    """批量全员/定向群福利空投分发"""
    try:
        data = await get_req_json(request, default={})
        if not isinstance(data, dict):
            return _err("invalid json body", 400)

        target_gid = str(data.get("gid") or "").strip()
        add_money = int(data.get("money") or 0)
        add_stamina = int(data.get("stamina") or 0)
        add_tickets = int(data.get("tickets") or 0)
        reason = str(data.get("reason") or "全员福利空投").strip()

        if add_money <= 0 and add_stamina <= 0 and add_tickets <= 0:
            return _err("请至少输入一项大于 0 的发放数值", 400)

        try:
            ST.flush_all()
        except Exception:
            pass

        def _collect_targets():
            _lock = getattr(ST, "_LOCK", None)
            if _lock is not None:
                _lock.acquire()
            try:
                cur = ST._DB.cursor()
                targets = set() # set of (gid, qq)

                if target_gid:
                    gid_arg = int(target_gid) if target_gid.isdigit() else str(target_gid)
                    cur.execute("SELECT gid, qq FROM wallet WHERE gid = ?", (gid_arg,))
                    for r in cur.fetchall():
                        targets.add((str(r[0]), str(r[1])))
                    cur.execute("SELECT gid, qq FROM accounts WHERE gid = ?", (gid_arg,))
                    for r in cur.fetchall():
                        targets.add((str(r[0]), str(r[1])))
                else:
                    cur.execute("SELECT gid, qq FROM wallet")
                    for r in cur.fetchall():
                        targets.add((str(r[0]), str(r[1])))
                    cur.execute("SELECT gid, qq FROM accounts")
                    for r in cur.fetchall():
                        targets.add((str(r[0]), str(r[1])))
                return targets
            finally:
                if _lock is not None:
                    try:
                        _lock.release()
                    except Exception:
                        pass

        targets = await asyncio.to_thread(_collect_targets)

        if not targets:
            return _err("未找到符合发放条件的目标用户", 404)

        def _do_airdrop():
            try:
                return _airdrop_batch(targets, add_money, add_stamina, add_tickets)
            except Exception:
                # 批量失败降级为逐用户老路径，保证发放不中断
                success_count = 0
                for g, q in targets:
                    try:
                        if add_money > 0:
                            ST.coins_add(g, q, add_money)
                        if add_stamina > 0:
                            ST.acct_add(g, q, "stamina", add_stamina)
                        if add_tickets > 0:
                            ST.acct_add(g, q, "lottery_tickets", add_tickets)
                        if add_stamina > 0 or add_tickets > 0:
                            ST.acct_save(g, q)
                        success_count += 1
                    except Exception:
                        pass
                return success_count

        success_count = await asyncio.to_thread(_do_airdrop)

        try:
            ST.flush_all()
        except Exception:
            pass

        return json_response({
            "ok": True,
            "target_count": success_count,
            "gid": target_gid or "all",
            "rewards": {
                "money": add_money,
                "stamina": add_stamina,
                "tickets": add_tickets
            },
            "reason": reason
        })
    except Exception as e:
        return _err(f"airdrop error: {e}", 500)


def _airdrop_batch(targets, add_money, add_stamina, add_tickets):
    """批量空投：缺失行补齐 + 条件更新 + 单事务一次提交（原 N 用户 × 3 事务）。

    语义与逐用户老路径一致：金币钳位 [0, 1e11]，体力/奖券下限 0；
    脏缓存用户走老路径保语义，其余批量后清缓存按需重载。返回成功数。
    """
    pairs = []
    for g, q in targets or []:
        try:
            pairs.append((int(g), int(q)))
        except Exception:
            continue
    if not pairs:
        return 0
    legacy, batched = [], []
    for gi, qi in pairs:
        _dirty = False
        try:
            for _k in ((str(gi), str(qi)), (gi, qi), (str(gi), qi), (gi, str(qi))):
                _a = ST._ACC_CACHE.get(_k)
                if _a is not None and getattr(_a, "dirty", False):
                    _dirty = True
                    break
        except Exception:
            _dirty = True
        (legacy if _dirty else batched).append((gi, qi))
    done = 0
    for g, q in legacy:
        try:
            if add_money > 0:
                ST.coins_add(g, q, add_money)
            if add_stamina > 0:
                ST.acct_add(g, q, "stamina", add_stamina)
            if add_tickets > 0:
                ST.acct_add(g, q, "lottery_tickets", add_tickets)
            if add_stamina > 0 or add_tickets > 0:
                ST.acct_save(g, q)
            done += 1
        except Exception:
            pass
    if not batched:
        return done
    with ST._LOCK:
        if ST._DB is None:
            raise RuntimeError("DB未初始化")
        try:
            if add_money > 0:
                ST._DB.executemany(
                    "INSERT OR IGNORE INTO wallet(gid, qq, money) VALUES(?, ?, 0)", batched)
                _cap = int(getattr(ST, "COIN_CAP", 100000000000))
                _sql_air = ("UPDATE wallet SET money = CASE WHEN money + ? < 0 THEN 0 "
                            "WHEN money + ? > " + str(_cap) + " THEN " + str(_cap) + " "
                            "ELSE money + ? END WHERE gid = ? AND qq = ?")
                ST._DB.executemany(
                    _sql_air,
                    [(add_money, add_money, add_money, g, q) for g, q in batched])
            if add_stamina > 0 or add_tickets > 0:
                ST._DB.executemany(
                    "INSERT OR IGNORE INTO accounts(gid, qq, data) VALUES(?, ?, '{}')", batched)
                if add_stamina > 0:
                    ST._DB.executemany(
                        "UPDATE accounts SET data = json_set(data, '$.stamina', CAST("
                        "CASE WHEN CAST(COALESCE(json_extract(data, '$.stamina'), '0') AS INTEGER) + ? < 0 THEN 0 "
                        "ELSE CAST(COALESCE(json_extract(data, '$.stamina'), '0') AS INTEGER) + ? END "
                        "AS TEXT)) WHERE gid = ? AND qq = ?",
                        [(add_stamina, add_stamina, g, q) for g, q in batched])
                if add_tickets > 0:
                    ST._DB.executemany(
                        "UPDATE accounts SET data = json_set(data, '$.lottery_tickets', CAST("
                        "CASE WHEN CAST(COALESCE(json_extract(data, '$.lottery_tickets'), '0') AS INTEGER) + ? < 0 THEN 0 "
                        "ELSE CAST(COALESCE(json_extract(data, '$.lottery_tickets'), '0') AS INTEGER) + ? END "
                        "AS TEXT)) WHERE gid = ? AND qq = ?",
                        [(add_tickets, add_tickets, g, q) for g, q in batched])
            ST._DB.commit()
        except Exception:
            try:
                ST._safe_rollback()
            except Exception:
                pass
            raise
    try:
        for g, q in batched:
            for _k in ((str(g), str(q)), (g, q), (str(g), q), (g, str(q))):
                _a = ST._ACC_CACHE.pop(_k, None)
                if _a is not None:
                    try:
                        _a.dirty = False
                        _a.kv.clear()
                    except Exception:
                        pass
    except Exception:
        pass
    return done + len(batched)
