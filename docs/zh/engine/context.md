# 上下文管理

上下文管理决定每次模型调用发什么。它要解决三件事：请求不能超过模型能接受的长度；会话可以一直进行下去，不会因为历史变长而失败；请求的开头保持不变，这样服务商的前缀缓存能命中。

提示词在每次模型调用前从数据库里的条目重新组装。条目里保存的是完整内容，裁剪和压缩都只影响发给模型的那份视图。

这部分在 `agent/contextmanager` 和 `agent/systemprompt`。`Manager` 每次运行创建一个，只保存模型名和输入预算。

## 窗口预算

每个模型在连接上声明 `llm.Limits`：

```go
type Limits struct {
	Context int `json:"context"`
	Output  int `json:"output"`
	// MaxInput is the most input the model accepts, for models that cap it below the window.
	MaxInput int `json:"input,omitempty"`
}
```

预算的公式：

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

### 按输入预算派生的份额

其他预算都从 `input` 算出。`share(input, pct) = max(256, input * pct / 100)`。

| 预算 | 公式 | input = 119808 时 |
|---|---|---|
| 系统提示词加工具定义的上限（`Fits`） | `input * 50 / 100` | 59904 |
| 自动压缩阈值（`CompactAtTokens`） | `input * 80 / 100` | 95846 |
| 压缩的最小收益 | `share(input, 10)` | 11980 |
| 全部工具定义（`ToolsFit`） | `share(input, 10)` | 11980 |
| 技能目录（`SkillBudget`） | `share(input, 4)` | 4792 |
| 记忆快照（`MemoryBudget`） | `max(0, min(4000, input * 8 / 100))` | 4000 |
| 技能内容（`artifactBudget`） | `share(input, 15)` | 17971 |
| 压缩后保留的用户消息 | `share(input, 10)` | 11980 |

`Fits` 只在启动时检查：`checkPromptFits` 对每个模型组装系统提示词和工具定义，超过 `input` 的一半时 `Agent.Start` 失败，错误信息写明实际占用和模型的上限。

### Token 估算

`llm.EstimateTokens` 不调用分词器：

```go
return (ascii+3)/4 + nonASCII
```

每 4 个 ASCII 字符算 1 个 token，每个非 ASCII 字符算 1 个。消息和工具定义用缩进 JSON 文本来估算，图片和文件加上附件上记录的 `Tokens`。

估算值会用真实用量校准。`calibrate` 倒序找最近一条同模型、带 `usage` 和 `context_stats` 的条目 `ref`：

- `ref` 在最近一次压缩之后：`校准值 = max(0, ref 的真实输入 + 当前估算 - ref 的估算)`。真实用量加上之后新增部分的估算。
- `ref` 是压缩条目，或在压缩之前：`校准值 = max(当前估算, 当前估算 * ref 的真实输入 / ref 的估算)`。这时内容差别太大，只能用比例。

阈值判断都用校准值（`CalibratedTokens`）。校准值同时作为 `ChatRequest.InputTokens` 传给客户端，用于算 `answer`。

## 组装消息

`Manager.Build` 调用 `transcript` 把条目渲染成消息。

| 条目 | 渲染成 |
|---|---|
| 最新的 `memoryContext` | 第一条 user 消息，内容是快照文本 |
| 最新一次完成的 `contextCompaction` | 一条 user 消息，内容是压缩历史。它之前的条目不再渲染 |
| `userMessage` | user 消息，开头加 `[sent Mon 2006-01-02 15:04 -07:00]` 和换行，附件作为 parts |
| 没有 `context_stats` 的 `error` | user 消息，原文。这是运行时的通知，比如停止工具使用 |
| 有 `context_stats` 的 `error` | 跳过。这是失败的模型调用 |
| 同一 `response_id` 的条目 | 一条 assistant 消息，每个工具调用再加一条 tool 消息 |

合并成 assistant 消息时：未完成的 `reasoning` 和 `agentMessage` 不要；没有正文也没有工具调用时整条跳过；`native` 原样带上，供同类提供方回放。

