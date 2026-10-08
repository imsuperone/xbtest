# 小白测试版 `astrbot_plugin_xbbot_beta` v26w1009b

> 深度复刻经典群互动玩法的 AstrBot 插件，附全功能 WebUI 管理大屏。

## 简介

包含奴隶、签到、银行、娱乐、精灵、坐骑、帮派、冒险、超管等 28 大系统，覆盖群内互动与数值养成，数据以 SQLite 落地。

本插件基于 [AstrBot](https://github.com/AstrBotDevs/AstrBot) 开发。AstrBot 是一个松耦合、异步、支持多消息平台部署，具有易用的插件系统和完善的大语言模型（LLM）接入功能的聊天机器人及开发框架，使用文档见 [docs.astrbot.app](https://docs.astrbot.app)。

- 插件 ID：`astrbot_plugin_xbbot_beta`
- 当前版本：`v26w1009b`
- 运行要求：AstrBot `>=3.4.0`，平台 `aiocqhttp`
- 仓库：https://github.com/imsuperone/xbtest

## 安装

1. AstrBot 插件管理器「安装插件」填入 `https://github.com/imsuperone/xbtest`；
2. 安装后在后台「小白测试版」页面使用 WebUI。

## 测试版说明

- 数据目录独立（`plugin_data/astrbot_plugin_xbbot_beta`），与正式版互不读写；
- 请勿与正式版同时启用，切换后建议重启 AstrBot。
