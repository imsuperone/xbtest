# -*- coding: utf-8 -*-
"""自检执行器：虚拟号前置摆设 + 探针执行 + 判定 + 清档。只碰 999999 号虚拟数据。"""
import asyncio
import json
import re
import time

try:
    from ... import storage as ST
    from .. import slave, sign, bank, ent, spirit, ride, guild, adventure
    from .assertions import snap_full, eval_check
    from .probes import SUITES, SUITE_MODS
except ImportError:
    import storage as ST
    try:
        from games import slave, sign, bank, ent, spirit, ride, guild, adventure
    except ImportError:
        from ...games import slave  # type: ignore
    try:
        from games.selftest.assertions import snap_full, eval_check
        from games.selftest.probes import SUITES, SUITE_MODS
    except ImportError:
        from assertions import snap_full, eval_check  # type: ignore
        from probes import SUITES, SUITE_MODS  # type: ignore

_MODS = {"sign": sign, "spirit": spirit, "ent": ent, "bank": bank,
         "slave": slave, "ride": ride, "guild": guild, "adventure": adventure}

_RICH_SPIRITS = {"list": [{"name": "火苗", "level": 5, "hp": 40, "atk": 51, "def": 40, "spa": 34, "spd": 40}, {"name": "水滴", "level": 5, "hp": 40, "atk": 34, "def": 40, "spa": 51, "spd": 40}, {"name": "木叶", "level": 5, "hp": 40, "atk": 40, "def": 45, "spa": 40, "spd": 35}], "active": "火苗", "adopted": 1, "bag": {"精灵球": 5, "大师球": 2}}
_RICH_RIDES = {"list": ["企鹅", "宝驴"], "welcome": "企鹅", "active": "企鹅"}

_SCHEMA_DEFAULTS = None


def _seed_schema_defaults():
    """隔离环境播种 schema 默认值（缺键才补）：让断言跑在与线上一致的数值口径下。
    线上 AstrBot 本就会按下发全量默认配置，此处仅补缺口，不覆盖任何现值。"""
    global _SCHEMA_DEFAULTS
    try:
        if _SCHEMA_DEFAULTS is None:
            import copy as _copy
            import os as _os
            import json as _js
            base = _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
            p = _os.path.join(base, "_conf_schema.json")
            if not _os.path.isfile(p):
                # 兼容旧位（selftest 曾在插件根直属）
                p = _os.path.join(_os.path.dirname(base), "_conf_schema.json")
            if not _os.path.isfile(p):
                p = _os.path.join(_os.getcwd(), "_conf_schema.json")
            raw = _js.load(open(p, encoding="utf-8"))
            d = {}
            for sec, obj in raw.items():
                if isinstance(obj, dict) and isinstance(obj.get("items"), dict):
                    for k, it in obj["items"].items():
                        if isinstance(it, dict) and "default" in it:
                            d.setdefault(sec, {})[k] = _copy.deepcopy(it["default"])
            _SCHEMA_DEFAULTS = d
        for sec, kv in (_SCHEMA_DEFAULTS or {}).items():
            try:
                dst = ST._CONFIG.setdefault(sec, {})
                if isinstance(dst, dict):
                    for k, v in kv.items():
                        if k not in dst:
                            import copy as _copy2
                            dst[k] = _copy2.deepcopy(v)
            except Exception:
                pass
    except Exception:
        pass


def _ent_session_keys(v_gid, extra_qqs=()):
    """娱乐会话 recall 键全集（开局前清场与跑后清档共用）"""
    keys = [f"ent_game_{v_gid}"]
    for kind in ("chain", "trick", "miri", "quiz", "guessnum", "game24"):
        for suffix in ("", "_owner", "_players", "_start", "_last_time", "_used", "_last_qq"):
            keys.append(f"{kind}_{suffix}_{v_gid}" if suffix else f"{kind}_{v_gid}")
        for vq in ("10006", "10007", "10008", "10009", "10010"):
            keys.append(f"{kind}_{v_gid}_{vq}")
    for vq in list(extra_qqs or ()):
        for kind in ("chain", "trick", "miri", "quiz", "guessnum", "game24"):
            keys.append(f"{kind}_{v_gid}_{vq}")
    return keys


