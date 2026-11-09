# 记忆

长期记忆是引擎从已经结束的轮次里提炼出来的笔记，新会话开始时载入其中放得下的部分。客户端用 `memory/*` 查看记忆和提炼的状态，替用户改正、搬动或遗忘某一条；会话里的 `memoryContext` 条目告诉客户端这一轮带上了哪些记忆。提炼怎样取证据、怎样合并、怎样重试，见[记忆的实现](/zh/engine/memory)。

## 概念与状态

**范围（scope）。** 每条记忆属于三种范围之一：

| 范围 | 含义 | 载入哪些会话 |
|---|---|---|
| `global` | 和工作区无关的偏好和事实 | 所有会话 |
| `general` | 不属于任何工作区的会话里得出的 | 不属于工作区的会话 |
| `workspace` | 某个工作区里得出的，带 `workspaceId` | 这个工作区的会话 |

同一范围里 `topic` 唯一。全局记忆可以带 `originWorkspaceId`，记着它是从哪个工作区的证据里提炼的。

**状态。** `active` 是在用的；`retired` 是被后来的提炼替换掉的；`forgotten` 是用户遗忘的，正文已清空。只有 `active` 的记忆会载入会话、出现在搜索里。

**用户编辑优先。** 用户改过的记忆（`userEdited`）提炼时不再覆盖。

**两个开关由宿主决定。** `memory/status` 的 `generationEnabled` 表示后台提炼开着，`useEnabled` 表示记忆会载入会话。两者都来自宿主装配 `memory.Manager` 时的选项，协议里改不了。

**没有变更通知。** 记忆的增删改，包括后台提炼产生的，都不发通知。客户端要看最新的列表，就重新调 `memory/list`；要知道提炼有没有进展，就调 `memory/status`。

## 一轮里的记忆：memoryContext 条目

`useEnabled` 时，会话第一次运行，以及每次上下文压缩完成之后的下一次运行，引擎会生成一份记忆快照，记成一条 `memoryContext` 条目，状态直接是 `completed`。客户端先后收到它的 `item/started` 和 `item/completed`。快照之后同一会话不再生成新的，直到下一次压缩。

条目里和记忆有关的两个字段：

| 字段 | 说明 |
|---|---|
| `memory?` | `MemoryReference[]`：这次载入了哪些记忆 |
| `text?` | 发给模型的快照正文 |

没有记忆可载入、或者一条也放不下时，条目照样生成，只是两个字段都不出现。录制的会话里就是这样（来自桌面端仓库的 `packages/protocol/fixtures/session.json`）：

```json
{"jsonrpc":"2.0","method":"item/completed","params":{"threadId":"9f311e1e-…","turnId":"59bc7f8b-…","item":{"id":"87577c1e-…","turnId":"59bc7f8b-…","seq":2,"type":"memoryContext","status":"completed","startedAt":"2026-11-08T11:44:54.508058Z","completedAt":"2026-11-08T11:44:54.508058Z"}}}
```

