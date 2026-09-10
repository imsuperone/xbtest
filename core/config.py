# -*- coding: utf-8 -*-
"""Layer 1 — Config Layer
负责配置归一、Schema 加载、指令索引收集。
被 main.XbBot 与 router 层复用，保持单一来源 store._CONFIG。
"""
import json
import os
import re

# 全量 schema 文件名（WebUI/播种共用；根 _conf_schema.json 仅留 AstrBot 原生页引导占位）
_SCHEMA_CANDS = ("data/webui_schema.json", "_conf_schema.json")


def _schema_path(base_dir=""):
    """全量 schema 路径：data/webui_schema.json 优先，根 _conf_schema.json 兼容回退。"""
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


# 指令索引正则（与 main._collect_commands 保持一致）
_CMD_RE1 = re.compile(r'\b(?:text|m)\s*\.startswith\(\s*\(?([^)]*)\)')
_CMD_RE1_TUPLE = re.compile(r'\b(?:text|m)\s*\.startswith\(\s*\(([^)]*)\)')
_CMD_RE2 = re.compile(r'\b(?:text|m)\s*==\s*["\']([^"\']+)["\']')
_CMD_RE3 = re.compile(r'(?:\btext\s*in\s*\(|(?<![A-Za-z0-9_])m\s+in\s*\()([^)]*)\)')
_CMD_RE_TBL_NEED = re.compile(r'_need\s*=\s*\(([^)]*)\)')
_CMD_RE_TBL_ADMIN = re.compile(r'_ADMIN_CMDS\s*=\s*\(([^)]*)\)', re.S)
_CMD_RE_TBL_EXACT = re.compile(r'_ROUTE_EXACT\s*=\s*\{(.*?)\}', re.S)


def _collect_commands(base_dir="", store=None):
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
                # 已拆包的系统：串联包内全部模块源码再采集（与单文件语义一致）
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
            src = ""
            for p in _files:
                if not p or not os.path.isfile(p):
                    continue
                try:
                    src += "\n" + open(p, encoding="utf-8").read()
                except Exception:
                    continue
            if not src:
                continue
            # 去掉 # 注释（整行+行尾，字符串内 # 保留），避免注释中文被收录
            _lines = []
            for _ln in src.splitlines():
                if _ln.lstrip().startswith("#"):
                    continue
                _q1 = _q2 = False
                _cut = None
                _prev = ""
                for _i, _ch in enumerate(_ln):
                    if _ch == "'" and not _q2 and _prev != "\\":
                        _q1 = not _q1
                    elif _ch == '"' and not _q1 and _prev != "\\":
                        _q2 = not _q2
                    elif _ch == "#" and not _q1 and not _q2:
                        _cut = _i
                        break
                    _prev = _ch
                if _cut is not None:
                    _ln = _ln[:_cut]
                _lines.append(_ln)
            src = "\n".join(_lines)
            cmds = []

            # 采集噪音：否定守卫元组里的路由前缀（非独立指令）+ 单字选项（作开关会误伤所有同字开头消息）
            # 来源：bank.py:1077（我要/自我）、ent.py:1124/1127（开始/加入/退出）、adventure.py:317（一/二/三）
            _CMD_NOISE = {"我要", "自我", "开始", "加入", "退出"}

            def _add(_c):
                _c = _c.strip()
                # 规范键：去内部空格（查询坐骑/查询 坐骑系同一指令），一词一开关，禁一词多开关
                _canon = _c.replace(" ", "")
                if len(_canon) < 2 or _canon in _CMD_NOISE:
                    return
                if _canon and re.search(r"[\u4e00-\u9fff]", _canon) and _canon not in cmds:
                    cmds.append(_canon)
            # RE1 单串+元组：body 内再抽所有引号串，兼容 text.startswith(("a","b"))
            try:
                for _body in _CMD_RE1.findall(src):
                    for _c in re.findall(r'["\']([^"\']+)["\']', _body):
                        _add(_c)
            except Exception:
                pass
            try:
                for _body in _CMD_RE1_TUPLE.findall(src):
                    for _c in re.findall(r'["\']([^"\']+)["\']', _body):
                        _add(_c)
            except Exception:
                pass
            for c in _CMD_RE2.findall(src):
                _add(c)
            for body in _CMD_RE3.findall(src):
                for c in re.findall(r'["\']([^"\']+)["\']', body):
                    _add(c)
            # 表驱动：_need / _ROUTE_EXACT / _ADMIN_CMDS 等元组/字典变量赋值的字符串元素
            try:
                for _body in _CMD_RE_TBL_NEED.findall(src):
                    for _c in re.findall(r'["\']([^"\']+)["\']', _body):
                        _add(_c)
            except Exception:
                pass
            try:
                for _body in _CMD_RE_TBL_ADMIN.findall(src):
                    for _c in re.findall(r'["\']([^"\']+)["\']', _body):
                        _add(_c)
            except Exception:
                pass
            try:
                for _body in _CMD_RE_TBL_EXACT.findall(src):
                    for _c in re.findall(r'["\']([^"\']+)["\']', _body):
                        _add(_c)
            except Exception:
                pass
            out[name] = cmds
        # 唤醒词显式展示
        try:
            sch_path = _schema_path(base_dir)
            with open(sch_path, encoding="utf-8") as f:
                sch = json.load(f)
            wc = sch.get("唤醒词配置", {}).get("items", {}) if isinstance(sch.get("唤醒词配置"), dict) else {}
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
        except Exception:
            pass
    except Exception:
        pass
    return out
