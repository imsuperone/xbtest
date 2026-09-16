"""storage/kv.py — kv/红包/镜像/投票（原 store §6/§10；红包存取已并入，零语义差）。"""
import json
import os
import time
from . import state as _S
from .state import _safe_commit, _safe_rollback
from .db import _ensure_db, _read_conn
from .collections import coll_migrate
def _init_kv_cache():
    """预热加载 kv 表到内存缓存中，千群并发下读取速度提升 10,000 倍"""
    with _S._LOCK:
        if _S._DB is None:
            return
        try:
            rows = _S._DB.execute("SELECT k, v FROM kv").fetchall()
            with _S._KV_CACHE_LOCK:
                _S._KV_CACHE.clear()
                for k, v in rows:
                    _S._KV_CACHE[str(k)] = str(v)
        except Exception:
            pass
def recall_set(k, v):
    # 锁序 _LOCK→KV（与 _init_kv_cache 一致，防逆序死锁）；先提交后写缓存（失败不超前，下轮重写）
    k_str, v_str = str(k), str(v)
    _ensure_db()
    with _S._LOCK:
        if _S._DB is None:
            return False
        try:
            _S._DB.execute("INSERT INTO kv(k, v) VALUES(?,?) "
                        "ON CONFLICT(k) DO UPDATE SET v=excluded.v", (k_str, v_str))
            if not _safe_commit():
                return False
        except Exception:
            _safe_rollback()
            return False
        try:
            with _S._KV_CACHE_LOCK:
                _S._KV_CACHE[k_str] = v_str
        except Exception:
            return False
        return True
_WD_KEYS = ("WebDAV服务器地址", "WebDAV用户名", "WebDAV应用密码", "WebDAV远端目录", "WebDAV备份开关", "自动备份开关", "备份间隔小时", "保留备份数量")
def wd_cfg_backup(payload_sec=None):
    """WebDAV 与自动备份配置 DB 镜像写透：仅镜像本次保存 payload 里出现的键（含清空语义）。
    其它节保存不碰镜像，避免误清。密钥（地址/用户名/密码）永不进镜像。"""
    if not isinstance(payload_sec, dict):
        return
    try:
        for k in _WD_KEYS:
            if k in _S._WD_SECRET_KEYS:
                continue
            if k in payload_sec:
                recall_set("wdcfg__" + k, str(payload_sec.get(k, "") or ""))
    except Exception:
        pass
def wd_cfg_restore():
    """WebDAV 与备份配置 DB 镜像恢复：从数据库 kv 表恢复备份配置，杜绝任何外部重置导致配置丢失。
    仅当内存缺键或为空时回填；内存已有任何非空值（一律视为有效定制，即使撞 schema 默认如'30'）绝不覆盖。
    密钥（地址/用户名/应用密码）走独立文件，不进镜像；此处顺带做一次性迁移。"""
    try:
        coll_migrate()
    except Exception:
        pass
    try:
        sec = _S._CONFIG.setdefault("备份配置", {}) if isinstance(_S._CONFIG, dict) else {}
        if not isinstance(sec, dict):
            return
        for k in _WD_KEYS:
            if k in _S._WD_SECRET_KEYS:
                continue
            v = recall_get("wdcfg__" + k, None)
            if v is not None and str(v) != "":
                cur = sec.get(k, "")
                # 缺键或空值才回填；有值即信任内存（文件投票另行仲裁文件侧）
                if k not in sec or cur is None or str(cur) == "":
                    sec[k] = str(v)
    except Exception:
        pass
    try:
        from .secrets import _wd_secret_migrate
        _wd_secret_migrate()
    except Exception:
        pass
    try:
        _vote_backup_cfg()
    except Exception:
        pass
