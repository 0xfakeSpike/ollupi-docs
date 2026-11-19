# 会话

会话（thread）是一段连续的对话，客户端用 `thread/*` 方法新建、列出、读取、改名、标记已读、归档和删除它，用 `thread/changed` 跟上它的变化。会话里的每一轮（turn）和条目（item）见[一轮与条目](/zh/integrate/protocol/turns)。

本页按引擎 v0.17.2 写。连接、认证、握手和错误码的通用规则见[网关协议](/zh/integrate/protocol)，怎样用 `seq` 把读到的一页和之后的通知对齐见[写一个客户端](/zh/integrate/client#本地状态)。

## 概念与状态

一个会话属于一个用户，可以属于一个工作区（`workspaceId`），也可以不属于任何工作区（界面上叫 general）。它还在某个执行环境（`environmentId`）里运行，环境在建会话时定下，之后不变，见[工作区与执行环境](/zh/integrate/protocol/workspaces)。

会话的内容是一份只追加的日志：用户的消息、模型的回答、工具调用的每一步都是追加进去的记录，轮次和条目是从日志算出来的投影，机制见[持久化](/zh/engine/persistence)。客户端看不到日志本身，只看到投影出来的行。

会话分两种：

| 种类 | 怎样产生 | `parentThreadId` | 在 `thread/list` 里 |
|---|---|---|---|
| 顶层会话 | 客户端调 `thread/start` | 没有 | 列出 |
| 子 agent 会话 | 模型调子 agent 工具（`general-sub-agent`、`browser-sub-agent`），引擎自己建 | 父会话的 ID | 不列出 |

子 agent 会话能读，但不能改，见下文[子 agent 会话](#子-agent-会话)。

### 会话状态

会话状态是 `ThreadRow.status`，每次 `thread/changed` 都带着它，`thread/list` 和 `thread/read` 读到的行里也有。它从会话日志里的当前一轮算出来（`conversation.View.Status`）：

| `ThreadStatus` | 什么时候 |
|---|---|
| `idle` | 没有当前一轮：没有还没结束的轮次 |
| `active` | 当前一轮在排队等槽位、在运行，或回答完了在等它启动的子 agent 回报 |
| `waitingOnApproval` | 当前一轮有调用在等审批；或者某个子 agent 会话在等审批 |
| `waitingOnUserInput` | 当前一轮有调用在等用户回答；或者某个子 agent 会话在等回答 |

子 agent 会话在等用户时，父会话也显示为在等：子会话的记录写入时，存储在同一个事务里重算它的祖先会话的状态，审批排在提问前面（`conversation.RollUp`），父会话的状态变了也会收到一条 `thread/changed`。客户端看顶层会话的状态就知道要不要提醒用户。等子 agent 本身不是一种状态，这时是 `active`。

### 已读和未读

`repliedAt` 是顶层会话的某一轮最近一次结束的时间，`readAt` 是用户最近一次调 `thread/markRead` 的时间。`repliedAt` 比 `readAt` 晚（或者有 `repliedAt` 而没有 `readAt`）时，这个会话有用户还没看过的回答。引擎只记这两个时间，"未读"由客户端比较得出；子 agent 会话的轮次结束不写 `repliedAt`。

::: info 演进
v0.12.1 的 `ThreadRow` 不带状态，状态只出现在 `thread/list` 的 `ThreadSummary` 和 `thread/status/changed` 通知里。v0.16.0 把状态放进行里、删掉这两者（`9b5b50b`）；子 agent 的等待算进父会话的状态在重建时丢过一次，v0.16.1 补回（`b02dbfd`）。已读和未读来自 `d6a80e8`。
:::

## 典型流程

下面的消息来自对着 v0.17.1 跑的一个最小宿主：`host.New` 配一个脚本化的假模型和一个非只读工具 `deploy`，网关用单用户令牌。ID、时间和 `seq` 是当时的值。

### 新建、列出、读取

新建一个会话。`thread/changed` 先于回复到达，带的是同一行：

```json
{"jsonrpc": "2.0", "id": 2, "method": "thread/start", "params": {"title": "Release notes"}}
{"jsonrpc": "2.0", "method": "thread/changed", "params": {
  "threadId": "a591bb17-9594-4102-959d-0d5d7a022a14",
  "thread": {
    "id": "a591bb17-9594-4102-959d-0d5d7a022a14",
    "environmentId": "896cdd51-3b22-4aaf-8e5b-e2ff4dc1a231",
    "title": "Release notes",
    "settings": {"permissions": {}},
    "status": "idle",
    "createdAt": "2026-11-18T12:24:06.105412Z",
    "updatedAt": "2026-11-18T12:24:06.105412Z"},
  "seq": 55}}
{"jsonrpc": "2.0", "id": 2, "result": {"thread": { "...": "同上" }}}
```

列出会话，每一项就是 `ThreadRow`：

```json
{"jsonrpc": "2.0", "id": 5, "method": "thread/list", "params": {"limit": 1}}
{"jsonrpc": "2.0", "id": 5, "result": {"data": [{
  "id": "a591bb17-9594-4102-959d-0d5d7a022a14",
  "environmentId": "896cdd51-3b22-4aaf-8e5b-e2ff4dc1a231",
  "title": "Release notes",
  "settings": {"approvalPolicy": "never", "permissions": {"deny": ["deploy"]}},
  "status": "idle",
  "createdAt": "2026-11-18T12:24:06.105412Z",
  "updatedAt": "2026-11-18T12:24:06.349957Z",
  "repliedAt": "2026-11-18T12:24:06.349957Z"}], "hasMore": true}}
```

打开一个会话时用 `thread/resume` 读最新一页，往上翻用 `thread/read` 带 `beforeSeq`。回复里的 `seq` 是读的那一刻已经提交到的序号，之后到达的通知里 `seq` 不大于它的都已经在这一页里。重连之后要重新读，因为断线期间的通知不补发，见[写一个客户端](/zh/integrate/client#重连)。

### 修改

改权限、改名、标记已读、归档都会发 `thread/changed`，带改过之后的整行，`updatedAt` 也会变：

```json
{"jsonrpc": "2.0", "id": 7, "method": "thread/markRead", "params": {"threadId": "a591bb17-9594-4102-959d-0d5d7a022a14"}}
{"jsonrpc": "2.0", "method": "thread/changed", "params": {
  "threadId": "a591bb17-9594-4102-959d-0d5d7a022a14",
  "thread": {"...": "...", "status": "idle",
             "updatedAt": "2026-11-18T12:24:06.658325Z",
             "repliedAt": "2026-11-18T12:24:06.349957Z",
             "readAt": "2026-11-18T12:24:06.658325Z"},
  "seq": 66}}
```

删除时 `thread` 为 `null`：

```json
{"jsonrpc": "2.0", "id": 10, "method": "thread/delete", "params": {"threadId": "a591bb17-9594-4102-959d-0d5d7a022a14"}}
{"jsonrpc": "2.0", "method": "thread/changed", "params": {"threadId": "a591bb17-9594-4102-959d-0d5d7a022a14", "thread": null, "seq": 68}}
{"jsonrpc": "2.0", "id": 10, "result": {}}
```

## 方法

所有方法都只能操作调用者自己的会话。别的用户的会话表现为不存在，返回 `-32004`。

### thread/start

新建一个顶层会话。

| 参数 | 类型 | 说明 |
|---|---|---|
| `workspaceId?` | string | 所属工作区。省略时不属于任何工作区 |
| `environmentId?` | string | 会话运行的执行环境，必须是这个用户的。省略时用他的本机环境（`local` 类型的那个） |
| `title?` | string | 标题。去掉首尾空白后最多 120 个字符，可以为空 |

新会话自己这一层的权限设置是空的，按部署、用户、工作区三层运行，之后用 `thread/updatePermissions` 改，见[权限](/zh/integrate/protocol/permissions)。

结果：`{thread: ThreadRow}`。回复之前已经发出 `thread/changed`。

| 错误 | 什么时候 |
|---|---|
| `-32602` | 标题超过 120 字符；参数里有契约之外的字段，比如旧客户端还在传 `approvalPolicy` 或 `permissions` |
| `-32004` | 工作区或执行环境不存在，或属于别的用户 |
| `-32014` | 工作区已归档 |

::: info 演进
v0.16.0 之前 `thread/start` 还收 `approvalPolicy` 和 `permissions`，作为新会话这一层的设置。`13eafa9` 去掉了这两个参数，新会话从空的一层开始。
:::

### thread/read 和 thread/resume

读会话的一页。两个方法的参数和结果一样，区别只在回复之后：`thread/resume` 会把这个会话和它的子 agent 会话里在等回答的请求再发一遍，这条连接上已经发过、还没回答的不重复发。客户端打开会话或重连后用 `thread/resume`，往上翻页用 `thread/read`。请求怎样重发见[审批与提问](/zh/integrate/protocol/approvals#重发)。

| 参数 | 类型 | 说明 |
|---|---|---|
| `threadId` | string | 会话 ID，子 agent 会话也可以读 |
| `beforeSeq?` | integer | 只取条目 `seq` 比它小的条目。省略或 `0` 表示从最新一条往前取 |
| `limit?` | integer | 条目数，默认 100，范围 1 到 500 |

结果是 `ThreadPageResult`：

| 字段 | 类型 | 说明 |
|---|---|---|
| `thread` | `ThreadRow` | 会话 |
| `turns` | `TurnRow[]` | 这一页的条目所属的轮次，加上所有还没结束的轮次，按提交顺序 |
| `items` | `ItemRow[]` | 这一页的条目，按条目 `seq` 升序 |
| `seq` | integer | 读这一页时已经提交到的序号。通知的 `seq` 不大于它时，那次变化已经在这一页里 |
| `hasMore` | boolean | 还有更早的条目 |

分页规则：

- 条目从新到旧取 `limit` 条，再按 `seq` 升序返回。下一页把这一页最小的 `seq` 作为 `beforeSeq`。条目的 `seq` 是条目在会话日志里第一次出现的位置，会跳号（日志里还有不成为条目的记录），只能用来排序和翻页。
- 页内条目序列化后累计超过 4 MiB（`pageBytes`）时，从旧的一端截掉，至少保留最新一条，`hasMore` 置为 `true`。
- 整页在一个读事务里读出，`seq` 也在同一个事务里读，所以这一页恰好包含序号不大于 `seq` 的全部提交。网关不阻止通知插在读和回复之间，对齐靠 `seq`，见[用 seq 对齐](/zh/integrate/client#用-seq-对齐)。

| 错误 | 什么时候 |
|---|---|
| `-32602` | `limit` 不在 1 到 500，或 `beforeSeq` 是负数 |
| `-32004` | 会话不存在或不是自己的 |

::: info 演进
v0.12.1 的一页带会话的全部轮次，没有 `seq`；网关从读库到回复入队之间持有这条连接的 `deliver` 锁，保证之后的通知排在回复后面。v0.16.0 去掉了这把锁，改成回报 `seq`、由客户端按 `seq` 丢掉已经包含的通知（`9b5b50b`）；一页只带它的条目所属的和没结束的轮次来自 v0.14.0（`2caad43`）。
:::

### thread/list

列出顶层会话，一页一页取。子 agent 会话不在里面。

| 参数 | 类型 | 说明 |
|---|---|---|
| `workspaceId?` | string \| null | 省略或 `null` 时不按工作区过滤；传空字符串只列不属于任何工作区的会话；传 ID 只列这个工作区的 |
| `archived?` | boolean | `false` 或省略只列未归档的，`true` 只列已归档的 |
| `after?` | `ThreadCursor` | 从这一项之后开始，传上一页最后一项的 `updatedAt`、`createdAt`、`id` |
| `limit?` | integer | 每页条数，默认 20，范围 1 到 100 |

排序是 `updatedAt`、`createdAt`、`id` 倒序。`updatedAt` 在会话日志每追加一次记录时更新，改名、改权限、标记已读、归档时也更新，所以列表按"最近有过动静"排，正在跑的会话会一直往前移；翻页期间顺序可能变化，客户端要按 `id` 去重。

结果：`{data: ThreadRow[], hasMore}`。

| 错误 | 什么时候 |
|---|---|
| `-32602` | `limit` 不在 1 到 100 |

::: info 演进
v0.12.1 的参数类型叫 `ThreadFilter`，结果里每一项是多带一个 `status` 的 `ThreadSummary`，`updatedAt` 只在一轮成为当前一轮和结束时更新。日志存储（`6a64e78`）让每次追加都更新它，`9b5b50b` 把参数改名为 `ThreadListParams`、结果改成 `ThreadRow`。
:::

### thread/rename

| 参数 | 类型 | 说明 |
|---|---|---|
| `threadId` | string | |
| `title` | string | 去掉首尾空白后 1 到 120 个字符 |

结果：`{thread}`，发 `thread/changed`。

| 错误 | 什么时候 |
|---|---|
| `-32602` | 标题为空或超过 120 字符 |
| `-32004` | 会话不存在 |
| `-32013` | 子 agent 会话 |

### thread/markRead

把会话标记为已读：`readAt` 设为现在。

| 参数 | 类型 | 说明 |
|---|---|---|
| `threadId` | string | |

结果：`{thread}`，发 `thread/changed`。用户的每条连接都收到这条通知，所以在一台设备上读过，别的设备上的未读标记也会消失。

| 错误 | 什么时候 |
|---|---|
| `-32004` | 会话不存在 |
| `-32013` | 子 agent 会话 |

### thread/updatePermissions

整体替换会话这一层的权限设置，不是合并。

| 参数 | 类型 | 说明 |
|---|---|---|
| `threadId` | string | |
| `approvalPolicy?` | `ApprovalPolicy` | 省略表示这一层不设策略，沿用下面几层 |
| `permissions` | `PermissionRules` | 这一层的全部规则。规则里的工具必须在这个用户的工具表里 |

结果：`{thread}`，发 `thread/changed`。进行中的一轮每一步都重读会话和权限，所以从下一次判定起用上新设置，已经判定过的调用不受影响。规则怎样写、各层怎样合并见[权限](/zh/integrate/protocol/permissions)。

| 错误 | 什么时候 |
|---|---|
| `-32602` | 设置不合法，或和部署、用户、工作区几层合并后不成立 |
| `-32004` | 会话不存在 |
| `-32013` | 子 agent 会话 |

### thread/archive

| 参数 | 类型 | 说明 |
|---|---|---|
| `threadId` | string | |
| `archived` | boolean | 必填：`true` 归档，`false` 取消归档 |

结果：`{thread}`，发 `thread/changed`。归档后 `archivedAt` 有值，取消归档后这个字段消失。

归档要求会话空闲（`status` 是 `idle`）：没有当前一轮，也没有排队的一轮。取消归档没有这个要求。归档的会话不能再开始新的一轮，`turn/start` 返回 `-32015`。

| 错误 | 什么时候 |
|---|---|
| `-32602` | 没给 `archived` |
| `-32004` | 会话不存在 |
| `-32013` | 子 agent 会话 |
| `-32016` | 归档时会话不空闲 |

### thread/delete

删除会话，连同它的日志、定时任务和子 agent 会话（外键 `ON DELETE CASCADE`）。没有回收站。

| 参数 | 类型 | 说明 |
|---|---|---|
| `threadId` | string | |

结果：`{}`。发 `thread/changed`，`thread` 为 `null`；并为删掉的每个定时任务发 `cron/changed`，`job` 为 `null`。子 agent 会话随父会话删掉，不单独发通知。

会话删掉之后，引擎再删这个会话的附件（`app.Attachments.DeletePrefix`，以会话 ID 加 `/` 为前缀）。删附件失败时会话已经删了，客户端却收到 `-32000`。

| 错误 | 什么时候 |
|---|---|
| `-32004` | 会话不存在 |
| `-32013` | 子 agent 会话 |
| `-32016` | 会话不空闲 |
| `-32000` | 会话已删除，附件没删掉（详情只在服务端） |

## 通知

### thread/changed

载荷：`{threadId, thread: ThreadRow | null, seq}`。

会话行所在的一次提交只要改动了这个会话，就发一条：日志追加了记录（发消息、模型回答、工具调用的每一步、一轮结束），会话行被修改（改名、改权限、标记已读、归档），子 agent 的等待让它的状态变了，或者新建。`thread` 是提交之后的整行，删除时为 `null`。同一次提交还改动了轮次或条目时，`turn/changed` 和 `item/changed` 紧跟在它后面，带同一个 `seq`。

所以这条通知很频繁：一轮对话里每一步都有一条，`updatedAt` 每次都变，`status` 多数时候不变。客户端要容忍"值和上一次相同"的通知。

子 agent 会话照样发 `thread/changed`，`thread.parentThreadId` 指向父会话。

::: info 演进
v0.12.1 有三种会话通知：`thread/started`（新建）、`thread/changed`（改名、改权限、归档、删除）和 `thread/status/changed`（状态）。v0.16.0 合成这一种，并带上提交序号 `seq`（`9b5b50b`）。
:::

## 子 agent 会话

模型调用子 agent 工具时，引擎为任务建一个子 agent 会话，排上它的第一轮，父会话里的那次调用立即完成；子 agent 自己跑，结束时把报告作为一条 `agentReport` 条目写回父会话的那一轮。父会话的那一轮回答完之后，会等到它启动的子 agent 都回报了才结束。机制见[执行模型](/zh/engine/execution)。客户端看到的是：

- **出现。** 和父会话里那次调用的完成在同一次提交里：一条子会话的 `thread/changed`，`parentThreadId` 指向父会话，`parentItemId` 指向那次调用的条目；子会话第一轮的 `turn/changed` 和任务消息的 `item/changed`；父会话里调用条目的 `item/changed`，`status` 为 `completed`，`childThreadId` 是子会话的 ID，`result.output` 是 `SubagentLaunched`。标题是调用参数里的 `description`。
- **继承。** 工作区和执行环境都和父会话相同，按父会话的权限运行；子会话的 `agent` 是 `general-sub-agent` 或 `browser-sub-agent`。
- **跟上。** 子会话的轮次和条目照常走 `turn/changed`、`item/changed`，`threadId` 是子会话的 ID。要展示嵌套的时间线，按 `parentItemId`（或调用条目的 `childThreadId`）把它挂到父会话的调用条目下面。
- **回报。** 子会话的一轮结束时，父会话那一轮多一条 `agentReport` 条目：`launchItemId` 指向启动它的调用，`childThreadId` 指向子会话，`text` 是任务，完成时 `result.output` 是子 agent 最后的回答，失败或被停下时 `status` 为 `failed`、`error` 是原因。
- **读取。** `thread/read`、`thread/resume`、`attachment/read` 都能用；`thread/list` 不列出它们。
- **拒绝。** `thread/rename`、`thread/markRead`、`thread/updatePermissions`、`thread/archive`、`thread/delete`、`turn/start`、`turn/steer` 返回 `-32013`（`subagentThread`）：子 agent 只执行父会话交给它的任务，用户通过父会话和它沟通。`turn/interrupt` 不拒绝，可以单独停下一个子 agent 的当前一轮。
- **结束。** 父会话的一轮结束时，它启动的、还没回报的子 agent 一并停下，子会话的那一轮以 `interrupted` 结束，`error` 是 `stopped with the turn that launched it`。父会话删除时子会话一起删除。

子 agent 的审批和提问也发给客户端，审批时选"总是允许"写进的是父会话所在的那一层，见[审批与提问](/zh/integrate/protocol/approvals)。

::: info 演进
v0.12.1 的子 agent 由 `Agent` 工具启动，那次调用一直停在 `inProgress`，条目的 `await.threadId` 指向子会话，子会话结束时调用才完成。v0.14.0 改成启动立即完成、报告作为条目回来（`975de2e`），子 agent 工具按角色命名（`d18618f`）；v0.16.0 的条目用 `childThreadId` 指向子会话（`9b5b50b`）。
:::

## 类型

`?` 表示字段可能不出现：Go 端用 `omitempty`，空字符串、`0`、`false`、空数组都不发，客户端把"缺"当成零值。时间都是 RFC 3339 的 UTC 字符串，带纳秒。

### ThreadRow

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | string | 会话 ID |
| `workspaceId?` | string | 所属工作区。不出现时，会话不属于任何工作区 |
| `environmentId?` | string | 会话运行的执行环境，建会话时选定，之后不变。每个会话都有，所以实际上总会出现 |
| `title` | string | 标题，可以是空字符串。子 agent 会话取任务的 `description` |
| `settings` | `PermissionSettings` | 会话这一层的权限设置，见[权限](/zh/integrate/protocol/permissions) |
| `parentThreadId?` | string | 子 agent 会话的父会话。顶层会话没有这个字段 |
| `parentItemId?` | string | 启动这个子 agent 的那条调用条目 |
| `status` | `ThreadStatus` | 会话状态，含子 agent 的等待，见[会话状态](#会话状态) |
| `createdAt` | string | 创建时间 |
| `updatedAt` | string | 最近一次有动静的时间：日志追加，或会话行被修改。`thread/list` 按它倒序 |
| `archivedAt?` | string \| null | 归档时间。不出现表示未归档 |
| `repliedAt?` | string \| null | 最近一轮结束的时间，只有顶层会话有 |
| `readAt?` | string \| null | 最近一次 `thread/markRead` 的时间 |

用户 ID 不在行里：会话总属于连接所认出的那个用户。

### ThreadStatus

`idle`、`active`、`waitingOnApproval`、`waitingOnUserInput`，含义见[会话状态](#会话状态)。

### ThreadCursor

| 字段 | 类型 | 说明 |
|---|---|---|
| `updatedAt` | string | 上一页最后一项的 `updatedAt` |
| `createdAt` | string | 上一页最后一项的 `createdAt` |
| `id` | string | 上一页最后一项的 `id` |

三个字段一起比较，所以 `updatedAt` 相同的会话也能稳定地翻过去。

### 参数和结果的包装

| 类型 | 字段 |
|---|---|
| `ThreadStartParams` | `workspaceId?`、`environmentId?`、`title?` |
| `ThreadPageParams` | `threadId`、`beforeSeq?`、`limit?` |
| `ThreadPageResult` | `thread`、`turns`、`items`、`seq`、`hasMore` |
| `ThreadListParams` | `workspaceId?`、`archived?`、`after?`、`limit?` |
| `ThreadListResult` | `data: ThreadRow[]`、`hasMore` |
| `ThreadRenameParams` | `threadId`、`title` |
| `ThreadMarkReadParams` | `threadId` |
| `ThreadPermissionsParams` | `threadId`、`approvalPolicy?`、`permissions`，见[权限](/zh/integrate/protocol/permissions) |
| `ThreadArchiveParams` | `threadId`、`archived` |
| `ThreadDeleteParams` | `threadId` |
| `ThreadResult` | `thread` |
| `ThreadChangedNotification` | `threadId`、`thread: ThreadRow \| null`、`seq` |

## 错误与边界

- **参数解码严格，必填不强制。** 多余字段返回 `-32602`；契约标为必填的字段缺了按零值处理。`thread/archive` 的 `archived` 是例外，网关显式检查。
- **列表只看顶层。** 子 agent 会话不在 `thread/list` 里，也没有别的方法能列出一个会话的全部子会话；客户端从父会话里调用条目的 `childThreadId`、`agentReport` 条目，或子会话 `thread/changed` 里的 `parentThreadId` 找到它们。
- **列表不是快照。** `thread/list` 一页一页读库，翻页期间会话的 `updatedAt` 会变，同一个会话可能出现在两页里，也可能被跳过。要完整的列表，翻完之后再用 `thread/changed` 修正。
- **删除不能撤销，也不经过回收站。** 会话、日志、定时任务、子 agent 会话一起删掉，附件随后删除。
- **排队的一轮会挡住归档和删除。** 协议里没有取消排队中一轮的方法，只能等它跑完，或者在它成为当前一轮后中断它。

## 代码位置

| 仓库 | 路径 | 职责 |
|---|---|---|
| ollupi | `gateway/threads.go` | `thread/*` 的处理函数、`thread/read` 的分页和 4 MiB 截断、`thread/resume` 的重发 |
| ollupi | `gateway/protocol.go` | 参数、结果和通知类型 |
| ollupi | `gateway/wire.go` | `ThreadRow` 和它从存储的转换 |
| ollupi | `gateway/server.go` | 变化到 `thread/changed` 的映射，`defaultItems`、`maxItems`、`defaultLimit`、`maxLimit` |
| ollupi | `app/threads.go` | `StartThread`、`Page`、`RenameThread`、`MarkThreadRead`、`ArchiveThread`、`DeleteThread` |
| ollupi | `conversation/view.go` | `View.Status`、`RollUp`：会话状态和子 agent 等待的汇总 |
| ollupi | `store/sqlite/conversations.go` | 追加时更新会话行和状态、`Page`、`Seq`、祖先会话的状态重算 |
| ollupi | `store/sqlite/owned.go` | `Threads` 的排序和过滤、`DeleteThread` |
| ollupi | `run/tools.go` | `launch`：建子 agent 会话，继承工作区和执行环境 |
| ollupi | `run/end.go` | 一轮结束时停下子 agent、子 agent 向父会话回报 |
