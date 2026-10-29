# -*- coding: utf-8 -*-
"""超管系统 - 对齐原版超管/账户管理指令(已并入原群管的禁言/踢人/账户管理)
权限: is_admin = AstrBot 机器人管理员(event.is_admin())
数据级可测: 群列表/应用统计/账户管理(扣钱/充值/清空)
平台操作: 禁言/踢人 通过 AstrBot 适配器 call_action 执行(见 main._do_platform)
"""
import os
import re

from . import storage as ST

MENU = (
    "🔧 超管系统\r\n"
    "━━━━━━━━━━━━━━\r\n"
    "📇 群列表　📊 应用统计　🔖 版本\r\n"
    "💸 扣钱 @QQ 金额　💳 充钱 @QQ 金额\r\n"
    "🧹 清空财富/体力/魅力/账户/精灵/用户 @QQ\r\n"
    "🔨 禁言 @QQ 分钟　🚪 踢人 @QQ\r\n"
    "💾 备份（立即备份全量数据）\r\n"
    "🛠️ 开启维护　关闭维护　维护信息 内容　查看维护（群内只管本群）\r\n"
    "📊 当前数值（查看当前生效数值与档位）\r\n"
    "🔖 检查更新（仅超管可查）\r\n"
    "━━━━━━━━━━━━━━\r\n"
    "⚠️ 全部指令仅限 AstrBot 机器人管理员\r\n"
    "💡 发送对应指令即可操作"
)


def _cfg(key, default=""):
    return ST.cfg("超管配置", key, default)



def _target_name(gid, t):
    t_str = str(t)
    try:
        from ..games import slave as S
        if gid:
            try:
                n = S.display_name(gid, t_str, "")
                if n:
                    return n
            except Exception:
                pass
        if hasattr(S, "uname"):
            try:
                n = S.uname(S.state(gid), t_str)
                if n and n != t_str:
                    return n
            except Exception:
                pass
        if hasattr(S, "NOTE_NAMES") and not gid:
            n = S.NOTE_NAMES.get(t_str)
            if n:
                return n
    except Exception:
        pass
    try:
        g = ST.group(gid)
        if g and t_str in g.users():
            n = g[t_str].get("name")
            if n and str(n).strip() and str(n).strip() != "0":
                return str(n).strip()
    except Exception:
        pass
    try:
        a = ST.acct(gid, t_str)
        n = a.get("name", "")
        if n and str(n).strip() and str(n).strip() != "0":
            return str(n).strip()
    except Exception:
        pass
    return t_str

def _name(qq, gid=""):
    try:
        from ..games import slave as S
        n = S.display_name(gid, str(qq), "")
        if n:
            return n
        if gid:
            return str(qq)
        return S.NOTE_NAMES.get(str(qq), str(qq)) if hasattr(S, "NOTE_NAMES") else str(qq)
    except Exception:
        return str(qq)


def _sum_money(gid, qq):
    return ST.coins_get(gid, qq)


def _acct(gid, qq):
    return ST.acct(gid, qq)


# 检查更新60s进程缓存：引擎跑在_XB_EXEC线程池，同步urllib约10s，连点即占满12 worker
_VER_CACHE = {"t": 0.0, "info": None}


# ---- 群列表 / 应用统计 ----
def cmd_groups():
    if ST._DB is None:
        return "无数据。"
    try:
        with ST._LOCK:
            rows = ST._DB.execute(
                "SELECT gid, COUNT(*) c FROM groups GROUP BY gid UNION ALL "
                "SELECT gid, COUNT(*) FROM accounts GROUP BY gid").fetchall()
    except Exception:
        return "暂无群数据。"
    seen = {}
    for gid, c in rows:
        seen[str(gid)] = seen.get(str(gid), 0) + int(c)
    lst = sorted(seen.items(), key=lambda x: -x[1])
    out = ["📇 群列表（群号：玩家数）"]
    for gid, c in lst[:30]:
        out.append(f"{gid}：{c}")
    return "\r\n".join(out) if len(out) > 1 else "暂无群数据。"


