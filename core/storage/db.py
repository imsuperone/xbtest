"""storage/db.py — DB 内核：连接/自愈/目录/迁移/落盘/合并（原 store §1/§7）。"""
import json
import os
import sqlite3
from . import state as _S
from .state import _safe_commit, _safe_rollback


def _read_conn():
    """懒加载只读连接（query_only），失败返回 None 由调用方回退主连接"""
    if _S._DB_R is not None:
        return _S._DB_R
    try:
        if not _S._DB_PATH or not os.path.isfile(_S._DB_PATH):
            return None
        c = sqlite3.connect(_S._DB_PATH, timeout=_S.DB_TIMEOUT, check_same_thread=False)
        try:
            c.execute("PRAGMA query_only=ON")
        except Exception:
            pass
        _S._DB_R = c
        return _S._DB_R
    except Exception:
        return None


def close_read_conn():
    """关闭只读连接；恢复/切库后必须调用，避免继续读旧快照。"""
    with _S._LOCK:
        conn = _S._DB_R
        _S._DB_R = None
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass

_SQL_INIT = """
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;
PRAGMA busy_timeout=""" + str(_S.DB_BUSY_MS) + """;
PRAGMA cache_size=-64000;
PRAGMA temp_store=MEMORY;
PRAGMA journal_size_limit=67108864;
CREATE TABLE IF NOT EXISTS wallet(
  gid INTEGER NOT NULL,
  qq  INTEGER NOT NULL,
  money INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY(gid, qq)
);
CREATE TABLE IF NOT EXISTS accounts(
  gid INTEGER NOT NULL,
  qq  INTEGER NOT NULL,
  data TEXT NOT NULL DEFAULT '{}',
  PRIMARY KEY(gid, qq)
);
CREATE TABLE IF NOT EXISTS groups(
  gid INTEGER NOT NULL,
  qq  INTEGER NOT NULL,
  data TEXT NOT NULL DEFAULT '{}',
  PRIMARY KEY(gid, qq)
);
CREATE TABLE IF NOT EXISTS redpacks(
  gid INTEGER, qq INTEGER, pwd TEXT, amount INTEGER, ts INTEGER
);
CREATE TABLE IF NOT EXISTS kv(
  k TEXT PRIMARY KEY, v TEXT
);
CREATE INDEX IF NOT EXISTS idx_wallet_gid ON wallet(gid);
CREATE INDEX IF NOT EXISTS idx_wallet_money ON wallet(money DESC);
CREATE INDEX IF NOT EXISTS idx_wallet_gid_money ON wallet(gid, money DESC);
CREATE INDEX IF NOT EXISTS idx_accounts_gid ON accounts(gid);
CREATE INDEX IF NOT EXISTS idx_groups_gid ON groups(gid);
CREATE INDEX IF NOT EXISTS idx_redpacks_gid ON redpacks(gid);
CREATE INDEX IF NOT EXISTS idx_redpacks_gid_pwd ON redpacks(gid, pwd);
CREATE INDEX IF NOT EXISTS idx_kv_k ON kv(k);
"""

# ---- DB 自举 ----
def _ensure_db():
    if _S._DB is not None:
        return _S._DB
    with _S._LOCK:
        if _S._DB is not None:
            return _S._DB
        try:
            base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            cand = _S._PERSISTENT_DATA_DIR or get_persistent_data_dir(base)
            p = os.path.join(cand, "xb.db")
            init(p)
        except Exception:
            pass
        return _S._DB

# ---- 持久化目录（热重连） ----

def set_persistent_data_dir(path):
    """显式设置或更新持久化数据目录（支持 AstrBot StarTools 官方注入与动态热重连）"""
    if not path:
        return
    path = str(path).strip()
    try:
        os.makedirs(path, exist_ok=True)
    except Exception:
        pass
    _S._PERSISTENT_DATA_DIR = path
    try:
        _S._COLL_CACHE.clear()
    except Exception:
        pass
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    _auto_migrate_and_heal(path, base)
    target_db = os.path.join(path, "xb.db")
    with _S._LOCK:
        if _S._DB is not None and _S._DB_PATH and _S._DB_PATH != target_db:
            try:
                if not flush_all():
                    raise RuntimeError("flush before database switch failed")
                _old_path = _S._DB_PATH
                _old_exists = bool(_old_path) and os.path.isfile(_old_path)
                _tgt_exists = os.path.isfile(target_db)
                if _old_exists and not _tgt_exists:
                    import shutil
                    shutil.copy2(_old_path, target_db)
                try:
                    _S._DB.close()
                except Exception:
                    pass
                _S._DB = None
                init(target_db)
                # 先切目标库再合旧库：旧 merge_from(旧址) 是自合并 no-op，真丢旧数据
                if _old_exists and _tgt_exists:
                    merge_from(_old_path)
            except Exception:
                pass


