# -*- coding: utf-8 -*-
"""core/router/rules.py — 路由·rules（原 router.py 切分）。"""
from . import shared as _S
from .shared import _norm_cmd, _resolve_reply, _multi_reply


def apply_reply_override(raw, reply, store):
    try:
        if not raw or not reply:
            return reply
        raw = str(raw).strip()
        sec = store._CONFIG.get(_S._REPLY_OVERRIDE_SEC) if hasattr(store, "_CONFIG") else None
        if not isinstance(sec, dict):
            return reply
        try:
            kws = list(_custom_idx(store).get("ovr") or ())
            _indexed = True
        except Exception:
            kws = []
            _indexed = False
        if not kws:
            # 回退：无索引时逐项最长匹配（语义与旧版一致，键按规范形比较）
            hit = None
            raw_n = _norm_cmd(raw)
            for k in sec.keys():
                k = str(k)
                if isinstance(sec[k], str) and str(sec[k]).strip() and raw_n.startswith(_norm_cmd(k)) and (hit is None or len(_norm_cmd(k)) > len(_norm_cmd(hit))):
                    hit = k
            if hit is None:
                return reply
        elif _indexed:
            # 索引已按长度降序，首个命中即最长（规范形比较，返回库中原键）
            hit = None
            raw_n = _norm_cmd(raw)
            for k in kws:
                if raw_n.startswith(_norm_cmd(k)):
                    hit = k
                    break
            if hit is None:
                return reply
        tpl = str(sec[hit])
        cands = [c.strip() for c in tpl.split("|") if c.strip()]
        if not cands:
            return reply
        cand = _S.random.choice(cands) if len(cands) > 1 else cands[0]
        return _resolve_reply(cand, reply)
    except Exception:
        return reply



def _custom_fp(store):
    try:
        import json as _js
        def _fp_sec(_s):
            if not isinstance(_s, dict):
                return ""
            try:
                return _js.dumps({str(k): (str(v) if not isinstance(v, dict) else _js.dumps(v, sort_keys=True, ensure_ascii=False)) for k, v in sorted(_s.items(), key=lambda x: str(x[0]))}, ensure_ascii=False, sort_keys=True)
            except Exception:
                try:
                    return str(sorted(str(k) for k in _s.keys()))
                except Exception:
                    return ""
        _c1 = store._CONFIG.get(_S._CUSTOM_SEC) if hasattr(store, "_CONFIG") else None
        _c2 = store._CONFIG.get(_S._DISABLE_SEC) if hasattr(store, "_CONFIG") else None
        _c3 = store._CONFIG.get(_S._REPLY_OVERRIDE_SEC) if hasattr(store, "_CONFIG") else None
        _c4 = store._CONFIG.get(_S._PERM_SEC) if hasattr(store, "_CONFIG") else None
        return (_fp_sec(_c1), _fp_sec(_c2), _fp_sec(_c3), _fp_sec(_c4))
    except Exception:
        return None


