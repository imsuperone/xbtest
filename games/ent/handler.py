# -*- coding: utf-8 -*-
"""games/ent·route（原 ent.py 切分，语义不变）。"""
import random
import re
import time
try:
    from ... import storage as ST
except ImportError:
    import storage as ST
from .content import *  # noqa
from .session import *  # noqa

# 指令前缀表（_play 作答时避让其他系统指令；有序去重，any-startswith 语义不变；提至模块级，每消息省一次建元组）
_CMD_PREFIXES = ('领养', '领取', '精灵', '坐骑', '帮派', 'adventure', '签到', '转账', 'deposit', '取款', '购买', '抽奖', '抽签', '扔炸弹', '猜拳', '开始', '加入', '退出', '我的', '查询', '打赏', '买下', '释放', '保护', '打架', '讨好', '学习', '祈福', '造反', '打工', '收工', '禁言', '踢人', '扣钱', '充钱', '群列表', '应用统计', '财富榜', '排行榜', '切换', '查看', '丢弃', '设置', '回收', '携带', '进化', '对战', '排行', '你好', '在吗', '谢谢', '晚安', '创建', '成员', '贡献', 'weapon', '修筑', '福利', '发起', '管理', '解散', '邀请', '同意', '接受', '当前', '选择', '复活', '背包', '商城', '地图', '出战', '银行', '奴隶', '超管', '娱乐', '私聊', '系统', '榜', '接龙', '急转弯', '字谜', '猜数', '答题', '二四点', '打劫', '赌博', '红包', '更新', '检查更新', '小白更新', '查询更新', '检查版本', '小白升级', '版本', '小白版本', 'xb版本', '插件版本', '清空', '重置', '备份', '维护', '菜单', '帮助')


