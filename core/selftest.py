# -*- coding: utf-8 -*-
"""core/selftest.py — 小白测试版全系统自动化自测探针引擎 (xbtest all)。
提供 8 大核心系统（签到、精灵、娱乐、银行、奴隶、坐骑、帮派、冒险）菜单汇总、
全量端到端探针自检与单系统针对性测试。
执行环境：独立隔离测试群（999999），测试完毕后全自动清理三表与会话缓存，零污染真实群数据。
"""
import asyncio
import datetime as dt
import json
import os
import sys
import time

try:
    from . import storage as ST
except ImportError:
    import core.storage as ST

try:
    from ..games import sign, spirit, ent, bank, slave, ride, guild, adventure
except (ImportError, ValueError):
    from games import sign, spirit, ent, bank, slave, ride, guild, adventure

SYS_ORDER = [
    ("sign", "签到系统", "测试xbtest 2"),
    ("spirit", "精灵系统", "测试xbtest 3"),
    ("ent", "娱乐系统", "测试xbtest 4"),
    ("bank", "银行系统", "测试xbtest 5"),
    ("slave", "奴隶系统", "测试xbtest 6"),
    ("ride", "坐骑系统", "测试xbtest 7"),
    ("guild", "帮派系统", "测试xbtest 8"),
    ("adventure", "冒险系统", "测试xbtest 9"),
]

SYS_MODS = {
    "sign": sign, "spirit": spirit, "ent": ent, "bank": bank,
    "slave": slave, "ride": ride, "guild": guild, "adventure": adventure,
}

# 8 大核心系统基础探针指令与期望关键字
PROBE_CASES = {
    "sign": [
        ("签到系统唤醒", "签到系统", "签到"),
        ("日常签到", "签到", ("金币", "体力", "已签到", "成功", "今日")),
        ("每日打卡", "每日打卡", ("金币", "体力", "已签到", "成功", "今日")),
        ("财富榜单", "财富榜", ("财富", "富豪", "榜")),
        ("新手礼包", "领取新手礼包", ("礼包", "金币", "已经领取", "成功")),
        ("购买体力", "购买体力 1", ("体力", "金币", "不足", "成功")),
    ],
    "spirit": [
        ("精灵系统唤醒", "精灵系统", "精灵"),
        ("领养精灵", "领养精灵", ("获得精灵", "领养", "火苗", "水灵", "草芽", "叶子", "已有")),
        ("我的精灵", "我的精灵", ("精灵", "火苗", "水灵", "叶子", "战力", "暂无")),
        ("精灵商城", "精灵商城", ("商城", "精灵球", "大师球", "金币")),
        ("精灵背包", "精灵背包", ("背包", "道具", "球", "空")),
        ("查看精灵", "查看精灵 火苗", ("火苗", "属性", "技能", "暂未", "没有该精灵")),
    ],
    "ent": [
        ("娱乐系统唤醒", "娱乐系统", "娱乐"),
        ("开始二四点", "开始二四点", ("二四点开始", "算式", "24")),
        ("退出二四点", "退出二四点", ("退出", "对局结束", "参考算式")),
        ("开始急转弯", "开始急转弯", ("急转弯", "题目", "请答")),
        ("退出急转弯", "退出急转弯", ("退出", "正确答案")),
        ("娱乐抽签", "抽签", ("签", "运势", "解曰")),
        ("猜拳测试", "猜拳 石头", ("猜拳", "出", "赢", "输", "平局")),
    ],
    "bank": [
        ("银行系统唤醒", "银行系统", "银行"),
        ("银行存款", "存款 100", ("存款成功", "存入", "总存款")),
        ("银行取款", "取款 10", ("取款成功", "本次取款", "还剩存款")),
        ("赌博测试", "赌博 500", ("赌博", "金币", "成功", "失败", "赢", "输", "监狱")),
        ("打劫银行", "打劫银行", ("打劫银行", "劫走", "体力", "失败", "分钟", "抓")),
    ],
    "slave": [
        ("奴隶系统唤醒", "奴隶系统", "奴隶"),
        ("个人档案", "我的信息", ("的档案", "资产", "体力")),
        ("奴隶打工", "奴隶打工", ("打工", "金币", "体力", "主人", "没有奴隶")),
        ("我要祈福", "我要祈福", ("祈福", "祭拜", "忍神", "魅力", "金币", "今日")),
        ("我要造反", "造反", ("造反", "自由", "主人", "不是奴隶")),
    ],
    "ride": [
        ("坐骑系统唤醒", "坐骑系统", "坐骑"),
        ("我的坐骑", "我的坐骑", ("坐骑", "当前", "暂无")),
        ("坐骑商城", "坐骑商城", ("商城", "企鹅", "宝驴", "金币")),
        ("查看坐骑", "查看坐骑 企鹅", ("企鹅", "价格", "金币", "坐骑")),
    ],
    "guild": [
        ("帮派系统唤醒", "帮派系统", "帮派"),
        ("帮派列表", "帮派列表", ("帮派", "帮派列表", "暂无")),
        ("我的帮派", "我的帮派", ("帮派", "尚未加入", "暂无")),
        ("帮派排行", "帮派排行", ("排行", "帮派", "榜")),
    ],
    "adventure": [
        ("冒险系统唤醒", "冒险系统", "冒险"),
        ("当前冒险", "当前冒险", ("冒险", "当前", "没有")),
        ("提前撤离", "提前撤离", ("冒险", "撤离", "没有")),
        ("复活币排行", "复活币排行", ("复活币", "排行", "榜")),
    ],
}


