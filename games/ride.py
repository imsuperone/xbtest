# -*- coding: utf-8 -*-
"""坐骑系统 - 对齐 open.xb 原版指令/文案/数据
数据: RIDES(坐骑名->价格) 从 open.xb.app.dll [坐骑] 节提取
坐骑属性=坐骑(纯展示/欢迎用, v1 无战斗加成)
"""
import json
import os
import time

try:
    from ..core import storage as ST
except ImportError:
    try:
        from . import storage as ST
    except ImportError:
        from core import storage as ST

try:
    from .config.shop import RIDE_PRICES as RIDES, RIDE_SHOP as DEFAULT_RIDE_SHOP_EXT
except ImportError:
    from games.config.shop import RIDE_PRICES as RIDES, RIDE_SHOP as DEFAULT_RIDE_SHOP_EXT  # type: ignore
RIDE_TYPE = "坐骑"

_PLUGIN_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_IMG_BASE = os.path.join(_PLUGIN_BASE, "data", "games", "img", "rides")
_IMG_BASE_LEGACY = os.path.join(_PLUGIN_BASE, "data", "img", "rides")
_IMG_BASE_V2 = os.path.join(_PLUGIN_BASE, "data", "games", "ride", "img")
# 兼容 Linux 部署的多种数据目录布局 + 旧中文目录
_ALT_IMG_BASES = [
    _IMG_BASE,
    _IMG_BASE_LEGACY,
    _IMG_BASE_V2,
    os.path.join(_PLUGIN_BASE, "data", "img", "坐骑图标"),
    os.path.join(_PLUGIN_BASE, "data", "img", "gacha"),
    "/AstrBot/data/plugins/astrbot_plugin_xbbot_beta/data/img/rides",
    "/AstrBot/data/plugin_data/astrbot_plugin_xbbot_beta/data/img/rides",
    "/AstrBot/data/plugins/astrbot_plugin_xbbot_beta/data/img/坐骑图标",
    "/AstrBot/data/plugin_data/astrbot_plugin_xbbot_beta/data/img/坐骑图标",
]


def _alias_img_path(p):
    """旧路径别名：坐骑图标/gacha_img ↔ rides/img/gacha，双向兼容已存配置"""
    try:
        s = str(p or "")
        if not s:
            return []
        out = [s]
        pairs = (("坐骑图标", "rides"), ("rides", "坐骑图标"),
                 ("data/gacha_img", "data/img/gacha"), ("data\\gacha_img", "data\\img\\gacha"),
                 ("data/img/gacha", "data/gacha_img"), ("data\\img\\gacha", "data\\gacha_img"),
                 ("data/img/rides", "data/games/ride/img"), ("data\\img\\rides", "data\\games\\ride\\img"),
                 ("data/games/ride/img", "data/games/img/rides"), ("data\\games\\ride\\img", "data\\games\\img\\rides"),
                 ("data/games/img/rides", "data/games/ride/img"), ("data\\games\\img\\rides", "data\\games\\ride\\img"),
                 ("data/games/ride/img", "data/img/rides"), ("data\\games\\ride\\img", "data\\img\\rides"))
        for a, b in pairs:
            if a in s and b not in s:
                out.append(s.replace(a, b))
        seen = []
        for x in out:
            if x not in seen:
                seen.append(x)
        return seen
    except Exception:
        return [p]


def _mount_img(name):
    # 有效目录缓存命中即停；全 miss 时重扫一次（覆盖运行中新上传的目录），仍无走旧兜底
    for base in _valid_img_bases():
        hit = _probe_img_base(base, name)
        if hit:
            return hit
    for base in _refresh_img_bases():
        hit = _probe_img_base(base, name)
        if hit:
            return hit
    # 最后尝试主路径直接返回（交由 _build_chain 再校验）
    p = os.path.join(_IMG_BASE, str(name) + ".jpg")
    return [p] if os.path.exists(p) else []


_IMG_BASES_CACHE = None


