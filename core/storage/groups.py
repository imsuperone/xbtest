"""storage/groups.py — 群档案增量落盘（原 store §5）。"""
import json
from . import state as _S
from .state import Group, _DirtyDict, _safe_commit, _safe_rollback, _maybe_commit, _force_commit
from .db import _ensure_db

def group(gid):
    gid = str(gid)
    with _S._LOCK:
        try:
            g = _S._GROUP_CACHE.get(gid)
            if g is not None:
                try:
                    _S._GROUP_CACHE.move_to_end(gid)
                except Exception:
                    pass
                return g
        except Exception:
            g = _S._GROUP_CACHE.get(gid)
            if g is not None:
                return g
        _ensure_db()
        rows = []
        if _S._DB is not None:
            # 持锁只做fetchall快照，逐行json/翻译在锁外（千人群5-30ms不再阻塞全插件）
            try:
                rows = _S._DB.execute(
                    "SELECT qq, data FROM groups WHERE gid=?", (int(gid),)).fetchall()
                rows = list(rows)
            except Exception:
                rows = []
    # 锁外解析：CPU密集的json/翻译不占用全局写锁
    users = {}
    for qq, data in rows:
        try:
            d = json.loads(data)
            if isinstance(d, dict) and d:
                # 快判：逐key早停，避免 "".join 1k分配
                need_tr = False
                for kk in d.keys():
                    for ch in kk:
                        if '\u4e00' <= ch <= '\u9fff':
                            need_tr = True
                            break
                    if need_tr:
                        break
                if need_tr:
                    d = _S.translate_dict(d)
            users[str(qq)] = d
        except Exception:
            users[str(qq)] = {}
    with _S._LOCK:
        # 双检：解析期间可能已有他线程回填，直接复用
        try:
            g = _S._GROUP_CACHE.get(gid)
            if g is not None:
                return g
        except Exception:
            pass
        g = Group(gid, users)
        _S._GROUP_CACHE[gid] = g
        try:
            if len(_S._GROUP_CACHE) > _S._GROUP_CACHE_MAX:
                # LRU 淘汰前落盘脏数据；写失败则保留 victim，下轮重试
                _evicted = False
                try:
                    oldest_gid, oldest_g = next(iter(_S._GROUP_CACHE.items()))
                    if oldest_g is not g and getattr(oldest_g, "_dirty", False):
                        # 增量落盘该群
                        dirty_qqs = getattr(oldest_g, "_dirty_qqs", None)
                        if dirty_qqs and len(dirty_qqs) > 0 and len(dirty_qqs) < len(oldest_g._users):
                            items = [(qq, oldest_g._users.get(qq, {})) for qq in list(dirty_qqs)]
                        else:
                            items = list(oldest_g._users.items())
                        for qq2, kv2 in items:
                            if not kv2:
                                _S._DB.execute("DELETE FROM groups WHERE gid=? AND qq=?", (int(oldest_gid), int(qq2)))
                            else:
                                _S._DB.execute("INSERT INTO groups(gid, qq, data) VALUES(?,?,?) ON CONFLICT(gid, qq) DO UPDATE SET data=excluded.data", (int(oldest_gid), int(qq2), json.dumps(kv2, ensure_ascii=False)))
                        oldest_g._dirty = False
                        try:
                            oldest_g._dirty_qqs.clear()
                        except Exception:
                            pass
                        _maybe_commit()
                    _evicted = True
                except Exception:
                    try:
                        _safe_rollback()
                    except Exception:
                        pass
                if _evicted:
                    try:
                        _S._GROUP_CACHE.popitem(last=False)
                    except Exception:
                        pass
        except Exception:
            pass
        return g


def save_group(gid):
    gid = str(gid)
    _ensure_db()
    with _S._LOCK:
        g = _S._GROUP_CACHE.get(gid)
        if g is None or _S._DB is None:
            return
        if not g._dirty:
            return  # 脏检查：千群千人“我的信息”等只读指令不再触发 DB 写
        try:
            # 增量提交：仅脏用户（单群1000人场景 1000次→1次，3.44s→0.02s）。
            # 快照→写→commit→仅清快照集：写盘期间新标脏进新集合，下轮再刷，不吞并发标记。
            dirty_qqs = getattr(g, "_dirty_qqs", None)
            if dirty_qqs is not None and len(dirty_qqs) > 0 and len(dirty_qqs) < len(g._users):
                snap = list(dirty_qqs)
                items = [(qq, g._users.get(qq, {})) for qq in snap]
            else:
                snap = None
                items = list(g._users.items())
            for qq, kv in items:
                if not kv:
                    _S._DB.execute("DELETE FROM groups WHERE gid=? AND qq=?", (int(gid), int(qq)))
                else:
                    _S._DB.execute(
                        "INSERT INTO groups(gid, qq, data) VALUES(?,?,?) "
                        "ON CONFLICT(gid, qq) DO UPDATE SET data=excluded.data",
                        (int(gid), int(qq), json.dumps(kv, ensure_ascii=False)))
            _safe_commit()
            if snap is None:
                g._dirty = False
                try:
                    g._dirty_qqs.clear()
                except Exception:
                    pass
            else:
                try:
                    for qq in snap:
                        g._dirty_qqs.discard(qq)
                    if not g._dirty_qqs:
                        g._dirty = False
                except Exception:
                    pass
        except Exception:
            _safe_rollback()


def user_clear(gid, qq):
    """彻底清除单用户在指定群的全部底层数据（钱包、账户、群组数据）"""
    gid_s = str(gid).strip()
    qq_s = str(qq).strip()
    if not (gid_s.isdigit() and qq_s.isdigit()):
        return False
    gid_i = int(gid_s)
    qq_i = int(qq_s)
    _ensure_db()
    with _S._LOCK:
        # 1. 彻底清除账户内存缓存与脏标记
        for k in ((gid_s, qq_s), (gid_i, qq_i), (gid_s, qq_i), (gid_i, qq_s)):
            a = _S._ACC_CACHE.pop(k, None)
            if a is not None:
                a.dirty = False
                a.kv.clear()

        # 2. 清除群成员内存缓存
        for g_k in (gid_s, gid_i):
            g = _S._GROUP_CACHE.get(g_k)
            if g is not None:
                g._users.pop(qq_s, None)
                g._users.pop(qq_i, None)
                if hasattr(g, "_dirty_qqs") and isinstance(g._dirty_qqs, set):
                    g._dirty_qqs.discard(qq_s)
                    g._dirty_qqs.discard(qq_i)

        # 3. 彻底删除 SQLite 数据库三表数据并强制落盘
        if _S._DB is not None:
            try:
                _S._DB.execute("DELETE FROM wallet WHERE gid=? AND qq=?", (gid_i, qq_i))
                _S._DB.execute("DELETE FROM accounts WHERE gid=? AND qq=?", (gid_i, qq_i))
                _S._DB.execute("DELETE FROM groups WHERE gid=? AND qq=?", (gid_i, qq_i))
                _force_commit()
            except Exception:
                try:
                    _safe_rollback()
                except Exception:
                    pass
    return True

__all__ = ["group", "save_group", "user_clear"]