def cmd_stats():
    if ST._DB is None:
        return "无数据。"
    try:
        with ST._LOCK:
            nw = ST._DB.execute("SELECT COUNT(*) FROM wallet").fetchone()[0]
            na = ST._DB.execute("SELECT COUNT(*) FROM accounts").fetchone()[0]
            ng = ST._DB.execute("SELECT COUNT(DISTINCT gid) FROM accounts").fetchone()[0]
            tm = ST._DB.execute("SELECT COALESCE(SUM(money),0) FROM wallet").fetchone()[0]
    except Exception:
        return "暂无统计数据。"
    # 兼容新旧键：deposit(英文化) 与 cunkuan(旧)，中文统计文案不变
    try:
        with ST._LOCK:
            td = ST._DB.execute("SELECT COALESCE(SUM(CAST(COALESCE(json_extract(data,'$.deposit'), json_extract(data,'$.cunkuan')) AS INTEGER)),0) FROM accounts").fetchone()[0] if ST._DB else 0
        td = int(td or 0)
    except Exception:
        td = 0
    try:
        _cn = ST.coin_name() if hasattr(ST, "coin_name") else "金币"
    except Exception:
        _cn = "金币"
    return (f"📊 应用统计\r\n"
            f"钱包用户：{nw}　档案用户：{na}\r\n"
            f"群数：{ng}　总{_cn}：{tm}　总存款：{td}")


# ---- 账户管理 ----
def _parse_target_amount(arg):
    """解析 扣钱/充钱 目标与金额: QQ-only（[CQ:at,qq=]/[At:QQ]/@QQ/纯数字），兼容长昵称/空格/Emoji/末尾附带@QQ，金额取正整数"""
    arg = str(arg or "").strip()
    if not arg:
        return None, None
    t, amt = None, None

    # 1. 查找明确的目标 QQ (CQ码 / [At:QQ] / @QQ / 开头QQ)
    m = re.search(r"(?:\[CQ:at,qq=(\d+)[^\]]*\]|\[At:\s*(\d+)\])", arg)
    if m:
        t = m.group(1) or m.group(2)
    if not t:
        # 末尾附带的 @QQ (由 _append_at_segments 产生)
        m = re.search(r"@(\d{5,12})\s*$", arg)
        if m:
            t = m.group(1)
    if not t:
        # @QQ (后跟非数字)
        m = re.search(r"@\s*(\d{5,12})(?!\d)", arg)
        if m:
            t = m.group(1)
    if not t:
        # 开头 QQ 数字串
        m = re.match(r"(\d{5,12})\b", arg)
        if m:
            t = m.group(1)

    # 2. 如果依然没有，测试纯数字双参数格式: QQ 金额
    if not t:
        m = re.fullmatch(r"@?\s*(\d{5,12})\s*\*?\s*(\d+)", arg)
        if m:
            return m.group(1), int(m.group(2))

    if not t:
        return None, None

    # 找到 t 后，从字符串中剔除所有针对 t 的标识（CQ码、[At:QQ]、@QQ 以及作为独立词的 t）
    rem = re.sub(r"\[CQ:at,qq=" + t + r"[^\]]*\]", " ", arg)
    rem = re.sub(r"\[At:\s*" + t + r"\]", " ", rem)
    rem = re.sub(r"@\s*" + t + r"(?!\d)", " ", rem)
    rem = re.sub(r"@" + t + r"\b", " ", rem)
    rem = re.sub(r"(?<!\d)" + t + r"(?!\d)", " ", rem, count=1)

    # 提取剩余文本中的金额数字（末尾或被空格/*包围的纯数字串）
    nums = re.findall(r"(?:^|[\s*])(\d+)(?:\s|$)", rem)
    if nums:
        try:
            amt = int(nums[-1])
        except Exception:
            pass

    if amt is not None and amt > 0:
        return t, amt
    return None, None


def _looks_like_target_arg(arg):
    """判断参数是否显式带有 @、CQ 码、[At:QQ] 或纯数字（用于区分输错参数的指令与日常闲聊）"""
    s = (arg or "").strip()
    if not s:
        return True
    if s.startswith(("@", "[CQ:at", "[At:")):
        return True
    if re.match(r"^\d+$", s):
        return True
    return False


def cmd_deduct(gid, qq, arg):
    """扣钱: 超管扣除指定用户指定金额（优先扣现金，现金不足自动扣银行存款），显示群昵称"""
    arg = (arg or "").strip()
    t, amt = _parse_target_amount(arg)
    if not t or amt is None or amt <= 0:
        if _looks_like_target_arg(arg):
            return "格式：扣钱 @QQ 金额（正整数）"
        return None
    with ST._LOCK:
        cur_cash = _sum_money(gid, t)
        a = _acct(gid, t)
        cur_dep = a.int("deposit")
        cash_ded = min(cur_cash, amt)
        dep_ded = min(cur_dep, max(0, amt - cash_ded))
        updates = {"deposit": str(max(0, cur_dep - dep_ded))} if dep_ded > 0 else None
        nv = ST.txn_coins_acct(gid, t, -cash_ded, updates)
        if nv is None:
            return "数据库繁忙，扣钱未成功，请稍后重试。"
    t_name = _target_name(gid, t)
    total_ded = cash_ded + dep_ded
    dep_info = f"，存款 {cur_dep}→{max(0, cur_dep - dep_ded)}" if dep_ded > 0 else ""
    return f"已扣除【{t_name}】{total_ded}{ST.coin_name()}（{cur_cash}→{nv}{dep_info}）"