_MIGRATED_DIRS = set()  # 进程内 once：同目录重复解析不再重跑迁移探测（热切换新目录仍跑）


def _auto_migrate_and_heal(cand, base):
    """自动双向自愈与迁移：把旧数据/图库无损同步迁移到持久化目录"""
    if not cand or not os.path.isdir(cand):
        return
    try:
        _key = os.path.abspath(cand)
        if _key in _MIGRATED_DIRS:
            return
    except Exception:
        _key = ""
    try:
        import shutil
        cand_db = os.path.join(cand, "xb.db")
        cand_nuli = os.path.join(cand, "nuli_slave.db")
        cand_xbbot = os.path.join(cand, "xbbot.db")
        # 兼容历史库名自动平滑迁入标准 xb.db
        if not os.path.isfile(cand_db):
            if os.path.isfile(cand_nuli):
                try:
                    shutil.copy2(cand_nuli, cand_db)
                except Exception:
                    pass
            elif os.path.isfile(cand_xbbot):
                try:
                    shutil.copy2(cand_xbbot, cand_db)
                except Exception:
                    pass
        # 插件根目录下旧数据自愈迁移到持久化目录（绝不反向覆盖已存在的有效用户数据）
        for f in ("xb.db", "nuli_slave.db", "xbbot.db", "config.json", "events.json"):
            src_f = os.path.join(base, "data", f)
            dst_f = os.path.join(cand, "xb.db" if f.endswith(".db") else f)
            if os.path.isfile(src_f) and not os.path.isfile(dst_f):
                try:
                    shutil.copy2(src_f, dst_f)
                except Exception:
                    pass
        # 内置武器图库自愈迁移（仅全新时播种一次；已存在则不动，避免覆盖用户改池/删图；
        # 旧 data/gacha_img 布局继续兼容读取，不强制搬迁）
        try:
            _dst_new = os.path.join(cand, "img", "gacha")
            _dst_old = os.path.join(cand, "gacha_img")
            _has_new = os.path.isdir(_dst_new) and bool(os.listdir(_dst_new))
            _has_old = os.path.isdir(_dst_old) and bool(os.listdir(_dst_old))
            if not _has_new and not _has_old:
                _src = os.path.join(base, "data", "games", "img", "nuli")
                if os.path.isdir(_src):
                    shutil.copytree(_src, _dst_new, dirs_exist_ok=True)
        except Exception:
            pass
        # 兼容旧 groups/wallet 目录自愈
        for sub in ("groups", "wallet"):
            src_sub = os.path.join(base, "data", sub)
            dst_sub = os.path.join(cand, sub)
            if os.path.isdir(src_sub):
                try:
                    shutil.copytree(src_sub, dst_sub, dirs_exist_ok=True)
                except Exception:
                    pass
        try:
            if _key:
                _MIGRATED_DIRS.add(_key)
        except Exception:
            pass
    except Exception:
        pass


