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
    """娱乐功能消耗金币与体力(娱乐配置__<kind>造价/消耗体力=0 免费)"""
    try:
        c = max(0, cfgi("娱乐配置", kind + "造价", cfgi("娱乐配置", kind + "需要金钱", 0)))
    except Exception:
        c = 0
    try:
        tili = max(0, cfgi("娱乐配置", kind + "消耗体力", 0))
    except Exception:
        tili = 0
    if c <= 0 and tili <= 0:
        return None
    if c > 0 and ST.coins_get(gid, qq) < c:
        return "笑~你没有那么多%s（%s需%d）" % (ST.coin_name(), kind, c)
    if tili > 0 and ST.acct(gid, qq).int("stamina") < tili:
        return "体力不足，%s需要%d体力！" % (kind, tili)
    with ST._LOCK:
        if c > 0 and ST.coins_get(gid, qq) < c:
            return "笑~你没有那么多%s（%s需%d）" % (ST.coin_name(), kind, c)
        if tili > 0 and ST.acct(gid, qq).int("stamina") < tili:
            return "体力不足，%s需要%d体力！" % (kind, tili)
        updates = {}
        if tili > 0:
            a = ST.acct(gid, qq)
            updates["stamina"] = str(max(0, a.int("stamina") - tili))
        if ST.txn_coins_acct(gid, qq, -c if c > 0 else 0, updates, require_funds=(c > 0)) is None:
            return "数据库繁忙，扣费未成功，请稍后重试。"
    return None




def _ent_cost(gid, qq, prefix):
    """通用娱乐消耗：需要金钱 + 消耗体力（0=免费）。两腿都校验返回值；
    体力扣失败时已扣金钱全额退回（禁半成功）"""
    need = cfgi("娱乐配置", prefix + "需要金钱", 0)
    tili = cfgi("娱乐配置", prefix + "消耗体力", 0)
    if need and ST.coins_get(gid, qq) < need:
        return f"笑~你没有那么多{ST.coin_name()}（{prefix}需{need}）"
    if tili and ST.acct(gid, qq).int("stamina") < tili:
        return f"体力不足，{prefix}需要{tili}体力！"
    # 锁内原子扣两腿（RLock 可重入）
    with ST._LOCK:
        if need and ST.coins_get(gid, qq) < need:
            return f"笑~你没有那么多{ST.coin_name()}（{prefix}需{need}）"
        if tili and ST.acct(gid, qq).int("stamina") < tili:
            return f"体力不足，{prefix}需要{tili}体力！"
        updates = {}
        if tili:
            a = ST.acct(gid, qq)
            updates["stamina"] = str(max(0, a.int("stamina") - tili))
        if ST.txn_coins_acct(gid, qq, -need if need else 0, updates, require_funds=True) is None:
            return "数据库繁忙，扣费未成功，请稍后重试。"
    return None


# ---- 词库/题库（全部独立存放于 data/questions/*.json，支持动态热重载与 WebUI 自定义） ----
# 老词库硬编码已清理，数据源完全收敛至外部 JSON 文件与管理台自定义配置
CHAIN_WORDS = []
TRICK = []
MIRI = []
QUIZ = []




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
_FILE_BANKS_CACHE = {}