def _valid_img_bases():
    """有效图片目录缓存：过滤不存在目录（/AstrBot 硬编码等多为 miss），命中即零扫描"""
    global _IMG_BASES_CACHE
    if _IMG_BASES_CACHE:
        return _IMG_BASES_CACHE
    out = []
    for base in _ALT_IMG_BASES:
        try:
            if base and os.path.isdir(base) and base not in out:
                out.append(base)
        except Exception:
            pass
    if not out:
        out = list(_ALT_IMG_BASES[:3])
    _IMG_BASES_CACHE = out
    return out


def _refresh_img_bases():
    global _IMG_BASES_CACHE
    _IMG_BASES_CACHE = None
    return _valid_img_bases()


def _probe_img_base(base, name):
    # 单目录单次 isfile 探测（原 isfile+pathlib 双查同义，合并省一半 syscall）
    # 优先检查主路径，兼容中文文件名编码与多布局
    try:
        p = os.path.join(base, str(name) + ".jpg")
        if os.path.isfile(p):
            return [p]
    except Exception:
        pass
    return []

MENU = (
    "🏍️ 坐骑管理\r\n"
    "━━━━━━━━━━━━━━\r\n"
    "🐴 我的坐骑　　🛒 坐骑商城\r\n"
    "💳 购买坐骑 名称　🔍 查看坐骑 名称\r\n"
    "🗑️ 丢弃坐骑 名称　🔄 切换坐骑 名称\r\n"
    "🎉 设置欢迎坐骑 名称\r\n"
    "👀 查看欢迎坐骑　🔁 回收欢迎坐骑 名称\r\n"
    "💠 携带精灵 名称（精灵当欢迎坐骑）\r\n"
    "━━━━━━━━━━━━━━\r\n"
    "💡 发送对应指令即可游玩"
)


def _cfg(key, default=""):
    return ST.cfg("坐骑配置", key, default)


def _u(gid, qq):
    return ST.acct(gid, qq)


def _rides(gid, qq):
    a = _u(gid, qq)
    try:
        return json.loads(a.get("rides", "{}") or "{}")
    except Exception:
        return {}


# 千群千人欢迎优化：内存集合快速过滤无欢迎群，避免每消息 DB 读
_WELCOME_GIDS = set()
_WELCOME_GIDS_LOCK = None
_WELCOME_INITIALIZED = False
try:
    import threading as _th_w
    _WELCOME_GIDS_LOCK = _th_w.RLock()
except Exception:
    pass

def _scan_welcome_gids():
    """启动时扫描含欢迎坐骑的群：LIKE 粗筛＋Python 精判。
    注意 rides 是双层编码（acct JSON 里套 JSON 字符串），带引号精确式
    LIKE '%"welcome"%' 永不命中（斜杠断开，已实证），曾致重启后欢迎全灭，只能靠重设恢复。"""
    found = set()
    try:
        if ST._DB is None:
            return found
        with ST._LOCK:
            rows = ST._DB.execute(
                "SELECT gid, data FROM accounts WHERE data LIKE '%welcome%'").fetchall()
        for g, d in rows or []:
            try:
                _j = json.loads(d or "{}")
                _r2 = json.loads(_j.get("rides", "{}") or "{}")
                if isinstance(_r2, dict) and _r2.get("welcome"):
                    found.add(str(g))
            except Exception:
                continue
    except Exception:
        pass
    return found


def _ensure_welcome_init():
    global _WELCOME_INITIALIZED
    if _WELCOME_INITIALIZED:
        return
    try:
        if _WELCOME_GIDS_LOCK:
            with _WELCOME_GIDS_LOCK:
                if not _WELCOME_INITIALIZED:
                    _WELCOME_GIDS.update(_scan_welcome_gids())
                    _WELCOME_INITIALIZED = True
        else:
            if not _WELCOME_INITIALIZED:
                _WELCOME_GIDS.update(_scan_welcome_gids())
                _WELCOME_INITIALIZED = True
    except Exception:
        pass

def _welcome_add(gid):
    try:
        if _WELCOME_GIDS_LOCK:
            with _WELCOME_GIDS_LOCK:
                _WELCOME_GIDS.add(str(gid))
        else:
            _WELCOME_GIDS.add(str(gid))
    except Exception:
        pass

