# -*- coding: utf-8 -*-
"""games/ — 纯游玩系统大文件夹。

系统 -> 位置 -> 玩法（统一 `handle(gid, qq, raw)` -> `str | (text, [img]) | None`，
只读 storage/store，不 import astrbot/adapters）：
  slave      slave/              奴隶买卖 / 抽奖 / 排行 / 昵称中枢（已拆包）
  sign       sign.py             签到 / 抽奖 / 新手 / 点赞 / 排行
  bank       bank/               银行 / 监狱 / 红包 / 赌博打劫（已拆包）
  ent        ent/                娱乐会话（30s 自愈，已拆包）
  spirit     spirit.py           精灵领养 / 冒险 / 收服 / 进化 / PVP
  ride       ride.py             坐骑商城 + 欢迎撒币
  guild      guild.py            帮派 / 贡献 / 福利 / 帮战
   adventure  adventure.py        14 秘境文字冒险
纯数据：data_spirit.py / text_slave.py / text_adventure.py。
偏底层运维（超管）已移入 core/superadmin.py，不在此注册。
"""
from . import slave as slave
from . import sign as sign
from . import bank as bank
from . import ent as ent
from . import spirit as spirit
from . import ride as ride
from . import guild as guild
from . import adventure as adventure

__all__ = ["slave", "sign", "bank", "ent", "spirit",
           "ride", "guild", "adventure"]
