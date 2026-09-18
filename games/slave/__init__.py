# -*- coding: utf-8 -*-
"""games/slave/ — 奴隶买卖包门面（base 地基/nick 昵称/profile 档案/combat 战力/
trade 交易/social 社交/gacha 抽奖/handler 入口）。对外与旧单文件一致。"""
try:
    from .base import *
    from .nick import *
    from .profile import *
    from .combat import *
    from .trade import *
    from .social import *
    from .gacha import *
    from .handler import *
    from . import base as base
    from . import nick as nick
    from . import profile as profile
    from . import combat as combat
    from . import trade as trade
    from . import social as social
    from . import gacha as gacha
    from . import handler as handler
    from . import slave_state as _state
except ImportError:
    from base import *
    from nick import *
    from profile import *
    from combat import *
    from trade import *
    from social import *
    from gacha import *
    from handler import *
    import base as base
    import nick as nick
    import profile as profile
    import combat as combat
    import trade as trade
    import social as social
    import gacha as gacha
    import handler as handler
    import slave_state as _state

__all__ = ["U", "atk_of", "battle_power", "cd_check", "cd_commit", "cfg", "cfgf", "cfgi", "clear_note_name", "clear_user_slave", "cmd_buy_slave", "cmd_buyslot", "cmd_fight", "cmd_flatter", "cmd_freedom", "cmd_gacha", "cmd_menu", "cmd_myinfo", "cmd_pray", "cmd_protect", "cmd_query", "cmd_rank", "cmd_rank_price", "cmd_rank_sign", "cmd_ransom", "cmd_release", "cmd_revolt", "cmd_starup", "cmd_study", "cmd_torture", "cmd_treasure_menu", "cmd_treasure_up", "cmd_weapon_menu", "cmd_work_collect", "cmd_work_dispatch", "cn_fmt", "cn_parse", "coin_name", "coins_add", "coins_get", "display_name", "exists_user", "fetch_card", "find_qq_by_name", "get_note_name", "handle", "init_slave", "load_events", "log", "mark_known", "protected_until", "save", "set_note_name", "slaves_of", "star_of", "state", "treasures_of", "uget", "uname", "uset", "weapons_of"]


_SUBMODS = (base, nick, profile, combat, trade, social, gacha, handler,)


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
    raise AttributeError(f"slave facade has no attribute {name!r}")
