# -*- coding: utf-8 -*-
"""games/slave/handler.py — 奴隶包·handler（原 slave.py 切分，语义不变）。"""
import os as _os
import re as _re
import threading as _threading
try:
    from ...core import storage as ST
    store = ST
except ImportError:
    from core import storage as ST
    store = ST
from . import slave_state as _S
from .base import U, _cmd_lock, cfg, load_events, log, save, star_of, state, uget, weapons_of
from .combat import _treasure_effect, _treasure_names, _weapon_atk_bonus, _weapon_desc, cmd_fight
from .gacha import _gacha_pool, _img_path, _weapon_img_path, cmd_gacha, cmd_starup, cmd_treasure_menu, cmd_treasure_up, cmd_weapon_menu
from .nick import clear_note_name, mark_known
from .profile import cmd_menu, cmd_myinfo, cmd_query, cmd_rank, cmd_rank_price, cmd_rank_sign
from .social import cmd_flatter, cmd_pray, cmd_revolt, cmd_self_work, cmd_study, cmd_work_collect, cmd_work_dispatch
from .trade import cmd_buy_slave, cmd_buyslot, cmd_freedom, cmd_protect, cmd_ransom, cmd_release, cmd_torture
from .slave_state import _resolve_persistent_data_dir

_LEGACY_ONCE = {"done": False}  # 旧档迁移＋gacha 预热只跑一次（锁＋flag 防并发双跑）
_LEGACY_LOCK = _threading.Lock()

_RE_QQ_DIGITS = _re.compile(r"\b(\d{5,12})\b")
_RE_CQ_CODE = _re.compile(r"\[(?:CQ|DR):[^\]]+\]")


def _ensure_legacy_once():
    """懒入口：首个奴隶 handle 时执行一次；init_slave 不再同步做，启动少 listdir＋ini 解析"""
    if _LEGACY_ONCE.get("done"):
        return
    with _LEGACY_LOCK:
        if _LEGACY_ONCE.get("done"):
            return
        try:
            for rar in ("SSR", "SR", "R"):
                _gacha_pool(rar)
        except Exception:
            pass
        try:
            _migrate_legacy_group_ini()
        except Exception:
            pass
        _LEGACY_ONCE["done"] = True


def handle(gid, qq, raw):
    try:
        _ensure_legacy_once()
        reply = _route(gid, qq, raw)
    except Exception:
        return "奴隶系统繁忙，请稍后重试~"
    if reply:
        try:
            # 字符串与元组(带图)统一落盘：此前元组直接返回，抽武器出金等会丢档
            save(str(gid))
        except Exception:
            pass
        return reply
    return None

# Fix: table-driven exact (re-added)
# 已退役查询（v0.7.29 删除）：查询更新/查询版本/查询维护 不再越权转发超管；
# 查询坐骑/精灵/帮派/冒险/查询地图/查询菜单 仅静默放行，避免奴隶查询截胡其他系统。
# 注意：变量名刻意避开 _need/_ADMIN_CMDS，调用处用变量引用，
# 使指令采集器不收录（WebUI 指令页不再出现），行为保持全静默。
_QUERY_SILENT = ("查询更新", "查询版本", "查询维护", "查询坐骑", "查询精灵", "查询帮派", "查询冒险", "查询地图", "查询菜单")
_ROUTE_EXACT = {
    "我要自由": lambda gid, qq, target, st, text: cmd_freedom(gid, qq, st),
    "武器菜单": lambda gid, qq, target, st, text: cmd_weapon_menu(gid, qq, st),
    "宝物菜单": lambda gid, qq, target, st, text: cmd_treasure_menu(gid, qq, st),
    "身价排行榜": lambda gid, qq, target, st, text: cmd_rank_price(gid, st),
    "身价排行": lambda gid, qq, target, st, text: cmd_rank_price(gid, st),
    "签到排行榜": lambda gid, qq, target, st, text: cmd_rank_sign(gid, st),
    "签到排行": lambda gid, qq, target, st, text: cmd_rank_sign(gid, st),
    "排行榜": lambda gid, qq, target, st, text: cmd_rank(gid, st),
    "奴隶打工": lambda gid, qq, target, st, text: cmd_work_dispatch(gid, qq, st),
    "我要打工": lambda gid, qq, target, st, text: cmd_work_dispatch(gid, qq, st),
    "奴隶收工": lambda gid, qq, target, st, text: cmd_work_collect(gid, qq, st),
    "搬砖": lambda gid, qq, target, st, text: cmd_self_work(gid, qq, st),
}


