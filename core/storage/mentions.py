"""storage/at.py — @ 文本解析与 QQ/昵称反查索引（原 store §0）。无 DB。"""
from . import state as _S

def _register_single(qq, name):
    # 单条增量：O(1)，供 main 每消息仅传新 card 使用，避免全量遍历
    q = str(qq); n = str(name or "").strip()
    if not q.isdigit() or not n:
        return
    with _S._AT_NAMES_LOCK:
        old = _S._AT_QQ_TO_NAME.get(q)
        if old == n:
            try:
                _S._AT_NAMES.move_to_end(n)
            except Exception:
                pass
            return
        if old and old in _S._AT_NAMES and _S._AT_NAMES.get(old) == q:
            try:
                del _S._AT_NAMES[old]
            except Exception:
                pass
        _S._AT_QQ_TO_NAME[q] = n
        _S._AT_NAMES[n] = q
        try:
            _S._AT_NAMES.move_to_end(n)
        except Exception:
            pass
        if len(_S._AT_NAMES) > 200000:
            try:
                for _ in range(40000):
                    _S._AT_NAMES.popitem(last=False)
            except Exception:
                for k in list(_S._AT_NAMES.keys())[:40000]:
                    try:
                        del _S._AT_NAMES[k]
                    except Exception:
                        pass
            valid_qqs = set(_S._AT_NAMES.values())
            for kk in list(_S._AT_QQ_TO_NAME.keys()):
                if kk not in valid_qqs:
                    _S._AT_QQ_TO_NAME.pop(kk, None)


def register_names(name_map):
    # 兼容旧全量调用：批量则逐条 _register_single，仍保持增量语义，千群每消息请改单条
    if not isinstance(name_map, dict) or not name_map:
        return
    for q, n in name_map.items():
        _register_single(q, n)

# 对外单条增量别名，供 main 每消息 O(1) 调用
register_name = _register_single


def parse_at(text):
    text = str(text or "")
    m = _S._AT_CQ.search(text)
    if m:
        return m.group(1), _S._AT_CQ.sub("", text).strip()
    m = _S._AT_QQ.search(text)
    if m:
        return m.group(1), _S._AT_QQ.sub("", text, count=1).strip()
    m = _S._AT_NAME.search(text)
    if m:
        key = m.group(1).strip()
        qq = None
        try:
            with _S._AT_NAMES_LOCK:
                qq = _S._AT_NAMES.get(key)
        except Exception:
            qq = _S._AT_NAMES.get(key)
        if qq:
            return qq, _S._AT_NAME.sub("", text, count=1).strip()
    return None, text.strip()

__all__ = ["parse_at", "register_name", "register_names"]
