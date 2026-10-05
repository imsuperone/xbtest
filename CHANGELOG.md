# 更新日志

## v26w1005f
- 🔐 **主题色 / 深浅色改存服务端**：AstrBot 用沙箱 iframe 载插件页，`localStorage` 被禁（稳定版 `pages/admin/app.js` 的「沙箱 iframe 禁止 localStorage, 仅内存切换」注释早已注明），此前主题色与深浅色只写本地，**刷新即恢复默认**。现统一落配置 `UI偏好` 节：`config/save` 逐节 `setdefault+update`、缺键不动，不碰玩法配置；该节不在 `config/schema` 内，配置页按 `schema.groups` 渲染不会被误显示。顶栏取色 / 切换后 600ms 防抖写入，启动时 `config/get` 立即回填。
- 🎞️ **首帧挂起，不再「先见默认色、再跳成已存色」**：`<head>` 内联脚本先置 `data-boot` 挂起首屏，主题色与深浅色回填完成后揭幕，并有 3s 兜底超时；沙箱外（直接开页）localStorage 仍作快速路径，不额外等待。
- 🧭 **首次使用自动补写**：服务端尚无 `主题模式` 时，回填完成后把当前解析值回写一次，保证第一次会话就能留住。