def cmd_recharge(gid, qq, arg):
    """充钱: 超管给指定用户充值指定金额，显示群昵称"""
    arg = (arg or "").strip()
    t, amt = _parse_target_amount(arg)
    if not t or amt is None or amt <= 0:
        if _looks_like_target_arg(arg):
            return "格式：充钱 @QQ 金额（正整数）"
        return None
    nv = ST.coins_add(gid, t, amt)
    if nv is None:
        return "数据库繁忙，充值未成功，请稍后重试。"
    t_name = _target_name(gid, t)
    return f"已为【{t_name}】充值 {amt}{ST.coin_name()}（当前 {nv}）"


def _clear_money(gid, t):
    with ST._LOCK:
        cur = _sum_money(gid, t)
        if ST.txn_coins_acct(gid, t, -cur if cur else 0, {"deposit": "0", "cunkuan": "0"}) is None:
            return "数据库繁忙，清空财富未成功，请稍后重试。"
    return f"已清空 <{_name(t, gid)}> 财富。"


def _clear_field(gid, t, field, label):
    a = _acct(gid, t)
    a.set(field, "0")
    ST.acct_save(gid, t)
    return f"已清空 <{_name(t, gid)}> 的{label}。"


def cmd_clear(gid, qq, arg):
    arg = (arg or "").strip()
    if arg in ("清空", "重置"):
        return "格式：清空{财富/体力/魅力/账户/精灵/用户} @QQ"
    m = re.match(r"^(?:清空|重置)(财富|体力|魅力|账户|精灵|用户)\s*(.*)$", arg)
    if not m:
        return None
    kind = m.group(1)
    rest = m.group(2).strip()
    t = None
    rem = rest
    try:
        t_parsed, rem_parsed = ST.parse_at(rest)
        if t_parsed:
            try:
                _ok = ST.is_qq_mention(t_parsed, rest) if hasattr(ST, "is_qq_mention") else True
            except Exception:
                _ok = True
            if _ok:
                t = str(t_parsed).strip()
                rem = (rem_parsed or "").strip()
    except Exception:
        pass
    if not t:
        m_cq = re.search(r"(?:\[CQ:at,qq=(\d+)[^\]]*\]|\[At:\s*(\d+)\])", rest)
        if m_cq:
            t = m_cq.group(1) or m_cq.group(2)
            rem = re.sub(r"(?:\[CQ:at,qq=\d+[^\]]*\]|\[At:\s*\d+\])", "", rest, count=1).strip()
    if not t:
        m_qq = re.search(r"@?\s*(\d{5,12})", rest)
        if m_qq:
            t = m_qq.group(1)
            rem = rest.replace(m_qq.group(0), "", 1).strip()
    rem = re.sub(r"@\S+", "", rem).strip()
    if not t or rem:
        if not rest or rest.startswith(("@", "[CQ:at", "[At:")):
            return "格式：清空{财富/体力/魅力/账户/精灵/用户} @QQ"
        return None
    if kind == "财富":
        return _clear_money(gid, t)
    if kind in ("体力", "stamina"):
        return _clear_field(gid, t, "stamina", "体力")
    if kind in ("魅力", "charm"):
        return _clear_field(gid, t, "charm", "魅力")
    if kind == "账户":
        a = _acct(gid, t)
        a.kv.clear()
        ST.acct_save(gid, t)
        _clear_money(gid, t)
        return f"已清空 <{_name(t, gid)}> 的账户及财富数据。"
    if kind == "精灵":
        a = _acct(gid, t)
        a.set("spirits", "{}")
        ST.acct_save(gid, t)
        return f"已清空 <{_name(t, gid)}> 的精灵。"
    if kind == "用户":
        # 1. 清空底层存储与三表数据 (wallet, accounts, groups)
        if hasattr(ST, "user_clear"):
            ST.user_clear(gid, t)
        else:
            a = _acct(gid, t)
            a.kv.clear()
            ST.acct_save(gid, t)
            _clear_money(gid, t)
        # 2. 清空奴隶与释放名下奴隶
        try:
            from ..games import slave as _sl
            if hasattr(_sl, "clear_user_slave"):
                _sl.clear_user_slave(gid, t)
        except Exception:
            try:
                import slave as _sl2
                if hasattr(_sl2, "clear_user_slave"):
                    _sl2.clear_user_slave(gid, t)
            except Exception:
                pass
        ST.flush_all()
        # 昵称同步清：否则 NOTE_NAMES 残留幽灵名，反查误中已删用户
        try:
            from ..games import slave as _sl4
            if hasattr(_sl4, "clear_note_name"):
                _sl4.clear_note_name(gid, t)
        except Exception:
            try:
                import slave as _sl5
                if hasattr(_sl5, "clear_note_name"):
                    _sl5.clear_note_name(gid, t)
            except Exception:
                pass
        # 清空后帮派缓存即时失效，避免列表/排行残留已删成员（15 秒窗口）
        try:
            from ..games import guild as _gd
            if hasattr(_gd, "_invalidate_guild_cache"):
                _gd._invalidate_guild_cache(gid)
        except Exception:
            try:
                import guild as _gd2
                if hasattr(_gd2, "_invalidate_guild_cache"):
                    _gd2._invalidate_guild_cache(gid)
            except Exception:
                pass
        return f"已彻底清空 <{_name(t, gid)}> 的所有数据（包含奴隶、精灵与礼包状态，可重新领取新手礼包）。"
    return "未知操作。"


