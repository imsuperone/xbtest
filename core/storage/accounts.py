"""storage/accounts.py — 账户 LRU 与落盘（原 store §4）。"""
import json
from . import state as _S
from .state import Acct, _safe_commit, _safe_rollback, _maybe_commit
from .db import _ensure_db

def acct(gid, qq):
    key = (str(gid), str(qq))
    with _S._LOCK:
        # OrderedDict LRU：命中则移至末尾
        try:
            a = _S._ACC_CACHE.get(key)
            if a is not None:
                try:
                    _S._ACC_CACHE.move_to_end(key)
                except Exception:
                    pass
                return a
        except Exception:
            a = _S._ACC_CACHE.get(key)
            if a is not None:
                return a
        kv = {}
        _ensure_db()
        row = None
        if _S._DB is not None:
            # 持锁只做fetch，json解析快照后执行，缩短持锁窗口
            try:
                row = _S._DB.execute("SELECT data FROM accounts WHERE gid=? AND qq=?",
                                  (int(gid), int(qq))).fetchone()
                row = (row[0],) if row else None
            except Exception:
                row = None
        if row:
            try:
                kv = json.loads(row[0])
            except Exception:
                kv = {}
        a = Acct(gid, qq, kv)
        _S._ACC_CACHE[key] = a
        # LRU 淘汰：超限则踢最旧
        try:
            if len(_S._ACC_CACHE) > _S._ACC_CACHE_MAX:
                try:
                    old_k, old_a = next(iter(_S._ACC_CACHE.items()))
                    if old_a is not a and getattr(old_a, "dirty", False) and _S._DB is not None:
                        if not old_a.kv:
                            _S._DB.execute("DELETE FROM accounts WHERE gid=? AND qq=?", (int(old_k[0]), int(old_k[1])))
                        else:
                            _S._DB.execute(
                                "INSERT INTO accounts(gid, qq, data) VALUES(?,?,?) "
                                "ON CONFLICT(gid, qq) DO UPDATE SET data=excluded.data",
                                (int(old_k[0]), int(old_k[1]), json.dumps(old_a.kv, ensure_ascii=False)))
                        old_a.dirty = False
                        _maybe_commit()
                except Exception:
                    pass
                _S._ACC_CACHE.popitem(last=False)
        except Exception:
            pass
        return a


def acct_add(gid, qq, name, delta, floor=0):
    a = acct(gid, qq)
    cur = a.int(name)
    newv = cur + int(delta)
    if newv < floor:
        newv = floor
    a.set(name, str(newv))
    acct_save(gid, qq)
    return newv


def acct_save(gid, qq):
    with _S._LOCK:
        a = _S._ACC_CACHE.get((str(gid), str(qq)))
        if a is None or _S._DB is None:
            return
        if not a.dirty:
            return  # 千群只读指令免 DB 写
        try:
            _S._DB.execute(
                "INSERT INTO accounts(gid, qq, data) VALUES(?,?,?) "
                "ON CONFLICT(gid, qq) DO UPDATE SET data=excluded.data",
                (int(gid), int(qq), json.dumps(a.kv, ensure_ascii=False)))
            a.dirty = False
            _safe_commit()
        except Exception:
            _safe_rollback()

__all__ = ["acct", "acct_add", "acct_save"]
