# -*- coding: utf-8 -*-
"""astrbot_plugin_xbbot_beta: 小白测试版统一模块（8大玩法引擎 + WebUI 管理台）。

导入约定（全仓唯一）：插件按包加载（真机 data.plugins.X / 测试命名包），
一律使用包内相对导入，绝无 sys.path 回退与双通道兜底。
"""
import os
import threading as _threading_mod
from importlib import import_module
from typing import Optional

from .adapters import AstrMessageEvent, MessageChain, Image, Context, Star
from . import storage as ST
from . import config as _cfg_layer
from . import messaging as _plat_layer
from . import router as _router_layer
from . import dispatch as _dispatch_all
from . import logger as _logger_layer
from .api.web_utils import _err
from .version import get_version as _get_version
from ..games import sign, bank, slave, ent, spirit, ride, guild, adventure, fishing
from . import superadmin

_HAS_CORE = True

# 平台层注入 Image 组件与 slave 模块（避免循环导入的注入点）
_plat_layer.bind(Image, slave)

# 配置层单源函数（供本文件与下游使用）
_maybe_dict = _cfg_layer._maybe_dict
_normalize_cfg = _cfg_layer._normalize_cfg
_fallback_cfg = _cfg_layer._fallback_cfg
# 平台层单源函数
_build_chain = _plat_layer._build_chain
_append_at_segments = _plat_layer._append_at_segments
_name_prefix = _plat_layer._name_prefix
_do_platform = _plat_layer._do_platform
# 分发流水线单文件（纯逻辑无 astrbot 依赖）
_dispatch_name_sync = _dispatch_test_menu = _dispatch_admins = _dispatch_reply = _dispatch_all

slave.log = lambda msg: _logger_layer.info(str(msg))

PLUGIN_ID = "astrbot_plugin_xbbot_beta"
PLUGIN_DESC = "小白测试版(奴/签/银/娱/私/灵/骑/超管/帮派/冒险+主菜单+WebUI), 现代SQLite存储"
try:
    PLUGIN_VERSION = _get_version()
except Exception:
    PLUGIN_VERSION = "unknown"

# 消息处理定长线程池：突发千群不再打爆默认无限池，与 ST._LOCK 串行叠加可控
# import 期不建池（工具链 import 零线程）：首个 XbBot 实例化/首消息时懒建，全局单例，永不 shutdown
_XB_EXEC = None
_XB_EXEC_WORKERS = 12
_GROUP_NAME_MEM = {}
_XB_EXEC_LOCK = _threading_mod.Lock()


def _get_exec():
    """消息线程池懒单例：并发度 12＋线程名前缀 xbb-msg 不变，语义与旧 import 期建池一致"""
    global _XB_EXEC
    ex = _XB_EXEC
    if ex is not None:
        return ex
    with _XB_EXEC_LOCK:
        if _XB_EXEC is not None:
            return _XB_EXEC
        try:
            from concurrent.futures import ThreadPoolExecutor as _TPE
            _XB_EXEC = _TPE(max_workers=_XB_EXEC_WORKERS, thread_name_prefix="xbb-msg")
        except Exception:
            _XB_EXEC = None
        return _XB_EXEC

_ENGINES = None  # 模块级单例：每消息重建10项字典+线程切换约0.2-0.5ms，启动即冻结
try:
    _ENGINES = {"slave": slave, "sign": sign, "bank": bank, "ent": ent, "spirit": spirit, "ride": ride, "guild": guild, "adventure": adventure, "fishing": fishing, "superadmin": superadmin}
except Exception:
    _ENGINES = None

def handle(gid, qq, raw, is_admin=False):
    """薄包装：直接委托 core.router.handle，保持与旧 handle 签名兼容"""
    try:
        if _router_layer and hasattr(_router_layer, "handle"):
            engines = _ENGINES or {"slave": slave, "sign": sign, "bank": bank, "ent": ent, "spirit": spirit, "ride": ride, "guild": guild, "adventure": adventure, "fishing": fishing, "superadmin": superadmin}
            return _router_layer.handle(gid, qq, raw, is_admin=is_admin, store=ST, engines=engines, superadmin_mod=superadmin)
    except Exception as e:
        import traceback
        if _logger_layer:
            try:
                _logger_layer.error(f"main.handle 异常: {e}\n{traceback.format_exc()}")
            except Exception:
                pass
        return f"系统处理异常，请稍后重试（{e}）"
    return None


_API_HANDLER_CACHE = {}


def _load_api_handler(mod_short, func_name):
    """双通道导入 API handler：插件根包绝对优先，顶层绝对回退。

    __package__ 为 `xxx.core` 时回溯到插件根 `xxx` 再拼 mod_short；
    真机只有 data.plugins.X 一条路，顶层回退仅本机直跑有效。"""
    cache_key = (str(mod_short), str(func_name))
    cached = _API_HANDLER_CACHE.get(cache_key)
    if cached is not None:
        return cached
    cands = []
    pkg = __package__ or ""
    # 插件根回溯：xxx.core 统一回到 xxx
    _root = pkg[:-len(".core")] if pkg.endswith(".core") else pkg
    if _root:
        cands.append(_root + "." + mod_short)
    if pkg and (not cands or cands[0] != pkg + "." + mod_short):
        cands.append(pkg + "." + mod_short)
    cands.append(mod_short)
    for cand in cands:
        try:
            fn = getattr(import_module(cand), func_name)
            _API_HANDLER_CACHE[cache_key] = fn
            return fn
        except (ImportError, ModuleNotFoundError, AttributeError):
            continue
    raise ImportError(f"cannot load API handler {mod_short}.{func_name}")