# ---- 禁言/踢人(平台动作, 由 main._do_platform 执行) ----
def cmd_mute(gid, qq, arg):
    """禁言 @QQ 分钟（QQ-only，不认昵称；日常聊天如“禁言原神原神”静默不回格式）"""
    arg = (arg or "").strip()
    if not arg:
        return "格式：禁言 @QQ 分钟"
    target = None
    rest = arg
    m_cq = re.search(r"(?:\[CQ:at,qq=(\d+)[^\]]*\]|\[At:\s*(\d+)\])", arg)
    if m_cq:
        target = m_cq.group(1) or m_cq.group(2)
        rest = re.sub(r"(?:\[CQ:at,qq=\d+[^\]]*\]|\[At:\s*\d+\])", "", arg, count=1).strip()
    else:
        try:
            t, r = ST.parse_at(arg)
            if t:
                try:
                    _ok = ST.is_qq_mention(t, arg) if hasattr(ST, "is_qq_mention") else True
                except Exception:
                    _ok = True
                if _ok:
                    target = str(t).strip()
                    rest = (r or "").strip()
        except Exception:
            pass
    if not target:
        m = re.search(r"@?\s*(\d{5,12})\s+(\d+)\s*(?:分钟|分|m|min)?", arg)
        if m:
            target = m.group(1)
            rest = m.group(2)
    if target:
        rest_clean = re.sub(r"@\S+", "", rest).strip()
        if not rest_clean:
            return "格式：禁言 @QQ 分钟"
        m2 = re.fullmatch(r"(\d+)\s*(?:分钟|分|m|min)?", rest_clean)
        if not m2:
            return None
        mins = int(m2.group(1))
        if mins <= 0:
            return "格式：禁言 @QQ 分钟"
        if str(target) == str(qq):
            return "不能对自己执行禁言！"
        return "__XB_PLATFORM__|mute|%s|%d" % (target, mins * 60)
    if _looks_like_target_arg(arg):
        return "格式：禁言 @QQ 分钟"
    return None


def cmd_kick(gid, qq, arg):
    """踢人 @QQ（QQ-only，与禁言同口径；日常聊天如“踢人了”静默不回格式）"""
    arg = (arg or "").strip()
    if not arg:
        return "格式：踢人 @QQ"
    target = None
    rest = ""
    m_cq = re.search(r"(?:\[CQ:at,qq=(\d+)[^\]]*\]|\[At:\s*(\d+)\])", arg)
    if m_cq:
        target = m_cq.group(1) or m_cq.group(2)
        rest = re.sub(r"(?:\[CQ:at,qq=\d+[^\]]*\]|\[At:\s*\d+\])", "", arg, count=1).strip()
    else:
        try:
            t, r = ST.parse_at(arg)
            if t:
                try:
                    _ok = ST.is_qq_mention(t, arg) if hasattr(ST, "is_qq_mention") else True
                except Exception:
                    _ok = True
                if _ok:
                    target = str(t).strip()
                    rest = (r or "").strip()
        except Exception:
            pass
    if not target:
        m_num = re.search(r"@?\s*(\d{5,12})", arg)
        if m_num:
            target = m_num.group(1)
            rest = arg.replace(m_num.group(0), "", 1).strip()

    rest_clean = re.sub(r"@\S+", "", rest).strip()
    if target:
        if rest_clean:
            return None
        if not target.isdigit():
            return "格式：踢人 @QQ"
        if target == str(qq):
            return "不能对自己执行踢人！"
        return "__XB_PLATFORM__|kick|%s|0" % target
    if _looks_like_target_arg(arg):
        return "格式：踢人 @QQ"
    return None