def _load_bank_file(filename, fallback_list=None):
    """从 data/questions/<filename> 读取独立题库文件；支持 JSON 与 文本行；带 mtime 缓存实时热重载"""
    import os
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    q_dir = os.path.join(base_dir, "data", "questions")
    target_path = os.path.join(q_dir, filename)

    def _def_fall():
        if fallback_list:
            return list(fallback_list)
        try:
            seed_path = os.path.join(base_dir, "data", "seeds", "questions", filename)
            if os.path.isfile(seed_path):
                import json as _js_seed
                with open(seed_path, "r", encoding="utf-8") as sf:
                    s_data = _js_seed.load(sf)
                if isinstance(s_data, list) and s_data:
                    if filename == "chain.json":
                        return [str(x).strip() for x in s_data if str(x).strip()]
                    _s_qa = []
                    for it in s_data:
                        if isinstance(it, dict):
                            sq = it.get("q") or it.get("question") or it.get("题干") or ""
                            sa = it.get("a") or it.get("answer") or it.get("答案") or ""
                            if sq and sa:
                                _s_qa.append((str(sq).strip(), str(sa).strip()))
                        elif isinstance(it, (list, tuple)) and len(it) >= 2:
                            _s_qa.append((str(it[0]).strip(), str(it[1]).strip()))
                    if _s_qa:
                        return _s_qa
        except Exception:
            pass
        if filename == "chain.json":
            return ["一帆风顺", "顺水推舟", "舟车劳顿", "顿开茅塞"]
        return [("请回答1+1等于几？", "2")]

    if not os.path.isfile(target_path):
        return _def_fall()
    try:
        mtime = os.path.getmtime(target_path)
        cache_entry = _FILE_BANKS_CACHE.get(target_path)
        if cache_entry and cache_entry[0] == mtime:
            return cache_entry[1]
        with open(target_path, "r", encoding="utf-8") as f:
            content = f.read().strip()
        parsed = []
        if filename.endswith(".json"):
            try:
                import json as _js
                data = _js.loads(content)
                if isinstance(data, list):
                    if filename == "chain.json":
                        parsed = [str(x).strip() for x in data if str(x).strip()]
                    else:
                        for it in data:
                            if isinstance(it, dict):
                                q = it.get("q") or it.get("question") or it.get("题干") or ""
                                a = it.get("a") or it.get("answer") or it.get("答案") or ""
                                if q and a:
                                    parsed.append((str(q).strip(), str(a).strip()))
                            elif isinstance(it, (list, tuple)) and len(it) >= 2:
                                parsed.append((str(it[0]).strip(), str(it[1]).strip()))
            except Exception:
                pass
        if not parsed:
            # 兼容非标准 JSON 或自定义文本
            if filename == "chain.json":
                parsed = _parse_custom_words(content)
            else:
                parsed = _parse_custom_qa(content)
        if not parsed:
            parsed = _def_fall()
        _FILE_BANKS_CACHE[target_path] = (mtime, parsed)
        return parsed
    except Exception:
        return _def_fall()


def _get_chain_words():
    global _CHAIN_WORDS_CACHE, _CHAIN_WORDS_CFG_RAW
    raw = ST.cfg("娱乐配置", "接龙词库", "")
    if _CHAIN_WORDS_CACHE is not None and raw == _CHAIN_WORDS_CFG_RAW:
        return _CHAIN_WORDS_CACHE
    base = _load_bank_file("chain.json", CHAIN_WORDS)
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
    """题库三取唯一实现：内置/外部 + 自定义 QA 追加（_get_trick/_get_miri/_get_quiz 薄委托，零语义差）"""
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
    base = _load_bank_file("trick.json", TRICK)
    return _get_qa_list(base, "急转弯题库")


def _get_miri():
    base = _load_bank_file("miri.json", MIRI)
    return _get_qa_list(base, "猜字谜题库")


def _get_quiz():
    base = _load_bank_file("quiz.json", QUIZ)
    return _get_qa_list(base, "答题题库")


def _pick_dedup_qa(kind, gid, qa_list):
    """短时间内问过的问题不能再次出现（群聊独立滑动窗口去重抽题算法）"""
    if not qa_list:
        return ("", "")
    if len(qa_list) == 1:
        return qa_list[0]

    # 动态窗口大小：最大不超过题库总数的 45% 或 35 题
    window_size = max(2, min(35, int(len(qa_list) * 0.45)))
    recent_raw = ST.recall_get(f"ent_recent_{kind}_{gid}", "") or ""
    recent_qs = [q.strip() for q in recent_raw.split("|||") if q.strip()] if recent_raw else []

    # 过滤出不在近期出现过的候选集
    recent_set = set(recent_qs)
    candidates = [qa for qa in qa_list if qa[0] not in recent_set]

    if not candidates:
        # 当题库几乎全被抽完一轮时，清退较早的一半历史，释放新空间
        cut = len(recent_qs) // 2
        recent_qs = recent_qs[cut:]
        recent_set = set(recent_qs)
        candidates = [qa for qa in qa_list if qa[0] not in recent_set]
        if not candidates:
            candidates = qa_list
            recent_qs = []

    chosen = random.choice(candidates)
    recent_qs.append(chosen[0])
    if len(recent_qs) > window_size:
        recent_qs = recent_qs[-window_size:]
    ST.recall_set(f"ent_recent_{kind}_{gid}", "|||".join(recent_qs))
    return chosen


