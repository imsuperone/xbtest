# 更新日志

## v26w1005d
- 🎨 **主题色只染「强调系」（方案 A）**：选色不再改 16 个变量，只改 `--m3-sys-color-primary` / `primary-container` 及 `--acc*` 系；**4 个 surface 系（页面底 / 卡片 / 面板 / 最高层）不再随选色变化**，整页保持中性灰，只有按钮、徽章、选中态取色。之前整页被染脏、"改太多太丑"的主因即 surface 染色。分段控件选中色改为按 CSS 中性默认底算对比度（不再依赖被染的 surface）。
- 🐛 **修「恢复默认后再切换又变回旧主题色」**：`applyAccentColor("")` 的恢复默认分支只清了 inline 样式和 `localStorage.xbbot_accent`，**没有清内存态 `_CURRENT_ACCENT_COLOR`**；而 `applyTheme()` 每次切换浅/深色末尾会 `applyAccentColor(_CURRENT_ACCENT_COLOR)`，于是把旧色重新写回 inline 并重新持久化 → 表现为"切换持久化卡住、恢复默认后一切换又变回第一次改的颜色、刷新也还在"。现恢复默认分支同步置空 `_CURRENT_ACCENT_COLOR`，并顺手 `removeItem` 掉旧版遗留键 `xbbot_monet_color`（留着会在下次冷启动被 `initAccentColor` 当兜底复活）；`initAccentColor` 不再预写内存态，统一由 `applyAccentColor` 维护。
- 🔢 **版本号改制 `26w1005d`（2 位年，去掉 20 前缀）**：格式门禁 `^\d{2}w\d{4}[a-z]$`，历史 4 位年仍可解析且单调成立（年份归一 2000+）。同步改 `bump_version.py`（SNAP_RE / snapshot_tuple / next_snapshot 输出 `%02d`）、`test_beta.py`（SNAP_RE + 硬编码扫描）、`pack.py` `DOC_VER_RE`、`core/version.py`（`_FALLBACK` + `parse_version_tuple`）、`core/api/version_check.py` 本地兜底正则，否则新号会退化成 semver 解析、被更新检查判成降级。
