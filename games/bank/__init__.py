# -*- coding: utf-8 -*-
"""games/bank/ — bank 系统包门面（原 games/bank.py 单文件切分，对外一致）。"""
try:
    from .common import *
    from .jail import *
    from .redpack import *
    from .transactions import *
    from .handler import *
    from . import common as common
    from . import jail as jail
    from . import redpack as redpack
    from . import transactions as transactions
    from . import handler as handler
except ImportError:
    from common import *
    from jail import *
    from redpack import *
    from transactions import *
    from handler import *
    import common as common
    import jail as jail
    import redpack as redpack
    import transactions as transactions
    import handler as handler

__all__ = ["_MENU", "_acct", "_bail_name", "_cd", "_check_jail", "_disp_name", "_ensure_target_qq", "_extract_transfer_target", "_jail_exp", "_jail_left", "_jail_put", "_jail_release", "_jail_stamp", "_now_s", "_settle_interest", "_show_jail", "cmd_bail", "cmd_deposit", "cmd_force_withdraw", "cmd_gamble", "cmd_go_jail", "cmd_jailbreak", "cmd_out_jail", "cmd_recv_red", "cmd_redpack", "cmd_rob_zone", "cmd_sell_slave", "cmd_transfer", "cmd_withdraw", "handle"]


_SUBMODS = (common, jail, redpack, transactions, handler,)


def __getattr__(name):
    for _m in _SUBMODS:
        try:
            return getattr(_m, name)
        except AttributeError:
            continue
    raise AttributeError(f"facade has no attribute {name!r}")