def handle(gid, qq, raw):
    text = (raw or "").strip()
    if not text:
        return None
    # 自动检查并清理群内闲置超时或异常遗留的游戏锁
    _clean_expired_game(gid)
    if text in ST.wake("娱乐系统", "娱乐系统"):
        return _MENU
    if text.startswith("抽签"):
        _e = _fee(gid, qq, "抽签")
        if _e:
            return _e
        # 每日一次
        a = ST.acct(gid, qq)
        today = ST.recall_get(f"chouqian_{gid}_{qq}", "")
        cur_day = time.strftime("%Y-%m-%d")
        if today == cur_day:
            return "今日已抽过签，明日再来试试手气吧～"
        ST.recall_set(f"chouqian_{gid}_{qq}", cur_day)
        n = random.randint(1, 100)
        if n <= 15:
            r = "大吉"
            reward = ST.cfgi("娱乐配置", "抽签大吉奖励", 888)
            ST.coins_add(gid, qq, reward)
            ST.acct_add(gid, qq, "charm", 2)
            return f"你抽到了【{r}】🎉 今日运势极佳！奖励{reward}{ST.coin_name()} 魅力+2，好好把握哦～"
        elif n <= 40:
            r = "上签"
            reward = ST.cfgi("娱乐配置", "抽签上签奖励", 388)
            ST.coins_add(gid, qq, reward)
            ST.acct_add(gid, qq, "charm", 1)
            return f"你抽到了【{r}】✨ 运势不错！奖励{reward}{ST.coin_name()} 魅力+1"
        elif n <= 70:
            r = "中签"
            reward = ST.cfgi("娱乐配置", "抽签中签奖励", 88)
            if reward:
                ST.coins_add(gid, qq, reward)
            return f"你抽到了【{r}】 平稳之签，奖励{reward}{ST.coin_name()}，继续加油～"
        else:
            r = "下签"
            return f"你抽到了【{r}】 别灰心，这个只是娱乐，没事的～保持好心情，坏运气很快就会过去的！"
    if text.startswith("扔炸弹"):
        return cmd_bomb(gid, qq, text[3:].strip())
    # ---- 会话类游戏 ----
    if text.startswith("开始接龙"):
        chk = _check_single_game(gid, "接龙", sender_qq=qq)
        if chk:
            return chk
        err = _ent_cost(gid, qq, "接龙")
        if err:
            return err
        first = random.choice(_get_chain_words())
        ST.recall_set(f"chain_owner_{gid}", str(qq))
        ST.recall_set(f"chain_{gid}", first)
        ST.recall_set(f"chain_start_{gid}", str(int(time.time())))
        ST.recall_set(f"chain_players_{gid}", "")
        ST.recall_set(f"chain_used_{gid}", first)
        ST.recall_set(f"chain_last_qq_{gid}", "")
        ST.recall_set(f"chain_last_time_{gid}", "0")
        _set_active_game(gid, "接龙")
        return (f"🧩 接龙开始！机器人先出词：【{first}】\r\n"
                f"请用尾字「{first[-1]}」接龙（词语2-6字）！\r\n"
                "其他玩家请在 30 秒内发送【加入接龙】加入！发送【退出接龙】结束。")
    if text in ("加入接龙", "我加入接龙"):
        _clean_expired_game(gid)
        cur = _active_game(gid)
        if cur != "接龙":
            return "当前群没有进行中的接龙游戏，发送【开始接龙】开启一局吧~"
        owner = ST.recall_get(f"chain_owner_{gid}")
        last_word = ST.recall_get(f"chain_{gid}", "")
        if not owner or not last_word:
            _clean_expired_game(gid, max_seconds=0)
            return "当前群没有进行中的接龙游戏，发送【开始接龙】开启一局吧~"
        start = ST.recall_get(f"chain_start_{gid}", "0")
        last_time = int(ST.recall_get(f"chain_last_time_{gid}", "0") or 0)
        try:
            start_ts = int(start or "0")
            effective_ts = max(start_ts, last_time)
            if effective_ts <= 0 or (int(time.time()) - effective_ts) > 30:
                _clean_expired_game(gid, max_seconds=0)
                return "当前接龙已超过30秒无人互动自动结束，发送【开始接龙】开启新的一局吧~"
        except Exception:
            pass
        if str(owner) == str(qq):
            return f"您是本局开局者，无需加入！当前词语为【{last_word}】，请用尾字「{last_word[-1]}」接龙~"
        players = _get_players(gid, "chain_players_")
        if str(qq) in players:
            return f"您已加入本局接龙，请直接接龙！当前词语为【{last_word}】，尾字「{last_word[-1]}」~"
        players.append(str(qq))
        ST.recall_set(f"chain_players_{gid}", ",".join(players))
        return f"你已加入接龙！当前词语为【{last_word}】，请用尾字「{last_word[-1]}」接龙（词语2-6字）~"
    if text in ("当前接龙", "查接龙", "接龙进度", "接龙词"):
        cur = _active_game(gid)
        if cur != "接龙":
            return "当前群没有进行中的接龙游戏，发送【开始接龙】开启一局吧~"
        start = ST.recall_get(f"chain_start_{gid}", "0")
        last_time = int(ST.recall_get(f"chain_last_time_{gid}", "0") or 0)
        try:
            start_ts = int(start or "0")
            effective_ts = max(start_ts, last_time)
            if effective_ts <= 0 or (int(time.time()) - effective_ts) > 30:
                _clean_expired_game(gid, max_seconds=0)
                return "当前群没有进行中的接龙游戏，发送【开始接龙】开启一局吧~"
        except Exception:
            pass
        last_word = ST.recall_get(f"chain_{gid}", "")
        if not last_word:
            return "当前群没有进行中的接龙游戏，发送【开始接龙】开启一局吧~"
        return f"当前接龙词语为【{last_word}】，请用尾字「{last_word[-1]}」接龙（词语2-6字）~"
    if text in ("结束接龙", "重置接龙", "退出接龙"):
        owner = ST.recall_get(f"chain_owner_{gid}")
        if not owner:
            _clear_active_game(gid)
            return "当前没有进行中的接龙游戏！"
        if text in ("结束接龙", "重置接龙") or str(owner) == str(qq):
            ST.recall_set(f"chain_owner_{gid}", "")
            ST.recall_set(f"chain_{gid}", "")
            ST.recall_set(f"chain_start_{gid}", "")
            ST.recall_set(f"chain_players_{gid}", "")
            ST.recall_set(f"chain_used_{gid}", "")
            ST.recall_set(f"chain_last_qq_{gid}", "")
            ST.recall_set(f"chain_last_time_{gid}", "")
            _clear_active_game(gid)
            return "接龙已结束并清理！随时发送【开始接龙】开启新局~"
        else:
            players = _get_players(gid, "chain_players_")
            if str(qq) in players:
                players.remove(str(qq))
                ST.recall_set(f"chain_players_{gid}", ",".join(players))
            return "你已退出接龙！"
    if text.startswith("开始急转弯"):
        chk = _check_single_game(gid, "急转弯", sender_qq=qq)
        if chk:
            return chk
        err = _ent_cost(gid, qq, "急转弯")
        if err:
            return err
        q, a = random.choice(_get_trick())
        ST.recall_set(f"trick_{gid}_{qq}", a)
        ST.recall_set(f"trick_owner_{gid}", str(qq))
        ST.recall_set(f"trick_start_{gid}", str(int(time.time())))
        ST.recall_set(f"trick_last_time_{gid}", str(int(time.time())))
        ST.recall_set(f"trick_players_{gid}", "")
        _set_active_game(gid, "急转弯")
        return "🤔 急转弯：" + q + "\r\n回复你的答案！（其他玩家30秒内发送【加入急转弯】加入）"
    if text.startswith("开始猜字谜"):
        chk = _check_single_game(gid, "猜字谜", sender_qq=qq)
        if chk:
            return chk
        err = _ent_cost(gid, qq, "猜字谜")
        if err:
            return err
        q, a = random.choice(_get_miri())
        ST.recall_set(f"miri_{gid}_{qq}", a)
        ST.recall_set(f"miri_owner_{gid}", str(qq))
        ST.recall_set(f"miri_start_{gid}", str(int(time.time())))
        ST.recall_set(f"miri_last_time_{gid}", str(int(time.time())))
        ST.recall_set(f"miri_players_{gid}", "")
        _set_active_game(gid, "猜字谜")
        return "🔤 字谜：" + q + "\r\n回复你的答案！（其他玩家30秒内发送【加入字谜】加入）"
    if text.startswith("开始猜数"):
        chk = _check_single_game(gid, "猜数", sender_qq=qq)
        if chk:
            return chk
        err = _ent_cost(gid, qq, "猜数")
        if err:
            return err
        n = random.randint(1, 100)
        ST.recall_set(f"guessnum_{gid}_{qq}", str(n))
        ST.recall_set(f"guessnum_owner_{gid}", str(qq))
        ST.recall_set(f"guessnum_start_{gid}", str(int(time.time())))
        ST.recall_set(f"guessnum_last_time_{gid}", str(int(time.time())))
        ST.recall_set(f"guessnum_players_{gid}", "")
        _set_active_game(gid, "猜数")
        return ("🎲 猜数开始！我心中想了一个 1-100 之间的数字，\r\n"
                "请你回复一个数字来猜，我会提示大了/小了！\r\n"
                "（其他玩家30秒内发送【加入猜数】加入，发送【退出猜数】结束）")
    if text.startswith("开始答题"):
        chk = _check_single_game(gid, "答题", sender_qq=qq)
        if chk:
            return chk
        err = _ent_cost(gid, qq, "答题")
        if err:
            return err
        q, a = random.choice(_get_quiz())
        ST.recall_set(f"quiz_{gid}_{qq}", a)
        ST.recall_set(f"quiz_owner_{gid}", str(qq))
        ST.recall_set(f"quiz_start_{gid}", str(int(time.time())))
        ST.recall_set(f"quiz_last_time_{gid}", str(int(time.time())))
        ST.recall_set(f"quiz_players_{gid}", "")
        _set_active_game(gid, "答题")
        return "❓ 答题开始！" + q + "\r\n回复你的答案！（其他玩家30秒内发送【加入答题】加入）"
    if text == "加入猜数":
        return _join_game(gid, qq, "guessnum", "猜数")
    if text == "加入答题":
        return _join_game(gid, qq, "quiz", "答题")
    if text == "加入字谜" or text == "加入猜字谜":
        return _join_game(gid, qq, "miri", "字谜")
    if text == "加入急转弯":
        return _join_game(gid, qq, "trick", "急转弯")
    if text == "加入二四点":
        return _join_game(gid, qq, "game24", "二四点")
    if text.startswith("退出猜数"):
        res = _quit_game(gid, qq, "guessnum", "猜数")
        # _quit_game 已清 owner 相关，若是开局者退出则清锁
        owner = ST.recall_get(f"guessnum_owner_{gid}")
        if not owner:
            _clear_active_game(gid)
        return res
    if text == "退出答题":
        res = _quit_game(gid, qq, "quiz", "答题")
        if not ST.recall_get(f"quiz_owner_{gid}"):
            _clear_active_game(gid)
        return res
    if text == "退出字谜" or text == "退出猜字谜":
        res = _quit_game(gid, qq, "miri", "字谜")
        if not ST.recall_get(f"miri_owner_{gid}"):
            _clear_active_game(gid)
        return res
    if text == "退出急转弯":
        res = _quit_game(gid, qq, "trick", "急转弯")
        if not ST.recall_get(f"trick_owner_{gid}"):
            _clear_active_game(gid)
        return res
    if text == "退出二四点":
        # 兼容旧单人键与新群组键
        owner = ST.recall_get(f"game24_owner_{gid}")
        if owner and str(owner) == str(qq):
            ST.recall_set(f"game24_owner_{gid}", "")
            ST.recall_set(f"game24_players_{gid}", "")
            ST.recall_set(f"game24_start_{gid}", "")
            ST.recall_set(f"game24_{gid}_{owner}", "")
            _clear_active_game(gid)
        else:
            # 参与者退出
            players = _get_players(gid, "game24_players_")
            if str(qq) in players:
                players.remove(str(qq))
                ST.recall_set(f"game24_players_{gid}", ",".join(players))
            ST.recall_set(f"game24_{gid}_{qq}", "")
            # 若此时无owner或参与者为空但owner仍在，不清锁
            if not ST.recall_get(f"game24_owner_{gid}"):
                _clear_active_game(gid)
        return "已退出二四点！"
    if text.startswith("开始二四点"):
        chk = _check_single_game(gid, "二四点", sender_qq=qq)
        if chk:
            return chk
        return _start_24(gid, qq)
    if text.startswith("二四点"):
        chk = _check_single_game(gid, "二四点", sender_qq=qq)
        if chk:
            return chk
        return _start_24(gid, qq)
    if text.startswith("猜拳"):
        m = re.search(r"猜拳\s*(石头|剪刀|布)", text)
        if not m:
            return "请输入：猜拳 石头/剪刀/布"
        err = _ent_cost(gid, qq, "猜拳")
        if err:
            return err
        choice = {"石头": 0, "剪刀": 1, "布": 2}[m.group(1)]
        names = ["石头", "剪刀", "布"]
        # 胜率走配置 猜拳成功概率%（需求19 默认50）
        win_prob = ST.cfgi("娱乐配置", "猜拳成功概率", 50)
        r = random.random() * 100
        if r < win_prob:
            ai = (choice + 2) % 3  # 必输给玩家
            res = f"我出{names[ai]}！你赢了！"
            coin = ST.cfgi("娱乐配置", "猜拳奖励金币", 58)
            meili = ST.cfgi("娱乐配置", "猜拳奖励魅力", 1)
            if coin:
                ST.coins_add(gid, qq, coin)
            if meili:
                ST.acct_add(gid, qq, "charm", meili)
            if coin or meili:
                res += f" 奖励{coin}{ST.coin_name()}" + (f" 魅力+{meili}" if meili else "")
            return res
        elif r < win_prob + 20:
            ai = choice
            return f"我出{names[ai]}！平局！"
        else:
            ai = (choice + 1) % 3
            return f"我出{names[ai]}！我赢了~"
    # 会话作答
    r = _play(gid, qq, text)
    if r:
        return r
    return None