def _init_sandbox_users(v_gid, rich_qq, poor_qq):
    """初始化沙盒测试账号初始状态"""
    try:
        # A 账号充钱充体力
        ST.coins_add(v_gid, rich_qq, 500000)
        a_rich = ST.acct(v_gid, rich_qq)
        a_rich.set("stamina", "200")
        a_rich.set("charm", "100")
        ST.acct_save(v_gid, rich_qq)

        # B 账号低保状态
        ST.coins_add(v_gid, poor_qq, 100)
        a_poor = ST.acct(v_gid, poor_qq)
        a_poor.set("stamina", "50")
        a_poor.set("charm", "10")
        ST.acct_save(v_gid, poor_qq)
    except Exception:
        pass


def _cleanup_sandbox(v_gid):
    """清理沙盒群（999999）残留数据，确保零污染"""
    try:
        with ST._LOCK:
            if ST._DB is not None:
                ST._DB.execute("DELETE FROM wallet WHERE gid=?", (int(v_gid),))
                ST._DB.execute("DELETE FROM accounts WHERE gid=?", (int(v_gid),))
                ST._DB.execute("DELETE FROM groups WHERE gid=?", (int(v_gid),))
                ST._DB.execute("DELETE FROM redpacks WHERE gid=?", (int(v_gid),))
                ST._DB.commit()
    except Exception:
        pass
    try:
        # 清除相关 recall
        ST.recall_set(f"ent_game_{v_gid}", "")
        for k in ("chain", "game24", "riddle", "idiom"):
            ST.recall_set(f"{k}_owner_{v_gid}", "")
            ST.recall_set(f"{k}_players_{v_gid}", "")
            ST.recall_set(f"{k}_ans_{v_gid}", "")
    except Exception:
        pass


def _check_expected(reply, expected):
    """校验回复是否符合预期"""
    if reply is None:
        return False, "无回复(None)"
    text = str(reply).strip()
    if not text:
        return False, "回复为空"
    if "Traceback" in text or "OperationalError" in text or "DatabaseError" in text:
        return False, f"发生未捕获异常: {text[:60]}"
    if isinstance(expected, str):
        if expected in text:
            return True, "匹配成功"
        return False, f"未包含期望关键词【{expected}】"
    if isinstance(expected, (list, tuple)):
        for kw in expected:
            if kw in text:
                return True, f"匹配成功({kw})"
        return False, f"未包含任一期望关键词{expected}"
    return True, "验证通过"


