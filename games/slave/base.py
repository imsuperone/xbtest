# -*- coding: utf-8 -*-
"""games/slave/base.py — 奴隶包·base（原 slave.py 切分，语义不变）。"""
import re as _re
import time as _time
import random as _random
import datetime as _dt
import threading as _threading
import json as _json
try:
    from ...core import storage as ST
    store = ST
except ImportError:
    from core import storage as ST
    store = ST
try:
    from ...core.keymap import cn_to_en as _cn2en
except ImportError:
    try:
        from core.keymap import cn_to_en as _cn2en  # type: ignore
    except Exception:
        def _cn2en(k): return k
try:
    from ..config.slave import DEFAULTS as _SLAVE_DEFAULTS
except ImportError:
    try:
        from games.config.slave import DEFAULTS as _SLAVE_DEFAULTS  # type: ignore
    except Exception:
        _SLAVE_DEFAULTS = {}
from . import slave_state as _S

def _cmd_lock(gid):
    with _S._CMD_LOCKS_GUARD:
        lk = _S._CMD_LOCKS.get(gid)
        if lk is None:
            lk = _threading.RLock()
            _S._CMD_LOCKS[gid] = lk
        return lk



def cfg(sec, key, default=""):
    # 默认值单源：games/config/slave.py DEFAULTS 表命中即用表值（行内兜底仅动态键时生效）
    try:
        if (sec, key) in _SLAVE_DEFAULTS:
            default = _SLAVE_DEFAULTS[(sec, key)]
    except Exception:
        pass
    return store.cfg(sec, key, default)




def cfgi(sec, key, default=0):
    try:
        return int(float(cfg(sec, key, default)))
    except Exception:
        return default




def cfgf(sec, key, default=0.0):
    try:
        return float(cfg(sec, key, default))
    except Exception:
        return float(default)




def _safe_int(v, default=0):
    try:
        if v is None:
            return default
        s = str(v).strip()
        if not s:
            return default
        return int(float(s))
    except Exception:
        return default




def log(msg):
    ts = _time.strftime("%H:%M:%S")
    line = f"[{ts}] [奴隶买卖] {msg}"
    print(line, flush=True)


# ---- 钱包(现代: SQLite, UTF-8, 事务安全; 旧drea数据可经 store.import_drea_wallet 导入) ----
def coins_get(gid, qq):
    return store.coins_get(gid, qq)




def coins_add(gid, qq, delta):
    return store.coins_add(gid, qq, delta)


# ---- 存档(现代: store/SQLite) ----
def state(gid):
    return store.group(gid)




def save(gid):
    store.save_group(gid)




def U(st, qq):
    qq = str(qq)
    init_price = cfgi("费用配置", "初始身价", 1000)
    if init_price <= 0:
        init_price = 1000
    if not st.has_section(qq):
        st.add_section(qq)
        u = st[qq]
        u["price"] = str(init_price)
        u["owner"] = ""
        u["weapon"] = ""
        u["treasure"] = ""
        u["weapon_exp"] = "0"
        u["slave_slots"] = str(cfgi("设置", "奴隶个数", 5))
        u["protect_until"] = ""
        u["sign_date"] = ""
        u["consecutive_days"] = "0"
    else:
        u = st[qq]
        try:
            cur_p = int(u.get("price", "0") or 0)
            if cur_p <= 0:
                u["price"] = str(init_price)
                if hasattr(st, "mark_dirty"):
                    st.mark_dirty(qq)
        except Exception:
            u["price"] = str(init_price)
    # 宝物旧键迁移（keymap 补映射前按 uXXXX 存的 4 内置宝物持有数/升阶，读时搬新键）
    try:
        _migrate_treasure_keys(u)
    except Exception:
        pass
    return st[qq]



def uget(u, k, d=""):
    return u.get(_cn2en(str(k)), d)




def uset(u, k, v):
    u[_cn2en(str(k))] = str(v)







































def slaves_of(st, qq):
    return [s for s in st.sections()
            if s.isdigit() and uget(st[s], "owner") == str(qq)]




def weapons_of(u):
    return [w for w in uget(u, "weapon").split("|") if w]




def treasures_of(u):
    try:
        _migrate_treasure_keys(u)
    except Exception:
        pass
    return [t for t in uget(u, "treasure").split("|") if t]