_PLUGIN_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _merge_persistent_config(data_dir):
    """三级高韧性持久配置自愈加载：
    1. SQLite kv 表 sys_config_json（最抗升级覆盖的持久数据库镜像）
    2. 外部持久化目录 data_dir/config.json（WebUI 落盘文件）
    3. 双向自愈：任何一侧缺失自动从另一侧回填；合并时保留 _custom_keys 与用户非空定制值；
    彻底隔离 AstrBot 宿主旧残留污染，杜绝更新/重启后任何数值被冲回默认值或 3% 利率。
    """
    try:
        import json as _pjs
        db_cfg = {}
        # 1. 优先从 SQLite 镜像读取（升级代码绝不会覆盖 .db 文件）
        try:
            if hasattr(ST, "recall_get"):
                _raw = ST.recall_get("sys_config_json", "")
                if _raw:
                    _parsed = _pjs.loads(_raw)
                    if isinstance(_parsed, dict) and _parsed:
                        db_cfg = _parsed
        except Exception:
            pass

        # 2. 读取持久化目录下的 config.json 文件
        file_cfg = {}
        _pcfg = os.path.join(data_dir, "config.json")
        if not os.path.isfile(_pcfg):
            # 自愈探测：如果持久目录无 config.json，尝试从插件包旧 data/ 目录自愈迁移
            _old_pcfg = os.path.join(_PLUGIN_BASE, "data", "config.json")
            if os.path.isfile(_old_pcfg):
                try:
                    import shutil
                    shutil.copy2(_old_pcfg, _pcfg)
                except Exception:
                    pass
        if os.path.isfile(_pcfg):
            try:
                with open(_pcfg, encoding="utf-8") as _pf:
                    _praw = _pjs.load(_pf)
                if isinstance(_praw, dict) and _praw:
                    file_cfg = _normalize_cfg(_praw) if callable(_normalize_cfg) else _praw
            except Exception:
                pass

        # 3. 双源深度合并与自愈
        # 以 DB 镜像为主干底座，叠加上文件非空值，确保即使文件被精简或部分重置，DB 历史配置依旧完整
        merged = {}
        for _sec, _kv in db_cfg.items():
            if _sec in getattr(ST, "_COLL_FILES", {}):
                continue
            if isinstance(_kv, dict):
                merged.setdefault(_sec, {}).update(_kv)
            else:
                merged[_sec] = _kv

        for _sec, _kv in file_cfg.items():
            if _sec in getattr(ST, "_COLL_FILES", {}):
                continue
            if isinstance(_kv, dict):
                _dst = merged.setdefault(_sec, {})
                for _k, _v in _kv.items():
                    if _k == "" and str(_v) != "":
                        merged[_sec] = _v
                    elif str(_v) != "" or _k not in _dst:
                        _dst[_k] = _v
            else:
                if str(_kv) != "" or _sec not in merged:
                    merged[_sec] = _kv

        # 强制修复历史遗留的赌博最大金额（绝不低于 100,000 / 10w）
        try:
            _b_sec = merged.setdefault("银行配置", {})
            if int(float(_b_sec.get("赌博最大金额", "0") or 0)) < 100000:
                _b_sec["赌博最大金额"] = "100000"
        except Exception:
            pass

        # 4. 用户自定义修改锁定列表 (_custom_keys) 绝对合并
        _all_custom = {}
        if isinstance(db_cfg.get("_custom_keys"), dict):
            _all_custom.update(db_cfg["_custom_keys"])
        if isinstance(file_cfg.get("_custom_keys"), dict):
            _all_custom.update(file_cfg["_custom_keys"])
        if isinstance(ST._CONFIG.get("_custom_keys"), dict):
            _all_custom.update(ST._CONFIG["_custom_keys"])
        if _all_custom:
            merged["_custom_keys"] = _all_custom

        # 5. 回填生效到运行配置，彻底冲刷 AstrBot 宿主旧残留
        if merged:
            ST._CONFIG.clear()
            ST._CONFIG.update(merged)
            try:
                if hasattr(ST, "_bump_config_ver"):
                    ST._bump_config_ver()
            except Exception:
                pass

        # 6. 双向镜像互补自愈
        if not file_cfg and db_cfg:
            try:
                ST.save_config()
            except Exception:
                pass
        elif file_cfg and not db_cfg:
            try:
                if hasattr(ST, "recall_set"):
                    _mirror = {s: kv for s, kv in ST._CONFIG.items() if s not in getattr(ST, "_COLL_FILES", {})}
                    ST.recall_set("sys_config_json", _pjs.dumps(_mirror, ensure_ascii=False))
            except Exception:
                pass
    except Exception:
        pass