def _welcome_remove(gid, qq):
    # 仅当该 qq 是该群最后一个欢迎用户时才移除 gid，需扫描同群其他用户；为保简单，仅在回收时按需扫描
    try:
        # 粗略：扫描同群是否还有其他 welcome，若无则移除
        if ST._DB is None:
            return
        with ST._LOCK:
            rows = ST._DB.execute("SELECT data FROM accounts WHERE gid=?", (int(gid),)).fetchall()
        has = False
        for (d,) in rows:
            try:
                j = json.loads(d or "{}")
                r2 = json.loads(j.get("rides", "{}") or "{}")
                if r2.get("welcome"):
                    has = True
                    break
            except Exception:
                continue
        if not has:
            if _WELCOME_GIDS_LOCK:
                with _WELCOME_GIDS_LOCK:
                    _WELCOME_GIDS.discard(str(gid))
            else:
                _WELCOME_GIDS.discard(str(gid))
    except Exception:
        pass


def _save(gid, qq, r):
    _u(gid, qq).set("rides", json.dumps(r, ensure_ascii=False))
    ST.acct_save(gid, qq)
    # 维护欢迎集合（中文文案不受影响，仅内存过滤）
    try:
        if r.get("welcome"):
            _welcome_add(gid)
        else:
            # welcome 被清空，检查同群是否还有其他 welcome
            _welcome_remove(gid, qq)
    except Exception:
        pass


def cmd_menu():
    return MENU


def cmd_my(gid, qq):
    r = _rides(gid, qq)
    lst = r.get("list", [])
    if not lst:
        return "亲，您还没有任何坐骑，发送【坐骑商城】去购买坐骑吧！\r\n发送【设置欢迎坐骑 名称】可设置欢迎坐骑！"
    lines = ["以下是您拥有的坐骑："]
    # 修复“没有骑为什么显示乘坐”：仅当 active 非空且与当前坐骑一致时才标记为当前乘坐
    # 且 active 必须在拥有的列表中，避免脏数据误显示；若 welcome 与 active 不一致，仅标“当前乘坐”不标欢迎
    active = (r.get("active") or "").strip() if isinstance(r.get("active"), str) else r.get("active")
    welcome = (r.get("welcome") or "").strip() if isinstance(r.get("welcome"), str) else r.get("welcome")
    for name in lst:
        is_active = bool(active) and name == active and name in lst
        # 严格模式：仅当 active==welcome==name 时才视为“乘坐中”；否则 active 单独时标“当前乘坐”
        # 为兼容旧数据，若 welcome 为空但 active 明确，仍标乘坐，避免全部不显示
        if is_active and (not welcome or name == welcome):
            mark = "【当前乘坐】"
        elif is_active:
            # welcome 与 active 不一致时，仍提示是乘坐但非欢迎坐骑，避免“没有骑却显示乘坐”误解
            mark = "【乘坐中】"
        else:
            mark = ""
        lines.append(f"{mark}{name}（{RIDE_TYPE}）")
    if r.get("welcome"):
        lines.append(f"当前欢迎坐骑：【{r['welcome']}】")
        # 若欢迎坐骑与当前乘坐不一致，额外提示当前乘坐
        if active and active != r.get("welcome") and active in lst:
            lines.append(f"当前乘坐坐骑：【{active}】")
    else:
        if active and active in lst:
            lines.append(f"当前乘坐坐骑：【{active}】")
            lines.append("发送【设置欢迎坐骑 名称】可设置欢迎坐骑！")
        else:
            lines.append("发送【设置欢迎坐骑 名称】可设置欢迎坐骑！")
    return "\r\n".join(lines)


def _parse_ride_shop(v):
    """ride_shop 配置体解析（dict/JSON串）→ {名: {price, img}} 规范形；非法/空回 {}。
    _ride_shop_raw 与 _ride_shop 唯一解析口（原两处内联逐行等价并入）"""
    out = {}
    try:
        d = v
        if isinstance(v, str) and v.strip():
            d = json.loads(v)
        if isinstance(d, dict):
            for k, val in d.items():
                if isinstance(val, dict):
                    out[str(k)] = {"price": int(float(val.get("price", 0) or 0)),
                                   "img": str(val.get("img", "") or "")}
                elif val is not None and str(val).strip() != "":
                    out[str(k)] = {"price": int(float(val)), "img": ""}
    except Exception:
        return {}
    return out


