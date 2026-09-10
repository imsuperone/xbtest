# -*- coding: utf-8 -*-
"""games/slave/slave_state.py — 奴隶包共享态唯一家（原 slave.py 顶层数据）。
可重绑态（BOT_UIN/EVENTS）经 _S. 访问；门面 __getattr__ 实时委托。"""
try:
    from ..text_slave import *  # noqa: F401,F403
except ImportError:
    try:
        from text_slave import *  # type: ignore  # noqa: F401,F403
    except Exception:
        pass
BOT_UIN = ""   # engine overwrites at runtime
import os as _os
import threading as _threading
STAR_ATK = [100, 200, 400, 600, 800, 1600]  # 0-5星
MAX_PRICE = 1000000
_CMD_LOCKS = {}
_CMD_LOCKS_GUARD = _threading.Lock()
try:
    from ... import storage as ST
    store = ST
except ImportError:
    try:
        from .. import storage as ST
        store = ST
    except ImportError:
        import storage as ST
        store = ST
def _resolve_persistent_data_dir():
    if hasattr(store, "get_persistent_data_dir"):
        return store.get_persistent_data_dir(_BASE)
    return _os.path.join(_BASE, "data")

_BASE    = _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))  # 包深+1  # 插件根
DATA_DIR = _resolve_persistent_data_dir()
GROUPS_DIR = _os.path.join(DATA_DIR, "groups")                     # 兼容旧目录(迁移用)
WALLET_DIR = _os.path.join(DATA_DIR, "wallet")                     # 兼容旧目录(迁移用)
DB_PATH = _os.path.join(DATA_DIR, "xb.db")                         # 现代存储(SQLite)
CONFIG_JSON = _os.path.join(DATA_DIR, "config.json")               # 现代配置(JSON)
GACHA_DIR = _os.path.join(DATA_DIR, "img", "gacha")
EVENTS_JSON = _os.path.join(DATA_DIR, "events.json")
NOTE_NAMES = {}   # qq -> card/nickname (由适配层注入，跨群最新兜底，仅兼容展示)
NOTE_NAMES_BY_GROUP = {}
NOTE_NAMES_REV = {}
_KNOWN = {}       # gid -> set(qq) 记录本群出现过的成员(@目标/发送者/已开户), 用于判断"是否存在人"
EVENTS = []
import types as _types
_tmap = {k: v for k, v in dict(globals()).items() if k.isupper() and not k.startswith("_")}
for _k2, _v2 in list(_tmap.items()):
    if _k2.startswith("T_"):
        _tmap.setdefault(_k2[2:], _v2)
T = _types.SimpleNamespace(**_tmap)
# 注：首轮 setdefault 已补齐全部 T_ 去前缀键，第二轮为空转，已删（零语义差）

_GACHA_CACHE = {}
_GACHA_CACHE_TS = {}  # 分 rar 独立 TTL，避免 SSR 刷新污染 R
_GACHA_TTL = 60.0  # 60s 刷新，千群每消息 listdir 1507次→0次
_GACHA_LABEL = {1: "单抽", 10: "十连抽", 30: "三十连抽", 50: "五十连抽"}
_GACHA_COST_KEY = {1: "抽武器花费", 10: "十连抽花费", 30: "三十连抽花费", 50: "五十连抽花费"}
_GACHA_COST_DEF = {1: 1988, 10: 18800, 30: 56000, 50: 92000}
