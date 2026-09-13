# -*- coding: utf-8 -*-
"""配置 API — schema / commands / get / save / auto_balance (覆盖28大系统全套平衡预设)"""
import asyncio
import math
import os
import json
try:
    from astrbot.api.web import json_response
except ImportError:
    def json_response(data, status=200):
        return data
from .web_utils import _err, get_req_json, no_cache_response

try:
    from .. import storage as ST
except ImportError:
    from core import storage as ST  # type: ignore

try:
    from .. import config as _cfg_layer
except ImportError:
    import config as _cfg_layer  # type: ignore


def _validate_config(norm, plugin_base=""):
    """校验已归一配置的已知字段；未知字段保留给兼容/专用 sidecar。"""
    base = plugin_base or os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    schema = _cfg_layer._load_schema(base)
    known = {}
    for sec, items in (schema.get("groups") or {}).items():
        for item in items or []:
            if isinstance(item, dict):
                known[(str(sec), str(item.get("key")))] = str(item.get("type", "string"))
    numeric = {}
    for sec, values in norm.items():
        if not isinstance(values, dict):
            continue
        for key, value in values.items():
            if value is None or (sec, str(key)) not in known:
                continue
            typ = known[(sec, str(key))]
            if typ not in ("int", "float"):
                continue
            try:
                number = float(value)
                if not math.isfinite(number):
                    raise ValueError
                if typ == "int" and number != int(number):
                    raise ValueError
            except (TypeError, ValueError):
                return f"{sec}.{key} 必须是{typ}"
            if "概率" in str(key) or "成功率" in str(key):
                if not 0 <= number <= 100:
                    return f"{sec}.{key} 必须在 0 到 100 之间"
            elif number < 0 and "变化下限" not in str(key):
                return f"{sec}.{key} 不能为负数"
            numeric[(sec, str(key))] = number
    for (sec, key), lower in list(numeric.items()):
        if not key.endswith("下限"):
            continue
        upper_key = key[:-2] + "上限"
        upper = numeric.get((sec, upper_key))
        if upper is not None and lower > upper:
            return f"{sec}.{key} 不能大于 {upper_key}"
    return None


async def handle_cfg_schema(request, plugin_base=""):
    try:
        base = plugin_base or os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        data = _cfg_layer._load_schema(base)
        return json_response(data)
    except Exception:
        return json_response({"groups": {}, "defaults": {}})


async def handle_commands(request, plugin_base=""):
    try:
        base = plugin_base or os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        out = _cfg_layer._collect_commands(base, ST)
        return json_response(out)
    except Exception as e:
        return _err(f"commands failed: {e}", 500)


async def handle_cfg_get(request):
    try:
        cfg = getattr(ST, "_CONFIG", {}) or {}
        # WebDAV 密钥回填显示（地址/用户名明文，密码恒空；密钥本体只在独立文件）
        try:
            if hasattr(ST, "wd_secret_load"):
                _sec = dict(ST.wd_secret_load() or {})
                if _sec and isinstance(cfg.get("备份配置"), dict):
                    cfg = {**cfg, "备份配置": {**cfg["备份配置"]}}
                    if _sec.get("WebDAV服务器地址"):
                        cfg["备份配置"]["WebDAV服务器地址"] = _sec["WebDAV服务器地址"]
                    if _sec.get("WebDAV用户名"):
                        cfg["备份配置"]["WebDAV用户名"] = _sec["WebDAV用户名"]
                    cfg["备份配置"]["WebDAV应用密码"] = ""
        except Exception:
            pass
        return no_cache_response(json_response(cfg))
    except Exception as e:
        return _err(f"get failed: {e}", 500)


