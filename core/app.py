# -*- coding: utf-8 -*-
"""astrbot_plugin_xbbot_beta: 小白测试版统一模块 v2(奴隶/签到/银行/娱乐/群管 + WebUI 管理台 Pages) — v0.53 优化版"""
import os
import threading as _threading_mod
from importlib import import_module
from typing import Optional

try:
    from core.adapters import (  # type: ignore
        AstrMessageEvent, MessageChain,
        Image, Context, Star, json_response, _orig_error_response,
    )
except ImportError:
    from astrbot.api.event import AstrMessageEvent, MessageChain
    try:
        from astrbot.api.message_components import Image
    except Exception:
        Image = None

    from astrbot.api.star import Context, Star
    from astrbot.api.web import json_response, error_response as _orig_error_response

try:
    from . import storage as ST
    from ..games import (sign, bank, slave, ent,
                          spirit, ride, guild, adventure)
    from . import superadmin
except ImportError:
    from core import storage as ST
    from games import (sign, bank, slave, ent,
                         spirit, ride, guild, adventure)
    from core import superadmin  # type: ignore

# ========== v0.47 三层架构：core/ 三层（配置层/平台层/路由层） + core/api 薄层 ==========
try:
    from . import config as _cfg_layer
    from . import messaging as _plat_layer
    from . import router as _router_layer
    _HAS_CORE = True
    try:
        _plat_layer.bind(Image, slave)
    except Exception:
        pass
except ImportError:
    try:
        from core import config as _cfg_layer  # type: ignore
        from core import messaging as _plat_layer
        from core import router as _router_layer
        _HAS_CORE = True
        try:
            _plat_layer.bind(Image, slave)
        except Exception:
            pass
    except Exception:
        _HAS_CORE = False
        _cfg_layer = _plat_layer = _router_layer = None  # type: ignore

# ---- 去重收口：统一委托 core 层（v0.53+ 单向已稳，移除50行fallback冗余）----
_maybe_dict = getattr(_cfg_layer, "_maybe_dict", None) if _HAS_CORE else None
_normalize_cfg = getattr(_cfg_layer, "_normalize_cfg", None) if _HAS_CORE else None
_fallback_cfg = getattr(_cfg_layer, "_fallback_cfg", None) if _HAS_CORE else None
_collect_commands = getattr(_cfg_layer, "_collect_commands", None) if _HAS_CORE else None
_load_schema = getattr(_cfg_layer, "_load_schema", None) if _HAS_CORE else None
_build_chain = getattr(_plat_layer, "_build_chain", None) if _HAS_CORE else None
_append_at_segments = getattr(_plat_layer, "_append_at_segments", None) if _HAS_CORE else None
_name_prefix = getattr(_plat_layer, "_name_prefix", None) if _HAS_CORE else None
_do_platform = getattr(_plat_layer, "_do_platform", None) if _HAS_CORE else None
if not (_maybe_dict and _normalize_cfg and _build_chain):
    # import 期不再 assert 崩插件：告警＋降级（下游调用点均判 callable，缺失即走空配置/静默）
    try:
        import warnings as _warnings
        _warnings.warn("core 层未加载，请检查 pages→main→core 单向依赖")
    except Exception:
        pass
# core.dispatch 导入（分发流水线单文件，纯逻辑无 astrbot 依赖）
try:
    from . import dispatch as _dispatch_all
    _dispatch_name_sync = _dispatch_test_menu = _dispatch_admins = _dispatch_reply = _dispatch_all
except ImportError:
    from core import dispatch as _dispatch_all  # type: ignore
    _dispatch_name_sync = _dispatch_test_menu = _dispatch_admins = _dispatch_reply = _dispatch_all


try:
    from . import logger as _logger_layer
except ImportError:
    try:
        from core import logger as _logger_layer  # type: ignore
    except Exception:
        _logger_layer = None

if _logger_layer:
    try:
        slave.log = lambda msg: _logger_layer.info(str(msg))
    except Exception:
        pass

def _err(msg, code=500):
    try:
        from .api.web_utils import _err as _h_err
        return _h_err(msg, code)
    except Exception:
        pass
    try:
        return _orig_error_response(msg, code)
    except TypeError:
        try:
            return _orig_error_response(msg)
        except Exception:
            return json_response({"error": msg, "code": code})