def _find_slave_qq_by_name(gid, name, st=None):
    name = str(name or "").strip()
    if not name:
        return None
    try:
        from .nick import NOTE_NAMES_BY_GROUP
        for (g, q), n in NOTE_NAMES_BY_GROUP.items():
            if (gid is None or str(g) == str(gid)) and n == name:
                return str(q)
    except Exception:
        pass
    if st is not None:
        try:
            for q in st.sections():
                if st[q].get("name", "").strip() == name:
                    return str(q)
        except Exception:
            pass
    try:
        with store._AT_NAMES_LOCK:
            q = store._AT_NAMES.get(name)
            if q:
                return str(q)
    except Exception:
        pass
    return None


def _route(gid, qq, raw):
    gid = str(gid); qq = str(qq)

    # Fix B5: serialize commands per group
    with _cmd_lock(gid):
        return _route_locked(gid, qq, raw)


def _route_locked(gid, qq, raw):

    # 分群开关
    if cfg("分群开关", gid, "") == "假":
        return None

    st = state(gid)
    target, text = store.parse_at(raw)
    # QQ-only：目标仅认 CQ 码 / @数字 / 独立数字串；@昵称命中一律丢弃（防撞名串人）。
    # 独立数字兜底在下方按指令前缀提取（金额误判防护见 _need）。
    try:
        _qq_ok = store.is_qq_mention(target, raw) if hasattr(store, "is_qq_mention") else True
    except Exception:
        _qq_ok = True
    if target and not _qq_ok:
        target = None
        text = str(raw or "").strip()
    mark_known(gid, qq)

    # 兼容纯 QQ 号（无 @）的写法：文案仅 @QQ，但解析支持 QQ 号
    if not target:
        # 仅对需要目标的指令尝试提取，避免金额被误判
        _need = ("我的信息", "查询", "买下", "折磨", "保护", "释放", "赎身", "打架")
        for _pref in _need:
            if text.startswith(_pref):
                m = _RE_QQ_DIGITS.search(text)
                if m:
                    target = m.group(1)
                    text = text.replace(m.group(0), "", 1).strip()
                break

    # 去掉开头的表情码干扰（保留未解析的 @ 文本以便识别无效 @昵称）
    text = _RE_CQ_CODE.sub("", text).strip()

    # Fast path: exact commands
    if text in _ROUTE_EXACT:
        return _ROUTE_EXACT[text](gid, qq, target, st, text)

    if text in store.wake("奴隶系统", "奴隶系统"):
        return cmd_menu()
    if text.startswith("我的信息"):
        rest = text[len("我的信息"):].strip()
        if target:
            _rest_pure = _re.sub(r"@\S+", "", rest).strip()
            if not _rest_pure:
                return cmd_query(gid, qq, target, st)
            return None
        if not rest:
            return cmd_myinfo(gid, qq, st)
        if rest.startswith("@"):
            cand_name = rest.lstrip("@").strip()
            t_cand = _find_slave_qq_by_name(gid, cand_name, st)
            if t_cand:
                return cmd_query(gid, qq, t_cand, st)
            return "未能找到该成员～格式：【查询 @QQ】"
        return None
    if text.startswith("查询"):
        # v0.7.29：9 个查询转发/放行全部退役，一律静默（空白无关，含全角/制表符）。
        if _re.sub(r"\s+", "", text).startswith(_QUERY_SILENT):
            return None
        rest_after_target = text[len("查询"):].strip()
        if target:
            _rest_pure = _re.sub(r"@\S+", "", rest_after_target).strip()
            if not _rest_pure:
                return cmd_query(gid, qq, target, st)
            return None
        _raw0 = _re.sub(r"\[(?:CQ|DR):(?!(?:at\b))[^\]]+\]", "", str(raw or "")).strip()
        rest = _raw0[len("查询"):].strip() if _raw0.startswith("查询") else rest_after_target
        if rest in ("", "我", "自己", "个人", "我的信息", "自己信息", "个人信息"):
            return cmd_myinfo(gid, qq, st)
        if rest.startswith("@"):
            cand_name = rest.lstrip("@").strip()
            t_cand = _find_slave_qq_by_name(gid, cand_name, st)
            if t_cand:
                return cmd_query(gid, qq, t_cand, st)
            return "未能找到该成员～格式：【查询 @QQ】"
        return None
    for _p, _fn in (
        ("买下", cmd_buy_slave),
        ("折磨", cmd_torture),
        ("保护", cmd_protect),
        ("释放", cmd_release),
        ("赎身", cmd_ransom),
        ("打架", cmd_fight),
    ):
        if text.startswith(_p):
            _rest = text[len(_p):].strip()
            if _rest and not _rest.startswith("@"):
                return None
            t_eff = target
            if not t_eff and _rest.startswith("@"):
                t_cand = _find_slave_qq_by_name(gid, _rest.lstrip("@").strip(), st)
                if t_cand:
                    t_eff = t_cand
            return _fn(gid, qq, t_eff, st)
    if text in ("买奴隶位", "购买奴隶位"):
        return cmd_buyslot(gid, qq, st)
    if text in ("百连抽", "100连抽"):
        return cmd_gacha(gid, qq, st, count=100)
    if text in ("五十连抽", "50连抽"):
        return cmd_gacha(gid, qq, st, count=50)
    if text in ("三十连抽", "30连抽"):
        return cmd_gacha(gid, qq, st, count=30)
    if text == "十连抽":
        return cmd_gacha(gid, qq, st, count=10)
    if text == "抽武器":
        return cmd_gacha(gid, qq, st, count=1)
    if text.startswith("武器升星"):
        return cmd_starup(gid, qq, text[4:], st)
    if text.startswith("宝物升阶"):
        return cmd_treasure_up(gid, qq, text[4:], st)
    if text in ("我要造反", "造反"):
        return cmd_revolt(gid, qq, st)
    if text in ("讨好主人", "讨好"):
        return cmd_flatter(gid, qq, st)
    if text in ("我要学习", "学习"):
        return cmd_study(gid, qq, st)
    if text in ("我要祈福", "祈福"):
        return cmd_pray(gid, qq, st)

    # 查询武器/宝物信息: 支持带【】或不带
    q = text
    if q.startswith("【") and q.endswith("】"):
        q = q[1:-1].strip()
    treas = _treasure_names()
    ssr_img_map = {}
    try:
        ssr_pool = _gacha_pool("SSR")
        all_w = [_os.path.splitext(_os.path.basename(p))[0] for p in ssr_pool]
        ssr_img_map = {_os.path.splitext(_os.path.basename(p))[0]: p for p in ssr_pool}
    except Exception:
        all_w = []
    if text.startswith("升星"):
        _raw_w = text[2:]
        _warg = _raw_w.strip("+＋ ").strip()
        if not _warg or _raw_w[:1] in (" ", "\t", "+", "＋") or _warg in all_w or _warg in weapons_of(U(st, qq)):
            return cmd_starup(gid, qq, _raw_w, st)
        return None
    if text.startswith("升阶"):
        _raw_t = text[2:]
        _targ = _raw_t.strip("+＋ ").strip()
        if not _targ or _raw_t[:1] in (" ", "\t", "+", "＋") or _targ in treas:
            return cmd_treasure_up(gid, qq, _raw_t, st)
        return None
    if q in treas:
        stage = int(uget(U(st, qq), q + "升阶", "0"))
        have = int(uget(U(st, qq), q, "0"))
        eff = _treasure_effect(q)
        return (_S.T.T_NAME.format(name=q) + "\r\n" + _S.T.T_STAGE.format(n=stage)
                + "\r\n" + _S.T.T_EFFECT.format(effect=eff)
                + f"\r\n持有数量: {have}")
    if q in all_w:
        u = U(st, qq)
        lv = star_of(u, q)
        table = _S.STAR_ATK
        owned = q in weapons_of(u)
        _lst = _weapon_img_path(q)
        if _lst:
            _pp = _lst[0]
        else:
            imgp = ssr_img_map.get(q, _os.path.join(_S.DATA_DIR, "img", "gacha", "SSR", q + ".png"))
            _pp = _img_path(imgp)
        _bonus = _weapon_atk_bonus(q)
        _desc = _weapon_desc(q)
        _txt = (_S.T.W_NAME.format(name=q) + f"★{lv}\r\n"
                + _S.T.W_EFFECT.format(atk=f"+{table[min(5, lv)] + _bonus}") + "\r\n"
                + _S.T.W_5STAR_EFFECT + "\r\n"
                + ("✔你已拥有" if owned else "✖未拥有")
                + (f"\r\n📝 {_desc}" if _desc else ""))
        if _pp:
            return _txt, [_pp]
        return _txt

    return None