def cmd_backup_xb():
    try:
        dst = ST.backup_user_data(force=True)
        if dst:
            # 脱敏：仅展示相对路径
            try:
                base = ST.BACKUP_DIR or ""
                rel = dst.replace(base, "").lstrip("/\\") if base else dst
            except Exception:
                rel = dst
            extra = ""
            try:
                from . import webdav as _wd
                if _wd.is_enabled():
                    extra = "，WebDAV 云备份任务已触发"
            except Exception:
                try:
                    from . import webdav as _wd
                    if _wd.is_enabled():
                        extra = "，WebDAV 云备份任务已触发"
                except Exception:
                    pass
            return f"备份成功：{rel}（已写入 backups{extra}）"
        return "备份失败（无数据或目录不可写）"
    except Exception as e:
        return f"备份异常：{e}"


def _maint_on(gid=None):
    # 群内发送只维修本群（recall 标记）；群号异常直接拒绝，禁回退全局（防误锁全群）
    if gid and str(gid).isdigit():
        try:
            ST.recall_set("group_maint_%s" % gid, "1")
        except Exception:
            pass
        return "本群已进入维修模式。"
    if gid:
        return "群号异常，已拒绝执行（未改动任何配置）。"
    cur = dict(ST._CONFIG)
    import copy as _copy
    cur = _copy.deepcopy(cur)
    cur.setdefault("维护配置", {})["维护开关"] = "真"
    ST.set_config(cur); ST.save_config()
    return "已开启全局维修模式。"

def _maint_off(gid=None):
    if gid and str(gid).isdigit():
        try:
            ST.recall_set("group_maint_%s" % gid, "0")
        except Exception:
            pass
        return "本群已退出维修模式。"
    if gid:
        return "群号异常，已拒绝执行（未改动任何配置）。"
    cur = dict(ST._CONFIG)
    import copy as _copy
    cur = _copy.deepcopy(cur)
    cur.setdefault("维护配置", {})["维护开关"] = "假"
    ST.set_config(cur); ST.save_config()
    return "已关闭全局维修模式。"

def _maint_msg(msg):
    msg = (msg or "").strip()
    if not msg:
        return "格式：维护信息 内容"
    cur = dict(ST._CONFIG)
    import copy as _copy
    cur = _copy.deepcopy(cur)
    cur.setdefault("维护配置", {})["维护信息"] = msg
    ST.set_config(cur); ST.save_config()
    return f"已设置维护信息：{msg}"

def _version():
    """本地版本：读 version.py 单源（get_version 恒有值，无兜底链）。"""
    from .version import get_version
    return f"小白测试版版本：{get_version()}"



# ---- 统一入口（测试指令仅超管，WebUI可配但不显示于MENU，已删 个人信息） ----
# 注意：凡 handle() 响应的别名必须同步进本表；非超管命中一律静默 None（BY DESIGN，见 AIINFO）
# 超管指令一律精确单触发词，禁冗余别名/模糊词
_ADMIN_CMDS = ("群列表", "应用统计", "扣钱", "充钱", "清空", "重置", "禁言", "踢人", "备份", "维护信息", "查看维护", "检查更新", "测试xbtest", "测试testxb", "xbtest", "测试xbtest all", "测试testxb all", "xbtest all", "测试testxb1", "测试testxb2", "测试testxb3", "测试testxb4", "测试testxb5", "测试testxb6", "测试testxb7", "测试testxb8", "超管列表", "测试图片", "webdav测试", "开启维护", "关闭维护", "当前数值", "数值调控")


