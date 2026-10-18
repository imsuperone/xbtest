# -*- coding: utf-8 -*-
"""questions API - 题库/词库管理（急转弯、猜字谜、答题、成语接龙 在线查看与自由增删改）"""
import os
import json
try:
    from ..adapters import json_response
except ImportError:
    from core.adapters import json_response  # type: ignore
from .web_utils import _err, get_req_json, get_req_query, no_cache_response

_BANK_MAP = {
    "trick": {"file": "trick.json", "name": "急转弯", "is_qa": True},
    "miri": {"file": "miri.json", "name": "猜字谜", "is_qa": True},
    "quiz": {"file": "quiz.json", "name": "知识问答", "is_qa": True},
    "chain": {"file": "chain.json", "name": "成语接龙", "is_qa": False},
}


def _get_q_dir():
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    q_dir = os.path.join(base_dir, "data", "questions")
    os.makedirs(q_dir, exist_ok=True)
    return q_dir


async def handle_questions_list(request=None):
    """读取题库列表（支持单独查某一库或全部返回）"""
    try:
        bank_key = str(get_req_query(request, "bank", "")).strip().lower()
        q_dir = _get_q_dir()
        result = {}

        targets = [bank_key] if bank_key in _BANK_MAP else list(_BANK_MAP.keys())
        for b in targets:
            meta = _BANK_MAP[b]
            fpath = os.path.join(q_dir, meta["file"])
            items = []
            if os.path.isfile(fpath):
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        items = json.load(f)
                except Exception as e:
                    items = []
            result[b] = {
                "id": b,
                "name": meta["name"],
                "file": meta["file"],
                "is_qa": meta["is_qa"],
                "total": len(items) if isinstance(items, list) else 0,
                "items": items if isinstance(items, list) else []
            }

        return no_cache_response(json_response({"ok": True, "banks": result}))
    except Exception as e:
        return _err(f"读取题库失败: {e}")


async def handle_questions_save(request=None):
    """保存指定题库列表"""
    try:
        data = await get_req_json(request)
        if not isinstance(data, dict):
            return _err("参数格式无效", 400)
        bank = str(data.get("bank", "")).strip().lower()
        if bank not in _BANK_MAP:
            return _err(f"不支持的题库类型: {bank}", 400)

        meta = _BANK_MAP[bank]
        raw_items = data.get("items", [])
        if not isinstance(raw_items, list):
            return _err("题库数据必须是数组", 400)

        cleaned = []
        if meta["is_qa"]:
            for it in raw_items:
                if isinstance(it, dict):
                    q = str(it.get("q", "")).strip()
                    a = str(it.get("a", "")).strip()
                    if q:
                        cleaned.append({"q": q, "a": a})
                elif isinstance(it, (list, tuple)) and len(it) >= 2:
                    q = str(it[0]).strip()
                    a = str(it[1]).strip()
                    if q:
                        cleaned.append({"q": q, "a": a})
        else:
            for it in raw_items:
                s = str(it).strip()
                if s:
                    cleaned.append(s)

        q_dir = _get_q_dir()
        fpath = os.path.join(q_dir, meta["file"])
        tmp_path = fpath + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(cleaned, f, ensure_ascii=False, indent=2)
        if os.path.isfile(fpath):
            os.replace(tmp_path, fpath)
        else:
            os.rename(tmp_path, fpath)

        return json_response({
            "ok": True,
            "msg": f"已成功保存「{meta['name']}」题库，共 {len(cleaned)} 条",
            "bank": bank,
            "total": len(cleaned)
        })
    except Exception as e:
        return _err(f"保存题库失败: {e}")