`ItemRow` 的其余字段见[一轮与条目](/zh/integrate/protocol/turns)。快照放多少条、怎样排序，见[快照](/zh/engine/memory#快照)。模型在一轮里还可以调 `memory_search` 工具搜更多记忆，它是普通的工具调用，界面按通用调用显示。

## 典型流程

下面的消息来自同一份录制。查看提炼状态：

```json
{"jsonrpc":"2.0","id":31,"method":"memory/status","params":{}}
{"jsonrpc":"2.0","id":31,"result":{"generationEnabled":false,"useEnabled":true,"pending":14,"active":0,"skipped":0}}
```

记忆页按范围分别列出。列工作区范围时必须带 `workspaceId`，其他范围不能带：

```json
{"jsonrpc":"2.0","id":34,"method":"memory/list","params":{"scope":"workspace","workspaceId":"ab146065-…"}}
{"jsonrpc":"2.0","id":34,"result":{"data":[]}}
{"jsonrpc":"2.0","id":35,"method":"memory/list","params":{"scope":"workspace"}}
{"jsonrpc":"2.0","id":35,"error":{"code":-32602,"message":"invalid memory change: give a workspaceId with the workspace scope, and only with it"}}
```

找不到的记忆：

```json
{"jsonrpc":"2.0","id":36,"method":"memory/move","params":{"id":"no-such-memory"}}
{"jsonrpc":"2.0","id":36,"error":{"code":-32004,"message":"storage: not found"}}
```

改动方法（`memory/update`、`memory/move`、`memory/forget`）之后，客户端用返回的 `memory` 替换本地那一条；`memory/forget` 不返回记忆，本地把它标成 `forgotten`、清空正文即可，和库里一致。

## 方法

宿主没有配置 `gateway.Options.Memory` 时，所有 `memory/*` 都返回 `-32000` `long-term memory is unavailable`，包括 `memory/list` 和 `memory/status`。

### memory/list

| 参数 | 类型 | 说明 |
|---|---|---|
| `scope` | `MemoryScope` | `global`、`general`、`workspace` |
| `workspaceId?` | string | `scope` 是 `workspace` 时必填，其他范围时不能给 |

结果是 `{data: MemoryRow[]}`，只含这一个范围的记忆（列 `workspace` 范围时不含全局记忆），三种状态都在里面，按 `updatedAt` 倒序。`workspaceId` 不存在时返回空数组。

| 错误 | 什么时候 |
|---|---|
| `-32602` | `scope` 不是三者之一：`invalid memory change: the scope must be one of [...]`；`workspaceId` 和 `scope` 不配：见上面的示例 |

### memory/status

无参数，结果是 `MemoryStatus`，见[类型](#memorystatus)。

### memory/update

| 参数 | 类型 | 说明 |
|---|---|---|
| `id` | string | 必填 |
| `text` | string | 新的正文，去掉首尾空白后 1 到 4000 字符 |

结果是 `{memory: MemoryRow}`。改完的记忆 `userEdited` 为 `true`、状态变成 `active`：改一条 `retired` 的记忆会让它重新生效。

| 错误 | 什么时候 |
|---|---|
| `-32602` `id is required` | `id` 为空 |
| `-32602` | 正文为空或超长：`memory text must contain 1 to 4000 characters`；记忆已被遗忘：`a forgotten memory cannot be edited` |
| `-32004` | 记忆不存在或属于别人 |

### memory/move

参数 `id`。在全局和本地范围之间切换：

| 原来 | 之后 |
|---|---|
| `workspace` 或 `general` | `global`，`originWorkspaceId` 记下原来的工作区 |
| `global` | 回到 `originWorkspaceId` 指的工作区（`workspace`）；没有来源工作区时变成 `general` |

结果是 `{memory: MemoryRow}`。

| 错误 | 什么时候 |
|---|---|
| `-32602` `id is required` | `id` 为空 |
| `-32602` | 记忆已被遗忘；目标范围里已有同一 `topic` 的记忆：`a memory with the topic "…" is already there; forget or edit that one instead` |
| `-32004` | 记忆不存在或属于别人 |

### memory/forget

参数 `id`，结果 `{}`。把记忆标成 `forgotten` 并清空正文，这一行留在库里。对已遗忘的记忆再调一次直接成功。被遗忘记忆引用过的证据，之后的提炼不会再拿来用，见[用户编辑保护](/zh/engine/memory#用户编辑保护)。

错误：`-32602` `id is required`；`-32004` 记忆不存在或属于别人。

## 类型

### MemoryRow

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | string | 记忆 ID |
| `scope` | `MemoryScope` | `global`、`general`、`workspace` |
| `workspaceId?` | string | `scope` 是 `workspace` 时的工作区 |
| `originWorkspaceId?` | string | 全局记忆是从哪个工作区的证据提炼出来的，只在 `global` 上出现 |
| `topic` | string | 主题，同一范围内唯一 |
| `kind` | string | `preference`、`decision`、`fact`、`procedure`；契约里是普通字符串 |
| `text` | string | 正文；遗忘后为空字符串 |
| `status` | `MemoryRowStatus` | `active`、`retired`、`forgotten` |
| `userEdited?` | boolean | 用户改过，提炼不再覆盖 |
| `sources` | `MemorySource[]` | 证据，总是数组 |
| `createdAt`、`updatedAt` | string | |

### MemorySource

| 字段 | 类型 | 说明 |
|---|---|---|
| `table` | string | 证据所在的表，目前总是 `items` |
| `id` | string | 条目 ID |
| `occurredAt?` | string | 证据发生的时间 |

### MemoryReference

`memoryContext` 条目的 `memory` 里用的精简形式：

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | string | 记忆 ID，可以用来在 `memory/list` 的结果里找到完整的一条 |
| `topic?` | string | 主题 |
| `text` | string | 载入时的正文 |
| `scope` | `MemoryScope` | 范围 |
| `workspaceId?` | string | `workspace` 范围时的工作区 |

### MemoryStatus

| 字段 | 类型 | 说明 |
|---|---|---|
| `generationEnabled` | boolean | 后台提炼开着 |
| `useEnabled` | boolean | 记忆会载入会话 |
| `pending` | integer | 已结束、还没提炼的轮次数 |
| `active` | integer | `active` 状态的记忆条数 |
| `attempts?` | integer | 连续失败的次数 |
| `nextAttempt?` | string | 下次重试的时间 |
| `skipped` | integer | 累计跳过的条目数：一批证据连续失败 10 次后被跳过，见[失败重试和跳过](/zh/engine/memory#失败重试和跳过) |
| `lastSuccess?` | string | 上次成功的时间 |
| `lastFailure?` | `MemoryFailure` | 上次失败 |
| `lastSkip?` | `MemorySkip` | 上次跳过的批次 |
| `lastReport?` | `MemoryReport` | 上次提炼请求的用量 |

`MemoryFailure` 是 `{code, error}`。`code` 是 `MemoryFailureCode`：

| `code` | 含义 |
|---|---|
| `model_request` | 模型请求失败 |
| `invalid_response` | 模型的回答不合格式 |
| `evidence` | 读证据出错 |
| `storage` | 写库出错 |

`MemorySkip` 是 `MemoryFailure` 的两个字段加上 `at`（跳过的时间）、`entries`（跳过的条目数）、`threadId`、`turnId`（这批证据所在的会话和轮次）。

`MemoryReport`：

| 字段 | 类型 | 说明 |
|---|---|---|
| `model` | `Model` | 提炼用的模型，同 `model/list` 里的 `Model`，见[模型、工具与 MCP](/zh/integrate/protocol/models-tools) |
| `estimatedInputTokens` | integer | 发送前估算的输入 token |
| `inputTokens`、`outputTokens` | integer | 服务商报告的用量 |
| `usageReported` | boolean | 服务商是否报告了用量；`false` 时前两个数不可信 |

## 错误与边界

- **没有通知，只能轮询。** 后台提炼写入或替换了记忆，客户端不会知道，要靠重新 `memory/list`。`memory/status` 的 `pending` 和 `lastSuccess` 可以拿来判断是否值得重读。
- **`memory/list` 不含全局记忆。** 列工作区范围只返回这个工作区的记忆。一个工作区实际会载入的是"这个工作区的加上全局的"，客户端要显示完整情况得调两次。
- **遗忘不可撤销。** `memory/forget` 清空正文，之后不能编辑也不能搬动，只能等提炼从新的证据里重新得出。
- **开关不在协议里。** 提炼和载入的开关、提炼用的模型都是宿主的配置，客户端只能从 `memory/status` 读到。

## 代码位置

| 仓库 | 路径 | 职责 |
|---|---|---|
| ollupi | `gateway/memory.go` | `memory/*` 的处理函数，未配置时的 `-32000` |
| ollupi | `gateway/protocol.go` | `MemoryListParams`、`MemoryUpdateParams`、`MemoryMoveParams`、`MemoryForgetParams`、`MemoryResult` |
| ollupi | `agent/memory/manager.go` | `List`、`Edit`、`Move`、`Forget`、`Status` 的校验和改动 |
| ollupi | `agent/memory/recall.go` | 记忆快照：载入哪些、放多少 |
| ollupi | `agent/runtime/runtime.go` | 什么时候生成 `memoryContext` 条目 |
| ollupi | `repo/memories.go` | `MemoryRow`、`MemorySource`、范围和状态的取值 |
| ollupi | `repo/memory_state.go` | `MemoryStatus`、`MemoryFailure`、`MemorySkip`、`MemoryReport` |
| ollupi | `repo/items.go` | `MemoryReference` |
