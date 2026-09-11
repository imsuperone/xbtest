"""storage/wallet.py — 钱包原子读写 + 批量排行（原 store §3/尾部；rank.py 已并入）。"""
import json
from . import state as _S
from .state import Acct, _safe_commit, _safe_rollback
from .db import _ensure_db, _read_conn
from .accounts import acct
from .groups import group
def coins_get(gid, qq):
    _ensure_db()
    # 读副本快路径：不持全局写锁，WAL 读与写并行
    try:
        rc = _read_conn()
        if rc is not None:
            with _S._RLOCK:
                row = rc.execute("SELECT money FROM wallet WHERE gid=? AND qq=?",
                                 (int(gid), int(qq))).fetchone()
            return int(row[0]) if row else 0
    except Exception:
        pass
    with _S._LOCK:
        if _S._DB is None:
            return 0
        try:
            row = _S._DB.execute("SELECT money FROM wallet WHERE gid=? AND qq=?",
                              (int(gid), int(qq))).fetchone()
            return int(row[0]) if row else 0
        except Exception:
            return 0


def coins_add(gid, qq, delta):
    _ensure_db()
    with _S._LOCK:
        if _S._DB is None:
            return 0
        cur = 0
        try:
            row = _S._DB.execute("SELECT money FROM wallet WHERE gid=? AND qq=?",
                              (int(gid), int(qq))).fetchone()
            cur = int(row[0]) if row else 0
        except Exception:
            return cur
        try:
            newv = cur + int(delta)
            if newv < 0:
                newv = 0
            if newv > 100000000000:
                newv = 100000000000
            _S._DB.execute(
                "INSERT INTO wallet(gid, qq, money) VALUES(?,?,?) "
                "ON CONFLICT(gid, qq) DO UPDATE SET money=excluded.money",
                (int(gid), int(qq), newv))
            _safe_commit()
            return newv
        except Exception:
            _safe_rollback()
            return cur


def txn_coins_acct(gid, qq, delta_coins=0, acct_updates=None):
    """原子事务：钱包 delta + 账户 kv 批量更新，同持 _LOCK 一次提交"""
    _ensure_db()
    if acct_updates is None:
        acct_updates = {}
    with _S._LOCK:
        if _S._DB is None:
            return 0
        try:
            # 钱包：单次查询去重（原双查 coins_get+SELECT 已合并）
            row = _S._DB.execute("SELECT money FROM wallet WHERE gid=? AND qq=?", (int(gid), int(qq))).fetchone()
            cur = int(row[0]) if row else 0
            newv = cur + int(delta_coins)
            if newv < 0:
                newv = 0
            if newv > 100000000000:
                newv = 100000000000
            _S._DB.execute(
                "INSERT INTO wallet(gid, qq, money) VALUES(?,?,?) "
                "ON CONFLICT(gid, qq) DO UPDATE SET money=excluded.money",
                (int(gid), int(qq), newv))
            # 账户
            if acct_updates:
                a = _S._ACC_CACHE.get((str(gid), str(qq)))
                if a is None:
                    # 热加载
                    kv = {}
                    row2 = _S._DB.execute("SELECT data FROM accounts WHERE gid=? AND qq=?", (int(gid), int(qq))).fetchone()
                    if row2:
                        try:
                            kv = json.loads(row2[0])
                        except Exception:
                            kv = {}
                    a = Acct(gid, qq, kv)
                    _S._ACC_CACHE[(str(gid), str(qq))] = a
                for k, v in acct_updates.items():
                    a.set(k, str(v))
                _S._DB.execute(
                    "INSERT INTO accounts(gid, qq, data) VALUES(?,?,?) "
                    "ON CONFLICT(gid, qq) DO UPDATE SET data=excluded.data",
                    (int(gid), int(qq), json.dumps(a.kv, ensure_ascii=False)))
                a.dirty = False
            _safe_commit()
            return newv
        except Exception:
            _safe_rollback()
            return 0


# ---- 原子转账 ----

def txn_two_wallets(gid, src_qq, dst_qq, amount):
    """原子双钱包转账：同持 _LOCK 一次提交，避免半成功"""
    if int(amount) <= 0:
        return False
    if str(src_qq) == str(dst_qq):
        return False
    _ensure_db()
    with _S._LOCK:
        if _S._DB is None:
            return False
        try:
            row = _S._DB.execute("SELECT money FROM wallet WHERE gid=? AND qq=?", (int(gid), int(src_qq))).fetchone()
            src_cur = int(row[0]) if row else 0
            if src_cur < int(amount):
                return False
            row2 = _S._DB.execute("SELECT money FROM wallet WHERE gid=? AND qq=?", (int(gid), int(dst_qq))).fetchone()
            dst_cur = int(row2[0]) if row2 else 0
            new_src = src_cur - int(amount)
            new_dst = min(100000000000, dst_cur + int(amount))
            _S._DB.execute("INSERT INTO wallet(gid, qq, money) VALUES(?,?,?) ON CONFLICT(gid, qq) DO UPDATE SET money=excluded.money", (int(gid), int(src_qq), new_src))
            _S._DB.execute("INSERT INTO wallet(gid, qq, money) VALUES(?,?,?) ON CONFLICT(gid, qq) DO UPDATE SET money=excluded.money", (int(gid), int(dst_qq), new_dst))
            _safe_commit()
            return True
        except Exception:
            _safe_rollback()
            return False

__all__ = ["coins_add", "coins_get", "rank_batch", "txn_coins_acct", "txn_two_wallets"]


def rank_batch(gid, field="money", topn=500):
    """统一批量排行：wallet+accounts 单次查询，去 N+1；field: money/cash/sign/stamina/charm/deposit（原 rank.py 并入）"""
    _ensure_db()
    with _S._LOCK:
        if _S._DB is None:
            return []
        try:
            # 持锁只做两次 fetchall 快照，json 解析与排序放锁外
            w_rows = _S._DB.execute("SELECT qq, money FROM wallet WHERE gid=?", (int(gid),)).fetchall()
            w_rows = list(w_rows)
            a_rows = _S._DB.execute("SELECT qq, data FROM accounts WHERE gid=?", (int(gid),)).fetchall()
            a_rows = [(r[0], r[1]) for r in a_rows]
        except Exception:
            return []
    try:
        wallet_map = {str(qq): int(m or 0) for qq, m in w_rows}
        acct_map = {}
        for qq, data in a_rows:
            try:
                kv = json.loads(data) if data else {}
            except Exception:
                kv = {}
            acct_map[str(qq)] = kv
    except Exception:
        return []
    try:
        qqs = set(wallet_map.keys()) | set(acct_map.keys())
        out = []
        for q in qqs:
            kv = acct_map.get(q, {})
            if field == "money":
                v = wallet_map.get(q, 0)
            elif field == "cash":
                v = wallet_map.get(q, 0) + int(float(kv.get("deposit", kv.get("cunkuan", 0)) or 0))
            elif field == "sign":
                v = int(float(kv.get("sign_count", 0) or 0))
            elif field == "stamina":
                v = int(float(kv.get("stamina", 0) or 0))
            elif field == "charm":
                v = int(float(kv.get("charm", 0) or 0))
            elif field == "deposit":
                v = int(float(kv.get("deposit", kv.get("cunkuan", 0)) or 0))
            else:
                v = 0
            out.append((v, q))
        out.sort(reverse=True)
        return out[:topn] if topn else out
    except Exception:
        return []
