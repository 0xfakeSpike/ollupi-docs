# 项目概览

Ollupi 是一个池化调度 agent 的运行时，由两个项目组成：Go 引擎 ollupi，以及基于引擎的 macOS 桌面端 ollupi-desktop。引擎接收任意数量的 agent 会话，在固定上限内调度执行，超出上限的排队等待；会话、模型调用和工具调用分别设有独立的池和上限。

| | ollupi | ollupi-desktop |
|---|---|---|
| 定位 | agent 运行时（Go 库） | macOS 桌面应用（Electron 界面与 Go 后端） |
| 适用场景 | 个人设备上的单用户部署，或服务商的多用户部署 | 个人在本机使用 agent |
| 部署形态 | 单个进程承载一个分片内的全部用户与会话 | 单用户；后端作为 sidecar 由应用托管 |
| 对外接口 | 基于 WebSocket 的 JSON-RPC 2.0 | 桌面界面、飞书机器人 |
| 仓库 | [0xfakeSpike/ollupi](https://github.com/0xfakeSpike/ollupi) | [0xfakeSpike/ollupi-desktop](https://github.com/0xfakeSpike/ollupi-desktop) |

设计动机与取舍见[agent 需要一个池子](/zh/intro/why)。

![Ollupi 架构](/images/architecture.svg)

## 两个项目的关系

桌面端是引擎的下游，依赖引擎的发布版本，自身只负责展示与装配：

- **引擎**：会话、调度、持久化、工具、权限、沙箱、记忆、定时任务、搜索与协议。
- **后端（sidecar）**：装配引擎，并提供本机特有的部分：配置文件、内置浏览器工具、飞书机器人。
- **界面**：仅通过协议与后端通信，类型定义由引擎导出的协议描述文件生成。

分层原则：逻辑归属于拥有它的那一层；引擎已实现的能力，桌面端不重复实现。

## 阅读路线

| 目标 | 入口 |
|---|---|
| 使用桌面端 | [桌面端上手](/zh/app/install) |
| 将引擎嵌入自有服务 | [把引擎嵌进服务](/zh/integrate/embed)、[协议](/zh/integrate/protocol) |
| 了解系统原理 | [核心概念](/zh/intro/concepts)、[架构总览](/zh/engine/architecture)、[执行模型](/zh/engine/execution) |
| 查看性能数据 | [性能基准](/zh/benchmarks/) |
| 查询功能清单 | [功能清单](/zh/reference/features) |
| 了解设计取舍 | [设计决策](/zh/reference/decisions)、[开发历程](/zh/reference/history)、[文章](/zh/articles/) |
| 了解后续计划 | [路线图](/zh/roadmap) |

## 文档来源

全部页面维护于 [ollupi-docs](https://github.com/0xfakeSpike/ollupi-docs) 仓库；图片与 logo 维护于引擎仓库的文档目录，构建时同步至本站。
