# -*- coding: utf-8 -*-
"""games/fishing/__init__.py — 钓鱼与迷你世界水族馆系统门面与指令调度器。"""
import re
from . import engine
from .engine import (
    cmd_bait, cmd_pond, cmd_fish, cmd_bucket, cmd_sell,
    cmd_aquarium, cmd_rename_aquarium, cmd_store_fish, cmd_take_fish,
    cmd_clean_water, cmd_steal_fish, cmd_atlas, cmd_menu
)

COMMANDS = (
    "钓鱼系统", "钓鱼菜单", "钓鱼帮助", "打窝列表", "打窝",
    "鱼塘", "钓鱼", "抛竿", "水桶", "出售", "卖鱼",
    "水族馆换水", "清洁水族馆", "水族馆改名", "改名水族馆", "水族馆",
    "存鱼", "取鱼", "偷鱼", "钓鱼图鉴", "鱼类图鉴"
)

__all__ = [
    "COMMANDS", "handle", "cmd_bait", "cmd_pond", "cmd_fish",
    "cmd_bucket", "cmd_sell", "cmd_aquarium", "cmd_rename_aquarium",
    "cmd_store_fish", "cmd_take_fish", "cmd_clean_water", "cmd_steal_fish",
    "cmd_atlas", "cmd_menu"
]

def handle(gid, qq, raw, is_admin=False):
    """钓鱼与水族馆指令路由分发"""
    if not raw:
        return None
    raw_s = str(raw).strip()

    # 兼容前导 @、CQ 码
    text = re.sub(r"^(?:\[CQ:at,qq=\d+[^\]]*\]|@\s*\S+\s*)+", "", raw_s).strip()
    if not text:
        return None

    # 菜单
    if text in ("钓鱼系统", "钓鱼菜单", "钓鱼帮助"):
        return cmd_menu()

    # 打窝 / 打窝列表
    if text in ("打窝列表", "打窝"):
        return cmd_bait(gid, qq, "")
    if text.startswith("打窝"):
        arg = text[2:].strip()
        return cmd_bait(gid, qq, arg)

    # 鱼塘
    if text == "鱼塘":
        return cmd_pond(gid, qq)

    # 钓鱼 / 抛竿 (硬核拦截水桶已满)
    if text in ("钓鱼", "抛竿"):
        return cmd_fish(gid, qq)

    # 水桶
    if text == "水桶":
        return cmd_bucket(gid, qq)

    # 出售 / 卖鱼
    if text in ("出售", "卖鱼"):
        return cmd_sell(gid, qq, "")
    if text.startswith("出售") or text.startswith("卖鱼"):
        arg = text[2:].strip()
        return cmd_sell(gid, qq, arg)

    # 水族馆改名
    if text.startswith("水族馆改名") or text.startswith("改名水族馆"):
        arg = text[5:].strip()
        return cmd_rename_aquarium(gid, qq, arg)

    # 水族馆换水 / 清洁水族馆
    if text in ("水族馆换水", "清洁水族馆"):
        return cmd_clean_water(gid, qq)

    # 存鱼 / 取鱼
    if text.startswith("存鱼"):
        arg = text[2:].strip()
        return cmd_store_fish(gid, qq, arg)
    if text.startswith("取鱼"):
        arg = text[2:].strip()
        return cmd_take_fish(gid, qq, arg)

    # 水族馆
    if text == "水族馆":
        return cmd_aquarium(gid, qq)

    # 偷鱼
    if text.startswith("偷鱼"):
        # 优先提取 CQ 码中的目标 QQ
        cq_m = re.search(r"\[CQ:at,qq=(\d+)\]", raw_s)
        if cq_m:
            target_qq = cq_m.group(1)
        else:
            # 兼容 @123456 或 纯数字
            num_m = re.search(r"(\d{5,12})", text[2:])
            if num_m:
                target_qq = num_m.group(1)
            else:
                target_qq = text[2:].strip().lstrip("@").strip()
        return cmd_steal_fish(gid, qq, target_qq)

    # 图鉴
    if text in ("钓鱼图鉴", "鱼类图鉴"):
        return cmd_atlas(gid, qq)

    return None
