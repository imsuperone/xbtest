# -*- coding: utf-8 -*-
"""
统一存储层门面（v0.53 重构）：实现已按职责拆入 storage/（state/db/kv/collections/secrets/
app_config/wallet/accounts/groups/backup/mentions），本文件只做兼容重导出 + 状态委托。

- 历史 `import storage as ST` / `from ... import store` 零改动：函数经星导入，态经 __getattr__ 实时委托。
 - `ST._CONFIG` 等状态通过 `__getattr__` 读取；可重绑状态必须使用显式 setter，不能依赖模块级 `__setattr__`。
"""
try:
    from .mentions import *
    from .db import *
    from .kv import *
    from .collections import *
    from .secrets import *
    from .app_config import *
    from .wallet import *
    from .accounts import *
    from .groups import *
    from .backup import *
    from . import state as _state
    from .state import Acct, Group, _DirtyDict
except ImportError:
    from .mentions import *
    from .db import *
    from .kv import *
    from .collections import *
    from .secrets import *
    from .app_config import *
    from .wallet import *
    from .accounts import *
    from .groups import *
    from .backup import *
    from . import state as _state
    from .state import Acct, Group, _DirtyDict

__all__ = ["register_names","register_name","parse_at","set_config","cfg","cfgi","cfgf","cfg_dict","cfg_scope","coin_name","wake",
           "coins_get","coins_add","txn_coins_acct","txn_two_wallets","txn_two_wallets_acct","rank_batch",
           "Acct","acct","acct_add","acct_save",
           "Group","group","save_group",
           "user_clear","redpack_put","redpack_get","wd_cfg_backup","wd_cfg_restore","clean_expired_kv",
           "coll_merge","coll_migrate","wd_secret_load","wd_secret_set","set_last_backup",
           "init","flush_all","merge_from","get_persistent_data_dir","set_persistent_data_dir",
           "set_config_path","set_astrbot_config","sync_astrbot_config","set_ini","save_config","load_config_from_db",
            "set_backup_dir","backup_user_data","maybe_auto_backup","clean_old_backups",
            "recall_set","recall_get","recall_prefix","dual_attr"]


def dual_attr(anchor, attr, *mod_candidates):
    """双通道导入收口（单名 from-import 的等价一行情）：按序尝试候选模块，取首个成功的属性。

    anchor 取调用方 __package__（相对导入基准，与旧 try/except 语义一致）；
    找不到抛 ImportError。只捕获 ImportError/AttributeError/TypeError（与旧 except ImportError
    同口径，不吞模块内部其它异常）。attr 可能是子模块名（如 from . import data_spirit），
    此时按 from 语义追加 mod.attr 子模块候选（旧写法天然支持，getattr 直取不支持，必须补）。
    首个 storage 双通道块仍保留手写（本函数驻此，无自举问题）。
    """
    import importlib
    _err = None
    for _mod in mod_candidates:
        _cands = [(_mod, False)]
        # from P import N 在 N 为子模块时会自动加载 P.N 并绑定模块本身：补该候选以逐字等价
        _sub = ("." if _mod == "." else _mod + ".") + attr
        if _sub != _mod:
            _cands.append((_sub, True))
        for _cand, _is_sub in _cands:
            try:
                if _cand.startswith("."):
                    _m = importlib.import_module(_cand, anchor or None)
                else:
                    _m = importlib.import_module(_cand)
                return _m if _is_sub else getattr(_m, attr)
            except (ImportError, AttributeError, TypeError) as _e:
                _err = _e
                continue
    raise ImportError(
        "dual_attr cannot import %r from %r" % (attr, mod_candidates)) from _err


try:
    from . import mentions as _m_at
    from . import db as _m_db
    from . import kv as _m_kv
    from . import collections as _m_sidecar
    from . import secrets as _m_secrets
    from . import app_config as _m_cfg
    from . import wallet as _m_wallet
    from . import accounts as _m_acc
    from . import groups as _m_grp
    from . import backup as _m_bak
except ImportError:
    from . import mentions as _m_at
    from . import db as _m_db
    from . import kv as _m_kv
    from . import collections as _m_sidecar
    from . import secrets as _m_secrets
    from . import app_config as _m_cfg
    from . import wallet as _m_wallet
    from . import accounts as _m_acc
    from . import groups as _m_grp
    from . import backup as _m_bak
_SUBMODS = (_m_at, _m_db, _m_kv, _m_sidecar, _m_secrets, _m_cfg,
            _m_wallet, _m_acc, _m_grp, _m_bak)


def __getattr__(name):
    try:
        return getattr(_state, name)
    except AttributeError:
        pass
    for _m in _SUBMODS:
        try:
            return getattr(_m, name)
        except AttributeError:
            continue
    raise AttributeError(f"store.py facade has no attribute {name!r}")
