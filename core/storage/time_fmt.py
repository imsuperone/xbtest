# -*- coding: utf-8 -*-
"""冷却时间与时长统一格式化模块。"""

def format_cd_time(left_seconds: float) -> str:
    """格式化冷却剩余时间：
    - 小于 1 分钟（< 60s）：精确到秒，如 '45秒'、'12秒'、'1秒'；
    - 大于等于 1 分钟（>= 60s）：显示分钟（可不显示秒），如 '3分钟'；
    - 大于等于 60 分钟：显示小时与分钟，如 '1小时15分钟' 或 '2小时'。
    """
    total_sec = int(max(1, round(float(left_seconds or 0))))
    if total_sec < 60:
        return f"{total_sec}秒"
    mins = total_sec // 60
    if mins < 60:
        return f"{mins}分钟"
    hrs = mins // 60
    rem_mins = mins % 60
    if rem_mins > 0:
        return f"{hrs}小时{rem_mins}分钟"
    return f"{hrs}小时"

__all__ = ["format_cd_time"]
