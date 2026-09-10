# -*- coding: utf-8 -*-
"""games/ent/ — ent 系统包门面（原 games/ent.py 单文件切分，对外一致）。"""
try:
    from .content import *
    from .session import *
    from .handler import *
    from . import content as content
    from . import session as session
    from . import handler as handler
except ImportError:
    from content import *
    from session import *
    from handler import *
    import content as content
    import session as session
    import handler as handler

__all__ = ["CHAIN_WORDS", "MIRI", "QUIZ", "TRICK", "_CHAIN_WORDS_CACHE", "_CHAIN_WORDS_CFG_RAW", "_GAME_KIND_MAP", "_MENU", "_PRE_SOLVABLE", "_active_game", "_can_make_24", "_can_make_24_cached", "_check_single_game", "_clean_expired_game", "_clear_active_game", "_ensure_pre_solvable", "_ent_cost", "_fee", "_generate_solvable_24", "_get_chain_words", "_get_miri", "_get_players", "_get_quiz", "_get_trick", "_is_player", "_join_game", "_parse_custom_qa", "_parse_custom_words", "_play", "_quit_game", "_safe_eval_24", "_set_active_game", "_start_24", "cmd_bomb", "handle"]


_SUBMODS = (content, session, handler,)


def __getattr__(name):
    for _m in _SUBMODS:
        try:
            return getattr(_m, name)
        except Exception:
            continue
    raise AttributeError(f"facade has no attribute {name!r}")
