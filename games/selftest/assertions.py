# -*- coding: utf-8 -*-
"""探针效果断言：快照执行前后状态，判定分支是否真走到（替代纯文本判定）。

check 规约（None=只看回复有无）：
  ("contains", s1, ...)            回复含全部子串（菜单/榜单类）
  ("contains_any", s1, ...)        回复含任一子串（随机多结局）
  ("recall", key前缀, True/False)  recall 执行标记有空（每日一次类）
  ("wallet"|"deposit"|"stamina"|"charm"|"tickets"|"like"|"gong", "+/-/=/"!=")
  ("slave_owner", 目标qq|"", 期望主人qq/"<me>")   奴隶归属
  ("slave_cd", 字段, True/False)   动作冷却已提交/未提交（证明执行到提交点）
  ("slots", "+/-//=")              奴隶位数量变化
  ("work", True/False)             打工进行中（work_time 有空）
  ("pray",)                        祈福：提交或未到12点（均属正确处理）
  ("flatter_ok",)                  讨好：成功/撒娇任一真结局（读文案常量，不硬编码）
  ("spirit_has", 名|True|None)     精灵持有（True=非空，None=空）
  ("spirits_n", "+/-//=")          精灵数量变化
  ("ball", 名, "+/-//=")           背包球数变化
  ("active", 名|None)              出战精灵
  ("ride_has", 名) / ("ride_lacks", 名)
  ("welcome", 名|None)
  ("jail", True/False)
  ("guild", 名|None)
  ("redpack", 口令, True/False)
  ("ent", 标签|None)               会话归属
  ("adv", True/False)              冒险进行中
  ("adv_round", "+")               冒险轮次推进
  ("other_wallet", qq, "+/-//=/!=")
check 可为单个规约或规约列表（全过才算过）。
"""
import json as _json

try:
    from ... import storage as ST
    from .. import slave as _slave
    from .. import text_slave as _T
except ImportError:
    import storage as ST
    try:
        from games import slave as _slave
        from games import text_slave as _T
    except ImportError:
        _slave = None
        _T = None


def _i(v):
    try:
        return int(float(v or 0))
    except Exception:
        return 0


def _acct_int(gid, qq, key):
    try:
        return ST.acct(gid, qq).int(key)
    except Exception:
        return 0


def snap_state(gid, qq, others=()):
    """执行前快照：钱包/账户六维/精灵背包/坐骑/帮派/冒险/奴隶位"""
    s = {"others": {}}
    try:
        s["wallet"] = ST.coins_get(gid, qq)
    except Exception:
        s["wallet"] = 0
    for k in ("stamina", "charm", "deposit", "lottery_tickets", "like_count"):
        s[k] = _acct_int(gid, qq, k)
    try:
        a = ST.acct(gid, qq)
        try:
            s["spirits"] = _json.loads(a.get("spirits", "") or "{}")
        except Exception:
            s["spirits"] = {}
        try:
            s["rides"] = _json.loads(a.get("rides", "") or "{}")
        except Exception:
            s["rides"] = {}
        try:
            s["guild"] = _json.loads(a.get("guild", "") or "{}")
        except Exception:
            s["guild"] = {}
        try:
            s["adv"] = _json.loads(a.get("adventure", "") or "{}")
        except Exception:
            s["adv"] = {}
        s["jail"] = str(a.get("jail", "") or "")
    except Exception:
        s["spirits"] = {}
        s["rides"] = {}
        s["guild"] = {}
        s["adv"] = {}
        s["jail"] = ""
    for o in others or ():
        try:
            s["others"][str(o)] = ST.coins_get(gid, o)
        except Exception:
            pass
    return s


def _sp_list(snap):
    sp = snap.get("spirits") or {}
    lst = sp.get("list") if isinstance(sp, dict) else None
    return lst if isinstance(lst, list) else []


def _bag(snap):
    sp = snap.get("spirits") or {}
    bag = sp.get("bag") if isinstance(sp, dict) else None
    return bag if isinstance(bag, dict) else {}


