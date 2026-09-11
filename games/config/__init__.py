# -*- coding: utf-8 -*-
"""games/config/ — 各系统可调集（纯数据＋纯常量，禁引引擎/storage，防循环）。
改这里即改行为：数值先算 EV 再动手，探针锁期望。
规则：DEFAULTS 表优先于行内兜底值（wrapper 查表命中即用表值）；
动态键（f-string/玩家群号）不在表内，走行内值。"""
