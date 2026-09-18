# -*- coding: utf-8 -*-
"""legacy_ini - 旧(NapCat/INI)群/用户ini解析入库（原 migration.py 独立，语义不变）"""
import configparser
import re
try:
    from .. import storage as ST
    from ...core.keymap import cn_to_en as _cn2en
except ImportError:
    from core import storage as ST
    try:
        from core.keymap import cn_to_en as _cn2en
    except Exception:
        def _cn2en(k): return k
try:
    from ...games.config.shop import RIDE_SHOP as _RIDE_SHOP_BUILTIN, RIDE_PRICES as _RIDE_PRICES_BUILTIN, TREASURES as _TREASURES_BUILTIN
except ImportError:
    try:
        from games.config.shop import RIDE_SHOP as _RIDE_SHOP_BUILTIN, RIDE_PRICES as _RIDE_PRICES_BUILTIN, TREASURES as _TREASURES_BUILTIN  # type: ignore
    except Exception:
        _RIDE_SHOP_BUILTIN = {}
        _RIDE_PRICES_BUILTIN = {}
        _TREASURES_BUILTIN = {}


def _handle_ini_content(content, rel_path=""):
    imported = 0
    try:
        cp = configparser.ConfigParser(interpolation=None)
        cp.optionxform = str
        cp.read_string(content)
    except Exception:
        return 0
    secs = cp.sections()
    digit_secs = [s for s in secs if s.isdigit()]
    # 推断 gid/qq（兼容 文件夹/文件名 双层）
    gid = None
    qq_from_file = None
    try:
        parent = os.path.basename(os.path.dirname(rel_path)) if rel_path else ""
        if parent.isdigit() and 5 <= len(parent) <= 12:
            gid = parent
        # 文件名 qq
        base = os.path.basename(rel_path) if rel_path else ""
        name_no_ext = os.path.splitext(base)[0]
        if name_no_ext.isdigit() and 5 <= len(name_no_ext) <= 12:
            qq_from_file = name_no_ext
            if not gid:
                # 目录可能是 gid
                gid = parent if parent.isdigit() else None
    except Exception:
        pass
    if not gid:
        m = re.search(r"(\d{5,12})", rel_path or "")
        if m:
            all_nums = re.findall(r"\d{5,12}", rel_path or "")
            gid = all_nums[-2] if len(all_nums) >= 2 else m.group(1)
    # 群共享 ini（digit Secs 为 QQ 列表）：如 <gid>.ini / nuli_slave/*.ini
    if digit_secs:
        if not gid:
            gid = "1000"
        # 分流：钱包/账户 vs 群档案（奴隶）
        _GROUP_EN = {"price","owner","purchase_price","purchase_time","protect_until","slave_slots","study_time","torture_time","fight_time","tip_time","flatter_time","revolt_time","free_time","coin_time","work_time","work_wage","work_status","weapon","weapon_exp","treasure","consecutive_days","ransom_time","name","protector","_work_wage"}
        for sec in digit_secs:
            qq = sec.strip()
            try:
                wallet_keys = ["现金总数", "现金", "金币", "货币", "金钱", "money", "cash_total"]
                hit = False
                for key in wallet_keys:
                    if cp.has_option(sec, key):
                        try:
                            val = int(float(cp.get(sec, key)))
                            cur = ST.coins_get(gid, qq)
                            if val != cur:
                                ST.coins_add(gid, qq, val - cur)
                            else:
                                if ST._DB.execute("SELECT 1 FROM wallet WHERE gid=? AND qq=?", (int(gid), int(qq))).fetchone() is None:
                                    ST.coins_add(gid, qq, 0)
                        except Exception:
                            pass
                        hit = True
                        break
                if not hit:
                    try:
                        if ST._DB.execute("SELECT 1 FROM wallet WHERE gid=? AND qq=?", (int(gid), int(qq))).fetchone() is None:
                            ST.coins_add(gid, qq, 0)
                    except Exception:
                        pass
                a = ST.acct(gid, qq)
                g = ST.group(gid)
                # 确保 DirtyDict
                gu = g[qq]
                for k in cp.options(sec):
                    if k in wallet_keys:
                        continue
                    nk = _cn2en(k)
                    v = cp.get(sec, k)
                    # 路由到群档案 vs 账户
                    if nk in _GROUP_EN or k in ["身价","主人","买入价格","购买时间","保护时间","奴隶位","武器","宝物","武器经验","身价","主人"]:
                        gu[nk] = v
                    else:
                        a.set(nk, v)
                # legacy English deposit_total -> deposit etc
                try:
                    if cp.has_option(sec, "deposit_total"):
                        a.set("deposit", cp.get(sec, "deposit_total"))
                    if cp.has_option(sec, "stamina_total"):
                        a.set("stamina", cp.get(sec, "stamina_total"))
                    if cp.has_option(sec, "charm_total"):
                        a.set("charm", cp.get(sec, "charm_total"))
                    if cp.has_option(sec, "lottery_total"):
                        a.set("lottery_tickets", cp.get(sec, "lottery_total"))
                    if cp.has_option(sec, "sign_count"):
                        a.set("sign_count", cp.get(sec, "sign_count"))
                except Exception:
                    pass
                ST.acct_save(gid, qq)
                # 签到次数同步到群档案
                try:
                    if cp.has_option(sec, "签到次数"):
                        gu["total_sign_days"] = cp.get(sec, "签到次数")
                        if cp.has_option(sec, "连签天数"):
                            gu["shadow_streak"] = cp.get(sec, "连签天数")
                except Exception:
                    pass
                ST.save_group(gid)
                imported += 1
            except Exception:
                pass
        # 后缀节 [QQ武器]/[QQ坐骑]：旧库把坐骑/部分宝物计数散落在此，主循环按 digit 节处理会整段丢失。
        # 归类：坐骑名（内置商城表）→ 账户 rides.list；宝物名/×升阶 → 群档案 treasure 名单＋账户计数；
        # 未知键 → 群档案原样保留（不丢数据，展示层只读已知键）。
        try:
            _ride_names = set((_RIDE_SHOP_BUILTIN or {}).keys()) | set((_RIDE_PRICES_BUILTIN or {}).keys())
            _tre_names = set((_TREASURES_BUILTIN or {}).keys()) | {"酒神葫芦", "四象护符"}
            try:
                for _tk in (ST.cfg("设置", "宝物", "") or "").split("|") + (ST.cfg("设置", "treasure", "") or "").split("|"):
                    _tk = str(_tk or "").strip()
                    if _tk:
                        _tre_names.add(_tk)
            except Exception:
                pass
            import re as _re_sfx
            _sfx = {}
            for _sec in secs:
                _m = _re_sfx.match(r"^(\d{5,12})(武器|坐骑)$", str(_sec or "").strip())
                if not _m:
                    continue
                _sfx.setdefault(str(_m.group(1)), []).append(str(_sec))
            for _qq, _seclist in _sfx.items():
                try:
                    _a = ST.acct(gid, _qq)
                    _g = ST.group(gid)
                    _gu = _g[_qq]
                    _touched = False
                    for _sec in _seclist:
                        try:
                            _items = list(cp.items(_sec))
                        except Exception:
                            continue
                        for _k, _v in _items:
                            _k = str(_k or "").strip()
                            if not _k:
                                continue
                            try:
                                _iv = int(float(str(_v or "0").strip() or "0"))
                            except Exception:
                                _iv = 0
                            if _k in _ride_names:
                                # 坐骑：并入 rides.list（去重）
                                try:
                                    _r = json.loads(_a.get("rides", "{}") or "{}")
                                    if not isinstance(_r, dict):
                                        _r = {}
                                except Exception:
                                    _r = {}
                                _lst = _r.get("list")
                                if not isinstance(_lst, list):
                                    _lst = []
                                if _k not in _lst:
                                    _lst.append(_k)
                                    _touched = True
                                _r["list"] = _lst
                                _a.set("rides", json.dumps(_r, ensure_ascii=False))
                            elif _k in _tre_names or _k.endswith("升阶"):
                                # 宝物计数/升阶：计数进账户（与 digit 节同口径 _cn2en），名单并入群档案
                                _base = _k[:-2] if _k.endswith("升阶") else _k
                                try:
                                    _a.set(_cn2en(_k), str(_v))
                                except Exception:
                                    pass
                                try:
                                    _tl = [t for t in str(_gu.get("treasure", "") or "").split("|") if t]
                                    if _base and _base not in _tl:
                                        _tl.append(_base)
                                        _touched = True
                                    _gu["treasure"] = "|".join(_tl)
                                except Exception:
                                    pass
                                _touched = True
                            else:
                                try:
                                    _gu[_cn2en(_k)] = str(_v)
                                    _touched = True
                                except Exception:
                                    pass
                    if _touched:
                        try:
                            ST.acct_save(gid, _qq)
                        except Exception:
                            pass
                        try:
                            ST.save_group(gid)
                        except Exception:
                            pass
                        imported += 1
                except Exception:
                    pass
        except Exception:
            pass
        return imported
    # 单用户 ini（文件名=QQ，父目录=gid）：如 精灵系统/游戏账户/<gid>/<qq>.ini
    # 若 rel_path 仅为文件名导致 gid==qq 或 gid 缺失，则尝试从 DB 推断真实 gid
    if qq_from_file and qq_from_file.isdigit() and (not gid or gid == qq_from_file):
        # 文件名为 QQ 且父目录丢失（单文件上传），尝试用库中最大群推断
        try:
            cand_gids = []
            if ST._DB is not None:
                for (cg,) in ST._DB.execute("SELECT DISTINCT gid FROM wallet").fetchall():
                    cand_gids.append(str(cg))
                for (cg,) in ST._DB.execute("SELECT DISTINCT gid FROM groups").fetchall():
                    if str(cg) not in cand_gids:
                        cand_gids.append(str(cg))
            # 优先成员最多的群
            if cand_gids:
                # 选成员最多的
                best = None; best_cnt = -1
                for cg in cand_gids:
                    try:
                        cnt = ST._DB.execute("SELECT COUNT(DISTINCT qq) FROM wallet WHERE gid=?", (int(cg),)).fetchone()[0] or 0
                    except Exception:
                        cnt = 0
                    if cnt > best_cnt:
                        best_cnt = cnt; best = cg
                if best and best_cnt>0:
                    gid = best
                else:
                    gid = cand_gids[0]
            # 若仍无，尝试从配置中取群组开关已配置的 gid
            if not gid or gid == qq_from_file:
                try:
                    sec = ST._CONFIG.get("群组开关配置") if hasattr(ST, "_CONFIG") else {}
                    if isinstance(sec, dict):
                        for k in sec.keys():
                            if str(k).isdigit() and str(k) != qq_from_file:
                                gid = str(k); break
                except Exception:
                    pass
        except Exception:
            pass
        # 仍无法推断则回退中性 gid（用 qq 作 gid 会导致显示异常；与上游 1000 约定一致）
        if gid == qq_from_file:
            gid = "1000"
    if qq_from_file and gid and qq_from_file.isdigit():
        qq = qq_from_file
        try:
            # 精灵系统单用户
            if any(s in secs for s in ["我的精灵","精灵列表","我的背包","精灵冒险"]):
                a = ST.acct(gid, qq)
                sp = {}
                try:
                    sp = json.loads(a.get("spirits", "{}") or "{}")
                    if not isinstance(sp, dict):
                        sp = {}
                except Exception:
                    sp = {}
                # 精灵列表：键须有同名属性节（LV）才算一条精灵，否则是分类占位（如 背包=1）直接跳过
                lst = []
                _listed = set()
                if cp.has_section("精灵列表"):
                    for name, val in cp.items("精灵列表"):
                        name = name.strip()
                        if not name or val.strip() != "1":
                            continue
                        if not cp.has_section(name):
                            continue
                        _listed.add(name)
                        it = {"name": name}
                        # LV/EXP/HP/攻击/防御/特攻/特防/速度
                        sec_items = dict(cp.items(name))
                        try:
                            it["level"] = int(float(sec_items.get("LV", "1") or "1"))
                        except Exception:
                            it["level"] = 1
                        try:
                            it["exp"] = int(float(sec_items.get("EXP", "0") or "0"))
                        except Exception:
                            it["exp"] = 0
                        for cn_key, en_key in [("HP","hp"),("攻击","atk"),("防御","def"),("特攻","spa"),("特防","spd"),("速度","spe")]:
                            try:
                                if cn_key in sec_items:
                                    it[en_key] = int(float(sec_items[cn_key] or "0"))
                            except Exception:
                                pass
                        # 额外保留收服信息
                        for k in ["收服地点","收服时间"]:
                            if k in sec_items:
                                it[k] = sec_items[k]
                        lst.append(it)
                # 收服名保留：[收服精灵]/收服精灵 有名但无属性节时，留一条 1 级占位（不丢名）
                try:
                    if cp.has_section("收服精灵") and cp.has_option("收服精灵", "收服精灵"):
                        _cn = cp.get("收服精灵", "收服精灵").strip()
                        if _cn and _cn not in _listed and not any(it.get("name") == _cn for it in lst):
                            lst.append({"name": _cn, "level": 1, "exp": 0})
                except Exception:
                    pass
                # 背包：新系统 shop/bag 全是中文名，键必须原样中文存（禁 _cn2en 译成拼音，否则买/用对不上）
                bag = {}
                if cp.has_section("我的背包"):
                    for k, v in cp.items("我的背包"):
                        try:
                            _bk = str(k or "").strip()
                            if not _bk:
                                continue
                            _bv = int(float(v or "0"))
                            if _bv:
                                bag[_bk] = _bv
                        except Exception:
                            pass
                # 出战精灵：[精灵冒险]/出战精灵优先；[我的精灵]/出战精灵 非数字且在列表中时兜底
                active = ""
                if cp.has_section("精灵冒险") and cp.has_option("精灵冒险", "出战精灵"):
                    active = cp.get("精灵冒险", "出战精灵").strip()
                if not active and cp.has_section("我的精灵"):
                    try:
                        for _ak, _av in cp.items("我的精灵"):
                            if str(_ak or "").strip() == "出战精灵":
                                _cand = str(_av or "").strip()
                                if _cand and not _cand.isdigit() and any(it.get("name") == _cand for it in lst):
                                    active = _cand
                    except Exception:
                        pass
                # 组装
                if lst or bag or active:
                    sp["list"] = lst
                    sp["active"] = active
                    sp["bag"] = bag
                    sp["adopted"] = 1
                    a.set("spirits", json.dumps(sp, ensure_ascii=False))
                    ST.acct_save(gid, qq)
                    # 确保钱包占位
                    try:
                        if ST._DB.execute("SELECT 1 FROM wallet WHERE gid=? AND qq=?", (int(gid), int(qq))).fetchone() is None:
                            ST.coins_add(gid, qq, 0)
                    except Exception:
                        pass
                    imported = 1
                    return imported
            # 通用单用户：所有节直接写入账户/群档案
            a = ST.acct(gid, qq)
            g = ST.group(gid)
            gu = g[qq]
            for sec in secs:
                for k, v in cp.items(sec):
                    nk = _cn2en(k)
                    # 启发式：奴隶相关进 group，其余进 acct
                    if nk in {"price","owner","weapon","treasure","weapon_exp","slave_slots","protect_until"} or k in ["身价","主人","武器","宝物"]:
                        gu[nk] = v
                    else:
                        a.set(nk, v)
            ST.acct_save(gid, qq)
            ST.save_group(gid)
            try:
                if ST._DB.execute("SELECT 1 FROM wallet WHERE gid=? AND qq=?", (int(gid), int(qq))).fetchone() is None:
                    ST.coins_add(gid, qq, 0)
            except Exception:
                pass
            imported = 1
        except Exception:
            pass
        return imported
    return imported
