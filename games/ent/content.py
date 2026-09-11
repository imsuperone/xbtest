# -*- coding: utf-8 -*-
"""games/ent·libs（原 ent.py 切分，语义不变；solver24 求解器已并入）."""
import ast as _ast
import random
import re
try:
    from functools import lru_cache as _lru24
except Exception:
    def _lru24(*a, **k):
        def d(f): return f
        return d
try:
    from ...core import storage as ST
except ImportError:
    from core import storage as ST
try:
    from ..config.ent import DEFAULTS as _ENT_DEFAULTS
except ImportError:
    try:
        from games.config.ent import DEFAULTS as _ENT_DEFAULTS  # type: ignore
    except Exception:
        _ENT_DEFAULTS = {}
try:
    from ..config.ent import (CHOUQIAN_P1, CHOUQIAN_P2, CHOUQIAN_P3,
                              MORA_DRAW_BAND, JIELONG_MIN, JIELONG_MAX)
except ImportError:
    from games.config.ent import (CHOUQIAN_P1, CHOUQIAN_P2, CHOUQIAN_P3,  # type: ignore
                                  MORA_DRAW_BAND, JIELONG_MIN, JIELONG_MAX)


def cfgi(sec, key, default=0):
    # 默认值单源：games/config/ent.py DEFAULTS 表命中即用表值（行内兜底仅动态键时生效）
    try:
        if (sec, key) in _ENT_DEFAULTS:
            default = _ENT_DEFAULTS[(sec, key)]
    except Exception:
        pass
    return ST.cfgi(sec, key, default)

_MENU = (
    "🎮 娱乐系统\r\n"
    "━━━━━━━━━━━━━━\r\n"
    "🎋 抽签　　　　　💣 扔炸弹\r\n"
    "🧩 开始接龙　　　🤔 开始急转弯\r\n"
    "🔤 开始猜字谜　　🎲 开始猜数\r\n"
    "❓ 开始答题　　　🃏 二四点\r\n"
    "✊ 猜拳 石头/剪刀/布\r\n"
    "📥 加入XX/退出XX（接龙/猜数/答题/字谜/急转弯/二四点）\r\n"
    "🔚 结束接龙/重置接龙　📊 接龙进度\r\n"
    "━━━━━━━━━━━━━━\r\n"
    "💡 发送对应指令即可游玩"
)




def _fee(gid, qq, kind):
    """娱乐功能消耗金币(娱乐配置__<kind>造价=0 免费)"""
    try:
        c = int(float(ST.cfg("娱乐配置", kind + "造价", "0") or "0"))
    except Exception:
        c = 0
    if c <= 0:
        return None
    if ST.coins_get(gid, qq) < c:
        return "笑~你没有那么多%s（%s需%d）" % (ST.coin_name(), kind, c)
    ST.coins_add(gid, qq, -c)
    return None




def _ent_cost(gid, qq, prefix):
    """通用娱乐消耗：需要金钱 + 消耗体力（0=免费）"""
    need = cfgi("娱乐配置", prefix + "需要金钱", 0)
    tili = cfgi("娱乐配置", prefix + "消耗体力", 0)
    if need and ST.coins_get(gid, qq) < need:
        return f"笑~你没有那么多{ST.coin_name()}（{prefix}需{need}）"
    if tili and ST.acct(gid, qq).int("stamina") < tili:
        return f"体力不足，{prefix}需要{tili}体力！"
    if need:
        ST.coins_add(gid, qq, -need)
    if tili:
        ST.acct_add(gid, qq, "stamina", -tili)
    return None


# ---- 词库/题库（内置可扩展，支持 WebUI 自定义） ----
CHAIN_WORDS = [
    "一帆风顺", "顺水推舟", "舟车劳顿", "顿开茅塞", "塞翁失马", "马到成功",
    "功成名就", "就事论事", "事半功倍", "倍道而行", "行云流水", "水到渠成",
    "成竹在胸", "胸有成竹", "竹报平安", "安居乐业", "业精于勤", "勤能补拙",
    "拙嘴笨舌", "舌战群儒", "儒雅风流", "流光溢彩", "彩云追月", "月白风清",
    "清风明月", "月明星稀", "稀世珍宝", "宝刀未老", "老当益壮", "壮志凌云",
    "云开见日", "日新月异", "异口同声", "声东击西", "西窗剪烛", "烛光摇曳",
    "曳尾涂中", "中流砥柱", "柱石之坚", "坚定不移", "移花接木", "木已成舟",
    "舟中敌国", "国泰民安", "安步当车", "车水马龙", "龙飞凤舞", "舞文弄墨",
    "墨守成规", "规行矩步", "步步为营", "营私舞弊", "弊绝风清", "清净无为",
    "为所欲为", "为虎作伥", "伥鬼不散", "散兵游勇", "勇往直前", "前程似锦",
    "锦上添花", "花好月圆", "圆满完成", "成群结队", "队友合作", "作壁上观",
]


