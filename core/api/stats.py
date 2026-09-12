# -*- coding: utf-8 -*-
"""stats / rank / groups / updater API — 总览与排行（含大屏聚合 analytics/overview + 日志 logs）
+ 群组开关 groups（原 groups.py 并入）+ 在线版本检测 updater（原 updater.py 并入，零语义差）。"""
import asyncio
import datetime
import functools
import json
import os
import re
import time
import urllib.request
import urllib.error
try:
    from astrbot.api.web import json_response
except ImportError:
    def json_response(data, status=200):
        return data
from .web_utils import _err, get_req_query, get_req_json, no_cache_response

try:
    from .. import storage as ST
    from ...games import slave
except ImportError:
    from core import storage as ST
    try:
        from games import slave
    except ImportError:
        import slave  # type: ignore

try:
    from .. import logger
except ImportError:
    from core import logger  # type: ignore


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
            total_dep = _one(cur, "SELECT COALESCE(SUM(CAST(COALESCE(json_extract(data,'$.deposit'), json_extract(data,'$.cunkuan'), json_extract(data,'$.\"存款总数\"'), '0') AS INTEGER)),0) FROM accounts")
            acct_rows = None
            if not total_dep and (n_acct or 0) < 100000:
                # 兜底全表仅小库执行，大库跳过防秒级阻塞
                try:
                    acct_rows = cur.execute("SELECT data FROM accounts").fetchall()
                except Exception:
                    acct_rows = None
            n_sign = _one(cur, "SELECT COALESCE(SUM(CAST(COALESCE(json_extract(data,'$.sign_count'), json_extract(data,'$.签到次数'), '0') AS INTEGER)),0) FROM accounts")
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
                         "FROM accounts ORDER BY 2 DESC LIMIT 20", None),
                "stamina": ("SELECT qq, CAST(COALESCE(json_extract(data,'$.stamina'), json_extract(data,'$.tili'), '0') AS INTEGER) "
                         "FROM accounts ORDER BY 2 DESC LIMIT 20", None),
                "charm": ("SELECT qq, CAST(COALESCE(json_extract(data,'$.charm'), json_extract(data,'$.meili'), '0') AS INTEGER) "
                          "FROM accounts ORDER BY 2 DESC LIMIT 20", None),
                "deposit": ("SELECT qq, CAST(COALESCE(json_extract(data,'$.deposit'), json_extract(data,'$.cunkuan'), json_extract(data,'$.存款总数'), '0') AS INTEGER) "
                         "FROM accounts ORDER BY 2 DESC LIMIT 20", None),
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
            name = nm.get(qq, "") or g_names.get(qq, "") or a_names.get(qq, "")
            out.append({"qq": qq, "name": name, "value": r[1]})
        return out
    out = await asyncio.to_thread(_work)
    return json_response(out)


# ==================== 日志（原 logs.py 并入） ====================

async def handle_logs_get(request=None):
    try:
        from .web_utils import get_req_json
        body = await get_req_json(request, {})
        limit_str = get_req_query(request, "limit", "") or (body.get("limit") if isinstance(body, dict) else "") or "200"
        level = get_req_query(request, "level", "") or (body.get("level") if isinstance(body, dict) else "") or ""
        keyword = get_req_query(request, "keyword", "") or (body.get("keyword") if isinstance(body, dict) else "") or ""

        try:
            limit = int(limit_str)
        except Exception:
            limit = 200

        # 日志文件读 + 正则过滤走线程池，不堵消息循环
        data = await asyncio.to_thread(
            functools.partial(logger.get_logs, limit=limit, level=level, keyword=keyword))
        return json_response({
            "status": "ok",
            "result": data,
            "logs": data.get("logs", []),
            "count": data.get("count", 0),
            "total_lines": data.get("total_lines", 0),
            "file_size_kb": data.get("file_size_kb", 0),
            "max_file_mb": data.get("max_file_mb", 2.0),
        })
    except Exception as e:
        return _err(f"获取日志失败: {e}", 500)


async def handle_logs_clear(request=None):
    try:
        ok = await asyncio.to_thread(logger.clear_logs)
        if ok:
            return json_response({"status": "ok", "message": "插件日志已清空"})
        else:
            return _err("清空日志失败", 500)
    except Exception as e:
        return _err(f"清空日志异常: {e}", 500)


