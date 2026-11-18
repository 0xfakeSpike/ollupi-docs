# 上下文管理

上下文管理决定每次模型调用发什么。它要解决三件事：请求不能超过模型能接受的长度；会话可以一直进行下去，不会因为历史变长而失败；请求的开头保持不变，这样服务商的前缀缓存（prefix cache，服务商对相同请求开头的缓存）能命中。

提示词在每次模型调用前从会话日志重新编译。日志里的条目（item）保存的是完整内容，裁剪和压缩都只影响发给模型的那份视图。

这部分在 `prompt` 包：`Window` 由模型名和输入预算构成，`Build` 把会话编译成一次请求，`Compaction` 编译压缩请求，`System` 写系统提示词。什么时候压缩、压缩的结果怎样写进日志，在 `run/model.go`。

## 为什么这样设计

- **条目存全文，裁剪只作用于视图。** 工具结果完整写进日志，每次组装按当次预算裁剪，被省略的中间部分模型可以用 `read_tool_output` 读回。
- **前缀稳定优先。** 系统提示词从最稳定到最不稳定排列，不含当前时间；记忆快照是日志里的一条记录，只在压缩后重新召回；提示词放不下时只缩最近一次回答的工具结果，更早的结果逐字节不变。见[设计决策 14](/zh/reference/decisions#_14-记忆快照与稳定前缀)。
- **回答只占窗口的一部分。** 为回答预留 `min(Output, Context/4)`，输出上限很大的模型也不会把对话能用的窗口挤小。
- **窗口小的模型换一个角色运行，不拒绝。** 输入预算不足 16384 token 的模型，这一轮用精简主 agent（`compact-main-agent`）的规则和工具，见[设计决策 13](/zh/reference/decisions#_13-精简模式)。
- **压缩是最后一步，而且要有收益。** 先缩工具结果，不够再压缩；压缩要求超过 80% 且至少能省下输入预算的 10%；什么都压不了时这一轮报错，不悄悄丢历史（见[设计决策 18](/zh/reference/decisions#_18-出错即暴露)）。
- **能不能放下，每一轮自己判断。** 启动时不预先检查系统提示词和工具定义的大小：用户自己的 MCP 工具、工作区、这一轮载入的工具都只有到这一轮才知道，`Build` 在什么都压不了时直接报错。

代价：每次模型调用都要重新组装、重新估算整份提示词；压缩会换掉前缀，之后的第一次请求缓存不命中；会话中途新提炼的记忆要等下一次压缩才进提示词；token 不用分词器计数，靠服务商上报的真实用量校准，没有可用的历史用量时只有估算；固定部分过大的部署能启动，但它的每一轮都会失败。

::: info 演进
- 以前渲染时先把每个工具输出固定截到 16000 rune，再按预算截一次，被截掉的部分模型没有办法读回，两次省略提示的位置也和原文对不上。`d74ad27` 改成存全文、只在视图上裁剪。
- 以前每轮丢掉上一轮的记忆条目，等于每轮都从上一轮的起点重写提示词，缓存每轮失效。系统提示词去掉当前时间来自 `98ff53f`；只缩最近一次回答的工具结果、放不下时报错来自 `6f94607`。
- 以前输入预算扣掉整个 `Output`，输出上限越大的模型，对话能用的窗口反而越小。`8d77f0c` 改成预留 `min(Output, Context/4)`。
- 以前一个输入预算很小的模型就让整个 agent 启动失败，`f1382d1` 改成精简模式。
- 以前启动时对每个模型检查系统提示词加工具定义不超过输入预算的一半，但这个检查看不到用户自己的工具、工作区和这一轮载入的工具。`e067f65` 去掉了它，交给每一轮的 `Build`。
- v0.16.0 把引擎重建为以会话日志为中心：`dc0bb5d` 把上下文管理器改写成 `prompt` 包，从日志的投影 `conversation.View` 编译请求；`cf4141e` 让压缩和记忆召回成为一轮里的普通步骤，结果作为日志记录追加。
:::

## 窗口预算

每个模型在连接上声明 `llm.Limits`（`pkg/llm/limits.go`）：

```go
type Limits struct {
	Context  int `json:"context"`
	Output   int `json:"output"`
	MaxInput int `json:"input,omitempty"`
}
```

`MaxInput` 是模型自己的输入上限，只有输入上限比窗口小的模型才需要填。预算的公式：

```text
reserve = min(Output, Context / 4)
input   = Context - reserve
input   = min(input, MaxInput)        （MaxInput > 0 时）
answer  = min(Output, max(reserve, Context - 估算输入))
```

`reserve` 是为回答预留的部分。`Output` 是回答最多能到多长，很少有回答真的到这么长，所以输出上限很高的模型最多让出窗口的四分之一。

`answer` 是要声明回答上限的 API 用的（`Limits.Answer`）。Anthropic 的 `max_tokens` 和 Gemini 的 `MaxOutputTokens` 取这个值，它按当次估算的输入收紧，让输入加回答放得进窗口。输入只是估算，所以 `reserve` 始终保留。OpenAI 兼容接口不发回答上限。

| Context | Output | reserve | input |
|---|---|---|---|
| 128000 | 8192 | 8192 | 119808 |
| 200000 | 64000 | 50000 | 150000 |
| 32000 | 4000 | 4000 | 28000 |
| 8192 | 2048 | 2048 | 6144 |

`MaxInput` 只在比 `Context - reserve` 小时起作用：`Context` 1000、`Output` 100、`MaxInput` 500 时 `input` 是 500。`answer` 的例子：`Context` 200000、`Output` 128000 时 `reserve` 是 50000，估算输入为 0、100000、150000、190000 时 `answer` 分别是 128000、100000、50000、50000。`Context` 和 `Output` 必须为正，`MaxInput` 不能为负；`Limits` 在连接上怎么声明见[模型接入](/zh/engine/models#每模型配置项)。

`prompt.NewWindow(model, limits)` 只记下模型名和 `limits.Input()`，之后所有预算都从这个 `input` 算出。

::: info 演进
来自 `52a529b`：`MaxInput` 只在比 `Context - reserve` 小时起作用。
:::

### 按输入预算派生的份额

`percentOf(input, pct) = max(256, input * pct / 100)`。

| 预算 | 公式 | input = 119808 时 | 位置 |
|---|---|---|---|
| 自动压缩阈值（`CompactAtTokens`） | `input * 80 / 100` | 95846 | `prompt/window.go` |
| 压缩的最小收益 | `percentOf(input, 10)` | 11980 | `prompt/window.go` |
| 一次回答的全部工具结果 | `percentOf(input, 25)` | 29952 | `prompt/transcript.go` |
| 全部工具定义（`toolsFit`） | `percentOf(input, 10)` | 11980 | `prompt/tools.go` |
| 技能目录 | `percentOf(input, 4)` | 4792 | `prompt/system.go` |
| 记忆快照（`MemoryBudget`） | `min(4000, input * 8 / 100)` | 4000 | `prompt/window.go` |
| 技能内容（`artifactBudget`） | `percentOf(input, 15)` | 17971 | `prompt/artifacts.go` |
| 压缩后保留的用户消息 | `percentOf(input, 10)` | 11980 | `prompt/compaction.go` |
| 单条用户消息 | `max(256, input * 25 / 100)` | 29952 | `app/turns.go` |

单条用户消息超过上限时，这条消息在进入日志之前就被拒绝，错误提示把长文本作为文件附件发送。

### Token 估算

`llm.EstimateTokens`（`pkg/llm/tokens.go`）不调用分词器：

```go
return (ascii+3)/4 + nonASCII
```

每 4 个 ASCII 字符算 1 个 token，每个非 ASCII 字符算 1 个。消息和工具定义用缩进 JSON 文本来估算，图片和文件再加上附件上记录的 `Tokens`。

估算值会用真实用量校准。`calibrate` 倒序找最近一次同模型、带输入用量和估算值的模型回答 `ref`（日志里的 `ModelResponded` 记录，`View.Responses`）：

- `ref` 在最近一次压缩之后，而且不是压缩本身的回答：`校准值 = max(0, ref 的真实输入 + 当前估算 - ref 的估算)`。真实用量加上之后新增部分的估算。
- `ref` 是压缩的回答（`Compaction` 为真），或在最近一次压缩之前：`校准值 = max(当前估算, 当前估算 * ref 的真实输入 / ref 的估算)`。这时内容差别太大，只能用比例。

阈值判断都用校准值（`CalibratedTokens`）。校准值同时作为 `ChatRequest.InputTokens` 传给客户端，用于算 `answer`。

## 组装消息

`Window.Build` 的输入是 `prompt.Context`：条目、模型回答、系统提示词和工具定义。条目由 `prompt.Transcript(view)` 取出：已经结束的轮次和当前轮次的全部条目，按日志顺序；排在后面还没开始的轮次不算。

`transcript` 把条目渲染成消息：

| 条目 | 渲染成 |
|---|---|
| 最新的 `memoryContext` | 第一条 user 消息，内容是快照文本 |
| 最新的 `contextCompaction` | 一条 user 消息，内容是压缩历史。它之前的条目不再渲染 |
| `userMessage` | user 消息，开头加 `[sent Mon 2006-01-02 15:04 -07:00]` 和换行，附件作为 parts |
| `notice` | user 消息，原文。这是运行时告诉模型的话，比如工具为什么停了 |
| `agentReport` | user 消息，开头是 `[report of the <工具名> launched by call <调用 ID>, "<任务>": <状态>]`，后面是子 agent 的报告，按单个工具结果裁剪 |
| `error` | 跳过。这是失败的模型调用 |
| 同一 `Response` 的 `reasoning`、`agentMessage`、`toolCall` | 一条 assistant 消息，每个工具调用再加一条 tool 消息 |

合并成 assistant 消息时：没有正文也没有工具调用时整条跳过；这次回答的 `ModelResponded` 记录里的 `Native` 原样带上，供同类服务商回放（见[模型接入](/zh/engine/models#思考内容和签名回放)）。

`[sent ...]` 是消息发送时的本地时间，来自条目的 `StartedAt`。系统提示词里没有当前时间，规则告诉模型取这些时间里最新的作为当前时间。

## 工具输出裁剪

工具结果完整写在日志里（`ToolResult`）。每次组装时按预算裁剪，所以同一个结果在不同请求里可以有不同长度。这是三层输出截断的最后一层，前两层（工具自身、注册表）决定写进日志的是什么，见[工具系统](/zh/engine/tools#输出截断)。

### 观察文本

`prompt.OutputText` 把工具结果变成文字。结构化结果用缩进 JSON。字符串里连续的装饰行（至少 3 个非空字符，其中 90% 以上是框线字符或 `-=*_+|`）换成一个 `...`。`read_tool_output` 用的也是这个函数，所以它数的字符位置和裁剪提示里的一致。

### 单个结果的预算

```go
func (w Window) observationBudget(calls, limit int) int {
	return min(limit, max(minPooledTokens, min(w.inputTokens/8, percentOf(w.inputTokens, responsePercent)/max(1, calls))))
}
```

`calls` 是这次回答的工具调用数。同一回答的调用共享输入预算的 25%，每个不超过八分之一，不低于 512，也不超过 `limit`。`limit` 默认是 6000（`maxObservationTokens`）。

以 `input = 119808` 为例：1 个调用的结果最多 6000；8 个调用每个 3744；64 个调用每个 512。

### 超出输入预算时

`fitted` 在提示词超过 `input` 时重新组装，`limit` 依次是 6000、3000、1500、750、375、256（`minOutputTokens`）。`limit` 只作用于最近一次回答的工具结果，更早的结果始终用 6000。子 agent 的报告始终按一个调用、6000 的上限渲染。

### clip

`clip` 保留开头和结尾，把中间换成提示：

1. 文本估算不超过预算时原样返回。
2. 二分找到能放下的保留长度（开头和结尾各 `lo` 个字符），再把这 `2·lo` 重新分配：开头约三分之一（`2·lo/3`），结尾约三分之二。
3. `redact.Cuts` 调整切点，让切口不落在敏感值中间（`redact.Spans` 找出的范围）。
4. 中间换成一行提示：

```text
[... characters 12000-48000 of this output omitted; call read_tool_output with output_id "<条目 ID>" and offset 12000 to read them ...]
```

空结果显示 `(no output)`。失败或被拒绝的调用显示 `error:` 加错误文本，裁剪时提示 `[... N characters omitted ...]`，不能读回。没结束的调用显示 `error: the call did not finish`。

### 技能内容

工具结果可以带技能内容（`Artifacts`，目前只有 `agent_skill` 一种，由 `activate_skill` 产生）。写进日志之前，`CheckArtifacts` 要求每份有名字和内容、不超过 20000 字符，整组的估算不超过技能内容预算（输入预算的 15%），否则这次调用以 `apply tool context: ...` 失败。

渲染时同一份技能（按种类和名字区分）只出现一次，在最后一次加载它的结果里；而且只保留最近加载、合起来放得进技能内容预算的那些。其余的位置写明原因：

- `--- <kind> <name>: loaded again later, and shown there ---`
- `--- <kind> <name>: no longer fits with what was loaded since; load it again if it is still needed ---`

技能内容不裁剪，它们的 token 先从这个结果的预算里扣除，正文至少留 256。

::: info 演进
以前技能内容逐个结果检查预算、在每个加载它的结果里全文渲染，同一回答里并排加载的几个技能各自没超预算，合起来却能占满窗口，压缩也救不了。`5af20fd` 改成每份只带一次、整体受预算约束。
:::

### read_tool_output

模型用 `read_tool_output`（`tool/builtin/outputs`）读被省略的部分：

| 参数 | 说明 |
|---|---|
| `output_id` | 必填，就是工具调用条目或子 agent 报告条目的 ID |
| `offset` | 必填，从 0 开始的字符位置 |
| `length` | 选填，默认 8000，最大 20000 |

工具从当前会话的视图里找到这个条目，重新算出同样的观察文本，取 `[offset, offset + length)`，返回 `Characters a-b of n:` 加内容。条目不在当前会话里、不是工具调用或报告、没有结果时，返回 `this conversation has no tool output "<ID>"`；`offset` 超过末尾时报错并给出总字符数。工具标了只读，不需要审批。

## 自动压缩

`Build` 第一遍组装（`limit = 6000`）时记下自然长度 `natural`（校准后）和可压缩部分 `compactable`：消息的估算减去固定内容（记忆快照和压缩历史），再按校准比例放大。

### 触发条件

三个条件都成立时 `NeedsCompaction` 为真：

```go
r.NeedsCompaction = natural > r.Stats.CompactAtTokens &&
	hasItemsAfterCompaction(in.Items) && compactable >= percentOf(w.inputTokens, compactMinPercent)
```

| 条件 | 含义 |
|---|---|
| `natural > CompactAtTokens` | 校准后的长度超过 `input` 的 80% |
| `hasItemsAfterCompaction` | 上次压缩之后有新东西，记忆快照和压缩本身不算 |
| `compactable >= percentOf(input, 10)` | 能压缩的部分至少占 `input` 的 10%。不算压缩历史和记忆快照这些固定内容 |

第三条防止固定内容已经占了大半窗口时反复压缩，每次又省不下什么。

`compactable` 不够时，提示词超过 80% 仍继续发送。超过 `input` 且不能压缩时，`Build` 返回错误 `prompt: the request needs N tokens even with the latest tool results clipped and nothing is left to compact; model M allows K`，这一轮失败。

### 压缩过程

压缩是一轮里的一个步骤（`run/model.go` 的 `callModel` 和 `compact`），就在原本的模型调用之前，占着槽位，用这一轮的模型和连接：

1. `Build` 得出 `NeedsCompaction`，`callModel` 改为调用 `compact`。
2. `Window.Compaction` 组装压缩请求。
3. 以 `ToolChoiceNone` 调用模型，不推送流式文本。
4. 校验：调用失败、要工具、被输出上限截断、没有正文，都返回错误，这一轮失败（`run: compaction: ...`），日志里不留压缩记录。
5. 成功时在一个事务里追加两条记录：`ModelResponded`（`Compaction` 为真，带这次的用量和上下文统计），以及 `Compacted`（摘要、`Through`、对应的回答 ID 和上下文统计）。`Compacted` 在视图里是一个 `contextCompaction` 条目。
6. 这一步结束。运行回到循环开头，重新读日志：先重新召回记忆（见下文），然后再一次 `Build`，这一次压缩历史已经替换了旧条目，照常调用模型。

`Through` 是被摘要覆盖的条目里最大的 `Updated`，也就是摘要代表日志中到哪一条记录为止。组装时 `prompt` 按压缩条目在会话里的位置决定换掉哪些条目，不读 `Through`。

压缩的回答不计入角色的模型调用上限（`MaxModelCalls`，`agent.responses` 跳过 `Compaction` 为真的回答），用量计入这一轮。

### 压缩请求

压缩请求沿用同一个系统提示词和工具定义，消息是历史记录再加一条 user 指令。指令要求为接手的另一个模型写一份交接摘要，包括用户的要求、偏好、约束和已做的决定；当前进度和产生的确切事实、ID、路径、结果；接下来要做什么；用用户的语言写，不调用工具。

组装时：

- 不带记忆快照。
- 所有工具结果都受 `limit` 约束，不只是最近一次。
- 上一次的压缩历史如果存在，放在最前面并始终保留。
- `fitted` 把工具结果压到最小后还放不下时，从最老的消息开始丢，一次丢到下一条 user 消息。
- 丢完还放不下时报错 `prompt: the compaction request needs N tokens even with every tool result clipped; model M allows K`。

### 压缩之后保留什么

之后的请求里，最新压缩条目之前的条目都不再渲染，换成一条压缩历史。`compactedHistory` 的内容依次是：

| 部分 | 内容 |
|---|---|
| 时间 | `Latest user message before this summary: [sent ...]` |
| 用户消息 | `Earlier messages from the user:` 列出最近的用户消息，预算 `percentOf(input, 10)`，从新往旧取，放不下就停，每条按估算加 4 计 |
| 摘要 | 固定前缀说明这是另一个模型的摘要，然后是摘要正文 |
| 激活的技能 | `--- active <kind>: <name> ---` 加内容，预算 `percentOf(input, 15)`，优先保留最近的 |
| 放不下的技能 | 一行提示，告诉模型需要时重新加载 |

压缩之前的条目仍在视图里，有几类效果靠读它们延续：

| 效果 | 怎样延续 |
|---|---|
| 用户消息 | 进入压缩历史的用户消息部分 |
| 已载入的延迟工具 | `Window.Offer` 读整段会话里完成的 `load_tools` 调用 |
| 激活的技能 | 压缩历史里的激活技能部分 |
| "在此会话中允许" | 权限判定读整个视图，见[审批与权限](/zh/engine/permissions) |

记忆快照不延续。`run.recall` 在每次模型调用之前检查：从后往前先碰到压缩、或者根本没有召回过，就重新召回一次（角色要召回、用户开着记忆时），召回到内容就作为一条 `Recalled` 记录追加，预算是 `MemoryBudget`。召回本身也是一个步骤，写完后回到循环开头。召回的规则见[记忆](/zh/engine/memory)。

::: info 演进
以前压缩先写一条 `inProgress` 的压缩条目，失败时把它标成 `failed`；压缩的回答靠条目重建出来，从而不计入模型调用上限。v0.16.0 的 `cf4141e` 让压缩成为一个步骤，只在成功时追加记录；`547c914` 让压缩的 `ModelResponded` 自己带上 `Compaction` 标记，`agent` 和 `prompt` 直接读这个标记。这个提交之前压缩过的轮次没有标记，它们的压缩回答计入模型调用上限。
:::

## 系统提示词

`Window.System` 把各段用空行连起来。顺序是从最稳定到最不稳定，这样其他会话和子 agent 的请求能共享缓存的前缀。

| 顺序 | 段 | 什么时候有 |
|---|---|---|
| 1 | agent 提示词 | 角色回答用户时（`Role.AnswersUser`，也就是两种主 agent）。`host.Config.Prompt`，空时用默认的个人助手提示词，名字取 `host.Config.Name` |
| 2 | 角色规则 | 总有。`Role.Rules`，每个角色一份（`agent/rules.go`） |
| 3 | `# AVAILABLE SKILLS` | 这个角色装了技能 |
| 4 | `# DEFERRED TOOLS` | 有延迟加载的工具 |
| 5 | `# PROJECT` | 会话属于工作区，而且这一轮能用工作区的工具；写明项目路径，命令默认在那里运行 |

每个角色的规则都有 `Safety` 一节，所以安全规则不依赖 agent 提示词，自定义提示词的部署也有。主 agent 的规则以 `Final answer` 一节收尾，子 agent 的以 `Report` 一节收尾；子 agent 的角色不带 agent 提示词，规则开头就说明它是子 agent、它的回复是给启动它的 agent 的报告。

技能按角色安装，目录在 `host.Config.SkillsDir` 下每个角色自己的子目录。技能目录超过输入预算的 4% 时从末尾删，并写明 `[N more skills are not listed: the catalog is over its budget]`。

系统提示词在每次模型调用前重新写（`run.input`），每次都重新读这个角色的技能目录。写它的输入不变时文字逐字节相同，缓存照样命中；运行中途出现或消失的工具、新装的技能，从下一次请求起出现，代价是一次缓存失效。

::: info 演进
来自 `263ceff`：以前系统提示词在一次运行开始时写一次，运行中途的变化要等下一次运行；现在每次请求都重新写。
:::

## 延迟加载工具

工具定义也占输入预算。工具太多，或者模型的输入预算很小时，一部分工具只列名字，模型用到时再用 `load_tools` 载入。载入只会把工具追加到列表末尾，请求开头不变，前缀缓存继续有效。触发条件和细节见[工具系统](/zh/engine/tools#延迟加载)。

## 精简模式

一轮排队时，`app` 按这一轮模型的输入预算选主 agent 的角色（`agent.MainRole`）：`input` 小于 16384（`compactBelowTokens`）时用 `compact-main-agent`，否则用 `full-main-agent`。角色记在这一轮上，之后不变。完整的规则和工具列表约 8k token，这样的模型放不下，所以改用更小的规则和工具列表，照常运行，见[设计决策 13](/zh/reference/decisions#_13-精简模式)。

| 方面 | `full-main-agent` | `compact-main-agent` |
|---|---|---|
| 规则 | `fullMainRules` | `compactMainRules`，只留最核心的规则 |
| 核心工具（`Role.Core`） | 无，内置工具都发送 | `read_file`、`run_command`，加上 `load_tools` |
| 工具放不下时 | 只延迟外部工具 | 先延迟外部工具，内置工具还放不下就只发核心工具 |
| 向用户提问 | `request_user_input` | 规则改成需要时在回复里问，因为这个工具通常被延迟 |

`compactMainRules` 还提醒模型上下文很小，只读需要的行，保持命令输出简短。

::: info 演进
精简模式原来是一个开关，由系统提示词和工具分配各自判断；`02c6e93` 把它写成一个 profile，`198b2aa` 把主 agent 和子 agent 都变成轮次指定的角色，精简模式成了其中一个角色。
:::

## 前缀缓存的稳定性

服务商的前缀缓存要求请求开头逐字节相同。下面这些设计都为了这一点，或者与它一致：

| 做法 | 效果 |
|---|---|
| 系统提示词按稳定程度排序 | 同一部署的不同会话和子 agent 共享开头 |
| 系统提示词不含当前时间 | 时间写在每条用户消息里，来自日志里的 `StartedAt`，重新组装时不变 |
| 工具按提供者和名字排序 | 注册表的列表是确定的 |
| 工具列表只增不减 | 已载入的工具接在末尾 |
| `# DEFERRED TOOLS` 不随载入变化 | 系统提示词在会话里保持不变 |
| 记忆快照只在压缩后重新召回 | 快照是日志里的一条记录，是第一条消息，不会每轮都变 |
| 旧工具结果用固定预算渲染 | `limit` 只影响最近一次回答，已发过的内容渲染结果不变 |
| 脱敏占位符稳定 | 每个用户一个 `redaction_key`，同一值在重启后仍得到同一占位符 |
| `Native` 原样回放 | 同类服务商收到自己的原始回答记录 |

压缩会换掉前缀，这是它的代价，所以 80% 才触发。

各服务商的缓存方式不同：Anthropic 请求带顶层 `cache_control`（自动断点），OpenAI 兼容接口和 Gemini 用隐式缓存。每次模型调用的用量里记下缓存命中和写入的 token（`cachedInputTokens`、`cacheWriteInputTokens`）。详情见[模型接入](/zh/engine/models#缓存断点)。

## 上下文统计

每次模型调用把 `conversation.ContextStats` 写进这次回答的 `ModelResponded` 记录；压缩还把压缩请求的统计写进 `Compacted`。协议里，轮次的 `responses` 列出每次回答的用量和 `contextStats`，压缩条目自己也带 `contextStats`，界面的上下文面板读它们。

| 字段 | 含义 |
|---|---|
| `model` | 模型名，校准时只取同模型的记录 |
| `budgetTokens` | `input` |
| `compactAtTokens` | 自动压缩阈值 |
| `systemTokens`、`messagesTokens`、`toolsTokens` | 各部分的估算 |
| `memoryTokens` | 记忆快照的估算 |
| `globalMemory`、`localMemory` | 全局和本地记忆的 token 与条目 ID |
| `estimatedTokens` | 估算总数 |
| `calibratedTokens` | 校准后的总数 |

压缩请求的统计没有记忆部分，因为压缩请求不带快照。

## 边界与已知问题

- **估算可能偏离真实值。** `EstimateTokens` 不用分词器，非 ASCII 字符一律算 1 个 token。校准只认同模型、带用量的历史回答，所以会话的第一次模型调用、以及会话换模型之后的第一次调用，都只有未校准的估算。
- **80% 到 100% 之间可能一直不压缩。** 可压缩部分不足输入预算的 10% 时不压缩，提示词照常发送；超过 `input` 又压不了时这一轮失败，见[触发条件](#触发条件)。
- **压缩失败，这一轮就失败。** 压缩调用出错、要工具、没有摘要或被输出上限截断时，没有退路；压缩占着槽位，用的是这一轮的模型和连接的并发名额。
- **新记忆进提示词有延迟。** 会话里有了快照之后，只在每次压缩后重新召回；会话中途提炼的记忆要靠 `memory_search` 查到。
- **召回为空时沿用旧快照。** 渲染取整段会话里最新的一份快照；压缩后重新召回得到空文本时不追加记录，提示词里仍是压缩前的那一份。
- **固定部分过大的部署每一轮都失败。** 启动时不检查系统提示词和工具定义的大小；它们占满窗口时，每一轮的 `Build` 都报错。用户的外部工具多到放不下时靠[延迟加载](/zh/engine/tools#延迟加载)处理；`load_tools` 不可见时（比如权限去掉了它）不延迟，超出预算就在 `Build` 报错。
- **压缩丢掉前缀缓存。** 这是有意的取舍，所以阈值定在 80%，见[前缀缓存的稳定性](#前缀缓存的稳定性)。

## 代码位置

| 仓库 | 路径 | 职责 |
|---|---|---|
| ollupi | `pkg/llm/limits.go` | `Limits`、`Input`、`Answer` |
| ollupi | `pkg/llm/tokens.go` | `EstimateTokens` |
| ollupi | `prompt/window.go` | `Window`、预算、`Build`、`fitted`、校准、`Transcript` |
| ollupi | `prompt/transcript.go` | 条目渲染成消息、单个结果的预算 |
| ollupi | `prompt/observation.go` | 工具结果渲染和 `clip` |
| ollupi | `prompt/render.go` | `OutputText`、装饰行折叠 |
| ollupi | `prompt/artifacts.go` | 技能内容的检查和预算 |
| ollupi | `prompt/compaction.go` | 压缩请求和压缩历史 |
| ollupi | `prompt/system.go` | 系统提示词 |
| ollupi | `prompt/tools.go` | `Offer`、延迟加载的划分 |
| ollupi | `agent/agent.go`、`agent/rules.go` | 角色、核心工具、`MainRole`、规则 |
| ollupi | `run/model.go` | `callModel`、`recall`、`compact`、`send` |
| ollupi | `tool/builtin/outputs/outputs.go` | `read_tool_output` |
| ollupi | `app/turns.go` | 单条消息上限、选择角色 |