def _cmd_current_values():
    """超管精确指令「当前数值」：输出当前生效的调控模式（固定/实时）＋12 项核心数值。"""
    try:
        from .api.balance import PRESETS as _PRE, _BALANCE_SIG_KEYS as _SIG, get_balance_state_snapshot as _snap
    except Exception:
        return "数值引擎未就绪，请稍后重试"
    try:
        st = _snap()
        ctrl = st.get("control_type", "fixed")
        best = st.get("mode", "standard")
        mm = int(st.get("mismatch_count", 0))
        rt = st.get("realtime_metrics") or {}
        _names = {"standard": "标准平衡模式", "casual": "休闲高福利模式", "hardcore": "硬核博弈模式"}
        custom_keys = st.get("custom_keys") or []
        if ctrl == "realtime":
            _head = (
                f"📊 当前数值【⚡ 实时调整模式】（基准：{_names.get(best, best)}）\r\n"
                f"🌐 经济阶段：{rt.get('phase', '均衡稳态期')}（通胀指数 {rt.get('inflation_index', 0)}）\r\n"
                f"👥 活跃玩家：{rt.get('player_count', 0)}人 | 中位资产：{ST.fmt_coins(rt.get('median_wealth', 0))} | 人均：{ST.fmt_coins(rt.get('avg_wealth', 0))}\r\n"
                f"⚖️ 动态倍率：产出 {rt.get('faucet_mult', 1.0)}x / 回收 {rt.get('sink_mult', 1.0)}x\r\n"
                f"🔄 实时修正：随玩家后续经济与活跃度自动动态校准，手动调控项绝对保护\r\n"
                f"----------------"
            )
        else:
            if mm == 0:
                _head = f"📊 当前数值【📌 固定模式 · {_names.get(best, best)}】"
            else:
                _head = f"📊 当前数值【📌 固定模式 · 自定义】（基准：{_names.get(best, best)}，偏移{mm}项）"
        _lines = [_head]
        if custom_keys:
            _lines.append(f"🔒 手动调控锁定（{len(custom_keys)}项保护）：{', '.join(custom_keys[:5])}{'等' if len(custom_keys) > 5 else ''}")
        _best_pre = _PRE.get(best, {})
        for _sec, _key in _SIG:
            try:
                _val = ST.cfg(_sec, _key, "")
                if _val == "":
                    _val = _best_pre.get(_sec, {}).get(_key, "")
                if _key == "赌博最大金额":
                    try:
                        if int(float(_val or 0)) < 100000:
                            _val = "100000"
                    except Exception:
                        _val = "100000"
                _lines.append("%s：%s" % (_key, _val))
            except Exception:
                pass
        return "\r\n".join(_lines)
    except Exception as e:
        return f"读取当前数值异常: {e}"


def _cmd_balance_control(arg):
    """超管指令「数值调控」：支持切换【固定模式（标准/休闲/硬核）】与【实时调整模式】。"""
    try:
        from .api.balance import apply_balance_config as _apply_bal
    except Exception:
        return "数值引擎未就绪，请稍后重试"
    a = (arg or "").strip()
    if not a or a in ("状态", "查看", "详情"):
        return (
            _cmd_current_values()
            + "\r\n----------------\r\n"
            + "💡 切换指令：\r\n"
            + "• 数值调控 固定 标准|休闲|硬核\r\n"
            + "• 数值调控 实时 [标准|休闲|硬核]"
        )
    parts = a.split()
    mode_map = {
        "标准": "standard", "标准平衡": "standard", "standard": "standard",
        "休闲": "casual", "休闲高福利": "casual", "高福利": "casual", "casual": "casual",
        "硬核": "hardcore", "硬核博弈": "hardcore", "hardcore": "hardcore",
    }
    mode_names = {"standard": "🟢 标准平衡模式", "casual": "🟡 休闲高福利模式", "hardcore": "🔴 硬核博弈模式"}
    p0 = parts[0].lower()
    if p0 in ("实时", "实时调整", "实时模式", "动态", "realtime", "dynamic"):
        base_m = ST.cfg("设置", "平衡模式", "standard") or "standard"
        if len(parts) >= 2 and parts[1].lower() in mode_map:
            base_m = mode_map[parts[1].lower()]
        if base_m not in mode_names:
            base_m = "standard"
        res = _apply_bal("realtime", base_m)
        rt = res.get("realtime_metrics") or {}
        lock_txt = f"\r\n🔒 已保护锁定项（{len(res['skipped_custom_keys'])}项免受覆盖）：{', '.join(res['skipped_custom_keys'][:4])}" if res.get("skipped_custom_keys") else ""
        return (
            f"⚡ 已开启【实时调整模式】\r\n"
            f"📌 基准档位：{mode_names.get(base_m, base_m)}\r\n"
            f"🌐 当前阶段：{rt.get('phase', '均衡稳态期')}（通胀指数 {rt.get('inflation_index', 0)}）\r\n"
            f"⚖️ 动态倍率：产出 {rt.get('faucet_mult', 1.0)}x / 回收 {rt.get('sink_mult', 1.0)}x\r\n"
            f"✅ 已同步调控 {res.get('updated_sections', 0)} 个模块（{res.get('updated_keys', 0)} 项参数）"
            f"{lock_txt}"
        )
    if p0 in ("固定", "固定模式", "预设", "fixed"):
        sub = parts[1].lower() if len(parts) >= 2 else "标准"
        m = mode_map.get(sub)
        if not m:
            return "格式：数值调控 固定 标准|休闲|硬核\r\n或：数值调控 实时 [标准|休闲|硬核]"
        res = _apply_bal("fixed", m)
        lock_txt = f"\r\n🔒 已保护锁定项（{len(res['skipped_custom_keys'])}项免受覆盖）：{', '.join(res['skipped_custom_keys'][:4])}" if res.get("skipped_custom_keys") else ""
        return (
            f"📌 已切换至【固定模式 · {mode_names.get(m, m)}】\r\n"
            f"✅ 已写入 {res.get('updated_sections', 0)} 个系统模块（{res.get('updated_keys', 0)} 项数值参数）"
            f"{lock_txt}"
        )
    if p0 in mode_map:
        m = mode_map[p0]
        res = _apply_bal("fixed", m)
        lock_txt = f"\r\n🔒 已保护锁定项（{len(res['skipped_custom_keys'])}项免受覆盖）：{', '.join(res['skipped_custom_keys'][:4])}" if res.get("skipped_custom_keys") else ""
        return (
            f"📌 已切换至【固定模式 · {mode_names.get(m, m)}】\r\n"
            f"✅ 已写入 {res.get('updated_sections', 0)} 个系统模块（{res.get('updated_keys', 0)} 项数值参数）"
            f"{lock_txt}"
        )
    return "格式：\r\n• 数值调控 固定 标准|休闲|硬核\r\n• 数值调控 实时 [标准|休闲|硬核]"


