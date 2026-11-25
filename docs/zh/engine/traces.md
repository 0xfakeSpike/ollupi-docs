# 执行轨迹

执行轨迹是一次运行留下的完整记录：模型说了什么、思考了什么，调用了哪些工具、参数和结果是什么，谁批准了什么，用了多少 token。Ollupi 不为它另写一份：每个会话（thread）本来就是一份只追加的日志，每一步先写进日志才执行，日志和从它折叠出来的轮次（turn）、条目（item）就是轨迹。日志的写入规则与表结构见[持久化](/zh/engine/persistence)。

## 为什么这样设计

- **轨迹是先写日志再执行的副产品。** 模型的回答和其中每个工具调用在一次提交里写下，调用这时已经过权限判定；执行前追加 `ToolStarted`，结果回来追加 `ToolResult`；要审批的调用，只有日志里有了 `Decided`，`conversation.Check` 才放行 `ToolStarted`。没写进日志的一步不会执行，所以不会漏记。见[设计决策 2](/zh/reference/decisions#_2-sqlite-与先落库再执行)。
- **记录写下后不再修改。** `entries` 表只插入，不更新；审批依据的参数和执行计划就是 `ToolCall` 记下的那份。见[设计决策 16](/zh/reference/decisions#_16-审批绑定执行内容)。
- **界面看到的就是日志。** `turn/changed`、`item/changed` 来自提交后 feed 上的事件，带的是折叠后的那一行。例外是流式增量，见[没有记录的](#没有记录的)。
- **内容只在库里存一份，而且存原文。** 消息、参数和输出只在会话日志里；脱敏只发生在发给模型的那一刻，回答还原后才写进日志。见[设计决策 15](/zh/reference/decisions#_15-脱敏只在模型边界)。

代价：每一步都要写库；同一件事在 `entries` 里有一份记录，在 `turns`、`items`、`responses` 里还有一份投影；投影按 ID 原地更新，逐条的时间只留在 `entries` 里，协议读不到；轨迹没有独立于会话的保存期限，也没有稳定的导出格式。

::: info 演进
`db4bdab` 引入 `log/slog`，只记 ID 和数字；`b1f7285` 加入 OpenTelemetry 链路追踪；`f87d65a` 删掉链路追踪，`bb13d13` 删掉全部 `slog` 日志，原来只写日志的错误改由事件告诉客户端。
:::

## 记录了什么

### 日志记录

一个会话的日志按 `seq` 排成一列记录（`conversation.Entry`），每条记录有所属轮次、条目（有的话）、时刻 `At` 和内容 `Body`。`Body` 有二十一种：

| 记录 | 记下什么 |
|---|---|
| `TurnQueued` | 一轮开始：模型、角色、来自哪个定时任务 |
| `UserMessage` | 用户消息、插话或子 agent 的任务，带附件元数据；`From` 是代用户发消息的 hub 会话（协议 `sentByThreadId`） |
| `ModelResponded` | 一次模型回答：回答 ID、用量、上下文统计、服务商原生格式的回答、是否压缩 |
| `Reasoning`、`AgentMessage` | 思考（带开始和结束时刻）、回答正文，都指向所属的回答 |
| `ModelFailed` | 模型调用失败的原因 |
| `ToolCall` | 调用 ID、工具名、provider、参数原文、所属回答、注解快照、冻结的执行计划 |
| `ApprovalAsked`、`Decided` | 要审批的原因、命中的规则、内容、建议的规则、是否全权（`Escalated`）；用户的决定和做决定的用户 |
| `ToolStarted` | 调用开始执行 |
| `InputAsked`、`Answered` | 工具向用户提的问题；回答或跳过 |
| `ToolResult` | 输出和产物，或错误；是否被拒 |
| `ChildLaunched`、`ChildReported` | 启动的子会话；子 agent 的任务和报告，或失败原因 |
| `TaskLaunched`、`TaskReported` | 后台任务的 ID；结束时的输出或错误，`Launch` 指回原调用 |
| `Compacted` | 压缩的摘要、覆盖到哪一条、上下文统计 |
| `Recalled` | 载入上下文的记忆快照：全文和每条记忆 |
| `Notice` | 运行时告诉模型的话，例如工具为什么停了 |
| `TurnEnded` | 一轮结束：`completed`、`failed` 或 `interrupted`，以及原因 |

### 条目

条目是从记录折叠出来的，九种类型：

| 类型 | 轨迹里能看到什么 |
|---|---|
| `userMessage` | 消息和插话的正文、附件元数据；`sentByThreadId` 指代发的 hub 会话 |
| `agentMessage` | 模型回答的正文 |
| `reasoning` | 模型的思考。`startedAt` 是第一个思考增量到达的时刻，`completedAt` 是随后第一个正文增量到达的时刻 |
| `toolCall` | 一次调用从记下到结束的全部信息，见下表 |
| `agentReport` | 一份报告：`ChildReported` 折叠出的带 `text`（任务）、`childThreadId`、`launchItemId`；`TaskReported` 折叠出的带 `taskId`、`launchItemId`、结果。两者都置原调用的 `reported` |
| `contextCompaction` | 一次压缩：`text` 是摘要，带 `contextStats` |
| `memoryContext` | 记忆快照：`text` 是放进上下文的全文，`memory` 列出每条记忆的 ID、主题、内容和范围 |
| `notice` | 运行时写给模型的通知，以 `[runtime]` 开头 |
| `error` | 模型调用失败的原因 |

状态有五种：`pending`、`inProgress`、`completed`、`failed`、`declined`。每条都有 `startedAt`，结束的有 `completedAt`，失败或被拒的有 `error`。

计划和提问没有单独的类型：`update_plan` 和 `request_user_input` 都是 `toolCall`，计划在参数里，回答就是工具结果。子 agent 的启动也是 `toolCall`，`childThreadId` 指向子会话（见[执行模型](/zh/engine/execution#子-agent)）。

`toolCall` 条目上的字段：

| 字段 | 内容 |
|---|---|
| `callId`、`tool`、`server` | 模型给的调用 ID、工具名、提供这个工具的 provider |
| `arguments` | 参数原文（JSON 字符串，已还原脱敏） |
| `annotations` | 写下时工具声明的注解快照（只读、开放世界等） |
| `preparedExecution` | `Prepare` 冻结的执行计划，内容由工具决定，例如命令的工作目录、程序与参数、环境、超时、沙箱，或文件的 diff |
| `approval` | `approvalId`、`reason`、`rule`、`content`、`suggestedRules`、`availableDecisions`、`escalated`、`askedAt`，决定后加上 `decision`、`decidedBy`、`decidedAt` |
| `input` | 向用户的提问：`request`、`askedAt`、`answered` |
| `result` | `output`（JSON）和 `artifacts`（例如激活的技能） |
| `childThreadId`、`taskId` | 启动的子会话；后台任务的 ID |
| `error` | 失败、被拒或被跳过的原因 |

### 每次模型调用

一次调用产生的 `reasoning`、`agentMessage` 和若干 `toolCall` 共用一个 `responseId`，由引擎生成，不是服务商返回的 ID。这次调用记在 `ModelResponded` 里，折叠进 `responses` 表，也进所属轮次的列表。

`usage` 是四个 token 数（`inputTokens`、`cachedInputTokens`、`cacheWriteInputTokens`、`outputTokens`）；`contextStats` 是这次请求的组成：`model`、`budgetTokens`、`compactAtTokens`、`systemTokens`、`messagesTokens`、`memoryTokens`、`toolsTokens`、`estimatedTokens`、`calibratedTokens`，以及 `globalMemory`、`localMemory` 各自的 token 数和记忆 ID。同一条记录还存服务商原生格式的回答（Anthropic、Gemini 原生接口），原样回放给同类服务商，思考的签名才有效，不发给客户端，见[模型接入](/zh/engine/models)；压缩的回答带标记，不算进这一轮的模型调用数。

这些 token 数也进派生表 `usage`：`usage.Recorder` 订阅 feed，从 `modelResponded` 记录补出，一条回复一行，行 ID 是 `<thread>:<seq>`，`source` 取 `response` 或 `compaction`。写日志的路径不碰这张表，所以刚结束的一轮可能晚一点才出现在 `usage/query` 里；记录器用 `MissingUsage` 每批 256 条扫描缺失的行，线程出错后隔 30 秒再试。行从不删除。表结构与查询见[用量](/zh/integrate/protocol/usage)。

### 轮次

轮次从 `TurnQueued` 和 `TurnEnded` 之间的记录折叠出来，协议里的 `TurnRow` 有 `status`（`queued`、`inProgress`、`completed`、`failed`、`interrupted`，见[执行模型](/zh/engine/execution#轮次状态机)）、`model` 与 `agent`、`usage`（所有回答含压缩的用量之和）、`responses`、`error`，以及 `cronJobId`、`queuedAt`、`completedAt`。用量和回答在同一次提交里折叠，进程中途退出也不会少记。

### 没有记录的

- **流式增量。** 增量只作为 feed 事件推给客户端（`item/agentMessage/delta`、`item/reasoning/textDelta`），完整文本在回答结束时一次写下。调用出错时只追加 `ModelFailed`，已推出的文本不在库里；进程中退出时这次调用什么也没留下。调用进行中用户插话时，这一批回答整批不写（工具调用也不写），下一步带着新消息重新调模型。
- **发给模型的请求本身。** 系统提示词和工具列表每一步重新算，不落库，`contextStats` 只留 token 数；脱敏后的消息也不落库。库里的记录能重建对话内容，但不能逐字还原某一次请求。
- **协议读得到的状态变迁。** `entries` 表只写不读，`store.Reader` 和协议都只读折叠后的投影，所以调用何时开始执行（`ToolStarted`）只能直接查表。
- **槽位。** 会话什么时候拿到、放出槽位不写进日志，排队和运行的时间从轨迹里分不开。
- **记忆提取的调用。** 后台提取不属于任何轮次，不写记录，也不留用量，`memory_state` 只记最近一次成功、失败和跳过，见[记忆](/zh/engine/memory#失败重试和跳过)。

### 脱敏前后各存在哪里

原值只在日志记录和投影里。占位符版本只在发出的请求和回答里，原生回答保存服务商的原始回答。对照只在 `redact.Redactor` 的内存里，每步新建一个；HMAC 密钥是用户设置里的 `RedactionKey`，`settings/read` 不返回。细节见[脱敏](/zh/engine/redaction#替换的时机和位置)。

## 怎样读回

| 途径 | 读到什么 |
|---|---|
| `thread/read`、`thread/resume` | 会话行、一页条目、它们所属的轮次和没结束的轮次、`hasMore`、读取时的 `seq`。条目从新到旧取，按 `seq` 升序返回，`limit` 默认 100、最大 500，用 `beforeSeq` 往前翻；一页超过 4 MiB 时从旧的一端截断；不带原生回答。参数见[协议](/zh/integrate/protocol/threads) |
| `turn/changed`、`item/changed` | 提交后变了的轮次和条目，带提交的 `seq`，加上流式增量。事件不缓存，断线期间的要重读 |
| feed 和 `store.Reader` | 宿主可以 `Feed.Subscribe` 一个用户的事件，或在 `store.Read` 里调 `View`、`Page`、`Thread` |
| `read_tool_output` | 模型用的工具：按条目 ID 和字符偏移读回被截短的输出或子 agent 报告，只读本会话，见[工具系统](/zh/engine/tools#输出交给模型) |
| `entries` 表 | 直接查 SQLite，才能看到每条记录和它的时刻 |

评测时 `eval/main.go` 的 `-out` 把每一轮和它的条目写成 JSON，桌面端能导出 Markdown 或 JSON。

全文搜索只覆盖用户消息和回答，不搜工具调用和思考，见[搜索](/zh/engine/search)。

## 用在哪里

- **重启恢复。** 运行接手会话时按日志决定怎么处理：`pending` 的调用照常执行，已开始未结束的记为被切断。见[执行模型](/zh/engine/execution#定时任务与重启)。
- **继续运行与界面。** 每一步都从日志读出下一步做什么，再从投影组装提示词；桌面端的会话页就是条目按 `seq` 排出来的，重连时用 `thread/resume` 重读。
- **长期记忆。** 提取读已结束轮次里的条目，带上轮次的结束状态，每条记忆的来源指回这些条目。见[记忆](/zh/engine/memory#取证据)。
- **评测与自我改进。** `eval -out` 留下每次试验的轨迹供 `eval/trace.py` 查看；按稳定格式导出、用来回放或重跑任务、让 agent 根据自己的轨迹改进，这些还没做，见[路线图](/zh/roadmap)。

## 边界与已知问题

- **没有稳定的导出格式。** 引擎本身没有导出方法。桌面端的 JSON 导出是读到的会话原样序列化，没有版本号，也不能导回；`eval -out` 只覆盖一轮。
- **导出不脱敏。** 导出的是库里的原文，包括密钥、手机号这类值；路线图里"导出前先脱敏"还没做。
- **轨迹随会话删除而删除。** 删除会话时，日志、投影、子会话、后台任务和定时任务随外键级联删除；链到这个会话或其子会话的待办不删，只解开关联，`handed` 的回到 `open`；附件按会话前缀删除；附件删除失败时 `thread/delete` 报错说附件没删。用量行不随会话删除，也没有单独的归档或保存期限。
- **存储随历史增长。** 每一步既写记录又写投影；压缩只影响发给模型的内容，旧记录和条目都留在库里。
- **逐条时间读不出来。** 算不出一个调用等了多久才开始执行，也算不出一轮排队和在槽位里各花了多久，见[没有记录的](#没有记录的)。
- **几乎没有日志，也没有指标和链路追踪。** 引擎只在用量记录器写失败或读不出一条回答时用 `slog` 打一条警告，没有别的日志，也没有暴露队列长度、槽位占用的指标，宿主只能订阅 feed 或读库。路线图列为[可观测性](/zh/roadmap#_4-可观测性)。

## 代码位置

| 仓库 | 路径 | 职责 |
|---|---|---|
| ollupi | `conversation/entry.go`、`conversation/view.go` | 记录的种类和字段；折叠成 `Turn`、`Item`、`Response`、`Approval`，`AwaitsReport` |
| ollupi | `store/sqlite/conversations.go`、`store/sqlite/usage.go` | 写 `entries` 和投影、读视图和分页、`CreateTask`/`StartTask`/`DeleteTask`；`MissingUsage` |
| ollupi | `store/sqlite/migrations/0004_tasks.sql`、`0011_usage.sql` | `tasks`、`usage` 两张表和索引 |
| ollupi | `run/model.go`、`run/tools.go` | 回答、思考时刻、流式增量、脱敏与还原、被抢先的回复整批不写；调用的记录与执行、后台任务的启动与报告 |
| ollupi | `usage/usage.go` | 从 `modelResponded` 补出 `usage` 表 |
| ollupi | `prompt/observation.go` | `OutputText`、`clip`、`maxObservationTokens`、`endedObservationTokens`、`minOutputTokens` |
| ollupi | `gateway/wire.go`、`gateway/threads.go` | `TurnRow`、`ItemRow`、`ResponseRow`；`thread/read`、`thread/resume` |
| ollupi | `tool/builtin/outputs/outputs.go` | `read_tool_output` |
| ollupi | `eval/main.go`、`eval/trace.py` | 评测时留下和查看轨迹 |
| ollupi-desktop | `apps/desktop/src/renderer/src/domains/export.ts`、`threadMarkdown.ts` | 导出 Markdown 和 JSON |