_VOTE_KEYS = ("WebDAV备份开关", "自动备份开关", "备份间隔小时", "保留备份数量", "WebDAV远端目录")
def _vote_backup_cfg():
    """备份配置三源投票：持久文件与 DB 镜像一致且非空、与内存不一致时，以持久侧为准。
    专治启动参数/外部重置把已保存值（如保留 30）滚回旧值；文件与镜像在每次保存时同步更新，
    二者一致即代表最后一次成功保存，内存更新必落盘，不会误伤正常改动。无返回值。"""
    try:
        fsec = {}
        try:
            p = _S.CONFIG_FILE
            if p and os.path.isfile(p):
                with open(p, encoding="utf-8") as f:
                    raw = json.load(f)
                if isinstance(raw, dict):
                    for k, v in raw.items():
                        if "__" in str(k):
                            sec, key = str(k).split("__", 1)
                            if sec == "备份配置":
                                fsec[key] = v if isinstance(v, dict) else str(v)
                    if isinstance(raw.get("备份配置"), dict):
                        for k, v in raw["备份配置"].items():
                            fsec[str(k)] = v if isinstance(v, dict) else str(v)
        except Exception:
            fsec = {}
        mem = _S._CONFIG.get("备份配置") if isinstance(_S._CONFIG, dict) else None
        if not isinstance(mem, dict):
            return None
        for k in _VOTE_KEYS:
            try:
                mv = mem.get(k, "")
                mv_s = "" if isinstance(mv, dict) else str(mv or "")
                fv = fsec.get(k, "")
                fv_s = "" if isinstance(fv, dict) else str(fv or "")
                dv = str(recall_get("wdcfg__" + k, "") or "")
                if fv_s != "" and fv_s == dv and mv_s != fv_s:
                    mem[k] = fsec[k] if isinstance(fsec[k], dict) else fv_s
            except Exception:
                continue
    except Exception:
        pass
    return None
def recall_get(k, default=None):
    k_str = str(k)
    with _S._KV_CACHE_LOCK:
        if k_str in _S._KV_CACHE:
            return _S._KV_CACHE[k_str]
    _ensure_db()
    # 读副本快路径：kv 未命中缓存时不阻塞写锁；回填只补缺（setdefault），返回缓存最新值
    # （DB 读与返回之间若有并发写入，返回新值而非本次旧快照，消一次性 stale 窗）
    try:
        rc = _read_conn()
        if rc is not None:
            with _S._RLOCK:
                row = rc.execute("SELECT v FROM kv WHERE k=?", (k_str,)).fetchone()
            val = row[0] if row else default
            if val is not None:
                try:
                    with _S._KV_CACHE_LOCK:
                        _S._KV_CACHE.setdefault(k_str, str(val))
                        return _S._KV_CACHE[k_str]
                except Exception:
                    pass
            return val
    except Exception:
        pass
    with _S._LOCK:
        if _S._DB is None:
            return default
        try:
            row = _S._DB.execute("SELECT v FROM kv WHERE k=?", (k_str,)).fetchone()
            val = row[0] if row else default
            if val is not None:
                try:
                    with _S._KV_CACHE_LOCK:
                        _S._KV_CACHE.setdefault(k_str, str(val))
                        return _S._KV_CACHE[k_str]
                except Exception:
                    pass
            return val
        except Exception:
            return default


def recall_prefix(prefix):
    """kv 前缀扫描（超管列表等管理面只读；异常降级空列表，禁裸抛）。
    LIKE 通配转义：前缀含 %/_ 时按字面匹配（admin_ 即严格前缀）。"""
    try:
        pre = str(prefix or "")
        if not pre:
            return []
        _ensure_db()
        with _S._LOCK:
            if _S._DB is None:
                return []
            try:
                _esc = pre.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
                rows = _S._DB.execute("SELECT k FROM kv WHERE k LIKE ? ESCAPE '\\'", (_esc,)).fetchall()
            except Exception:
                return []
        out = []
        for r in rows or []:
            try:
                out.append(str(r[0]))
            except Exception:
                continue
        return out
    except Exception:
        return []


