# 项目概览

Ollupi 由两个项目组成：一个 Go agent 引擎，和一个基于引擎的 macOS 桌面端。

| | ollupi | ollupi-desktop |
|---|---|---|
| 是什么 | Go 库，agent 运行时 | Electron 应用 + Go 后端 `ollupid` |
| 面向谁 | 构建大规模个人 agent 服务的云服务商 | 在自己 Mac 上用 agent 的人 |
| 运行形态 | 一个进程托管一个分片里的所有用户和会话 | 本机一个用户，后端作为 sidecar 由应用托管 |
| 对外接口 | WebSocket 上的 JSON-RPC 2.0 | 桌面界面、飞书机器人 |
| 仓库 | [0xfakeSpike/ollupi](https://github.com/0xfakeSpike/ollupi) | [0xfakeSpike/ollupi-desktop](https://github.com/0xfakeSpike/ollupi-desktop) |

引擎为什么这样设计、付出了什么代价，见[为什么做 Ollupi](/zh/intro/why)。

![Ollupi 架构](/images/architecture.svg)

## 两个项目的关系

桌面端是引擎的下游。`sidecar/go.mod` 依赖一个发布过的引擎版本，桌面端只做展示和装配：

- 引擎提供会话、调度、持久化、工具、权限、沙箱、记忆、定时任务、搜索和协议。
- sidecar 把引擎装配起来，补上本机才有的东西：配置文件、内置浏览器工具、飞书机器人。
- 界面只通过协议和后端说话，类型由引擎生成的 `protocol.schema.json` 得到。

原则是逻辑放在拥有它的那一层。引擎能做的事，桌面端不重新实现一遍。

## 阅读路线

| 你想做什么 | 从这里开始 |
|---|---|
| 用桌面端 | [桌面端上手](/zh/app/install) |
| 把引擎嵌进自己的服务 | [把引擎嵌进服务](/zh/integrate/embed)、[协议](/zh/integrate/protocol) |
| 理解系统怎么工作 | [核心概念](/zh/intro/concepts)、[架构总览](/zh/engine/architecture)、[执行模型](/zh/engine/execution) |
| 看性能数据 | [性能基准](/zh/benchmarks/) |
| 查某个功能有没有 | [功能清单](/zh/reference/features) |
| 了解为什么这样设计 | [设计决策](/zh/reference/decisions)、[开发历程](/zh/reference/history)、[文章](/zh/articles/) |
| 了解接下来做什么 | [路线图](/zh/roadmap) |

## 文档的来源

[功能清单](/zh/reference/features)、[桌面端待办](/zh/reference/backlog) 和[飞书机器人设置](/zh/app/feishu)维护在 `ollupi-desktop/docs`，图片和 logo 维护在 `ollupi/docs`，构建时同步到这里。其余页面维护在 [ollupi-docs](https://github.com/0xfakeSpike/ollupi-docs) 仓库。