def get_persistent_data_dir(plugin_base=""):
    """解析 AstrBot 官方推荐持久化目录 data/plugin_data/astrbot_plugin_xbbot_beta/（测试版独立）
    1. 优先使用 AstrBot 官方 StarTools.get_data_dir()
    2. 多层级智能解析上级 data/plugin_data/
    3. 优雅回退至 plugin_base/data 并保持结构双向自愈
    """
    if _S._PERSISTENT_DATA_DIR and os.path.isdir(_S._PERSISTENT_DATA_DIR):
        return _S._PERSISTENT_DATA_DIR

    base = plugin_base or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if not os.path.isdir(os.path.join(base, "data")) and os.path.isdir(os.path.join(os.path.dirname(base), "data")):
        base = os.path.dirname(base)

    # 1. 官方最高优先级：AstrBot 官方 StarTools.get_data_dir()
    try:
        from astrbot.api.star import StarTools
        official_p = StarTools.get_data_dir()
        if official_p:
            cand = str(official_p)
            os.makedirs(cand, exist_ok=True)
            _S._PERSISTENT_DATA_DIR = cand
            _auto_migrate_and_heal(cand, base)
            return cand
    except Exception:
        pass

    # 2. 向上多级探查 AstrBot 规范 data/plugin_data/astrbot_plugin_xbbot_beta（测试版独立）
    try:
        p = os.path.abspath(base)
        for _ in range(5):
            parent = os.path.dirname(p)
            if not parent or parent == p:
                break
            p_name = os.path.basename(parent)
            if p_name in ("plugins", "astrbot_plugins"):
                grandparent = os.path.dirname(parent)
                gp_name = os.path.basename(grandparent)
                cands = []
                if gp_name == "data":
                    # 如 /root/data/plugins/xbbot -> grandparent 就是 /root/data
                    cands.append(os.path.join(grandparent, "plugin_data", "astrbot_plugin_xbbot_beta"))
                    cands.append(os.path.join(os.path.dirname(grandparent), "data", "plugin_data", "astrbot_plugin_xbbot_beta"))
                else:
                    # 如 /root/astrbot_plugins/xbbot -> grandparent 就是 /root
                    cands.append(os.path.join(grandparent, "data", "plugin_data", "astrbot_plugin_xbbot_beta"))
                    cands.append(os.path.join(grandparent, "plugin_data", "astrbot_plugin_xbbot_beta"))
                for cand in cands:
                    try:
                        os.makedirs(cand, exist_ok=True)
                        _S._PERSISTENT_DATA_DIR = cand
                        _auto_migrate_and_heal(cand, base)
                        return cand
                    except Exception:
                        continue
            p = parent
    except Exception:
        pass

    fallback = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
    os.makedirs(fallback, exist_ok=True)
    _S._PERSISTENT_DATA_DIR = fallback
    _auto_migrate_and_heal(fallback, base)
    return fallback


def init(db_path, config=None):
    try:
        from .app_config import set_config as _apply_cfg  # 延迟导入：破 app_config↔db 循环
    except ImportError:
        _apply_cfg = None
    with _S._LOCK:
        if _S._DB is not None and _S._DB_PATH == db_path:
            if isinstance(config, dict):
                if _apply_cfg is not None:
                    _apply_cfg(config)
            return
        new_db = None
        old_db = _S._DB
        old_path = _S._DB_PATH
        try:
            d = os.path.dirname(db_path)
            if d and not os.path.isdir(d):
                os.makedirs(d, exist_ok=True)
            new_db = sqlite3.connect(db_path, timeout=_S.DB_TIMEOUT, check_same_thread=False)
            new_db.executescript(_SQL_INIT)
            new_db.commit()
            _S._DB = new_db
            _S._DB_PATH = db_path
            close_read_conn()
            if old_db is not new_db:
                _S._ACC_CACHE.clear()
                _S._GROUP_CACHE.clear()
            from .kv import _init_kv_cache
            _init_kv_cache()
            if isinstance(config, dict):
                if _apply_cfg is not None:
                    _apply_cfg(config)
            if old_db is not None and old_db is not new_db:
                try:
                    old_db.close()
                except Exception:
                    pass
        except Exception:
            try:
                if new_db is not None:
                    new_db.rollback()
                    new_db.close()
            except Exception:
                pass
            _S._DB = old_db
            _S._DB_PATH = old_path