def init_slave(bot_uin="", note_names=None, import_wallet_dir=""):
    """适配层启动时调用: store 初始化 + 机器人QQ + 名片缓存 + (可选)旧drea钱包导入"""
    _S.DATA_DIR = _resolve_persistent_data_dir()
    _S.GROUPS_DIR = _os.path.join(_S.DATA_DIR, "groups")
    _S.WALLET_DIR = _os.path.join(_S.DATA_DIR, "wallet")
    _S.DB_PATH = _os.path.join(_S.DATA_DIR, "xb.db")
    _S.CONFIG_JSON = _os.path.join(_S.DATA_DIR, "config.json")
    _S.GACHA_DIR = _os.path.join(_S.DATA_DIR, "img", "gacha")
    _S.EVENTS_JSON = _os.path.join(_S.DATA_DIR, "events.json")
    _S.BOT_UIN = str(bot_uin or "")
    if note_names:
        _S.NOTE_NAMES.update(note_names)
    load_events()
    if getattr(store, "_DB", None) is None:
        store.init(_S.DB_PATH, _S.CONFIG_JSON)
    _os.makedirs(_S.GROUPS_DIR, exist_ok=True)
    _os.makedirs(_S.WALLET_DIR, exist_ok=True)
    if import_wallet_dir and _os.path.isdir(import_wallet_dir):
        try:
            log("旧drea钱包导入(请用WebUI配置: 已切换为现代存储方案)")
        except Exception as e:
            log(f"钱包导入失败: {e}")
    # gacha 预热＋旧 ini 迁移已懒化（首个 handle 时 _ensure_legacy_once 跑一次），此处不再同步做




