# 执行轨迹

执行轨迹是一次运行留下的完整记录：模型说了什么、推理了什么，调用了哪些工具、参数和结果是什么，谁批准了什么，用了多少 token。Ollupi 不为它单独写日志。每一步本来就要先写进数据库才能执行，库里的会话（thread）、轮次（turn）和条目（item）就是轨迹。这一页讲轨迹里有什么、没有什么、怎样读回、拿来做什么。表结构见[持久化](/zh/engine/persistence#表和关系)，这里不重复列。

## 为什么这样设计

- **轨迹是先落库再执行的副产品。** 模型回答先记成条目，回答里的工具调用记成 `pending`；执行前改成 `inProgress`，结果回来写 `completed` 或 `failed`；审批决定写在调用条目上之后才放行（顺序见[持久化](/zh/engine/persistence#先落库再执行的顺序)）。没写进库的一步不会执行，所以不会漏记，也不会出现"记的和做的不一样"。这条规则本来是为崩溃恢复定的，见[设计决策 2](/zh/reference/decisions#_2-sqlite-与先落库再执行)；轨迹是同一份数据的另一种用法，不需要额外的写入。
- **事件跟在写库之后。** 引擎发出的 `item/started`、`item/updated`、`item/completed` 都是 `RecordItem` 成功之后由 `recorder` 发出的（`agent/run.go`），带的就是库里存下的那一行。界面看到的时间线和库里的轨迹是同一份，断线后重读也一样。唯一的例外是增量文本，见[没有记录的](#没有记录的)。
- **进程日志不带内容。** README 对比的另一种做法（每个 agent 一个进程或容器）把调度状态放在进程内存里，那种做法要留下轨迹，只能另写一份日志，和执行走两条路径。Ollupi 的日志（`log/slog`）只记 ID 和数字：轮次开始与结束、每次模型调用的耗时、token 和结束原因、每次工具调用的耗时和成败。消息、参数和输出不进日志，有测试守着（`agent/deferred_test.go`）。内容只在库里存一份。
- **记下的执行内容不能改。** `saveItemOf` 拒绝修改条目的会话、类型和轮次；条目一旦有了 `prepared_execution`，参数、工具名和冻结内容都不能再改。所以轨迹里审批时看到的内容就是执行的内容。见[设计决策 16](/zh/reference/decisions#_16-审批绑定执行内容)。
- **库里存原文。** 脱敏只发生在发给模型的那一刻，回答还原后才写库，所以轨迹对用户和工具可读。代价是库里是明文。见[设计决策 15](/zh/reference/decisions#_15-脱敏只在模型边界)。

代价：每一步都写库，[基准](/zh/benchmarks/#容量)里一轮（三次模型调用、两次工具调用，模拟模型、改动前测得）约 68 次读、15 次写、11.6 KB 磁盘；条目按 ID 原地更新，轨迹只留每条的最终状态和起止时间，不留状态变迁；轨迹没有独立于会话的保存期限，也没有稳定的导出格式。

::: info 演进
来自 `600d071`：加了测试，确认消息、参数和输出不进日志。
:::

## 记录了什么

### 条目

一轮的全部过程按 `seq` 排成一列条目，`seq` 在会话内递增，第一次写入时分配。七种类型：

| 类型 | 轨迹里能看到什么 |
|---|---|
| `userMessage` | 用户消息和插话的正文；`attachments` 是附件的元数据，文件本身在宿主的附件存储里 |
| `agentMessage` | 模型回答的正文 |
| `reasoning` | 模型的推理文本 |
| `toolCall` | 一次工具调用从记下到结束的全部信息，见下表 |
| `contextCompaction` | 一次压缩：`text` 是摘要，带这次压缩自己的 `usage` 和 `contextStats` |
| `memoryContext` | 载入的记忆快照：`text` 是放进上下文的全文，`memory` 列出快照里每条记忆的 ID、主题、内容和范围 |
| `error` | 模型调用失败的原因，或运行时写给模型的通知（例如以 `[runtime] Tool use has stopped:` 开头的停止工具使用通知） |

状态有五种：`pending`、`inProgress`、`completed`、`failed`、`declined`，含义见[持久化](/zh/engine/persistence#状态)。每条都有 `startedAt`，结束的有 `completedAt`，失败或被拒的有 `error`。

计划和提问没有单独的类型。`update_plan` 和 `request_user_input` 都是 `toolCall`：计划在参数里，用户的回答就是工具结果。子 agent 也是一次 `Agent` 工具调用，`await.threadId` 指向子会话，子 agent 自己的轨迹在那个会话里（见[执行模型](/zh/engine/execution#子-agent)）。

`toolCall` 条目上的字段：

| 字段 | 内容 |
|---|---|
| `callId`、`tool`、`server` | 模型给的调用 ID、工具名、提供这个工具的 provider |
| `arguments` | 模型给的参数原文（JSON 字符串，已还原脱敏） |
| `annotations` | 调用时工具声明的注解快照（只读、幂等等） |
| `preparedExecution` | `Prepare` 冻结的执行内容：工作目录、程序和参数、环境变量、超时、是否在沙箱里、是否提权及理由、文件 diff，以及设置和参数的摘要（`tools/prepared.go`） |
| `approval` | 审批记录：`id`、`requestedAt`、`reason`、`rule`、`content`、`suggestedRules`，决定后加上 `decision`、`decidedBy`、`decidedAt` |
| `await` | 在等什么：`by` 是 `user` 或 `agent`，`request` 是请求内容，`threadId` 是子会话 |
| `result` | `output`（JSON）和 `artifacts`（例如激活的技能） |
| `error` | 失败、被拒或被跳过的原因 |

### 每次模型调用

一次模型调用产生的 `reasoning`、`agentMessage` 和若干 `toolCall` 共用一个 `responseId`。这个 ID 由引擎为每次调用生成（`responseRecorder`），不是服务商返回的 ID。一轮调用了几次模型，就是这一轮有几个不同的 `responseId`（压缩不算）。

这次调用的三样东西只写在它记录的第一个条目上，所以每次调用只计一次（`agent/runtime/stream.go` 的 `carry`）：

| 字段 | 内容 |
|---|---|
| `usage` | `inputTokens`、`cachedInputTokens`、`cacheWriteInputTokens`、`outputTokens`。服务商没有报用量时为空 |
| `contextStats` | 这次请求的组成：`model`、`budgetTokens`、`compactAtTokens`、`systemTokens`、`messagesTokens`、`memoryTokens`、`toolsTokens`、`estimatedTokens`、`calibratedTokens`，以及 `globalMemory`、`localMemory` 各自的 token 数和记忆 ID |
| `native` | 服务商自己格式的回答记录（Anthropic、Gemini 原生接口），原样回放给同类服务商，推理签名才有效。不发给客户端，见[模型接入](/zh/engine/models) |

优先级是 `agentMessage`、`reasoning`、第一个 `toolCall`。调用失败时写在失败的部分文本条目上，或写在新建的 `error` 条目上。

### 轮次

`turns` 一行对应一轮，轨迹相关的字段：

| 字段 | 内容 |
|---|---|
| `status` | 九个状态之一，见[执行模型](/zh/engine/execution#轮次状态机) |
| `model` | 这一轮用的模型和连接 |
| `usage` | 这一轮所有模型调用（含压缩）的累计用量，四个字段同上 |
| `error` | 失败或中断的原因 |
| `cronJobId` | 由定时任务发出时非空 |
| `createdAt` | 提交时间 |
| `startedAt` | 成为会话当前轮次的时间。从等待回到 `ready` 时不变 |
| `completedAt` | 结束时间 |

轮次用量在每次运行结束时由 `AddUsage` 累加，不是逐次写的。进程在运行中途退出时，这次运行的用量只留在各个条目上，不会补加到轮次上。

### 没有记录的

- **增量文本。** 流式输出时，第一个增量到达就插入一条正文为空、状态 `inProgress` 的条目，之后的增量只作为事件推给客户端（`item/agentMessage/delta`、`item/reasoning/textDelta`），完整文本在回答结束时一次写入。模型调用出错时，已收到的部分文本写进条目并标 `failed`；进程在流式中途退出时，恢复把这条标 `failed`，已推给界面的部分文本不在库里。
- **发给模型的请求本身。** 系统提示词和工具列表每次运行由 `systemprompt.Build` 和 `Offer` 重新算，不落库，`contextStats` 只留它们的 token 数。脱敏后的消息也不落库。所以库里的条目能重建对话内容，但不能逐字还原某一次请求。
- **状态变迁。** 条目按 ID 原地更新（`saveItem` 的 upsert），一条工具调用什么时候从 `pending` 变成 `inProgress` 没有时间戳。轮次进入槽位也不记时间，排队和运行的时间从轮次行上分不开。
- **记忆提炼的调用。** 后台提炼不属于任何轮次，不写条目。它的用量在 `memory_state.last_report` 里，只留最近一次，见[记忆](/zh/engine/memory#失败重试和跳过)。

### 脱敏前后各存在哪里

| 内容 | 位置 |
|---|---|
| 原值 | 库里：条目的 `text`、`arguments`、`result`，轮次的 `input` |
| 占位符版本 | 只在发出的请求和收到的回答里，不落库。例外是 `native`：它保存服务商的原始回答，里面的占位符原样保留 |
| 占位符和原值的对照表 | `Redactor` 的 `reverse`，在内存里，每次运行新建，不落库 |
| HMAC 密钥 | `settings.redaction_key`，每用户一个，不经协议暴露 |

细节见[脱敏](/zh/engine/redaction#替换的时机和位置)。

## 怎样读回

| 途径 | 读到什么 |
|---|---|
| `thread/read`、`thread/resume` | 会话行、全部轮次、一页条目和 `hasMore`。条目从新到旧取，按 `seq` 升序返回，`limit` 默认 100、最大 500，用 `beforeSeq` 往前翻；一页超过 4 MiB 时从旧的一端截断。不带 `native`。参数见[协议](/zh/integrate/protocol/threads) |
| `item/*` 通知 | 每次写库后的那一行条目，加上增量文本。事件不缓存，断线期间的要重读 |
| 桌面端导出 | 会话页可以导出 Markdown 或 JSON。导出前先用 `thread/read` 每页 100 条读完整个会话。JSON 是读到的会话、轮次和全部条目原样序列化；Markdown 只留用户消息、回答和每个工具调用一行，不含推理（`domains/export.ts`、`domains/threadMarkdown.ts`） |
| `read_tool_output` | 模型用的工具。上下文里被截短的工具输出，按条目 ID 和字符偏移读回库里的完整结果，只能读本会话的，见[工具系统](/zh/engine/tools#输出截断) |
| `repo.DB` | 嵌入引擎的宿主可以直接调 `Thread`、`ThreadPage`、`TurnItems`、`Item` 这些读方法 |

全文搜索只覆盖完成的用户消息和回答，不搜工具调用和推理，见[搜索](/zh/engine/search)。

## 用在哪里

- **崩溃恢复。** 重启时按条目的状态决定怎么处理：`pending` 的调用照常执行，`inProgress` 的标成"可能已生效"。见[持久化与崩溃恢复](/zh/engine/persistence#崩溃恢复)。
- **继续运行。** 每次运行都从库里重读条目组装提示词（`RunItems`），停放再唤醒的轮次靠的就是这份记录。`native` 让原生接口的推理签名在下一次请求里仍然有效。
- **界面时间线。** 桌面端的会话页就是条目按 `seq` 排出来的，重连时用 `thread/resume` 重读。
- **长期记忆。** 提炼任务读已结束轮次里的 `userMessage`、`agentMessage`、`toolCall`、`error` 条目，状态限于 `completed`、`failed`、`declined`，取正文、工具名、参数、结果和错误，不读推理和冻结的执行内容。每条记忆的 `sources` 指回这些条目的 ID。见[记忆](/zh/engine/memory#取证据)。
- **评测与自我改进。** 路线图的下一步是把轨迹当数据：按稳定的格式导出，用来回放或重跑任务、给改动打分，再让 agent 根据自己的轨迹提出改进。这些都还没做，见[路线图](/zh/roadmap)。

## 边界与已知问题

- **没有稳定的导出格式。** 桌面端的 JSON 导出是 `thread/read` 结果的原样序列化，没有版本号，字段随引擎变化，也不能导回。引擎本身没有导出方法。
- **导出不脱敏。** 导出的是库里的原文，包括密钥、手机号这类值。路线图里"导出前先脱敏"是计划，还没做。
- **轨迹随会话删除而删除。** 删除会话时，轮次、条目、子 agent 会话和定时任务随外键级联删除，附件按会话前缀删除（失败只写日志）。没有单独的归档或保存期限。
- **存储随历史增长。** 压缩只影响发给模型的内容，旧条目留在库里。基准里每轮约 11.6 KB 磁盘，长跑实验里库每轮增长约 3.2 KB（模拟模型、改动前测得，见[基准](/zh/benchmarks/#长跑)）。引擎没有清理旧条目的机制。
- **只有最终状态。** 条目原地更新，轮次不记进入槽位的时间，算不出一轮在队列里和在槽位里各花了多久，见[没有记录的](#没有记录的)。
- **增量和请求本身不落库。** 流式中途崩溃会丢掉已显示的部分文本；系统提示词和工具列表不落库，不能逐字还原某一次请求。
- **轮次用量可能少记。** 运行中途进程退出时，这次运行的用量不会加到轮次上；`AddUsage` 写失败也只写日志。要准确的用量，按条目上的 `usage` 加总。
- **审批人只记来源。** 经网关做出的决定，`decidedBy` 一律是 `gateway`（`gateway/server.go`），不区分具体是哪个连接或哪个人。
- **没有指标和链路追踪。** 引擎没有暴露队列长度、槽位占用这类指标，也没有分布式追踪的接口，宿主只能读日志和库。路线图把它列为[可观测性](/zh/roadmap#_4-可观测性)。

## 代码位置

| 仓库 | 路径 | 职责 |
|---|---|---|
| ollupi | `repo/items.go` | 条目、`ContextStats`、`Approval`、`saveItemOf` 的写入约束 |
| ollupi | `repo/turns.go` | 轮次的状态、`Usage`、时间点、`AddUsage`、`TurnItems` |
| ollupi | `repo/threads.go` | `Thread`、`ThreadPage`（不读 `native`）、删除会话 |
| ollupi | `agent/run.go` | `recorder`：写库后发事件，`AddUsage` |
| ollupi | `agent/events.go` | 引擎发出的事件 |
| ollupi | `agent/runtime/stream.go` | 流式记录、`carry`、失败时写部分文本 |
| ollupi | `agent/runtime/chat.go` | `send` 的脱敏与还原、`responseUsage`、日志 |
| ollupi | `agent/contextmanager/outputs.go` | `read_tool_output` |
| ollupi | `gateway/threads.go`、`gateway/server.go` | `thread/read`、`thread/resume`、分页上限 |
| ollupi | `agent/deferred_test.go` | 检查日志不含消息、参数和输出 |
| ollupi-desktop | `apps/desktop/src/renderer/src/domains/export.ts`、`threadMarkdown.ts` | 导出 Markdown 和 JSON |