def _play(gid, qq, text):
    try:
        from ... import storage as S
    except Exception:
        import storage as S
    # 奖励 helper
    def _reward(gid, qq, coin=0, meili=0):
        if coin:
            try: S.coins_add(gid, qq, int(coin))
            except Exception: pass
        if meili:
            try: S.acct_add(gid, qq, "charm", int(meili))
            except Exception: pass
    # 若文本明显是其他系统的指令，则不拦截为答题答案，避免吞掉（需求14/15）
    def _is_cmd(txt):
        t = txt.strip()
        for p in _CMD_PREFIXES:
            if t.startswith(p):
                return True
        return False

    cur = _active_game(gid)
    if not cur:
        # 无活跃娱乐游戏，立即放行，零数据库查询
        return None

    # quiz/字谜/急转弯 分别按游戏独立会话(题面存开局者 key, 参与者均可作答)
    # 需求14/15：中途不提醒未加入者（非参与者直接静默放行）；参与者发其他指令时放行
    # label -> 配置前缀映射（字谜 实际为 猜字谜）
    _LABEL_CFG = {"答题": "答题", "字谜": "猜字谜", "急转弯": "急转弯"}
    if cur in ("答题", "字谜", "猜字谜", "急转弯"):
        for kind, label in (("quiz", "答题"), ("miri", "字谜"), ("trick", "急转弯")):
            owner = S.recall_get(f"{kind}_owner_{gid}")
            if not owner:
                continue
            try:
                start_val = S.recall_get(f"{kind}_start_{gid}", "0")
                start_ts = int(start_val or "0")
                try:
                    _lt = int(S.recall_get(f"{kind}_last_time_{gid}", "0") or 0)
                except Exception:
                    _lt = 0
                effective_ts = max(start_ts, _lt)
                if effective_ts <= 0 or (int(time.time()) - effective_ts) > 30:
                    S.recall_set(f"{kind}_{gid}_{owner}", "")
                    S.recall_set(f"{kind}_owner_{gid}", "")
                    S.recall_set(f"{kind}_players_{gid}", "")
                    S.recall_set(f"{kind}_start_{gid}", "")
                    S.recall_set(f"{kind}_last_time_{gid}", "")
                    S.recall_set(f"ent_game_{gid}", "")
                    continue
            except Exception:
                pass
            if not _is_player(gid, qq, kind):
                continue
            try:
                S.recall_set(f"{kind}_last_time_{gid}", str(int(time.time())))
            except Exception:
                pass
            ans = S.recall_get(f"{kind}_{gid}_{owner}")
            if not ans:
                continue
            if _is_cmd(text):
                continue
            if text.strip() == ans:
                S.recall_set(f"{kind}_{gid}_{owner}", "")
                S.recall_set(f"{kind}_owner_{gid}", "")
                S.recall_set(f"{kind}_players_{gid}", "")
                S.recall_set(f"{kind}_start_{gid}", "")
                S.recall_set(f"{kind}_last_time_{gid}", "")
                S.recall_set(f"ent_game_{gid}", "")
                # 奖励（全量可配，默认值保持旧行为）
                cfg_prefix = _LABEL_CFG.get(label, label)
                coin = S.cfgi("娱乐配置", f"{cfg_prefix}奖励金币", 88 if label!="答题" else 128)
                meili = S.cfgi("娱乐配置", f"{cfg_prefix}奖励魅力", 1)
                _reward(gid, qq, coin, meili)
                return f"恭喜！【{label}】答案正确：{ans} 奖励{coin}{S.coin_name()} 魅力+{meili}"
            return f"答案不对，再想想~（发送【退出{label}】结束）"
    # 猜数(题面存开局者 key, 参与者均可作答)
    elif cur == "猜数":
        owner = S.recall_get(f"guessnum_owner_{gid}")
        if owner:
            try:
                start_val = S.recall_get(f"guessnum_start_{gid}", "0")
                start_ts = int(start_val or "0")
                try:
                    _lt = int(S.recall_get(f"guessnum_last_time_{gid}", "0") or 0)
                except Exception:
                    _lt = 0
                effective_ts = max(start_ts, _lt)
                if effective_ts <= 0 or (int(time.time()) - effective_ts) > 30:
                    S.recall_set(f"guessnum_{gid}_{owner}", "")
                    S.recall_set(f"guessnum_owner_{gid}", "")
                    S.recall_set(f"guessnum_players_{gid}", "")
                    S.recall_set(f"guessnum_start_{gid}", "")
                    S.recall_set(f"guessnum_last_time_{gid}", "")
                    S.recall_set(f"ent_game_{gid}", "")
                    owner = None
            except Exception:
                pass
        if owner and _is_player(gid, qq, "guessnum"):
            try:
                S.recall_set(f"guessnum_last_time_{gid}", str(int(time.time())))
            except Exception:
                pass
            g = S.recall_get(f"guessnum_{gid}_{owner}")
            if g and text.strip().isdigit():
                v = int(text.strip())
                n = int(g)
                if v == n:
                    S.recall_set(f"guessnum_{gid}_{owner}", "")
                    S.recall_set(f"guessnum_owner_{gid}", "")
                    S.recall_set(f"guessnum_players_{gid}", "")
                    S.recall_set(f"guessnum_start_{gid}", "")
                    S.recall_set(f"guessnum_last_time_{gid}", "")
                    S.recall_set(f"ent_game_{gid}", "")
                    coin = S.cfgi("娱乐配置", "猜数奖励金币", 188)
                    meili = S.cfgi("娱乐配置", "猜数奖励魅力", 2)
                    _reward(gid, qq, coin, meili)
                    return f"🎉 猜中啦！答案是 {n}！奖励{coin}{S.coin_name()} 魅力+{meili}"
                return "📉 小了，再猜！" if v < n else "📈 大了，再猜！"
    # 二四点（群组共享，可加入，30秒内）
    elif cur == "二四点":
        owner = S.recall_get(f"game24_owner_{gid}")
        if owner:
            try:
                start_val = S.recall_get(f"game24_start_{gid}", "0")
                start_ts = int(start_val or "0")
                try:
                    _lt = int(S.recall_get(f"game24_last_time_{gid}", "0") or 0)
                except Exception:
                    _lt = 0
                effective_ts = max(start_ts, _lt)
                if effective_ts <= 0 or (int(time.time()) - effective_ts) > 30:
                    S.recall_set(f"game24_{gid}_{owner}", "")
                    S.recall_set(f"game24_owner_{gid}", "")
                    S.recall_set(f"game24_players_{gid}", "")
                    S.recall_set(f"game24_start_{gid}", "")
                    S.recall_set(f"game24_last_time_{gid}", "")
                    S.recall_set(f"ent_game_{gid}", "")
                    owner = None
            except Exception:
                pass
        if owner:
            # 非参与者：只有发送本次题目数字时才提醒，否则静默（需求18）
            if not _is_player(gid, qq, "game24"):
                gtmp = S.recall_get(f"game24_{gid}_{owner}", "")
                if gtmp and re.search(r"\d", text):
                    nums_tmp = [int(x) for x in gtmp.split("|") if x != ""]
                    used_tmp = [int(x) for x in re.findall(r"\d+", text) if x.isdigit()]
                    if any(u in nums_tmp for u in used_tmp):
                        return "您不是本局参与者，无法参与二四点！发送【加入二四点】加入吧~"
                # 非数字/非相关数字则放行
                pass
            else:
                try:
                    S.recall_set(f"game24_last_time_{gid}", str(int(time.time())))
                except Exception:
                    pass
                g = S.recall_get(f"game24_{gid}_{owner}", "")
                # 兼容旧单人键
                if not g:
                    g = S.recall_get(f"game24_{gid}_{qq}", "")
                if g and re.search(r"[\+\-\*/()×÷]", text):
                    nums = [int(x) for x in g.split("|") if x != ""]
                    t = text.strip().replace("×", "*").replace("÷", "/").replace("（", "(").replace("）", ")")
                    try:
                        used = [int(x) for x in re.findall(r"\d+", t)]
                        if sorted(used) == sorted(nums):
                            val = _safe_eval_24(t)
                            if val is None:
                                return "算式有误，请检查（只用 %s 和 +-*/ 括号）：%s" % (" ".join(map(str, nums)), t)
                            if abs(val - 24) < 1e-6:
                                S.recall_set(f"game24_{gid}_{owner}", "")
                                S.recall_set(f"game24_{gid}_{qq}", "")
                                S.recall_set(f"game24_owner_{gid}", "")
                                S.recall_set(f"game24_players_{gid}", "")
                                S.recall_set(f"game24_start_{gid}", "")
                                S.recall_set(f"game24_last_time_{gid}", "")
                                S.recall_set(f"ent_game_{gid}", "")
                                coin = S.cfgi("娱乐配置", "二四点奖励金币", 128)
                                meili = S.cfgi("娱乐配置", "二四点奖励魅力", 1)
                                _reward(gid, qq, coin, meili)
                                return f"太棒了！『{t}』= 24，二四点通关！奖励{coin}{S.coin_name()} 魅力+{meili}"
                            return "算式得数不是 24，再试试~"
                        return "请只用给出的 4 个数！"
                    except Exception:
                        return "算式有误，请检查（只用 %s 和 +-*/ 括号）：%s" % (" ".join(map(str, nums)), t)
        else:
            # 兼容旧单人二四点（无owner时）
            g = S.recall_get(f"game24_{gid}_{qq}")
            if g and re.search(r"[\+\-\*/()×÷]", text):
                nums = [int(x) for x in g.split("|") if x != ""]
                t = text.strip().replace("×", "*").replace("÷", "/").replace("（", "(").replace("）", ")")
                try:
                    used = [int(x) for x in re.findall(r"\d+", t)]
                    if sorted(used) == sorted(nums):
                        val = _safe_eval_24(t)
                        if val is None:
                            return "算式有误，请检查（只用 %s 和 +-*/ 括号）：%s" % (" ".join(map(str, nums)), t)
                        if abs(val - 24) < 1e-6:
                            S.recall_set(f"game24_{gid}_{qq}", "")
                            S.recall_set(f"ent_game_{gid}", "")
                            coin = S.cfgi("娱乐配置", "二四点奖励金币", 128)
                            meili = S.cfgi("娱乐配置", "二四点奖励魅力", 1)
                            _reward(gid, qq, coin, meili)
                            return f"太棒了！『{t}』= 24，二四点通关！奖励{coin}{S.coin_name()} 魅力+{meili}"
                        return "算式得数不是 24，再试试~"
                    return "请只用给出的 4 个数！"
                except Exception:
                    return "算式有误，请检查（只用 %s 和 +-*/ 括号）：%s" % (" ".join(map(str, nums)), t)
    # 接龙延续: 只允许参与者, 词尾字需接上
    # 需求14：仅当提及结尾字时才提醒未加入；指令不视为接龙词
    elif cur == "接龙":
        owner = S.recall_get(f"chain_owner_{gid}")
        if owner:
            # 若是其他系统指令，直接放行不作接龙处理
            if _is_cmd(text):
                return None
            last = S.recall_get(f"chain_{gid}", "")
            start = S.recall_get(f"chain_start_{gid}", "0")
            last_time = int(S.recall_get(f"chain_last_time_{gid}", "0") or 0)
            try:
                start_ts = int(start or "0")
                effective_ts = max(start_ts, last_time)
                if effective_ts <= 0 or (int(time.time()) - effective_ts) > 30:
                    _clean_expired_game(gid, max_seconds=0)
                    return "接龙超过30秒无人作答，已自动结束~"
            except Exception:
                _clean_expired_game(gid, max_seconds=0)
                return "接龙超过30秒无人作答，已自动结束~"
            if not _is_player(gid, qq, "chain"):
                # 仅当非参与者尝试接龙（2-6字且首字接尾字）才提醒
                if text and 2 <= len(text) <= 6 and not text.startswith(("开始", "加入", "退出")) and last and text[0] == last[-1]:
                    return "您不是本局参与者，无法接龙！发送【加入接龙】加入吧~"
                return None
            if text and 2 <= len(text) <= 6 and not text.startswith(("开始", "加入", "退出")):
                if last:
                    # 关键优化：首字不匹配上一词尾字，说明参与者在群里正常闲聊，绝不拦截轰炸，直接静默放行！
                    if text[0] != last[-1]:
                        return None
                    if text == last:
                        return f"不能重复接上一个完全相同的词语「{last}」哦，请换一个词~"
                used_str = S.recall_get(f"chain_used_{gid}", "")
                used_list = [w for w in used_str.split(",") if w]
                if text in used_list:
                    return f"词语「{text}」在本轮接龙中已经使用过了，请换一个新词吧~"

                now = int(time.time())
                last_qq = S.recall_get(f"chain_last_qq_{gid}", "")
                last_time = int(S.recall_get(f"chain_last_time_{gid}", "0") or 0)
                if last_qq == str(qq) and now - last_time < 2:
                    return "接得太快啦，深呼吸一下再接吧~"

                used_list.append(text)
                if len(used_list) > 100:
                    used_list = used_list[-100:]
                S.recall_set(f"chain_used_{gid}", ",".join(used_list))
                S.recall_set(f"chain_{gid}", text)
                S.recall_set(f"chain_start_{gid}", str(now))
                S.recall_set(f"chain_last_qq_{gid}", str(qq))
                S.recall_set(f"chain_last_time_{gid}", str(now))

                coin = S.cfgi("娱乐配置", "接龙奖励金币", 20)
                meili = S.cfgi("娱乐配置", "接龙奖励魅力", 0)
                _reward(gid, qq, coin, meili)
                if meili > 0:
                    return f"→ {text} 奖励{coin}{S.coin_name()} 魅力+{meili}"
                return f"→ {text} 奖励{coin}{S.coin_name()}"
            return None

__all__ = ["_play", "handle"]