async def handle_logs_export(request=None):
    try:
        log_path = logger.get_log_file_path()

        def _work():
            if os.path.isfile(log_path):
                with open(log_path, "r", encoding="utf-8", errors="replace") as f:
                    return f.read()
            return ""

        content_str = await asyncio.to_thread(_work)

        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"xb_logs_{ts}.log"

        return json_response({
            "status": "ok",
            "filename": filename,
            "content": content_str
        })
    except Exception as e:
        return _err(f"导出日志失败: {e}", 500)


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


# ==================== 群组开关（原 groups.py 并入） ====================
async def handle_groups_list(request=None):
    def _work():
        _lock = getattr(ST, "_LOCK", None)
        if _lock is not None:
            _lock.acquire()
        try:
            counts = {}
            try:
                if ST._DB is not None:
                    # 单次聚合替代 3×DISTINCT+逐群COUNT：三表 UNION 去重后按群计数
                    for gid_, cnt in ST._DB.execute(
                        "SELECT gid, COUNT(DISTINCT qq) FROM ("
                        "SELECT gid, qq FROM wallet "
                        "UNION SELECT gid, qq FROM accounts "
                        "UNION SELECT gid, qq FROM groups"
                        ") GROUP BY gid"
                    ).fetchall():
                        if str(gid_).isdigit():
                            counts[str(gid_)] = int(cnt or 0)
            except Exception:
                pass
            gids = set(counts.keys())
            try:
                sec = ST._CONFIG.get("群组开关配置") if hasattr(ST, "_CONFIG") and isinstance(ST._CONFIG, dict) else {}
                if isinstance(sec, dict):
                    for k in sec.keys():
                        if str(k).isdigit():
                            gids.add(str(k))
            except Exception:
                pass

            out = []
            for gid in sorted(gids, key=lambda x: int(x) if str(x).isdigit() else 0):
                enabled = ST.cfg("群组开关配置", str(gid), "真") != "假"
                try:
                    _maint = ST.recall_get("group_maint_%s" % gid, "0") == "1"
                except Exception:
                    _maint = False
                out.append({"gid": str(gid), "enabled": enabled, "maintenance": _maint, "member_count": int(counts.get(str(gid), 0)), "is_test": str(gid) == "999999"})
            total_enabled = ST.cfg("总开关配置", "总开关", "真") == "真"
            return {"total_enabled": total_enabled, "groups": out}
        finally:
            if _lock is not None:
                try:
                    _lock.release()
                except Exception:
                    pass
    data = await asyncio.to_thread(_work)
    return json_response(data)

async def handle_groups_toggle(request):
    data = await get_req_json(request, default={})
    gid = str(data.get("gid", "") or data.get("group_id", "") or "").strip()
    enabled = data.get("enabled")
    if isinstance(enabled, str):
        enabled = enabled.strip() not in ("假", "false", "False", "0", "off")
    else:
        enabled = bool(enabled) if enabled is not None else True
    # 本群维修开关（WebUI 群聊开关 Tab 可直接切换；聊天内 开启维护/关闭维护 同效）
    maint = data.get("maintenance", None)
    do_enabled = "enabled" in data

    if gid in ("total", "__total__", "总开关"):
        ST._CONFIG.setdefault("总开关配置", {})
        ST._CONFIG["总开关配置"]["总开关"] = "真" if enabled else "假"
        try: ST.save_config()
        except Exception: pass
        try: ST.sync_astrbot_config(ST._CONFIG)
        except Exception: pass
        return json_response({"ok": True, "total_enabled": enabled})

    if not gid or not gid.isdigit():
        return json_response({"ok": False, "msg": "群号必填且需为纯数字"})

    def _work():
        if do_enabled:
            ST._CONFIG.setdefault("群组开关配置", {})
            ST._CONFIG["群组开关配置"][gid] = "真" if enabled else "假"
            try: ST.save_config()
            except Exception: pass
            try: ST.sync_astrbot_config(ST._CONFIG)
            except Exception: pass
            try: ST.recall_set(f"group_switch_{gid}", "1" if enabled else "0")
            except Exception: pass
        _maint_now = None
        if maint is not None:
            _maint_now = bool(maint) if not isinstance(maint, str) else maint.strip() not in ("假", "false", "False", "0", "off", "")
            try: ST.recall_set(f"group_maint_{gid}", "1" if _maint_now else "0")
            except Exception: pass

        # 同步初始化 group 实体
        try:
            grp = ST.group(gid)
            ST.save_group(gid)
        except Exception:
            pass

        _resp = {"ok": True, "gid": gid}
        if do_enabled:
            _resp["enabled"] = enabled
        if _maint_now is not None:
            _resp["maintenance"] = _maint_now
        return json_response(_resp)

    return await asyncio.to_thread(_work)