def run_system_probes(sys_key, v_gid="999999", rich_qq="10006"):
    """单系统同步探针测试"""
    mod = SYS_MODS.get(sys_key)
    cases = PROBE_CASES.get(sys_key, [])
    if not mod or not cases:
        return []

    results = []
    for label, cmd, expected in cases:
        try:
            # 优先调用引擎 handle
            if hasattr(mod, "handle"):
                try:
                    rep = mod.handle(v_gid, rich_qq, cmd)
                except TypeError:
                    rep = mod.handle(v_gid, rich_qq, cmd, is_admin=True)
            else:
                rep = mod(v_gid, rich_qq, cmd)

            ok, note = _check_expected(rep, expected)
            mark = "✅" if ok else "❌"
            summary_rep = str(rep).replace("\r\n", " ").replace("\n", " ").strip()
            if len(summary_rep) > 40:
                summary_rep = summary_rep[:37] + "..."
            results.append((mark, label, cmd, ok, summary_rep, note))
        except Exception as e:
            results.append(("❌", label, cmd, False, "崩溃异常", str(e)))

    return results


def run_all_probe_suites(v_gid="999999"):
    """执行全部 8 系统自测并汇总"""
    rich_qq = "10006"
    poor_qq = "10007"
    _init_sandbox_users(v_gid, rich_qq, poor_qq)

    all_results = {}
    total_cases = 0
    total_passed = 0

    try:
        for sys_key, sys_name, _ in SYS_ORDER:
            res = run_system_probes(sys_key, v_gid=v_gid, rich_qq=rich_qq)
            all_results[sys_name] = res
            passed = sum(1 for r in res if r[3])
            total_cases += len(res)
            total_passed += passed
    finally:
        _cleanup_sandbox(v_gid)

    return all_results, total_passed, total_cases


def format_system_report(sys_name, res_list):
    """格式化单系统自测报告"""
    passed = sum(1 for r in res_list if r[3])
    total = len(res_list)
    is_all_ok = (passed == total and total > 0)
    lines = [f"【{sys_name}】通过率: {passed}/{total} {'✅全过' if is_all_ok else '⚠️存在异常'}"]
    for mark, label, cmd, ok, rep, note in res_list:
        lines.append(f"{mark} [{label}] 指令: {cmd}\n   回复: {rep}")
    return "\n".join(lines)


def format_all_report(all_results, total_passed, total_cases):
    """格式化全系统合并自测报告"""
    all_ok = (total_passed == total_cases and total_cases > 0)
    sections = [
        f"📊 小白测试版全系统自测报告 (xbtest all)\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"总项数: {total_cases} | 通过: {total_passed} | 失败: {total_cases - total_passed}\n"
        f"整体结论: {'✅ 全链路 100% 通过' if all_ok else '❌ 部分系统存在异常'}\n"
        f"━━━━━━━━━━━━━━━━━━"
    ]
    for sys_name, res in all_results.items():
        sections.append(format_system_report(sys_name, res))
    return "\n\n".join(sections)


def build_test_menu_text():
    """测试总入口导航说明"""
    return (
        "🧪 小白测试版自动化自测系统 (xbtest)\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "可用测试指令：\n"
        "▶ 测试xbtest all  (或 测试testxb all / xbtest all)\n"
        "  全系统 8 大模块自动化端到端探针自检\n\n"
        "▶ 测试xbtest 签到   ▶ 测试xbtest 精灵\n"
        "▶ 测试xbtest 娱乐   ▶ 测试xbtest 银行\n"
        "▶ 测试xbtest 奴隶   ▶ 测试xbtest 坐骑\n"
        "▶ 测试xbtest 帮派   ▶ 测试xbtest 冒险\n"
        "  单系统针对性自动化自检\n\n"
        "▶ 测试xbtest 菜单\n"
        "  合并转发查看 8 大系统完整菜单视图\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "⚠️ 仅限机器人管理员触发，测试走沙盒隔离环境，零污染群数据"
    )


