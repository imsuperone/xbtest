# 更新日志 (Changelog)

## v26w1013a

- **启动性能与热路径减负优化**：
  - 已完成 `mig_force_stat_clamp_v2` 一次性强压迁移的实例不再在每次启动/重载时全表扫描并反序列化 `accounts` 表（运行时各入口已具备体力 `1000` / 魅力 `500` 硬上限保护），显著降低大库启动耗时与锁竞争。
  - `_dispatch` 群昵称自动同步新增进程级内存快表 `_GROUP_NAME_MEM`，避免每条群消息重复触发 `recall_get` 查询。
  - 清理 `core/api/web_utils.py` 中未使用的 `_raw_file_response` 与 `games/bank/jail.py` 中未使用的 `_jail_put` 历史残留代码。
- **智能数值调控双模式升级与修复**：
  - 新增 **📌 固定预设模式（`control_type = "fixed"`）** 与 **⚡ 实时调整模式（`control_type = "realtime"`）** 双模式切换，固定模式保留「⚖️ 标准平衡 / 🌱 休闲高产 / 🔥 硬核防通胀」三档预设。
  - 全面对齐 28 大系统真实配置键（打工、抢劫、坐骑、奴隶位默认 2 / 上限 5 等），修复 SQLite `groups` 表全群身价校准与 WebUI 调控按钮事件绑定。