`[sent ...]` 是消息发送时的本地时间，来自条目的 `started_at`。系统提示词里没有当前时间。提示词告诉模型取这些时间里最新的作为当前时间。这是提交 98ff53f 的改动：之前模型只能从工具描述里看到进程启动时的时间。

## 工具输出裁剪

工具结果完整存在 `items.result` 里。每次组装时按预算裁剪，所以同一个结果在不同请求里可以有不同长度。

### 观察文本

`observationText` 把工具结果变成文字。结构化结果用缩进 JSON。字符串里连续的装饰行（至少 3 个非空字符，其中 90% 以上是框线字符或 `-=*_+|`）换成一个 `...`。

### 单个结果的预算

```go
func (m *Manager) observationBudget(calls, limit int) int {
	return min(limit, max(minPooledTokens, min(m.inputTokens/8, share(m.inputTokens, responsePercent)/max(1, calls))))
}
```

`calls` 是这次回答的工具调用数。同一回答的调用共享窗口的 25%，每个不超过窗口的八分之一，不低于 512，也不超过 `limit`。`limit` 默认是 6000（`maxObservationTokens`）。

以 `input = 119808` 为例：1 个调用的结果最多 6000；8 个调用每个 3744；64 个调用每个 512。

### 超出输入预算时

`fitted` 在提示词超过 `input` 时重新组装，`limit` 依次是 6000、3000、1500、750、375、256（`minOutputTokens`）。`limit` 只作用于最近一次回答的工具结果，更早的结果始终用 6000。

### clip

`clip` 保留开头和结尾，把中间换成提示：

1. 文本估算不超过预算时原样返回。
2. 二分找到能放下的保留长度（开头和结尾各 `lo` 个字符），再把这 `2·lo` 重新分配：开头约三分之一（`2·lo/3`），结尾约三分之二。
3. `cutPoints` 调整切点，让切口不落在敏感值中间（`redact.Spans` 找出的范围）。
4. 中间换成一行提示：

```text
[... characters 12000-48000 of this output omitted; call read_tool_output with output_id "<条目 ID>" and offset 12000 to read them ...]
```

结果里的技能内容（artifacts）不裁剪，它们的 token 先从预算里扣除，正文至少留 256。没有结果的失败调用显示 `error:` 加错误文本，裁剪时提示 `[... N characters omitted ...]`。没结束的调用显示 `error: the call did not finish`。

### read_tool_output

模型用 `read_tool_output` 读被省略的部分：

| 参数 | 说明 |
|---|---|
| `output_id` | 必填，就是工具调用条目的 ID |
| `offset` | 必填，从 0 开始的字符位置 |
| `length` | 选填，默认 8000，最大 20000 |

工具重新算出同样的观察文本，取 `[offset, offset + length)`，返回 `Characters a-b of n:` 加内容。位置按字符算，和 `clip` 提示里的数字一致。

条目不存在、不属于当前会话、不是工具调用或没有结果时，都返回 `this conversation has no tool output`。工具标了只读，不需要审批。

## 自动压缩

`Build` 第一遍组装（`limit = 6000`）时记下自然长度 `natural` 和可压缩部分 `compactable`。

### 触发条件

三个条件都成立时 `NeedsCompaction` 为真：

```go
p.NeedsCompaction = natural > p.Stats.CompactAtTokens &&
	hasItemsAfterCompaction(in.Items) && compactable >= share(m.inputTokens, compactMinPercent)
```

| 条件 | 含义 |
|---|---|
| `natural > CompactAtTokens` | 校准后的长度超过 `input` 的 80% |
| `hasItemsAfterCompaction` | 上次压缩之后有新东西，记忆快照和压缩本身不算 |
| `compactable >= share(input, 10)` | 能压缩的部分至少占 `input` 的 10%。不算压缩历史和记忆快照这些固定内容 |

第三条防止固定内容已经占了大半窗口时反复压缩，每次又省不下什么。

