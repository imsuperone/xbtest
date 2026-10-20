# -*- coding: utf-8 -*-
"""Unit tests for ride image persistence and system align defaults"""
import asyncio
import json
import os
import shutil
import tempfile
import unittest

import core.storage as ST
from core.api.images import _safe_path
from core.api.system_align import handle_align_defaults
from core.storage.db import _auto_migrate_and_heal, get_persistent_data_dir
from games import ride
from games.ent import content as ent_content


class TestPersistenceAndAlign(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="xb_test_persist_")
        self.plugin_base = os.path.join(self.test_dir, "plugin")
        self.pers_dir = os.path.join(self.test_dir, "persistent")
        os.makedirs(os.path.join(self.plugin_base, "data", "img", "rides"), exist_ok=True)
        os.makedirs(os.path.join(self.plugin_base, "data", "questions"), exist_ok=True)
        os.makedirs(os.path.join(self.plugin_base, "data", "seeds", "questions"), exist_ok=True)
        os.makedirs(self.pers_dir, exist_ok=True)
        ST.set_persistent_data_dir(self.pers_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_ride_image_safe_path_and_discovery(self):
        # 1. Simulate user uploaded image only in persistent storage (e.g. after plugin update)
        pers_ride_dir = os.path.join(self.pers_dir, "data", "img", "rides")
        os.makedirs(pers_ride_dir, exist_ok=True)
        custom_img_path = os.path.join(pers_ride_dir, "custom_mount.png")
        with open(custom_img_path, "wb") as f:
            f.write(b"PNG_FAKE_CUSTOM_RIDE")

        # 2. _safe_path should find custom_mount.png in persistent storage
        resolved = _safe_path("data/img/rides/custom_mount.png", self.plugin_base)
        self.assertIsNotNone(resolved)
        self.assertTrue(os.path.isfile(resolved))
        self.assertEqual(os.path.abspath(resolved), os.path.abspath(custom_img_path))

        # 3. Test _auto_migrate_and_heal restores missing user image to plugin_base
        _auto_migrate_and_heal(self.pers_dir, self.plugin_base, force=True)
        healed_path = os.path.join(self.plugin_base, "data", "img", "rides", "custom_mount.png")
        self.assertTrue(os.path.isfile(healed_path))
        with open(healed_path, "rb") as f:
            self.assertEqual(f.read(), b"PNG_FAKE_CUSTOM_RIDE")

    def test_ride_img_path_fallback_to_persistent(self):
        # Place an image only in persistent storage
        pers_ride_dir = os.path.join(self.pers_dir, "data", "img", "rides")
        os.makedirs(pers_ride_dir, exist_ok=True)
        img_name = "test_horse.jpg"
        img_full = os.path.join(pers_ride_dir, img_name)
        with open(img_full, "wb") as f:
            f.write(b"HORSE_IMAGE")

        # Configure shop with custom ride pointing to relative path
        test_shop = {
            "神驹": {
                "price": 888888,
                "img": "data/img/rides/test_horse.jpg",
                "buff": 12,
                "buff_type": "all"
            }
        }
        ST.coll_merge("商城图鉴", {"ride_shop": test_shop})

        found = ride._ride_img_path("神驹")
        self.assertTrue(bool(found))
        self.assertTrue(os.path.isfile(found[0]))

    def test_align_defaults_preserves_custom_data(self):
        # Setup active question bank with a custom question
        q_dir = os.path.join(self.plugin_base, "data", "questions")
        trick_file = os.path.join(q_dir, "trick.json")
        active_trick = [
            {"q": "测试用户自建问题？", "a": "自建答案"},
            {"q": "世界上哪个英文字母最多人戴？", "a": "旧错误答案"}
        ]
        with open(trick_file, "w", encoding="utf-8") as f:
            json.dump(active_trick, f, ensure_ascii=False)

        # Setup seed question bank with official corrected question
        seed_dir = os.path.join(self.plugin_base, "data", "seeds", "questions")
        seed_trick = [
            {"q": "世界上哪个英文字母最多人戴？", "a": "T / T恤 / 帽子"}
        ]
        with open(os.path.join(seed_dir, "trick.json"), "w", encoding="utf-8") as f:
            json.dump(seed_trick, f, ensure_ascii=False)

        # Setup user custom mount in ride shop
        user_rides = {
            "赤兔马": {"price": 9999999, "img": "data/img/rides/chitu.jpg", "buff": 20, "buff_type": "all"},
            "企鹅": {"price": 100, "img": "data/img/rides/my_custom_penguin.jpg", "buff": 5, "buff_type": "work"}
        }
        ST.coll_merge("商城图鉴", {"ride_shop": user_rides})

        # Run handle_align_defaults
        payload = {"targets": ["riddles", "rides", "presets"], "backup": True}
        res = asyncio.run(handle_align_defaults(payload, self.plugin_base))
        self.assertTrue(res.get("ok"))
        self.assertIn("details", res)

        # Verify riddles: user custom question preserved, official question updated
        with open(trick_file, "r", encoding="utf-8") as f:
            merged_tricks = json.load(f)
        q_map = {it["q"]: it["a"] for it in merged_tricks}
        self.assertIn("测试用户自建问题？", q_map)
        self.assertEqual(q_map["测试用户自建问题？"], "自建答案")
        self.assertIn("世界上哪个英文字母最多人戴？", q_map)
        self.assertEqual(q_map["世界上哪个英文字母最多人戴？"], "T / T恤 / 帽子")

        # Verify rides: user custom mount preserved!
        updated_rides = ST.cfg("商城图鉴", "ride_shop", {})
        if isinstance(updated_rides, str):
            updated_rides = json.loads(updated_rides)
        self.assertIn("赤兔马", updated_rides)
        self.assertEqual(updated_rides["赤兔马"]["price"], 9999999)
        self.assertIn("企鹅", updated_rides)
        # Custom image path for penguin was kept!
        self.assertEqual(updated_rides["企鹅"]["img"], "data/img/rides/my_custom_penguin.jpg")
        # Penguin price aligned to official standard (213250)
        self.assertEqual(updated_rides["企鹅"]["price"], 213250)


if __name__ == "__main__":
    unittest.main()