def _slave_sec(gid, qq):
    try:
        if _slave is None:
            return {}
        st = _slave.state(gid)
        if st.has_section(qq):
            return dict(st[qq])
    except Exception:
        pass
    return {}


def _cd_key(field):
    """冷却键引擎口径：uset 经 _cn2en 转英文存储，断言必须同口径读"""
    try:
        if _slave is not None and hasattr(_slave, "_cn2en"):
            return _slave._cn2en(str(field))
    except Exception:
        pass
    return str(field)


def _cmp(op, before, after):
    d = after - before
    if op == "+":
        return d > 0
    if op == "-":
        return d < 0
    if op == "=":
        return d == 0
    if op == "!=":
        return d != 0
    return False


def _eval_one(spec, gid, qq, pre, reply):
    kind = spec[0] if isinstance(spec, (list, tuple)) and spec else ""
    # --- 回复文本类 ---
    if kind == "contains":
        miss = [s for s in spec[1:] if s not in reply]
        return (not miss, "" if not miss else "回复缺：" + "/".join(miss))
    if kind == "contains_any":
        ok = any(s in reply for s in spec[1:])
        return (ok, "" if ok else "回复非预期分支")
    if kind == "flatter_ok":
        cands = ["不为所动"]
        try:
            if _T is not None and hasattr(_T, "FLATTER_OK"):
                cands.append(str(_T.FLATTER_OK).split("{")[0])
        except Exception:
            pass
        ok = any(c in reply for c in cands if c)
        return (ok, "" if ok else "非讨好真结局")
    # --- 数值变化类 ---
    if kind in ("wallet", "deposit", "stamina", "charm", "tickets", "like", "gong"):
        if kind == "like":
            before = _i((pre.get("like_count", 0)))
            after = _acct_int(gid, qq, "like_count")
            key = "like_count"
        elif kind == "tickets":
            before = _i(pre.get("lottery_tickets", 0))
            after = _acct_int(gid, qq, "lottery_tickets")
            key = "lottery_tickets"
        elif kind == "gong":
            before = _i((pre.get("guild") or {}).get("gong", 0))
            try:
                after = _i(_json.loads(ST.acct(gid, qq).get("guild", "") or "{}").get("gong", 0))
            except Exception:
                after = 0
            key = "帮贡"
        elif kind == "wallet":
            before = _i(pre.get("wallet", 0))
            try:
                after = ST.coins_get(gid, qq)
            except Exception:
                after = 0
            key = "钱包"
        else:
            before = _i(pre.get(kind, 0))
            after = _acct_int(gid, qq, kind)
            key = kind
        ok = _cmp(spec[1], before, after)
        return (ok, "" if ok else f"{key}期望{spec[1]}实际{before}->{after}")
    if kind == "other_wallet":
        oqq, op = str(spec[1]), spec[2]
        before = _i(pre.get("others", {}).get(oqq, 0))
        try:
            after = ST.coins_get(gid, oqq)
        except Exception:
            after = 0
        ok = _cmp(op, before, after)
        return (ok, "" if ok else f"{oqq}钱包期望{op}实际{before}->{after}")
    if kind == "slots":
        before = _i(pre.get("slots", 0))
        after = _i(_slave_sec(gid, qq).get("slave_slots", 0))
        ok = _cmp(spec[1], before, after)
        return (ok, "" if ok else f"奴隶位期望{spec[1]}实际{before}->{after}")
    # --- 奴隶归属/冷却 ---
    if kind == "slave_owner":
        target = str(spec[1])
        want = str(spec[2])
        if want == "<me>":
            want = str(qq)
        post = _slave_sec(gid, target).get("owner", "")
        ok = str(post or "") == want
        return (ok, "" if ok else f"{target}主人期望{want}实际{post}")
    if kind == "slave_cd":
        field, want = str(spec[1]), bool(spec[2])
        sec = _slave_sec(gid, qq)
        has = bool(str(sec.get(_cd_key(field), "") or sec.get(field, "") or ""))
        return (has == want, "" if has == want else f"{field}期望{'已提交' if want else '空'}")
    if kind == "work":
        has = bool(str(_slave_sec(gid, qq).get("work_time", "") or ""))
        want = bool(spec[1])
        return (has == want, "" if has == want else "打工状态不符")
    if kind == "pray":
        import datetime as _dt
        has = bool(str(_slave_sec(gid, qq).get("pray_time", "") or ""))
        if _dt.datetime.now().hour < 12:
            return (True, "")
        return (has, "" if has else "祈福未提交")
    # --- 精灵 ---
    if kind == "spirit_has":
        want = spec[1]
        lst = _sp_list({"spirits": _cur_spirits(gid, qq)})
        if want is None:
            return (len(lst) == 0, "" if len(lst) == 0 else "仍有精灵")
        if want is True:
            return (len(lst) > 0, "" if len(lst) > 0 else "无精灵")
        return (any(isinstance(x, dict) and x.get("name") == want for x in lst),
                "" if any(isinstance(x, dict) and x.get("name") == want for x in lst) else f"缺{want}")
    if kind == "spirits_n":
        before = len(_sp_list(pre))
        after = len(_sp_list({"spirits": _cur_spirits(gid, qq)}))
        ok = _cmp(spec[1], before, after)
        return (ok, "" if ok else f"精灵数期望{spec[1]}实际{before}->{after}")
    if kind == "ball":
        name, op = str(spec[1]), spec[2]
        before = _i(_bag(pre).get(name, 0))
        after = _i(_bag({"spirits": _cur_spirits(gid, qq)}).get(name, 0))
        ok = _cmp(op, before, after)
        return (ok, "" if ok else f"{name}期望{op}实际{before}->{after}")
    if kind == "sp_active":
        want = spec[1]
        cur = _cur_spirits(gid, qq).get("active", "") if isinstance(_cur_spirits(gid, qq), dict) else ""
        want_s = "" if want is None else str(want)
        return (str(cur or "") == want_s, "" if str(cur or "") == want_s else f"出战期望{want_s}实际{cur}")
    if kind == "ride_active":
        want = spec[1]
        cur = _cur_rides(gid, qq).get("active", "") if isinstance(_cur_rides(gid, qq), dict) else ""
        want_s = "" if want is None else str(want)
        return (str(cur or "") == want_s, "" if str(cur or "") == want_s else f"切换期望{want_s}实际{cur}")
    # --- 坐骑 ---
    if kind == "ride_has":
        lst = (_cur_rides(gid, qq).get("list") or [])
        if spec[1] is None:
            return (len(lst) == 0, "" if len(lst) == 0 else "仍有坐骑")
        return (spec[1] in lst, "" if spec[1] in lst else f"缺坐骑{spec[1]}")
    if kind == "ride_lacks":
        lst = (_cur_rides(gid, qq).get("list") or [])
        return (spec[1] not in lst, "" if spec[1] not in lst else f"仍在{spec[1]}")
    if kind == "welcome":
        want = spec[1]
        cur = _cur_rides(gid, qq).get("welcome", "")
        want_s = "" if want is None else str(want)
        return (str(cur or "") == want_s, "" if str(cur or "") == want_s else f"欢迎期望{want_s}实际{cur}")
    # --- 监狱/帮派/红包 ---
    if kind == "jail":
        try:
            cur = str(ST.acct(gid, qq).get("jail", "") or "")
        except Exception:
            cur = ""
        want = bool(spec[1])
        return ((cur == "1") == want, "" if (cur == "1") == want else "监狱状态不符")
    if kind == "guild":
        want = spec[1]
        try:
            cur = _json.loads(ST.acct(gid, qq).get("guild", "") or "{}").get("name", "")
        except Exception:
            cur = ""
        want_s = "" if want is None else str(want)
        return (str(cur or "") == want_s, "" if str(cur or "") == want_s else f"帮派期望{want_s}实际{cur}")
    if kind == "redpack":
        pwd, want = str(spec[1]), bool(spec[2])
        try:
            row = ST._DB.execute("SELECT pwd FROM redpacks WHERE gid=? AND pwd=?", (int(gid), pwd)).fetchone() if ST._DB is not None else None
        except Exception:
            row = None
        has = row is not None
        return (has == want, "" if has == want else "红包状态不符")
    # --- 会话/冒险 ---
    if kind == "recall":
        try:
            cur = ST.recall_get(f"{spec[1]}_{gid}_{qq}", "")
        except Exception:
            cur = ""
        has = bool(str(cur or ""))
        want = bool(spec[2])
        return (has == want, "" if has == want else "执行标记缺失")
    if kind == "ent":
        want = spec[1]
        try:
            cur = ST.recall_get("ent_game_" + str(gid), "")
        except Exception:
            cur = ""
        want_s = "" if want is None else str(want)
        return (str(cur or "") == want_s, "" if str(cur or "") == want_s else f"会话期望{want_s}实际{cur}")
    if kind == "adv":
        try:
            cur = _json.loads(ST.acct(gid, qq).get("adventure", "") or "{}")
            has = bool(cur.get("map"))
        except Exception:
            has = False
        want = bool(spec[1])
        return (has == want, "" if has == want else "冒险状态不符")
    if kind == "wild":
        # 精灵冒险遭遇（存于 spirits.wild，与文字冒险 adventure 键无关）
        try:
            cur = _json.loads(ST.acct(gid, qq).get("spirits", "") or "{}")
            has = bool(cur.get("wild"))
        except Exception:
            has = False
        want = bool(spec[1])
        return (has == want, "" if has == want else "精灵遭遇状态不符")
    if kind == "adv_round":
        before = _i((pre.get("adv") or {}).get("round", 0))
        try:
            after = _i(_json.loads(ST.acct(gid, qq).get("adventure", "") or "{}").get("round", 0))
        except Exception:
            after = 0
        ok = _cmp(spec[1], before, after)
        return (ok, "" if ok else f"轮次期望{spec[1]}实际{before}->{after}")
    return (True, "")


