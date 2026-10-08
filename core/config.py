# -*- coding: utf-8 -*-
"""Layer 1 — Config Layer
负责配置归一、Schema 加载、指令索引收集。
被 main.XbBot 与 router 层复用，保持单一来源 store._CONFIG。
"""
import ast
import json
import os
import re

# 全量 schema 文件名单源：data/webui_schema.json（_conf_schema.json 已删，不再回退）
_SCHEMA_CANDS = ("data/webui_schema.json",)


def _schema_path(base_dir=""):
    """全量 schema 路径：data/webui_schema.json 单源（_conf_schema.json 已删，无回退）。"""
    try:
        if not base_dir:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        for _fn in _SCHEMA_CANDS:
            _q = os.path.join(base_dir, _fn)
            if os.path.isfile(_q):
                return _q
            _q2 = os.path.join(os.path.dirname(base_dir), _fn)
            if os.path.isfile(_q2):
                return _q2
    except Exception:
        pass
    return ""


def _maybe_dict(v):
    if isinstance(v, str) and v[:1] == "{" and v[-1:] == "}":
        try:
            j = json.loads(v)
            if isinstance(j, dict):
                return j
        except Exception:
            pass
        try:
            import ast
            p = ast.literal_eval(v)
            if isinstance(p, dict):
                return p
        except Exception:
            pass
    return v


def _normalize_cfg(cfg):
    out = {}
    if not isinstance(cfg, dict):
        return out
    for k, v in cfg.items():
        k = str(k)
        if k == "_comment":
            continue  # schema 占位键（AstrBot 原生页引导），不进运行配置
        if "__" in k:
            sec, key = k.split("__", 1)
            out.setdefault(sec, {})[key] = _maybe_dict(v)
        elif isinstance(v, dict):
            sec = k
            for kk, vv in v.items():
                out.setdefault(sec, {})[str(kk)] = _maybe_dict(vv)
        else:
            out.setdefault(k, {})[""] = str(v)
    return out


def _fallback_cfg(base_dir=""):
    cfg = {}
    try:
        if not base_dir:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        # try file in plugin data/
        p = os.path.join(base_dir, "data", "config.json")
        # fallback: if base_dir is core/, go up one more
        if not os.path.isfile(p):
            p = os.path.join(os.path.dirname(base_dir), "data", "config.json")
        if os.path.isfile(p):
            with open(p, encoding="utf-8") as f:
                cfg = _normalize_cfg(json.load(f))
    except Exception:
        cfg = {}
    return cfg


def _load_schema(base_dir=""):
    p = _schema_path(base_dir)
    groups = {}
    defaults = {}
    try:
        with open(p, encoding="utf-8") as f:
            c = json.load(f)
        for sec, obj in c.items():
            if not isinstance(obj, dict):
                continue
            items = obj.get("items") if isinstance(obj.get("items"), dict) else {}
            for key, it in items.items():
                it = it if isinstance(it, dict) else {}
                d = it.get("default", "")
                t = it.get("type", "string")
                desc = it.get("description", "")
                groups.setdefault(sec, []).append({"key": key, "desc": desc, "default": d, "type": t})
                defaults["%s__%s" % (sec, key)] = d
    except Exception:
        pass
    return {"groups": groups, "defaults": defaults}


_WAKE_CACHE = {"path": "", "mt": 0.0, "items": {}}  # 唤醒词节缓存：path+mtime 双键，文件不变零重解析


def _load_wake_items(base_dir=""):
    """唤醒词语配置节（items dict）：_collect_commands 专用缓存，store 当前值仍每次实时读（语义不变）"""
    try:
        sch_path = _schema_path(base_dir)
        if not sch_path:
            return {}
        try:
            mt = os.path.getmtime(sch_path)
        except Exception:
            mt = 0.0
        if _WAKE_CACHE.get("path") == sch_path and _WAKE_CACHE.get("mt") == mt and isinstance(_WAKE_CACHE.get("items"), dict):
            # 返回拷贝：调用方改动不得污染缓存（外改污染曾致唤醒词漂移）
            return dict(_WAKE_CACHE.get("items") or {})
        with open(sch_path, encoding="utf-8") as f:
            sch = json.load(f)
        wc = sch.get("唤醒词配置", {}).get("items", {}) if isinstance(sch.get("唤醒词配置"), dict) else {}
        if not isinstance(wc, dict):
            wc = {}
        _WAKE_CACHE["path"], _WAKE_CACHE["mt"], _WAKE_CACHE["items"] = sch_path, mt, wc
        return dict(wc)
    except Exception:
        try:
            return dict(_WAKE_CACHE.get("items") or {})
        except Exception:
            return {}


# V8：六族指令刮词正则（startswith / == / in / _need / _ADMIN_CMDS / _ROUTE_EXACT）已退役——
# 词表唯一来源 = 各引擎模块级 COMMANDS（AST 静态求值）+ 唤醒词配置，见 _collect_commands。


def _cmds_static(node, consts):
    """静态求值模块级词表表达式：字面量 / 常量名引用 / 加法拼接（superadmin：静态词 + _ADMIN_CMDS）。
    常量须定义在 COMMANDS 之前（与模块执行语义一致）；不可静态求值时返回 None，由调用方记日志。"""
    try:
        v = ast.literal_eval(node)
        if isinstance(v, (list, tuple)):
            return [str(x) for x in v]
    except Exception:
        pass
    if isinstance(node, ast.Name):
        return consts.get(node.id)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = _cmds_static(node.left, consts)
        right = _cmds_static(node.right, consts)
        if left is not None and right is not None:
            return list(left) + list(right)
    return None