async def handle_cfg_save(request, plugin_base=""):
    try:
        p = await get_req_json(request, default={})
        if not isinstance(p, dict) or not p:
            return _err("未能读取到有效配置数据(请求体为空或解析失败)，请重试", 400)
        norm = _cfg_layer._normalize_cfg(p)
        validation_error = _validate_config(norm, plugin_base)
        if validation_error:
            return _err(validation_error, 400)
        # WebDAV 密钥分存：地址/用户名按 payload 落独立文件（含清空语义），密码仅非空更新；
        # 内存/_CONFIG/镜像/快照/备份里一律留空，防泄露。
        _secrets_changed = False
        try:
            _bsec = norm.get("备份配置")
            if isinstance(_bsec, dict) and hasattr(ST, "wd_secret_set"):
                for _k in ("WebDAV服务器地址", "WebDAV用户名"):
                    if _k in _bsec:
                        if ST.wd_secret_set(_k, str(_bsec.get(_k) or "")):
                            _secrets_changed = True
                        _bsec[_k] = ""
                if "WebDAV应用密码" in _bsec:
                    if str(_bsec.get("WebDAV应用密码") or "") != "":
                        if ST.wd_secret_set("WebDAV应用密码", str(_bsec.get("WebDAV应用密码"))):
                            _secrets_changed = True
                    _bsec["WebDAV应用密码"] = ""
        except Exception:
            pass

        def _work():
            # 自定义三节显式删除语义：值为 null 即删键（前端删除/改名后发 {旧触发词:null}，
            # merge 语义下缺键≠删除，不加这段会假成功复活；仅限这三节，其他节 null 照常存）
            try:
                for _sec in ("自定义指令配置", "指令启用配置", "指令回复配置", "指令权限配置"):
                    _d = norm.get(_sec)
                    if isinstance(_d, dict):
                        for _k in [k for k, v in _d.items() if v is None]:
                            _d.pop(_k, None)
                            try:
                                if isinstance(ST._CONFIG.get(_sec), dict):
                                    ST._CONFIG[_sec].pop(_k, None)
                            except Exception:
                                pass
            except Exception:
                pass
            _coll_failed = []
            _mem_saved = False
            for sec, kv in norm.items():
                if sec in getattr(ST, "_COLL_FILES", {}):
                    # 商城/图鉴走独立 sidecar，不进内存/_CONFIG
                    try:
                        if ST.coll_merge(sec, kv) is False:
                            _coll_failed.append(sec)
                    except Exception:
                        _coll_failed.append(sec)
                    continue
                ST._CONFIG.setdefault(sec, {})
                ST._CONFIG[sec].update(kv)
                _mem_saved = True
            try:
                if hasattr(ST, "_bump_config_ver"):
                    ST._bump_config_ver()
            except Exception:
                pass
            # WebDAV 配置 DB 镜像写透（含用户主动清空语义）
            try:
                if hasattr(ST, "wd_cfg_backup"):
                    ST.wd_cfg_backup(norm.get("备份配置"))
            except Exception:
                pass
            # 全量配置自动快照（去重，删改乱可一键恢复）
            try:
                from .snapshots import auto_snapshot_if_changed as _auto_snap
                _auto_snap()
            except Exception:
                try:
                    from core.api.snapshots import auto_snapshot_if_changed as _auto_snap2
                    _auto_snap2()
                except Exception:
                    pass
            try:
                ST.save_config()
            except Exception:
                pass
            try:
                ST.sync_astrbot_config(ST._CONFIG)
            except Exception:
                pass
            if _coll_failed and not _mem_saved:
                return _err("save failed: %s" % "、".join(_coll_failed), 500)
            _resp = {"saved": True, "备份配置": ST._CONFIG.get("备份配置", {}), "webdav_secrets": "updated" if _secrets_changed else "kept"}
            if _coll_failed:
                _resp["coll_failed"] = _coll_failed
            return no_cache_response(json_response(_resp))

        import asyncio as _aio
        return await _aio.to_thread(_work)
    except Exception as e:
        return _err(f"save failed: {e}", 500)