async def handle_groups_delete(request):
    data = await get_req_json(request, default={})
    gid = str(data.get("gid", "") or data.get("group_id", "") or "").strip()
    if not gid or not gid.isdigit():
        return json_response({"ok": False, "msg": "群号必填且需为纯数字"})

    def _work():
        try:
            sec = ST._CONFIG.get("群组开关配置") if hasattr(ST, "_CONFIG") and isinstance(ST._CONFIG, dict) else {}
            if isinstance(sec, dict) and gid in sec:
                sec.pop(gid, None)
            try: ST.save_config()
            except Exception: pass
            try: ST.sync_astrbot_config(ST._CONFIG)
            except Exception: pass
            try: ST.recall_set(f"group_switch_{gid}", "1")
            except Exception: pass
            return json_response({"ok": True, "gid": gid, "deleted": True})
        except Exception as e:
            return json_response({"ok": False, "msg": str(e)}, status=500)

    return await asyncio.to_thread(_work)


# ==================== 在线版本检测（原 updater.py 并入） ====================
GITHUB_REPO = "imsuperone/xb"
GITHUB_REPO_XBTEST = "imsuperone/xbtest"  # BETA 通道：快照版跟踪仓
API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
UPDATE_CHANNELS = ("正式", "BETA")

_LAST_CHECK_RES = {}
_LAST_CHECK_TIME = {}
_CHECK_CACHE_TTL = 300.0  # 成功结果缓存 5 分钟：版本不变时不再打 GitHub，防 RateLimit
_CHECK_FAIL_TTL = 60.0  # 失败结果缓存 1 分钟：网络故障时不再每点每试
_CHECK_RUNNING_SINCE = {}  # channel -> 在途检测开始时间戳（分槽：双通道并查互不阻塞，防惊群）
_CHECK_RUNNING_TTL = 30.0  # 在途超时：拥有者超过此时长未回即视为死亡，等候者自行接管


def _get_local_version(plugin_base=""):
    """本地版本：委托 version.py 单源（读 metadata.yaml），失败回 _FALLBACK。"""
    try:
        try:
            from ..version import get_version as _gv
        except ImportError:
            from core.version import get_version as _gv  # type: ignore
        return _gv(plugin_base)
    except Exception:
        pass
    return "2026w0912d"


def _parse_version_tuple(v_str):
    """纪元比较：委托 version.parse_version_tuple（单源，含快照制），失败走本地同逻辑兜底。"""
    try:
        try:
            from ..version import parse_version_tuple as _pvt
        except ImportError:
            from core.version import parse_version_tuple as _pvt  # type: ignore
        return _pvt(v_str)
    except Exception:
        pass
    s = str(v_str or "").strip()
    m0 = re.match(r"^(\d{4})[wW](\d{2})(\d{2})([a-zA-Z]+)$", s)
    if m0:
        try:
            _seq = 0
            for _ch in m0.group(4).lower():
                _seq = _seq * 26 + (ord(_ch) - 96)
            return (2, int(m0.group(1) + m0.group(2) + m0.group(3)), _seq)
        except Exception:
            pass
    m = re.findall(r"\d+", s)
    nums = [int(x) for x in m] if m else [0, 0, 0]
    while len(nums) < 3:
        nums.append(0)
    major, minor, patch = nums[0], nums[1], nums[2]
    epoch = 0 if (major == 0 and 10 <= minor <= 68) else 1
    return (epoch, major, minor, patch)





def _update_channel():
    """更新通道：recall 记忆，缺省 BETA（beta 插件；正式版树可另行默认正式）。"""
    try:
        c = str(ST.recall_get("update_channel", "BETA") or "BETA").strip()
        if c in UPDATE_CHANNELS:
            return c
    except Exception:
        pass
    return "BETA"


def _channel_repo(channel):
    return GITHUB_REPO_XBTEST if channel == "BETA" else GITHUB_REPO


