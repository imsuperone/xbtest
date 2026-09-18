# -*- coding: utf-8 -*-
"""stats API — 总览/排行/大屏聚合（logs/groups/version_check/balance/legacy_ini 已独立，端点不变）"""
import asyncio
import json
import time
try:
    from ..adapters import json_response
except ImportError:
    from core.adapters import json_response
from .web_utils import _err, get_req_query

try:
    from .. import storage as ST
    from ...games import slave
except ImportError:
    from core import storage as ST
    try:
        from games import slave
    except ImportError:
        import slave  # type: ignore


# ==================== stats/rank/logs/overview（原 stats.py） ====================
async def handle_stats(request=None):
    def _one(cur, sql, default=0):
        try:
            row = cur.execute(sql).fetchone()
            return row[0] if row and row[0] is not None else default
        except Exception:
            return default

    def _work():
        # 锁内只做 cursor 快照取数，json 解析放锁外，防大库 massive 解析卡住全局写锁
        _lock = getattr(ST, "_LOCK", None)
        if _lock is not None:
            _lock.acquire()
        try:
            if ST._DB is None:
                return {"players": {"wallet": 0, "accounts": 0, "groups": 0}, "total_money": 0, "total_deposit": 0, "total_sign": 0}
            cur = ST._DB.cursor()
            n_wallet = _one(cur, "SELECT COUNT(*) FROM wallet")
            n_acct = _one(cur, "SELECT COUNT(*) FROM accounts")
            n_group = _one(cur, "SELECT COUNT(DISTINCT gid) FROM wallet")
            total = _one(cur, "SELECT COALESCE(SUM(money),0) FROM wallet")
            total_dep = _one(cur, "SELECT COALESCE(SUM(CAST(COALESCE(json_extract(data,'$.deposit'), json_extract(data,'$.cunkuan'), json_extract(data,'$.\"存款总数\"'), '0') AS INTEGER)),0) FROM accounts WHERE json_valid(data)")
            acct_rows = None
            if not total_dep and (n_acct or 0) < 100000:
                # 兜底全表仅小库执行，大库跳过防秒级阻塞
                try:
                    acct_rows = cur.execute("SELECT data FROM accounts").fetchall()
                except Exception:
                    acct_rows = None
            n_sign = _one(cur, "SELECT COALESCE(SUM(CAST(COALESCE(json_extract(data,'$.sign_count'), json_extract(data,'$.签到次数'), '0') AS INTEGER)),0) FROM accounts WHERE json_valid(data)")
            try:
                cur.close()
            except Exception:
                pass
        finally:
            if _lock is not None:
                try:
                    _lock.release()
                except Exception:
                    pass
        if acct_rows:
            try:
                s = 0
                for (d,) in acct_rows:
                    try:
                        j = json.loads(d or "{}")
                        v = j.get("deposit") or j.get("cunkuan") or j.get("存款总数") or "0"
                        s += int(float(v or 0))
                    except Exception:
                        pass
                if s:
                    total_dep = s
            except Exception:
                pass
        return {
            "players": {"wallet": n_wallet, "accounts": n_acct, "groups": n_group},
            "total_money": total,
            "total_deposit": int(total_dep or 0),
            "total_sign": n_sign,
        }
    data = await asyncio.to_thread(_work)
    return json_response(data)


