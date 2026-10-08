# 小白测试版 · AstrBot 插件 `astrbot_plugin_xbbot_beta` v26w1008d

深度复刻经典群互动玩法的 AstrBot 插件：奴隶、签到、银行、娱乐、精灵、坐骑、帮派、冒险、超管等 28 大系统，附带全功能 WebUI 管理大屏。

本插件基于 [AstrBot](https://github.com/AstrBotDevs/AstrBot) —— 开源的一站式 Agent 聊天机器人平台，支持主流 IM 平台与多种大模型接入，内置 WebUI 与插件扩展体系。使用文档见 [docs.astrbot.app](https://docs.astrbot.app)。

- 项目主页：https://github.com/imsuperone/xbtest
- 插件 ID：`astrbot_plugin_xbbot_beta`
- 当前版本：`v26w1008d`（要求 AstrBot `>=3.4.0`，平台 `aiocqhttp`）

## 安装

1. 在 AstrBot 插件管理器「安装插件」中填入仓库地址 `https://github.com/imsuperone/xbtest`，一键安装；
2. 安装后在 AstrBot 后台进入「小白测试版」页面，使用 WebUI 管理大屏进行玩法配置。

## 测试版说明

- 插件名 `astrbot_plugin_xbbot_beta`，显示名「小白测试版」，网页路由为 `/astrbot_plugin_xbbot_beta/...`；
- 数据目录独立（`plugin_data/astrbot_plugin_xbbot_beta`），与正式版互不读写；
- 不要与正式版同时启用；切换后建议重启 AstrBot，保证模块状态干净。

## 更新日志

见 [CHANGELOG.md](./CHANGELOG.md)。