TRICK = [
    ("什么门永远关不上？", "球门"),
    ("什么东西越洗越脏？", "水"),
    ("什么东西有头无脚？", "图钉"),
    ("什么马不能骑？", "海马"),
    ("什么书在书店买不到？", "遗书"),
    ("什么瓜不能吃？", "傻瓜"),
    ("什么布剪不断？", "瀑布"),
    ("什么英文字母最多人喜欢听？", "CD"),
    ("哪一个月有28天？", "每个月"),
    ("小华在偷偷做作业被发现，为什么老师没骂他？", "他在办公室做"),
    ("什么东西倒立后会增加一半？", "6"),
    ("什么东西有5个头但人不觉的它怪呢？", "手脚"),
    ("一个人在沙滩上行走，回头却看不见脚印，为什么？", "倒着走"),
    ("什么车最长？", "堵车"),
    ("什么东西越用越少？", "常识"),
    ("为什么企鹅的肚子是白的？", "手短擦不到"),
    ("什么东西没吃之前是绿的，吃下去是红的，吐出来是黑的？", "西瓜"),
    ("森林里有一条眼镜蛇，可是它从来不咬人，为什么？", "森林里没人"),
    ("什么房子最多人进去却没人出来？", "厕所"),
    ("什么东西天气越热，它爬得越高？", "温度计"),
]


MIRI = [
    ("一口咬掉牛尾巴（打一字）", "告"),
    ("大雨落在横山上（打一字）", "雪"),
    ("十张口，一颗心（打一字）", "思"),
    ("七十二小时（打一字）", "晶"),
    ("一月七日（打一字）", "脂"),
    ("一口咬定（打一字）", "交"),
    ("武（打一字）", "斐"),
    ("九十九（打一字）", "白"),
    ("上下难分（打一字）", "卡"),
    ("田中（打一字）", "十"),
    ("一口吃掉牛尾巴少一点（打一字）", "告"),
    ("一点一横长，一撇到南洋，南洋有个人，只有一寸长（打一字）", "府"),
    ("四面都是山，山山皆相连（打一字）", "田"),
    ("一字十三点，难在如何点（打一字）", "汁"),
    ("皇帝新衣（打一字）", "袭"),
    ("拱猪入门（打一字）", "阂"),
    ("守门员（打一字）", "闪"),
    ("一口咬掉多半截（打一字）", "名"),
]


QUIZ = [
    ("中国最长的河流是？", "长江"),
    ("太阳系最大的行星是？", "木星"),
    ("一公斤棉花和一公斤铁哪个重？", "一样重"),
    ("一年有多少个星期？", "52"),
    ("中国的首都是哪里？", "北京"),
    ("世界上最高的山峰是？", "珠穆朗玛峰"),
    ("一年有多少天（平年）？", "365"),
    ("水在多少度结冰？", "0度"),
    ("中国四大发明不包括哪一个？火药/指南针/造纸术/印刷术/蒸汽机", "蒸汽机"),
    ("三原色是哪三种？", "红黄蓝"),
    ("人体最大的器官是？", "皮肤"),
    ("光速大约是多少万公里每秒？", "30"),
    ("哪个星球被称为红色星球？", "火星"),
    ("《西游记》中孙悟空的兵器叫什么？", "金箍棒"),
    ("一个正方体有几个面？", "6"),
    ("北京奥运会是哪一年？", "2008"),
    ("我国国歌叫什么？", "义勇军进行曲"),
    ("世界上最大的海洋是？", "太平洋"),
    ("九九乘法表 7*8 等于？", "56"),
    ("人体有多少块骨头？", "206"),
    ("月亮围绕什么转？", "地球"),
    ("中国古代四大美女之一貂蝉对应？", "貂蝉"),
    ("清明上河图是谁的作品？", "张择端"),
    ("元素周期表第一个元素是？", "氢"),
]