async def execute_test_command(raw, gid, qq, is_admin, event=None, bot=None):
    """执行自测指令核心分发函数"""
    text = (raw or "").strip()
    if not is_admin:
        return "亲亲，你没有相关权限哦~该指令仅限机器人管理员使用！"

    # 1. 纯菜单汇总 / 帮助
    if text in ("测试xbtest", "测试testxb", "xbtest", "测试xbtest 菜单", "测试testxb 1"):
        # 尝试生成 8 系统菜单合并转发
        try:
            from .dispatch import _build_test_menus, SYS_LABELS
            menus = await asyncio.to_thread(_build_test_menus, gid, qq, SYS_MODS)
            if bot and getattr(event, "call_action", None):
                nodes = []
                for idx, m in enumerate(menus):
                    nodes.append({
                        "type": "node",
                        "data": {
                            "name": f"小白测试-{SYS_LABELS[idx]}",
                            "uin": str(getattr(slave, "BOT_UIN", "") or qq),
                            "content": [{"type": "text", "data": {"text": str(m)[:4000]}}]
                        }
                    })
                await asyncio.wait_for(
                    bot.call_action("send_group_forward_msg", group_id=int(gid), messages=nodes),
                    timeout=8
                )
                return "__FORWARD_OK__已发送 8 大系统完整菜单合并转发"
        except Exception:
            pass
        return build_test_menu_text()

    # 2. 全量自检：测试xbtest all / 测试testxb all / xbtest all
    norm_cmd = text.lower().replace(" ", "").replace("_", "")
    if norm_cmd in ("测试xbtestall", "测试testxball", "xbtestall", "测试全部"):
        # 异步线程池执行全量探针
        all_results, total_passed, total_cases = await asyncio.to_thread(run_all_probe_suites)
        report_text = format_all_report(all_results, total_passed, total_cases)

        # 若处于真机环境且支持合并转发，按系统切分成转发节点发送
        if bot and getattr(event, "call_action", None):
            try:
                nodes = [
                    {
                        "type": "node",
                        "data": {
                            "name": "小白自测-总览",
                            "uin": str(getattr(slave, "BOT_UIN", "") or qq),
                            "content": [{"type": "text", "data": {
                                "text": f"📊 小白测试版全系统自测报告 (xbtest all)\n"
                                        f"总项数: {total_cases} | 通过: {total_passed} | 失败: {total_cases - total_passed}\n"
                                        f"结论: {'✅ 全链路通过' if total_passed == total_cases else '❌ 存在异常项'}"
                            }}]
                        }
                    }
                ]
                for sys_name, res in all_results.items():
                    sec_text = format_system_report(sys_name, res)
                    nodes.append({
                        "type": "node",
                        "data": {
                            "name": f"小白自测-{sys_name}",
                            "uin": str(getattr(slave, "BOT_UIN", "") or qq),
                            "content": [{"type": "text", "data": {"text": sec_text}}]
                        }
                    })
                await asyncio.wait_for(
                    bot.call_action("send_group_forward_msg", group_id=int(gid), messages=nodes),
                    timeout=10
                )
                return f"__FORWARD_OK__已发送全量自检报告合并转发（通过率: {total_passed}/{total_cases}）"
            except Exception:
                pass
        return report_text

    # 3. 单系统针对性自检：测试xbtest 签到 / 测试xbtest 2 ...
    target_key = None
    arg = text.replace("测试xbtest", "").replace("测试testxb", "").replace("xbtest", "").strip()
    sys_name_map = {
        "签到": "sign", "1": "sign", "2": "sign",
        "精灵": "spirit", "3": "spirit",
        "娱乐": "ent", "4": "ent",
        "银行": "bank", "5": "bank",
        "奴隶": "slave", "6": "slave",
        "坐骑": "ride", "7": "ride",
        "帮派": "guild", "8": "guild",
        "冒险": "adventure", "9": "adventure",
    }
    for k, v in sys_name_map.items():
        if arg == k or arg.startswith(k):
            target_key = v
            break

    if target_key:
        sys_display = dict((s[0], s[1]) for s in SYS_ORDER).get(target_key, target_key)
        _init_sandbox_users("999999", "10006", "10007")
        try:
            res = await asyncio.to_thread(run_system_probes, target_key, "999999", "10006")
        finally:
            await asyncio.to_thread(_cleanup_sandbox, "999999")
        return format_system_report(sys_display, res)

    return build_test_menu_text()