`compactable` 不够时，提示词超过 80% 仍继续发送。超过 `input` 且不能压缩时，`Build` 返回错误 `the prompt needs N tokens even with the latest tool results clipped and nothing is left to compact`，这一轮失败。

### 压缩过程

压缩在 `Runtime.respond` 里发生，就在模型调用之前，占着槽位，用这一轮的模型：

1. `CompactionPrompt` 组装请求。
2. 写入 `contextCompaction` 条目（`inProgress`），带这次的 `context_stats`。
3. 以 `ToolChoiceNone` 调用模型，不流式推送。
4. 校验：调用失败、没有摘要、要工具或被输出上限截断，条目标 `failed`，这一轮失败。
5. 摘要写入条目，标 `completed`。
6. `loadMemory` 刷新记忆快照。
7. 重新 `Build`，继续原来的模型调用。

压缩不计入 `maxModelCalls`，用量计入轮次。

### 压缩请求

压缩请求沿用同一个系统提示词和工具定义，消息是历史记录再加一条 user 指令。指令要求写一份交接摘要，包括用户的要求、偏好、约束和决定；当前进度和产生的确切事实、ID、路径、结果；接下来要做什么。

组装时：

- 不带记忆快照。
- 所有工具结果都受 `limit` 约束，不只是最近一次。
- 上一次的压缩历史如果存在，放在最前面并始终保留。
- `fitted` 把工具结果压到最小后还放不下时，从最老的消息开始丢，一次丢到下一条 user 消息。
- 丢完还放不下时报错 `the compaction request needs N tokens even with every tool result clipped`。

### 压缩之后保留什么

之后的请求里，压缩之前的条目都不再渲染，换成一条压缩历史。`compactedHistory` 的内容依次是：

| 部分 | 内容 |
|---|---|
| 时间 | `Latest user message before this summary: [sent ...]` |
| 用户消息 | `Earlier messages from the user:` 列出最近的用户消息，预算 `share(input, 10)`，从新往旧取，放不下就停，每条按估算加 4 计 |
| 摘要 | 固定前缀说明这是另一个模型的摘要，然后是摘要正文 |
| 激活的技能 | `--- active <kind>: <name> ---` 加内容，预算 `share(input, 15)`，优先保留最近的 |
| 放不下的技能 | 一行提示，告诉模型需要时重新加载 |

压缩之前还有些条目的效果要延续，`RunItems` 通过 `carriedItem` 条件把它们读出来：

| 条目 | 延续的效果 |
|---|---|
| 所有 `userMessage` | 进入压缩历史的用户消息部分 |
| 决定为 `acceptForSession` 的工具调用 | "在此会话中允许"继续生效 |
| 完成的 `load_tools` | 已加载的工具继续在工具列表里 |
| 结果带 artifacts 的调用 | 激活的技能继续有效 |

记忆快照不延续。`hasSnapshot` 从后往前找，先碰到压缩就算没有快照。所以压缩后、以及每次进槽位时如果还没有，都会载入一份新的，预算是 `MemoryBudget`。

## 系统提示词

`systemprompt.Build` 把各段用空行连起来。顺序是从最稳定到最不稳定，这样其他会话和子 agent 的请求能共享缓存的前缀。

| 顺序 | 段 | 什么时候有 |
|---|---|---|
| 1 | agent 提示词 | 总有。`Config.Prompt`，空时用默认的个人助手提示词 |
| 2 | 循环规则 | 总有。`loopRules`，精简模式用 `compactRules` |
| 3 | `# AVAILABLE SKILLS` | 有技能且不是精简模式 |
| 4 | `# DEFERRED TOOLS` | 有延迟加载的工具 |
| 5 | `# PROJECT` | 会话属于工作区，写明项目路径 |
| 6 | `# You are a subagent` | 子 agent |

`loopRules` 包含 `Working rules`、`Safety`、`Final answer` 三节，这样安全规则不依赖 agent 提示词，自定义提示词的 agent 也有。

技能目录超过 `SkillBudget` 时从末尾删，并写明 `[N more skills are not listed: the catalog is over its budget]`。