async def handle_rank(request=None):
    from .web_utils import get_req_query
    rtype = get_req_query(request, "type", "money")
    if rtype == "tili":
        rtype = "stamina"
    if rtype == "meili":
        rtype = "charm"
    if rtype == "cunkuan":
        rtype = "deposit"

    def _work():
        # 锁内只做快照取数，昵称解析与组装放锁外
        _lock = getattr(ST, "_LOCK", None)
        if _lock is not None:
            _lock.acquire()
        try:
            sql = {
                "money": ("SELECT qq, money FROM wallet ORDER BY money DESC LIMIT 20", None),
                "sign": ("SELECT qq, CAST(COALESCE(json_extract(data,'$.sign_count'), json_extract(data,'$.签到次数'), '0') AS INTEGER) "
                         "FROM accounts WHERE json_valid(data) ORDER BY 2 DESC LIMIT 20", None),
                "stamina": ("SELECT qq, CAST(COALESCE(json_extract(data,'$.stamina'), json_extract(data,'$.tili'), '0') AS INTEGER) "
                           "FROM accounts WHERE json_valid(data) ORDER BY 2 DESC LIMIT 20", None),
                "charm": ("SELECT qq, CAST(COALESCE(json_extract(data,'$.charm'), json_extract(data,'$.meili'), '0') AS INTEGER) "
                           "FROM accounts WHERE json_valid(data) ORDER BY 2 DESC LIMIT 20", None),
                "deposit": ("SELECT qq, CAST(COALESCE(json_extract(data,'$.deposit'), json_extract(data,'$.cunkuan'), json_extract(data,'$.存款总数'), '0') AS INTEGER) "
                          "FROM accounts WHERE json_valid(data) ORDER BY 2 DESC LIMIT 20", None),
            }.get(rtype)
            try:
                if not sql:
                    rows = ST._DB.execute("SELECT qq, data FROM accounts ORDER BY qq LIMIT 20").fetchall() if ST._DB else []
                else:
                    rows = ST._DB.execute(sql[0]).fetchall() if ST._DB else []
            except Exception:
                rows = []
            qq_list = [str(r[0]) for r in rows]
            g_rows, a_rows = [], []
            if qq_list:
                try:
                    placeholders = ",".join("?" for _ in qq_list)
                    g_rows = ST._DB.execute(f"SELECT qq, data FROM groups WHERE qq IN ({placeholders})", tuple(int(q) for q in qq_list)).fetchall()
                except Exception:
                    g_rows = []
                try:
                    placeholders = ",".join("?" for _ in qq_list)
                    a_rows = ST._DB.execute(f"SELECT qq, data FROM accounts WHERE qq IN ({placeholders})", tuple(int(q) for q in qq_list)).fetchall()
                except Exception:
                    a_rows = []
        finally:
            if _lock is not None:
                try:
                    _lock.release()
                except Exception:
                    pass
        nm = getattr(slave, "NOTE_NAMES", {}) or {}
        # 批量预取昵称，避免 N+1
        g_names, a_names = {}, {}
        for qq_, d in g_rows:
            try:
                j = json.loads(d or "{}")
                if j.get("name"):
                    g_names[str(qq_)] = j["name"]
            except Exception:
                pass
        for qq_, d in a_rows:
            try:
                j = json.loads(d or "{}")
                if j.get("name"):
                    a_names[str(qq_)] = j["name"]
            except Exception:
                pass
        out = []
        for r in rows:
            qq = str(r[0])
            # 本人存档名优先，全局昵称最后兜底（全局是跨群最新，排行无群上下文时只能兜底）
            name = g_names.get(qq, "") or a_names.get(qq, "") or nm.get(qq, "")
            out.append({"qq": qq, "name": name, "value": r[1]})
        return out
    out = await asyncio.to_thread(_work)
    return json_response(out)


# ==================== 大屏聚合（原 overview.py 并入，SQL 聚合 + 3s 轻量缓存） ====================

_CACHE_DATA = None
_CACHE_TIME = 0.0
_CACHE_TTL = 3.0