def _pick_dedup_word(kind, gid, word_list):
    """接龙首词短期去重"""
    if not word_list:
        return ""
    if len(word_list) == 1:
        return word_list[0]
    window_size = max(2, min(30, int(len(word_list) * 0.4)))
    recent_raw = ST.recall_get(f"ent_recent_{kind}_{gid}", "") or ""
    recent_ws = [w.strip() for w in recent_raw.split("|||") if w.strip()] if recent_raw else []
    recent_set = set(recent_ws)
    candidates = [w for w in word_list if w not in recent_set]
    if not candidates:
        cut = len(recent_ws) // 2
        recent_ws = recent_ws[cut:]
        recent_set = set(recent_ws)
        candidates = [w for w in word_list if w not in recent_set] or word_list
    chosen = random.choice(candidates)
    recent_ws.append(chosen)
    if len(recent_ws) > window_size:
        recent_ws = recent_ws[-window_size:]
    ST.recall_set(f"ent_recent_{kind}_{gid}", "|||".join(recent_ws))
    return chosen


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
        allowed_types = [_ast.Expression, _ast.BinOp, _ast.UnaryOp, _ast.Constant, _ast.Add, _ast.Sub, _ast.Mult, _ast.Div, _ast.USub, _ast.UAdd, _ast.Load]
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


def _solve_24_expr(nums):
    """返回 4 个数的一个可行 24 点解法算式，无解或异常返回空字符串。"""
    def helper(arr):
        if len(arr) == 1:
            val, expr = arr[0]
            if abs(val - 24) < 1e-6:
                return expr
            return None
        seen = set()
        for i in range(len(arr)):
            for j in range(len(arr)):
                if i == j:
                    continue
                (a, ea), (b, eb) = arr[i], arr[j]
                pair = (a, b)
                if pair in seen:
                    continue
                seen.add(pair)
                rest = [arr[k] for k in range(len(arr)) if k != i and k != j]
                ops = [
                    (a + b, f"({ea}+{eb})"),
                    (a - b, f"({ea}-{eb})"),
                    (a * b, f"({ea}*{eb})"),
                ]
                if abs(b) > 1e-9:
                    ops.append((a / b, f"({ea}/{eb})"))
                for c, ec in ops:
                    res = helper(tuple(rest) + ((c, ec),))
                    if res is not None:
                        return res
        return None
    try:
        init_arr = tuple((float(x), str(int(x))) for x in nums)
        ans = helper(init_arr)
        if ans and ans.startswith("(") and ans.endswith(")"):
            ans = ans[1:-1]
        return ans or ""
    except Exception:
        return ""


__all__ = ["CHAIN_WORDS", "MIRI", "QUIZ", "TRICK", "_CHAIN_WORDS_CACHE", "_CHAIN_WORDS_CFG_RAW", "_MENU", "_PRE_SOLVABLE", "_can_make_24", "_can_make_24_cached", "_ensure_pre_solvable", "_ent_cost", "_fee", "_generate_solvable_24", "_get_chain_words", "_get_miri", "_get_quiz", "_get_trick", "_parse_custom_qa", "_parse_custom_words", "_safe_eval_24", "_solve_24_expr", "_pick_dedup_qa", "_pick_dedup_word", "cfgi",
  "CHOUQIAN_P1", "CHOUQIAN_P2", "CHOUQIAN_P3", "MORA_DRAW_BAND", "JIELONG_MIN", "JIELONG_MAX"]
