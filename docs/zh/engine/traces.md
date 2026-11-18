# 执行轨迹

执行轨迹是一次运行留下的完整记录：模型说了什么、思考了什么，调用了哪些工具、参数和结果是什么，谁批准了什么，用了多少 token。Ollupi 不为它另写一份。每个会话（thread）本来就是一份只追加的日志，每一步先写进日志才执行，所以日志和从它折叠出来的轮次（turn）、条目（item）就是轨迹。引擎没有别的轨迹：不写进程日志，也不接 OpenTelemetry。这一页讲轨迹里有什么、没有什么、怎样读回、拿来做什么。日志的写入规则和表结构见[持久化](/zh/engine/persistence)，这里不重复。

## 为什么这样设计

- **轨迹是先写日志再执行的副产品。** 模型的回答和其中每个工具调用在一次提交里写下，调用这时已经过权限判定；执行前追加 `ToolStarted`，结果回来追加 `ToolResult`；要审批的调用，只有日志里有了批准的 `Decided`，`conversation.Check` 才放行 `ToolStarted`。没写进日志的一步不会执行，所以不会漏记，也不会出现"记的和做的不一样"。这条规则本来是为崩溃恢复定的，见[设计决策 2](/zh/reference/decisions#_2-sqlite-与先落库再执行)；轨迹是同一份数据的另一种用法，不需要额外的写入。
- **记录写下后不再修改。** `entries` 表只插入，不更新。每条记录都要接在调用当前的状态之后（`conversation.Check`），审批依据的参数和执行计划就是 `ToolCall` 记下的那份。所以轨迹里审批时看到的内容就是执行的内容。见[设计决策 16](/zh/reference/decisions#_16-审批绑定执行内容)。
- **界面看到的就是日志。** 网关发出的 `turn/changed`、`item/changed` 都来自提交之后 feed 上的事件，带的是折叠后的那一行。界面的时间线和库里的轨迹是同一份，断线后重读也一样。唯一的例外是流式增量，见[没有记录的](#没有记录的)。
- **内容只在库里存一份。** 引擎不写进程日志，也不发链路追踪，消息、参数和输出只在会话日志里。宿主要观察运行，就订阅 feed 或读库。
- **库里存原文。** 脱敏只发生在发给模型的那一刻，回答还原后才写进日志，所以轨迹对用户和工具可读。代价是库里是明文。见[设计决策 15](/zh/reference/decisions#_15-脱敏只在模型边界)。

代价：每一步都要写库；同一件事在 `entries` 里有一份记录，在 `turns`、`items`、`responses` 里还有一份折叠后的投影；投影按 ID 原地更新，逐条的时间只留在 `entries` 里，而协议读不到它；轨迹没有独立于会话的保存期限，也没有稳定的导出格式。

::: info 演进
- `600d071` 引入 `log/slog`，只记 ID 和数字，并加了测试确认消息、参数和输出不进日志。
- v0.13.0 的 `2c2d8cd` 加入 OpenTelemetry 链路追踪：经全局 TracerProvider，每个轮次一条 trace，trace ID 就是轮次 ID，里面有等待、运行、模型调用和它的每次 HTTP 尝试、工具调用、压缩和沙箱命令，客户端的每个请求一个 span。
- v0.14.0 的 `4be2eed` 删掉了链路追踪；`34d96a9` 删掉了全部 `slog` 日志，原来只写日志的错误改由事件告诉客户端，或在无事可做时忽略。`go.mod` 里剩下的 `go.opentelemetry.io` 都是间接依赖，引擎代码不导入它们。
:::

## 记录了什么

### 日志记录

一个会话的日志按 `seq` 排成一列记录（`conversation.Entry`），`seq` 在会话内递增。每条记录有它所属的轮次、条目（有的话）、写下的时刻 `At` 和内容 `Body`。`Body` 有十九种：

| 记录 | 记下什么 |
|---|---|
| `TurnQueued` | 一轮开始：模型、角色、来自哪个定时任务 |
| `UserMessage` | 用户消息、插话或子 agent 的任务，带附件的元数据 |
| `ModelResponded` | 一次模型回答：回答 ID、用量、上下文统计、服务商原生格式的回答、是不是压缩 |
| `Reasoning`、`AgentMessage` | 思考（带开始和结束时刻）、回答正文，都指向所属的回答 |
| `ModelFailed` | 模型调用失败的原因 |
| `ToolCall` | 调用 ID、工具名、提供它的 provider、参数原文、所属回答、注解快照、冻结的执行计划 |
| `ApprovalAsked`、`Decided` | 要审批的原因、命中的规则、审批内容、建议的规则；用户的决定和做决定的用户 |
| `ToolStarted` | 调用开始执行 |
| `InputAsked`、`Answered` | 工具向用户提的问题；用户的回答，或跳过 |
| `ToolResult` | 输出和产物，或错误；是否被拒 |
| `ChildLaunched`、`ChildReported` | 启动的子会话；子 agent 的任务和报告，或它失败的原因 |
| `Compacted` | 压缩的摘要、它覆盖到哪一条、上下文统计 |
| `Recalled` | 载入上下文的记忆快照：全文和每条记忆 |
| `Notice` | 运行时告诉模型的话，例如工具为什么停了 |
| `TurnEnded` | 一轮结束：`completed`、`failed` 或 `interrupted`，以及原因 |

### 条目

条目是从记录折叠出来的，九种类型：

| 类型 | 轨迹里能看到什么 |
|---|---|
| `userMessage` | 用户消息和插话的正文；`attachments` 是附件的元数据，文件本身在附件存储里 |
| `agentMessage` | 模型回答的正文 |
| `reasoning` | 模型的思考。`startedAt` 是第一个思考增量到达的时刻，`completedAt` 是随后第一个正文增量到达的时刻；没有这些增量时，退回请求发出和回答结束的时刻 |
| `toolCall` | 一次工具调用从记下到结束的全部信息，见下表 |
| `agentReport` | 一个子 agent 的报告：`text` 是任务，`result` 是报告，`childThreadId` 和 `launchItemId` 指向子会话和启动它的调用 |
| `contextCompaction` | 一次压缩：`text` 是摘要，带这次压缩的 `contextStats` |
| `memoryContext` | 载入的记忆快照：`text` 是放进上下文的全文，`memory` 列出每条记忆的 ID、主题、内容和范围 |
| `notice` | 运行时写给模型的通知，以 `[runtime]` 开头 |
| `error` | 模型调用失败的原因 |

状态有五种：`pending`、`inProgress`、`completed`、`failed`、`declined`。每条都有 `startedAt`（第一条记录的时刻），结束的有 `completedAt`，失败或被拒的有 `error`。

计划和提问没有单独的类型。`update_plan` 和 `request_user_input` 都是 `toolCall`：计划在参数里，用户的回答就是工具结果。子 agent 的启动也是一次 `toolCall`，`childThreadId` 指向子会话，子 agent 自己的轨迹在那个会话里（见[执行模型](/zh/engine/execution#子-agent)）。

`toolCall` 条目上的字段：

| 字段 | 内容 |
|---|---|
| `callId`、`tool`、`server` | 模型给的调用 ID、工具名、提供这个工具的 provider |
| `arguments` | 模型给的参数原文（JSON 字符串，已还原脱敏） |
| `annotations` | 写下时工具声明的注解快照（只读、开放世界等） |
| `preparedExecution` | `Prepare` 冻结的执行计划，内容由工具决定，例如命令的工作目录、程序和参数、环境、超时、沙箱与提权，或文件的 diff |
| `approval` | 审批记录：`approvalId`、`reason`、`rule`、`content`、`suggestedRules`、`availableDecisions`、`askedAt`，决定后加上 `decision`、`decidedBy`（做决定的用户）、`decidedAt` |
| `input` | 向用户的提问：`request`、`askedAt`、`answered` |
| `result` | `output`（JSON）和 `artifacts`（例如激活的技能） |
| `childThreadId` | 启动的子会话 |
| `error` | 失败、被拒或被跳过的原因 |

### 每次模型调用

一次模型调用产生的 `reasoning`、`agentMessage` 和若干 `toolCall` 共用一个 `responseId`。这个 ID 由引擎为每次调用生成，不是服务商返回的 ID。

这次调用本身记在 `ModelResponded` 里，折叠进 `responses` 表，也进它所属轮次的 `responses` 列表：

| 字段 | 内容 |
|---|---|
| `usage` | `inputTokens`、`cachedInputTokens`、`cacheWriteInputTokens`、`outputTokens`。服务商没有报用量时为零 |
| `contextStats` | 这次请求的组成：`model`、`budgetTokens`、`compactAtTokens`、`systemTokens`、`messagesTokens`、`memoryTokens`、`toolsTokens`、`estimatedTokens`、`calibratedTokens`，以及 `globalMemory`、`localMemory` 各自的 token 数和记忆 ID |
| 原生回答 | 服务商自己格式的回答记录（Anthropic、Gemini 原生接口），原样回放给同类服务商，思考的签名才有效。不发给客户端，见[模型接入](/zh/engine/models) |
| 压缩标记 | 压缩的回答带这个标记，不算进这一轮的模型调用数 |

压缩的回答同样有 `responseId`，`contextCompaction` 条目指向它。

### 轮次

轮次从 `TurnQueued` 和 `TurnEnded` 之间的记录折叠出来，协议里的 `TurnRow` 有这些字段：

| 字段 | 内容 |
|---|---|
| `status` | `queued`、`inProgress`、`completed`、`failed`、`interrupted`，见[执行模型](/zh/engine/execution#轮次状态机) |
| `model`、`agent` | 这一轮用的模型和连接；角色 |
| `usage` | 这一轮所有模型回答（含压缩）的用量之和 |
| `responses` | 每次模型回答的 ID、用量和上下文统计 |
| `error` | 失败或中断的原因 |
| `cronJobId` | 由定时任务发出时非空 |
| `queuedAt` | 写下 `TurnQueued` 的时刻 |
| `completedAt` | 写下 `TurnEnded` 的时刻 |

轮次的用量和回答在同一次提交里折叠，不会因为进程中途退出而少记。

### 没有记录的

- **流式增量。** 流式输出时，增量只作为 feed 上的事件推给客户端（`item/agentMessage/delta`、`item/reasoning/textDelta`），完整文本在回答结束时一次写下。模型调用出错时只追加 `ModelFailed`，已推给界面的部分文本不在库里；进程在流式中途退出时，这次调用什么也没留下。
- **发给模型的请求本身。** 系统提示词和工具列表每一步重新算，不落库，`contextStats` 只留它们的 token 数。脱敏后的消息也不落库。所以库里的记录能重建对话内容，但不能逐字还原某一次请求。
- **协议读得到的状态变迁。** 每条记录都有时刻，但 `entries` 表只写不读：`store.Reader` 和协议都只读折叠后的投影。投影上只有条目的开始和结束、审批的提出和决定、提问的提出这几个时刻，调用什么时候开始执行（`ToolStarted`）只能直接查 `entries` 表。
- **槽位。** 会话什么时候拿到、放出槽位不写进日志，排队和运行的时间从轨迹里分不开。
- **记忆提取的调用。** 后台提取不属于任何轮次，不写记录，也不留用量；`memory_state` 只记最近一次成功、失败和跳过，见[记忆](/zh/engine/memory#失败重试和跳过)。

### 脱敏前后各存在哪里

| 内容 | 位置 |
|---|---|
| 原值 | 库里：日志记录和投影里的正文、参数、结果 |
| 占位符版本 | 只在发出的请求和收到的回答里，不落库。例外是原生回答：它保存服务商的原始回答，里面的占位符原样保留 |
| 占位符和原值的对照 | `redact.Redactor` 在内存里，运行每一步新建一个，不落库 |
| HMAC 密钥 | 用户设置里的 `RedactionKey`，每用户一个，`settings/read` 不返回它 |

细节见[脱敏](/zh/engine/redaction#替换的时机和位置)。

## 怎样读回

| 途径 | 读到什么 |
|---|---|
| `thread/read`、`thread/resume` | 会话行、一页条目、这些条目所属的轮次和没结束的轮次、`hasMore`，以及读取时的 `seq`。条目从新到旧取，按 `seq` 升序返回，`limit` 默认 100、最大 500，用 `beforeSeq` 往前翻；一页超过 4 MiB 时从旧的一端截断。不带原生回答。参数见[协议](/zh/integrate/protocol/threads) |
| `turn/changed`、`item/changed` | 每次提交后变了的轮次和条目，带提交的 `seq`；加上流式增量。事件不缓存，断线期间的要重读 |
| feed 和 `store.Reader` | 嵌入引擎的宿主可以 `Feed.Subscribe` 一个用户的事件，或在 `Store.Read` 里调 `View`、`Page`、`Thread` |
| `eval -out` | `eval/main.go` 每次提交后把这一轮和它的条目重写成一个 JSON 文件，每次回答的上下文统计放在它的第一个条目上；`eval/trace.py` 把它和测试结果一起打印出来 |
| 桌面端导出 | 会话页可以导出 Markdown 或 JSON，导出前先用 `thread/read` 每页 100 条读完整个会话（`domains/export.ts`、`domains/threadMarkdown.ts`） |
| `read_tool_output` | 模型用的工具。上下文里被截短的工具输出或子 agent 报告，按条目 ID 和字符偏移读回库里的完整结果，只能读本会话的，见[工具系统](/zh/engine/tools#输出截断) |
| `entries` 表 | 直接查 SQLite，才能看到每条记录和它的时刻 |

全文搜索只覆盖用户消息和回答，不搜工具调用和思考，见[搜索](/zh/engine/search)。

## 用在哪里

- **重启恢复。** 运行接手会话时按日志决定怎么处理：`pending` 的调用照常执行，已开始未结束的记为被切断、提示模型先核实。见[执行模型](/zh/engine/execution#重启恢复)。
- **继续运行。** 每一步都从日志读出下一步做什么，再从投影组装提示词。停放再唤醒的轮次靠的就是这份记录。原生回答让思考的签名在下一次请求里仍然有效。
- **界面时间线。** 桌面端的会话页就是条目按 `seq` 排出来的，重连时用 `thread/resume` 重读。
- **长期记忆。** 提取读已结束轮次里的 `userMessage`、`agentMessage`、`toolCall`、`error` 条目，只取已经结束的，带上轮次的结束状态。每条记忆的来源指回这些条目。见[记忆](/zh/engine/memory#取证据)。
- **评测与自我改进。** `eval` 用 `-out` 留下每次试验的轨迹供 `eval/trace.py` 查看。路线图的下一步是把轨迹当数据：按稳定的格式导出，用来回放或重跑任务、给改动打分，再让 agent 根据自己的轨迹提出改进。这些还没做，见[路线图](/zh/roadmap)。

## 边界与已知问题

- **没有稳定的导出格式。** 引擎本身没有导出方法。桌面端的 JSON 导出是读到的会话原样序列化，没有版本号，字段随引擎变化，也不能导回；`eval -out` 只覆盖一轮。
- **导出不脱敏。** 导出的是库里的原文，包括密钥、手机号这类值。路线图里"导出前先脱敏"是计划，还没做。
- **轨迹随会话删除而删除。** 删除会话时，日志、投影、子会话和定时任务随外键级联删除，附件按会话前缀删除。附件删除失败时会话已经删掉，`thread/delete` 报错说附件没删。没有单独的归档或保存期限。
- **存储随历史增长。** 每一步既写记录又写投影；压缩只影响发给模型的内容，旧记录和条目都留在库里。引擎没有清理旧记录的机制。
- **逐条时间读不出来。** 协议只给投影上的几个时刻，算不出一个调用等了多久才开始执行，也算不出一轮在队列里和在槽位里各花了多久，见[没有记录的](#没有记录的)。
- **增量和请求本身不落库。** 模型调用失败或流式中途崩溃会丢掉已显示的部分文本；系统提示词和工具列表不落库，不能逐字还原某一次请求。
- **没有日志、指标和链路追踪。** 引擎不写日志，没有暴露队列长度、槽位占用这类指标，也没有链路追踪的接口，宿主只能订阅 feed 或读库。路线图把它列为[可观测性](/zh/roadmap#_4-可观测性)。

## 代码位置

| 仓库 | 路径 | 职责 |
|---|---|---|
| ollupi | `conversation/entry.go` | 记录的种类和字段、`Usage`、`ContextStats` |
| ollupi | `conversation/view.go` | 折叠：`Turn`、`Item`、`Response`、`Approval` |
| ollupi | `conversation/check.go` | 记录能不能追加 |
| ollupi | `store/sqlite/conversations.go` | 写 `entries` 和投影、读视图和分页 |
| ollupi | `run/model.go` | 回答的记录、思考的时刻、流式增量、脱敏与还原 |
| ollupi | `run/tools.go` | 调用的记录、执行、结果 |
| ollupi | `gateway/wire.go` | `TurnRow`、`ItemRow`、`ResponseRow` |
| ollupi | `gateway/threads.go` | `thread/read`、`thread/resume`、分页上限 |
| ollupi | `tool/builtin/outputs/outputs.go` | `read_tool_output` |
| ollupi | `eval/main.go`、`eval/trace.py` | 评测时留下和查看轨迹 |
| ollupi-desktop | `apps/desktop/src/renderer/src/domains/export.ts`、`threadMarkdown.ts` | 导出 Markdown 和 JSON |
