# 更新日志

## v26w1005e
- 🎨 **调色盘按钮重做**：顶栏取色按钮原先是一个纯色空心圆、没有任何图标，现在改为 **外圈彩虹取色环 + 内圈当前主题色 + 调色板图标**，既一眼看出是"选颜色"，也仍然能直接看到当前取色。图标取 `--m3-sys-color-on-primary`，与按钮底色成对（黄色等浅底自动转深色字），换色 / 换深浅色都跟随；配套 hover 轻抬、active 内缩、focus-visible 描边。
- 🧩 **压过全局按钮样式**：规则选择器升级为 `button.m3-accent-picker`，避免被全局 `button:hover`（棕色阴影 + `brightness(0.96)` 滤镜）和 `button:active` 覆盖，深浅色两套主题下 hover 表现一致；并显式声明 `inline-flex` 居中，不依赖各端全局 `button` 规则。
- 🔁 **调色逻辑与 xbdoc / xbimg 三端对齐**：三个插件的调色盘按钮外观、内嵌 SVG 图标、取色派生逻辑统一；xbdoc / xbimg 同步移除 4 个 surface 系染色（只染 `primary` / `primary-container`），分段控件字色改为按 CSS 中性默认底算对比度。