def _ride_shop_raw():
    """返回原始 ride_shop 配置对象(可能含 {price,img} 结构)，供取图用"""
    v = ST.cfg("商城图鉴", "ride_shop", "")
    if isinstance(v, dict) and v:
        return v
    if v:
        d = _parse_ride_shop(v)
        if d:
            # 保持原返回口径：dict 原样回（调用方只读 .get(name)/["img"]）
            try:
                raw = json.loads(v) if isinstance(v, str) else v
                if isinstance(raw, dict) and raw:
                    return raw
            except Exception:
                pass
            return d
    return DEFAULT_RIDE_SHOP_EXT

def _ride_shop():
    """坐骑商城数据: 优先 商城图鉴.ride_shop(JSON name->price 或 {price,img})；空=未自定义，回退 RIDES 内置"""
    v = ST.cfg("商城图鉴", "ride_shop", "")
    d = _parse_ride_shop(v) if v else {}
    if d:
        return {k: val["price"] for k, val in d.items()}
    out = {}
    for name in RIDES:
        out[name] = _mount_price(name)
    return out

def _ride_img_path(name):
    """取坐骑绑定图片路径(优先配置的 img，新旧目录双向兼容)，否则默认坐骑图标"""
    raw = _ride_shop_raw()
    if raw and isinstance(raw, dict):
        v = raw.get(name)
        if isinstance(v, dict) and v.get("img"):
            p = str(v.get("img")).strip()
            if p:
                cands = []
                if os.path.isabs(p):
                    cands.append(p)
                else:
                    # 相对插件 data 目录 + 旧路径别名
                    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                    for _ap in _alias_img_path(p):
                        cands.append(os.path.join(base, _ap))
                    cands.append(p)
                for cand in cands:
                    try:
                        if cand and os.path.isfile(cand):
                            return [cand]
                    except Exception:
                        continue
    return _mount_img(name)


def _mount_price(name):
    try:
        return int(float(_cfg("价格_" + name, RIDES.get(name, 0))))
    except Exception:
        return int(RIDES.get(name, 0))


def cmd_shop():
    lines = ["欢迎来到坐骑商城！", "━━━━━━━━━━━━━━"]
    for name, price in _ride_shop().items():
        lines.append(f"{name}　{price}{ST.coin_name()}")
    lines.append("发送【购买坐骑 名称】购买炫酷坐骑！\r\n发送【查看坐骑 名称】查看坐骑信息！")
    return "\r\n".join(lines)


def cmd_buy(gid, qq, name):
    if not name:
        return "亲，您的格式有误，购买坐骑格式为：【购买坐骑 名称】！"
    shop = _ride_shop()
    if name not in shop:
        return "亲，商城中不存在该坐骑，请发送【坐骑商城】查看商城中正在售卖的坐骑吧！"
    r = _rides(gid, qq)
    if name in r.get("list", []):
        return "亲，您已经拥有了该坐骑，无需再次购买，发送【我的坐骑】查看您当前所拥有的所有坐骑吧！"
    price = shop[name]
    if ST.coins_get(gid, qq) < price:
        return f"笑~你没有那么多{ST.coin_name()}（需要{price}）"
    r.setdefault("list", []).append(name)
    if not r.get("welcome"):
        r["welcome"] = name
        r["active"] = name
    if price > 0:
        if ST.txn_coins_acct(gid, qq, -price, {"rides": json.dumps(r, ensure_ascii=False)}, require_funds=True) is None:
            return "坐骑商城繁忙，购买未成功，请稍后重试！"
    else:
        _save(gid, qq, r)
    return (f"购买到炫酷的坐骑「{name}」！\r\n发送【我的坐骑】查看你拥有的坐骑！", _ride_img_path(name))


def cmd_view(gid, qq, name):
    if not name:
        return "亲，您的格式有误，查看坐骑信息格式为：【查看坐骑 名称】！"
    shop = _ride_shop()
    if name not in shop:
        return "亲，商城中不存在该坐骑！\r\n请发送【坐骑商城】查看商城正在售卖的坐骑吧！"
    owned = name in _rides(gid, qq).get("list", [])
    return (f"〈{name}〉\r\n属性：{RIDE_TYPE}\r\n价格：{shop[name]}{ST.coin_name()}\r\n"
            f"状态：{'已拥有' if owned else '未拥有（发送【购买坐骑 %s】购买）' % name}", _ride_img_path(name))


