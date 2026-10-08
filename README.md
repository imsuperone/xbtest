# 小白测试版 `astrbot_plugin_xbbot_beta` v26w1009a

> 深度复刻经典群互动玩法的 AstrBot 插件，附全功能 WebUI 管理大屏。

## 简介

包含奴隶、签到、银行、娱乐、精灵、坐骑、帮派、冒险、超管等 28 大系统，覆盖群内互动与数值养成，数据以 SQLite 落地。

本插件基于 [AstrBot](https://github.com/AstrBotDevs/AstrBot) 开发。AstrBot 是一款开源的多平台聊天机器人框架，可接入 QQ、Telegram 等消息平台与多家大模型服务，自带 Web 管理界面，使用文档见 [docs.astrbot.app](https://docs.astrbot.app)。

- 插件 ID：`astrbot_plugin_xbbot_beta`
- 当前版本：`v26w1009a`
- 运行要求：AstrBot `>=3.4.0`，平台 `aiocqhttp`
- 仓库：https://github.com/imsuperone/xbtest

## 安装

1. AstrBot 插件管理器「安装插件」填入 `https://github.com/imsuperone/xbtest`；
2. 安装后在后台「小白测试版」页面使用 WebUI。

## 测试版说明

- 数据目录独立（`plugin_data/astrbot_plugin_xbbot_beta`），与正式版互不读写；
- 请勿与正式版同时启用，切换后建议重启 AstrBot。