def _clear_ent_session(v_gid, extra_qqs=()):
    try:
        for k in _ent_session_keys(v_gid, extra_qqs):
            try:
                ST.recall_set(k, "")
            except Exception:
                pass
    except Exception:
        pass


_START_CMDS = ("开始接龙", "开始急转弯", "开始猜字谜", "开始猜数", "开始答题", "二四点")


def _setup_user(v_gid, v_qq, label, cmd):
    try:
        ST.coins_add(v_gid, v_qq, 1000000)
        ST.acct(v_gid, v_qq).set("stamina", "3000")
        ST.acct(v_gid, v_qq).set("charm", "3000")
        ST.acct(v_gid, v_qq).set("deposit", "50000")
        ST.acct(v_gid, v_qq).set("lottery_tickets", "5")
        ST.acct_save(v_gid, v_qq)
        try:
            slave.mark_known(v_gid, v_qq)
            try:
                if hasattr(slave, "set_note_name"):
                    slave.set_note_name(v_gid, v_qq, f"测试{v_qq[-2:]}")
                else:
                    slave.NOTE_NAMES[v_qq] = f"测试{v_qq[-2:]}"
            except Exception:
                slave.NOTE_NAMES[v_qq] = f"测试{v_qq[-2:]}"
        except Exception:
            pass
        if "没钱" in label:
            cur = ST.coins_get(v_gid, v_qq)
            ST.coins_add(v_gid, v_qq, -cur)
            ST.acct(v_gid, v_qq).set("deposit", "0")
            ST.acct_save(v_gid, v_qq)
        if "没存款" in label:
            ST.acct(v_gid, v_qq).set("deposit", "0")
            ST.acct_save(v_gid, v_qq)
        if "没体力" in label:
            ST.acct(v_gid, v_qq).set("stamina", "0")
            ST.acct_save(v_gid, v_qq)
        # ---- 精灵：按标签精确摆前置（无残留依赖） ----
        if label in ("我的精灵-无", "领养精灵-无", "领养精灵"):
            try:
                a = ST.acct(v_gid, v_qq)
                a.set("spirits", "{}")
                ST.acct_save(v_gid, v_qq)
            except Exception:
                pass
        elif label == "使用精灵球-没球":
            try:
                a = ST.acct(v_gid, v_qq)
                sp = dict(_RICH_SPIRITS)
                sp["bag"] = {}
                a.set("spirits", json.dumps(sp, ensure_ascii=False))
                ST.acct_save(v_gid, v_qq)
            except Exception:
                pass
        elif label == "丢弃精灵-末位保底":
            try:
                a = ST.acct(v_gid, v_qq)
                sp = {"list": [{"name": "火苗", "level": 5, "hp": 40, "atk": 51, "def": 40, "spa": 34, "spd": 40}], "active": "火苗", "adopted": 1, "bag": {}}
                a.set("spirits", json.dumps(sp, ensure_ascii=False))
                ST.acct_save(v_gid, v_qq)
            except Exception:
                pass
        elif "精灵" in label or "精灵" in cmd:
            # 通用：缺精灵才补（末位/没球专案已优先处理，不覆盖；坐骑等动词相同但无精灵二字的命令不受影响）
            try:
                a = ST.acct(v_gid, v_qq)
                cur = a.get("spirits", "")
                if not cur or cur == "{}" or "火苗" not in cur:
                    a.set("spirits", json.dumps(dict(_RICH_SPIRITS), ensure_ascii=False))
                    ST.acct_save(v_gid, v_qq)
            except Exception:
                pass
        # 使用精灵球成功分支：确保有球且有野生 encounter（顺序无关）
        if cmd.startswith("使用精灵球") and "没球" not in label:
            try:
                a = ST.acct(v_gid, v_qq)
                cur = a.get("spirits", "")
                sp = json.loads(cur) if cur and cur.strip().startswith("{") else {}
                if not isinstance(sp, dict):
                    sp = {}
                if not sp.get("list"):
                    sp = dict(_RICH_SPIRITS)
                bag = sp.get("bag") if isinstance(sp.get("bag"), dict) else {}
                bag["精灵球"] = max(int(bag.get("精灵球", 0) or 0), 1)
                ball = cmd.split()[-1] if len(cmd.split()) > 1 else "大师球"
                bag[ball] = max(int(bag.get(ball, 0) or 0), 1)
                sp["bag"] = bag
                sp["adopted"] = 1
                a.set("spirits", json.dumps(sp, ensure_ascii=False))
                ST.acct_save(v_gid, v_qq)
                # 无野生 encounter 则静默开一场（只摆 encounter，不经过 handle）
                if not sp.get("wild"):
                    try:
                        spirit.cmd_adventure(v_gid, v_qq, "原神")
                    except Exception:
                        pass
            except Exception:
                pass
        if "没券" in label:
            try:
                a = ST.acct(v_gid, v_qq)
                a.set("lottery_tickets", "0")
                ST.acct_save(v_gid, v_qq)
            except Exception:
                pass
        # ---- 坐骑：仅 -有 类标签给满配；裸动作标签测空态错误分支，不给 ----
        _ride_empty = label.endswith("-无") or "不存在" in label or label in ("我的坐骑-无", "我的坐骑", "查看欢迎-无", "回收欢迎-无",
                                                                              "丢弃坐骑", "切换坐骑", "设置欢迎", "查看欢迎", "回收欢迎", "查看坐骑")
        _ride_need = ("有坐骑" in label or ("已有" in label and "坐骑" in cmd)
                      or label in ("我的坐骑-有", "切换坐骑-有", "丢弃坐骑-有", "丢弃坐骑-欢迎中",
                                   "设置欢迎-有", "查看欢迎-有", "回收欢迎-有", "查看坐骑-存在"))
        if _ride_empty:
            try:
                a = ST.acct(v_gid, v_qq)
                a.set("rides", "{}")
                ST.acct_save(v_gid, v_qq)
            except Exception:
                pass
        elif _ride_need:
            try:
                a = ST.acct(v_gid, v_qq)
                a.set("rides", json.dumps(dict(_RICH_RIDES), ensure_ascii=False))
                ST.acct_save(v_gid, v_qq)
            except Exception:
                pass
        # ---- 帮派 ----
        if "有帮派" in label or ("已有" in label and "帮派" in label) or label in ["我的帮派-有", "成员列表-有", "帮派贡献-有钱", "帮战-有"]:
            try:
                a = ST.acct(v_gid, v_qq)
                pos = "帮主" if label in ["帮战-有", "帮派贡献-有钱"] else "成员"
                g = {"name": "测试已有帮", "pos": pos, "gong": 0, "build": 0, "intro": ""}
                a.set("guild", json.dumps(g, ensure_ascii=False))
                ST.acct_save(v_gid, v_qq)
            except Exception:
                pass
        if label == "帮战-有":
            try:
                b = ST.acct(v_gid, "10001")
                g2 = {"name": "测试帮", "pos": "帮主", "gong": 0, "build": 0, "intro": ""}
                b.set("guild", json.dumps(g2, ensure_ascii=False))
                ST.acct_save(v_gid, "10001")
                try:
                    slave.mark_known(v_gid, "10001")
                except Exception:
                    pass
            except Exception:
                pass
        if label.endswith("-无") and "帮派" in label or label in ["帮派列表-空", "我的帮派-无", "成员列表-无", "帮派贡献-没钱", "帮战-无帮派"]:
            try:
                a = ST.acct(v_gid, v_qq)
                a.set("guild", "{}")
                ST.acct_save(v_gid, v_qq)
            except Exception:
                pass
        # ---- 冒险：没体力/没钱先清场，保证 False 断言精确 ----
        if label in ("冒险-没体力", "冒险-没钱"):
            try:
                a = ST.acct(v_gid, v_qq)
                a.set("adventure", "{}")
                ST.acct_save(v_gid, v_qq)
            except Exception:
                pass
        # ---- 娱乐单开局探针：先清场，会话断言精确（序列探针 再开/有解/加入 除外） ----
        if cmd in _START_CMDS and "再开" not in label and "有解" not in label and not label.endswith("-加入"):
            _clear_ent_session(v_gid, (v_qq,))
        # ---- 结束冒险：预发复活币，保证可结束 ----
        if label == "结束冒险-有":
            try:
                ST.acct(v_gid, v_qq).set("revive_coins", "3")
                ST.acct_save(v_gid, v_qq)
            except Exception:
                pass
        try:
            v_gid_s = v_gid
            for tgt in ("10001", "10002", "10003", "10004", "10005"):
                try:
                    slave.mark_known(v_gid_s, tgt)
                    ST.coins_add(v_gid_s, tgt, 1000000)
                    ST.acct(v_gid_s, tgt).set("stamina", "3000")
                    ST.acct(v_gid_s, tgt).set("charm", "3000")
                    ST.acct_save(v_gid_s, tgt)
                    st = slave.state(v_gid_s)
                    if not st.has_section(tgt):
                        st.add_section(tgt)
                    u = st[tgt]
                    if not u.get("price"):
                        u["price"] = "1000"
                    if not u.get("owner"):
                        u["owner"] = ""
                    slave.save(v_gid_s)
                except Exception:
                    pass
            st = slave.state(v_gid)
            tgt = "10002"

            def _ensure_sec(q):
                try:
                    if not st.has_section(q):
                        st.add_section(q)
                except Exception:
                    pass
            if "买下-已是奴隶" in label:
                if st.has_section(tgt):
                    st[tgt]["owner"] = v_qq
                    slave.save(v_gid)
            elif "买下-有钱有位" in label or "买下" in label and "有钱" in label:
                if st.has_section(tgt):
                    st[tgt]["owner"] = ""
                    slave.save(v_gid)
            elif "释放-是主人" in label or "保护-是主人" in label or "保护-没钱" in label:
                _ensure_sec(v_qq)
                if st.has_section(tgt):
                    st[tgt]["owner"] = v_qq
                    slave.save(v_gid)
            elif "释放-非主人" in label or "保护-非主人" in label:
                if st.has_section(tgt):
                    st[tgt]["owner"] = "10001"
                    slave.save(v_gid)
            elif "释放-无奴隶" in label:
                if st.has_section(tgt):
                    st[tgt]["owner"] = ""
                    slave.save(v_gid)
            if "打架-有奴隶" in label:
                for owner, s in [(v_qq, "10003"), ("10002", "10004")]:
                    if not st.has_section(s):
                        st.add_section(s)
                    st[s]["owner"] = owner
                    st[s]["price"] = "1500"
                slave.save(v_gid)
                if st.has_section(v_qq):
                    st[v_qq]["slave_slots"] = "5"
                    slave.save(v_gid)
            if "打架-无奴隶" in label:
                for s in list(st.sections()):
                    if s.isdigit() and st[s].get("owner") == v_qq:
                        st[s]["owner"] = ""
                slave.save(v_gid)
            if "打工-有奴隶" in label:
                if not any(st[s].get("owner") == v_qq for s in st.sections() if s.isdigit()):
                    if not st.has_section("10003"):
                        st.add_section("10003")
                    st["10003"]["owner"] = v_qq
                    st["10003"]["price"] = "1200"
                    slave.save(v_gid)
            if "打工-无奴隶" in label:
                for s in list(st.sections()):
                    if s.isdigit() and st[s].get("owner") == v_qq:
                        st[s]["owner"] = ""
                slave.save(v_gid)
            if "讨好-有主人" in label or "造反-有主人" in label:
                _ensure_sec(v_qq)
                if st.has_section(v_qq):
                    st[v_qq]["owner"] = "10001"
                    slave.save(v_gid)
            if "讨好-无主人" in label or "造反-无主人" in label or "学习-无主人" in label:
                _ensure_sec(v_qq)
                if st.has_section(v_qq):
                    st[v_qq]["owner"] = ""
                    slave.save(v_gid)
            if "学习-有主人" in label:
                _ensure_sec(v_qq)
                if st.has_section(v_qq):
                    st[v_qq]["owner"] = "10001"
                    slave.save(v_gid)
            if "买下-无位" in label:
                if not st.has_section(v_qq):
                    st.add_section(v_qq)
                st[v_qq]["slave_slots"] = "1"
                st[v_qq]["price"] = "1000"
                if not st.has_section("10003"):
                    st.add_section("10003")
                st["10003"]["owner"] = v_qq
                st["10003"]["price"] = "1200"
                if st.has_section("10002"):
                    st["10002"]["owner"] = ""
                    if st["10002"].get("purchase_time", ""):
                        st["10002"]["purchase_time"] = ""
                slave.save(v_gid)
            if label.startswith("买下-") and "已是" not in label:
                try:
                    if st.has_section("10002"):
                        if st["10002"].get("owner", "") != "":
                            st["10002"]["owner"] = ""
                        if st["10002"].get("purchase_time", ""):
                            st["10002"]["purchase_time"] = ""
                        slave.save(v_gid)
                except Exception:
                    pass
            if label in ("释放", "保护"):
                # 裸动作用错误分支：目标保持无主，断言精确
                try:
                    if st.has_section("10002"):
                        st["10002"]["owner"] = ""
                        slave.save(v_gid)
                except Exception:
                    pass
            if "越狱" in label or "保释" in label:
                try:
                    import time as _t
                    import datetime as _dt
                    if "越狱" in label:
                        a = ST.acct(v_gid, v_qq)
                        a.set("jail", "1")
                        a.set("jail_start", _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                        a.set("release_timestamp", str(int(_t.time()) + 600))
                        if "没体力" in label:
                            a.set("stamina", "0")
                        else:
                            a.set("stamina", "3000")
                        ST.acct_save(v_gid, v_qq)
                    if "保释" in label:
                        tgt = "10001"
                        a2 = ST.acct(v_gid, tgt)
                        a2.set("jail", "1")
                        a2.set("jail_start", _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                        a2.set("release_timestamp", str(int(_t.time()) + 600))
                        ST.acct_save(v_gid, tgt)
                        try:
                            slave.mark_known(v_gid, tgt)
                        except Exception:
                            pass
                except Exception:
                    pass
            if any(k in label for k in ["存款", "取款", "转账", "发红包", "抢红包", "赌博", "打劫"]) and not any(k in label for k in ["越狱", "保释", "进监狱", "出狱", "劫狱"]):
                try:
                    a = ST.acct(v_gid, v_qq)
                    a.set("jail", "0")
                    a.set("jail_start", "")
                    a.set("release_timestamp", "")
                    ST.acct_save(v_gid, v_qq)
                except Exception:
                    pass
            if "保释" in label or "进监狱" in label:
                # 保释/进监狱要求执行者本身不在狱中（赌博/打劫失败会连带关人，先清）
                try:
                    a = ST.acct(v_gid, v_qq)
                    a.set("jail", "0")
                    a.set("jail_start", "")
                    a.set("release_timestamp", "")
                    ST.acct_save(v_gid, v_qq)
                except Exception:
                    pass
        except Exception:
            pass
    except Exception:
        pass


def _pick_test_qq(mod_name, label, prev_qq, n, A_RICH, B_POOR):
    if mod_name in ("slave", "ride"):
        return str(10006 + (n % 5))
    if mod_name == "guild" and "创建帮派" in label:
        if "有钱" in label:
            return "10008"
        elif "没钱" in label:
            return "10009"
        else:
            return "10010"
    if label == "抢红包-有口令" or label == "抢红包":
        return B_POOR
    if "再开" in label and "接龙" in label:
        # 第三人重开，测群级“进行中”拦截（冒险按人隔离，保持同人测冷却）
        return "10008"
    if "重复" in label and prev_qq:
        return prev_qq
    is_poor = any(k in label for k in ["没钱", "没券", "没体力", "没球", "没口令", "错口令"]) or label.endswith("-无") or label.endswith("-空") or label.endswith("-不存在")
    if "非主人" in label or "无主人" in label or "无奴隶" in label:
        is_poor = "没钱" in label
    if "无位" in label:
        is_poor = False
    return B_POOR if is_poor else A_RICH


def _verify_24(reply):
    """二四点有解校验：从开局回复解析 4 数，验算可解性"""
    try:
        m = re.search(r"【([\d\s]+)】", str(reply or ""))
        if not m:
            return "有解校验：❌未解析到题目"
        nums = tuple(sorted(int(x) for x in m.group(1).split()))
        if len(nums) != 4:
            return "有解校验：❌题目不足4数"
        ok24 = bool(ent._can_make_24_cached(nums))
        return "有解校验：✅可解" if ok24 else "有解校验：❌无解"
    except Exception as e:
        return f"有解校验：❌校验异常{e}"


def _execute_system(mod_name, probes, v_gid, A_RICH, B_POOR):
    """同步执行单系统探针表（重活，调用方负责扔线程池）。探针为 (label, cmd[, check])。
    返回 ([(label, cmd, mark, text)], v_qqs)。绝不碰真实群/真实QQ。"""
    mod = _MODS[mod_name]
    outs = []
    v_qqs = []
    prev_qq = None
    _seed_schema_defaults()
    for item in probes:
        label, cmd = item[0], item[1]
        check = item[2] if len(item) > 2 else None
        v_qq = _pick_test_qq(mod_name, label, prev_qq, len(v_qqs), A_RICH, B_POOR)
        if mod_name not in ("slave", "ride"):
            prev_qq = v_qq
        else:
            prev_qq = v_qq if "重复" in label else None
        v_qqs.append(v_qq)
        _setup_user(v_gid, v_qq, label, cmd)
        if mod_name == "slave":
            try:
                st2 = slave.state(v_gid)
                if st2.has_section(v_qq):
                    u2 = st2[v_qq]
                    for ck in ["flatter_time", "study_time", "torture_time", "protect_time", "pray_time", "打架时间", "造反时间", "讨好时间", "学习时间", "保护时间"]:
                        try:
                            mk = slave._cn2en(ck) if hasattr(slave, "_cn2en") else ck
                        except Exception:
                            mk = ck
                        # 引擎 uset 经 _cn2en 转英文存储，中英双键都清（防旧数据残留）
                        for kk in {ck, mk}:
                            try:
                                if kk in u2:
                                    u2[kk] = ""
                            except Exception:
                                pass
                    slave.save(v_gid)
            except Exception:
                pass
        if label.endswith("-加入"):
            try:
                ST.recall_set(f"ent_game_{v_gid}", "")
            except Exception:
                pass
        pre = snap_full(v_gid, v_qq, check)
        try:
            r = mod.handle(v_gid, v_qq, cmd)
            if not r:
                r = f"【{label}】无回复（虚拟环境）"
            if label == "二四点-有解校验":
                r = str(r) + "\r\n" + _verify_24(r)
            ok, note = eval_check(check, v_gid, v_qq, pre, str(r))
            mark = "✅" if ok else "❌"
            if not ok:
                r = str(r) + f"\r\n断言失败：{note}"
            outs.append((label, cmd, mark, str(r)[:800]))
        except Exception as e:
            outs.append((label, cmd, "❌", f"【{label}】异常: {e}"))
    return outs, v_qqs


def _cleanup_test_users(v_gid, v_qqs):
    """虚拟号清档：三表+红包+会话键+奴隶群档案+缓存（防跨轮污染）"""
    uniq = set((v_qqs or []) + ["10001", "10002", "10003", "10004", "10005", "10006", "10007", "10008", "10009", "10010"])
    try:
        for vq in uniq:
            try:
                ST._DB.execute("DELETE FROM wallet WHERE gid=? AND qq=?", (int(v_gid), int(vq)))
                ST._DB.execute("DELETE FROM accounts WHERE gid=? AND qq=?", (int(v_gid), int(vq)))
                ST._DB.execute("DELETE FROM groups WHERE gid=? AND qq=?", (int(v_gid), int(vq)))
            except Exception:
                pass
        try:
            ST._DB.execute("DELETE FROM redpacks WHERE gid=?", (int(v_gid),))
        except Exception:
            pass
        ST._DB.commit()
        for vq in uniq:
            ST._ACC_CACHE.pop((v_gid, vq), None)
        ST._GROUP_CACHE.pop(v_gid, None)
    except Exception:
        pass
    _clear_ent_session(v_gid, uniq)
    try:
        for vq in uniq:
            for k in (f"advt_{v_gid}_{vq}", f"ride_welcome_{v_gid}_{vq}", f"chouqian_{v_gid}_{vq}",
                      f"spadv_{v_gid}_{vq}"):
                try:
                    ST.recall_set(k, "")
                except Exception:
                    pass
            try:
                import datetime as _dt
                _today = _dt.date.today()
                ST.recall_set(f"gamble_{v_gid}_{vq}_{_today}", "")
                ST.recall_set(f"jailgo_{v_gid}_{vq}_{_today}", "")
                try:
                    import time as _tm
                    ST.recall_set(f"guildwar_{v_gid}_{vq}_{_tm.strftime('%Y%m%d')}", "")
                except Exception:
                    pass
            except Exception:
                pass
    except Exception:
        pass
    # 引擎内存缓存失效（帮派15秒成员缓存等）+ 测试昵称/已知名单 scrub，防跨轮污染真索引
    try:
        try:
            guild._invalidate_guild_cache(str(v_gid))
        except Exception:
            pass
        try:
            slave._KNOWN.pop(str(v_gid), None)
        except Exception:
            pass
        try:
            slave.NOTE_NAMES_BY_GROUP.pop(str(v_gid), None)
        except Exception:
            pass
        try:
            for vq in uniq:
                old = slave.NOTE_NAMES.pop(str(vq), None)
                if old:
                    try:
                        if slave.NOTE_NAMES_REV.get((str(v_gid), old)) == str(vq):
                            slave.NOTE_NAMES_REV.pop((str(v_gid), old), None)
                    except Exception:
                        pass
        except Exception:
            pass
    except Exception:
        pass
    try:
        st = slave.state(v_gid)
        for vq in uniq:
            try:
                if st.has_section(vq):
                    st.remove_section(vq)
            except Exception:
                pass
        slave.save(v_gid)
    except Exception:
        pass


async def _forward_texts(bot, gid, uin, title, texts, is_private):
    """合并转发（8秒熔断，uin 取机器人QQ防适配器拒收）"""
    if not bot or is_private:
        return False
    try:
        nodes = []
        for idx, txt in enumerate(texts):
            nodes.append({"type": "node", "data": {"name": f"{title}-{idx+1}", "uin": str(uin), "content": [{"type": "text", "data": {"text": txt[:4000]}}]}})
        await asyncio.wait_for(bot.call_action("send_group_forward_msg", group_id=int(gid), messages=nodes), timeout=8)
        return True
    except Exception as e:
        try:
            print(f"forward {title} failed: {e}")
        except Exception:
            pass
        return False


def _render_report(title, outs):
    """探针报告：逐条 verdict + 通过率汇总"""
    lines = []
    ok = 0
    for label, cmd, mark, text in outs:
        if mark == "✅":
            ok += 1
        lines.append(f"{mark}【{label}】\r\n指令：{cmd}\r\n回复：\r\n{text}")
    total = len(outs)
    head = f"{title} 通过 {ok}/{total}" + (" ✅全过" if ok == total else "")
    return head, lines, ok, total


async def handle_test_probes(raw, gid, qq, is_admin, event, is_private):
    if raw.strip() == "测试testxb all":
        pass
    elif raw.strip() not in SUITES:
        return None
    if not is_admin:
        try:
            event.stop_event()
        except Exception:
            pass
        return None  # 全静默（BY DESIGN，见 AIINFO）
    try:
        if raw.strip() == "测试testxb all":
            outs = []
            v_gid = "999999"
            A_RICH = "10006"
            B_POOR = "10007"
            v_qqs = []
            sys_order = [("测试testxb 2", "sign"), ("测试testxb 3", "spirit"), ("测试testxb 4", "ent"), ("测试testxb 5", "bank"), ("测试testxb 6", "slave"), ("测试testxb 7", "ride"), ("测试testxb 8", "guild"), ("测试testxb 9", "adventure")]
            for sys_key, mod_name in sys_order:
                # 重活扔线程池，主循环零阻塞；单条结构 (label, cmd, mark, text)
                sys_outs, sys_qqs = await asyncio.to_thread(
                    _execute_system, mod_name, SUITES.get(sys_key, []), v_gid, A_RICH, B_POOR)
                outs.append((sys_key, sys_outs))
                v_qqs += sys_qqs
            await asyncio.to_thread(_cleanup_test_users, v_gid, v_qqs)
            uin = getattr(slave, "BOT_UIN", "") or str(qq)
            bot = getattr(event, "bot", None)
            if bot and not is_private:
                sent = 0
                try:
                    for sys_key, sys_outs in outs:
                        head, lines, _ok, _total = _render_report(sys_key, sys_outs)
                        if not await _forward_texts(bot, gid, uin, sys_key, [head] + lines, is_private):
                            break
                        sent += 1
                    try:
                        event.stop_event()
                    except Exception:
                        pass
                    if sent == len(outs):
                        return f"__HANDLED__已发送测试testxb all {len(outs)}系统（逐条✅❌见转发）"
                except Exception as e:
                    try:
                        print(f"forward all failed: {e}")
                    except Exception:
                        pass
            merged = ""
            for sys_key, sys_outs in outs:
                head, lines, _ok, _total = _render_report(sys_key, sys_outs)
                merged += f"\n\n===== {sys_key}（{head}） =====\n\n" + "\n\n".join(lines)
            try:
                event.stop_event()
            except Exception:
                pass
            return merged
        key = raw.strip()
        mod_name = SUITE_MODS.get(key, "sign")
        v_gid = "999999"
        A_RICH = "10006"
        B_POOR = "10007"
        outs, v_qqs = await asyncio.to_thread(
            _execute_system, mod_name, SUITES[key], v_gid, A_RICH, B_POOR)
        await asyncio.to_thread(_cleanup_test_users, v_gid, v_qqs)
        head, lines, _ok, _total = _render_report(key, outs)
        uin = getattr(slave, "BOT_UIN", "") or str(qq)
        bot = getattr(event, "bot", None)
        if bot and not is_private:
            if await _forward_texts(bot, gid, uin, key, [head] + lines, is_private):
                try:
                    event.stop_event()
                except Exception:
                    pass
                return f"__HANDLED__已发送{key}合并转发（{head}）"
        merged = f"\n\n===== {key}（{head}） =====\n\n" + "\n\n".join(lines)
        try:
            event.stop_event()
        except Exception:
            pass
        return merged
    except Exception as e:
        try:
            event.stop_event()
        except Exception:
            pass
        return f"{raw.strip()} 异常: {e}"