系统提示词在 `Runtime.start` 里组装一次，这次运行的所有模型调用都用同一份。

## 延迟加载工具

工具定义也占输入预算。工具太多，或者模型的输入预算很小时，一部分工具只列名字，模型用到时再用 `load_tools` 载入。载入只会把工具追加到列表末尾，请求开头不变，前缀缓存继续有效。触发条件和细节见[工具](/zh/engine/tools#延迟加载)。

## 精简模式

`input` 小于 16384（`compactInputTokens`）的模型走精简模式。完整的提示词和工具列表约 8k token，`Fits` 把它们限制在 `input` 的一半以内，这样的模型放不下。以前一个这样的模型会让整个 agent 启动失败。

| 方面 | 普通模式 | 精简模式 |
|---|---|---|
| 规则 | `loopRules` | `compactRules`，只留最核心的规则 |
| 技能目录 | 列出 | 不列 |
| 工具定义 | 全部，或只延迟外部工具 | `read_file`、`run_command`、`load_tools` |
| 其他工具 | 正常 | 只在 `# DEFERRED TOOLS` 里列名字 |
| 向用户提问 | `request_user_input` | 规则改成需要时在回复里问，因为这个工具默认没加载 |

`compactRules` 还提醒模型上下文很小，只读需要的行，保持命令输出简短。

## 前缀缓存的稳定性

服务商的前缀缓存要求请求开头逐字节相同。下面这些设计都为了这一点，或者与它一致：

| 做法 | 效果 |
|---|---|
| 系统提示词按稳定程度排序 | 同一 agent 的不同会话和子 agent 共享开头 |
| 系统提示词不含当前时间 | 时间写在每条用户消息里，来自存好的 `started_at`，重新组装时不变 |
| 工具按提供方和名字排序 | `Registry` 的列表是确定的 |
| 工具列表只增不减 | 已加载的工具接在末尾 |
| `# DEFERRED TOOLS` 不随加载变化 | 系统提示词在会话里保持不变 |
| 记忆快照只在压缩后刷新 | 快照是一个存下来的条目，是第一条消息，不会每轮都变 |
| 旧工具结果用固定预算渲染 | `limit` 只影响最近一次回答，已发过的内容渲染结果不变 |
| 脱敏占位符稳定 | 每个用户一个 `redaction_key`，同一值在重启后仍得到同一占位符 |
| `native` 原样回放 | 同类提供方收到自己的原始回答记录 |

压缩会换掉前缀，这是它的代价，所以 80% 才触发。

各提供方的缓存方式不同：Anthropic 请求带 `cache_control`（自动断点），Gemini 用隐式缓存。每次模型调用的用量里记下缓存命中和写入的 token（`cached_input_tokens`、`cache_write_input_tokens`）。详情见[模型](/zh/engine/models)。

## 上下文统计

每次模型调用把 `repo.ContextStats` 写到它的第一个条目上，界面的上下文面板读它：

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

## 代码位置

| 仓库 | 路径 | 职责 |
|---|---|---|
| ollupi | `pkg/llm/connection.go` | `Limits`、`Input`、`Answer` |
| ollupi | `pkg/llm/tokens.go` | `EstimateTokens` |
| ollupi | `agent/contextmanager/manager.go` | 预算、组装、校准 |
| ollupi | `agent/contextmanager/compaction.go` | 压缩请求和压缩历史 |
| ollupi | `agent/contextmanager/observation.go` | 工具输出渲染和裁剪 |
| ollupi | `agent/contextmanager/outputs.go` | `read_tool_output` |
| ollupi | `agent/systemprompt/systemprompt.go` | 系统提示词 |
| ollupi | `agent/runtime/runtime.go` | `Offer`、`start`、记忆载入 |
| ollupi | `agent/runtime/chat.go` | `respond`、`compact`、`send` |
| ollupi | `agent/runtime/loader.go` | `load_tools` |
| ollupi | `agent/models.go` | `windowFor`、`checkPromptFits` |
| ollupi | `repo/turns.go` | `RunItems`、`carriedItem` |
