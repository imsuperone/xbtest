# -*- coding: utf-8 -*-
"""games/slave/handler.py — 奴隶包·handler（原 slave.py 切分，语义不变）。"""
import os as _os
import re as _re
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
from .nick import clear_note_name, find_qq_by_name, mark_known
from .profile import cmd_menu, cmd_myinfo, cmd_query, cmd_rank, cmd_rank_price, cmd_rank_sign
from .social import cmd_flatter, cmd_pray, cmd_revolt, cmd_study, cmd_work_collect, cmd_work_dispatch
from .trade import cmd_buy_slave, cmd_buyslot, cmd_freedom, cmd_protect, cmd_ransom, cmd_release, cmd_torture
from .slave_state import _resolve_persistent_data_dir
def handle(gid, qq, raw):
    try:
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
# 注意：变量名刻意避开 _need/_ADMIN_CMDS/_ROUTE_EXACT，调用处用变量引用，
# 使指令采集器不收录（WebUI 指令页不再出现），行为保持全静默。

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
    mark_known(gid, qq)

    # @名字 兜底: 从 NOTE_NAMES / store._AT_NAMES / 本群已有档案(名片/昵称)反查 qq
    if not target:
        m = _re.search(r"@\s*([^@\s，,\r\n]+)", text)
        if m:
            nm = m.group(1).strip()
            clean_nm = _re.sub(r"[\[\]【】\(\)\s]", "", nm)
            # 1. 查本群分群昵称反向索引（精确 O(1)，模糊限本群）
            try:
                _t = find_qq_by_name(gid, nm)
            except Exception:
                _t = None
            if _t:
                target = str(_t)
                text = text.replace(m.group(0), "", 1).strip()
            # 1b. 查全局 NOTE_NAMES 兜底（dm/旧数据）
            if not target and _S.NOTE_NAMES:
                for _q, _n in _S.NOTE_NAMES.items():
                    clean_n = _re.sub(r"[\[\]【】\(\)\s]", "", str(_n or ""))
                    if clean_n and (clean_n == clean_nm or clean_nm in clean_n or clean_n in clean_nm):
                        target = str(_q)
                        text = text.replace(m.group(0), "", 1).strip()
                        break
            # 2. 查 store._AT_NAMES
            if not target and hasattr(store, "_AT_NAMES") and store._AT_NAMES:
                for _an, _aq in store._AT_NAMES.items():
                    clean_an = _re.sub(r"[\[\]【】\(\)\s]", "", str(_an or ""))
                    if clean_an and (clean_an == clean_nm or clean_nm in clean_an or clean_an in clean_nm):
                        target = str(_aq)
                        text = text.replace(m.group(0), "", 1).strip()
                        break
            # 3. 查群档案
            if not target:
                for _uid in st.users():
                    _unm = uget(U(st, _uid), "name")
                    clean_unm = _re.sub(r"[\[\]【】\(\)\s]", "", str(_unm or ""))
                    if clean_unm and (clean_unm == clean_nm or clean_nm in clean_unm or clean_unm in clean_nm):
                        target = str(_uid)
                        text = text.replace(m.group(0), "", 1).strip()
                        break
            if not target and store._AT_NAMES:
                store.register_names(_S.NOTE_NAMES)  # 确保索引最新
        # 兼容纯 QQ 号（无 @）的写法：文案仅 @QQ，但解析支持 QQ 号
        if not target:
            # 仅对需要目标的指令尝试提取，避免金额被误判
            _need = ("查询","买下","折磨","保护","释放","赎身","打架","购买奴隶位")
            for _pref in _need:
                if text.startswith(_pref):
                    m = _re.search(r"\b(\d{5,12})\b", text)
                    if m:
                        target = m.group(1)
                        text = text.replace(m.group(0), "", 1).strip()
                    break
            # 通用兜底：若仍无 target 且文本含 @QQ 之外的独立 QQ 号（如 买下 123），也尝试首个数字
            if not target:
                # 对于买下/查询等，即使前缀不完全匹配也尝试
                if any(kw in text for kw in ("买下","查询","保护","释放","赎身","打架")):
                    m = _re.search(r"\b(\d{5,12})\b", text)
                    if m:
                        target = m.group(1)
                        text = text.replace(m.group(0), "", 1).strip()

    # 去掉开头的表情码干扰
    text = _re.sub(r"\[(?:CQ|DR):[^\]]+\]", "", text).strip()

    # Fast path: exact commands
    if text in _ROUTE_EXACT:
        return _ROUTE_EXACT[text](gid, qq, target, st, text)

    if text in store.wake("奴隶系统", "奴隶系统"):
        return cmd_menu()
    if text == "我的信息" or text.startswith("我的信息"):
        # 支持 我的信息 @QQ / QQ 查询他人（兼容已提取的 target）
        t = target
        if not t and text.startswith("我的信息 "):
            # 兜底：从剩余文本再解析（纯数字或@）
            t2, _ = store.parse_at(text[len("我的信息 "):])
            if t2:
                t = t2
            else:
                import re as _re2
                m = _re2.search(r"(\d{5,12})", text)
                if m:
                    t = m.group(1)
        if t:
            return cmd_query(gid, qq, t, st)
        return cmd_myinfo(gid, qq, st)
    if text.startswith("查询"):
        # v0.7.29：9 个查询转发/放行全部退役，一律静默（空白无关，含全角/制表符）。
        # 此前查询更新/版本以 is_admin=True 越权转发超管（与全静默红线冲突），查询维护同理；
        # 查询菜单（无空格）/查询 地图（有空格）此前漏放行会误查用户，现一并静默，行为一致。
        if _re.sub(r"\s+", "", text).startswith(_QUERY_SILENT):
            return None
        # 查询 (不带参数) / 查询我 / 查询自己 -> 直接查看自己的档案
        rest = text[len("查询"):].strip()
        if not target and (not rest or rest in ("我", "自己", "个人", "我的信息", "自己信息", "个人信息")):
            return cmd_myinfo(gid, qq, st)

        # 查询@QQ / 查询 @名字 / 查询 QQ / 查询 名字 -> 查他人档案，兼容已提取的 target
        t = target
        if not t:
            t2, _ = store.parse_at(text)
            if t2:
                t = t2
            else:
                if rest.startswith("@"):
                    rest = rest[1:].strip()
                if rest:
                    m_num = _re.search(r"^(\d{5,12})$", rest)
                    if m_num:
                        t = m_num.group(1)
                    else:
                        clean_rest = _re.sub(r"[\[\]【】\(\)\s]", "", rest)
                        # 1. 查本群分群昵称反向索引（精确 O(1)，模糊限本群）
                        try:
                            _t2 = find_qq_by_name(gid, rest)
                        except Exception:
                            _t2 = None
                        if _t2:
                            t = str(_t2)
                        # 1b. 查全局 NOTE_NAMES 兜底
                        if not t:
                            for _q, _n in _S.NOTE_NAMES.items():
                                clean_n = _re.sub(r"[\[\]【】\(\)\s]", "", str(_n or ""))
                                if clean_n and (clean_n == clean_rest or clean_rest in clean_n or clean_n in clean_rest):
                                    t = str(_q)
                                    break
                        # 2. 查 store._AT_NAMES
                        if not t and hasattr(store, "_AT_NAMES") and store._AT_NAMES:
                            for _an, _aq in store._AT_NAMES.items():
                                clean_an = _re.sub(r"[\[\]【】\(\)\s]", "", str(_an or ""))
                                if clean_an and (clean_an == clean_rest or clean_rest in clean_an or clean_an in clean_rest):
                                    t = str(_aq)
                                    break
                        # 3. 查群档案
                        if not t:
                            for _uid in st.users():
                                _unm = uget(U(st, _uid), "name")
                                clean_unm = _re.sub(r"[\[\]【】\(\)\s]", "", str(_unm or ""))
                                if clean_unm and (clean_unm == clean_rest or clean_rest in clean_unm or clean_unm in clean_rest):
                                    t = str(_uid)
                                    break
        if t:
            return cmd_query(gid, qq, t, st)
        return "未能找到该成员～格式：【查询 @QQ】或【查询 昵称】"
    if text.startswith("买下"):
        return cmd_buy_slave(gid, qq, target, st)
    if text.startswith("折磨"):
        return cmd_torture(gid, qq, target, st)
    if text.startswith("保护"):
        return cmd_protect(gid, qq, target, st)
    if text.startswith("释放"):
        return cmd_release(gid, qq, target, st)
    if text.startswith("赎身"):
        return cmd_ransom(gid, qq, target, st)
    if text == "我要自由":
        return cmd_freedom(gid, qq, st)
    if text.startswith("买奴隶位") or text.startswith("购买奴隶位"):
        return cmd_buyslot(gid, qq, st)
    if text.startswith("打架"):
        return cmd_fight(gid, qq, target, st)
    if text.startswith("五十连抽") or text.startswith("50连抽"):
        return cmd_gacha(gid, qq, st, count=50)
    if text.startswith("三十连抽") or text.startswith("30连抽"):
        return cmd_gacha(gid, qq, st, count=30)
    if text.startswith("十连抽"):
        return cmd_gacha(gid, qq, st, count=10)
    if text.startswith("抽武器"):
        return cmd_gacha(gid, qq, st, count=1)
    if text.startswith("武器升星"):
        return cmd_starup(gid, qq, text[4:], st)
    if text.startswith("升星"):
        return cmd_starup(gid, qq, text[2:], st)
    if text.startswith("宝物升阶"):
        return cmd_treasure_up(gid, qq, text[4:], st)
    if text.startswith("升阶"):
        return cmd_treasure_up(gid, qq, text[2:], st)
    if text == "奴隶打工" or text == "我要打工":
        return cmd_work_dispatch(gid, qq, st)
    if text == "奴隶收工":
        return cmd_work_collect(gid, qq, st)
    if text == "我要造反" or text.startswith("造反"):
        return cmd_revolt(gid, qq, st)
    if text.startswith("讨好主人") or text == "讨好":
        return cmd_flatter(gid, qq, st)
    if text == "我要学习" or text.startswith("学习"):
        return cmd_study(gid, qq, st)
    if text == "我要祈福" or text.startswith("祈福"):
        return cmd_pray(gid, qq, st)
    if text == "武器菜单":
        return cmd_weapon_menu(gid, qq, st)
    if text == "宝物菜单":
        return cmd_treasure_menu(gid, qq, st)
    if text == "身价排行榜" or text == "身价排行":
        return cmd_rank_price(gid, st)
    if text == "签到排行榜" or text == "签到排行":
        return cmd_rank_sign(gid, st)
    if text == "排行榜":
        return cmd_rank(gid, st)

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
    # 预加载 gacha 池（千群并发下避免每消息 listdir 0.285s）
    try:
        for rar in ("SSR", "SR", "R"):
            _gacha_pool(rar)
    except Exception:
        pass
    # 兼容旧群档案: 若存在 ini 且 sqlite 仍为空, 尝试搬入
    try:
        _migrate_legacy_group_ini()
    except Exception:
        pass




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



# 使指令采集器不收录（WebUI 指令页不再出现），行为保持全静默。
_QUERY_SILENT = ("查询更新", "查询版本", "查询维护", "查询坐骑", "查询精灵", "查询帮派", "查询冒险", "查询地图", "查询菜单")
_ROUTE_EXACT = {
    "我的信息": lambda gid, qq, target, st, text: cmd_myinfo(gid, qq, st),
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
}


__all__ = ["clear_user_slave", "handle", "init_slave"]
