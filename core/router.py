# -*- coding: utf-8 -*-
"""core/router.py — 统一指令路由单文件（原 router/ 包 6 文件并入，零语义差）。
shared（常量/缓存/渲染，原 template 已并入）/ guards（开关守卫）/ commands（引擎指令）/
rules（自定义/禁用/权限）/ pipeline（11 层 handle）。对外名与包门面一致。"""
import random
import time as _t_guard
_REPLY_OVERRIDE_SEC = "指令回复配置"
_DEFAULT_MARKERS = ("{回复}", "{默认}", "默认", "默认回复")
_CUSTOM_SEC = "自定义指令配置"
_DISABLE_SEC = "指令启用配置"
_PERM_SEC = "指令权限配置"
_ADMIN_ONLY = "超管"
_SYS_ENG = {'slave': '奴隶', 'sign': '签到', 'bank': '银行', 'ent': '娱乐', 'spirit': '精灵', 'ride': '坐骑', 'guild': '帮派', 'superadmin': '超管', 'adventure': '冒险'}
_MAIN_MENU = (
    "★ 小白测试版主菜单 ★\r\n"
    "----------------\r\n"
    "| ❤️ 签到系统 | ✨ 精灵系统 |\r\n"
    "| 🎮 娱乐系统 | 🏦 银行系统 |\r\n"
    "| ⛓️ 奴隶系统 | 🏍️ 坐骑系统 |\r\n"
    "| ⚔️ 帮派系统 | 🗺️ 冒险系统 |\r\n"
    "----------------\r\n"
    "发送系统关键词打开菜单，如【签到系统】【精灵系统】"
)
def _resolve_reply(cand, reply):
    if cand in _DEFAULT_MARKERS:
        return reply
    if "{回复}" in cand:
        return cand.replace("{回复}", reply)
    if "{默认}" in cand:
        return cand.replace("{默认}", reply)
    return cand
def _norm_cmd(s):
    """指令规范形：去内部空格（查询坐骑≡查询 坐骑）。仅用于内置开关/回复/引擎匹配；
    用户自定义触发词保持精确匹配，不走此函数（零行为变化）"""
    try:
        return str(s or "").replace(" ", "")
    except Exception:
        return ""
def _multi_reply(reply_tpl):
    """多回复随机（原 template.py 并入）：按 | 切分随机取一"""
    try:
        cands = [c.strip() for c in str(reply_tpl).split("|") if c.strip()]
        return random.choice(cands) if cands else reply_tpl
    except Exception:
        return reply_tpl




def _render_vars(tpl, gid, qq, store):
    """变量渲染（原 template.py 并入）：{name}/{qq}/{gid}/{time}/{coin}/{at} 等"""
    try:
        import datetime as _dt
        name = qq
        try:
            from ..games import slave as _sl  # type: ignore
            name = _sl.NOTE_NAMES.get(str(qq), str(qq))
        except Exception:
            try:
                import slave as _sl2  # type: ignore
                name = _sl2.NOTE_NAMES.get(str(qq), str(qq))
            except Exception:
                pass
        coin = ""
        try:
            coin = store.coin_name() if hasattr(store, "coin_name") else "金币"
        except Exception:
            coin = "金币"
        now = _dt.datetime.now()
        vars_map = {
            "{name}": str(name), "{qq}": str(qq), "{gid}": str(gid),
            "{group}": str(gid), "{time}": now.strftime("%H:%M:%S"),
            "{date}": now.strftime("%Y-%m-%d"), "{datetime}": now.strftime("%Y-%m-%d %H:%M:%S"),
            "{coin}": str(coin), "{金币}": str(coin),
        }
        for k, v in vars_map.items():
            if k in tpl:
                tpl = tpl.replace(k, v)
        # {at} -> @qq
        if "{at}" in tpl:
            tpl = tpl.replace("{at}", f"[CQ:at,qq={qq}]")
        return tpl
    except Exception:
        return tpl
