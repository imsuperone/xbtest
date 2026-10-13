# 更新日志 (Changelog)

## v26w1012r (2026-10-13)

- **智能数值调控双模式升级**：
  - 新增 **📌 固定预设模式（`control_type = "fixed"`）** 与 **⚡ 实时调整模式（`control_type = "realtime"`）** 双模式切换。
  - **固定预设模式**保留「⚖️ 标准平衡 / 🌱 休闲高产 / 🔥 硬核防通胀」三档预设，按选定档位校准全服 28 大系统参数与身价，不受通胀指数浮动影响。
  - **实时调整模式**实时采样全服人均资产、中位数与 Top10% 富豪集中度，自动计算通胀倍率并动态缩放消耗、商店物价、副本门票与身价。
- **修复智能数值调控多项缺陷**：
  - 修复 `_DEFAULT_BALANCE_TEMPLATE` 中无效配置键（如 `work_reward_min/max`、`rob_cooldown` 等），全面对齐 `games/*` 真实读取的配置键（`work_min_gain`/`work_max_gain`/`work_duration_minutes`/`slave_slots_default`/`slave_slots_max` 等）。
  - 修复坐骑校准使用错误键名的问题，对齐真实坐骑表（`幽灵狼 / 烈焰马 / 雷霆狮鹫 / 冰霜巨龙 / 星界鲲鹏 / 混沌神龙`）。
  - 修复 `_calibrate_slave_prices` 仅扫描旧内存字典而不扫描 SQLite `groups` 表导致全群用户身价校准失效的问题。
  - 修复 WebUI 管理台 `btnAutoBalance` / `btnAutoBalance2` 按钮未绑定点击事件及 `mismatch` 字段名不一致的问题。
  - 新增「智能调控 [固定/实时/标准/休闲/硬核/状态]」超管群聊指令。
