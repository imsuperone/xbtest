# -*- coding: utf-8 -*-
"""AstrBot 插件入口（必须驻留插件根，AstrBot 只认 main.py）。

主类必须定义在本文件：Star 靠 __init_subclass__ 按定义模块自动注册，
旧版扫描只认类名以 Plugin 结尾 / 命名为 Main 的类。逻辑全在 core/app.py 的 XbBot，
此处 Main 仅做入口声明 + 消息入口装饰（装饰器决定 handler 归属模块，必须在 main.py）。
"""
try:
    from .core.app import XbBot, handle, PLUGIN_ID, PLUGIN_VERSION, PLUGIN_DESC
except ImportError:
    from core.app import XbBot, handle, PLUGIN_ID, PLUGIN_VERSION, PLUGIN_DESC  # type: ignore

try:
    from astrbot.api.event import AstrMessageEvent
    from astrbot.api.event.filter import EventMessageType, event_message_type
except Exception:
    AstrMessageEvent = object  # type: ignore

    class EventMessageType:  # type: ignore
        GROUP_MESSAGE = 1
        PRIVATE_MESSAGE = 2

    def event_message_type(*_a, **_k):  # type: ignore
        def _deco(fn):
            return fn
        return _deco


class Main(XbBot):
    """小白测试版入口主类（AstrBot Star 注册用，逻辑继承 XbBot，零重复）。"""


    @event_message_type(EventMessageType.GROUP_MESSAGE)
    async def on_message(self, event: AstrMessageEvent):
        async for r in super().on_message(event):
            yield r


__all__ = ["Main", "XbBot", "handle", "PLUGIN_ID", "PLUGIN_VERSION", "PLUGIN_DESC"]
