# -*- coding: utf-8 -*-
"""questions API - 题库/词库管理（急转弯、猜字谜、答题、成语接龙 在线查看、自由增删改与全量/单库自由导入导出）"""
import os
import json
import re
import time
from ..adapters import json_response
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


def _clean_items(bank, raw_items):
    """规范化清洗词条数据"""
    meta = _BANK_MAP.get(bank, {})
    cleaned = []
    if meta.get("is_qa", True):
        for it in (raw_items or []):
            if isinstance(it, dict):
                q = str(it.get("q") or it.get("question") or it.get("题干") or "").strip()
                a = str(it.get("a") or it.get("answer") or it.get("答案") or "").strip()
                if q:
                    cleaned.append({"q": q, "a": a})
            elif isinstance(it, (list, tuple)) and len(it) >= 2:
                q = str(it[0]).strip()
                a = str(it[1]).strip()
                if q:
                    cleaned.append({"q": q, "a": a})
    else:
        for it in (raw_items or []):
            s = str(it).strip()
            if s:
                cleaned.append(s)
    return cleaned


def _merge_items(bank, base, incoming):
    """合并词条并去重"""
    meta = _BANK_MAP.get(bank, {})
    is_qa = meta.get("is_qa", True)
    out = list(base)
    if is_qa:
        seen = {item.get("q", "").strip().lower() for item in base if isinstance(item, dict)}
        for it in incoming:
            qk = it.get("q", "").strip().lower()
            if qk not in seen:
                out.append(it)
                seen.add(qk)
    else:
        seen = {str(item).strip().lower() for item in base}
        for it in incoming:
            sk = str(it).strip().lower()
            if sk not in seen:
                out.append(it)
                seen.add(sk)
    return out


def _parse_text_items(bank, text):
    """解析纯文本导入（TXT/CSV），支持多种分隔符"""
    meta = _BANK_MAP.get(bank, {})
    is_qa = meta.get("is_qa", True)
    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
    out = []
    if is_qa:
        for ln in lines:
            # 兼容多种常用分隔符：---- / ==== / \t / | / —— / : / ： / 逗号 / 空格
            q, a = "", ""
            for sep in ["----", "====", "\t", "|", "——", " - ", " : ", "：", ","]:
                if sep in ln:
                    parts = ln.split(sep, 1)
                    q = parts[0].strip()
                    a = parts[1].strip()
                    break
            if not q and " " in ln:
                parts = ln.rsplit(" ", 1)
                q = parts[0].strip()
                a = parts[1].strip()
            if q:
                out.append({"q": q, "a": a})
    else:
        for ln in lines:
            # 成语接龙：每行一个词，或空格/逗号分隔多个
            for w in re.split(r"[\s,，、|/]+", ln):
                w = w.strip()
                if w:
                    out.append(w)
    return out


def _write_bank_file(fpath, items):
    """安全原子写入题库文件（同时镜像写入 AstrBot 规范持久化目录，升级绝不丢失）"""
    tmp_path = fpath + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
    if os.path.isfile(fpath):
        os.replace(tmp_path, fpath)
    else:
        os.rename(tmp_path, fpath)

    # 同步镜像写入持久化目录
    try:
        from .. import storage as ST
        pers = ST.get_persistent_data_dir() if hasattr(ST, "get_persistent_data_dir") else ""
        if pers:
            pq_dir = os.path.join(pers, "data", "questions")
            os.makedirs(pq_dir, exist_ok=True)
            p_target = os.path.join(pq_dir, os.path.basename(fpath))
            if os.path.abspath(p_target) != os.path.abspath(fpath):
                p_tmp = p_target + ".tmp"
                with open(p_tmp, "w", encoding="utf-8") as pf:
                    json.dump(items, pf, ensure_ascii=False, indent=2)
                if os.path.isfile(p_target):
                    os.replace(p_tmp, p_target)
                else:
                    os.rename(p_tmp, p_target)
    except Exception:
        pass


