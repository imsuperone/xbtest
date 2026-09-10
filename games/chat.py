# -*- coding: utf-8 -*-
"""私聊系统: 关键词词库聊天 + 前缀开关 + 黑名单关键字拦截"""
import random

try:
    from .. import storage as ST
except ImportError:
    try:
        from . import storage as ST
    except ImportError:
        import storage as ST

DEMO_REPLIES = [
    "你好呀！我是小白~",
    "在的在的，找我有什么事吗~",
    "今天天气不错，适合玩游戏哦！",
    "我记住你啦，下次慢慢聊~",
    "嘿嘿，收到！",
    "主人有什么吩咐？",
    "这个问题我还在学习中……但是陪你聊天我很开心！",
    "机器人也想吃好吃的呢~",
    "我不太懂,但我会努力学习！",
]

KEYWORDS = {
    "你好": ["你好呀~", "嗨！", "见到你很高兴！"],
    "你是谁": ["我是小白，一款可爱的群机器人！", "小白呀，你忘了嘛？"],
    "吃饭": ["吃饭饭了吗？要按时吃饭哦~", "吃啦吃啦，你呢？"],
    "晚安": ["晚安好梦~", "晚安！梦里见！"],
    "起床": ["早！今天也要元气满满！", "早安~"],
    "天气": ["我这边阳光明媚！（要接入真实天气请配置API）"],
    "谢谢": ["不客气呀~", "嘿嘿，应该的！"],
    "讨厌": ["哎哟，不要这样说人家嘛！"],
    "在吗": ["在呢！", "一直在线哦~"],
}


def handle(qq, raw):
    text = (raw or "").strip()
    if not text:
        return None
    if ST.cfg("私聊配置", "前缀开关", "假") == "真":
        if not (text.startswith("@") or text.startswith("#")):
            return None
        text = text[1:].strip()
    # 黑名单关键字优先拦截
    ban = ST.cfg("私聊配置", "黑名单关键字", "")
    if ban and any(x in text for x in ban.split("|") if x):
        return "抱歉，您的消息包含敏感词汇，已被拦截。"
    # 关键词匹配
    for k, replies in KEYWORDS.items():
        if k in text:
            return random.choice(replies)
    if ST.cfg("私聊配置", "私聊开关", "真") == "真":
        # 轻量随意回复(5秒限频防刷 + 概率缓存，防私聊高频刷屏)
        try:
            _now = __import__("time").time()
            _last = float(ST.recall_get(f"chat_ts_{qq}", "0") or 0)
            if _now - _last < 5:
                return None
        except Exception:
            _now = 0
        try:
            _prob = float(ST.cfg("私聊配置", "回复概率", "0.3") or 0.3)
        except Exception:
            _prob = 0.3
        if random.random() < _prob:
            try:
                ST.recall_set(f"chat_ts_{qq}", str(_now))
            except Exception:
                pass
            return random.choice(DEMO_REPLIES)
    return None