_GUARD_CACHE = {}
_GUARD_CACHE_TTL = 5.0  # 5s 缓存，千群每消息 18次kv/config读→命中后0次DB；由 _bump_config_ver 主动清空
_GUARD_CACHE_MAX = 5000  # 无界增长防护：千群×9系统键超限淘汰最旧一半
_GUARD_BATCH_TTL = 2.0  # 同 gid 批量复用：2s 内9引擎守卫共享一次计算，突发消息0重复计算
_GUARD_BATCH_CACHE = {}  # gid -> (ts, {engine: blocked_msg_or_None})
_ENGINE_CMDS = {}
_ENGINE_CMDS_VER = None
_ENGINE_MT_CACHE = {"t": 0.0, "mt": 0.0}
_ENGINE_MT_TTL = 10.0  # mtime 探测节流：10 秒内复用，避免每消息 10 次 stat
_CUSTOM_IDX = {"ver": -1, "cmds": (), "dis": (), "ovr": (), "adm": (), "_fp": None}


# ==================== guards（原 router/guards.py 并入） ====================
def _sys_off(gid, engine, store):
    sysname = _SYS_ENG.get(engine)
    if not sysname:
        return False
    key = ("swf", str(gid), sysname)
    try:
        hit = _GUARD_CACHE.get(key)
        if hit and _t_guard.time() - hit[0] < _GUARD_CACHE_TTL:
            try:
                _GUARD_CACHE[key] = _GUARD_CACHE.pop(key)  # LRU：命中上浮，淘汰真正最久未用
            except Exception:
                pass
            return hit[1]
    except Exception:
        pass
    try:
        val = store.recall_get("swf_%s_%s" % (gid, sysname), "1") == "0"
        try:
            _GUARD_CACHE[key] = (_t_guard.time(), val)
            if len(_GUARD_CACHE) > _GUARD_CACHE_MAX:
                # FIFO 踢最旧 1/10（dict 有序，O(n) 远小于全排序；TTL 兜底过期）
                try:
                    for _k in list(_GUARD_CACHE.keys())[:_GUARD_CACHE_MAX // 10]:
                        _GUARD_CACHE.pop(_k, None)
                except Exception:
                    pass
        except Exception:
            pass
        return val
    except Exception:
        return False




def _cfg_sys_off(engine, store):
    sysname = _SYS_ENG.get(engine)
    if not sysname:
        return False
    key = ("cfg", sysname)
    try:
        hit = _GUARD_CACHE.get(key)
        if hit and _t_guard.time() - hit[0] < _GUARD_CACHE_TTL:
            return hit[1]
    except Exception:
        pass
    try:
        val = store.cfg("系统开关配置", sysname + "系统", "真") != "真"
        try:
            _GUARD_CACHE[key] = (_t_guard.time(), val)
        except Exception:
            pass
        return val
    except Exception:
        return False




def _guard(gid, engine, is_admin, raw, store):
    # 开关对超管同样生效（关＝全员静默不运行，WebUI 为唯一控制面）
    sysname = _SYS_ENG.get(engine, engine)
    # 群开关 gacha/守卫缓存需在配置变更时失效，由 store._bump_config_ver 清空 _GUARD_CACHE
    if _cfg_sys_off(engine, store):
        return "【%s系统】已经被关闭了，无法使用该功能！" % sysname
    if _sys_off(gid, engine, store):
        return "【%s系统】已经被关闭了，无法使用该功能！\r\n如需开启，请发送【%s开关】开启！" % (sysname, sysname)
    return None


def clear_guard_cache():
    try:
        _GUARD_CACHE.clear()
    except Exception:
        pass
    try:
        _GUARD_BATCH_CACHE.clear()
    except Exception:
        pass


def _batch_guard_map(gid, is_admin, store):
    # 批量预计算9引擎守卫结果，2s 内同键复用，避免每引擎2次kv读。
    # key 带 is_admin：_guard 当前无视 is_admin（关＝全员静默），值恒一致；带上防后人加权限语义时穿透复用。
    _bkey = (str(gid), bool(is_admin))
    try:
        now = _t_guard.time()
        hit = _GUARD_BATCH_CACHE.get(_bkey)
        if hit and now - hit[0] < _GUARD_BATCH_TTL:
            return hit[1]
    except Exception:
        hit = None
    res = {}
    for eng in ("slave", "sign", "bank", "ent", "spirit", "ride", "guild", "adventure", "superadmin"):
        msg = _guard(gid, eng, is_admin, "", store)
        res[eng] = msg  # None表示放行
    try:
        _GUARD_BATCH_CACHE[_bkey] = (now, res)
    except Exception:
        pass
    return res


# ==================== commands（原 router/commands.py 并入） ====================
import os


def _engine_cache_ver(store=None):
    try:
        ver = getattr(store, "_CONFIG_VER", 0) if store is not None else 0
    except Exception:
        ver = 0
    try:
        _now = _t_guard.time()
        if _now - _ENGINE_MT_CACHE.get("t", 0.0) < _ENGINE_MT_TTL:
            return (_ENGINE_MT_CACHE.get("mt", 0.0), ver)
        base = os.path.dirname(os.path.abspath(__file__))
        eng_dir = os.path.join(base, "games")
        if not os.path.isdir(eng_dir):
            try:
                eng_dir = os.path.join(os.path.dirname(base), "games")
            except Exception:
                pass
        max_mt = 0.0
        _watch = [os.path.join(eng_dir, _n + ".py")
                  for _n in ("sign", "spirit", "ride", "guild", "adventure")]
        for _pkg in ("slave", "bank", "ent", "ride", "guild", "adventure"):
            _pd = os.path.join(eng_dir, _pkg)
            if os.path.isdir(_pd):
                _watch.extend(os.path.join(_pd, f) for f in os.listdir(_pd) if f.endswith(".py"))
        _watch.append(os.path.join(base, "superadmin.py"))  # base 即 core/，超管与其同级（曾误拼 core/superadmin.py 永不存在）
        for _p in _watch:
            try:
                _mt = os.path.getmtime(_p)
                if _mt > max_mt:
                    max_mt = _mt
            except Exception:
                pass
        _ENGINE_MT_CACHE["t"] = _now
        _ENGINE_MT_CACHE["mt"] = max_mt
    except Exception:
        max_mt = _ENGINE_MT_CACHE.get("mt", 0.0)
    return (max_mt, ver)


def _get_engine_cmds(engine, store=None):
    global _ENGINE_CMDS_VER  # 合并单文件后裸重绑必须声明 global，否则读到 UnboundLocalError 被吞错
    try:
        cur_ver = _engine_cache_ver(store)
    except Exception:
        cur_ver = None
    try:
        if _ENGINE_CMDS_VER != cur_ver or engine not in _ENGINE_CMDS:
            try:
                from .config import _collect_commands
                base = os.path.dirname(os.path.abspath(__file__))
                all_cmds = _collect_commands(base, store)
                if all_cmds:
                    _ENGINE_CMDS.clear()
                    _ENGINE_CMDS.update(all_cmds)
                    _ENGINE_CMDS_VER = cur_ver
            except Exception:
                pass
            # 注：曾有第二遍同参重扫回退（_cc2），与首遍完全等价，删（零语义差）
    except Exception:
        pass
    return _ENGINE_CMDS.get(engine, [])


def _matches_engine(raw, engine, store=None):
    if not raw:
        return False
    rt = str(raw).strip()
    sysname = _SYS_ENG.get(engine, engine)
    if store and hasattr(store, "wake"):
        try:
            wakes = store.wake(sysname + "系统", sysname + "系统")
            if rt in wakes:
                return True
        except Exception:
            pass
    if rt in (sysname + "系统", sysname + "菜单", sysname + "帮助"):
        return True
    cmds = _get_engine_cmds(engine, store)
    rt_n = _norm_cmd(rt)
    for c in cmds:
        if c and rt_n.startswith(_norm_cmd(c)):
            return True
    return False


# ==================== rules（原 router/rules.py 并入） ====================
def apply_reply_override(raw, reply, store):
    try:
        if not raw or not reply:
            return reply
        raw = str(raw).strip()
        sec = store._CONFIG.get(_REPLY_OVERRIDE_SEC) if hasattr(store, "_CONFIG") else None
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
        cand = random.choice(cands) if len(cands) > 1 else cands[0]
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
        _c1 = store._CONFIG.get(_CUSTOM_SEC) if hasattr(store, "_CONFIG") else None
        _c2 = store._CONFIG.get(_DISABLE_SEC) if hasattr(store, "_CONFIG") else None
        _c3 = store._CONFIG.get(_REPLY_OVERRIDE_SEC) if hasattr(store, "_CONFIG") else None
        _c4 = store._CONFIG.get(_PERM_SEC) if hasattr(store, "_CONFIG") else None
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
        if _CUSTOM_IDX.get("ver") == ver and ver != -1:
            return _CUSTOM_IDX
    except Exception:
        pass
    try:
        fp = _custom_fp(store)
    except Exception:
        fp = None
    try:
        # ver != -1 时上已命中返回，此处只剩 ver == -1（无版本哨兵的裸 store）才走指纹
        if ver == -1 and fp is not None and _CUSTOM_IDX.get("_fp") == fp and _CUSTOM_IDX.get("_fp") is not None:
            return _CUSTOM_IDX
    except Exception:
        pass
    cmds, dis, ovr, adm = (), (), (), ()
    try:
        sec = store._CONFIG.get(_CUSTOM_SEC) if hasattr(store, "_CONFIG") else None
        if isinstance(sec, dict):
            cmds = tuple(sorted((str(t) for t in sec.keys() if str(t)), key=len, reverse=True))
    except Exception:
        pass
    try:
        sec2 = store._CONFIG.get(_DISABLE_SEC) if hasattr(store, "_CONFIG") else None
        if isinstance(sec2, dict):
            dis = tuple(sorted((str(k) for k, v in sec2.items() if str(k) and (str(v).strip() == "假" or str(v).strip().lower() in ("0", "false"))), key=len, reverse=True))
    except Exception:
        pass
    try:
        sec3 = store._CONFIG.get(_REPLY_OVERRIDE_SEC) if hasattr(store, "_CONFIG") else None
        if isinstance(sec3, dict):
            ovr = tuple(sorted((str(k) for k in sec3.keys() if isinstance(sec3[k], str) and str(sec3[k]).strip()), key=len, reverse=True))
    except Exception:
        pass
    try:
        sec4 = store._CONFIG.get(_PERM_SEC) if hasattr(store, "_CONFIG") else None
        if isinstance(sec4, dict):
            adm = tuple(sorted((str(k) for k, v in sec4.items() if str(k) and str(v).strip() == _ADMIN_ONLY), key=lambda x: len(_norm_cmd(x)), reverse=True))
    except Exception:
        pass
    try:
        _CUSTOM_IDX["ver"], _CUSTOM_IDX["cmds"], _CUSTOM_IDX["dis"], _CUSTOM_IDX["ovr"], _CUSTOM_IDX["adm"] = ver, cmds, dis, ovr, adm
        try:
            _CUSTOM_IDX["_fp"] = fp
        except Exception:
            pass
    except Exception:
        pass
    return _CUSTOM_IDX




def _custom_cmd(raw, store):
    try:
        sec = store._CONFIG.get(_CUSTOM_SEC) if hasattr(store, "_CONFIG") else None
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
                        _sec_all = store._CONFIG.get(_DISABLE_SEC) if hasattr(store, "_CONFIG") else None
                        if _longer_exempts(raw_n, len(_norm_cmd(k)), _sec_all,
                                           lambda _av: not (str(_av).strip() == "假" or str(_av).strip().lower() in ("0", "false"))):
                            return None
                    except Exception:
                        pass
                    return k
            return None
        sec = store._CONFIG.get(_DISABLE_SEC) if hasattr(store, "_CONFIG") else None
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
                        _sec_all = store._CONFIG.get(_PERM_SEC) if hasattr(store, "_CONFIG") else None
                        if _longer_exempts(raw_n, len(_norm_cmd(k)), _sec_all,
                                           lambda _av: str(_av).strip() != _ADMIN_ONLY):
                            return None
                    except Exception:
                        pass
                    return k
            return None
        sec = store._CONFIG.get(_PERM_SEC) if hasattr(store, "_CONFIG") else None
        if not isinstance(sec, dict):
            return None
        hit = None
        for k, v in sec.items():
            k = str(k)
            if not k or str(v).strip() != _ADMIN_ONLY:
                continue
            if raw_n.startswith(_norm_cmd(k)) and (hit is None or len(_norm_cmd(k)) > len(_norm_cmd(hit))):
                hit = k
        if hit is not None:
            if _longer_exempts(raw_n, len(_norm_cmd(hit)), sec,
                               lambda _av: str(_av).strip() != _ADMIN_ONLY):
                return None
        return hit
    except Exception:
        return None



# ==================== pipeline（原 router/pipeline.py 并入） ====================
def handle(gid, qq, raw, is_admin=False, store=None, engines=None, superadmin_mod=None):
    # 自定义索引版本兜底：handle_cfg_save 直改 _CONFIG 不走 set_config 时 ver 未 bump，
    # 每次使用 _CUSTOM_IDX 前以 ver+内容指纹重建，避免 stale
    try:
        if store is not None:
            _custom_idx(store)
    except Exception:
        pass
    # 总开关：完全静默，包括超管，最高优先级
    try:
        if store and store.cfg("总开关配置", "总开关", "真") != "真":
            return None
    except Exception:
        pass
    # 群组开关：按 gid 静默，包括超管
    if gid and store:
        try:
            if store.cfg("群组开关配置", str(gid), "真") != "真":
                return None
        except Exception:
            pass
    # 维护开关（全局＋本群）：开则全员（含超管）不再执行业务；仅被@时回一条维护通知，
    # 其余完全静默。聊天内无法自救关闭维护，WebUI 为唯一控制面（§7.8）。
    try:
        _maint_g = bool(store) and store.cfg("维护配置", "维护开关", "假") == "真"
    except Exception:
        _maint_g = False
    try:
        _maint_l = (gid and str(gid).isdigit() and bool(store)
                    and store.recall_get("group_maint_%s" % gid, "0") == "1")
    except Exception:
        _maint_l = False
    if _maint_g or _maint_l:
        try:
            _pa = getattr(store, "parse_at", None) if store is not None else None
            # 被@才回一条：走 storage.parse_at（CQ:at,qq=/@QQ/@昵称），防 "[CQ:at" 子串误判
            _mentioned = (_pa(str(raw or ""))[0] is not None) if callable(_pa) else ("[CQ:at" in str(raw or ""))
        except Exception:
            _mentioned = ("[CQ:at" in str(raw or ""))
        if _mentioned:
            try:
                return store.cfg("维护配置", "维护信息", "🚧 维护中")
            except Exception:
                return "🚧 维护中"
        return None
    if raw.strip() in ("主菜单", "菜单", "系统菜单"):
        return _MAIN_MENU
    if store:
        try:
            creply, raw = _custom_cmd(raw, store)
            if creply:
                # 纯自定义变量渲染（{name}/{qq}/{gid}/{time}/{coin}/{at}）且不再走名字前缀在 main 已跳过
                try:
                    creply = _render_vars(creply, gid, qq, store)
                except Exception:
                    pass
                return creply
        except Exception:
            pass
    dis = _cmd_disabled(raw, store) if store else None
    if dis:
        return None  # 被禁用指令完全静默（BY DESIGN：不提示 AT 用户）
    # 超管权限：命中 指令权限配置=超管 的指令，非超管一律静默（与超管系统同规则）
    if not is_admin and store:
        try:
            if _cmd_need_admin(raw, store):
                return None
        except Exception:
            pass
    # 依次分发 9 引擎（批量守卫预计算，单消息18次读→0次）
    _batch_map = _batch_guard_map(gid, is_admin, store) if store else {}
    if engines:
        for _eng in ("slave", "sign", "bank", "ent", "spirit", "ride", "guild", "adventure"):
            fn = engines.get(_eng)
            if not fn:
                continue
            matched = _matches_engine(raw, _eng, store)
            g = _batch_map.get(_eng) if _batch_map else (_guard(gid, _eng, is_admin, raw, store) if store else None)
            if g:
                if matched:
                    return None  # 系统已关：命中也不运行、不回复
                continue
            try:
                r = fn.handle(gid, qq, raw) if hasattr(fn, "handle") else fn(gid, qq, raw)
            except Exception as e:
                import traceback
                err_tb = traceback.format_exc()
                try:
                    from .logger import error as _log_err
                    _log_err(f"[{_eng}] handle异常: {e}\n{err_tb}")
                except Exception:
                    pass
                # 若消息明确匹配该系统指令却执行崩溃，绝不可静默吞掉！向用户反馈错误提示
                # 底层存储异常必须优雅降级为繁忙提示，严禁向群聊暴露 database is locked / rollback 等原始DB错误
                if matched:
                    sysname = _SYS_ENG.get(_eng, _eng)
                    try:
                        msg_l = str(e).lower()
                    except Exception:
                        msg_l = ""
                    if any(k in msg_l for k in ("database", "locked", "rollback", "transaction", "sqlite", "misuse")):
                        return f"【{sysname}系统】当前人数较多，系统繁忙，请稍后重试~"
                    return f"【{sysname}系统】处理指令时出现异常，请稍后重试（原因: {e}）"
                r = None
            if r:
                return apply_reply_override(raw, r, store)
    # 超管（复用同一批量map）
    matched_admin = _matches_engine(raw, "superadmin", store)
    if engines and superadmin_mod:
        g = _batch_map.get("superadmin") if _batch_map else (_guard(gid, "superadmin", is_admin, raw, store) if store else None)
        if g:
            if matched_admin:
                return None  # 系统已关：命中也不运行、不回复
        else:
            try:
                r = superadmin_mod.handle(gid, qq, raw, is_admin)
                if r:
                    return apply_reply_override(raw, r, store)
            except Exception as e:
                import traceback
                try:
                    from .logger import error as _log_err
                    _log_err(f"[superadmin] handle异常: {e}\n{traceback.format_exc()}")
                except Exception:
                    pass
                if matched_admin:
                    try:
                        _ml = str(e).lower()
                    except Exception:
                        _ml = ""
                    if any(k in _ml for k in ("database", "locked", "rollback", "transaction", "sqlite", "misuse")):
                        return "【超管系统】当前人数较多，系统繁忙，请稍后重试~"
                    return f"【超管系统】处理指令时出现异常，请稍后重试（原因: {e}）"
    elif engines and "superadmin" in engines:
        fn = engines["superadmin"]
        g = _batch_map.get("superadmin") if _batch_map else (_guard(gid, "superadmin", is_admin, raw, store) if store else None)
        if g:
            if matched_admin:
                return None  # 系统已关：命中也不运行、不回复
        else:
            try:
                r = fn.handle(gid, qq, raw, is_admin) if hasattr(fn, "handle") else fn(gid, qq, raw, is_admin)
                if r:
                    return apply_reply_override(raw, r, store)
            except Exception as e:
                import traceback
                try:
                    from .logger import error as _log_err
                    _log_err(f"[superadmin] handle异常: {e}\n{traceback.format_exc()}")
                except Exception:
                    pass
                if matched_admin:
                    try:
                        _ml2 = str(e).lower()
                    except Exception:
                        _ml2 = ""
                    if any(k in _ml2 for k in ("database", "locked", "rollback", "transaction", "sqlite", "misuse")):
                        return "【超管系统】当前人数较多，系统繁忙，请稍后重试~"
                    return f"【超管系统】处理指令时出现异常，请稍后重试（原因: {e}）"
    return None


__all__ = ["_MAIN_MENU", "_SYS_ENG", "_resolve_reply", "_norm_cmd",
           "apply_reply_override", "_sys_off", "_cfg_sys_off", "_guard",
           "clear_guard_cache", "_batch_guard_map",
           "_engine_cache_ver", "_get_engine_cmds", "_matches_engine",
           "_multi_reply", "_render_vars",
           "_custom_fp", "_custom_idx", "_custom_cmd", "_cmd_disabled", "_cmd_need_admin",
           "handle"]