def _custom_idx(store):
    """自定义/禁用/回复覆盖三表统一索引：按触发词长度降序预排，配置版本变更时重建。
    每消息三遍全量遍历 O(3C) → 一次索引命中，C=50 时约省 0.1-0.3ms。"""
    try:
        ver = getattr(store, "_CONFIG_VER", -1)
    except Exception:
        ver = -1
    try:
        # 主路径：版本命中直接返回，零序列化（指纹只在版本变化时算一次）
        if _S._CUSTOM_IDX.get("ver") == ver and ver != -1:
            return _S._CUSTOM_IDX
    except Exception:
        pass
    try:
        fp = _custom_fp(store)
    except Exception:
        fp = None
    try:
        if _S._CUSTOM_IDX.get("ver") == ver and ver != -1 and _S._CUSTOM_IDX.get("_fp") == fp:
            return _S._CUSTOM_IDX
        if ver == -1 and fp is not None and _S._CUSTOM_IDX.get("_fp") == fp and _S._CUSTOM_IDX.get("_fp") is not None:
            return _S._CUSTOM_IDX
    except Exception:
        pass
    cmds, dis, ovr, adm = (), (), (), ()
    try:
        sec = store._CONFIG.get(_S._CUSTOM_SEC) if hasattr(store, "_CONFIG") else None
        if isinstance(sec, dict):
            cmds = tuple(sorted((str(t) for t in sec.keys() if str(t)), key=len, reverse=True))
    except Exception:
        pass
    try:
        sec2 = store._CONFIG.get(_S._DISABLE_SEC) if hasattr(store, "_CONFIG") else None
        if isinstance(sec2, dict):
            dis = tuple(sorted((str(k) for k, v in sec2.items() if str(k) and (str(v).strip() == "假" or str(v).strip().lower() in ("0", "false"))), key=len, reverse=True))
    except Exception:
        pass
    try:
        sec3 = store._CONFIG.get(_S._REPLY_OVERRIDE_SEC) if hasattr(store, "_CONFIG") else None
        if isinstance(sec3, dict):
            ovr = tuple(sorted((str(k) for k in sec3.keys() if isinstance(sec3[k], str) and str(sec3[k]).strip()), key=len, reverse=True))
    except Exception:
        pass
    try:
        sec4 = store._CONFIG.get(_S._PERM_SEC) if hasattr(store, "_CONFIG") else None
        if isinstance(sec4, dict):
            adm = tuple(sorted((str(k) for k, v in sec4.items() if str(k) and str(v).strip() == _S._ADMIN_ONLY), key=lambda x: len(_norm_cmd(x)), reverse=True))
    except Exception:
        pass
    try:
        _S._CUSTOM_IDX["ver"], _S._CUSTOM_IDX["cmds"], _S._CUSTOM_IDX["dis"], _S._CUSTOM_IDX["ovr"], _S._CUSTOM_IDX["adm"] = ver, cmds, dis, ovr, adm
        try:
            _S._CUSTOM_IDX["_fp"] = fp
        except Exception:
            pass
    except Exception:
        pass
    return _S._CUSTOM_IDX




def _custom_cmd(raw, store):
    try:
        sec = store._CONFIG.get(_S._CUSTOM_SEC) if hasattr(store, "_CONFIG") else None
        if not isinstance(sec, dict):
            return None, raw
        raw = str(raw or "").strip()
        hit = None
        try:
            _cmds = _custom_idx(store).get("cmds") or ()
        except Exception:
            _cmds = ()
        if _cmds:
            for t in _cmds:
                if raw.startswith(t):
                    hit = t
                    break
        else:
            for t in sec.keys():
                t = str(t)
                if t and raw.startswith(t) and (hit is None or len(t) > len(hit)):
                    hit = t
        if hit is None:
            return None, raw
        e = sec[hit]
        e = e if isinstance(e, dict) else {"reply": str(e)}
        cmd = str(e.get("command", "") or "").strip()
        reply = str(e.get("reply", "") or "").strip()
        rest = raw[len(hit):].strip()
        if cmd:
            return None, (cmd + (" " if rest else "") + rest)
        if reply:
            # 变量渲染 + 多回复随机（纯自定义支持 {name}/{qq}/{gid}/{time}/{coin}/{at} 等）
            try:
                # _custom_cmd 在路由层无 gid/qq 上下文时由 handle 传入 rest，此处先多选再渲染
                # 实际渲染在 handle 层带 gid/qq 时更准，这里仅做初步多选
                reply = _multi_reply(reply)
                # 尝试在 handle 层二次渲染（带真实 gid/qq），此处若能取到 store 的 gid/qq 透传则直接渲染
                # 保持兼容：若 reply 含 { 则留到 handle 再渲染
            except Exception:
                pass
            return reply, raw
        return None, raw
    except Exception:
        return None, raw




