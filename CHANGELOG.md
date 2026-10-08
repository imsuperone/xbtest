# 更新日志

## v26w1008a
- 🔧 **恢复备份收敛为单一实现**：新增 `storage.restore_db_from()`（flush→checkpoint→sqlite backup→清缓存→reload，KV 缓存清理带锁），本地恢复与 WebDAV 远端恢复共用；API 层两份复制粘贴实现删除，修一处不再漏另一处。
- 🔧 **立即备份独立接口**：新增 `POST backups/create`，退役借道 `backups/restore` 的 `__backup_now__` 魔法哨兵（前端同步改调），清理 `webdav/upload` 对该哨兵的死守卫；一接口一语义。
- 📚 **接口总账与架构审计**：`aidocs/aiall.md` 新增 §8（67 条 HTTP 路由总账、170 条指令声明、多实现违规 V1-V14、层间数据反复传输 L1-L8、死代码 D1-D7；本地文档不进包）。