def check_latest_version(plugin_base="", repo=""):
    """
    双通道检测最新版本：
    1. GitHub Releases 接口 (官方标准发版，带版本日志与元数据)
    2. GitHub main 分支 metadata.yaml (实时 Git 提交版本，支持多镜像加速容灾)
    择优选取版本号最高者，并与本地版本进行纪元元组比较。
    repo 为空则用官方仓；BETA 通道传 xbtest 仓。
    """
    local_ver = _get_local_version(plugin_base)
    repo = (repo or "").strip() or GITHUB_REPO
    api_url = f"https://api.github.com/repos/{repo}/releases/latest"
    headers = {
        "User-Agent": "XbBot-AutoUpdater/1.0",
        "Accept": "application/vnd.github.v3+json"
    }

    # 1. 优先尝试检测 main 分支 metadata.yaml（多镜像加速容灾；3 镜像×2 秒=最坏 6 秒，
    # 加 Releases 4 秒共 10 秒，低于前端 20 秒熔断；慢代理镜像已剔除）
    main_ver = ""
    ts = int(time.time())
    raw_meta_urls = [
        f"https://raw.githubusercontent.com/{repo}/main/metadata.yaml",
        f"https://cdn.jsdelivr.net/gh/{repo}@main/metadata.yaml?_t={ts}",
        f"https://fastly.jsdelivr.net/gh/{repo}@main/metadata.yaml?_t={ts}"
    ]
    for url in raw_meta_urls:
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=2) as resp:
                if resp.status == 200:
                    txt = resp.read().decode("utf-8")
                    for line in txt.splitlines():
                        if line.strip().startswith("version:"):
                            main_ver = line.split(":", 1)[1].strip().strip('"').strip("'")
                            break
                    if main_ver:
                        break
        except Exception:
            continue

    # 2. 检测 GitHub Releases 接口
    rel_ver = ""
    rel_name = ""
    rel_date = ""
    rel_body = ""
    try:
        req = urllib.request.Request(api_url, headers=headers)
        with urllib.request.urlopen(req, timeout=4) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                rel_ver = (data.get("tag_name") or data.get("name") or "").replace("v", "").strip()
                rel_name = data.get("name") or rel_ver
                rel_date = (data.get("published_at") or "")[:10]
                rel_body = data.get("body") or ""
    except Exception:
        pass

    # 3. 双通道择优：取版本号更高者
    # 若 main 分支最新提交版本严格高于 Release 版本，则提示 main 分支源码更新
    # 否则若存在 Release 发版，优先使用官方规范发版与更新日志
    if main_ver and _parse_version_tuple(main_ver) > _parse_version_tuple(rel_ver):
        best_ver = main_ver
        best_name = f"小白 v{main_ver} (Git main 源码更新)"
        best_date = time.strftime("%Y-%m-%d")
        best_body = "已检测到 GitHub 仓库 main 分支最新提交版本，可前往 AstrBot 插件管理面板一键更新或拉取代码。"
    elif rel_ver:
        best_ver = rel_ver
        best_name = rel_name or f"小白 v{rel_ver} 正式版"
        best_date = rel_date or time.strftime("%Y-%m-%d")
        best_body = rel_body or "请查看 GitHub Releases 更新说明。"
    elif main_ver:
        best_ver = main_ver
        best_name = f"小白 v{main_ver}"
        best_date = time.strftime("%Y-%m-%d")
        best_body = "已检测到 GitHub 仓库最新代码。"
    else:
        best_ver = local_ver
        best_name = f"小白 {local_ver}"
        best_date = time.strftime("%Y-%m-%d")
        best_body = "当前已是最新版本。"

    has_update = _parse_version_tuple(best_ver) > _parse_version_tuple(local_ver)
    detect_error = None
    if not main_ver and not rel_ver:
        detect_error = "无法连接 GitHub（raw/Api 双通道均失败，多为服务器网络或代理问题），请检查网络后重试"
    return {
        "ok": True,
        "current_version": local_ver,
        "latest_version": best_ver,
        "has_update": has_update,
        "release_name": best_name,
        "release_date": best_date,
        "changelog": best_body,
        "detect_error": detect_error
    }