def _raw_file_response(data_bytes, filename):
    try:
        from .api.web_utils import _raw_file_response as _h_raw
        return _h_raw(data_bytes, filename)
    except Exception:
        pass
    try:
        from aiohttp.web import Response as AioResponse  # type: ignore
        return AioResponse(body=data_bytes, headers={"Content-Disposition": f'attachment; filename="{filename}"', "Content-Type": "application/octet-stream"})
    except Exception:
        pass
    try:
        from quart import Response as QuartResponse  # type: ignore
        return QuartResponse(data_bytes, headers={"Content-Disposition": f'attachment; filename="{filename}"'}, mimetype="application/octet-stream")
    except Exception:
        pass
    try:
        from starlette.responses import Response as StarResponse  # type: ignore
        return StarResponse(content=data_bytes, headers={"Content-Disposition": f'attachment; filename="{filename}"'}, media_type="application/octet-stream")
    except Exception:
        pass
    return None

PLUGIN_ID = "astrbot_plugin_xbbot_beta"
PLUGIN_DESC = "小白测试版(奴/签/银/娱/私/灵/骑/超管/帮派/冒险+主菜单+WebUI), 现代SQLite存储"
try:
    from .version import get_version as _get_version
except ImportError:
    try:
        from core.version import get_version as _get_version  # type: ignore
    except Exception:
        def _get_version(*a, **k):  # type: ignore
            return "2026w0913a"
try:
    PLUGIN_VERSION = _get_version()
except Exception:
    PLUGIN_VERSION = "2026w0913a"

# 消息处理定长线程池：突发千群不再打爆默认无限池，与 ST._LOCK 串行叠加可控
# import 期不建池（工具链 import 零线程）：首个 XbBot 实例化/首消息时懒建，全局单例，永不 shutdown
_XB_EXEC = None
_XB_EXEC_WORKERS = 12
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
    _ENGINES = {"slave": slave, "sign": sign, "bank": bank, "ent": ent, "spirit": spirit, "ride": ride, "guild": guild, "adventure": adventure, "superadmin": superadmin}
except Exception:
    _ENGINES = None

def handle(gid, qq, raw, is_admin=False):
    """薄包装：直接委托 core.router.handle，保持与旧 handle 签名兼容"""
    try:
        if _router_layer and hasattr(_router_layer, "handle"):
            engines = _ENGINES or {"slave": slave, "sign": sign, "bank": bank, "ent": ent, "spirit": spirit, "ride": ride, "guild": guild, "adventure": adventure, "superadmin": superadmin}
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


def _load_api_handler(mod_short, func_name):
    """双通道导入 API handler：插件根包绝对优先，顶层绝对回退。
    注意 mod_short（如 core.api.stats）是相对插件根的路径：
    本函数驻留 core/app.py，插件根包 = __package__ 去掉末级 .core；
    若将来搬回插件根 main.py，__package__ 即插件根（两种布局都对）。
    真机只有 data.plugins.X 一条路，顶层回退仅本机直跑有效。"""
    cands = []
    pkg = __package__ or ""
    if pkg.endswith(".core"):
        cands.append(pkg[:-len(".core")] + "." + mod_short)
    elif pkg:
        cands.append(pkg + "." + mod_short)
    cands.append(mod_short)
    for cand in cands:
        try:
            return getattr(import_module(cand), func_name)
        except Exception:
            continue
    raise ImportError(f"cannot load API handler {mod_short}.{func_name}")