def _longer_exempts(raw_n, hit_len, sec, exempted):
    """更长键优先豁免（禁用/权限四处复用，零语义差）：
    存在更长的同前缀已知键且 exempted(其值) 为真时，本次命中豁免（返 True）。
    如禁“签到”不应误杀“签到系统”菜单；超管“签到”不应误杀所有人“签到系统”。"""
    try:
        if not isinstance(sec, dict):
            return False
        for _ak, _av in sec.items():
            _ak = str(_ak)
            if not _ak or len(_norm_cmd(_ak)) <= hit_len:
                continue
            if raw_n.startswith(_norm_cmd(_ak)):
                try:
                    if exempted(_av):
                        return True
                except Exception:
                    continue
        return False
    except Exception:
        return False


def _cmd_disabled(raw, store):
    try:
        raw = str(raw or "")
        raw_n = _norm_cmd(raw)
        try:
            _dis = _custom_idx(store).get("dis") or ()
        except Exception:
            _dis = ()
        if _dis:
            for k in _dis:
                if raw_n.startswith(_norm_cmd(k)):
                    # 最长优先：若存在更长的已知指令键同样前缀命中且未被禁用，则不拦截
                    # （如禁“签到”不应误杀“签到系统”菜单）
                    try:
                        _sec_all = store._CONFIG.get(_S._DISABLE_SEC) if hasattr(store, "_CONFIG") else None
                        if _longer_exempts(raw_n, len(_norm_cmd(k)), _sec_all,
                                           lambda _av: not (str(_av).strip() == "假" or str(_av).strip().lower() in ("0", "false"))):
                            return None
                    except Exception:
                        pass
                    return k
            return None
        sec = store._CONFIG.get(_S._DISABLE_SEC) if hasattr(store, "_CONFIG") else None
        if not isinstance(sec, dict):
            return None
        hit = None
        for k, v in sec.items():
            k = str(k)
            if not k:
                continue
            if not (str(v).strip() == "假" or str(v).strip().lower() in ("0", "false")):
                continue
            if raw_n.startswith(_norm_cmd(k)) and (hit is None or len(_norm_cmd(k)) > len(_norm_cmd(hit))):
                hit = k
        if hit is not None:
            if _longer_exempts(raw_n, len(_norm_cmd(hit)), sec,
                               lambda _av: not (str(_av).strip() == "假" or str(_av).strip().lower() in ("0", "false"))):
                return None
        return hit
    except Exception:
        return None




def _cmd_need_admin(raw, store):
    """指令超管权限：命中 指令权限配置=超管 的规范键（空格无关，最长匹配）时仅超管可用"""
    try:
        raw_n = _norm_cmd(raw)
        if not raw_n:
            return None
        try:
            _adm = _custom_idx(store).get("adm") or ()
        except Exception:
            _adm = ()
        if _adm:
            for k in _adm:
                if raw_n.startswith(_norm_cmd(k)):
                    # 同禁用：更长的非超管指令键优先（如“签到系统”所有人 vs “签到”超管时不误静默）
                    try:
                        _sec_all = store._CONFIG.get(_S._PERM_SEC) if hasattr(store, "_CONFIG") else None
                        if _longer_exempts(raw_n, len(_norm_cmd(k)), _sec_all,
                                           lambda _av: str(_av).strip() != _S._ADMIN_ONLY):
                            return None
                    except Exception:
                        pass
                    return k
            return None
        sec = store._CONFIG.get(_S._PERM_SEC) if hasattr(store, "_CONFIG") else None
        if not isinstance(sec, dict):
            return None
        hit = None
        for k, v in sec.items():
            k = str(k)
            if not k or str(v).strip() != _S._ADMIN_ONLY:
                continue
            if raw_n.startswith(_norm_cmd(k)) and (hit is None or len(_norm_cmd(k)) > len(_norm_cmd(hit))):
                hit = k
        if hit is not None:
            if _longer_exempts(raw_n, len(_norm_cmd(hit)), sec,
                               lambda _av: str(_av).strip() != _S._ADMIN_ONLY):
                return None
        return hit
    except Exception:
        return None



__all__ = ["_cmd_disabled", "_cmd_need_admin", "_custom_cmd", "_custom_fp", "_custom_idx", "apply_reply_override"]