def _cmd_imgtest():
    """超管图片链路诊断：文本报告 + 双图元组直传（图2路径，生产验证有效）。

    发送后对照：图1/图2各应出现一张（均走元组）。
    只见文字不见图→都没图=适配器发图整体失败或文件不可读；缺一张=对应文件缺失。
    CQ 路径已退役（中文+斜杠在适配器侧不稳定），引擎内部不再拼CQ。
    """
    lines = ["🧪 图片链路诊断"]
    try:
        from . import messaging as _plat
        _bound = getattr(_plat, "_Image", None) is not None
    except Exception:
        try:
            from . import messaging as _plat
            _bound = getattr(_plat, "_Image", None) is not None
        except Exception:
            _bound = False
    lines.append("Image 组件绑定：%s" % ("✅ 已绑定" if _bound else "❌ 未绑定（图片将静默丢失）"))
    cands = []
    try:
        base = os.path.dirname(os.path.abspath(__file__))
        roots = [os.path.join(base, "..", "data", "img", "gacha", "SSR"),
                 os.path.join(base, "..", "data", "gacha_img", "SSR"),
                 os.path.join(base, "..", "data", "img", "nuli", "SSR"),
                 os.path.join(base, "..", "data", "img", "rides"),
                 os.path.join(base, "..", "data", "img")]
        for r in roots:
            try:
                if os.path.isdir(r):
                    for fn in sorted(os.listdir(r)):
                        if fn.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp")):
                            fp = os.path.abspath(os.path.join(r, fn))
                            if os.path.isfile(fp):
                                cands.append(fp)
                                break
            except Exception:
                pass
            if len(cands) >= 2:
                break
    except Exception:
        pass
    seen = []
    for p in cands:
        if p not in seen:
            seen.append(p)
    cands = seen[:2]
    if not cands:
        return "\r\n".join(lines + ["❌ 未找到任何可用图片文件", "请检查 data/img/gacha/SSR 与 data/img/rides 目录是否存在图片"])
    for i, p in enumerate(cands, 1):
        try:
            sz = os.path.getsize(p)
            lines.append("图%d：%s（%dKB，存在✅）" % (i, os.path.basename(p), sz // 1024))
        except Exception:
            lines.append("图%d：%s" % (i, os.path.basename(p)))
    lines.append("下面应出现 2 张图：图1/图2 均走元组路径")
    text = "\r\n".join(lines)
    imgs = list(cands[:2]) if len(cands) >= 2 else list(cands[:1])
    return text, imgs


def handle(gid, qq, raw, is_admin=False):
    text = (raw or "").strip()
    if not text:
        return None
    if not is_admin:
        # 全静默：非超管任何输入均无提示（BY DESIGN，见 AIINFO）
        return None
    if text == "版本":
        return _version()
    if text == "检查更新":
        try:
            info = None
            try:
                import time as _t_ver
                _now = _t_ver.time()
                if _VER_CACHE.get("info") is not None and (_now - float(_VER_CACHE.get("t") or 0)) < 60:
                    info = _VER_CACHE.get("info")
                else:
                    raise ValueError("cache-miss")
            except ValueError:
                from .api import version_check as updater
                # 测试版查 BETA 通道（xbtest 快照仓）；空 repo 默认查官方仓，对 beta 是误导
                info = updater.check_latest_version("", updater.GITHUB_REPO_XBTEST)
                try:
                    import time as _t_ver2
                    _VER_CACHE["t"] = _t_ver2.time()
                    _VER_CACHE["info"] = info
                except Exception:
                    pass

            if info and info.get("has_update"):
                lat_v = info.get("latest_version")
                cur_v = info.get("current_version")
                name = info.get("release_name", "")
                return f"🚀 发现小白新版本【{lat_v}】(当前: {cur_v})\n🏷️ 发布信息: {name}\n💡 可前往 AstrBot 后台「插件管理」页面点击更新升级！"
            elif info:
                cur_v = info.get("current_version")
                lat_v = info.get("latest_version")
                return f"✅ 当前小白已是最新版本【{cur_v}】(云端最新: {lat_v})。"
            else:
                return _version()
        except Exception as e:
            return f"检查更新异常: {e}"

    if text in ST.wake("超管系统", "超管系统"):
        return MENU
    if _cfg("开关", "真") != "真":
        return "【超管系统】已经被关闭了，无法使用该功能！"
    if text == "群列表":
        return cmd_groups()
    if text == "应用统计":
        return cmd_stats()
    if text.startswith("扣钱"):
        return cmd_deduct(gid, qq, text[2:].strip())
    if text.startswith("充钱"):
        return cmd_recharge(gid, qq, text[2:].strip())
    if text.startswith("清空") or text.startswith("重置"):
        return cmd_clear(gid, qq, text)
    if text.startswith("禁言"):
        return cmd_mute(gid, qq, text[2:].strip())
    if text.startswith("踢人"):
        return cmd_kick(gid, qq, text[2:].strip())
    if text == "备份":
        return cmd_backup_xb()
    # 测试图片：超管图片链路诊断（已在入口按超管全锁）
    if text == "测试图片":
        return _cmd_imgtest()
    if text == "webdav测试":
        try:
            from . import webdav as _wd
            ok, msg = _wd.test_connection()
            return f"【WebDAV测试】{'✅ 成功' if ok else '❌ 失败'}\r\n{msg}"
        except Exception:
            try:
                from . import webdav as _wd
                ok, msg = _wd.test_connection()
                return f"【WebDAV测试】{'✅ 成功' if ok else '❌ 失败'}\r\n{msg}"
            except Exception as e:
                return f"【WebDAV测试】❌ 模块调用异常: {e}"
    if text == "开启维护":
        return _maint_on(gid)
    if text == "关闭维护":
        return _maint_off(gid)
    if text == "维护信息" or text.startswith("维护信息 ") or text.startswith("维护信息\t"):
        return _maint_msg(text[4:].strip())
    if text == "查看维护":
        sw = ST.cfg("维护配置", "维护开关", "假")
        msg = ST.cfg("维护配置", "维护信息", "🚧 维护中")
        try:
            _gm = ST.recall_get("group_maint_%s" % gid, "0") == "1" if gid and str(gid).isdigit() else False
        except Exception:
            _gm = False
        return f"全局维护：{sw}\r\n本群维护：{'开' if _gm else '关'}\r\n维护信息：{msg}"
    # 当前数值 / 数值调控：超管精确指令，无模糊唤醒（BY DESIGN 同超管静默规则）
    if text == "当前数值":
        return _cmd_current_values()
    if text == "数值调控" or text.startswith("数值调控 ") or text.startswith("数值调控\t"):
        return _cmd_balance_control(text[4:].strip())
    # 测试testxb / 超管列表由 app._dispatch 入口直收（聊天不显示，BY DESIGN），此处无需分支
    return None


# COMMANDS 已并入 protocol.engine_commands 统一读取；此处保留模块级声明供反射。
# V8 联合表：静态前缀词 + _ADMIN_CMDS（超管精确词单源）——模块级常量拼接，
# engine_commands 与 _collect_commands（AST 静态求值）同读此表，正则刮词已退役。
COMMANDS = ("超管", "系统开关", "群开关", "维护", "空投", "版本") + _ADMIN_CMDS