def _apply_fresh_casual(data_dir):
    """新装默认休闲+实时模式（仅真新装：无持久配置＋空库；老用户升级绝不覆盖）。
    无 AstrBot 下发可用时给出一套完整休闲数值，而非各引擎兜底拼凑的混合态。
    只改内存＋bump（返回 True 表脏），落盘由 XbBot.__init__ 尾部统一一次完成，省重复全量序列化。"""
    try:
        if os.path.isfile(os.path.join(data_dir, "config.json")):
            return False
        _empty = True
        try:
            if ST._DB is not None and hasattr(ST, "_LOCK"):
                with ST._LOCK:
                    _c = ST._DB.execute("SELECT COUNT(*) FROM wallet").fetchone()
                    _c2 = ST._DB.execute("SELECT COUNT(*) FROM accounts").fetchone()
                    _c3 = ST._DB.execute("SELECT COUNT(*) FROM groups").fetchone()
                _empty = (int((_c or [0])[0] or 0) == 0 and int((_c2 or [0])[0] or 0) == 0 and int((_c3 or [0])[0] or 0) == 0)
            elif ST._DB is not None:
                _c = ST._DB.execute("SELECT COUNT(*) FROM wallet").fetchone()
                _c2 = ST._DB.execute("SELECT COUNT(*) FROM accounts").fetchone()
                _c3 = ST._DB.execute("SELECT COUNT(*) FROM groups").fetchone()
                _empty = (int((_c or [0])[0] or 0) == 0 and int((_c2 or [0])[0] or 0) == 0 and int((_c3 or [0])[0] or 0) == 0)
        except Exception:
            return False
        if not _empty:
            return False
        from .api.settings import PRESETS as _PRE
        _cas = (_PRE or {}).get("casual") or {}
        for _sec, _kv in _cas.items():
            if _sec in getattr(ST, "_COLL_FILES", {}):
                try:
                    ST.coll_merge(_sec, _kv)
                except Exception:
                    pass
                continue
            if isinstance(_kv, dict):
                ST._CONFIG.setdefault(_sec, {}).update(_kv)
        ST._CONFIG["_active_balance_mode"] = "casual"
        ST._CONFIG["_balance_control_type"] = "realtime"
        try:
            ST._CONFIG.setdefault("设置", {})["平衡模式"] = "casual"
            ST._CONFIG.setdefault("设置", {})["调控模式"] = "realtime"
        except Exception:
            pass
        try:
            if hasattr(ST, "_bump_config_ver"):
                ST._bump_config_ver()
        except Exception:
            pass
        # 落盘合并到 XbBot.__init__ 尾部统一一次完成（本函数只改内存＋bump，调用方统一 save+sync）
        return True
    except Exception:
        return False


# Web API 路由表单源 core/web_routes
from .web_routes import _XB_API_ROUTES, _XB_WEBDAV_ROUTES, _XB_MUTATING_HANDLERS, _web_admin_explicit_deny


