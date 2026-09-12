# -*- coding: utf-8 -*-
"""
统一存储层门面（v0.53 重构）：实现已按职责拆入 storage/（state/db/kv/collections/secrets/
app_config/wallet/accounts/groups/backup/mentions），本文件只做兼容重导出 + 状态委托。

- 历史 `import storage as ST` / `from ... import store` 零改动：函数经星导入，态经 __getattr__ 实时委托。
- `ST._CONFIG` 等可重绑态永远新鲜（set_config 重绑后依然一致）；`ST._last_backup = x` 类外部写入经 __setattr__ 转交 state。
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
           "coins_get","coins_add","txn_coins_acct","txn_two_wallets","rank_batch",
           "Acct","acct","acct_add","acct_save",
           "Group","group","save_group",
           "redpack_put","redpack_get",
           "init","flush_all","merge_from","get_persistent_data_dir","set_persistent_data_dir",
           "set_config_path","set_astrbot_config","sync_astrbot_config","set_ini","save_config","load_config_from_db",
           "set_backup_dir","backup_user_data","maybe_auto_backup","clean_old_backups",
           "recall_set","recall_get","recall_prefix"]


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


def __setattr__(name, value):
    if name.startswith("__") and name.endswith("__"):
        globals()[name] = value
        return
    try:
        if name in globals():
            globals()[name] = value
            return
    except Exception:
        pass
    try:
        setattr(_state, name, value)
    except Exception:
        globals()[name] = value