def _parse_custom_words(raw):
    """解析自定义接龙词库：支持 | 、换行 、，、, 分隔"""
    if not raw or not str(raw).strip():
        return []
    s = str(raw).strip()
    # 尝试 JSON 数组
    if s.startswith("["):
        try:
            import json as _json
            arr = _json.loads(s)
            if isinstance(arr, list):
                return [str(x).strip() for x in arr if str(x).strip()]
        except Exception:
            pass
    # 按分隔符切分
    import re as _re2
    parts = _re2.split(r"[\r\n\|，,、;；]+", s)
    out = []
    for p in parts:
        p = p.strip().strip("【】[]（）()\"' ")
        if p and 2 <= len(p) <= 8:
            out.append(p)
    return out




def _parse_custom_qa(raw):
    """解析自定义题库：每行 问题|答案 或 问题=答案 或 JSON"""
    if not raw or not str(raw).strip():
        return []
    s = str(raw).strip()
    if s.startswith("["):
        try:
            import json as _json
            arr = _json.loads(s)
            res = []
            for it in arr:
                if isinstance(it, (list, tuple)) and len(it) >= 2:
                    res.append((str(it[0]).strip(), str(it[1]).strip()))
                elif isinstance(it, dict):
                    q = it.get("q") or it.get("question") or it.get("题干") or ""
                    a = it.get("a") or it.get("answer") or it.get("答案") or ""
                    if q and a:
                        res.append((str(q).strip(), str(a).strip()))
            if res:
                return res
        except Exception:
            pass
    out = []
    for line in re.split(r"[\r\n]+", s):
        line = line.strip()
        if not line:
            continue
        # 支持 | ｜ -> 分隔、 = 、:、：、->、—
        m = re.split(r"\s*[\|｜]\s*|\s*=\s*|\s*:\s*|：|->|—", line, maxsplit=1)
        if len(m) >= 2 and m[0].strip() and m[1].strip():
            out.append((m[0].strip(), m[1].strip()))
        elif " " in line:
            # 尝试最后空格分隔
            parts = line.rsplit(None, 1)
            if len(parts) == 2 and parts[0].strip() and parts[1].strip():
                out.append((parts[0].strip(), parts[1].strip()))
    return out




_CHAIN_WORDS_CACHE = None
_CHAIN_WORDS_CFG_RAW = None


def _get_chain_words():
    global _CHAIN_WORDS_CACHE, _CHAIN_WORDS_CFG_RAW
    raw = ST.cfg("娱乐配置", "接龙词库", "")
    if _CHAIN_WORDS_CACHE is not None and raw == _CHAIN_WORDS_CFG_RAW:
        return _CHAIN_WORDS_CACHE
    base = list(CHAIN_WORDS)
    try:
        custom = _parse_custom_words(raw)
        if custom:
            seen = set(base)
            for w in custom:
                if w not in seen:
                    base.append(w)
                    seen.add(w)
    except Exception:
        pass
    _CHAIN_WORDS_CACHE = base
    _CHAIN_WORDS_CFG_RAW = raw
    return base




def _get_qa_list(base, cfg_key):
    """题库三取唯一实现：内置 + 自定义 QA 追加（_get_trick/_get_miri/_get_quiz 薄委托，零语义差）"""
    out = list(base)
    try:
        raw = ST.cfg("娱乐配置", cfg_key, "")
        custom = _parse_custom_qa(raw)
        if custom:
            out = out + custom
    except Exception:
        pass
    return out


def _get_trick():
    return _get_qa_list(TRICK, "急转弯题库")


def _get_miri():
    return _get_qa_list(MIRI, "猜字谜题库")


def _get_quiz():
    return _get_qa_list(QUIZ, "答题题库")


# ---- 单游戏锁（同一群同时只能一个会话游戏） ----

# ---- 24 点求解器（原 solver24.py 并入，纯函数无状态） ----

