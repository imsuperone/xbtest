# 更新日志

## v2026w1005b
- 📁 **图片目录归位（用户反馈）**：包内 52 张内置图从 `data/games/img/` 全部迁到 `data/img/` —— 奴隶图 `data/img/nuli/{R,SR,SSR}/*.png`（42 张）、坐骑图 `data/img/rides/*.jpg`（10 张），删空 `data/games/`；包内无游戏数据文件（游戏数据在 `xb.db` 与持久化目录），故不建空 `data/game/`。代码引用改为新路径优先、旧 `data/games/img/*` 保留兼容回退：`db.py` 播种源、`weapon_pool.py` 包内种子、`gacha.py` 池候选、`ride.py` `_IMG_BASE` 反转 + `_alias_img_path` 新旧直连双向对、`shop.py` 10 处默认坐骑图、`08_shop.js` 22 处、`images.py` 缩略图回退新旧双向、`superadmin.py` 诊断 roots 补 `data/img/nuli/SSR`。
- 📦 **入库与打包规则同步**：`.gitignore` 由整目录忽略 `data/img/` 改为 `data/img/*` + `!data/img/nuli/` + `!data/img/rides/`（内置图入库、运行时武器池/上传仍忽略）；`pack.py` 对 beta 不再整目录排除 `data/img`，改为仅收 `nuli|rides` 两棵（防 gacha 等运行时副本再次膨胀 zip，161 条口径不变）。
- 🔢 **版本**：`2026w1005b`；`bump_version.py` 同步 metadata / index 四锚点 / `FRONTEND_VER`，`?v=` 12 处手升，`core/version.py` `_FALLBACK` 同步，README 标题同步 —— 本轮改了 JS/py 路径，刷前端缓存锚点让真机拉到新代码。