def _clear_runtime_cache():
    """清除娱乐系统运行时的题库缓存，使其即时热重载"""
    try:
        try:
            from ...games.ent import content as _ent_content
        except (ImportError, ValueError):
            from ...ent import content as _ent_content  # type: ignore
        if hasattr(_ent_content, "_FILE_BANKS_CACHE") and isinstance(_ent_content._FILE_BANKS_CACHE, dict):
            _ent_content._FILE_BANKS_CACHE.clear()
        if hasattr(_ent_content, "_CHAIN_WORDS_CACHE"):
            _ent_content._CHAIN_WORDS_CACHE = None
    except Exception:
        pass


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
                except Exception:
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

        cleaned = _clean_items(bank, raw_items)
        q_dir = _get_q_dir()
        fpath = os.path.join(q_dir, meta["file"])
        _write_bank_file(fpath, cleaned)
        _clear_runtime_cache()

        return json_response({
            "ok": True,
            "msg": f"已成功保存「{meta['name']}」题库，共 {len(cleaned)} 条",
            "bank": bank,
            "total": len(cleaned)
        })
    except Exception as e:
        return _err(f"保存题库失败: {e}")


async def handle_questions_export(request=None):
    """导出题库：支持单库或全部四大题库打包导出"""
    try:
        bank_key = str(get_req_query(request, "bank", "")).strip().lower()
        if not bank_key:
            try:
                body = await get_req_json(request)
                if isinstance(body, dict):
                    bank_key = str(body.get("bank", "")).strip().lower()
            except Exception:
                pass
        q_dir = _get_q_dir()

        if bank_key in _BANK_MAP:
            meta = _BANK_MAP[bank_key]
            fpath = os.path.join(q_dir, meta["file"])
            items = []
            if os.path.isfile(fpath):
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        items = json.load(f)
                except Exception:
                    items = []
            return json_response({
                "ok": True,
                "app": "astrbot_plugin_xbbot_beta",
                "kind": "question_bank",
                "bank": bank_key,
                "name": meta["name"],
                "version": 1,
                "exported_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "total": len(items) if isinstance(items, list) else 0,
                "items": items if isinstance(items, list) else []
            })
        else:
            banks = {}
            for b, meta in _BANK_MAP.items():
                fpath = os.path.join(q_dir, meta["file"])
                items = []
                if os.path.isfile(fpath):
                    try:
                        with open(fpath, "r", encoding="utf-8") as f:
                            items = json.load(f)
                    except Exception:
                        items = []
                banks[b] = {
                    "name": meta["name"],
                    "is_qa": meta["is_qa"],
                    "total": len(items) if isinstance(items, list) else 0,
                    "items": items if isinstance(items, list) else []
                }
            return json_response({
                "ok": True,
                "app": "astrbot_plugin_xbbot_beta",
                "kind": "questions_all",
                "version": 1,
                "exported_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "banks": banks
            })
    except Exception as e:
        return _err(f"导出题库失败: {e}")


