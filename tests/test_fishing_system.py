# -*- coding: utf-8 -*-
"""tests/test_fishing_system.py — 钓鱼与迷你世界水族馆系统全链路功能测试。"""
import os
import sys
import unittest
import asyncio
import json

# 加入项目根目录
_PROJ_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJ_ROOT not in sys.path:
    sys.path.insert(0, _PROJ_ROOT)

from games.fishing import data_fishes, engine, handle, COMMANDS
from core import storage as ST
from core.api import fishing_api


class TestFishingSystem(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # 初始化独立内存测试库
        cls.test_db = os.path.join(_PROJ_ROOT, "data", "test_fishing_tmp.db")
        ST.init(cls.test_db)

    @classmethod
    def tearDownClass(cls):
        if os.path.isfile(cls.test_db):
            try:
                os.remove(cls.test_db)
            except Exception:
                pass

    def setUp(self):
        self.gid = "10001"
        self.qq = "20002"
        # 给测试用户充足金币与体力
        ST.coins_add(self.gid, self.qq, 50000)
        # 清空钓鱼数据
        engine._save_data(self.gid, self.qq, {})

    def test_01_fishes_database_and_roll(self):
        """测试 105 种鱼类数据库读取与抽样"""
        fishes = data_fishes.load_all_fishes()
        self.assertGreaterEqual(len(fishes), 105)

        # 抽样 30 次，验证重量在范围区间内且具备必要字段
        for _ in range(30):
            f = data_fishes.roll_random_fish(bonus_luck=0.2)
            self.assertIn("name", f)
            self.assertIn("weight", f)
            self.assertIn("grade", f)
            self.assertIn("price", f)
            self.assertIn("zone", f)
            self.assertGreater(f["price"], 0)
            if f["grade"] == "SS级":
                self.assertTrue(f["is_gold_crown"])

    def test_02_bucket_overflow_hard_blocker(self):
        """测试核心硬指标：水桶满仓前置拦截，绝不扣体力与次数"""
        d = engine._get_data(self.gid, self.qq)
        # 打窝
        res_bait = engine.cmd_bait(self.gid, self.qq, "蚯蚓饵")
        self.assertIn("打窝培育成功", res_bait)

        # 手动将鱼塘设为成熟
        d = engine._get_data(self.gid, self.qq)
        d["pond"]["mature_ts"] = 0
        # 填满水桶 (10条)
        d["bucket"] = [{"name": f"大鱼_{i}", "price": 100} for i in range(10)]
        d["bucket_cap"] = 10
        engine._save_data(self.gid, self.qq, d)

        # 尝试挥竿钓鱼
        casts_before = d["pond"]["remain_casts"]
        res_fish = engine.cmd_fish(self.gid, self.qq)

        # 验证：前置拦截提示，且竿梢被阻断
        self.assertIn("水桶已经装满啦", res_fish)
        self.assertIn("竿梢已被阻断", res_fish)

        # 验证：鱼塘次数未被消耗
        d_after = engine._get_data(self.gid, self.qq)
        self.assertEqual(d_after["pond"]["remain_casts"], casts_before)

    def test_03_bucket_and_sell(self):
        """测试水桶查看与出售渔获"""
        d = engine._get_data(self.gid, self.qq)
        d["bucket"] = [
            {"fish_id": "f1", "name": "彩虹金鳞鲤", "quality_label": "⚪普通", "weight": 1.5, "grade": "B级", "price": 100, "is_gold_crown": False},
            {"fish_id": "f2", "name": "星穹织梦鲲", "quality_label": "🌈神话", "weight": 350.0, "grade": "SS级", "price": 6000, "is_gold_crown": True}
        ]
        engine._save_data(self.gid, self.qq, d)

        # 查看水桶
        res_b = engine.cmd_bucket(self.gid, self.qq)
        self.assertIn("彩虹金鳞鲤", res_b)
        self.assertIn("星穹织梦鲲", res_b)
        self.assertIn("👑", res_b)

        # 单条出售
        coins_before = ST.coins_get(self.gid, self.qq)
        res_sell_single = engine.cmd_sell(self.gid, self.qq, "1")
        self.assertIn("单条出售成功", res_sell_single)
        self.assertEqual(ST.coins_get(self.gid, self.qq), coins_before + 100)

        # 一键全卖
        res_sell_all = engine.cmd_sell(self.gid, self.qq, "")
        self.assertIn("全桶变现成功", res_sell_all)
        self.assertEqual(ST.coins_get(self.gid, self.qq), coins_before + 100 + 6000)

    def test_04_aquarium_life_cycle_and_decay(self):
        """测试水族馆入住、换水保洁、离线利息与水质动态衰减防通胀"""
        d = engine._get_data(self.gid, self.qq)
        # 默认名称
        self.assertEqual(d["aquarium"]["name"], "水族馆")

        # 放入一条高身价鱼
        d["aquarium"]["fishes"].append({
            "name": "巨齿噬渊鲨",
            "quality": "橙色传说",
            "quality_label": "🟠传说",
            "size": "超大型",
            "weight": 25.0,
            "price": 2000
        })
        d["aquarium"]["water_quality"] = 100
        # 模拟过去 5 小时
        d["aquarium"]["last_settle_ts"] = int(engine.time.time()) - 5 * 3600
        engine._save_data(self.gid, self.qq, d)

        # 触发水族馆利息结算
        res_aq = engine.cmd_aquarium(self.gid, self.qq)
        self.assertIn("水族馆", res_aq)
        self.assertIn("结算了离线利息", res_aq)

        # 验证水质发生了衰减
        d_after = engine._get_data(self.gid, self.qq)
        self.assertLess(d_after["aquarium"]["water_quality"], 100)

        # 执行水族馆换水
        res_clean = engine.cmd_clean_water(self.gid, self.qq)
        self.assertIn("换水保洁完成", res_clean)
        d_clean = engine._get_data(self.gid, self.qq)
        self.assertEqual(d_clean["aquarium"]["water_quality"], 100)

        # 水族馆改名
        res_rename = engine.cmd_rename_aquarium(self.gid, self.qq, "深海梦境馆")
        self.assertIn("深海梦境馆", res_rename)
        d_rename = engine._get_data(self.gid, self.qq)
        self.assertEqual(d_rename["aquarium"]["name"], "深海梦境馆")

    def test_05_social_steal(self):
        """测试群友偷鱼博弈"""
        target_qq = "30003"
        # 目标建立成熟且已过保护期的鱼塘
        t_data = engine._get_data(self.gid, target_qq)
        t_data["pond"] = {
            "bait": "复合颗粒窝料",
            "mature_ts": 0,
            "protect_end_ts": 0,
            "remain_casts": 2,
            "total_casts": 5,
            "is_active": True
        }
        engine._save_data(self.gid, target_qq, t_data)

        # 偷鱼
        res_steal = engine.cmd_steal_fish(self.gid, self.qq, target_qq)
        self.assertIn("偷鱼成功", res_steal)

        # 验证对方鱼塘次数被消耗
        t_after = engine._get_data(self.gid, target_qq)
        self.assertEqual(t_after["pond"]["remain_casts"], 1)

    def test_06_router_command_dispatch(self):
        """测试指令入口路由分发"""
        self.assertIn("钓鱼", COMMANDS)
        self.assertIn("水族馆", COMMANDS)
        self.assertIn("水桶", COMMANDS)

        res_menu = handle(self.gid, self.qq, "钓鱼菜单")
        self.assertIn("元梦之星风格钓鱼与水族馆", res_menu)

        res_pond = handle(self.gid, self.qq, "鱼塘")
        self.assertTrue(len(res_pond) > 0)

    def test_07_web_api_endpoints(self):
        """测试管理后台 Web API"""
        # 总览
        ov = asyncio.run(fishing_api.handle_fishing_overview())
        self.assertEqual(ov.get("code"), 0)
        self.assertGreaterEqual(ov.get("total_species"), 105)

        # 列表与搜索
        fl = asyncio.run(fishing_api.handle_fishing_fishes({"query": {"search": "鲲"}}))
        self.assertEqual(fl.get("code"), 0)
        self.assertTrue(any("鲲" in f.get("name", "") for f in fl.get("data", [])))

        # 恢复默认
        rst = asyncio.run(fishing_api.handle_fishing_reset())
        self.assertEqual(rst.get("code"), 0)


if __name__ == "__main__":
    unittest.main()