def cmd_discard(gid, qq, name):
    if not name:
        return "亲，您的格式有误，丢弃坐骑格式为：【丢弃坐骑 名称】！"
    r = _rides(gid, qq)
    if name not in r.get("list", []):
        return "亲，您并没有该坐骑，无需丢弃！"
    if r.get("welcome") == name:
        return "亲，该坐骑为欢迎坐骑，请先回收该坐骑再进行丢弃，回收格式为：【回收欢迎坐骑 名称】！"
    r["list"] = [x for x in r.get("list", []) if x != name]
    if r.get("active") == name:
        r["active"] = r.get("list", [""])[0] if r.get("list") else ""
    _save(gid, qq, r)
    return f"已丢弃坐骑「{name}」！"


def cmd_set_welcome(gid, qq, name):
    if not name:
        return "亲，您的格式有误，设置欢迎坐骑格式为：【设置欢迎坐骑 名称】！"
    r = _rides(gid, qq)
    if name not in r.get("list", []):
        return "亲，您没有该坐骑，发送【我的坐骑】看看吧！"
    r["welcome"] = name
    _save(gid, qq, r)
    return f"恭喜您将欢迎坐骑设置为「{name}」！\r\n发送【查看欢迎坐骑】查看当前欢迎坐骑！"


def cmd_switch(gid, qq, name):
    if not name:
        return "亲，您的格式有误，切换坐骑格式为：【切换坐骑 名称】！"
    r = _rides(gid, qq)
    if name not in r.get("list", []):
        return "亲，您没有该坐骑，发送【我的坐骑】看看吧！"
    r["active"] = name
    _save(gid, qq, r)
    return f"已切换乘坐坐骑为「{name}」！"


def cmd_view_welcome(gid, qq):
    r = _rides(gid, qq)
    w = r.get("welcome")
    if not w:
        return "亲，您还没有设置欢迎坐骑！\r\n发送【携带精灵 名称】可将您的其他精灵设置为欢迎坐骑！"
    return (f"您当前欢迎坐骑为：「{w}」\r\n"
            "发送【设置欢迎坐骑 名称】可更换当前欢迎坐骑！")


def cmd_recycle_welcome(gid, qq, name):
    r = _rides(gid, qq)
    w = name or r.get("welcome", "")
    if not r.get("welcome"):
        return "亲，您并没有设置欢迎坐骑，无需回收！\r\n发送【设置欢迎坐骑 名称】或【携带精灵 名称】可设置欢迎坐骑！"
    if w and r.get("welcome") != w:
        return f"亲，该坐骑不是当前的欢迎坐骑，无法回收！当前欢迎坐骑为：【{r['welcome']}】"
    r["welcome"] = ""
    _save(gid, qq, r)
    ST.recall_set(f"ride_welcome_{gid}_{qq}", "")
    return "已回收欢迎坐骑！后续将不再触发进群欢迎，如需重新启用，请发送【设置欢迎坐骑 名称】重新设置！"