def _migrate_legacy_group_ini():
    """一次性: 把旧 light 群档案 ini 迁入 SQLite(源文件保留安全备份)"""
    import configparser as _cp2
    candidate_dirs = [_S.GROUPS_DIR]
    cand_light = _os.path.join(_S._BASE, "..", "..", "light", "data", "nuli_slave")
    if _os.path.isdir(cand_light):
        candidate_dirs.append(cand_light)
    for gdir in candidate_dirs:
        if not _os.path.isdir(gdir):
            continue
        for fn in _os.listdir(gdir):
            if not fn.lower().endswith(".ini"):
                continue
            gid = fn[:-4]
            if not gid.isdigit():
                continue
            g = store.group(gid)
            if g.users():
                continue
            path = _os.path.join(gdir, fn)
            for enc in ("utf-8", "gbk"):
                try:
                    cp = _cp2.ConfigParser(interpolation=None)
                    cp.optionxform = str
                    cp.read(path, encoding=enc)
                    for sec in cp.sections():
                        g[sec].update({k: cp.get(sec, k, fallback="") for k in cp.options(sec)})
                    store.save_group(gid)
                    log(f"群档案迁移成功: {fn} -> 群 {gid}")
                    break
                except Exception:
                    continue




def clear_user_slave(gid, qq):
    """清除单用户的奴隶信息，并释放该用户持有的所有奴隶"""
    gid = str(gid).strip()
    qq = str(qq).strip()
    if not (gid.isdigit() and qq.isdigit()):
        return
    clear_note_name(gid, qq)
    with _cmd_lock(gid):
        st = state(gid)
        # 1. 移除该用户自己的奴隶档案（重置为完全未建立档案状态）
        if hasattr(st, "remove_section"):
            st.remove_section(qq)
        elif st.has_section(qq):
            try:
                del st._users[qq]
            except Exception:
                pass
        # 2. 释放该用户名下的所有奴隶
        for sec in st.sections():
            if str(sec) == qq:
                continue
            u = st[sec]
            if str(u.get("owner", "")) == qq:
                u["owner"] = ""
                u["purchase_price"] = "0"
                u["purchase_time"] = ""
                u["protect_until"] = ""
                u["protector"] = ""
                if hasattr(st, "mark_dirty"):
                    st.mark_dirty(sec)
        save(gid)


__all__ = ["clear_user_slave", "handle", "init_slave", "COMMANDS"]


# 显式指令注册表（与 handle 分支逐字对应，增删指令两处同改；V8 起为唯一词表来源）
COMMANDS = (
    "我的信息", "查询", "买下", "折磨", "保护", "释放", "赎身",
    "买奴隶位", "购买奴隶位", "打架", "五十连抽", "50连抽",
    "三十连抽", "30连抽", "十连抽", "抽武器", "武器升星", "升星",
    "宝物升阶", "升阶", "我要造反", "造反", "讨好主人", "讨好",
    "我要学习", "学习", "我要祈福", "祈福",
    # V8 并入：原正则刮词域（与 handle/_ROUTE_EXACT 分支对应），路由前缀词回归显式表
    "排行榜", "奴隶打工", "我要打工", "奴隶收工", "搬砖",
    "武器菜单", "宝物菜单",
    "我要自由", "身价排行", "身价排行榜", "签到排行", "签到排行榜",
)
