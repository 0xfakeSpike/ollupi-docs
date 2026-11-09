# 会话

会话（thread）是一段连续的对话，客户端用 `thread/*` 方法新建、列出、读取、改名、归档和删除它，用三种通知跟上它的变化。会话里的每一轮（turn）和条目（item）见[一轮与条目](/zh/integrate/protocol/turns)。

本页按引擎 v0.12.1 写。连接、认证、握手和错误码的通用规则见[网关协议](/zh/integrate/protocol)。

## 概念与状态

一个会话属于一个用户，可以属于一个工作区（`workspaceId`），也可以不属于任何工作区（界面上叫 general）。v0.12.0 起它还在某个执行环境（`environmentId`）里运行，环境在建会话时定下，之后不变，见[工作区与执行环境](/zh/integrate/protocol/workspaces)。

会话分两种：

| 种类 | 怎样产生 | `parentThreadId` | 在 `thread/list` 里 |
|---|---|---|---|
| 顶层会话 | 客户端调 `thread/start` | 没有 | 列出 |
| 子 agent 会话 | 模型调 `Agent` 工具，引擎自己建 | 父会话的 ID | 不列出 |

子 agent 会话能读，但不能改，见下文[子 agent 会话](#子-agent-会话)。

### 会话状态

`ThreadRow` 本身不带状态。状态是从会话的当前一轮推出来的，只在两处出现：`thread/list` 结果里每一项的 `status`，和 `thread/status/changed` 通知。

| `ThreadStatus` | 什么时候 |
|---|---|
| `idle` | 没有当前一轮（没有在进行中、准备中或等待中的一轮） |
| `active` | 当前一轮在排队等槽位、在运行，或在等子 agent 而子 agent 没有在等人 |
| `waitingOnApproval` | 当前一轮在等审批；或者它在等子 agent，而某个子 agent 在等审批 |
| `waitingOnUserInput` | 当前一轮在等用户回答；或者某个它在等的子 agent 在等回答 |

所以子 agent 的审批和提问会让父会话显示为在等人，客户端看父会话的状态就知道要不要提醒用户。轮次本身的九个状态见[一轮与条目](/zh/integrate/protocol/turns#一轮的状态)。

## 典型流程

### 新建、列出、读取

下面的消息来自桌面端仓库录制的会话 `ollupi-desktop/packages/protocol/fixtures/session.json`：它用假模型跑了一遍 sidecar，录制时的协议摘要和 v0.12.0、v0.12.1 的 `protocolSha256` 相同。ID 和时间是录制时的值。

新建一个属于工作区的会话：

```json
{"jsonrpc": "2.0", "id": 8, "method": "thread/start",
 "params": {"workspaceId": "ab146065-d40b-4f19-bdda-d2c4ea51a3ae", "permissions": {}}}
```

`thread/started` 先于回复到达，两者带的是同一行：

```json
{"jsonrpc": "2.0", "method": "thread/started", "params": {"thread": {
  "id": "9f311e1e-e8d6-47b8-a5f5-2e49f0d1be23",
  "workspaceId": "ab146065-d40b-4f19-bdda-d2c4ea51a3ae",
  "environmentId": "3792e905695b164d7e281e236fc20963",
  "title": "",
  "settings": {"permissions": {}},
  "createdAt": "2026-11-08T11:44:54.505636Z",
  "updatedAt": "2026-11-08T11:44:54.505636Z"}}}
{"jsonrpc": "2.0", "id": 8, "result": {"thread": { "...": "同上" }}}
```

列出会话，每一项比 `ThreadRow` 多一个 `status`：

```json
{"jsonrpc": "2.0", "id": 40, "method": "thread/list", "params": {"limit": 100}}
{"jsonrpc": "2.0", "id": 40, "result": {"data": [{
  "id": "9f311e1e-e8d6-47b8-a5f5-2e49f0d1be23",
  "workspaceId": "ab146065-d40b-4f19-bdda-d2c4ea51a3ae",
  "environmentId": "3792e905695b164d7e281e236fc20963",
  "title": "",
  "settings": {"approvalPolicy": "never", "permissions": {"deny": ["run_command(rm:*)"]}},
  "createdAt": "2026-11-08T11:44:54.505636Z",
  "updatedAt": "2026-11-08T11:45:07.487543Z",
  "status": "idle"}], "hasMore": false}}
```

打开一个会话时用 `thread/resume` 读最新一页，往上翻用 `thread/read` 带 `beforeSeq`。重连之后要重新读，因为断线期间的通知不补发，见[写一个客户端](/zh/integrate/client#重连)。

### 修改

改权限的请求和它引发的 `thread/changed`：

```json
{"jsonrpc": "2.0", "id": 28, "method": "thread/updatePermissions", "params": {
  "threadId": "9f311e1e-e8d6-47b8-a5f5-2e49f0d1be23",
  "approvalPolicy": "never",
  "permissions": {"deny": ["run_command(rm:*)"]}}}
{"jsonrpc": "2.0", "method": "thread/changed", "params": {
  "threadId": "9f311e1e-e8d6-47b8-a5f5-2e49f0d1be23",
  "thread": { "...": "改过之后的整行，settings 是新值" }}}
```

改名、权限、归档都发 `thread/changed`，带改过之后的整行；删除也发 `thread/changed`，`thread` 为 `null`。

## 方法

所有方法都只能操作调用者自己的会话。别的用户的会话表现为不存在，返回 `-32004`。

### thread/start

新建一个顶层会话。

| 参数 | 类型 | 说明 |
|---|---|---|
| `workspaceId?` | string | 所属工作区。省略时不属于任何工作区 |
| `environmentId?` | string | v0.12.0 起。会话运行的执行环境，必须是这个用户的。省略时用他在这台机器上的环境 |
| `title?` | string | 标题。去掉首尾空白后最多 120 个字符，可以为空 |
| `approvalPolicy?` | `ApprovalPolicy` | 会话这一层的审批策略 |
| `permissions` | `PermissionRules` | 会话这一层的规则。契约标为必填，网关不检查，省略时按空规则处理 |

`approvalPolicy` 和 `permissions` 组成会话这一层的权限设置，合并规则见[权限](/zh/integrate/protocol/permissions)。

结果：`{thread: ThreadRow}`。回复之前已经发出 `thread/started`。

| 错误 | 什么时候 |
|---|---|
| `-32602` | 标题超过 120 字符；权限设置不合法（未知的策略、写错的规则，或和上层合并后不成立） |
| `-32004` | 工作区或执行环境不存在，或属于别的用户 |
| `-32014` | 工作区已归档 |

### thread/read 和 thread/resume

读会话的一页。两个方法的参数和结果一样，区别只在回复之后：`thread/resume` 会把这个会话和它正在等的子 agent 的待回答请求再发一遍，这条连接上已经发过、还没回答的不重复发。客户端打开会话或重连后用 `thread/resume`，往上翻页用 `thread/read`。请求怎样重发见[审批与提问](/zh/integrate/protocol/approvals)。

| 参数 | 类型 | 说明 |
|---|---|---|
| `threadId` | string | 会话 ID，子 agent 会话也可以读 |
| `beforeSeq?` | integer | 只取 `seq` 比它小的条目。省略或 `0` 表示从最新一条往前取 |
| `limit?` | integer | 条目数，默认 100，范围 1 到 500 |

结果是 `ThreadPageResult`：

| 字段 | 类型 | 说明 |
|---|---|---|
| `thread` | `ThreadRow` | 会话 |
| `turns` | `TurnRow[]` | 这个会话的全部轮次，不分页 |
| `items` | `ItemRow[]` | 这一页的条目，按 `seq` 升序 |
| `hasMore` | boolean | 还有更早的条目 |

分页规则：

- 条目从新到旧取 `limit` 条，再按 `seq` 升序返回。下一页把这一页最小的 `seq` 作为 `beforeSeq`。
- 页内条目序列化后累计超过 4 MiB（`pageBytes`）时，从旧的一端截掉，至少保留最新一条，`hasMore` 置为 `true`。
- 网关从读库到回复入队之间持有这条连接的 `deliver` 锁，所以这一页之后发生的变化，通知一定排在回复之后，客户端可以先应用这一页，再应用之后的通知。连接层的顺序保证见[连接模型](/zh/integrate/protocol#连接模型)。

| 错误 | 什么时候 |
|---|---|
| `-32602` | `limit` 不在 1 到 500，或 `beforeSeq` 是负数 |
| `-32004` | 会话不存在或不是自己的 |

### thread/list

列出顶层会话，一页一页取。子 agent 会话不在里面。

参数是 `ThreadFilter`：

| 参数 | 类型 | 说明 |
|---|---|---|
| `workspaceId?` | string | 省略时不按工作区过滤；传空字符串只列不属于任何工作区的会话；传 ID 只列这个工作区的 |
| `archived?` | boolean | `false` 或省略只列未归档的，`true` 只列已归档的 |
| `after?` | `ThreadCursor` | 从这一项之后开始，传上一页最后一项的 `updatedAt`、`createdAt`、`id` |
| `limit?` | integer | 每页条数，默认 20，范围 1 到 100 |

排序是 `updatedAt`、`createdAt`、`id` 倒序。`updatedAt` 只在一轮成为会话的当前一轮、和一轮结束时更新（`touchThread`）；改名、改权限、归档都不动它，进入排队也不动。所以列表是按"最近有过对话"排的，活跃的会话会往前移；翻页期间顺序可能变化，客户端要按 `id` 去重。

结果：`{data: ThreadSummary[], hasMore}`。`status` 是列出那一刻算出来的，之后的变化走 `thread/status/changed`。

| 错误 | 什么时候 |
|---|---|
| `-32602` | `limit` 不在 1 到 100 |

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

### thread/updatePermissions

整体替换会话这一层的权限设置，不是合并。

| 参数 | 类型 | 说明 |
|---|---|---|
| `threadId` | string | |
| `approvalPolicy?` | `ApprovalPolicy` | 省略表示这一层不设策略，沿用上层 |
| `permissions` | `PermissionRules` | 这一层的全部规则 |

结果：`{thread}`，发 `thread/changed`。进行中的一轮每圈循环都重读一次会话和权限（运行时的 `Reload`），所以从下一圈的工具调用起用上新设置，已经判定过的调用不受影响。规则怎样写、三层怎样合并见[权限](/zh/integrate/protocol/permissions)。

| 错误 | 什么时候 |
|---|---|
| `-32602` | 设置不合法，或和工作区、agent 默认层合并后不成立 |
| `-32004` | 会话不存在 |
| `-32013` | 子 agent 会话 |

### thread/archive

| 参数 | 类型 | 说明 |
|---|---|---|
| `threadId` | string | |
| `archived` | boolean | 必填：`true` 归档，`false` 取消归档 |

结果：`{thread}`。归档后 `archivedAt` 有值，取消归档后这个字段消失。

归档要求会话空闲：没有当前一轮，也没有排队的一轮。取消归档没有这个要求。归档的会话不能再开始新的一轮，`turn/start` 返回 `-32015`。

发 `thread/changed`，并为这个会话的每个定时任务发一次 `cron/changed`，因为任务的视图随会话的归档状态变化，见[定时任务](/zh/integrate/protocol/cron)。

| 错误 | 什么时候 |
|---|---|
| `-32602` | 没给 `archived` |
| `-32004` | 会话不存在 |
| `-32013` | 子 agent 会话 |
| `-32016` | 归档时会话有进行中或排队的一轮 |

### thread/delete

删除会话，连同它的轮次、条目、定时任务和子 agent 会话（外键 `ON DELETE CASCADE`，见[持久化](/zh/engine/persistence#表和关系)）。没有回收站。

| 参数 | 类型 | 说明 |
|---|---|---|
| `threadId` | string | |

结果：`{}`。发 `thread/changed`，`thread` 为 `null`；并为删掉的每个定时任务发 `cron/changed`，`job` 为 `null`。子 agent 会话随父会话删掉，不单独发通知。

配置了附件存储时，引擎在回复前删掉这个会话的附件（`blobs.Store.DeletePrefix`，按会话 ID 作前缀）；删除附件失败只写一条警告日志，会话照样删除。

| 错误 | 什么时候 |
|---|---|
| `-32004` | 会话不存在 |
| `-32013` | 子 agent 会话 |
| `-32016` | 会话有进行中或排队的一轮 |

## 通知

三种通知都只发给会话所属用户当前已初始化的连接。

### thread/started

载荷：`{thread: ThreadRow}`。会话建出来时发，包括引擎为 `Agent` 工具建的子 agent 会话：

```json
{"jsonrpc": "2.0", "method": "thread/started", "params": {"thread": {
  "id": "4debd310-b1d6-4181-bc26-d5d0bb15295e",
  "workspaceId": "ab146065-d40b-4f19-bdda-d2c4ea51a3ae",
  "environmentId": "3792e905695b164d7e281e236fc20963",
  "title": "Check the weather",
  "settings": {"permissions": {}},
  "parentThreadId": "9f311e1e-e8d6-47b8-a5f5-2e49f0d1be23",
  "parentItemId": "acbe7691-a9a3-4ee9-a196-80778225016c",
  "createdAt": "2026-11-08T11:45:00.379553Z",
  "updatedAt": "2026-11-08T11:45:00.379553Z"}}}
```

`thread/start` 的 `thread/started` 先于它的回复到达。

### thread/changed

载荷：`{threadId, thread: ThreadRow | null}`。改名、改权限（包括审批时选"总是允许"而会话不属于工作区时）、归档和取消归档时，`thread` 是改过之后的整行；删除时 `thread` 为 `null`。

### thread/status/changed

载荷：`{threadId, status: ThreadStatus}`。只针对顶层会话：子 agent 会话的状态变化会让引擎重算它的父会话，发的是父会话的 `threadId` 和状态。

客户端要容忍重复：录制的会话里，父会话已经是 `active`，子 agent 开始运行时又收到一次 `active`。这条通知表示"重算过一次"，不保证值和上一次不同。它和触发它的轮次通知的先后见[一轮与条目](/zh/integrate/protocol/turns#一次完整对话)。

## 子 agent 会话

模型调用 `Agent` 工具时，引擎为每个任务建一个子 agent 会话，跑一个普通的轮次，父会话的调用条目等它回报。机制见[执行模型](/zh/engine/execution#子-agent)。客户端看到的是：

- **出现。** 一条 `thread/started`，`parentThreadId` 指向父会话，`parentItemId` 指向那条 `Agent` 调用条目；那条调用条目的 `await.threadId` 也写着子会话的 ID。标题是任务描述，最多 120 字符。
- **继承。** 工作区和执行环境都和父会话相同。
- **跟上。** 子会话的轮次和条目照常走 `turn/*`、`item/*` 通知，`threadId` 是子会话的 ID。要展示嵌套的时间线，按 `parentItemId` 把它挂到父会话的调用条目下面。
- **读取。** `thread/read`、`thread/resume`、`attachment/read` 都能用；`thread/list` 不列出它们。
- **拒绝。** `thread/rename`、`thread/updatePermissions`、`thread/archive`、`thread/delete`、`turn/start`、`turn/steer` 返回 `-32013`（`subagentThread`）：子 agent 只执行父会话交给它的任务，用户通过父会话和它沟通。`turn/interrupt` 不拒绝，可以单独停下一个子 agent 的当前一轮。
- **结束。** 父会话的一轮结束时，它还没结束的子 agent 一并停下，子会话的那一轮以 `interrupted` 结束，`error` 是 `stopped with the turn that launched it`。父会话删除时子会话一起删除。

子 agent 的审批和提问也发给客户端，审批时选"总是允许"写进的是父会话所在的那一层，见[审批与提问](/zh/integrate/protocol/approvals)。

## 类型

`?` 表示字段可能不出现：Go 端用 `omitempty`，空字符串、`0`、`false`、空数组都不发，客户端把"缺"当成零值。时间都是 RFC 3339 的 UTC 字符串，带纳秒。

### ThreadRow

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | string | 会话 ID |
| `workspaceId?` | string | 所属工作区。不出现时，会话不属于任何工作区 |
| `environmentId?` | string | v0.12.0 起：会话运行的执行环境，建会话时选定，之后不变。migration 0007 给旧会话都补上了这台机器上的环境，新会话也总会写上，所以实际上总会出现 |
| `title` | string | 标题，可以是空字符串。子 agent 会话取任务描述 |
| `settings` | `PermissionSettings` | 会话这一层的权限设置，见[权限](/zh/integrate/protocol/permissions) |
| `parentThreadId?` | string | 子 agent 会话的父会话。顶层会话没有这个字段 |
| `parentItemId?` | string | 派生这个子 agent 的那条 `Agent` 工具调用条目 |
| `createdAt` | string | 创建时间 |
| `updatedAt` | string | 最近一次有一轮开始或结束的时间，`thread/list` 按它倒序。改名、改权限、归档不更新它 |
| `archivedAt?` | string \| null | 归档时间。不出现表示未归档 |

用户 ID 不在行里：会话总属于连接所认出的那个用户。

### ThreadSummary

`ThreadRow` 的全部字段，加：

| 字段 | 类型 | 说明 |
|---|---|---|
| `status` | `ThreadStatus` | 列出那一刻算出的会话状态，见[会话状态](#会话状态) |

只出现在 `thread/list` 的结果里。

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
| `ThreadStartParams` | `workspaceId?`、`environmentId?`、`title?`、`approvalPolicy?`、`permissions` |
| `ThreadPageParams` | `threadId`、`beforeSeq?`、`limit?` |
| `ThreadPageResult` | `thread`、`turns`、`items`、`hasMore` |
| `ThreadFilter` | `workspaceId?`、`archived?`、`after?`、`limit?` |
| `ThreadListResult` | `data: ThreadSummary[]`、`hasMore` |
| `ThreadRenameParams` | `threadId`、`title` |
| `ThreadPermissionsParams` | `threadId`、`approvalPolicy?`、`permissions` |
| `ThreadArchiveParams` | `threadId`、`archived` |
| `ThreadDeleteParams` | `threadId` |
| `ThreadResult` | `thread` |
| `ThreadChangedNotification` | `threadId`、`thread: ThreadRow \| null` |
| `ThreadStatusNotification` | `threadId`、`status` |

## 错误与边界

- **参数解码严格，必填不强制。** 多余字段返回 `-32602`；契约标为必填的字段缺了按零值处理，例如 `thread/start` 省略 `permissions`。`thread/archive` 的 `archived` 是例外，网关显式检查。
- **列表只看顶层。** 子 agent 会话不在 `thread/list` 里，也没有别的方法能列出一个会话的全部子会话；客户端从父会话的 `Agent` 调用条目（`await.threadId`）或 `thread/started` 的 `parentThreadId` 找到它们。
- **列表不是快照。** `thread/list` 一页一页读库，翻页期间会话的 `updatedAt` 会变，同一个会话可能出现在两页里，也可能被跳过。要完整的列表，翻完之后再用 `thread/changed` 和 `turn/*` 通知修正。
- **删除不能撤销，也不经过回收站。** 会话、轮次、条目、定时任务、子 agent 会话一起删掉，附件尽力删除。
- **排队的一轮会挡住归档和删除。** 协议里没有取消排队中一轮的方法，只能等它跑完，或者在它成为当前一轮后中断它。

## 代码位置

| 仓库 | 路径 | 职责 |
|---|---|---|
| ollupi | `gateway/threads.go` | `thread/*` 的处理函数、`thread/read` 的分页和 4 MiB 截断、`thread/resume` 的重发 |
| ollupi | `gateway/protocol.go` | `ThreadStartParams` 等参数和结果类型、通知类型 |
| ollupi | `gateway/server.go` | 事件到 `thread/*` 通知的映射，`defaultItems`、`maxItems`、`defaultLimit`、`maxLimit`、`pageBytes` |
| ollupi | `agent/threads.go` | `StartThread`、`RenameThread`、`ArchiveThread`、`DeleteThread`、`ListThreads`、`threadStatus`、`topThread`、`idle` |
| ollupi | `agent/events.go` | `emitStatus`：子 agent 的状态变化算到父会话上 |
| ollupi | `agent/subagents.go` | 建子 agent 会话，继承工作区和执行环境 |
| ollupi | `repo/threads.go` | `ThreadRow`、`ThreadSummary`、`ThreadFilter`、`ThreadCursor`、`ThreadRows` 的排序和过滤 |