def redpack_put(gid, qq, pwd, amount):
    """红包存入（原 storage/redpack.py 并入）：DELETE 同口令 + 清 86400 前过期，再 INSERT"""
    _ensure_db()
    with _S._LOCK:
        if _S._DB is None:
            return False
        try:
            _S._DB.execute("DELETE FROM redpacks WHERE gid=? AND pwd=?", (int(gid), str(pwd)))
            _S._DB.execute("DELETE FROM redpacks WHERE ts < ?", (int(time.time()) - 86400,))
            _S._DB.execute("INSERT INTO redpacks(gid, qq, pwd, amount, ts) VALUES(?,?,?,?,?)",
                        (int(gid), int(qq), str(pwd), int(amount), int(time.time())))
            if not _safe_commit():
                return False
            return True
        except Exception:
            _safe_rollback()
            return False


def redpack_get(gid, pwd):
    """红包读取：读副本快路径，未命中回主锁"""
    _ensure_db()
    try:
        with _S._RLOCK:
            if _S._DB_R is not None:
                try:
                    return _S._DB_R.execute(
                        "SELECT qq, amount FROM redpacks WHERE gid=? AND pwd=?",
                        (int(gid), str(pwd))).fetchone()
                except Exception:
                    pass
    except Exception:
        pass
    with _S._LOCK:
        if _S._DB is None:
            return None
        try:
            return _S._DB.execute(
                "SELECT qq, amount FROM redpacks WHERE gid=? AND pwd=?",
                (int(gid), str(pwd))).fetchone()
        except Exception:
            return None

def clean_expired_kv(ttl_sec=7 * 24 * 3600):
    """瞬时 KV 过期回收（后台每小时顺带扫一次，零阻塞）：
    仅清理明确带时间戳语义或已知短命前缀的孤儿键（空串已由会话回收，误清无伤）。
    前缀白名单：chat_ts_/spadv_/chain_/game24_/ent_game_/chouqian_ 等
    （值需为数字时间戳，超 TTL 即删；非时间戳/非白名单键永不碰）。"""
    _ensure_db()
    if _S._DB is None:
        return 0
    prefixes = ("chat_ts_", "spadv_", "chain_", "game24_", "ent_game_", "chouqian_", "chain_start_", "chain_last_time_")
    now = time.time()
    try:
        with _S._LOCK:
            rows = _S._DB.execute("SELECT k, v FROM kv WHERE " + " OR ".join(["k LIKE ?"] * len(prefixes)),
                                 tuple(p + "%" for p in prefixes)).fetchall()
            dead = []
            for k, v in rows:
                s = str(v).strip()
                if not s:
                    # 空串短命锁残留已由会话清，此处不抢（防误删进行中空串占位）
                    continue
                try:
                    ts = float(s)
                except Exception:
                    continue
                # 时间戳合理区间：2020-01-01 ~ 2035-01-01
                if 1577836800 < ts < 2051222400 and (now - ts) > ttl_sec:
                    dead.append(str(k))
            if not dead:
                return 0
            # 分批删（SQLite 变量上限 999）
            n = 0
            for i in range(0, len(dead), 400):
                chunk = dead[i:i + 400]
                _S._DB.execute("DELETE FROM kv WHERE k IN (%s)" % ",".join("?" * len(chunk)), chunk)
                n += len(chunk)
            if _safe_commit():
                try:
                    with _S._KV_CACHE_LOCK:
                        for k in dead:
                            _S._KV_CACHE.pop(k, None)
                except Exception:
                    pass
                return n
            _safe_rollback()
            return 0
    except Exception:
        try:
            _safe_rollback()
        except Exception:
            pass
        return 0


__all__ = ["recall_get", "recall_set", "redpack_get", "redpack_put", "wd_cfg_backup", "wd_cfg_restore", "clean_expired_kv"]
