# 记忆

长期记忆是引擎从已经结束的轮次里提炼出来的笔记，会话运行时载入其中放得下的部分。客户端用 `memory/*` 查看记忆和提炼的状态，替用户改正、搬动或遗忘某一条，用 `memory/changed` 跟上变化；会话里的 `memoryContext` 条目告诉客户端这一轮带上了哪些记忆。提炼怎样取证据、怎样合并、怎样重试，见[记忆的实现](/zh/engine/memory)；开关在[设置](/zh/integrate/protocol/settings)里。

示例来自对本机网关的脚本试验（假模型、单用户，两条记忆是直接写进库里的）。

## 概念与状态

**范围（scope）。** 每条记忆属于三种范围之一：

| 范围 | 含义 | 载入哪些会话 |
|---|---|---|
| `global` | 和工作区无关的偏好和事实 | 所有会话 |
| `general` | 不属于任何工作区的会话里得出的 | 不属于工作区的会话 |
| `workspace` | 某个工作区里得出的，带 `workspaceId` | 这个工作区的会话 |

同一范围里 `topic` 唯一。全局记忆可以带 `originWorkspaceId`，记着它是从哪个工作区搬过来的。

**状态。** `active` 是在用的；`retired` 是被后来的提炼替换掉的；`forgotten` 是用户遗忘的，正文已清空。只有 `active` 的记忆会载入会话、出现在搜索里。

**用户编辑优先。** 用户改过的记忆（`userEdited`）提炼时不再覆盖。

**谁决定提炼和载入。**

| 条件 | 管什么 | 在哪里改 |
|---|---|---|
| 宿主给了提炼模型 `host.Config.Memory` | 有没有后台提炼 | 宿主配置，协议里改不了 |
| 用户的 `memory` 开关 | 载入、`memory_search` 工具、提炼，三样一起 | `settings/update` |
| 用户的 `learn` 开关 | 只管提炼 | `settings/update` |

开关关着时结束的轮次，提炼读到时直接跳过，以后重新打开也不补学。`memory/*` 方法和 `search` 不看开关，关着时照样能列、能改、能搜。

**变更有通知。** 每次一条记忆被写入，不管是客户端改的还是后台提炼写的，网关都发 `memory/changed`，载荷是写之后的整条记忆。提炼的进度（`memory/status`）变化时没有通知。

::: info 演进
v0.12.1 的记忆没有任何通知，两个开关 `generationEnabled`、`useEnabled` 是宿主的配置，没配记忆时所有 `memory/*` 都返回 `-32000`。`3580e6f` 把记忆开关存进每个用户的设置；`499f96f` 加了 `memory/changed`，`memory/status` 改成 `enabled`、`unread`、`active`；`e451d91` 拆出 `learn` 开关。
:::

## 一轮里的记忆：memoryContext 条目

`memory` 开关开着、会话里还没有快照（或者上次压缩之后还没有）时，引擎在每次调用模型之前生成一份记忆快照：这个用户的全局记忆，加上会话所在范围（这个工作区，或不属于工作区）的记忆，挑 `active` 的、按类型排序、放进预算里。放进了至少一条时，快照记成一条 `memoryContext` 条目，状态直接是 `completed`；一条也没有时不生成条目，下一次调用模型前再试。有了快照之后同一会话不再生成新的，直到下一次压缩。浏览器子 agent 不载入记忆。

条目里和记忆有关的两个字段：