PRESETS = {
    "standard": {
        "新手配置": {
            "现金": "5000", "体力": "150", "魅力": "50", "奖券": "5",
            "新手金币": "5000", "新手体力": "150", "新手魅力": "50", "新手奖券": "5"
        },
        "间隔配置": {
            "购买间隔": "1", "折磨间隔": "1", "打工间隔": "1",
            "打架间隔": "1", "学习间隔": "1", "祈福间隔": "5", "讨好间隔": "1",
            "造反间隔": "1", "释放间隔": "1", "赎身间隔": "30", "自由间隔": "30", "保护间隔": "10"
        },
        "费用配置": {
            "初始身价": "500", "工资比例": "35",
            "变化上限": "500", "变化下限": "-500", "买入身价上涨": "1.25", "赎身花费倍率": "1.3"
        },
        "概率配置": {
            "讨好概率": "65", "造反概率": "35", "折磨成功率": "75"
        },
        "祈福配置": {
            "祈福奖励下限": "500", "祈福奖励上限": "3000", "人品爆发概率": "5", "人品爆发奖励": "10000"
        },
        "签到配置": {
            "基础奖励": "500", "连签加成": "50", "金钱下限": "300", "金钱上限": "800",
            "体力下限": "20", "体力上限": "40", "魅力下限": "5", "魅力上限": "10",
            "奖券下限": "1", "奖券上限": "3", "体力价格": "30", "魅力价格": "50"
        },
        "抽奖配置": {
            "中奖率": "50", "现金奖": "600", "体力奖": "10", "魅力奖": "5"
        },
        "点赞配置": {
            "点赞数": "5"
        },
        "银行配置": {
            "打劫失败罚金": "500", "打劫成功概率": "50", "打劫消耗体力": "10", "打劫魅力减少": "2",
            "打劫金钱下限": "500", "打劫金钱上限": "3000", "打劫关押时间": "1",
            "打劫银行消耗体力": "15", "打劫银行魅力减少": "5", "打劫银行金钱下限": "2000", "打劫银行金钱上限": "8000",
            "打劫银行成功概率": "45", "打劫银行关押时间": "1", "赌博成功概率": "48", "赌博消耗体力": "5",
            "赌博魅力减少": "5", "赌博限定次数": "10", "赌博关押时间": "1", "赌博最大金额": "50000",
            "存取款消耗体力": "1", "存款利率": "2", "利息上限": "50000", "转账消耗体力": "1",
            "转账最小金额": "100", "转账接收额度": "999999999", "越狱消耗体力": "5", "越狱魅力减少": "2",
            "越狱成功概率": "60", "保释消耗体力": "5", "保释魅力减少": "5", "保释金钱下限": "1000", "保释金钱上限": "5000",
            "红包_最小金额": "200", "红包_最大金额": "50000", "红包_发体力": "2", "红包_抢体力": "1",
            "红包_抢魅力": "2", "存款期限": "1", "红包_间隔时间": "15", "红包_基本魅力": "1", "越狱关押时间": "1",
            "劫狱消耗体力": "5", "劫狱间隔": "1", "劫狱魅力减少": "0", "打劫银行间隔": "10", "进监狱增加体力": "10", "进监狱次数": "8"
        },
        "娱乐配置": {
            "抽签造价": "50", "扔炸弹_需要金钱": "5000", "扔炸弹_消耗体力": "10", "扔炸弹_魅力减少": "2",
            "扔炸弹_个数下限": "1", "扔炸弹_个数上限": "2", "扔炸弹_成功概率": "75", "扔炸弹_禁言下限": "1",
            "扔炸弹_禁言上限": "5", "抽签大吉奖励": "888", "抽签上签奖励": "388", "抽签中签奖励": "88",
            "猜拳奖励金币": "300", "猜拳奖励魅力": "2", "猜拳成功概率": "50", "猜拳消耗体力": "5",
            "猜拳需要金钱": "0", "猜数奖励金币": "500", "猜数奖励魅力": "3", "猜数消耗体力": "5",
            "猜数需要金钱": "0", "急转弯奖励金币": "300", "急转弯奖励魅力": "2", "急转弯消耗体力": "0", "急转弯需要金钱": "0", "猜字谜奖励金币": "300", "猜字谜奖励魅力": "2", "猜字谜消耗体力": "0",
            "接龙奖励金币": "20", "接龙奖励魅力": "0", "接龙消耗体力": "0", "接龙需要金钱": "0",
            "答题奖励金币": "300", "答题奖励魅力": "2", "答题消耗体力": "0", "二四点奖励金币": "500", "二四点奖励魅力": "3",
            "二四点消耗体力": "0", "二四点需要金钱": "0", "急转弯需要金钱": "0", "猜字谜需要金钱": "0", "答题需要金钱": "0"
        },
        "坐骑配置": {
            "开关": "真", "价格_企鹅": "20000", "价格_伞兵": "50000", "价格_宝驴": "100000",
            "价格_保时捷": "250000", "价格_法拉利": "500000", "价格_玛莎拉蒂": "800000",
            "价格_劳斯莱斯": "1500000", "价格_布加迪威龙": "3000000", "价格_私人航空": "8000000"
        },
        "帮派配置": {
            "开关": "真", "创建消耗金钱": "50000", "创建消耗体力": "200", "创建需要魅力": "500",
            "人数上限": "30", "帮战次数上限": "5", "升级需要帮贡": "50000", "福利基数": "2000",
            "修筑价格": "5000", "修筑上限": "50",
            "加入消耗体力": "5", "加入需要魅力": "100", "退出消耗体力": "5", "退出扣除魅力": "50",
            "解散消耗体力": "100", "解散扣除魅力": "500", "帮战获贡下限": "10", "帮战获贡上限": "30", "贡献下限": "50"
        },
        "冒险配置": {
            "冒险消耗体力": "10", "冒险需要金钱": "200", "冒险间隔": "5", "事件金钱下限": "200",
            "事件金钱上限": "800", "结局金钱下限": "1000", "结局金钱上限": "3000", "最大轮数": "8"
        },
        "精灵配置": {
            "开关": "真", "升级经验": "500", "最大等级": "100", "冒险间隔": "3", "等级加成下限": "2",
            "等级加成上限": "5", "精灵数量": "6", "魅力减少": "20", "大师球": "2", "奇异甜食": "5",
            "挑战奖励_金钱上限": "1000", "挑战奖励_经验下限": "300", "挑战奖励_经验上限": "600",
            "挑战扣除_金钱下限": "100", "挑战扣除_金钱上限": "300", "初始精灵_1": "叶子", "初始精灵_2": "火苗",
            "初始精灵_3": "水滴", "挑战奖励_金钱下限": "400", "挑战扣除_消耗体力": "5", "精灵球": "10"
        },
        "设置": {
            "货币名称": "金币", "奴隶个数": "3", "奴隶个数上限": "10", "奴隶位价格": "10000",
            "保护时长小时": "12", "保护费用": "1000", "抽武器花费": "1988",
            "奇遇触发概率": "10", "十连抽花费": "3000", "三十连抽花费": "8000", "五十连抽花费": "12000",
            "抽武器R概率": "55", "抽武器SR概率": "38", "抽武器SSR概率": "7", "R经验": "10", "SR经验": "100",
            "SSR经验": "500", "一星武器花费": "2000", "二星武器花费": "5000", "三星武器花费": "15000",
            "四星武器花费": "30000", "五星武器花费": "60000", "一星武器概率": "80", "二星武器概率": "60",
            "三星武器概率": "45", "四星武器概率": "30", "五星武器概率": "15", "一阶宝物花费": "10000",
            "二阶宝物花费": "25000", "三阶宝物花费": "50000", "一阶宝物概率": "60", "二阶宝物概率": "30", "三阶宝物概率": "10"
        },
        "商城图鉴": {
            "ride_shop": json.dumps({"企鹅": 20000, "伞兵": 50000, "宝驴": 100000, "保时捷": 250000, "法拉利": 500000, "玛莎拉蒂": 800000, "劳斯莱斯": 1500000, "布加迪威龙": 3000000, "私人航空": 8000000}, ensure_ascii=False)
        }
    },
    "casual": {
        "新手配置": {
            "现金": "10000", "体力": "300", "魅力": "100", "奖券": "15",
            "新手金币": "10000", "新手体力": "300", "新手魅力": "100", "新手奖券": "15"
        },
        "间隔配置": {
            "购买间隔": "1", "折磨间隔": "1", "打工间隔": "1",
            "打架间隔": "1", "学习间隔": "1", "祈福间隔": "3", "讨好间隔": "1",
            "造反间隔": "1", "释放间隔": "1", "赎身间隔": "30", "自由间隔": "30", "保护间隔": "5"
        },
        "费用配置": {
            "初始身价": "1000", "工资比例": "50",
            "变化上限": "1000", "变化下限": "-200", "买入身价上涨": "1.35", "赎身花费倍率": "1.1"
        },
        "概率配置": {
            "讨好概率": "80", "造反概率": "20", "折磨成功率": "88"
        },
        "祈福配置": {
            "祈福奖励下限": "1000", "祈福奖励上限": "6000", "人品爆发概率": "15", "人品爆发奖励": "30000"
        },
        "签到配置": {
            "基础奖励": "1000", "连签加成": "100", "金钱下限": "800", "金钱上限": "2000",
            "体力下限": "20", "体力上限": "40", "魅力下限": "5", "魅力上限": "10",
            "奖券下限": "1", "奖券上限": "3", "体力价格": "30", "魅力价格": "50"
        },
        "抽奖配置": {
            "中奖率": "60", "现金奖": "600", "体力奖": "10", "魅力奖": "5"
        },
        "点赞配置": {
            "点赞数": "10"
        },
        "银行配置": {
            "打劫失败罚金": "200", "打劫成功概率": "65", "打劫消耗体力": "5", "打劫魅力减少": "1",
            "打劫金钱下限": "1000", "打劫金钱上限": "6000", "打劫关押时间": "1",
            "打劫银行消耗体力": "10", "打劫银行魅力减少": "2", "打劫银行金钱下限": "5000", "打劫银行金钱上限": "15000",
            "打劫银行成功概率": "60", "打劫银行关押时间": "1", "赌博成功概率": "60", "赌博消耗体力": "5",
            "赌博魅力减少": "2", "赌博限定次数": "20", "赌博关押时间": "1", "赌博最大金额": "100000",
            "存取款消耗体力": "1", "存款利率": "3", "利息上限": "100000", "转账消耗体力": "1",
            "转账最小金额": "50", "转账接收额度": "999999999", "越狱消耗体力": "3", "越狱魅力减少": "1",
            "越狱成功概率": "80", "保释消耗体力": "3", "保释魅力减少": "2", "保释金钱下限": "500", "保释金钱上限": "2000",
            "红包_最小金额": "100", "红包_最大金额": "100000", "红包_发体力": "1", "红包_抢体力": "1",
            "红包_抢魅力": "1", "存款期限": "1", "红包_间隔时间": "10", "红包_基本魅力": "1", "越狱关押时间": "1",
            "劫狱消耗体力": "3", "劫狱间隔": "1", "劫狱魅力减少": "0", "打劫银行间隔": "5", "进监狱增加体力": "20", "进监狱次数": "8"
        },
        "娱乐配置": {
            "抽签造价": "20", "扔炸弹_需要金钱": "2000", "扔炸弹_消耗体力": "5", "扔炸弹_魅力减少": "1",
            "扔炸弹_个数下限": "1", "扔炸弹_个数上限": "2", "扔炸弹_成功概率": "85", "扔炸弹_禁言下限": "1",
            "扔炸弹_禁言上限": "3", "抽签大吉奖励": "1888", "抽签上签奖励": "888", "抽签中签奖励": "288",
            "猜拳奖励金币": "600", "猜拳奖励魅力": "5", "猜拳成功概率": "60", "猜拳消耗体力": "2",
            "猜拳需要金钱": "0", "猜数奖励金币": "1000", "猜数奖励魅力": "6", "猜数消耗体力": "2",
            "猜数需要金钱": "0", "急转弯奖励金币": "600", "急转弯奖励魅力": "4", "急转弯消耗体力": "0",
            "猜字谜奖励金币": "600", "猜字谜奖励魅力": "4", "猜字谜消耗体力": "0", "接龙奖励金币": "20",
            "接龙奖励魅力": "0", "接龙消耗体力": "0", "接龙需要金钱": "0", "答题奖励金币": "600",
            "答题奖励魅力": "4", "答题消耗体力": "0", "二四点奖励金币": "1000", "二四点奖励魅力": "6",
            "二四点消耗体力": "0", "二四点需要金钱": "0", "急转弯需要金钱": "0", "猜字谜需要金钱": "0", "答题需要金钱": "0"
        },
        "坐骑配置": {
            "开关": "真", "价格_企鹅": "10000", "价格_伞兵": "25000", "价格_宝驴": "50000",
            "价格_保时捷": "120000", "价格_法拉利": "250000", "价格_玛莎拉蒂": "400000",
            "价格_劳斯莱斯": "800000", "价格_布加迪威龙": "1500000", "价格_私人航空": "4000000"
        },
        "帮派配置": {
            "开关": "真", "创建消耗金钱": "20000", "创建消耗体力": "100", "创建需要魅力": "200",
            "人数上限": "50", "帮战次数上限": "8", "升级需要帮贡": "20000", "福利基数": "4000",
            "修筑价格": "2000", "修筑上限": "100",
            "加入消耗体力": "2", "加入需要魅力": "50", "退出消耗体力": "2", "退出扣除魅力": "20",
            "解散消耗体力": "50", "解散扣除魅力": "200", "帮战获贡下限": "20", "帮战获贡上限": "50", "贡献下限": "20"
        },
        "冒险配置": {
            "冒险消耗体力": "5", "冒险需要金钱": "100", "冒险间隔": "3", "事件金钱下限": "500",
            "事件金钱上限": "1500", "结局金钱下限": "2000", "结局金钱上限": "5000", "最大轮数": "6"
        },
        "精灵配置": {
            "开关": "真", "升级经验": "300", "最大等级": "100", "冒险间隔": "2", "等级加成下限": "3",
            "等级加成上限": "8", "精灵数量": "8", "魅力减少": "10", "大师球": "5", "奇异甜食": "10",
            "挑战奖励_金钱上限": "2000", "挑战奖励_经验下限": "500", "挑战奖励_经验上限": "1000",
            "挑战扣除_金钱下限": "50", "挑战扣除_金钱上限": "150", "初始精灵_1": "叶子", "初始精灵_2": "火苗",
            "初始精灵_3": "水滴", "挑战奖励_金钱下限": "800", "挑战扣除_消耗体力": "3", "精灵球": "20"
        },
        "设置": {
            "货币名称": "金币", "奴隶个数": "5", "奴隶个数上限": "15", "奴隶位价格": "5000",
            "保护时长小时": "12", "保护费用": "500", "抽武器花费": "1000",
            "奇遇触发概率": "20", "十连抽花费": "1500", "三十连抽花费": "4000", "五十连抽花费": "6000",
            "抽武器R概率": "45", "抽武器SR概率": "40", "抽武器SSR概率": "15", "R经验": "20", "SR经验": "200",
            "SSR经验": "1000", "一星武器花费": "1000", "二星武器花费": "2500", "三星武器花费": "8000",
            "四星武器花费": "15000", "五星武器花费": "30000", "一星武器概率": "90", "二星武器概率": "75",
            "三星武器概率": "60", "四星武器概率": "45", "五星武器概率": "30", "一阶宝物花费": "5000",
            "二阶宝物花费": "12000", "三阶宝物花费": "25000", "一阶宝物概率": "75", "二阶宝物概率": "45", "三阶宝物概率": "20"
        },
        "商城图鉴": {
            "ride_shop": json.dumps({"企鹅": 10000, "伞兵": 25000, "宝驴": 50000, "保时捷": 120000, "法拉利": 250000, "玛莎拉蒂": 400000, "劳斯莱斯": 800000, "布加迪威龙": 1500000, "私人航空": 4000000}, ensure_ascii=False)
        }
    },
    "hardcore": {
        "新手配置": {
            "现金": "1000", "体力": "80", "魅力": "20", "奖券": "2",
            "新手金币": "1000", "新手体力": "80", "新手魅力": "20", "新手奖券": "2"
        },
        "间隔配置": {
            "购买间隔": "1", "折磨间隔": "1", "打工间隔": "2",
            "打架间隔": "2", "学习间隔": "2", "祈福间隔": "8", "讨好间隔": "1",
            "造反间隔": "2", "释放间隔": "1", "赎身间隔": "30", "自由间隔": "30", "保护间隔": "15"
        },
        "费用配置": {
            "初始身价": "300", "工资比例": "25",
            "变化上限": "300", "变化下限": "-800", "买入身价上涨": "1.15", "赎身花费倍率": "1.5"
        },
        "概率配置": {
            "讨好概率": "50", "造反概率": "45", "折磨成功率": "60"
        },
        "祈福配置": {
            "祈福奖励下限": "200", "祈福奖励上限": "1500", "人品爆发概率": "2", "人品爆发奖励": "5000"
        },
        "签到配置": {
            "基础奖励": "200", "连签加成": "20", "金钱下限": "150", "金钱上限": "400",
            "体力下限": "10", "体力上限": "30", "魅力下限": "2", "魅力上限": "8",
            "奖券下限": "1", "奖券上限": "1", "体力价格": "80", "魅力价格": "50"
        },
        "抽奖配置": {
            "中奖率": "35", "现金奖": "500", "体力奖": "8", "魅力奖": "3"
        },
        "点赞配置": {
            "点赞数": "3"
        },
        "银行配置": {
            "打劫失败罚金": "1000", "打劫成功概率": "38", "打劫消耗体力": "20", "打劫魅力减少": "5",
            "打劫金钱下限": "200", "打劫金钱上限": "1500", "打劫关押时间": "2",
            "打劫银行消耗体力": "25", "打劫银行魅力减少": "10", "打劫银行金钱下限": "1000", "打劫银行金钱上限": "5000",
            "打劫银行成功概率": "30", "打劫银行关押时间": "2", "赌博成功概率": "40", "赌博消耗体力": "10",
            "赌博魅力减少": "10", "赌博限定次数": "5", "赌博关押时间": "2", "赌博最大金额": "20000",
            "存取款消耗体力": "2", "存款利率": "1", "利息上限": "20000", "转账消耗体力": "2",
            "转账最小金额": "200", "转账接收额度": "999999999", "越狱消耗体力": "10", "越狱魅力减少": "5",
            "越狱成功概率": "40", "保释消耗体力": "10", "保释魅力减少": "10", "保释金钱下限": "2000", "保释金钱上限": "8000",
            "红包_最小金额": "500", "红包_最大金额": "20000", "红包_发体力": "3", "红包_抢体力": "2",
            "红包_抢魅力": "3", "存款期限": "1", "红包_间隔时间": "20", "红包_基本魅力": "2", "越狱关押时间": "2",
            "劫狱消耗体力": "10", "劫狱间隔": "2", "劫狱魅力减少": "1", "打劫银行间隔": "20", "进监狱增加体力": "5", "进监狱次数": "8"
        },
        "娱乐配置": {
            "抽签造价": "100", "扔炸弹_需要金钱": "10000", "扔炸弹_消耗体力": "20", "扔炸弹_魅力减少": "5",
            "扔炸弹_个数下限": "1", "扔炸弹_个数上限": "1", "扔炸弹_成功概率": "60", "扔炸弹_禁言下限": "2",
            "扔炸弹_禁言上限": "10", "抽签大吉奖励": "500", "抽签上签奖励": "200", "抽签中签奖励": "50",
            "猜拳奖励金币": "150", "猜拳奖励魅力": "1", "猜拳成功概率": "45", "猜拳消耗体力": "10",
            "猜拳需要金钱": "0", "猜数奖励金币": "250", "猜数奖励魅力": "2", "猜数消耗体力": "10",
            "猜数需要金钱": "0", "急转弯奖励金币": "150", "急转弯奖励魅力": "1", "急转弯消耗体力": "0",
            "猜字谜奖励金币": "150", "猜字谜奖励魅力": "1", "猜字谜消耗体力": "0", "接龙奖励金币": "20",
            "接龙奖励魅力": "0", "接龙消耗体力": "0", "接龙需要金钱": "0", "答题奖励金币": "150",
            "答题奖励魅力": "1", "答题消耗体力": "0", "二四点奖励金币": "250", "二四点奖励魅力": "2",
            "二四点消耗体力": "0", "二四点需要金钱": "0", "急转弯需要金钱": "0", "猜字谜需要金钱": "0", "答题需要金钱": "0"
        },
        "坐骑配置": {
            "开关": "真", "价格_企鹅": "40000", "价格_伞兵": "100000", "价格_宝驴": "200000",
            "价格_保时捷": "500000", "价格_法拉利": "1000000", "价格_玛莎拉蒂": "1600000",
            "价格_劳斯莱斯": "3000000", "价格_布加迪威龙": "6000000", "价格_私人航空": "15000000"
        },
        "帮派配置": {
            "开关": "真", "创建消耗金钱": "100000", "创建消耗体力": "300", "创建需要魅力": "1000",
            "人数上限": "20", "帮战次数上限": "3", "升级需要帮贡": "100000", "福利基数": "1000",
            "修筑价格": "10000", "修筑上限": "30",
            "加入消耗体力": "10", "加入需要魅力": "200", "退出消耗体力": "10", "退出扣除魅力": "100",
            "解散消耗体力": "200", "解散扣除魅力": "1000", "帮战获贡下限": "5", "帮战获贡上限": "15", "贡献下限": "100"
        },
        "冒险配置": {
            "冒险消耗体力": "15", "冒险需要金钱": "500", "冒险间隔": "8", "事件金钱下限": "100",
            "事件金钱上限": "500", "结局金钱下限": "500", "结局金钱上限": "1500", "最大轮数": "10"
        },
        "精灵配置": {
            "开关": "真", "升级经验": "800", "最大等级": "100", "冒险间隔": "5", "等级加成下限": "1",
            "等级加成上限": "3", "精灵数量": "4", "魅力减少": "30", "大师球": "1", "奇异甜食": "2",
            "挑战奖励_金钱上限": "500", "挑战奖励_经验下限": "150", "挑战奖励_经验上限": "300",
            "挑战扣除_金钱下限": "150", "挑战扣除_金钱上限": "500", "初始精灵_1": "叶子", "初始精灵_2": "火苗",
            "初始精灵_3": "水滴", "挑战奖励_金钱下限": "200", "挑战扣除_消耗体力": "10", "精灵球": "5"
        },
        "设置": {
            "货币名称": "金币", "奴隶个数": "2", "奴隶个数上限": "6", "奴隶位价格": "20000",
            "保护时长小时": "24", "保护费用": "2000", "抽武器花费": "3000",
            "奇遇触发概率": "5", "十连抽花费": "5000", "三十连抽花费": "14000", "五十连抽花费": "22000",
            "抽武器R概率": "70", "抽武器SR概率": "27", "抽武器SSR概率": "3", "R经验": "5", "SR经验": "50",
            "SSR经验": "250", "一星武器花费": "4000", "二星武器花费": "10000", "三星武器花费": "30000",
            "四星武器花费": "60000", "五星武器花费": "120000", "一星武器概率": "70", "二星武器概率": "45",
            "三星武器概率": "30", "四星武器概率": "15", "五星武器概率": "5", "一阶宝物花费": "20000",
            "二阶宝物花费": "50000", "三阶宝物花费": "100000", "一阶宝物概率": "45", "二阶宝物概率": "15", "三阶宝物概率": "5"
        },
        "商城图鉴": {
            "ride_shop": json.dumps({"企鹅": 40000, "伞兵": 100000, "宝驴": 200000, "保时捷": 500000, "法拉利": 1000000, "玛莎拉蒂": 1600000, "劳斯莱斯": 3000000, "布加迪威龙": 6000000, "私人航空": 15000000}, ensure_ascii=False)
        }
    }
}


