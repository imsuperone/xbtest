# -*- coding: utf-8 -*-
"""商城可调集：坐骑内置商城＋武器池常量。图片文件在池目录，属性在 weapon_attrs sidecar；
这里只放结构性常量（顺序/白名单/内置售价），改完重载即生效。抽奖券价格已在
slave_state._GACHA_COST_DEF 单源，不搬（消费方 slave/gacha.py 经 _S. 取用）。"""

# 宝物实效类型（商城图鉴.treasures {名: {type, value, desc}}；老 treasure_effects 只读兼容）
# atk=攻击加成计入主人战力；shield=打架护盾；pardon=造反免罪；
# work=打工工资加成%；worth=身价加成%（战斗力身价部分）；空=纯收藏
TREASURE_TYPES = ("", "atk", "shield", "pardon", "work", "worth")

# 稀有度陈列顺序（武器池页签/校验共用）
POOL_RARS = ("SSR", "SR", "R")

# 武器池上传图片白名单
POOL_IMG_EXTS = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp")

# 坐骑纯价格表（按名取价用；与 RIDE_SHOP 价格保持一致，改价两处同改）
RIDE_PRICES = {
    "企鹅": 213250, "伞兵": 500000, "宝驴": 1000000, "保时捷": 1500000,
    "法拉利": 1500000, "玛莎拉蒂": 1500000, "劳斯莱斯": 1500000,
    "布加迪威龙": 1500000, "私人航空": 5000000, "老八": 500000,
}
# 坐骑内置商城 {名: {price, img}}：未自定义（商城图鉴.ride_shop 为空）时回退此表
RIDE_SHOP = {
    "企鹅": {"price": 213250, "img": "data/games/img/rides/企鹅.jpg"},
    "伞兵": {"price": 500000, "img": "data/games/img/rides/伞兵.jpg"},
    "宝驴": {"price": 1000000, "img": "data/games/img/rides/宝驴.jpg"},
    "保时捷": {"price": 1500000, "img": "data/games/img/rides/保时捷.jpg"},
    "法拉利": {"price": 1500000, "img": "data/games/img/rides/法拉利.jpg"},
    "玛莎拉蒂": {"price": 1500000, "img": "data/games/img/rides/玛莎拉蒂.jpg"},
    "劳斯莱斯": {"price": 1500000, "img": "data/games/img/rides/劳斯莱斯.jpg"},
    "布加迪威龙": {"price": 1500000, "img": "data/games/img/rides/布加迪威龙.jpg"},
    "私人航空": {"price": 5000000, "img": "data/games/img/rides/私人航空.jpg"},
    "老八": {"price": 500000, "img": "data/games/img/rides/老八.jpg"},
}
