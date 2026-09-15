"""storage/collections.py — 商城/精灵图鉴独立文件（原 store sidecar 节）。"""
import json
import os
from . import state as _S
from .db import get_persistent_data_dir


def _coll_path(sec):
    try:
        base = ""
        if _S.CONFIG_FILE:
            try:
                base = os.path.dirname(os.path.abspath(_S.CONFIG_FILE))
            except Exception:
                base = ""
        if not base:
            try:
                base = get_persistent_data_dir()
            except Exception:
                base = ""
        if not base:
            return ""
        return os.path.join(base, _S._COLL_FILES.get(sec, ""))
    except Exception:
        return ""




def _sidecar_exists(sec):
    try:
        p = _coll_path(sec)
        return bool(p and os.path.isfile(p))
    except Exception:
        return False




def _coll_load(sec):
    """读 sidecar（内存缓存；缺文件返回 {}，不回退内存，防旧值复活）"""
    try:
        if sec in _S._COLL_CACHE and isinstance(_S._COLL_CACHE[sec], dict):
            if _S._COLL_CACHE[sec]:
                return _S._COLL_CACHE[sec]
            # 空缓存可能是“文件缺失时”留下的 miss 印记：文件仍不存在则维持，
            # 文件已出现（后建/恢复）则穿透重读，防永久隐身；热路径非空缓存零额外开销
            try:
                if not _sidecar_exists(sec):
                    return _S._COLL_CACHE[sec]
            except Exception:
                return _S._COLL_CACHE[sec]
        d = {}
        p = _coll_path(sec)
        if p and os.path.isfile(p):
            try:
                with open(p, encoding="utf-8") as f:
                    raw = json.load(f)
                if isinstance(raw, dict):
                    d = raw
                else:
                    # 非字典坏文件：不缓存，下次重读（禁 {} 污染后被 merge 落盘放大）
                    return {}
            except Exception:
                # 解析失败不缓存：下次重读，禁坏文件钉死缓存
                return {}
        _S._COLL_CACHE[sec] = d
        return d
    except Exception:
        return {}




def _coll_write(sec):
    try:
        p = _coll_path(sec)
        if not p:
            return False
        # 非空坏文件禁写：防 {} 回写吞待修旧档（空文件无物可护，照写）
        try:
            if os.path.isfile(p) and os.path.getsize(p) > 0:
                with open(p, encoding="utf-8") as _bf:
                    if not isinstance(json.load(_bf), dict):
                        return False
        except Exception:
            return False
        d = _S._COLL_CACHE.get(sec) if isinstance(_S._COLL_CACHE.get(sec), dict) else {}
        tmp = p + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=2)
        os.replace(tmp, p)
        return True
    except Exception:
        return False




def _coll_coerce(v):
    if isinstance(v, dict):
        return v
    if isinstance(v, str) and v.strip():
        try:
            d = json.loads(v)
            if isinstance(d, dict):
                return d
        except Exception:
            pass
        try:
            import ast as _ast
            d = _ast.literal_eval(v)
            if isinstance(d, dict):
                return d
        except Exception:
            pass
    return {}




def coll_migrate():
    """启动迁移（once 语义，幂等）：sidecar 缺失时才从 AstrBot 参数 ∪ 持久文件收编
    （文件优先），随后逐出内存；sidecar 已存在则只逐出内存，绝不回写覆盖用户定制。
    在 wd_cfg_restore 头部调用，此时参数与文件回填均已就位。旧快照恢复时同样调用。"""
    try:
        # 读持久文件侧（扁平 已弃用节__键 + 嵌套节 两形态）
        fsec_all = {}
        try:
            p = _S.CONFIG_FILE
            if p and os.path.isfile(p):
                with open(p, encoding="utf-8") as f:
                    raw = json.load(f)
                if isinstance(raw, dict):
                    for k, v in raw.items():
                        if "__" in str(k):
                            s2, key = str(k).split("__", 1)
                            if s2 in _S._COLL_FILES:
                                fsec_all.setdefault(s2, {})[key] = v
                    for s2 in _S._COLL_FILES:
                        if isinstance(raw.get(s2), dict):
                            for k, v in raw[s2].items():
                                fsec_all.setdefault(s2, {})[str(k)] = v
        except Exception:
            pass
        for sec in _S._COLL_FILES:
            try:
                if _sidecar_exists(sec):
                    # 已有 sidecar：只逐出内存，不收编（用户定制至上）
                    pass
                else:
                    mem = _S._CONFIG.get(sec) if isinstance(_S._CONFIG, dict) and isinstance(_S._CONFIG.get(sec), dict) else {}
                    merged = dict(mem or {})
                    for k, v in (fsec_all.get(sec) or {}).items():
                        merged[str(k)] = v
                    if merged:
                        cur = _coll_load(sec)
                        cur.update(merged)
                        if _S._COLL_LOCK is not None:
                            try:
                                with _S._COLL_LOCK:
                                    _coll_write(sec)
                            except Exception:
                                _coll_write(sec)
                        else:
                            _coll_write(sec)
            except Exception:
                pass
            try:
                if isinstance(_S._CONFIG, dict):
                    _S._CONFIG.pop(sec, None)
            except Exception:
                pass
    except Exception:
        pass




def coll_merge(sec, kv):
    """sidecar 合并写（供 config/save、平衡预设、旧快照恢复）：只动本节，单次落盘"""
    try:
        if sec not in _S._COLL_FILES or not isinstance(kv, dict):
            return False

        def _do():
            d = _coll_load(sec)
            try:
                _backup = dict(d)
            except Exception:
                _backup = None
            for k, v in kv.items():
                if v is None or (isinstance(v, str) and v.strip() == ""):
                    d.pop(str(k), None)
                elif isinstance(v, dict):
                    d[str(k)] = v
                elif isinstance(v, str):
                    c = _coll_coerce(v)
                    if c or c == {} and v.strip() in ("{}", "[]"):
                        # 空对象串视为显式清空；不可解析串跳过防误清
                        d[str(k)] = c
            if not _coll_write(sec):
                # 落盘失败回滚内存，防内存新盘旧（重启丢配置却显示成功）
                try:
                    if _backup is not None:
                        _S._COLL_CACHE[sec] = _backup
                except Exception:
                    pass
                return False
            return True

        if _S._COLL_LOCK is not None:
            try:
                with _S._COLL_LOCK:
                    return _do()
            except Exception:
                return _do()
        return _do()
    except Exception:
        return False



__all__ = ["coll_merge", "coll_migrate"]
