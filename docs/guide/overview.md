# 项目概览

Ollupi 由两个项目组成：一个 Go agent 引擎，和一个基于引擎的 macOS 桌面端。

| | ollupi | ollupi-desktop |
|---|---|---|
| 是什么 | Go 库，agent 运行时 | Electron 应用 + Go 后端 `ollupid` |
| 面向谁 | 构建大规模个人 agent 服务的云服务商 | 在自己 Mac 上用 agent 的人 |
| 运行形态 | 一个进程托管一个分片里的所有用户和会话 | 本机一个用户，后端作为 sidecar 由应用托管 |
| 对外接口 | WebSocket 上的 JSON-RPC 2.0 | 桌面界面、飞书机器人 |
| 仓库 | [0xfakeSpike/ollupi](https://github.com/0xfakeSpike/ollupi) | [0xfakeSpike/ollupi-desktop](https://github.com/0xfakeSpike/ollupi-desktop) |

## 要解决的问题

给每个 agent 开一个虚拟机或容器，隔离简单，但成本跟着会话数走：不活跃的会话要么占着进程，要么冷启动重建；等用户回答时进程挂起，内存还在；重启时进行中的工作中断。

个人 agent 的大部分时间都在等：等用户、等审批、等子代理、等定时任务到点。Ollupi 的做法是不隔离进程，而是池化 runtime，把运行状态放进数据库：

- 每一步先写库再执行，调度状态不留在内存，所以进程随时可以死，重启后接着跑。
- 等待中的会话离开执行池，只剩数据库记录，不占内存和算力。
- 所有可运行的轮次进同一个队列，按槽位调度；模型调用按连接限流，和服务商的账户配额对齐。

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
| 用桌面端 | [桌面端上手](/guide/desktop-quickstart) |
| 把引擎嵌进自己的服务 | [把引擎嵌进服务](/guide/engine-quickstart)、[协议](/engine/protocol) |
| 理解系统怎么工作 | [核心概念](/guide/concepts)、[架构总览](/engine/architecture)、[执行模型](/engine/execution) |
| 看性能数据 | [性能基准](/engine/benchmarks) |
| 查某个功能有没有 | [功能清单](/reference/features) |
| 了解为什么这样设计 | [设计决策](/notes/decisions)、[开发历程](/notes/history) |

## 文档的来源

[功能清单](/reference/features)、[路线图](/reference/roadmap) 和[飞书机器人设置](/desktop/feishu)维护在 `ollupi-desktop/docs`，图片和 logo 维护在 `ollupi/docs`，构建时同步到这里。其余页面维护在 [ollupi-docs](https://github.com/0xfakeSpike/ollupi-docs) 仓库。