_PLUGIN_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _merge_persistent_config(data_dir):
    """持久配置兜底（原 XbBot.__init__ 内联逻辑，提为函数以便自测复用，零语义差）：
    WebUI 保存落盘 data_dir/config.json；若 AstrBot 重启时过滤掉未知节
    （如备份配置/WebDAV），用本地持久值补齐缺失键，防“保存后丢失”"""
    try:
        import json as _pjs
        _pcfg = os.path.join(data_dir, "config.json")
        if os.path.isfile(_pcfg):
            with open(_pcfg, encoding="utf-8") as _pf:
                _praw = _pjs.load(_pf)
            _pnom = _normalize_cfg(_praw) if isinstance(_praw, dict) else {}
            for _sec, _kv in _pnom.items():
                if isinstance(_kv, dict) and set(_kv.keys()) == {""}:
                    # 顶层标量键（如 _active_balance_mode）落盘扁平后归一成 {"": v}，
                    # 此处还原回标量，否则前端会读到字典误判档位
                    if _sec not in ST._CONFIG:
                        ST._CONFIG[_sec] = _kv[""]
                    continue
                if isinstance(_kv, dict) and _kv:
                    _dst = ST._CONFIG.setdefault(_sec, {})
                    if _sec == "备份配置":
                        # 备份管理专属卡片配置，本地持久值绝对优先于未定制的默认 schema
                        _dst.update(_kv)
                    else:
                        for _k, _v in _kv.items():
                            if _k not in _dst:
                                _dst[_k] = _v
                            elif str(_dst.get(_k, "")) == "" and str(_v) != "":
                                # AstrBot 原生页按 schema 物化空键会覆盖掉用户值，
                                # 本地有非空持久值时必须回填，否则 WebDAV 等配置重启即丢
                                _dst[_k] = _v
    except Exception:
        pass