async def handle_questions_import(request=None):
    """题库导入：支持单库/全量包、JSON/TXT格式、覆盖/追加模式"""
    try:
        data = await get_req_json(request)
        if not isinstance(data, dict):
            return _err("参数格式无效", 400)
        mode = str(data.get("mode", "replace")).strip().lower()
        q_dir = _get_q_dir()

        # 1. 检查是否为全量包多库导入
        raw_banks = data.get("banks")
        if isinstance(raw_banks, dict):
            res_summary = {}
            for b, b_data in raw_banks.items():
                if b not in _BANK_MAP:
                    continue
                meta = _BANK_MAP[b]
                raw_items = b_data.get("items", []) if isinstance(b_data, dict) else (b_data if isinstance(b_data, list) else [])
                fpath = os.path.join(q_dir, meta["file"])
                cur_items = []
                if mode == "append" and os.path.isfile(fpath):
                    try:
                        with open(fpath, "r", encoding="utf-8") as f:
                            cur_items = json.load(f)
                    except Exception:
                        cur_items = []
                new_items = _clean_items(b, raw_items)
                merged = _merge_items(b, cur_items, new_items) if mode == "append" else new_items
                _write_bank_file(fpath, merged)
                res_summary[b] = len(merged)
            _clear_runtime_cache()
            return json_response({
                "ok": True,
                "msg": f"全量题库已成功导入！共更新 {len(res_summary)} 个题库分类",
                "banks": res_summary
            })

        # 2. 单库导入
        bank = str(data.get("bank", "")).strip().lower()
        if bank not in _BANK_MAP:
            return _err(f"不支持的题库类型: {bank}", 400)
        meta = _BANK_MAP[bank]

        raw_items = data.get("items")
        raw_text = data.get("text", "")
        if raw_items is None and raw_text:
            raw_items = _parse_text_items(bank, str(raw_text))
        if not isinstance(raw_items, list):
            return _err("题库数据必须是数组或文本内容", 400)

        fpath = os.path.join(q_dir, meta["file"])
        cur_items = []
        if mode == "append" and os.path.isfile(fpath):
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    cur_items = json.load(f)
            except Exception:
                cur_items = []

        new_items = _clean_items(bank, raw_items)
        merged = _merge_items(bank, cur_items, new_items) if mode == "append" else new_items
        _write_bank_file(fpath, merged)
        _clear_runtime_cache()

        added_cnt = len(merged) - len(cur_items) if mode == "append" else len(merged)
        action_desc = "追加合并" if mode == "append" else "覆盖导入"
        return json_response({
            "ok": True,
            "msg": f"已成功{action_desc}「{meta['name']}」题库，当前总计 {len(merged)} 条（导入 {len(new_items)} 条）",
            "bank": bank,
            "total": len(merged),
            "added": added_cnt
        })
    except Exception as e:
        return _err(f"导入题库失败: {e}")


async def handle_questions_reset(request=None):
    """恢复题库为系统默认种子（支持指定单独题库或全部恢复）"""
    try:
        data = await get_req_json(request) if request else {}
        if not isinstance(data, dict):
            data = {}
        bank = str(data.get("bank", "")).strip().lower()

        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        seed_dir = os.path.join(base_dir, "data", "seeds", "questions")
        q_dir = _get_q_dir()

        targets = [bank] if bank in _BANK_MAP else list(_BANK_MAP.keys())
        restored = {}

        for b in targets:
            meta = _BANK_MAP[b]
            seed_file = os.path.join(seed_dir, meta["file"])
            target_file = os.path.join(q_dir, meta["file"])
            if not os.path.isfile(seed_file):
                continue
            with open(seed_file, "r", encoding="utf-8") as f:
                content = f.read()
            tmp_path = target_file + ".tmp"
            with open(tmp_path, "w", encoding="utf-8") as f:
                f.write(content)
            if os.path.isfile(target_file):
                os.replace(tmp_path, target_file)
            else:
                os.rename(tmp_path, target_file)

            try:
                items = json.loads(content)
            except Exception:
                items = []
            restored[b] = len(items) if isinstance(items, list) else 0

        _clear_runtime_cache()

        if bank in _BANK_MAP:
            name = _BANK_MAP[bank]["name"]
            count = restored.get(bank, 0)
            return json_response({
                "ok": True,
                "msg": f"已成功恢复「{name}」默认题库，共 {count} 条数据",
                "bank": bank,
                "total": count
            })
        else:
            return json_response({
                "ok": True,
                "msg": "已成功恢复全部默认题库（急转弯、猜字谜、知识问答、成语接龙）",
                "restored": restored
            })
    except Exception as e:
        return _err(f"恢复默认题库失败: {e}")