# keymap 补齐 4 内置宝物映射前的旧 escapes：读时一次性搬到新键（只搬空键，不覆盖新数据）。
# 旧档（u91d1u87fe 等）持有数/升阶原地保留，老键不清（回滚安全），写一律走新键。
_TREASURE_KEY_MIGRATIONS = (
    ("u91d1u87fe", "jinchan"),
    ("u91d1u87feu5347u9636", "jinchan_stage"),
    ("u7389u5982u610f", "yuruyi"),
    ("u7389u5982u610fu5347u9636", "yuruyi_stage"),
    ("u96f7u516cu9524", "leigongchui"),
    ("u96f7u516cu9524u5347u9636", "leigongchui_stage"),
    ("u591cu660eu73e0", "yemingzhu"),
    ("u591cu660eu73e0u5347u9636", "yemingzhu_stage"),
)


def _migrate_treasure_keys(u):
    try:
        get = u.get
    except Exception:
        return
    for _old, _new in _TREASURE_KEY_MIGRATIONS:
        try:
            _nv = get(_new, "")
            if str(_nv or "").strip() in ("", "0"):
                _ov = get(_old, "")
                if str(_ov or "").strip() not in ("", "0"):
                    u[_new] = str(_ov)
        except Exception:
            continue




def star_of(u, w):
    try:
        return int(uget(u, w + "升星", "0"))
    except Exception:
        return 0




def protected_until(u):
    v = cn_parse(uget(u, "protect_until"))
    return v if v is not None else 0


# ---- 原版中文时间格式 ----
def cn_parse(s):
    if not s:
        return None
    m = _re.match(r"(\d+)年(\d+)月(\d+)日(\d+)时(\d+)分(\d+)秒", str(s))
    if m:
        y, mo, d, h, mi, se = map(int, m.groups())
        try:
            # Validate date
            if not (1970 <= y <= 2100 and 1 <= mo <= 12 and 1 <= d <= 31 and 0 <= h < 24 and 0 <= mi < 60 and 0 <= se < 60):
                return None
            return _dt.datetime(y, mo, d, h, mi, se).timestamp()
        except Exception:
            return None
    try:
        v = float(s)
        if v < 0 or v > 4102444800:
            return None
        return v
    except Exception:
        return None




def cn_fmt(ts):
    if not ts:
        return ""
    dt = _dt.datetime.fromtimestamp(ts)
    return dt.strftime("%Y年%m月%d日%H时%M分%S秒")




def cd_check(u, key, minutes_key):
    # Fix B7: check only, no write; caller commits on success
    minutes = cfgi("间隔配置", minutes_key, 1)
    last = cn_parse(uget(u, key))
    if last is None:
        return True, 0
    left = minutes * 60 - (_time.time() - last)
    if left > 0:
        return False, int(left / 60) + 1
    return True, 0


def cd_commit(u, key):
    uset(u, key, _dt.datetime.now().strftime("%Y年%m月%d日%H时%M分%S秒"))




def _event_delta():
    """奇遇变化量: 在[下限,上限]取有符号随机值后取绝对值, 保证为正且保留随机性"""
    lo = cfgi("费用配置", "变化下限", -200)
    hi = cfgi("费用配置", "变化上限", 1000)
    if lo > hi:
        lo, hi = hi, lo
    return max(1, abs(_random.randint(lo, hi)))


# ============================================================
# 逻辑层 · 第2块: 经济与社交指令
# ============================================================


def _fmt(mins, act):
    return _S.T.COOLDOWN_MIN.format(min=mins, act=act)




























def load_events():
    try:
        with open(_S.EVENTS_JSON, encoding="utf-8") as _f:
            _S.EVENTS = _json.load(_f)
    except Exception:
        _S.EVENTS = []

# 注：import 期不再预读（曾在此调用一次＋init_slave 又读一次）：唯一调用方 init_slave/懒迁移负责加载



__all__ = ["U", "cd_check", "cd_commit", "cfg", "cfgf", "cfgi", "cn_fmt", "cn_parse", "coins_add", "coins_get", "load_events", "log", "protected_until", "save", "slaves_of", "star_of", "state", "treasures_of", "uget", "uset", "weapons_of"]
