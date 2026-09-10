# -*- coding: utf-8 -*-
"""版本号唯一真相源读取器（驻 core/，根 metadata.yaml 仍是唯一手写处）。

唯一手写处：`metadata.yaml` 的 `version` 字段。
全仓 Python 代码一律 `get_version()` 获取，禁止各自硬编码版本号字面量。
（Web 前端显示回退与 CHANGELOG/README 文档行由 `tools/verify_plugin.py` 校验对齐，
打包脚本负责把占位回退刷成当前版。）
"""
import os as _os

_FALLBACK = "0.7.44"
_CACHE = ""


def _plugin_root():
    try:
        return _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
    except Exception:
        return ""


def _meta_path(plugin_base=""):
    try:
        base = plugin_base or _plugin_root()
        p = _os.path.join(base, "metadata.yaml")
        if _os.path.isfile(p):
            return p
    except Exception:
        pass
    return ""


def get_version(plugin_base=""):
    """读 metadata.yaml 的 version，失败回 _FALLBACK。带进程缓存，永不抛错。"""
    global _CACHE
    if _CACHE:
        return _CACHE
    try:
        p = _meta_path(plugin_base)
        if p:
            with open(p, encoding="utf-8") as f:
                for line in f:
                    if line.strip().startswith("version:"):
                        v = line.split(":", 1)[1].strip().strip('"').strip("'")
                        if v:
                            _CACHE = v
                            return v
    except Exception:
        pass
    _CACHE = _FALLBACK
    return _CACHE


def parse_version_tuple(v_str):
    """纪元比较 (epoch, major, minor, patch)：0.10~0.68 为旧纪元 0，其余为 1。
    保证 0.7.0+ 恒大于历史 0.68.x。原 `core/api/updater._parse_version_tuple` 已委托至此。"""
    import re as _re
    m = _re.findall(r"\d+", str(v_str or ""))
    nums = [int(x) for x in m] if m else [0, 0, 0]
    while len(nums) < 3:
        nums.append(0)
    major, minor, patch = nums[0], nums[1], nums[2]
    epoch = 0 if (major == 0 and 10 <= minor <= 68) else 1
    return (epoch, major, minor, patch)
