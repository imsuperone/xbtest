# 更新日志

## v26w1008c
- 🧹 **死代码清理（AST 全仓零引用扫描）**：删除 `api/stats.py` 尾部三段「兼容重导出」块（16 行，全仓零消费——五元组与导入链均指向 logs/groups/version_check 原模块）；`api/settings.py` 重导出瘦身只留 `PRESETS`/`_BALANCE_SIG_KEYS`（app/superadmin 兼容导入链的实际消费对，删零消费的 2 个 handle 再导出）；删除零引用常量 `TREASURE_TYPES`（shop.py，前端 07_spirit.js 有独立同名实现不受影响）、`NOTE_NAMES_REV`（slave_state.py）、`T_GOURD_EFFECT`/`T_CHARM_EFFECT`（text_slave.py）、`API_URL`（version_check.py，已被按通道动态拼 URL 取代）。
- 🧹 **扫描结论**：775 个函数/类定义 0 死亡（含字符串注册表匹配）；JS 407 个声明 0 死亡；无注释掉的代码块。
- 🧪 **门禁**：STRICT 7/7、routes 64/64/37、parity GATE 9 引擎 lost=0、V8+L2/L4 冒烟、compileall 0、复扫 0 死函数/0 死常量。未做真机回归。

## v26w1008b
- 🔧 **指令索引大一统（V8/L3）**：六族正则索引退役留墓碑，`config._collect_commands` 改逐文件 AST 读 `COMMANDS` 单源（常量须先于表定义）；8 张引擎表并入 V8 词（slave11/bank3/ent20/spirit9/ride1/guild8/adventure1）与 superadmin 联合表（静态 6 + `_ADMIN_CMDS` 27 = 33）；`router._matches_engine` 重写为三段单索引（唤醒前缀 → 系统三件套 → 引擎 COMMANDS 前缀），删 `_ENGINE_CMDS` 双层缓存；奇偶门禁 9 引擎 lost=0。
- 🔧 **自定义指令配置单源（L2）**：`_custom_idx` 携带 `ent` 入口载荷，`_custom_cmd`（路由匹配）与 `dispatch._is_pure_custom`（回复后处理）只走索引——未升 `_CONFIG_VER` 不回读配置节，消除同一条消息读两遍并重排序。
- 🔧 **显示名解析单源（L4）**：新增 `messaging.resolve_display_name`（分群 → 跨群 NOTE_NAMES → qq，slave_mod 可注入），`_render_vars` 变量渲染与 `_name_prefix` 发送前缀委托同链，两处各解析一遍的重复实现合一。
- 🔧 **HTTP 路由五元组直发（L5/L6）**：`web_routes` 五元组单源，删 app 侧 `_XB_PAGE_CALLS`/`locals()` 合成层，64 路由直发 `handle_*`（MUTATING 37 token 翻 handle 名）。
- 🔧 **导出与预览接口合并（V12/V13）**：统一 `GET images/preview?path=` 单图预览（旧 thumb/pool-img 退役）；新增 `exporters.handle_export(kind)` + `GET export?kind=` 合并三导出（kind 先 query 后 body 只读一次、400 兜底），前端 12 处 endpoint/kind 同步。
- 🔧 **单入口收敛（V4/V5/V6/V7/V9/V10/V11/V14）**：版本逻辑全走 `get_version()`；`save_config+sync` 12 处组合收敛为 `ST.save_config()` 单入口（sync 折叠为内部步骤）；`_err`/`_raw_file_response` 只留 `web_utils`、`json_response` adapters 收口；3 处被遮蔽重复指令删除；维护门只留 `router.maintenance_gate`（app 内联改单源调用）；前端原生 `confirm`/`callApi` 删除（定案保留 overlayConfirm/pageConfirm 双机制）。
- 🧹 **死代码清理与审计标记（D2-D7）**：8 个 `can_handle`、9 个 `WAKE`、protocol 死件三连、4 空壳包、`domains.py` 全删（删除前全仓零引用自证）；`aidocs/aiall.md` §8 逐条标记（V1 冻结维持、L1/L7 留档、D7 BY DESIGN 记录在案）。
- 🧪 **门禁**：STRICT 7/7、路由 64/64/37、奇偶门禁 9 引擎 lost=0、V8/L2/L4 行为冒烟全绿、compileall 0。未做真机回归。

## v26w1008a
- 🔧 **恢复备份收敛为单一实现**：新增 `storage.restore_db_from()`（flush→checkpoint→sqlite backup→清缓存→reload，KV 缓存清理带锁），本地恢复与 WebDAV 远端恢复共用；API 层两份复制粘贴实现删除，修一处不再漏另一处。
- 🔧 **立即备份独立接口**：新增 `POST backups/create`，退役借道 `backups/restore` 的 `__backup_now__` 魔法哨兵（前端同步改调），清理 `webdav/upload` 对该哨兵的死守卫；一接口一语义。
- 📚 **接口总账与架构审计**：`aidocs/aiall.md` 新增 §8（67 条 HTTP 路由总账、170 条指令声明、多实现违规 V1-V14、层间数据反复传输 L1-L8、死代码 D1-D7；本地文档不进包）。
