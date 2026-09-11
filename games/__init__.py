# -*- coding: utf-8 -*-
"""games/ — 纯游玩系统大文件夹。

系统 -> 位置 -> 玩法（统一 `handle(gid, qq, raw)` -> `str | (text, [img]) | None`，
只读 storage/store，不 import astrbot/adapters）：
  slave      slave/              奴隶买卖 / 抽奖 / 排行 / 昵称中枢（已拆包）
  sign       sign.py             签到 / 抽奖 / 新手 / 点赞 / 排行
  bank       bank/               银行 / 监狱 / 红包 / 赌博打劫（已拆包）
  ent        ent/                娱乐会话（30s 自愈，已拆包）
  spirit     spirit/             精灵领养 / 冒险 / 收服 / 进化 / PVP（已拆包：handler 入口＋data_spirit 内置数据）
  ride       ride.py             坐骑商城 + 欢迎撒币
  guild      guild.py            帮派 / 贡献 / 福利 / 帮战
   adventure  adventure.py        14 秘境文字冒险
纯数据：text/ 文案库（text_slave/text_adventure）＋ spirit/data_spirit.py 内置精灵数据。
可调集：config/（slave/spirit/shop 默认值＋公式参数，纯数据，引擎查表，改数即改行为）。
域隔离：包外只经门面拿整包（`from games import spirit`）；包内互引仅限同包；text/config 无导入。
特许例外（只读昵称展示）：adventure/guild/ride/sign/spirit 调 `slave.get_note_name/fetch_card`；
bank 调 slave 做账（函数级懒导入）。除此之外无跨域。
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