def _safe_eval_24(expr):
    """安全计算二四点算式：仅允许数字 + - * / ( ) ，防注入"""
    try:
        # 仅允许数字、运算符、括号、空格
        if not re.fullmatch(r"[\d\s+\-*/().×÷（）]+", expr):
            return None
        # 统一符号
        expr = expr.replace("×", "*").replace("÷", "/").replace("（", "(").replace("）", ")")
        node = _ast.parse(expr, mode="eval")
        # 兼容 Python3.12+：Constant 替代 Num，动态构造 allowed
        allowed_types = [_ast.Expression, _ast.BinOp, _ast.UnaryOp, _ast.Constant, _ast.Add, _ast.Sub, _ast.Mult, _ast.Div, _ast.USub, _ast.UAdd, _ast.Mod, _ast.Pow, _ast.Load]
        try:
            allowed_types.append(_ast.Num)
        except Exception:
            pass
        allowed = tuple(allowed_types)
        for n in _ast.walk(node):
            if not isinstance(n, allowed):
                # 禁止 Call/Name/Attribute 等
                if isinstance(n, (_ast.Call, _ast.Name, _ast.Attribute, _ast.Subscript)):
                    return None
                return None
        # 禁止幂运算大数
        if "**" in expr:
            return None
        return eval(compile(node, "<24>", "eval"), {"__builtins__": {}}, {})
    except Exception:
        return None


@_lru24(maxsize=8192)
def _can_make_24_cached(key):
    nums_f = [float(x) for x in key]
    def helper(arr):
        if len(arr) == 1:
            return abs(arr[0] - 24) < 1e-6
        # 去重：相同数值对避免重复计算
        seen = set()
        for i in range(len(arr)):
            for j in range(len(arr)):
                if i == j:
                    continue
                a, b = arr[i], arr[j]
                pair = (a,b)
                if pair in seen:
                    continue
                seen.add(pair)
                rest = [arr[k] for k in range(len(arr)) if k != i and k != j]
                for c in (a+b, a-b, a*b, a/b if abs(b) > 1e-9 else None):
                    if c is None:
                        continue
                    if helper(tuple(rest) + (c,)):
                        return True
        return False
    return helper(tuple(nums_f))


def _can_make_24(nums):
    """判断4个数是否能通过 +-*/ 括号算出24（浮点容差）带缓存"""
    try:
        key = tuple(sorted(int(x) for x in nums))
        return _can_make_24_cached(key)
    except Exception:
        return False




_PRE_SOLVABLE = None
def _ensure_pre_solvable():
    global _PRE_SOLVABLE
    if _PRE_SOLVABLE is not None:
        return _PRE_SOLVABLE
    # 轻量预生成：仅用 5 兜底+ 20 随机尝试，避免首次 800 次递归 2s 卡顿
    pool = [[3, 3, 6, 6], [1, 4, 4, 4], [2, 3, 5, 7], [1, 2, 3, 6], [4, 4, 4, 4]]
    seen = {tuple(sorted(x)) for x in pool}
    for _ in range(20):
        cand = [random.randint(1, 13) for _ in range(4)]
        key = tuple(sorted(cand))
        if key in seen:
            continue
        if _can_make_24(cand):
            pool.append(cand)
            seen.add(key)
            if len(pool) >= 20:
                break
    _PRE_SOLVABLE = pool
    return pool


def _generate_solvable_24(max_try=100):
    # 优先预生成池 O(1)，避免每局随机试算 100 次
    try:
        pool = _ensure_pre_solvable()
        if pool:
            return random.choice(pool)
    except Exception:
        pass
    for _ in range(max_try):
        nums = [random.randint(1, 13) for _ in range(4)]
        if _can_make_24(nums):
            return nums
    fallback = [[3, 3, 6, 6], [1, 4, 4, 4], [2, 3, 5, 7], [1, 2, 3, 6], [4, 4, 4, 4]]
    return random.choice(fallback)


__all__ = ["CHAIN_WORDS", "MIRI", "QUIZ", "TRICK", "_CHAIN_WORDS_CACHE", "_CHAIN_WORDS_CFG_RAW", "_MENU", "_PRE_SOLVABLE", "_can_make_24", "_can_make_24_cached", "_ensure_pre_solvable", "_ent_cost", "_fee", "_generate_solvable_24", "_get_chain_words", "_get_miri", "_get_quiz", "_get_trick", "_parse_custom_qa", "_parse_custom_words", "_safe_eval_24", "cfgi",
  "CHOUQIAN_P1", "CHOUQIAN_P2", "CHOUQIAN_P3", "MORA_DRAW_BAND", "JIELONG_MIN", "JIELONG_MAX"]