def _cur_json(gid, qq, key):
    """账户 JSON 大字段唯一读取：spirits/rides 容错解析（_cur_spirits/_cur_rides 薄委托，零语义差）"""
    try:
        return _json.loads(ST.acct(gid, qq).get(key, "") or "{}")
    except Exception:
        return {}


def _cur_spirits(gid, qq):
    return _cur_json(gid, qq, "spirits")


def _cur_rides(gid, qq):
    return _cur_json(gid, qq, "rides")


def extra_qqs(check):
    """断言涉及的第三方 QQ（快照用）"""
    out = []
    specs = check if isinstance(check, list) else [check]
    for s in specs or []:
        try:
            if isinstance(s, (list, tuple)) and s and s[0] == "other_wallet":
                out.append(str(s[1]))
        except Exception:
            pass
    return out


def snap_full(gid, qq, check):
    pre = snap_state(gid, qq)
    # 奴隶位快照（slave section 口径）
    try:
        pre["slots"] = _i(_slave_sec(gid, qq).get("slave_slots", 0))
    except Exception:
        pre["slots"] = 0
    for o in extra_qqs(check):
        try:
            pre.setdefault("others", {})[o] = ST.coins_get(gid, o)
        except Exception:
            pass
    return pre


def eval_check(check, gid, qq, pre, reply):
    """返回 (ok, note)。check 为 None 时只看回复有无。"""
    if not check:
        t = str(reply or "")
        if "异常" in t or "无回复" in t:
            return (False, "无有效回复")
        return (True, "")
    specs = check if isinstance(check, list) else [check]
    for s in specs:
        ok, note = _eval_one(s, gid, qq, pre, reply)
        if not ok:
            return (False, note)
    return (True, "")