def flush_all():
    # 先快照→全写→commit，成功后才清脏标：中途抛错回滚＋标保留，下轮重刷（旧代码先清标后写，失败即永久丢增量）
    with _S._LOCK:
        if _S._DB is None:
            return False
        try:
            acc_items = [(key, a) for key, a in list(_S._ACC_CACHE.items()) if a.dirty]
            grp_items = [(gid, g) for gid, g in list(_S._GROUP_CACHE.items()) if g._dirty]
            _grp_written = []
            _acc_ok = []
            for key, a in acc_items:
                # 逐 key 隔离：毒 key 只跳过自己，不卡死全量落盘（脏保留下轮重试）
                try:
                    # 空 kv 视作清理，避免幽灵账户
                    if not a.kv:
                        _S._DB.execute("DELETE FROM accounts WHERE gid=? AND qq=?", (int(key[0]), int(key[1])))
                    else:
                        _S._DB.execute(
                            "INSERT INTO accounts(gid, qq, data) VALUES(?,?,?) "
                            "ON CONFLICT(gid, qq) DO UPDATE SET data=excluded.data",
                            (int(key[0]), int(key[1]), json.dumps(a.kv, ensure_ascii=False)))
                    _acc_ok.append((key, a))
                except Exception:
                    continue
            for gid, g in grp_items:
                try:
                    dirty_qqs = getattr(g, "_dirty_qqs", None)
                    if dirty_qqs and len(dirty_qqs) > 0 and len(dirty_qqs) < len(g._users):
                        snap = list(dirty_qqs)
                        items = [(qq, g._users.get(qq, {})) for qq in snap]
                    else:
                        snap = None
                        items = list(g._users.items())
                    written = set()
                    for qq, kv in items:
                        if not kv:
                            _S._DB.execute("DELETE FROM groups WHERE gid=? AND qq=?", (int(gid), int(qq)))
                        else:
                            _S._DB.execute(
                                "INSERT INTO groups(gid, qq, data) VALUES(?,?,?) "
                                "ON CONFLICT(gid, qq) DO UPDATE SET data=excluded.data",
                                (int(gid), int(qq), json.dumps(kv, ensure_ascii=False)))
                        written.add(str(qq))
                    _grp_written.append((g, snap, written))
                except Exception:
                    continue
            # 先验 commit 再清标：提交失败全脏保留，下轮重刷
            try:
                _S._DB.commit()
            except Exception:
                _safe_rollback()
                return False
        except Exception:
            _safe_rollback()
            return False
        for _, a in _acc_ok:
            try:
                a.dirty = False
            except Exception:
                pass
        for g, snap, written in _grp_written:
            # 只清本次写盘的快照集：写盘期新标脏保留，下轮再刷
            try:
                if snap is None:
                    for qq in written:
                        g._dirty_qqs.discard(qq)
                else:
                    for qq in snap:
                        g._dirty_qqs.discard(qq)
                if not g._dirty_qqs:
                    g._dirty = False
            except Exception:
                pass
        return True


def merge_from(db_path):
    if not os.path.isfile(db_path):
        return 0
    n = 0
    src = None
    try:
        src = sqlite3.connect(db_path)
        with _S._LOCK:
            for tbl in ("wallet", "accounts", "groups"):
                if not src.execute(
                        "SELECT name FROM sqlite_master WHERE name=?",
                        (tbl,)).fetchone():
                    continue
                # 表名已白名单校验，仍显式分支避免 f-string 注入误判
                if tbl == "wallet":
                    rows = src.execute("SELECT * FROM wallet").fetchall()
                    for r in rows:
                        _S._DB.execute("INSERT OR IGNORE INTO wallet VALUES(?,?,?)", r)
                        n += 1
                elif tbl == "accounts":
                    rows = src.execute("SELECT * FROM accounts").fetchall()
                    for r in rows:
                        _S._DB.execute("INSERT OR IGNORE INTO accounts VALUES(?,?,?)", r)
                        n += 1
                else:
                    rows = src.execute("SELECT * FROM groups").fetchall()
                    for r in rows:
                        _S._DB.execute("INSERT OR IGNORE INTO groups VALUES(?,?,?)", r)
                        n += 1
            if not _safe_commit():
                n = 0
                raise RuntimeError("database merge commit failed")
    except Exception:
        try:
            _safe_rollback()
        except Exception:
            pass
        # n保留已统计数调用方仅记数，不抛（写入降级禁裸抛）
    finally:
        try:
            if src is not None:
                src.close()
        except Exception:
            pass
    return n

__all__ = ["close_read_conn", "flush_all", "get_persistent_data_dir", "init", "merge_from", "set_persistent_data_dir"]