| 字段 | 说明 |
|---|---|
| `memory?` | [`MemoryReference[]`](#memoryreference)：这次载入了哪些记忆 |
| `text?` | 发给模型的快照正文 |

`ItemRow` 的其余字段见[一轮与条目](/zh/integrate/protocol/turns)。快照放多少条、怎样排序，见[快照](/zh/engine/memory#快照)。模型在一轮里还可以调 `memory_search` 工具搜更多记忆，它是普通的工具调用，界面按通用调用显示。

::: info 演进
v0.12.1 在会话第一次运行时总会生成 `memoryContext` 条目，没有记忆可载入时条目照样有，只是两个字段都不出现。`b7b6bdf` 把一轮改成从日志一步步运行，没有可载入的记忆就不写这条条目。
:::

## 典型流程

查看提炼状态（这个宿主没有配提炼模型）：

```json
→ {"jsonrpc":"2.0","id":57,"method":"memory/status","params":{}}
← {"jsonrpc":"2.0","id":57,"result":{"enabled":true,"unread":0,"active":0,"skipped":0}}
```

记忆页按范围分别列出。列工作区范围时必须带 `workspaceId`，其他范围不能带：

```json
→ {"jsonrpc":"2.0","id":58,"method":"memory/list","params":{"scope":"workspace"}}
← {"jsonrpc":"2.0","id":58,"error":{"code":-32602,"message":"invalid memory change: give a workspaceId with the workspace scope, and only with it"}}
→ {"jsonrpc":"2.0","id":60,"method":"memory/list","params":{"scope":"workspace","workspaceId":"4dc76ecd-…"}}
← {"jsonrpc":"2.0","id":60,"result":{"data":[{"id":"m1","scope":"workspace","workspaceId":"4dc76ecd-…","topic":"deploy target","kind":"fact","text":"Deploys go to the staging cluster first.","status":"active","sources":[{"thread":"3f8c1952-…","item":"c2"}],"createdAt":"2026-11-18T12:19:29.298599Z","updatedAt":"2026-11-18T12:19:29.298599Z"}]}}
```

改正一条，网关先发 `memory/changed`，再回复同一条：

```json
→ {"jsonrpc":"2.0","id":61,"method":"memory/update","params":{"id":"m1","text":"Deploys go to staging first, then production."}}
← {"jsonrpc":"2.0","method":"memory/changed","params":{"memory":{"id":"m1","scope":"workspace", … ,"text":"Deploys go to staging first, then production.","status":"active","userEdited":true, … ,"updatedAt":"2026-11-18T12:19:29.800986Z"}}}
← {"jsonrpc":"2.0","id":61,"result":{"memory":{ …同上… }}}
```

搬到全局，再搬回来：

```json
→ {"jsonrpc":"2.0","id":62,"method":"memory/move","params":{"id":"m1"}}
← {"jsonrpc":"2.0","method":"memory/changed","params":{"memory":{"id":"m1","scope":"global","originWorkspaceId":"4dc76ecd-…", … }}}
← {"jsonrpc":"2.0","id":62,"result":{"memory":{ … }}}
→ {"jsonrpc":"2.0","id":63,"method":"memory/move","params":{"id":"m1"}}
← {"jsonrpc":"2.0","method":"memory/changed","params":{"memory":{"id":"m1","scope":"workspace","workspaceId":"4dc76ecd-…", … }}}
← {"jsonrpc":"2.0","id":63,"result":{"memory":{ … }}}
```

遗忘一条，通知里正文已清空，回复是 `{}`；之后再改它被拒：

```json
→ {"jsonrpc":"2.0","id":64,"method":"memory/forget","params":{"id":"m2"}}
← {"jsonrpc":"2.0","method":"memory/changed","params":{"memory":{"id":"m2","scope":"global","topic":"language","kind":"preference","text":"","status":"forgotten","sources":[], … }}}
← {"jsonrpc":"2.0","id":64,"result":{}}
→ {"jsonrpc":"2.0","id":65,"method":"memory/update","params":{"id":"m2","text":"x"}}
← {"jsonrpc":"2.0","id":65,"error":{"code":-32602,"message":"invalid memory change: a forgotten memory cannot be edited"}}
```

客户端的本地状态只需要一张按 `id` 索引的记忆表：`memory/list` 读一次，之后每条 `memory/changed` 按 `id` 整条替换。

## 方法

### memory/list

| 参数 | 类型 | 说明 |
|---|---|---|
| `scope` | `Scope` | `global`、`general`、`workspace` |
| `workspaceId?` | string | `scope` 是 `workspace` 时必填，其他范围时不能给 |

结果是 `{data: MemoryRow[]}`，只含这一个范围的记忆（列 `workspace` 范围时不含全局记忆），三种状态都在里面，按 `updatedAt` 倒序，相同时按 `id`。`workspaceId` 不存在时返回空数组。

| 错误 | 什么时候 |
|---|---|
| `-32602` | `scope` 不是三者之一：`invalid memory change: the scope must be one of [global general workspace]`；`workspaceId` 和 `scope` 不配：见上面的示例 |

### memory/status

无参数，结果是 [`MemoryStatus`](#memorystatus)。

### memory/update

| 参数 | 类型 | 说明 |
|---|---|---|
| `id` | string | 记忆 ID |
| `text` | string | 新的正文，去掉首尾空白后 1 到 4000 字符 |

结果是 `{memory: MemoryRow}`，同时发 `memory/changed`。改完的记忆 `userEdited` 为 `true`、状态变成 `active`：改一条 `retired` 的记忆会让它重新生效。

| 错误 | 什么时候 |
|---|---|
| `-32602` | 正文为空或超长：`invalid memory change: memory text must contain 1 to 4000 characters`；记忆已被遗忘：`a forgotten memory cannot be edited` |
| `-32004` | 记忆不存在或属于别人（`id` 为空也是这样）：`store: memory <id>: store: not found` |

### memory/move

参数 `id`。在全局和本地范围之间切换：

| 原来 | 之后 |
|---|---|
| `workspace` 或 `general` | `global`；从工作区搬来的，`originWorkspaceId` 记下原来的工作区 |
| `global` | 回到 `originWorkspaceId` 指的工作区（`workspace`）；没有来源工作区时变成 `general` |

结果是 `{memory: MemoryRow}`，同时发 `memory/changed`。

| 错误 | 什么时候 |
|---|---|
| `-32602` | 记忆已被遗忘：`a forgotten memory cannot be moved`；目标范围里已有同一 `topic` 的记忆，不论它是什么状态：`a memory with the topic "…" is already there; forget or edit that one instead` |
| `-32004` | 记忆不存在或属于别人 |

### memory/forget

参数 `id`，结果 `{}`，同时发 `memory/changed`。把记忆标成 `forgotten` 并清空正文，这一行留在库里。对已遗忘的记忆再调一次也成功，也会再发一条通知。被遗忘记忆引用过的证据，之后的提炼不会再拿来用，见[用户编辑保护](/zh/engine/memory#用户编辑保护)。

错误：`-32004` 记忆不存在或属于别人。

## 通知：memory/changed

载荷是 `MemoryResult`：`{"memory": MemoryRow}`，写之后的整条记忆。什么时候发：

| 起因 | 记忆的样子 |
|---|---|
| `memory/update`、`memory/move` | 改之后的 |
| `memory/forget` | `status` 为 `forgotten`、`text` 为空 |
| 后台提炼新建、更新或退役了一条 | 写之后的那条；退役的 `status` 是 `retired`。一次提炼动了几条就发几条 |

通知在事务提交之后、回复之前，发给这个用户的每一条连接。记忆不会被物理删除，所以没有"已删除"的形式。

## 类型

### MemoryRow

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | string | 记忆 ID |
| `scope` | `Scope` | `global`、`general`、`workspace` |
| `workspaceId?` | string | `scope` 是 `workspace` 时的工作区 |
| `originWorkspaceId?` | string | 全局记忆是从哪个工作区搬过来的，只在 `global` 上出现 |
| `topic` | string | 主题，同一范围内唯一 |
| `kind` | `Kind` | `preference`、`decision`、`fact`、`procedure` |
| `text` | string | 正文；遗忘后为空字符串 |
| `status` | `Status` | `active`、`retired`、`forgotten` |
| `userEdited?` | boolean | 用户改过，提炼不再覆盖 |
| `sources` | [`MemorySource[]`](#memorysource) | 证据，总是数组 |
| `createdAt`、`updatedAt` | string | |

`Scope`、`Kind`、`Status` 是契约里这三个枚举的名字。

### MemorySource

| 字段 | 类型 | 说明 |
|---|---|---|
| `thread` | string | 证据所在的会话 |
| `item` | string | 证据所在的条目 |

客户端可以用 `thread` 打开会话，再在条目里找 `item`。

### MemoryReference

`memoryContext` 条目的 `memory` 里用的精简形式：

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | string | 记忆 ID，可以用来在 `memory/list` 的结果里找到完整的一条 |
| `topic?` | string | 主题 |
| `text` | string | 载入时的正文 |
| `scope` | string | 范围，取值同 `Scope` |
| `workspaceId?` | string | `workspace` 范围时的工作区 |

### MemoryStatus

| 字段 | 类型 | 说明 |
|---|---|---|
| `enabled` | boolean | 用户的 `memory` 开关，同 `SettingsRow.memory`；不反映 `learn`，也不反映宿主有没有配提炼模型 |
| `unread` | integer | 已结束、提炼还没读到的轮次数，包括子 agent 会话的轮次。没配提炼模型时只增不减 |
| `active` | integer | `active` 状态的记忆条数 |
| `attempts?` | integer | 当前这一轮连续失败的次数 |
| `nextAttempt?` | string | 下次重试的时间：失败后等 1、2、4……分钟，最多 60 分钟 |
| `skipped` | integer | 累计跳过的轮次数：一轮连续失败 10 次后被跳过，见[失败重试和跳过](/zh/engine/memory#失败重试和跳过) |
| `lastSuccess?` | string | 上次成功的时间 |
| `lastFailure?` | `MemoryFailure` | 上次失败，成功后清掉 |
| `lastSkip?` | `MemorySkip` | 上次跳过的那一轮 |

`MemoryFailure` 是 `{code, error}`。`code` 是 `FailureCode`：

| `code` | 含义 |
|---|---|
| `model_request` | 模型请求失败 |
| `invalid_response` | 模型的回答不合格式 |
| `evidence` | 读证据出错 |
| `storage` | 写库出错 |

`MemorySkip` 是 `MemoryFailure` 的两个字段加上 `at`（跳过的时间）、`threadId`、`turnId`（被跳过的那一轮）。

### 参数类型

`MemoryListParams`、`MemoryUpdateParams`、`MemoryMoveParams`、`MemoryForgetParams` 的字段就是上面各方法的参数表；`MemoryListResult` 包了一层 `data`，`MemoryResult` 包了一层 `memory`。

::: info 演进
v0.12.1 的 `MemorySource` 是 `{table, id, occurredAt}`，`MemoryStatus` 有 `generationEnabled`、`useEnabled`、`pending` 和上次提炼的用量 `lastReport`，`MemorySkip` 还有 `entries`。`50c35eb` 改成按轮次提炼，证据记成会话和条目；`499f96f` 换成现在的 `MemoryStatus`。
:::

## 错误与边界

- **`memory/list` 不含全局记忆。** 列工作区范围只返回这个工作区的记忆。一个工作区实际会载入的是"这个工作区的加上全局的"，客户端要显示完整情况得调两次。
- **遗忘不可撤销。** `memory/forget` 清空正文，之后不能编辑也不能搬动，只能等提炼从新的证据里重新得出。
- **被遗忘或替换的同名记忆挡住搬动。** 目标范围里只要有同一 `topic` 的记忆，哪怕已经 `forgotten` 或 `retired`，`memory/move` 也会被拒。
- **提炼的进度没有通知。** `unread`、`lastSuccess` 这些只能靠轮询 `memory/status`；新记忆本身有 `memory/changed`。
- **关掉开关不藏记忆。** `memory` 关着时会话不用记忆，但 `memory/list` 和 `search` 照样返回它们。

## 代码位置

| 路径 | 职责 |
|---|---|
| `gateway/owned.go` | `memory/*` 的处理函数，`memory/status` 合上用户的开关 |
| `gateway/server.go` | 把变更流里的事件转成 `memory/changed` |
| `gateway/protocol.go`、`gateway/wire.go` | `MemoryListParams`、`MemoryUpdateParams`、`MemoryMoveParams`、`MemoryForgetParams`、`MemoryResult`、`MemoryRow`、`MemoryStatus` |
| `app/memory.go` | `Memories`、`MemoryStatus`、`EditMemory`、`MoveMemory`、`ForgetMemory` |
| `memory/memory.go` | `Scope`、`Kind`、`Status`、`Place.Check`、`Edit`、`Move`、`Forget` |
| `memory/state.go` | `State`、`Failure`、`Skip`，重试间隔和 10 次上限 |
| `memory/recall.go` | 记忆快照：载入哪些、放多少 |
| `run/model.go` | `recall`：什么时候生成 `memoryContext` 条目 |
| `extract/extract.go` | 后台提炼；开关关着时跳过轮次 |
| `store/sqlite/memories.go` | `memories`、`memory_state` 两张表，`PutMemory` 发出 `memory/changed` 的事件，`Unread` |
