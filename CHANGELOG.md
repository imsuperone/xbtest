# 更新日志

## v26w1006a
- 🐛 **文本预览关闭确认不再吞稿**：`pageConfirm` 此前落到 03_import 的 `#appModal` 版确认框，会把正在编辑的预览内容整个清掉——取消也丢稿，还留下 `modal-wide` 残留把后续弹窗撑宽。现 01_theme 的 overlay 版改名 `overlayConfirm` 专门服务 `pageConfirm`，独立浮层不碰 `#appModal`。
- 🧹 **消除 uiConfirm/uiPrompt 双定义**：`01_theme.js` 与 `03_import.js` 曾各定义一对同名函数（后加载者胜出），overlay 版整层死代码、按钮文案参数被当成标题。现 `uiConfirm/uiPrompt` 只由 03_import 定义，overlay 侧只留 `overlayConfirm`，死掉的 `uiPrompt` overlay 版与 `.xb-confirm-input` 样式一并删除。

## v26w1005g
- 🔔 **通知统一样式 + 全部可复制**：三端 toast 改为同款「右下堆叠胶囊 + 类型图标」，按文案自动配色（失败类红 / 完成类绿 / 进行中中性，显式 `type` 仍优先）。点击通知或右侧复制按钮即可复制全文；沙箱禁剪贴板时自动全选文本供手动 Ctrl+C。
- ✨ **通知体验细节**：文本可手动选中、支持换行；长文本自动延长展示时间（最长 9s）；同屏最多堆 4 条；离场改为渐隐下沉动画。
- 🧹 **清理遗留通知通道**：删除早已停用的 `#toast` / `#snackbar` 元素与对应样式——同一条消息曾会渲染三份、层间叠出怪底色与描边线。