class XbBot(Star):
    def __init__(self, context: Context, config: Optional[dict] = None):
        super().__init__(context)
        _get_exec()  # 实例化时建消息池（import 期零线程；并发语义不变）
        if isinstance(config, dict) and config and callable(_normalize_cfg):
            cfg = _normalize_cfg(config)
        elif callable(_fallback_cfg):
            cfg = _fallback_cfg()
        else:
            cfg = {}
        if not isinstance(cfg, dict):
            cfg = {}
        _BASE = _PLUGIN_BASE
        try:
            from .adapters import StarTools
            official_dir = str(StarTools.get_data_dir()) if StarTools else ""
            if official_dir:
                ST.set_persistent_data_dir(official_dir)
        except Exception:
            pass
        data_dir = ST.get_persistent_data_dir(_BASE) if hasattr(ST, "get_persistent_data_dir") else os.path.join(_BASE, "data")
        if _logger_layer:
            try:
                _logger_layer.set_log_dir(os.path.join(data_dir, "logs"))
            except Exception:
                pass
        db_path = str(cfg.get("网络", {}).get("db_path", "") or "") or os.path.join(data_dir, "xb.db")
        # 宿主配置纯隔离：ST.init 传入 None，禁止宿主旧参数直接塞进 ST._CONFIG
        ST.init(db_path, None)
        # 仅同步宿主基础设施级网络配置，业务玩法配置绝对以持久层为准
        if isinstance(cfg.get("网络"), dict) and cfg["网络"]:
            ST._CONFIG.setdefault("网络", {}).update(cfg["网络"])
        ST.set_config_path(os.path.join(data_dir, "config.json"))
        ST.set_backup_dir(os.path.join(data_dir, "backups"))
        ST.set_astrbot_config(config)
        _merge_persistent_config(data_dir)
        _need_save = bool(_apply_fresh_casual(data_dir))
        # 默认模式补全：若未设置调控模式或平衡模式，默认使用 实时模式 + 休闲高福利
        try:
            if not ST._CONFIG.get("_balance_control_type") and not ST.cfg("设置", "调控模式", ""):
                ST._CONFIG["_balance_control_type"] = "realtime"
                ST._CONFIG.setdefault("设置", {})["调控模式"] = "realtime"
            if not ST._CONFIG.get("_active_balance_mode") and not ST.cfg("设置", "平衡模式", ""):
                ST._CONFIG["_active_balance_mode"] = "casual"
                ST._CONFIG.setdefault("设置", {})["平衡模式"] = "casual"
        except Exception:
            pass
        # DB 镜像最后一道兜底：文件也被污染时仍可从库恢复
        try:
            if hasattr(ST, "wd_cfg_restore"):
                ST.wd_cfg_restore()
        except Exception:
            pass
        # 迁移防御机制：所有迁移均受 _custom_keys 保护，任何用户手动保存过的自定义项绝对禁动
        _customs = ST._CONFIG.get("_custom_keys") or {}
        # 赌博单笔限额升级与强制保底（绝不低于 10w，防止实时调控或历史库重置回 2w）
        try:
            _bcfg = ST._CONFIG.setdefault("银行配置", {})
            if int(float(_bcfg.get("赌博最大金额", "0") or 0)) < 100000:
                _bcfg["赌博最大金额"] = "100000"
                _need_save = True
            ST.recall_set("mig_gamble_max_10w", "1")
        except Exception:
            pass
        # 赌博限定次数调高至 30~50 次，概率调低至 32~35%（受 _customs 保护）
        try:
            if str(ST.recall_get("mig_gamble_rebalance_v26b", "") or "") != "1":
                _bcfg = ST._CONFIG.setdefault("银行配置", {})
                if "银行配置.赌博限定次数" not in _customs:
                    try:
                        if int(float(_bcfg.get("赌博限定次数", "0") or 0)) < 30:
                            _bcfg["赌博限定次数"] = "50"
                            _need_save = True
                    except Exception:
                        _bcfg["赌博限定次数"] = "50"
                        _need_save = True
                if "银行配置.赌博成功概率" not in _customs:
                    try:
                        if int(float(_bcfg.get("赌博成功概率", "0") or 0)) > 35:
                            _bcfg["赌博成功概率"] = "35"
                            _need_save = True
                    except Exception:
                        _bcfg["赌博成功概率"] = "35"
                        _need_save = True
                ST.recall_set("mig_gamble_rebalance_v26b", "1")
        except Exception:
            pass
        # 赌博获胜倍率升级为 1.8x
        try:
            if str(ST.recall_get("mig_gamble_mult_18", "") or "") != "1":
                _bcfg = ST._CONFIG.setdefault("银行配置", {})
                if "银行配置.赌博倍率" not in _customs:
                    _bcfg["赌博倍率"] = "1.8"
                    _need_save = True
                ST.recall_set("mig_gamble_mult_18", "1")
        except Exception:
            pass
        try:
            if str(ST.recall_get("mig_bank_rate_1pct", "") or "") != "1":
                if "银行配置.存款利率" not in _customs:
                    _bcfg = ST._CONFIG.setdefault("银行配置", {})
                    if str(_bcfg.get("存款利率", "1")) in ("2", "3"):
                        _bcfg["存款利率"] = "1"
                        _need_save = True
                ST.recall_set("mig_bank_rate_1pct", "1")
        except Exception:
            pass
        # 一次性迁移：搬砖间隔拉长至 30 分钟、消耗体力 15 点，并锁定签到软硬上限配置
        try:
            if str(ST.recall_get("mig_banzhuan_cd_30m", "") or "") != "1":
                _icfg = ST._CONFIG.setdefault("间隔配置", {})
                if "间隔配置.搬砖间隔" not in _customs:
                    try:
                        if int(float(_icfg.get("搬砖间隔", "0") or 0)) < 30:
                            _icfg["搬砖间隔"] = "30"
                            _need_save = True
                    except Exception:
                        _icfg["搬砖间隔"] = "30"
                        _need_save = True
                _fcfg = ST._CONFIG.setdefault("费用配置", {})
                if "费用配置.搬砖消耗体力" not in _customs:
                    try:
                        if int(float(_fcfg.get("搬砖消耗体力", "0") or 0)) < 15:
                            _fcfg["搬砖消耗体力"] = "15"
                            _need_save = True
                    except Exception:
                        _fcfg["搬砖消耗体力"] = "15"
                        _need_save = True
                _scfg = ST._CONFIG.setdefault("签到配置", {})
                for _sk, _sv in [
                    ("体力软上限", "300"), ("体力硬上限", "1000"), ("购买体力上限", "1000"),
                    ("溢出体力折算金币", "4"), ("魅力软上限", "500"), ("魅力硬上限", "800"),
                    ("溢出魅力折算金币", "2")
                ]:
                    if f"签到配置.{_sk}" not in _customs and _sk not in _scfg:
                        _scfg[_sk] = _sv
                        _need_save = True
                ST.recall_set("mig_banzhuan_cd_30m", "1")
            if str(ST.recall_get("mig_slave_work_cd_15m", "") or "") != "1":
                _icfg2 = ST._CONFIG.setdefault("间隔配置", {})
                if "间隔配置.打工间隔" not in _customs:
                    try:
                        if int(float(_icfg2.get("打工间隔", "0") or 0)) < 15:
                            _icfg2["打工间隔"] = "15"
                            _need_save = True
                    except Exception:
                        _icfg2["打工间隔"] = "15"
                        _need_save = True
                ST.recall_set("mig_slave_work_cd_15m", "1")
        except Exception:
            pass
        # 抽奖福利平衡迁移：平滑迁移历史默认高福利至新平衡值（受 _custom_keys 保护）
        try:
            if str(ST.recall_get("mig_lottery_rebalance_v26", "") or "") != "1":
                _lcfg = ST._CONFIG.setdefault("抽奖配置", {})
                if "抽奖配置.中奖率" not in _customs:
                    if str(_lcfg.get("中奖率", "45")) in ("70", "80"):
                        _lcfg["中奖率"] = "45"
                        _need_save = True
                if "抽奖配置.现金奖" not in _customs:
                    if str(_lcfg.get("现金奖", "500")) in ("2000", "4000"):
                        _lcfg["现金奖"] = "500"
                        _need_save = True
                if "抽奖配置.体力奖" not in _customs:
                    if str(_lcfg.get("体力奖", "10")) in ("30", "50"):
                        _lcfg["体力奖"] = "10"
                        _need_save = True
                if "抽奖配置.魅力奖" not in _customs:
                    if str(_lcfg.get("魅力奖", "10")) in ("20", "35"):
                        _lcfg["魅力奖"] = "10"
                        _need_save = True
                ST.recall_set("mig_lottery_rebalance_v26", "1")
        except Exception:
            pass
        # 全库体力/魅力强压执行：首次迁移将全库历史存量 >300 的体力与魅力强制压回 300 软上限（按 25% 折算补贴金币），
        # 并清理旧键 tili/meili 残留；已完成迁移的实例跳过启动期全表扫描，运行时由各入口硬上限兜底
        try:
            if ST._DB is not None and str(ST.recall_get("mig_force_stat_clamp_v2", "") or "") != "1":
                import json as _mjs
                _stam_lim = 300
                _charm_lim = 300
                with ST._LOCK:
                    _arows = ST._DB.execute("SELECT gid, qq, data FROM accounts").fetchall()
                    _upd_accts = []
                    _upd_coins = []
                    for _agid, _aqq, _adata in (_arows or []):
                        try:
                            _akv = _mjs.loads(_adata) if _adata else {}
                        except Exception:
                            continue
                        if not isinstance(_akv, dict):
                            continue
                        _changed = False
                        # 合并并清理旧键名，防止 SQL json_extract 或旧字段残留绕过压制
                        _raw_st = _akv.get("stamina", _akv.get("tili", _akv.get("体力", _akv.get("体力总数", "0"))))
                        _raw_ch = _akv.get("charm", _akv.get("meili", _akv.get("魅力", _akv.get("魅力总数", "0"))))
                        for _old_k in ("tili", "体力", "体力总数", "meili", "魅力", "魅力总数"):
                            if _old_k in _akv:
                                _akv.pop(_old_k, None)
                                _changed = True
                        try:
                            _st_v = max(0, int(float(_raw_st or 0)))
                        except Exception:
                            _st_v = 0
                        try:
                            _ch_v = max(0, int(float(_raw_ch or 0)))
                        except Exception:
                            _ch_v = 0
                        _comp_coin = 0
                        if _st_v > _stam_lim:
                            _ov_s = _st_v - _stam_lim
                            _comp_coin += min(_ov_s, 75) * 4
                            _st_v = _stam_lim
                            _akv["stamina"] = str(_st_v)
                            _changed = True
                        elif _changed and "stamina" not in _akv and _st_v > 0:
                            _akv["stamina"] = str(_st_v)
                        if _ch_v > _charm_lim:
                            _ov_c = _ch_v - _charm_lim
                            _comp_coin += min(_ov_c, 75) * 2
                            _ch_v = _charm_lim
                            _akv["charm"] = str(_ch_v)
                            _changed = True
                        elif _changed and "charm" not in _akv and _ch_v > 0:
                            _akv["charm"] = str(_ch_v)
                        if _changed:
                            _upd_accts.append((_mjs.dumps(_akv, ensure_ascii=False), int(_agid), int(_aqq)))
                            if _comp_coin > 0:
                                _upd_coins.append((int(_agid), int(_aqq), int(_comp_coin)))
                    if _upd_accts:
                        ST._DB.executemany("UPDATE accounts SET data=? WHERE gid=? AND qq=?", _upd_accts)
                        for _cg, _cq, _cc in _upd_coins:
                            _wrow = ST._DB.execute("SELECT money FROM wallet WHERE gid=? AND qq=?", (_cg, _cq)).fetchone()
                            _wcur = int(_wrow[0]) if _wrow else 0
                            _wnew = min(getattr(ST, "COIN_CAP", 100000000000), _wcur + _cc)
                            ST._DB.execute(
                                "INSERT INTO wallet(gid, qq, money) VALUES(?,?,?) "
                                "ON CONFLICT(gid, qq) DO UPDATE SET money=excluded.money",
                                (_cg, _cq, _wnew),
                            )
                        ST._safe_commit()
                        try:
                            ST._ACC_CACHE.clear()
                        except Exception:
                            pass
                        if _logger_layer:
                            try:
                                _logger_layer.info(f"[强压迁移] 已压制 {len(_upd_accts)} 个超标账户的体力/魅力存量 (上限={_stam_lim}/{_charm_lim})")
                            except Exception:
                                pass
                ST.recall_set("mig_force_stat_clamp_v2", "1")
        except Exception:
            pass
        # 接龙奖励历史旧档纠偏：仅在首次迁移且用户未自定义锁定时纠偏
        try:
            if str(ST.recall_get("mig_jielong_seed_v1", "") or "") != "1":
                _ent = ST._CONFIG.setdefault("娱乐配置", {})
                if "娱乐配置.接龙奖励金币" not in _customs and "接龙奖励金币" not in _ent:
                    _ent["接龙奖励金币"] = "20"
                    _need_save = True
                if "娱乐配置.接龙奖励魅力" not in _customs and "接龙奖励魅力" not in _ent:
                    _ent["接龙奖励魅力"] = "0"
                    _need_save = True
                ST.recall_set("mig_jielong_seed_v1", "1")
        except Exception:
            pass
        # 精灵冒险历练奖励历史旧档纠偏：将历史 >100 的膨胀数值纠偏至平衡值（20-45经验，10-30金币）
        try:
            if str(ST.recall_get("mig_spirit_adv_rebalance_v2", "") or "") != "1":
                _spcfg = ST._CONFIG.setdefault("精灵配置", {})
                if "精灵配置.挑战奖励_经验上限" not in _customs:
                    if int(float(_spcfg.get("挑战奖励_经验上限", "45") or 0)) > 100:
                        _spcfg["挑战奖励_经验下限"] = "20"
                        _spcfg["挑战奖励_经验上限"] = "45"
                        _need_save = True
                if "精灵配置.挑战奖励_金钱上限" not in _customs:
                    if int(float(_spcfg.get("挑战奖励_金钱上限", "30") or 0)) > 100:
                        _spcfg["挑战奖励_金钱下限"] = "10"
                        _spcfg["挑战奖励_金钱上限"] = "30"
                        _need_save = True
                ST.recall_set("mig_spirit_adv_rebalance_v2", "1")
        except Exception:
            pass
        self._db_path = db_path
        old_db = str(cfg.get("网络", {}).get("merge_from_db", "") or "")
        if old_db:
            ST.merge_from(old_db)
        slave.init_slave(
            bot_uin="",  # 完全自动获取，已移除 bot_uin 手动配置
            import_wallet_dir=str((cfg.get("网络") or {}).get("import_wallet_dir", "") or "") if isinstance(cfg.get("网络"), dict) else "")
        # 兜底自定义示例：mj + 像素方块…（纯自定义 command="" reply）仅首次建库/迁移补齐一次，后台删除后不再复活
        try:
            if not ST.recall_get("mig_custom_seed_v1", ""):
                sec = ST._CONFIG.get("自定义指令配置")
                if not isinstance(sec, dict):
                    sec = {}
                    ST._CONFIG["自定义指令配置"] = sec
                need = False
                if "mj" not in sec:
                    sec["mj"] = {"command": "", "reply": "mj"}
                    need = True
                if "像素方块的硬核才是王道" not in sec:
                    sec["像素方块的硬核才是王道"] = {"command": "", "reply": "你的卡通画风根本没技巧"}
                    need = True
                ST.recall_set("mig_custom_seed_v1", "1")
                if need:
                    _need_save = True
        except Exception:
            pass
        # __init__ 种子三处（新装预设/接龙纠正/mj 示例）落盘合并为一次：全量 JSON＋文件＋DB 三写只付一次
        if _need_save:
            try:
                ST.save_config()
            except Exception:
                pass
        if _logger_layer:
            try:
                _logger_layer.info(f"小白测试版 v{PLUGIN_VERSION} 启动初始化完成 (PID={os.getpid()}) 数据:{self._db_path}")
            except Exception:
                pass
        # Web API — 9Tab 懒加载（路由+分发单源 core/web_routes 五元组，注册期直接绑定路由闭包）
        for _suffix, _methods, _page, _desc, (_pm, _pf, _pl, _pk) in _XB_API_ROUTES:
            context.register_web_api(f"/{PLUGIN_ID}/{_suffix}", self._route_handler(_page, _pm, _pf, _pl, **_pk), _methods.split(","), _desc)
        for _suffix, _methods, _page, _desc, (_pm, _pf, _pl, _pk) in _XB_WEBDAV_ROUTES:
            _h = self._route_handler(_page, _pm, _pf, _pl, **_pk)
            context.register_web_api(f"/{PLUGIN_ID}/backup/{_suffix}", _h, _methods.split(","), _desc)
            context.register_web_api(f"/{PLUGIN_ID}/backups/{_suffix}", _h, _methods.split(","), f"{_desc} (兼容别名)")

        # 后台独立守护线程执行自动备份与超期清理，绝不阻塞主消息循环与事件分发
        # 单例 guard：按线程名去重，插件热重载后旧线程仍在跑则不再起新线程，
        # 根治重载累积多 worker 同时 tick 导致备份时间错乱与双份文件
        def _bg_auto_backup_worker():
            import time
            _last_clean = 0.0
            while True:
                time.sleep(60)
                try:
                    ST.maybe_auto_backup()
                except Exception:
                    pass
                # 每小时顺带执行一次保留数修剪 + 瞬时 KV 过期回收（零阻塞，见 storage/kv.clean_expired_kv）
                try:
                    _now_c = time.time()
                    if _now_c - _last_clean >= 3600:
                        _last_clean = _now_c
                        ST.clean_old_backups()
                        try:
                            if hasattr(ST, "clean_expired_kv"):
                                ST.clean_expired_kv()
                        except Exception:
                            pass
                        # 碎片回收：WAL 增量回收（auto_vacuum=0 下为 no-op，开增量后自动生效）
                        try:
                            if hasattr(ST, "_DB") and ST._DB is not None:
                                ST._DB.execute("PRAGMA incremental_vacuum(50)")
                        except Exception:
                            pass
                except Exception:
                    pass
        import threading
        try:
            _has_bck = any(
                getattr(t, "name", "") == "xb-auto-backup-beta" and t.is_alive()
                for t in threading.enumerate()
            )
        except Exception:
            _has_bck = False
        if not _has_bck:
            t_bg_bck = threading.Thread(target=_bg_auto_backup_worker, daemon=True, name="xb-auto-backup-beta")
            t_bg_bck.start()

    def _extract_bot_uin_sync(self, event):
        cur_bot = slave.get_bot_uin() if hasattr(slave, "get_bot_uin") else getattr(slave, "BOT_UIN", "")
        if cur_bot:
            return True
        cands = []
        try:
            fn = getattr(event, "get_self_id", None)
            if callable(fn):
                v = fn()
                if v:
                    cands.append(str(v).strip())
        except Exception:
            pass
        for attr in ("self_id", "bot_id"):
            try:
                v = getattr(event, attr, None)
                if v:
                    cands.append(str(v).strip())
            except Exception:
                pass
        try:
            mo = getattr(event, "message_obj", None)
            if mo is not None:
                for attr in ("self_id", "bot_id", "to_me"):
                    v = getattr(mo, attr, None)
                    if v and str(v).strip().isdigit():
                        cands.append(str(v).strip())
        except Exception:
            pass
        bot = getattr(event, "bot", None)
        if bot is not None:
            for attr in ("self_id", "uin", "bot_uin", "user_id"):
                try:
                    v = getattr(bot, attr, None)
                    if v and str(v).strip().isdigit():
                        cands.append(str(v).strip())
                except Exception:
                    pass
        for c in cands:
            if c.isdigit() and 5 <= len(c) <= 12:
                if hasattr(slave, "set_bot_uin"):
                    slave.set_bot_uin(c)
                else:
                    slave.BOT_UIN = c
                return True
        return False

    async def _dispatch(self, event):
        """消息分发编排：解析身份 -> 名片同步 -> 测试菜单/探针/超管列表 -> 业务执行与发送。
        重活均在 core/dispatch/*，本函数只做分支编排（含法则 7 全静默守卫）。只处理群聊。"""
        try:
            try:
                if _HAS_CORE and hasattr(_plat_layer, 'set_latest_bot'):
                    _plat_layer.set_latest_bot(getattr(event, 'bot', None))
            except Exception:
                pass
            try:
                self._extract_bot_uin_sync(event)
            except Exception:
                pass
            gid = str(event.get_group_id() or "").strip()
            if not gid or not gid.isdigit():
                return
            plat = ""
            try:
                gpn = getattr(event, "get_platform_name", None)
                if callable(gpn):
                    plat = str(gpn() or "").strip().lower()
                if not plat:
                    plat = str(getattr(event, "platform_id", "") or getattr(event, "platform", "") or "").strip().lower()
            except Exception:
                pass
            if plat and plat not in ("onebot", "aiocqhttp", "aihttpcq", "cqhttp", "onebot11", "onebot_v11"):
                return
            try:
                _grp = getattr(getattr(event, "message_obj", None), "group", None)
                _gname = str(getattr(_grp, "group_name", "") or "").strip() if _grp is not None else ""
                if not _gname:
                    _raw_m = getattr(getattr(event, "message_obj", None), "raw_message", None)
                    if isinstance(_raw_m, dict):
                        _gname = str(_raw_m.get("group_name") or "").strip()
                if _gname and _gname != gid and _GROUP_NAME_MEM.get(gid) != _gname:
                    _GROUP_NAME_MEM[gid] = _gname
                    if ST.recall_get(f"group_name_{gid}", "") != _gname:
                        ST.recall_set(f"group_name_{gid}", _gname)
            except Exception:
                pass
            qq = str(event.get_sender_id() or "").strip()
            if not qq or not qq.isdigit():
                return
            try:
                card = (getattr(event.message_obj.sender, "card", None)
                        or getattr(event.message_obj.sender, "nickname", None) or "")
                card = str(card).strip()
            except Exception:
                card = ""
            _dispatch_name_sync.maybe_sync_card(gid, qq, card, slave, ST)
            slave.mark_known(gid, qq)
            raw = event.message_str or ""
            raw = _append_at_segments(raw, event, gid)
            if not raw.strip():
                return
            try:
                is_admin = bool(event.is_admin())
            except Exception:
                is_admin = False
            # 维护统一门（单源 core.router.maintenance_gate，与管线同语义）：
            # 开则普通用户不再执行业务（测试菜单/超管列表/迎新），仅被@时回一条维护通知；超管豁免
            # （维护不忽略超管；忽略超管的是总开关/群组开关）。
            try:
                _mg = _router_layer.maintenance_gate(gid, raw, ST, is_admin) if _HAS_CORE else None
                if _mg is not None:
                    try:
                        event.stop_event()
                    except Exception:
                        pass
                    # _PROTO_SILENT 哨兵：维护中静默；str：被@回一条
                    if isinstance(_mg, str):
                        try:
                            if _HAS_CORE and _name_prefix:
                                try:
                                    _mg = _name_prefix(qq, _mg, None, gid)
                                except TypeError:
                                    _mg = _name_prefix(qq, _mg)
                        except Exception:
                            pass
                        yield event.plain_result(_mg)
                    return
            except Exception:
                pass
            if raw.strip().startswith(("测试xbtest", "测试testxb", "xbtest")):
                if not is_admin:
                    try:
                        event.stop_event()
                    except Exception:
                        pass
                    yield event.plain_result("亲亲，你没有相关权限哦~该指令仅限机器人管理员使用！")
                    return
                try:
                    from . import selftest as _selftest_mod
                    bot = getattr(event, "bot", None)
                    rep = await _selftest_mod.execute_test_command(raw, gid, qq, is_admin, event=event, bot=bot)
                    if rep:
                        if str(rep).startswith("__FORWARD_OK__"):
                            yield event.plain_result(str(rep)[14:])
                        else:
                            yield event.plain_result(rep)
                    try:
                        event.stop_event()
                    except Exception:
                        pass
                    return
                except Exception as e:
                    try:
                        event.stop_event()
                    except Exception:
                        pass
                    yield event.plain_result(f"自测异常: {e}")
                    return
            if raw.strip() == "超管列表":
                if not is_admin:
                    try:
                        event.stop_event()
                    except Exception:
                        pass
                    return  # 全静默（BY DESIGN，见 AIINFO）
                async for r in _dispatch_admins.handle_admin_list(event, gid, qq, slave, ST):
                    yield r
                return
            # 单次 executor 内串行 handle + 迎新检查，闲聊消息不再付双倍线程切换
            reply = await _dispatch_reply.run_business(
                gid, qq, raw, is_admin, _get_exec(), handle, ride)
            if reply:
                is_w = isinstance(reply, tuple) and len(reply) == 2 and reply[0] == "__WELCOME__"
                actual_reply = reply[1] if is_w else reply
                if is_w:
                    # 迎新坐骑专属：独立通道直接投递群聊，绝不占用当前 event.result，绝不调用 stop_event
                    # 这样 AstrBot 会将用户原消息完整继续传递给后续的大模型 AI 和其他插件，彻底杜绝吞指令与吞聊天
                    sent = await _dispatch_reply.send_welcome_async(
                        event, actual_reply, qq, raw, gid, ST, _logger_layer,
                        _do_platform, _name_prefix, _build_chain, MessageChain,
                        _HAS_CORE,
                        _plat_layer._CQ_IMG if _HAS_CORE else None)
                    if sent:
                        return
                async for r in _dispatch_reply.send_reply(
                        event, actual_reply, qq, raw, gid, ST, _logger_layer,
                        _do_platform, _name_prefix, _build_chain, MessageChain,
                        _HAS_CORE,
                        _plat_layer._CQ_IMG if _HAS_CORE else None,
                        is_welcome=is_w):
                    yield r
        except Exception as e:
            import traceback
            if _logger_layer:
                try:
                    _logger_layer.error(f"on_message异常: {e}\n{traceback.format_exc()}")
                except Exception:
                    pass
            try:
                slave.log(f"on_message异常: {e}\n{traceback.format_exc()}")
            except Exception:
                pass

    async def on_message(self, event: AstrMessageEvent):
        async for r in self._dispatch(event):
            yield r

    # ---------- Pages APIs (薄委托 → core/api) ----------
    @staticmethod
    def _get_req(request=None, args=None):
        if request is not None:
            return request
        if args and len(args) > 0:
            return args[0]
        try:
            from .adapters import request as _web_req
            return _web_req
        except Exception:
            return None

    async def _call_api(self, mod_short, func_name, err_label, request=None, args=None,
                        mode="request", with_base=False, use_context=False, fallback=None):
        """page_* 统一薄委托：双通道导入 handler 后按模式组装参数调用，异常归一 _err"""
        try:
            # 管理 API 服务端收口：AstrBot 宿主 dashboard 会话是鉴权边界（宿主契约未在本仓提供，
            # 见 AICODE_AUDIT §10）。宿主 view_handler 从不传 request（仅绑在 astrbot.api.web.request
            # 上下文代理），缺失时代理解析（同 _get_req 单源）＋绑定探测：代理未绑定时访问属性抛
            # RuntimeError → 仍失败关闭 403；绑定后仅做显式非管理员标记检查，缺标记交宿主会话判定。
            if func_name in _XB_MUTATING_HANDLERS:
                _deny_req = request if request is not None else (args[0] if args else None)
                if _deny_req is None:
                    try:
                        from .adapters import request as _proxy_req
                        getattr(_proxy_req, "method")  # 绑定探测：未绑定代理访问属性即抛
                        _deny_req = _proxy_req
                    except Exception:
                        _deny_req = None
                if _deny_req is None:
                    return _err("forbidden: admin required", 403)
                if _web_admin_explicit_deny(_deny_req):
                    return _err("forbidden: admin required", 403)
            fn = _load_api_handler(mod_short, func_name)
            if mode == "none":
                return await fn()
            if mode == "get_req":
                req = self._get_req(request, args)
            elif mode == "req":
                req = request if request is not None else (args[0] if args else None)
            else:
                req = request
            call_args = [req]
            if with_base:
                call_args.append(_PLUGIN_BASE)
            if use_context:
                call_args.append(getattr(self, "context", None))
            return await fn(*call_args)
        except Exception as e:
            if fallback is not None:
                try:
                    return fallback()
                except Exception:
                    pass
            return _err(f"{err_label} failed: {e}", 500)

    def _route_handler(self, _page, _mod, _fn, _label, **_kw):
        """注册期绑定的路由闭包（L5/L6 收敛：page_* 合成层退役，分发四元组单源 core/web_routes）。
        鉴权门/参数组装/动态加载/异常归一全部走 _call_api 单实现，签名与原 page_* 合成方法等价。"""
        async def _handler(request=None, *args, **kwargs):
            return await self._call_api(_mod, _fn, _label, request, args, **_kw)
        _handler.__name__ = _page
        _handler.__qualname__ = "XbBot." + _page
        return _handler
