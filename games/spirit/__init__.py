# -*- coding: utf-8 -*-
"""games/spirit/ — 精灵包门面（handler 玩法入口 / data_spirit 内置数据）。对外与旧单文件一致。"""
try:
    from .handler import *
    from .handler import _SPIRITS, _MAPS, _SHOP
    from . import handler as handler
    from . import data_spirit as data_spirit
except ImportError:
    from handler import *
    from handler import _SPIRITS, _MAPS, _SHOP
    import handler as handler
    import data_spirit as data_spirit

__all__ = ["MENU", "handle", "cmd_adopt", "cmd_gift", "cmd_my", "cmd_view",
           "cmd_shop", "cmd_buy", "cmd_map", "cmd_map_detail", "cmd_backpack",
           "cmd_adventure", "cmd_catch", "cmd_set_active", "cmd_active",
           "cmd_cancel_active", "cmd_ride", "cmd_discard", "cmd_evolve",
           "cmd_pvp", "cmd_rank", "handler", "data_spirit"]


def __getattr__(name):
    try:
        return getattr(handler, name)
    except AttributeError:
        pass
    try:
        return getattr(data_spirit, name)
    except AttributeError:
        pass
    raise AttributeError(f"spirit facade has no attribute {name!r}")
