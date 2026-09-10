# -*- coding: utf-8 -*-
"""core/adapters.py — AstrBot SDK 唯一收口（原 adapters/astrbot_io.py 并入，零语义差）。
收敛范围（与重构前 main.py:9-14 / platform.py:27 / helpers.py:6 等价行为）：
  事件/消息：AstrMessageEvent, MessageChain, event_message_type, EventMessageType
  组件：Image（可能为 None）, Plain（含降级实现）
  插件基类：Context, Star
  网页：json_response, error_response, request
  工具：StarTools（目录探测用，缺失则为 None，由调用方回退）

用法（包内相对优先，顶层绝对回退，与全仓既有范式一致）：
  try:
      from .adapters import Image, Plain, json_response          # core/ 内模块用
  except ImportError:
      from core.adapters import Image, Plain, json_response     # 顶层直跑用

行为保证：astrbot 缺失时不抛异常，返回降级替身（Plain 回显文本，
json_response 回显 dict），与重构前各文件内联 try/except 完全一致。
"""
try:
    from astrbot.api.event import AstrMessageEvent, MessageChain
except Exception:
    AstrMessageEvent = None
    MessageChain = None

try:
    from astrbot.api.event.filter import event_message_type, EventMessageType
except Exception:
    def event_message_type(*args, **kwargs):
        def _deco(fn):
            return fn
        return _deco

    class EventMessageType:  # type: ignore
        GROUP_MESSAGE = "group"
        PRIVATE_MESSAGE = "private"

try:
    from astrbot.api.message_components import Image
except Exception:
    Image = None

try:
    from astrbot.api.message_components import Plain
except Exception:
    class Plain:  # type: ignore
        def __init__(self, text):
            self.text = text

try:
    from astrbot.api.star import Context, Star
except Exception:
    Context = None

    class Star:  # type: ignore
        def __init__(self, context=None, *args, **kwargs):
            self.context = context

try:
    from astrbot.api.web import json_response, error_response as _orig_error_response, request
except Exception:
    def json_response(data, *args, **kwargs):
        return data

    def _orig_error_response(msg, code=500):
        return {"error": msg, "code": code}

    request = None

try:
    from astrbot.api.star import StarTools
except Exception:
    StarTools = None

__all__ = [
    "AstrMessageEvent", "MessageChain",
    "event_message_type", "EventMessageType",
    "Image", "Plain", "Context", "Star",
    "json_response", "_orig_error_response", "request",
    "StarTools",
]
