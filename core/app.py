# -*- coding: utf-8 -*-
"""astrbot_plugin_xbbot_beta: 小白测试版统一模块 v2(奴隶/签到/银行/娱乐/群管 + WebUI 管理台 Pages) — v0.53 优化版"""
import os
import threading as _threading_mod
from importlib import import_module
from typing import Optional

try:
    from core.adapters import (  # type: ignore
        AstrMessageEvent, MessageChain,
        Image, Context, Star,
    )
except ImportError:
    from astrbot.api.event import AstrMessageEvent, MessageChain
    try:
        from astrbot.api.message_components import Image
    except Exception:
        Image = None

    from astrbot.api.star import Context, Star

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

# _err 单源 core/api/web_utils（V6 收敛：本地 _err 副本与零调用的 _raw_file_response
# 死副本已删，文件响应统一出口只留 web_utils 一份）
try:
    from .api.web_utils import _err
except ImportError:
    from core.api.web_utils import _err  # type: ignore

PLUGIN_ID = "astrbot_plugin_xbbot_beta"
PLUGIN_DESC = "小白测试版(奴/签/银/娱/私/灵/骑/超管/帮派/冒险+主菜单+WebUI), 现代SQLite存储"
try:
    from .version import get_version as _get_version
except ImportError:
    try:
        from core.version import get_version as _get_version  # type: ignore
    except Exception:
        def _get_version(*a, **k):  # type: ignore
            return "unknown"
try:
    PLUGIN_VERSION = _get_version()
except Exception:
    PLUGIN_VERSION = "unknown"

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


# 路由表单源已迁 core/web_routes（老路径兼容重导出）
try:
    from .web_routes import _XB_API_ROUTES, _XB_WEBDAV_ROUTES, _XB_MUTATING_HANDLERS, _web_admin_explicit_deny  # type: ignore
except ImportError:
    try:
        from core.web_routes import _XB_API_ROUTES, _XB_WEBDAV_ROUTES, _XB_MUTATING_HANDLERS, _web_admin_explicit_deny  # type: ignore
    except Exception:
        pass


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
        for _prefix in ("backup", "backups"):
            for _suffix, _methods, _page, _desc, (_pm, _pf, _pl, _pk) in _XB_WEBDAV_ROUTES:
                context.register_web_api(f"/{PLUGIN_ID}/{_prefix}/{_suffix}", self._route_handler(_page, _pm, _pf, _pl, **_pk), _methods.split(","), _desc)

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
            # 管理 API 服务端收口：AstrBot 宿主 dashboard 会话是鉴权边界（宿主契约未在本仓提供，
            # 见 AICODE_AUDIT §10）。宿主 view_handler 从不传 request（仅绑在 astrbot.api.web.request
            # 上下文代理），缺失时代理解析（同 _get_req 单源）＋绑定探测：代理未绑定时访问属性抛
            # RuntimeError → 仍失败关闭 403；绑定后仅做显式非管理员标记检查，缺标记交宿主会话判定。
            if func_name in _XB_MUTATING_HANDLERS:
                _deny_req = request if request is not None else (args[0] if args else None)
                if _deny_req is None:
                    try:
                        from astrbot.api.web import request as _proxy_req
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