async def handle_version_check(request=None, plugin_base=""):
    """从云端检测是否有最新 Release 或 main 分支版本（完全异步化，绝不阻塞主事件循环）。
    通道：显式 channel 参数 > 存储记忆 > 默认 BETA；BETA 查 xbtest 快照仓，正式查官方仓。"""
    global _LAST_CHECK_RES, _LAST_CHECK_TIME, _CHECK_RUNNING_SINCE
    import asyncio
    channel = ""
    try:
        if isinstance(request, dict):
            channel = str(request.get("channel") or "")
        elif request is not None:
            channel = get_req_query(request, "channel", "")
    except Exception:
        pass
    if (not channel or channel.strip() not in UPDATE_CHANNELS):
        # 官方 proxy 直读（真机唯一真相，request=None 时唯一有效路）
        try:
            from astrbot.api.web import request as _proxy
            try:
                channel = str(_proxy.query.get("channel", "") or "")
            except Exception:
                pass
        except Exception:
            pass
    channel = (channel or "").strip()
    if channel not in UPDATE_CHANNELS:
        channel = _update_channel()
    # 旧单槽缓存（无 channel 键）直接丢弃重检
    if not isinstance(_LAST_CHECK_RES, dict):
        _LAST_CHECK_RES = {}
    if not isinstance(_LAST_CHECK_TIME, dict):
        _LAST_CHECK_TIME = {}
    if not isinstance(_CHECK_RUNNING_SINCE, dict):
        _CHECK_RUNNING_SINCE = {}
    repo = _channel_repo(channel)
    now = time.time()
    # 成功/失败分级缓存（按通道分槽隔离：双通道并查互不覆盖）
    _cached = _LAST_CHECK_RES.get(channel)
    if _cached is not None:
        _failed = bool(_cached.get("detect_error") or _cached.get("error"))
        _ttl = _CHECK_FAIL_TTL if _failed else _CHECK_CACHE_TTL
        if (now - _LAST_CHECK_TIME.get(channel, 0)) < _ttl:
            return no_cache_response(json_response(_cached))
    # 在途共享（同通道）：已有检测在跑则等候结果（8 秒），防并发惊群打 GitHub
    _t0 = now
    if _CHECK_RUNNING_SINCE.get(channel, 0) > 0 and (now - _CHECK_RUNNING_SINCE.get(channel, 0)) < _CHECK_RUNNING_TTL:
        try:
            for _ in range(16):
                await asyncio.sleep(0.5)
                if (_LAST_CHECK_TIME.get(channel, 0) > _t0 and _LAST_CHECK_RES.get(channel) is not None):
                    return no_cache_response(json_response(_LAST_CHECK_RES.get(channel)))
                if _CHECK_RUNNING_SINCE.get(channel, 0) <= 0:
                    break
        except Exception:
            pass
        now = time.time()
        _cached = _LAST_CHECK_RES.get(channel)
        if (_cached is not None
                and (now - _LAST_CHECK_TIME.get(channel, 0)) < _CHECK_CACHE_TTL):
            return no_cache_response(json_response(_cached))
    # 成为拥有者执行检测
    _CHECK_RUNNING_SINCE[channel] = time.time()
    try:
        try:
            res = await asyncio.to_thread(check_latest_version, plugin_base, repo)
        except Exception as e:
            res = {
                "current_version": _get_local_version(plugin_base),
                "latest_version": _get_local_version(plugin_base),
                "has_update": False,
                "error": str(e)
            }
        res["channel"] = channel
        res["repo"] = repo
        _LAST_CHECK_RES[channel] = res
        _LAST_CHECK_TIME[channel] = time.time()
    finally:
        _CHECK_RUNNING_SINCE[channel] = 0.0
    return no_cache_response(json_response(res))


async def handle_version_channel(request=None):
    """更新通道读写：GET 查当前；POST {channel: 正式/BETA} 切换（记忆进 recall，检测即时跟随）。
    取参全收：dict/body/query/官方 proxy（request=None 真机路），防桥转发形态差异致切换无效。"""
    try:
        data = None
        if isinstance(request, dict):
            data = request
        elif request is not None:
            try:
                data = await get_req_json(request, default={})
            except Exception:
                data = {}
        _c = ""
        try:
            if isinstance(data, dict) and str(data.get("channel") or "").strip() in UPDATE_CHANNELS:
                _c = str(data.get("channel")).strip()
        except Exception:
            pass
        if not _c:
            try:
                _q = get_req_query(request, "channel", "")
                if str(_q or "").strip() in UPDATE_CHANNELS:
                    _c = str(_q).strip()
            except Exception:
                pass
        if not _c:
            # 官方 proxy 直读（request=None 真机路；body/query 双收）
            try:
                from astrbot.api.web import request as _proxy
                try:
                    _jb = _proxy.json
                    if callable(_jb):
                        import inspect as _ins
                        _r = _jb(default={})
                        if _ins.isawaitable(_r):
                            _r = await _r
                        if isinstance(_r, dict) and str(_r.get("channel") or "").strip() in UPDATE_CHANNELS:
                            _c = str(_r.get("channel")).strip()
                except Exception:
                    pass
                if not _c:
                    try:
                        _pq = str(_proxy.query.get("channel", "") or "").strip()
                        if _pq in UPDATE_CHANNELS:
                            _c = _pq
                    except Exception:
                        pass
            except Exception:
                pass
        if _c in UPDATE_CHANNELS:
            try:
                ST.recall_set("update_channel", _c)
            except Exception:
                pass
    except Exception:
        pass
    return json_response({"ok": True, "channel": _update_channel(), "channels": list(UPDATE_CHANNELS)})
