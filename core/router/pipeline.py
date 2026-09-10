# -*- coding: utf-8 -*-
"""core/router/pipeline.py — 路由·pipeline（原 router.py 切分）。"""
from . import shared as _S
from .commands import _matches_engine
from .guards import _batch_guard_map, _guard
from .rules import _cmd_disabled, _cmd_need_admin, _custom_cmd, _custom_idx, apply_reply_override
from .shared import _render_vars


def handle(gid, qq, raw, is_private=False, is_admin=False, store=None, engines=None, chat_mod=None, superadmin_mod=None):
    # 自定义索引版本兜底：handle_cfg_save 直改 _CONFIG 不走 set_config 时 ver 未 bump，
    # 每次使用 _CUSTOM_IDX 前以 ver+内容指纹重建，避免 stale（群聊仍不走 chat，只补映射不断路）
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
    # 群组开关：按 gid 静默，包括超管，仅群聊
    if not is_private and gid and store:
        try:
            if store.cfg("群组开关配置", str(gid), "真") != "真":
                return None
        except Exception:
            pass
    # 维护开关
    try:
        if store and store.cfg("维护配置", "维护开关", "假") == "真" and not is_admin:
            return store.cfg("维护配置", "维护信息", "🚧 维护中")
    except Exception:
        pass
    if is_private:
        try:
            if chat_mod:
                return chat_mod.handle(qq, raw)
        except Exception:
            pass
        if engines and "chat" in engines:
            try:
                return engines["chat"].handle(qq, raw)
            except Exception:
                pass
        return None
    if raw.strip() in ("主菜单", "菜单", "系统菜单"):
        return _S._MAIN_MENU
    if not is_private and store:
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
        return "【指令】「%s」已被禁用，无法使用该功能！如需开启，请在指令页勾选启用。" % dis
    # 超管权限：命中 指令权限配置=超管 的指令，非超管一律静默（与超管系统同规则）
    if not is_admin and store:
        try:
            if _cmd_need_admin(raw, store):
                return None
        except Exception:
            pass
    # 依次分发 9 引擎（批量守卫预计算，单消息18次读→0次）
    _batch_map = _batch_guard_map(gid, is_admin, store) if store and not is_private else {}
    if engines:
        for _eng in ("slave", "sign", "bank", "ent", "spirit", "ride", "guild", "adventure"):
            fn = engines.get(_eng)
            if not fn:
                continue
            matched = _matches_engine(raw, _eng, store)
            g = _batch_map.get(_eng) if _batch_map else (_guard(gid, _eng, is_admin, raw, store) if store else None)
            if g:
                if matched:
                    return g
                continue
            try:
                r = fn.handle(gid, qq, raw) if hasattr(fn, "handle") else fn(gid, qq, raw)
            except Exception as e:
                import traceback
                err_tb = traceback.format_exc()
                try:
                    from ..logger import error as _log_err
                    _log_err(f"[{_eng}] handle异常: {e}\n{err_tb}")
                except Exception:
                    pass
                # 若消息明确匹配该系统指令却执行崩溃，绝不可静默吞掉！向用户反馈错误提示
                # 底层存储异常必须优雅降级为繁忙提示，严禁向群聊暴露 database is locked / rollback 等原始DB错误
                if matched:
                    sysname = _S._SYS_ENG.get(_eng, _eng)
                    try:
                        msg_l = str(e).lower()
                    except Exception:
                        msg_l = ""
                    if any(k in msg_l for k in ("database", "locked", "rollback", "transaction", "sqlite", "misuse", "owner", "not defined")):
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
                return g
        else:
            try:
                r = superadmin_mod.handle(gid, qq, raw, is_admin)
                if r:
                    return apply_reply_override(raw, r, store)
            except Exception as e:
                import traceback
                try:
                    from ..logger import error as _log_err
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
                return g
        else:
            try:
                r = fn.handle(gid, qq, raw, is_admin) if hasattr(fn, "handle") else fn(gid, qq, raw, is_admin)
                if r:
                    return apply_reply_override(raw, r, store)
            except Exception as e:
                import traceback
                try:
                    from ..logger import error as _log_err
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

__all__ = ["handle"]