_BALANCE_SIG_KEYS = (
    ("签到配置", "金钱下限"), ("签到配置", "金钱上限"), ("签到配置", "连签加成"),
    ("银行配置", "存款利率"), ("银行配置", "打劫银行成功概率"),
    ("银行配置", "打劫银行金钱下限"), ("银行配置", "打劫银行金钱上限"),
    ("概率配置", "造反概率"), ("祈福配置", "祈福奖励下限"), ("祈福配置", "祈福奖励上限"),
    ("设置", "十连抽花费"), ("费用配置", "初始身价"),
)
# 注：设置.抽武器花费 刻意不进抽检——出厂即混合态（schema/引擎/标准=1988，休闲=1000），
# 无论用户动没动都会命中某档的反例，属永恒噪音；其余 12 键三档全异，检测力无损。


async def handle_balance_state(request):
    """平衡档位真实状态：逐档推断最佳匹配，防徽标与实际两张皮。
    规则：空=未自定义=运行时用内置，缺键不计偏离；三档取 mismatch 最少者；
    并列优先当前标记档，其次 standard。"""
    try:
        cfg = getattr(ST, "_CONFIG", {}) or {}
        marked = str(cfg.get("_active_balance_mode") or (cfg.get("设置") or {}).get("平衡模式") or "").strip()
        if marked not in PRESETS:
            marked = ""
        results = {}
        for mode, preset in PRESETS.items():
            mm = []
            for sec, key in _BALANCE_SIG_KEYS:
                try:
                    cur = ST.cfg(sec, key, "")
                    if cur == "":
                        continue  # 缺键=未自定义，不计偏离
                    want = preset.get(sec, {}).get(key, "")
                    if str(cur) != str(want):
                        mm.append({"sec": sec, "key": key, "cur": str(cur), "preset": str(want)})
                except Exception:
                    continue
            results[mode] = mm
        _tiebreak = marked or "standard"
        best = sorted(PRESETS.keys(),
                      key=lambda m: (len(results[m]), 0 if m == _tiebreak else 1, 0 if m == "standard" else 1))[0]
        mismatches = results[best]
        return json_response({"ok": True, "mode": best, "marked": marked or "standard",
                              "checked": len(_BALANCE_SIG_KEYS),
                              "mismatch": len(mismatches), "mismatches": mismatches[:8],
                              "modes": {m: len(results[m]) for m in PRESETS}})
    except Exception as e:
        return _err(f"balance state failed: {e}", 500)


