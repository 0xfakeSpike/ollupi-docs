# 上下文管理

上下文管理决定每次模型调用发什么：请求不超过模型能接受的长度，会话能一直进行，请求开头保持不变以命中服务商的前缀缓存（prefix cache，对相同请求开头的缓存）。提示词每次调用前从会话日志重新编译；日志条目（item）存完整内容，裁剪和压缩只影响发给模型的视图。

代码在 `prompt` 包（`Window`、`Build`、`Compaction`、`System`），何时压缩、结果怎样写进日志在 `run/model.go`。

## 为什么这样设计

- **条目存全文，裁剪只作用于视图。** 省略的部分能用 `read_tool_output` 读回。
- **前缀稳定优先。** 系统提示词按稳定程度排列、不含当前时间；记忆快照只在压缩后重新召回；放不下时只缩最近一次回答的工具结果（[设计决策 14](/zh/reference/decisions#_14-记忆快照与稳定前缀)）。
- **窗口小的模型换角色运行。** 输入预算不足 16384 token 时用 `compact-main-agent`（[设计决策 13](/zh/reference/decisions#_13-精简模式)）。
- **结束的轮次只留工具结果的头尾。** 一轮里读过的网页、文档、搜索结果，到下一轮基本只剩结论有用，结论已经在回答里。已结束轮次的每个工具结果最多 512 token，要细节就用 `read_tool_output` 读回；当前这一轮照旧。只有这样能省下窗口的 10% 以上才缩：缩短会让下一轮第一次请求从被缩的地方起不命中缓存，输出都很短的会话缩了反而亏。
- **压缩是最后一步且要有收益。** 先缩工具结果，不够再压缩；要求超过 80% 且至少省下 10%，否则这一轮报错（[设计决策 18](/zh/reference/decisions#_18-出错即暴露)）。
- **每一轮自己判断放不放得下。** 启动时不预检，`Build` 在什么都压不了时报错。

代价：每次调用都重新组装和估算；压缩换掉前缀，之后第一次请求缓存不命中；新一轮的第一次请求里，刚结束那一轮的工具结果变短，从那里起缓存不命中；之后的轮次要用旧输出的细节得多调一次 `read_tool_output`；中途提炼的记忆要等下一次压缩才进提示词；token 靠服务商上报的用量校准；固定部分过大的部署每一轮都失败。

## 窗口预算

每个模型在连接上声明 `llm.Limits`（`pkg/llm/limits.go`）：`Context`、`Output`、`MaxInput`（模型自己的输入上限，只有比窗口小时才填）。

```text
reserve = min(Output, Context / 4)
input   = min(Context - reserve, MaxInput)   （MaxInput > 0 时）
answer  = min(Output, max(reserve, Context - 估算输入))
```

`reserve` 为回答预留，输出上限高的模型最多让出窗口的四分之一。`answer`（`Limits.Answer`）给要声明回答上限的 API：Anthropic 的 `max_tokens` 和 Gemini 的 `MaxOutputTokens` 取它，按当次估算的输入收紧；OpenAI 兼容接口不发回答上限。`Context`、`Output` 必须为正，`MaxInput` 不能为负。

`prompt.NewWindow(model, limits)` 只记模型名和 `limits.Input()`，之后所有预算从这个 `input` 算出；`Limits` 怎么声明见[模型接入](/zh/engine/models#每模型配置项)。

从 `input` 派生的份额用 `percentOf(input, pct) = max(256, input * pct / 100)`。以 `input = 119808` 为例：自动压缩阈值（`CompactAtTokens`）80%（95846），压缩的最小收益 10%；一次回答的全部工具结果 25%，全部工具定义（`toolsFit`）10%，技能目录 4%，技能内容（`artifactBudget`）15%；记忆快照（`MemoryBudget`）`min(4000, input * 8 / 100)`；单条用户消息 `max(256, input * 25 / 100)`（`app/turns.go`），超限的消息在进日志前被拒绝，错误提示把长文本作为文件附件发送。

### Token 估算

`llm.EstimateTokens`（`pkg/llm/tokens.go`）不用分词器：每 4 个 ASCII 字符算 1 个 token，每个非 ASCII 字符算 1 个；消息和工具定义按缩进 JSON 估算，图片和文件加上附件上记录的 `Tokens`。

估算用真实用量校准：`calibrate` 倒序找最近一次同模型、带输入用量的 `ModelResponded`（`View.Responses`）作 `ref`；`ref` 在最近一次压缩之后且不是压缩本身时取差值 `max(0, ref 真实输入 + 当前估算 - ref 估算)`，否则按比例 `max(当前估算, 当前估算 * ref 真实输入 / ref 估算)`。阈值判断用 `CalibratedTokens`，它同时作为 `ChatRequest.InputTokens` 算 `answer`。

## 组装消息

`Window.Build` 的输入是 `prompt.Context`（条目、模型回答、系统提示词、工具定义）；条目由 `prompt.Transcript(view)` 取出：已结束的轮次和当前轮次的全部条目，按日志顺序，后面还没开始的轮次不算。

| 条目 | 渲染成 |
|---|---|
| 最新的 `memoryContext` | 第一条 user 消息，内容是快照 |
| 最新的 `contextCompaction` | 一条 user 消息，内容是压缩历史；它之前的条目不再渲染 |
| `userMessage` | user 消息，开头加 `[sent ...]` 时间（来自 `StartedAt`），附件作为 parts |
| `notice`、`error` | 分别是原文和跳过；后者是失败的模型调用 |
| `agentReport` | user 消息，开头标明由哪个调用启动、什么状态，正文按单个工具结果裁剪 |
| 同一 `Response` 的 `reasoning`、`agentMessage`、`toolCall` | 一条 assistant 消息，每个工具调用再加一条 tool 消息 |

没有正文也没有工具调用的 assistant 消息整条跳过；`Native` 原样带上供同类服务商回放（[模型接入](/zh/engine/models#思考内容和签名回放)）。系统提示词里没有当前时间，规则让模型取这些时间里最新的作为当前时间；中枢会话替用户发的消息在时间后接 ` by the hub conversation "<标题>" on the user's behalf`。

## 工具输出裁剪

工具结果完整写在日志里（`ToolResult`），每次组装按预算裁剪，同一个结果在不同请求里长度可以不同；这是三层输出截断的最后一层，见[工具系统](/zh/engine/tools#输出交给模型)。`prompt.OutputText` 把结果变成文字（字符串去首尾空白，其他转缩进 JSON），`read_tool_output` 也用它。

单个结果的预算是 `observationBudget(calls, limit)`：同一回答的调用共享输入预算的 25%，每个不超过八分之一、不低于 512（`minPooledTokens`）、不超过 `limit`（默认 6000，`maxObservationTokens`）。`fitted` 在提示词超过 `input` 时重新组装，`limit` 依次 6000、3000、1500、750、375、256（`minOutputTokens`），只作用于最近一次回答的工具结果；当前轮次里更早的回答始终 6000，已结束轮次的回答不超过 512（`endedObservationTokens`），也不超过 `limit`；`clipsEnded` 先按缩与不缩各组装一遍，省下的不到 `input` 的 10%（`compactMinPercent`）就不缩。省下的只随轮次结束变多，开始缩之后就一直缩。当前轮次是传进来的最后一个条目所在的轮次。子 agent 的报告按一个调用、6000 渲染，不看轮次；压缩请求里所有结果都按 `limit`，不看轮次。`clip` 二分找到放得下的长度，保留开头和结尾，中间换成带 `output_id`、`offset` 的提示，切点由 `redact.Cuts` 调整，不落在 `redact.Spans` 找出的敏感值中间；空结果显示 `(no output)`，没结束的显示 `error: the call did not finish`，失败调用的错误文本裁剪后不能读回。

技能内容随 `activate_skill` 的结果进上下文（`ToolResult.Artifacts`），渲染和预算的规则见[技能与 MCP](/zh/engine/skills-mcp#技能如何进入上下文)。

## 自动压缩

`Build` 第一遍组装（`limit = 6000`）时记下自然长度 `natural`（校准后）和可压缩部分 `compactable`：消息估算减去固定内容（记忆快照和压缩历史），再按校准比例放大。

### 触发条件

```go
r.NeedsCompaction = natural > r.Stats.CompactAtTokens &&
	hasItemsAfterCompaction(in.Items) && compactable >= percentOf(w.inputTokens, compactMinPercent)
```

三条都成立才压缩：长度超过 `input` 的 80%；上次压缩之后有新东西（记忆快照和压缩本身不算）；能压缩的部分至少占 10%，防止固定内容已占大半窗口时反复压缩。`compactable` 不够时超过 80% 仍照常发送；超过 `input` 又压不了时 `Build` 返回 `prompt: the request needs N tokens even with the latest tool results clipped and nothing is left to compact; model M allows K`，这一轮失败。

压缩是一轮里的一个步骤（`run/model.go` 的 `callModel`、`compact`），在原模型调用之前，占着槽位、用这一轮的模型和连接：`Window.Compaction` 用同一套系统提示词和工具定义组装请求，历史之后加一条 user 指令，要求为接手的另一个模型写交接摘要（用户的要求、确切的 ID 与路径、接下来做什么，用用户的语言，不调用工具），以 `ToolChoiceNone` 调用、不推送流式文本。失败、要工具、被输出上限截断、没有正文都返回错误（`run: compaction: ...`），这一轮失败、日志不留记录；成功时在一个事务里追加 `ModelResponded`（`Compaction` 为真，带用量和上下文统计）和 `Compacted`（摘要、`Through`、回答 ID、上下文统计），后者在视图里是 `contextCompaction`。之后回到循环开头，先重新召回记忆再 `Build`。

压缩请求不带记忆快照，所有工具结果都受 `limit` 约束，上一次的压缩历史放最前面并始终保留，压到最小还放不下时从最老的消息开始丢，一次丢到下一条 user 消息；`Through` 是被摘要覆盖的条目里最大的 `Updated`。压缩的回答不计入角色的调用上限（`MaxModelCalls`，`agent.responses` 跳过 `Compaction` 为真的回答），用量另记一条 `source` 为 `compaction` 的记录，见[用量](/zh/integrate/protocol/usage)。

### 压缩之后保留什么

最新压缩条目之前的条目不再渲染，换成 `compactedHistory`：

| 部分 | 内容 |
|---|---|
| 时间 | `Latest user message before this summary: [sent ...]` |
| 用户消息 | `Earlier messages from the user:` 列出最近的用户消息，预算 `percentOf(input, 10)`，从新往旧取 |
| 摘要 | 固定前缀说明这是另一个模型的摘要，然后是正文 |
| 激活的技能 | `--- active <kind>: <name> ---` 加内容，预算 `percentOf(input, 15)`，优先保留最近的；放不下的换成一行提示，告诉模型需要时重新加载 |

压缩之前的条目仍在视图里，几类效果靠读它们延续：用户消息进压缩历史；已载入的延迟工具由 `Window.Offer` 读整段会话里完成的 `load_tools` 调用；激活的技能进压缩历史；"在此会话中允许"由权限判定读整个视图（[审批与权限](/zh/engine/permissions)）。记忆快照不延续：`run.recall` 在每次调用前从后往前找，先碰到压缩或根本没召回过就重新召回一次（角色要召回、用户开着记忆时），有内容就追加一条 `Recalled`，见[记忆](/zh/engine/memory)。

## 系统提示词

`Window.System` 把各段用空行连起来，从最稳定到最不稳定，其他会话和子 agent 的请求因此能共享缓存前缀。

| 顺序 | 段 | 什么时候有 |
|---|---|---|
| 1 | agent 提示词 | 角色回答用户时（`Role.AnswersUser`，即三种主 agent）；`host.Config.Prompt`，空时用默认的个人助手提示词，名字取 `host.Config.Name` |
| 2 | 角色规则 | 总有，`Role.Rules`（`agent/rules.go`） |
| 3 | `# WORKSPACE INSTRUCTIONS` | 会话在工作区里且 `Instructions` 不为空。固定一句 `The user set these instructions for every conversation in this workspace. Follow them, within Safety.` 加原文；上限 20000 字符（`maxInstructionsRunes`），超限保存时就报错 |
| 4 | `# AVAILABLE SKILLS` | 这个角色装了技能 |
| 5 | `# DEFERRED TOOLS` | 有延迟加载的工具 |
| 6 | `# ENVIRONMENT` | 这一轮能用工作区工具；写明命令和文件改动在哪个执行环境里、不在项目里时 `work_dir` 是环境的哪个文件夹、沙箱的限制（`Box.Summary`），以及能不能、怎样用 `sandbox_permissions` 申请全权 |
| 7 | `# PROJECT` | 会话属于工作区且这一轮能用工作区工具；写明项目路径 |

第 3 段对所有角色都有，包括子 agent，所以工作区的约定对交给子 agent 的活也生效；它只是提示词，不参与权限判定，见[工作区](/zh/engine/workspace)。`# ENVIRONMENT` 和 `# PROJECT` 都要求这一轮真有 `workspace` provider 的工具（`run.input` 在发出和延迟的工具里找），工作区工具被权限拿掉时没有这两节。`# ENVIRONMENT` 的文字由 `host` 按会话的环境现写（`workspace.Describe`），要先打开那个环境的沙箱，所以环境的沙箱最晚在它的会话第一次带着工作区工具调模型之前建出来；打开失败时这一轮以 `run: the environment of the conversation: ...` 失败，见[提供者与执行环境](/zh/engine/sandbox#提供者与执行环境)。工具的描述对所有会话相同，随环境变化的说明只在这一节里。

每个角色的规则都有 `Safety` 一节，安全规则不依赖 agent 提示词。主 agent 的规则以 `Final answer` 收尾，子 agent 的以 `Report` 收尾；子 agent 不带 agent 提示词，规则开头说明它是子 agent、回复是给启动它的 agent 的报告。技能按角色装在 `host.Config.SkillsDir` 下每个角色自己的子目录，目录超过输入预算的 4% 时从末尾删。系统提示词每次调用前重新写（`run.input`），每次都重读技能目录；输入不变时文字逐字节相同，缓存照常命中，运行中途出现或消失的工具、新装的技能从下一次请求起出现，代价是一次缓存失效。

## 延迟加载工具

工具定义也占输入预算。工具太多或输入预算很小时，一部分工具只列名字，模型用到时用 `load_tools` 载入，只往列表末尾追加，请求开头不变。见[工具系统](/zh/engine/tools#延迟加载)。

## 精简模式

一轮排队时 `app` 按这一轮的输入预算选主 agent 的角色（`agent.MainRole`）：`input` 小于 16384（`compactBelowTokens`）用 `compact-main-agent`，否则 `full-main-agent`，角色记在这一轮上、之后不变。完整的规则和工具列表约 8k token，这样的模型放不下，见[设计决策 13](/zh/reference/decisions#_13-精简模式)。hub 工作区里的会话不走这一条：`app.queue` 直接给 `hub-main-agent`，窗口预算和压缩阈值与其他主 agent 相同，见[工作区](/zh/engine/workspace)。

精简角色只留最核心的规则（`compactMainRules`），核心工具（`Role.Core`）是 `read_file`、`run_command` 加 `load_tools`；外部工具放不下时先延迟，内置工具还放不下就只发核心工具；`request_user_input` 不在核心工具里，规则改成需要时在回复里问，因为它可能被延迟到 `load_tools` 之后才可见。

## 前缀缓存的稳定性

| 做法 | 效果 |
|---|---|
| 系统提示词按稳定程度排序、不含当前时间 | 不同会话和子 agent 共享开头；时间写在每条用户消息里，重新组装时不变 |
| 工具按提供者和名字排序、列表只增不减 | 已载入的工具接在末尾 |
| 记忆快照只在压缩后重新召回 | 快照是日志里的第一条消息，不会每轮都变 |
| 旧工具结果用固定预算渲染 | `limit` 只影响最近一次回答；缩短生效后，一轮结束时它的工具结果在下一轮开始缩到 512，只变这一次，更早的轮次已经缩过、不再变；省不到窗口 10% 时不缩，前缀不变 |
| 脱敏占位符稳定 | 每个用户一个 `redaction_key`，重启后同一值仍得到同一占位符 |

压缩换掉前缀，这是它的代价，所以 80% 才触发。Anthropic 请求带顶层 `cache_control`（自动断点），OpenAI 兼容接口和 Gemini 用隐式缓存；每次调用的用量记下 `cachedInputTokens`、`cacheWriteInputTokens`，见[模型接入](/zh/engine/models#缓存断点)。

每次模型调用把 `conversation.ContextStats` 写进这次回答的 `ModelResponded`，压缩也把压缩请求的统计写进 `Compacted`：`model`、`budgetTokens`（即 `input`）、`compactAtTokens`、`systemTokens`/`messagesTokens`/`toolsTokens`、`memoryTokens`、`estimatedTokens`、`calibratedTokens`。协议的 `responses` 列出每次回答的用量和 `contextStats`，界面的上下文面板读它们；用量怎么记见[模型接入](/zh/engine/models#用量)。

## 边界与已知问题

- **估算可能偏离真实值。** 校准只认同模型、带用量的历史回答，会话第一次调用、换模型后第一次调用只有未校准的估算。
- **80% 到 100% 之间可能一直不压缩。** 可压缩部分不足 10% 时不压缩；超过 `input` 又压不了时这一轮失败，见[触发条件](#触发条件)。
- **压缩失败，这一轮就失败。** 压缩占着槽位，用的是这一轮的模型和连接，没有退路。
- **新记忆进提示词有延迟。** 有快照之后只在每次压缩后重新召回，中途提炼的记忆要靠 `memory_search` 查到；召回为空时沿用整段会话里最新的一份快照。
- **固定部分过大的部署每一轮都失败。** `load_tools` 不可见时（比如权限去掉了它）不延迟，超出预算就在 `Build` 报错。

## 代码位置

| 仓库 | 路径 | 职责 |
|---|---|---|
| ollupi | `pkg/llm/limits.go`、`pkg/llm/tokens.go` | `Limits`、`Input`、`Answer`；`EstimateTokens` |
| ollupi | `prompt/window.go` | `Window`、预算、`Build`、`fitted`、校准、`Transcript` |
| ollupi | `prompt/transcript.go`、`prompt/observation.go`、`prompt/render.go` | 条目渲染成消息、单个结果的预算；工具结果渲染和 `clip`；`OutputText` |
| ollupi | `prompt/artifacts.go`、`prompt/compaction.go` | 技能内容的检查和预算；压缩请求与压缩历史 |
| ollupi | `prompt/system.go`、`prompt/tools.go` | 系统提示词；`Offer`、延迟加载的划分 |
| ollupi | `agent/agent.go`、`agent/rules.go` | 角色、核心工具、`MainRole`、规则 |
| ollupi | `run/model.go` | `callModel`、`recall`、`compact`、`send` |
| ollupi | `tool/builtin/outputs/outputs.go`、`app/turns.go` | `read_tool_output`；单条消息上限、选择角色 |