async def handle_analytics_overview(request):
    """返回群生态与宏观经济运行多维大屏数据（纯净统一无冗余）"""
    global _CACHE_DATA, _CACHE_TIME
    now = time.time()
    if _CACHE_DATA is not None and (now - _CACHE_TIME) < _CACHE_TTL:
        return json_response(_CACHE_DATA)

    def _work():
        if ST._DB is None:
            return {"ok": True, "summary": {}}

        _lock = getattr(ST, "_LOCK", None)
        if _lock is not None:
            _lock.acquire()
        try:
            cur = ST._DB.cursor()

            # 1. 钱包与资产统计
            cur.execute("SELECT SUM(money), COUNT(*), COUNT(DISTINCT gid) FROM wallet")
            row = cur.fetchone()
            total_wallet_money = int(row[0]) if row and row[0] is not None else 0
            total_users_count = int(row[1]) if row and row[1] is not None else 0
            total_groups_count = int(row[2]) if row and row[2] is not None else 0

            # 2. 银行储蓄与签到人次统计：SQL 侧聚合（原逐行 json.loads，百万行即秒级）
            #    语义与旧循环一致：deposit 按行取整累加；sign 取 sign_count 回退 total_sign_days；
            #    非法 JSON/非对象行整行跳过（旧 json.loads 抛错即跳过）；NULL data 视作 {}。
            #    注意 json_each 遇脏串会抛错（json_extract 只回 NULL），故 WHERE 先过滤。
            cur.execute("""
                SELECT
                    COALESCE(SUM(CAST(COALESCE(json_extract(data, '$.deposit'), '0') AS INTEGER)), 0),
                    COALESCE(SUM(CASE WHEN CAST(COALESCE(json_extract(data, '$.deposit'), '0') AS REAL) > 0 THEN 1 ELSE 0 END), 0),
                    COALESCE(SUM(CAST(COALESCE(json_extract(data, '$.sign_count'), json_extract(data, '$.total_sign_days'), '0') AS INTEGER)), 0)
                FROM accounts
                WHERE json_valid(COALESCE(data, '{}'))
            """)
            row = cur.fetchone()
            total_bank_deposit = int(row[0]) if row and row[0] is not None else 0
            total_bank_users = int(row[1]) if row and row[1] is not None else 0
            total_sign_count = int(row[2]) if row and row[2] is not None else 0

            # 3. 奴隶生态与总身价统计：SQL 侧聚合（原 groups 全表逐行解析）
            #    非法 JSON/非对象/NULL 行按旧逻辑处理（NULL 视作 {} 计默认身价，其余跳过）
            default_init_price = ST.cfgi("费用配置", "初始身价", 500) if hasattr(ST, "cfgi") else 500
            cur.execute("""
                SELECT
                    COALESCE(SUM(CAST(COALESCE(json_extract(data, '$.price'), json_extract(data, '$.worth'), ?) AS INTEGER)), 0),
                    COALESCE(SUM(CASE WHEN TRIM(COALESCE(json_extract(data, '$.owner'), '')) NOT IN ('', '0', 'None') THEN 1 ELSE 0 END), 0),
                    COUNT(DISTINCT CASE WHEN TRIM(COALESCE(json_extract(data, '$.owner'), '')) NOT IN ('', '0', 'None')
                                        THEN TRIM(json_extract(data, '$.owner')) END)
                FROM groups
                WHERE data IS NULL OR (json_valid(data) AND json_type(data) = 'object')
            """, (default_init_price,))
            row = cur.fetchone()
            total_slave_worth = int(row[0]) if row and row[0] is not None else 0
            total_slaves_count = int(row[1]) if row and row[1] is not None else 0
            total_masters_count = int(row[2]) if row and row[2] is not None else 0
        finally:
            if _lock is not None:
                try:
                    _lock.release()
                except Exception:
                    pass

        total_economy_pool = total_wallet_money + total_bank_deposit
        avg_money_per_user = int(total_economy_pool / max(1, total_users_count))

        result = {
            "ok": True,
            "summary": {
                "total_users": total_users_count,
                "total_groups": total_groups_count,
                "total_wallet_money": total_wallet_money,
                "total_bank_deposit": total_bank_deposit,
                "total_bank_users": total_bank_users,
                "total_sign_count": total_sign_count,
                "total_economy_pool": total_economy_pool,
                "avg_money_per_user": avg_money_per_user,
                "total_slave_worth": total_slave_worth,
                "total_slaves_count": total_slaves_count,
                "total_masters_count": total_masters_count
            }
        }
        return result

    try:
        result = await asyncio.to_thread(_work)
        _CACHE_DATA = result
        _CACHE_TIME = now
        return json_response(result)
    except Exception as e:
        return _err(f"analytics failed: {e}", 500)



# ==================== 拆分门面（logs/groups/version_check 已独立，老路径兼容） ====================
try:
    from .logs import handle_logs_get, handle_logs_clear, handle_logs_export  # type: ignore
except ImportError:
    pass
try:
    from .groups import handle_groups_list, handle_groups_toggle, handle_groups_delete  # type: ignore
except ImportError:
    pass
try:
    from .version_check import (  # type: ignore
        GITHUB_REPO, GITHUB_REPO_XBTEST, API_URL, UPDATE_CHANNELS,
        check_latest_version, handle_version_check, handle_version_channel,
    )
except ImportError:
    pass