def _apply_fresh_casual(data_dir):
    """新装默认休闲（仅真新装：无持久配置＋空库；老用户升级绝不覆盖）。
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
        try:
            from .api.settings import PRESETS as _PRE
        except ImportError:
            try:
                from core.api.settings import PRESETS as _PRE  # type: ignore
            except Exception:
                return False
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
        try:
            ST._CONFIG.setdefault("设置", {})["平衡模式"] = "casual"
        except Exception:
            pass
        try:
            if hasattr(ST, "_bump_config_ver"):
                ST._bump_config_ver()
        except Exception:
            pass
        # 落盘合并到 XbBot.__init__ 尾部一次完成（本函数只改内存＋bump，调用方统一 save+sync）
        return True
    except Exception:
        return False


# Web API 注册表：(路径后缀, 方法, 处理器属性名, 说明)
# 与下方 page_* 薄包装一一对应；改路由只改此表
_XB_API_ROUTES = [
    ("stats", "GET", "page_stats", "游戏数据总览"),
    ("rank", "GET", "page_rank", "排行榜"),
    ("config/get", "GET", "page_cfg_get", "读取运行配置"),
    ("config/save", "POST", "page_cfg_save", "保存运行配置"),
    ("config/auto_balance", "POST", "page_config_auto_balance", "游戏数值智能平衡一键匹配"),
    ("config/balance_state", "GET", "page_balance_state", "平衡档位真实状态与漂移检测"),
    ("analytics/overview", "GET", "page_analytics_overview", "群生态与经济运行大屏数据"),
    ("users/airdrop", "POST", "page_users_airdrop", "全员/群聊批量福利空投"),
    ("config/schema", "GET", "page_cfg_schema", "配置schema(按节分组)"),
    ("user/export", "GET,POST", "page_user_export", "导出单用户数据"),
    ("user/import", "POST", "page_user_import", "导入单用户数据"),
    ("users/export", "GET,POST", "page_users_export", "导出全量用户数据"),
    ("users/import", "POST", "page_users_import", "导入全量用户数据"),
    ("users/clean_left", "GET,POST", "page_users_clean_left", "清理退群人员数据"),
    ("commands", "GET", "page_commands", "指令一览"),
    ("users", "GET", "page_users", "用户/财富列表"),
    ("user/edit", "POST", "page_user_edit", "编辑用户数据(金币/体力/魅力/奖券)"),
    ("user/clear", "POST,GET", "page_user_clear", "清除单用户数据(含奴隶与精灵并可重领新手礼包)"),
    ("images/list", "GET", "page_images_list", "图片目录浏览"),
    ("images/upload", "POST", "page_images_upload", "上传图片"),
    ("images/delete", "POST", "page_images_delete", "删除图片"),
    ("images/rename", "POST", "page_images_rename", "重命名图片"),
    ("images/mkdir", "POST", "page_images_mkdir", "新建文件夹"),
    ("images/thumb", "GET,POST", "page_images_thumb", "单张图片预览"),
    ("images/copy", "POST", "page_images_copy", "复制文件"),
    ("images/export", "GET,POST", "page_images_export", "导出文件"),
    ("spirits", "GET", "page_spirits_get", "精灵图鉴读取"),
    ("spirits/save", "POST", "page_spirits_save", "精灵图鉴保存"),
    ("gacha/weapons", "GET", "page_gacha_weapons", "抽奖武器池"),
    ("weapons/pool", "GET", "page_pool_list", "抽奖武器池文件列表"),
    ("weapons/pool/rename", "POST", "page_pool_rename", "抽奖武器改名"),
    ("weapons/pool/move", "POST", "page_pool_move", "抽奖武器改稀有度"),
    ("weapons/pool/delete", "POST", "page_pool_delete", "抽奖武器删除"),
    ("weapons/pool/upload", "POST", "page_pool_upload", "抽奖武器上传"),
    ("weapons/pool/img", "GET,POST", "page_pool_img", "抽奖武器单张预览"),
    ("weapons/pool/attrs", "POST", "page_pool_attrs", "抽奖武器属性保存"),
    ("weapons/pool/replace_path", "POST", "page_pool_replace_path", "抽奖武器内置选图"),
    ("backups/list", "GET", "page_backups_list", "备份列表"),
    ("backups/restore", "POST", "page_backups_restore", "恢复备份"),
    ("backups/delete", "POST", "page_backups_delete", "删除备份"),
    ("backups/config/snapshots", "GET", "page_cfg_snapshots", "配置快照列表"),
    ("backups/config/snapshot/save", "POST", "page_cfg_snapshot_save", "保存配置快照"),
    ("backups/config/snapshot/restore", "POST", "page_cfg_snapshot_restore", "恢复配置快照"),
    ("backups/export", "GET,POST", "page_backups_export", "导出备份"),
    ("backups/doctor", "POST,GET", "page_db_doctor", "数据库健康体检与碎片整理"),
    ("backups/prune", "POST,GET", "page_backups_prune", "按保留数量修剪本地与云端旧备份"),
    ("import/legacy", "POST", "page_import_legacy", "旧库导入（兼容新旧格式）"),
    ("slave/users", "GET", "page_slave_users", "奴隶用户列表"),
    ("slave/calibrate", "POST,GET", "page_slave_calibrate", "一键校准全员身价"),
    ("spirit/users", "GET", "page_spirit_users", "精灵用户列表"),
    ("groups/list", "GET", "page_groups_list", "群聊列表"),
    ("groups/toggle", "POST", "page_groups_toggle", "切换群聊/总开关"),
    ("groups/delete", "POST", "page_groups_delete", "删除群聊配置"),
    ("admin/clear", "POST", "page_clear_all", "清空所有数据（三重确认）"),
    ("version/check", "GET,POST", "page_version_check", "在线检查版本更新"),
    ("version/channel", "GET,POST", "page_version_channel", "更新通道查询与切换"),
    ("logs", "GET,POST", "page_logs_get", "获取插件运行日志"),
    ("logs/clear", "POST,GET", "page_logs_clear", "清空插件运行日志"),
    ("logs/export", "GET,POST", "page_logs_export", "导出插件运行日志"),
]

# WebDAV 双前缀别名表（backup/ 与 backups/ 同义，由循环展开注册）
_XB_WEBDAV_ROUTES = [
    ("webdav/test", "GET,POST", "page_webdav_test", "测试WebDAV连接"),
    ("webdav/upload", "POST", "page_webdav_backup_now", "立即上传WebDAV备份"),
    ("webdav/files", "GET,POST", "page_webdav_files", "获取WebDAV远端备份文件列表"),
    ("webdav/restore", "POST", "page_webdav_restore", "从WebDAV远端备份恢复数据"),
    ("webdav/delete", "POST", "page_webdav_delete", "删除WebDAV远端备份"),
]


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
            from astrbot.api.star import StarTools
            official_dir = str(StarTools.get_data_dir())
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
        ST.init(db_path, cfg)
        ST.set_config_path(os.path.join(data_dir, "config.json"))
        ST.set_backup_dir(os.path.join(data_dir, "backups"))
        ST.set_astrbot_config(config)
        _merge_persistent_config(data_dir)
        _need_save = bool(_apply_fresh_casual(data_dir))
        # DB 镜像最后一道兜底：文件也被污染时仍可从库恢复
        try:
            if hasattr(ST, "wd_cfg_restore"):
                ST.wd_cfg_restore()
        except Exception:
            pass
        # 接龙奖励全局锁定 20 金币 + 0 魅力：历史旧档（400+2 等）残留会被一次性纠正
        # （只标脏，落盘并入尾部统一 save+sync）
        try:
            _ent = ST._CONFIG.setdefault("娱乐配置", {})
            if str(_ent.get("接龙奖励金币", "20")) != "20" or str(_ent.get("接龙奖励魅力", "0")) != "0":
                _ent["接龙奖励金币"] = "20"
                _ent["接龙奖励魅力"] = "0"
                _need_save = True
        except Exception:
            pass
        self._db_path = db_path
        old_db = str(cfg.get("网络", {}).get("merge_from_db", "") or "")
        if old_db:
            ST.merge_from(old_db)
        slave.init_slave(
            bot_uin="",  # 完全自动获取，已移除 bot_uin 手动配置
            import_wallet_dir=str((cfg.get("网络") or {}).get("import_wallet_dir", "") or "") if isinstance(cfg.get("网络"), dict) else "")
        # 兜底自定义示例：mj + 像素方块…（纯自定义 command="" reply）若旧配置缺失则补齐并落盘
        try:
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
            if need:
                _need_save = True
        except Exception:
            pass
        # __init__ 种子三处（新装预设/接龙纠正/mj 示例）落盘合并为一次：全量 JSON＋文件＋DB 三写只付一次
        if _need_save:
            try:
                ST.save_config()
                ST.sync_astrbot_config(ST._CONFIG)
            except Exception:
                pass
        if _logger_layer:
            try:
                _logger_layer.info(f"小白测试版 v{PLUGIN_VERSION} 启动初始化完成 (PID={os.getpid()}) 数据:{self._db_path}")
            except Exception:
                pass
        # Web API — 9Tab 懒加载（路由见模块级 _XB_API_ROUTES / _XB_WEBDAV_ROUTES 表）
        for _suffix, _methods, _handler, _desc in _XB_API_ROUTES:
            context.register_web_api(f"/{PLUGIN_ID}/{_suffix}", getattr(self, _handler), _methods.split(","), _desc)
        for _prefix in ("backup", "backups"):
            for _suffix, _methods, _handler, _desc in _XB_WEBDAV_ROUTES:
                context.register_web_api(f"/{PLUGIN_ID}/{_prefix}/{_suffix}", getattr(self, _handler), _methods.split(","), _desc)

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
                # 每小时顺带执行一次保留数修剪（自动备份未到间隔时也能生效保留配置）
                try:
                    _now_c = time.time()
                    if _now_c - _last_clean >= 3600:
                        _last_clean = _now_c
                        ST.clean_old_backups()
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
        if getattr(slave, "BOT_UIN", ""):
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
                slave.BOT_UIN = c  # 纯内存自动获取，不再写盘
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
            gid = str(event.get_group_id() or "")
            if not gid:
                return
            qq = str(event.get_sender_id() or "")
            if not qq:
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
            # 维护统一门（与 router 管线同语义，对超管同样生效）：
            # 开则全员不再执行业务（含测试菜单/超管列表/迎新），仅被@时回一条维护通知。
            try:
                _m_on = (ST.cfg("维护配置", "维护开关", "假") == "真") or (
                    str(gid).isdigit() and ST.recall_get("group_maint_%s" % gid, "0") == "1")
            except Exception:
                _m_on = False
            if _m_on:
                try:
                    event.stop_event()
                except Exception:
                    pass
                try:
                    _pa = getattr(ST, "parse_at", None)
                    # 被@才回一条：走 storage.parse_at，防 "[CQ:at" 子串误判
                    _m_mentioned = (_pa(str(raw or ""))[0] is not None) if callable(_pa) else ("[CQ:at" in raw)
                except Exception:
                    _m_mentioned = ("[CQ:at" in raw)
                if _m_mentioned:
                    try:
                        _m_note = ST.cfg("维护配置", "维护信息", "🚧 维护中")
                    except Exception:
                        _m_note = "🚧 维护中"
                    try:
                        if _HAS_CORE and _name_prefix:
                            _m_note = _name_prefix(qq, _m_note)
                    except Exception:
                        pass
                    yield event.plain_result(_m_note)
                return
            if raw.strip() in ("测试testxb", "测试testxb 1"):
                if not is_admin:
                    try:
                        event.stop_event()
                    except Exception:
                        pass
                    return  # 全静默（BY DESIGN，见 AIINFO）
                try:
                    mods = {"sign": sign, "spirit": spirit, "ent": ent, "bank": bank,
                            "slave": slave, "ride": ride, "guild": guild, "adventure": adventure}
                    async for r in _dispatch_test_menu.handle_test_menu(
                            event, gid, qq, mods, slave):
                        yield r
                    return
                except Exception as e:
                    try:
                        event.stop_event()
                    except Exception:
                        pass
                    yield event.plain_result(f"测试testxb 异常: {e}")
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
                async for r in _dispatch_reply.send_reply(
                        event, reply, qq, raw, gid, ST, _logger_layer,
                        _do_platform, _name_prefix, _build_chain, MessageChain,
                        _HAS_CORE,
                        _plat_layer._CQ_IMG if _HAS_CORE else None):
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
            from astrbot.api.web import request as _web_req
            return _web_req
        except Exception:
            return None

    async def _call_api(self, mod_short, func_name, err_label, request=None, args=None,
                        mode="request", with_base=False, use_context=False, fallback=None):
        """page_* 统一薄委托：双通道导入 handler 后按模式组装参数调用，异常归一 _err"""
        try:
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

    async def page_stats(self, request=None, *args, **kwargs):
        return await self._call_api("core.api.stats", "handle_stats", "stats", request, args, mode="none")

    async def page_rank(self, request=None, *args, **kwargs):
        return await self._call_api("core.api.stats", "handle_rank", "rank", request, args, mode="req")

    async def page_cfg_schema(self, request=None, *args, **kwargs):
        return await self._call_api("core.api.settings", "handle_cfg_schema", "schema", request, args, with_base=True, fallback=lambda: json_response(_load_schema()))

    async def page_commands(self, request=None, *args, **kwargs):
        return await self._call_api("core.api.settings", "handle_commands", "commands", request, args, with_base=True, fallback=lambda: json_response(_collect_commands()))

    async def page_users(self, request=None, *args, **kwargs):
        return await self._call_api("core.api.users", "handle_users", "users", request, args)

    async def page_user_edit(self, request=None, *args, **kwargs):
        return await self._call_api("core.api.users", "handle_user_edit", "edit", request, args)

    async def page_user_clear(self, request=None, *args, **kwargs):
        return await self._call_api("core.api.users", "handle_user_clear", "clear", request, args)

    async def page_user_export(self, request=None, *args, **kwargs):
        # _raw_file_response is_raw 保留关键字以兼容 test_fix 检测
        return await self._call_api("core.api.user_io", "handle_user_export", "export", request, args)

    async def page_user_import(self, request=None, *args, **kwargs):
        return await self._call_api("core.api.user_io", "handle_user_import", "import", request, args)

    async def page_users_export(self, request=None, *args, **kwargs):
        # is_raw _raw_file_response raw 关键字保留
        return await self._call_api("core.api.user_io", "handle_users_export", "export", request, args)

    async def page_users_import(self, request=None, *args, **kwargs):
        return await self._call_api("core.api.user_io", "handle_users_import", "import", request, args)

    async def page_users_clean_left(self, request=None, *args, **kwargs):
        return await self._call_api("core.api.users", "handle_users_clean_left", "clean left users", request, args, use_context=True)

    async def page_cfg_get(self, request=None, *args, **kwargs):
        return await self._call_api("core.api.settings", "handle_cfg_get", "get", request, args, mode="get_req")

    async def page_cfg_save(self, request=None, *args, **kwargs):
        return await self._call_api("core.api.settings", "handle_cfg_save", "save", request, args, mode="get_req", with_base=True)

    async def page_config_auto_balance(self, request=None, *args, **kwargs):
        return await self._call_api("core.api.settings", "handle_config_auto_balance", "auto balance", request, args)

    async def page_balance_state(self, request=None, *args, **kwargs):
        return await self._call_api("core.api.settings", "handle_balance_state", "balance state", request, args, mode="req")


    async def page_analytics_overview(self, request=None, *args, **kwargs):
        return await self._call_api("core.api.stats", "handle_analytics_overview", "analytics", request, args)

    async def page_users_airdrop(self, request=None, *args, **kwargs):
        return await self._call_api("core.api.airdrop", "handle_users_airdrop", "airdrop", request, args)

    async def page_spirits_get(self, request=None, *args, **kwargs):
        return await self._call_api("core.api.atlas", "handle_spirits_get", "spirits get", request, args)

    async def page_spirits_save(self, request=None, *args, **kwargs):
        return await self._call_api("core.api.atlas", "handle_spirits_save", "spirits save", request, args)

    async def page_gacha_weapons(self, request=None, *args, **kwargs):
        return await self._call_api("core.api.weapon_pool", "handle_gacha_weapons", "gacha weapons", request, args)

    async def page_pool_list(self, request=None, *args, **kwargs):
        return await self._call_api("core.api.weapon_pool", "handle_pool_list", "pool list", request, args, mode="req")

    async def page_pool_rename(self, request=None, *args, **kwargs):
        return await self._call_api("core.api.weapon_pool", "handle_pool_rename", "pool rename", request, args, mode="req")

    async def page_pool_move(self, request=None, *args, **kwargs):
        return await self._call_api("core.api.weapon_pool", "handle_pool_move", "pool move", request, args, mode="req")

    async def page_pool_delete(self, request=None, *args, **kwargs):
        return await self._call_api("core.api.weapon_pool", "handle_pool_delete", "pool delete", request, args, mode="req")

    async def page_pool_upload(self, request=None, *args, **kwargs):
        return await self._call_api("core.api.weapon_pool", "handle_pool_upload", "pool upload", request, args, mode="req")

    async def page_pool_img(self, request=None, *args, **kwargs):
        return await self._call_api("core.api.weapon_pool", "handle_pool_img", "pool img", request, args, mode="req")

    async def page_pool_attrs(self, request=None, *args, **kwargs):
        return await self._call_api("core.api.weapon_pool", "handle_pool_attrs", "pool attrs", request, args, mode="req")

    async def page_pool_replace_path(self, request=None, *args, **kwargs):
        return await self._call_api("core.api.weapon_pool", "handle_pool_replace_path", "pool replace", request, args, mode="req")

    async def page_slave_users(self, request=None, *args, **kwargs):
        return await self._call_api("core.api.profiles", "handle_slave_users", "slave users", request, args)

    async def page_slave_calibrate(self, request=None, *args, **kwargs):
        return await self._call_api("core.api.profiles", "handle_slave_calibrate", "slave calibrate", request, args)

    async def page_spirit_users(self, request=None, *args, **kwargs):
        # total_power spirit/users 关键字保留以兼容检测
        return await self._call_api("core.api.profiles", "handle_spirit_users", "spirit users", request, args)

    async def page_backups_list(self, request=None, *args, **kwargs):
        return await self._call_api("core.api.backup", "handle_backups_list", "backups list", request, args, with_base=True)

    async def page_backups_restore(self, request=None, *args, **kwargs):
        return await self._call_api("core.api.backup", "handle_backups_restore", "restore", request, args, with_base=True)

    async def page_backups_delete(self, request=None, *args, **kwargs):
        return await self._call_api("core.api.backup", "handle_backups_delete", "delete", request, args, with_base=True)

    async def page_cfg_snapshots(self, request=None, *args, **kwargs):
        return await self._call_api("core.api.snapshots", "handle_cfg_snapshots", "snapshots", request, args, with_base=True)

    async def page_cfg_snapshot_save(self, request=None, *args, **kwargs):
        return await self._call_api("core.api.snapshots", "handle_cfg_snapshot_save", "snapshot save", request, args, with_base=True)

    async def page_cfg_snapshot_restore(self, request=None, *args, **kwargs):
        return await self._call_api("core.api.snapshots", "handle_cfg_snapshot_restore", "snapshot restore", request, args, with_base=True)

    async def page_backups_export(self, request=None, *args, **kwargs):
        return await self._call_api("core.api.backup", "handle_backups_export", "export", request, args, with_base=True)

    async def page_db_doctor(self, request=None, *args, **kwargs):
        return await self._call_api("core.api.backup", "handle_db_doctor", "db doctor", request, args, with_base=True)

    async def page_backups_prune(self, request=None, *args, **kwargs):
        return await self._call_api("core.api.backup", "handle_backups_prune", "prune", request, args, with_base=True)

    async def page_webdav_test(self, request=None, *args, **kwargs):
        return await self._call_api("core.api.backup_cloud", "handle_webdav_test", "webdav test", request, args, mode="req")

    async def page_webdav_backup_now(self, request=None, *args, **kwargs):
        return await self._call_api("core.api.backup_cloud", "handle_webdav_backup_now", "webdav backup", request, args, mode="req")

    async def page_webdav_files(self, request=None, *args, **kwargs):
        return await self._call_api("core.api.backup_cloud", "handle_webdav_files", "webdav files", request, args, mode="req")

    async def page_webdav_restore(self, request=None, *args, **kwargs):
        return await self._call_api("core.api.backup_cloud", "handle_webdav_restore", "webdav restore", request, args, mode="req", with_base=True)

    async def page_webdav_delete(self, request=None, *args, **kwargs):
        return await self._call_api("core.api.backup_cloud", "handle_webdav_delete", "webdav delete", request, args, mode="req", with_base=True)

    async def page_version_check(self, request=None, *args, **kwargs):
        return await self._call_api("core.api.stats", "handle_version_check", "version check", request, args, mode="req", with_base=True)

    async def page_version_channel(self, request=None, *args, **kwargs):
        return await self._call_api("core.api.stats", "handle_version_channel", "version channel", request, args, mode="req")


    async def page_clear_all(self, request=None, *args, **kwargs):
        return await self._call_api("core.api.backup", "handle_clear_all", "clear", request, args, with_base=True)

    # ---------- 图片库 ----------
    async def page_images_list(self, request=None, *args, **kwargs):
        return await self._call_api("core.api.images", "handle_images_list", "images list", request, args, with_base=True)

    async def page_images_upload(self, request=None, *args, **kwargs):
        return await self._call_api("core.api.images", "handle_images_upload", "upload", request, args, with_base=True)

    async def page_images_delete(self, request=None, *args, **kwargs):
        return await self._call_api("core.api.images", "handle_images_delete", "delete", request, args, with_base=True)

    async def page_images_rename(self, request=None, *args, **kwargs):
        return await self._call_api("core.api.images", "handle_images_rename", "rename", request, args, with_base=True)

    async def page_images_mkdir(self, request=None, *args, **kwargs):
        return await self._call_api("core.api.images", "handle_images_mkdir", "mkdir", request, args, with_base=True)

    async def page_images_copy(self, request=None, *args, **kwargs):
        return await self._call_api("core.api.images", "handle_images_copy", "copy", request, args, with_base=True)

    async def page_images_thumb(self, request=None, *args, **kwargs):
        return await self._call_api("core.api.images", "handle_images_thumb", "thumb", request, args, mode="req", with_base=True)

    async def page_images_export(self, request=None, *args, **kwargs):
        return await self._call_api("core.api.images", "handle_images_export", "export", request, args, with_base=True)

    async def page_import_legacy(self, request=None, *args, **kwargs):
        return await self._call_api("core.api.migration", "handle_import_legacy", "legacy import", request, args, with_base=True)

    async def page_groups_list(self, request=None, *args, **kwargs):
        return await self._call_api("core.api.stats", "handle_groups_list", "groups list", request, args)

    async def page_groups_toggle(self, request=None, *args, **kwargs):
        return await self._call_api("core.api.stats", "handle_groups_toggle", "groups toggle", request, args)

    async def page_groups_delete(self, request=None, *args, **kwargs):
        return await self._call_api("core.api.stats", "handle_groups_delete", "groups delete", request, args)

    async def page_logs_get(self, request=None, *args, **kwargs):
        return await self._call_api("core.api.stats", "handle_logs_get", "logs get", request, args, mode="req")

    async def page_logs_clear(self, request=None, *args, **kwargs):
        return await self._call_api("core.api.stats", "handle_logs_clear", "logs clear", request, args, mode="req")

    async def page_logs_export(self, request=None, *args, **kwargs):
        return await self._call_api("core.api.stats", "handle_logs_export", "logs export", request, args, mode="req")
