# 核心概念

Ollupi 的数据按四层组织：用户拥有工作区，工作区下有会话，会话由一轮一轮组成，每一轮产生一串条目。

```mermaid
flowchart LR
  U["用户"] --> W["工作区"]
  U --> T["会话"]
  W --> T
  T --> R["一轮"]
  R --> I["条目"]
```

## 工作区（workspace）

用户沙箱（`Box`）里的一个项目文件夹：桌面端是本机的文件夹，云端是用户自己那台沙箱机器里的路径。工具在这里读写文件、执行命令，权限规则可以按工作区设置。会话可以属于一个工作区，也可以不属于任何工作区（general）。

## 执行环境（environment）

会话的命令和文件工具在哪里运行。每个用户都有"这台机器"这个环境，还可以登记自己的云沙箱。会话开始时选定一个环境，之后不再改变，子 agent 跟随父会话；不选时在这台机器上运行。环境怎样对应到一台具体的机器由宿主决定。见[网关协议](/zh/integrate/protocol#执行环境)。

## 会话（thread）

一段连续的对话。子 agent 和定时任务用的也是普通会话，引擎没有为它们设特殊运行机制。

会话的状态：

| 状态 | 含义 |
|---|---|
| `idle` | 没有进行中的轮次 |
| `active` | 有轮次在跑 |
| `waitingOnApproval` | 等用户审批 |
| `waitingOnUserInput` | 等用户回答问题 |

## 轮次（turn）

用户发一条消息到 agent 给出结果，是一轮。一轮可能调用多次模型和工具。同一个会话同一时间只有一轮在进行，其余的排队。

| 状态 | 含义 | 占槽位 |
|---|---|---|
| `queued` | 排在同一会话的前一轮之后 | 否 |
| `ready` | 可以运行，等空闲槽位 | 否 |
| `inProgress` | 正在运行 | 是 |
| `waitingOnApproval` | 等审批 | 否 |
| `waitingOnUserInput` | 等回答 | 否 |
| `waitingOnAgent` | 等子 agent | 否 |
| `completed` / `interrupted` / `failed` | 结束 | 否 |

状态怎么转换，见[执行模型](/zh/engine/execution)。

## 条目（item）

一轮里发生的每件事都是一条条目，界面的时间线就是条目列表。

| 类型 | 内容 |
|---|---|
| `userMessage` | 用户消息 |
| `agentMessage` | 模型给用户的回复 |
| `reasoning` | 模型的思考过程 |
| `toolCall` | 一次工具调用 |
| `contextCompaction` | 上下文压缩 |
| `memoryContext` | 载入的记忆 |
| `error` | 错误 |

条目有自己的状态：`pending`、`inProgress`、`completed`、`failed`、`declined`。其中 `pending` 和 `inProgress` 的区别决定了重启后工具能不能重做：`pending` 还没执行，照常运行；`inProgress` 可能已经生效，不会再跑一次。

## 槽位（slot）

执行池的并发单位。占着槽位的轮次才在运行，默认 32 个。等待中的轮次让出槽位，所以槽位数限制的是同时在跑的轮次，不是会话总数。

模型调用另有一层限制：按模型连接算，默认每连接 4 个。工具执行不占这个名额。

## 分片（shard）

一个数据库是一个分片，一个分片里有多个用户，共用同一组表，数据按用户隔离。同一时间只有一个进程持有分片的租约。分片数决定容量。桌面端只有一个分片和一个默认用户。详见[多用户与分片](/zh/engine/sharding)。

## 审批和提问

工具调用可能需要用户批准，agent 也可以用 `request_user_input` 向用户提结构化的问题。这两种情况下轮次都会让出槽位，用户处理之后回到队列。详见[权限与审批](/zh/engine/permissions)。

## 子 agent

`Agent` 工具派生的子任务。子 agent 是一个普通会话，它的轮次和其他轮次一起排队，只是优先级低于普通会话。父轮次等待时处于 `waitingOnAgent`，不占槽位，子 agent 的结果作为工具调用的结果返回。

## 记忆和技能

记忆是后台从已结束的轮次里提炼出的长期信息，分偏好、决定、流程、事实四类，见[记忆](/zh/engine/memory)。

技能是一个含 `SKILL.md` 的文件夹，agent 按需激活，见[技能与 MCP](/zh/engine/skills-mcp)。

## 相关页面

更多术语见[术语表](/zh/reference/glossary)。