async def handle_config_auto_balance(request):
    """一键应用28大系统智能数值平衡预设与奴隶全员身价联动校准"""
    try:
        data = await get_req_json(request, default={})

        mode = str(data.get("mode") or "standard").lower().strip()
        if mode not in PRESETS:
            mode = "standard"

        target_preset = PRESETS[mode]

        # 1. 平衡前快照记账（kv 快操作：覆盖前抓拍旧值；慢速全库冷备挪后见 §4）
        pre_snapshot = ""
        try:
            from .snapshots import auto_snapshot_if_changed as _auto_snap
            _auto_snap()
        except Exception:
            try:
                from core.api.snapshots import auto_snapshot_if_changed as _auto_snap2
                _auto_snap2()
            except Exception:
                pass
        try:
            pre_snapshot = str(ST.recall_get("cfgsnap__latest", "") or "")
            if pre_snapshot and not pre_snapshot.startswith("pre_balance_"):
                _raw = ST.recall_get("cfgsnap__" + pre_snapshot, "")
                if _raw:
                    _new_name = "pre_balance_%s_%s" % (mode, pre_snapshot)
                    ST.recall_set("cfgsnap__" + _new_name, _raw)
                    try:
                        _idx = json.loads(ST.recall_get("cfgsnap__index", "[]") or "[]")
                    except Exception:
                        _idx = []
                    if not isinstance(_idx, list):
                        _idx = []
                    _idx = [_new_name] + [x for x in _idx if x != _new_name]
                    try:
                        from .snapshots import _snap_index_save as _sidx
                    except Exception:
                        try:
                            from core.api.snapshots import _snap_index_save as _sidx  # type: ignore
                        except Exception:
                            _sidx = None
                    if _sidx is not None:
                        _sidx(_idx)  # 统一走 5 份上限 + 孤儿行清理
                    else:
                        ST.recall_set("cfgsnap__index", json.dumps(_idx[:5], ensure_ascii=False))
                    pre_snapshot = _new_name
        except Exception:
            pass
        # 2. 合并覆盖各系统配置（含当前模式标记，便于 WebUI 回显；内存毫秒级生效）
        try:
            ST._CONFIG.setdefault("设置", {})["平衡模式"] = mode
        except Exception:
            pass
        ST._CONFIG["_active_balance_mode"] = mode
        for sec, kv in target_preset.items():
            if sec in getattr(ST, "_COLL_FILES", {}):
                try:
                    ST.coll_merge(sec, kv)
                except Exception:
                    pass
                continue
            ST._CONFIG.setdefault(sec, {})
            ST._CONFIG[sec].update(kv)
        try:
            if hasattr(ST, "_bump_config_ver"):
                ST._bump_config_ver()
        except Exception:
            pass

        # 3. 落盘与同步
        try:
            ST.save_config()
        except Exception:
            pass
        try:
            ST.sync_astrbot_config(ST._CONFIG)
        except Exception:
            pass

        # 4. 全库冷备双保险（慢 I/O：放写盘之后，再慢也不影响本次生效；失败仅丢本次冷备）
        try:
            await asyncio.to_thread(ST.backup_user_data, True)
        except Exception:
            pass

        # 5. 联动校准所有奴隶身价（走 ST.group/save_group：持锁规范、缓存一致、中英键自动翻译）
        #    仅补齐零/空身价（正身价保留，避免新老玩家双轨套利；需重置请用清空指令）
        calibrated_slaves = 0
        target_init_price = int(target_preset.get("费用配置", {}).get("初始身价", 500))

        def _calibrate():
            count = 0
            try:
                if ST._DB is not None:
                    _cur = ST._DB.cursor()
                    _cur.execute("SELECT DISTINCT gid FROM groups")
                    _gids = [str(r[0]) for r in _cur.fetchall()]
                    for _gid in _gids:
                        try:
                            _g = ST.group(_gid)
                            _users = getattr(_g, "_users", {}) or {}
                            for _qq, _u in list(_users.items()):
                                try:
                                    if not isinstance(_u, dict):
                                        continue
                                    try:
                                        _cur_p = int(float(_u.get("price") or _u.get("worth") or 0))
                                    except Exception:
                                        _cur_p = 0
                                    if _cur_p <= 0:
                                        _u["price"] = target_init_price
                                        _u["worth"] = target_init_price
                                        try:
                                            if hasattr(_g, "mark_dirty"):
                                                _g.mark_dirty(_qq)
                                            else:
                                                _g._dirty = True
                                                _g._dirty_qqs.add(str(_qq))
                                        except Exception:
                                            try:
                                                _g._dirty = True
                                            except Exception:
                                                pass
                                        count += 1
                                except Exception:
                                    pass
                            ST.save_group(_gid)
                        except Exception:
                            pass
            except Exception:
                pass
            return count
        try:
            calibrated_slaves = await asyncio.to_thread(_calibrate)
        except Exception:
            pass

        mode_name_map = {
            "standard": "🟢 标准均衡模式 (全面适配)",
            "casual": "🟡 休闲高福利模式 (双倍掉落/超快回血)",
            "hardcore": "🔴 硬核博弈模式 (高风控/紧缩刺激)"
        }

        return json_response({
            "ok": True,
            "mode": mode,
            "mode_name": mode_name_map.get(mode, mode),
            "calibrated_slaves": calibrated_slaves,
            "pre_snapshot": pre_snapshot,
            "msg": f"🎉 成功应用【{mode_name_map.get(mode, mode)}】！已覆盖全28大系统奖励、惩罚、概率、新手礼包与冷却时间，补齐 {calibrated_slaves} 名零身价奴隶"
                 + (f"，平衡前快照 [{pre_snapshot}] 已保存（备份页→配置快照可一键恢复）" if pre_snapshot else "")
                 + "。"
        })
    except Exception as e:
        return _err(f"auto balance failed: {e}", 500)