def check_welcome(gid, qq):
    """欢迎坐骑触发: 用户 3 小时内第一次出现(发消息)时, 若设置了欢迎坐骑则推送一次。
    返回 (文本, [图片]) 或 None。由 main._dispatch 在收到群消息时调用。欢迎文案带群昵称、坐骑图片及微量金币奖励（坐骑价值/5000）。
    维护期直接 None（与 router/_dispatch 维护门同语义，直调也不漏）。"""
    try:
        if ST.cfg("维护配置", "维护开关", "假") == "真":
            return None
        if str(gid).isdigit() and ST.recall_get("group_maint_%s" % gid, "0") == "1":
            return None
    except Exception:
        pass
    try:
        # 快速过滤：该群从未设置过欢迎，直接返回，避免每消息一次 acct DB 读（千群千人关键）
        try:
            _ensure_welcome_init()
            if _WELCOME_GIDS is not None and str(gid) not in _WELCOME_GIDS:
                return None
        except Exception:
            pass
        r = _rides(gid, qq)
        w = r.get("welcome")
        if not w:
            return None
        key = f"ride_welcome_{gid}_{qq}"
        try:
            last = ST.recall_get(key, "")
        except Exception:
            last = ""
        now = int(time.time())
        try:
            _last_ts = int(last or "0")
        except Exception:
            _last_ts = 0
        if last and now - _last_ts < 3 * 3600:
            return None
        ST.recall_set(key, str(now))
        # 群昵称优先（本群分群昵称，防跨群串扰）
        disp = str(qq)
        try:
            from . import slave as SL
            try:
                disp = SL.get_note_name(gid, str(qq)) or SL.fetch_card(gid, str(qq)) or str(qq)
            except Exception:
                disp = SL.NOTE_NAMES.get(str(qq), str(qq)) or str(qq)
            # 若为 QQ 本身，尝试档案 name
            if disp == str(qq):
                try:
                    st = SL.state(str(gid))
                    if st.has_section(str(qq)):
                        nm = st[str(qq)].get("name", "")
                        if nm:
                            disp = nm
                except Exception:
                    pass
        except Exception:
            try:
                import slave as SL2
                try:
                    disp = SL2.get_note_name(gid, str(qq)) or SL2.fetch_card(gid, str(qq)) or str(qq)
                except Exception:
                    disp = SL2.NOTE_NAMES.get(str(qq), str(qq)) or str(qq)
            except Exception:
                pass
        # 微量金币奖励：坐骑价值/5000（最低 10，最高 500）
        reward = 0
        try:
            shop = _ride_shop()
            price = int(shop.get(w, 0) or 0)
            reward = max(10, min(500, price // 5000)) if price else 20
            if reward:
                # 欢迎奖励增发：失败不展示奖励文案（禁冒领成功）
                if ST.coins_add(str(gid), str(qq), reward) is None:
                    reward = 0
        except Exception:
            reward = 0
        extra = f" 获得 {reward}{ST.coin_name()}奖励！" if reward else ""
        txt = f"【{disp}】骑着【{w}】来啦！欢迎再次出现！{extra}"
        return txt, _ride_img_path(w)
    except Exception:
        return None


def cmd_ride_spirit(gid, qq, name):
    """携带精灵: 把精灵设为欢迎坐骑(需拥有该精灵)"""
    if not name:
        return "亲，您的格式有误，携带精灵格式为：【携带精灵 名称】！"
    a = _u(gid, qq)
    try:
        sp = json.loads(a.get("spirits", "{}") or "{}")
        own = any((it.get("name") == name) for it in sp.get("list", []))
    except Exception:
        own = False
    if not own:
        return "亲，您没有该精灵，无法携带！"
    r = _rides(gid, qq)
    r["welcome"] = name
    _save(gid, qq, r)
    return f"已将精灵「{name}」设置为欢迎坐骑！"


# ---- 统一入口 ----
def handle(gid, qq, raw):
    text = (raw or "").strip()
    if not text:
        return None
    if text in ST.wake("坐骑系统", "坐骑系统"):
        return cmd_menu()
    if _cfg("开关", "真") != "真" and text not in ST.wake("坐骑系统", "坐骑系统"):
        return "【坐骑管理】已经被关闭了，无法使用该功能！\r\n如需开启，请机器人管理发送【坐骑开关】进行开启！"
    if text == "我的坐骑":
        return cmd_my(gid, qq)
    if text == "坐骑商城":
        return cmd_shop()
    if text == "查看欢迎坐骑":
        return cmd_view_welcome(gid, qq)
    if text.startswith("购买坐骑"):
        return cmd_buy(gid, qq, text[4:].strip())
    if text.startswith("查看坐骑"):
        return cmd_view(gid, qq, text[4:].strip())
    if text.startswith("丢弃坐骑"):
        return cmd_discard(gid, qq, text[4:].strip())
    if text.startswith("设置欢迎坐骑"):
        return cmd_set_welcome(gid, qq, text[6:].strip())
    if text.startswith("切换坐骑"):
        return cmd_switch(gid, qq, text[4:].strip())
    if text.startswith("回收欢迎坐骑"):
        return cmd_recycle_welcome(gid, qq, text[6:].strip())
    if text.startswith("携带精灵"):
        return cmd_ride_spirit(gid, qq, text[4:].strip())
    return None