def _collect_commands(base_dir="", store=None):
    """显式指令表（V8 单源）：各引擎模块级 COMMANDS + 唤醒词（schema 默认 ∪ store 当前值）。
    不再刮源码正文——一个接口一个实现，正则六族已退役。"""
    out = {}
    try:
        if not base_dir:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        eng_dir = os.path.join(base_dir, "games")
        if not os.path.isdir(eng_dir):
            eng_dir = os.path.join(os.path.dirname(base_dir), "games")
        # also try plugin root
        if not os.path.isdir(eng_dir):
            eng_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "games")
            eng_dir = os.path.abspath(eng_dir)
        core_dir = os.path.join(base_dir, "core")
        if not os.path.isdir(core_dir):
            core_dir = os.path.join(os.path.dirname(base_dir), "core")
        _targets = []
        for name in ("slave", "sign", "bank", "ent", "spirit", "ride", "guild", "adventure"):
            _one = os.path.join(eng_dir, name + ".py")
            if not os.path.isfile(_one) and os.path.isdir(os.path.join(eng_dir, name)):
                # 已拆包的系统：逐文件取其模块级 COMMANDS（词表在 handler 单文件，与单文件语义一致）
                _targets.append((name, sorted(
                    os.path.join(eng_dir, name, f) for f in os.listdir(os.path.join(eng_dir, name))
                    if f.endswith(".py"))))
            else:
                _targets.append((name, [_one]))
        _sup = os.path.join(core_dir, "superadmin.py")
        if not os.path.isfile(_sup):
            _sup = os.path.join(eng_dir, "superadmin.py")  # 旧位兼容
        _targets.append(("superadmin", [_sup]))
        for name, _files in _targets:
            # V8：AST 读模块级 COMMANDS（字面量/常量名/加法拼接静态求值；包内多文件取首个可求值者）
            consts = {}
            cmds = None
            seen = False
            for p in _files:
                if not p or not os.path.isfile(p):
                    continue
                try:
                    with open(p, encoding="utf-8") as _rf:
                        _tree = ast.parse(_rf.read())
                except Exception:
                    continue
                for _node in _tree.body:
                    if not isinstance(_node, ast.Assign):
                        continue
                    for _t in _node.targets:
                        if not isinstance(_t, ast.Name):
                            continue
                        if _t.id == "COMMANDS":
                            if not seen:
                                seen = True
                                cmds = _cmds_static(_node.value, consts)
                        elif _t.id not in consts:
                            try:
                                _v = ast.literal_eval(_node.value)
                                if isinstance(_v, (list, tuple)):
                                    consts[_t.id] = [str(x) for x in _v]
                            except Exception:
                                pass
            if seen and not cmds:
                try:
                    from .logger import error as _log_err_cmds
                except ImportError:
                    try:
                        from core.logger import error as _log_err_cmds  # type: ignore
                    except Exception:
                        _log_err_cmds = None
                try:
                    if _log_err_cmds:
                        _log_err_cmds(f"_collect_commands: {name}.COMMANDS 静态求值失败（仅支持字面量/常量名/加法拼接）")
                except Exception:
                    pass
            out[name] = [c for c in (cmds or []) if str(c)]
        # 唤醒词显式展示（77KB schema 按 path+mtime 缓存，miss/VER 失效时才重解析；当前值仍实时读 store）
        try:
            wc = _load_wake_items(base_dir)
            for sysname, it in wc.items():
                eng_name = None
                for _e, _s in (("sign", "签到系统"), ("spirit", "精灵系统"), ("ent", "娱乐系统"), ("bank", "银行系统"), ("slave", "奴隶系统"), ("ride", "坐骑系统"), ("guild", "帮派系统"), ("adventure", "冒险系统"), ("superadmin", "超管系统")):
                    if _s == sysname:
                        eng_name = _e
                        break
                if eng_name is None:
                    continue
                default = str((it.get("default") if isinstance(it, dict) else "") or sysname)
                cur = None
                if store is not None and hasattr(store, "cfg"):
                    try:
                        cur = store.cfg("唤醒词配置", sysname, default)
                    except Exception:
                        cur = default
                else:
                    cur = default
                words = [w for w in re.split(r"[|，,]+", cur.strip()) if w.strip()] or [default]
                if default not in words:
                    words.insert(0, default)
                for w in words:
                    if w not in out.setdefault(eng_name, []):
                        out[eng_name].insert(0, w)
        except Exception as _e_wake:
            # 唤醒词扩展失败记日志（曾 except:pass 吞错，语义不变：失败即无扩展词）
            try:
                from .logger import error as _log_err_wake
            except ImportError:
                try:
                    from core.logger import error as _log_err_wake  # type: ignore
                except Exception:
                    _log_err_wake = None
            try:
                if _log_err_wake:
                    _log_err_wake(f"_collect_commands 唤醒词扩展失败: {_e_wake}")
            except Exception:
                pass
    except Exception as _e_coll:
        # 采集整体失败记日志（曾吞错致指令索引静默为空）
        try:
            from .logger import error as _log_err_coll
        except ImportError:
            try:
                from core.logger import error as _log_err_coll  # type: ignore
            except Exception:
                _log_err_coll = None
        try:
            if _log_err_coll:
                _log_err_coll(f"_collect_commands 采集失败: {_e_coll}")
        except Exception:
            pass
    return out
