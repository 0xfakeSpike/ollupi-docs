# 会话

会话（thread）是一段连续的对话。客户端用 `thread/*` 新建、列出、读取、改名、标记已读、归档和删除它，用 `thread/changed` 跟上它的变化。轮次和条目见[一轮与条目](/zh/integrate/protocol/turns)；连接、认证、握手和错误码见[网关协议](/zh/integrate/protocol)；怎样用 `seq` 把读到的一页和之后的通知对齐见[写一个客户端](/zh/integrate/client#本地状态)。

## 概念与状态

一个会话属于一个用户，可以属于一个工作区（`workspaceId`），也可以不属于任何工作区（界面上叫 general）。它在某个执行环境（`environmentId`）里运行，环境建会话时定下，之后不变，见[工作区与执行环境](/zh/integrate/protocol/workspaces)。

会话的内容是只追加的日志，轮次和条目是从日志算出的投影，机制见[持久化](/zh/engine/persistence)；客户端看不到日志本身，只看到投影出的行。

| 种类 | 怎样产生 | `parentThreadId` | 在 `thread/list` 里 |
|---|---|---|---|
| 顶层会话 | 客户端调 `thread/start` | 没有 | 列出 |
| 子 agent 会话 | 模型调子 agent 工具（`general-sub-agent`、`browser-sub-agent` 等），引擎自己建 | 父会话的 ID | 不列出 |

两种会话用同一套方法，子 agent 会话也能改名、标记已读、改权限、归档、删除；`thread/list` 只列顶层会话，因为列表要回答"用户有哪些对话"，子会话属于父会话里的某次调用。

### 会话状态

会话状态是 `ThreadRow.status`，`thread/changed`、`thread/list`、`thread/read` 都带着它，从会话日志里的当前一轮算出来（`conversation.View.Status`）：

| `ThreadStatus` | 什么时候 |
|---|---|
| `idle` | 没有当前一轮：没有还没结束的轮次 |
| `active` | 当前一轮在排队等槽位、在运行，或回答完了在等它启动的子 agent 回报 |
| `waitingOnApproval` | 当前一轮有调用在等审批；或者某个子 agent 会话在等审批 |
| `waitingOnUserInput` | 当前一轮有调用在等用户回答；或者某个子 agent 会话在等回答 |

子 agent 会话在等用户时，父会话也显示为在等：子会话的记录写入时，存储在同一个事务里重算祖先会话的状态，审批排在提问前面（`conversation.RollUp`），父会话状态变了也会收到 `thread/changed`。等子 agent 本身不是一种状态，这时是 `active`。

`repliedAt` 是顶层会话最近一次结束一轮的时间，`readAt` 是最近一次 `thread/markRead` 的时间；`repliedAt` 比 `readAt` 晚（或有 `repliedAt` 而没有 `readAt`）时会话有用户没看过的回答，子 agent 会话的轮次结束不写 `repliedAt`。引擎只记这两个时间，"未读"由客户端比较得出。

## 方法

所有方法都只能操作自己的会话；别人的会话表现为不存在，返回 `-32004`。

### thread/start

新建一个顶层会话。

| 参数 | 类型 | 说明 |
|---|---|---|
| `workspaceId?` | string | 所属工作区。省略时不属于任何工作区 |
| `environmentId?` | string | 执行环境，必须是这个用户的。省略时取他的本机环境（`local` 类型的那个） |
| `title?` | string | 去掉首尾空白后最多 120 字符（`account.maxNameRunes`），可以为空 |

新会话这一层的权限设置是空的，按部署、用户、工作区三层运行，之后用 `thread/updatePermissions` 改，见[权限](/zh/integrate/protocol/permissions)。结果 `{thread: ThreadRow}`，回复之前已发出 `thread/changed`。

| 错误 | 什么时候 |
|---|---|
| `-32602` | 标题超过 120 字符；参数里有多余字段 |
| `-32004` | 工作区或执行环境不存在，或属于别的用户 |
| `-32014` | 工作区已归档 |

### thread/read 和 thread/resume

读会话的一页。两个方法的参数和结果一样，区别只在回复之后：`thread/resume` 还会把这个会话和它的子 agent 会话里在等回答的请求再发一遍，这条连接上已经发过、还没回答的不重复发，所以打开会话或重连用 `thread/resume`，往上翻页用 `thread/read`。重发规则见[审批与提问](/zh/integrate/protocol/approvals#重发)。

| 参数 | 类型 | 说明 |
|---|---|---|
| `threadId` | string | 会话 ID，子 agent 会话也可以读 |
| `beforeSeq?` | integer | 只取条目 `seq` 比它小的条目。省略或 `0` 表示从最新一条往前取 |
| `limit?` | integer | 条目数，默认 100（`defaultItems`），范围 1 到 500（`maxItems`） |

结果 `ThreadPageResult`：`thread` 是 `ThreadRow`；`turns` 是这一页条目所属的轮次加上所有未结束的轮次，按提交顺序；`items` 按 `seq` 升序；`seq` 是读这一页时已提交到的序号；`hasMore` 表示还有更早的条目。

分页规则：

- 条目从新到旧取 `limit` 条，再按 `seq` 升序返回，下一页把这一页最小的 `seq` 作为 `beforeSeq`。条目的 `seq` 是它在日志里第一次出现的位置，会跳号（日志里还有不成为条目的记录），只能用来排序和翻页；页内序列化后累计超过 4 MiB（`pageBytes`）时从旧的一端截掉，至少保留最新一条，`hasMore` 置为 `true`。
- 整页和 `seq` 在同一个读事务里读出，这一页恰好包含序号不大于 `seq` 的全部提交；通知插在读和回复之间不影响对齐，见[用 seq 对齐](/zh/integrate/client#用-seq-对齐)。

| 错误 | 什么时候 |
|---|---|
| `-32602` | `limit` 不在 1 到 500，`beforeSeq` 是负数 |
| `-32004` | 会话不存在或不是自己的 |

### thread/list

列出顶层会话，一页一页取。子 agent 会话不在里面（查询条件是 `parent_id IS NULL`）。

| 参数 | 类型 | 说明 |
|---|---|---|
| `workspaceId?` | string \| null | 省略或 `null` 不过滤；空字符串只列不属于任何工作区的；ID 只列这个工作区的 |
| `archived?` | boolean | `false` 或省略只列未归档的，`true` 只列已归档的 |
| `after?` | `ThreadCursor` | 从这一项之后开始，传上一页最后一项的 `updatedAt`、`createdAt`、`id`；三个一起比较，`updatedAt` 相同的会话也能稳定翻过去 |
| `limit?` | integer | 每页条数，默认 20（`defaultLimit`），范围 1 到 100（`maxLimit`） |

排序是 `updatedAt`、`createdAt`、`id` 倒序。`updatedAt` 在日志追加、改名、改权限、标记已读、归档时都更新，所以列表按"最近有过动静"排，正在跑的会话一直往前移；翻页期间顺序会变，同一个会话可能出现在两页里或被跳过，客户端按 `id` 去重，翻完再用 `thread/changed` 修正。结果 `{data: ThreadRow[], hasMore}`，`limit` 越界时错误信息是 `limit must be 1 to %d`。

### thread/rename

参数：`threadId`，`title`（去掉首尾空白后 1 到 120 个字符）。结果 `{thread}`，发 `thread/changed`。

| 错误 | 什么时候 |
|---|---|
| `-32602` | 标题为空或超过 120 字符（`account.ErrInvalidName`） |
| `-32004` | 会话不存在 |

### thread/markRead

参数：`threadId`。把 `readAt` 设为现在，结果 `{thread}`，发 `thread/changed`。用户的每条连接都收到这条通知，所以一台设备上读过，别的设备上的未读标记也消失。

| 错误 | 什么时候 |
|---|---|
| `-32004` | 会话不存在 |

### thread/updatePermissions

整体替换会话这一层的权限设置，不是合并。参数：`threadId`、`approvalPolicy?`（`ApprovalPolicy`，省略表示这一层不设策略）、`permissions`（`PermissionRules`，这一层的全部规则，里面的工具必须在这个用户的工具表里）。结果 `{thread}`，发 `thread/changed`。

进行中的一轮每一步都重读会话和权限，从下一次判定起用上新设置，已判定过的调用不受影响；规则怎样写、各层怎样合并见[权限](/zh/integrate/protocol/permissions)。

| 错误 | 什么时候 |
|---|---|
| `-32602` | 设置不合法，或和部署、用户、工作区几层合并后不成立 |
| `-32004` | 会话不存在 |

### thread/archive

参数：`threadId`、`archived`（boolean，必填：`true` 归档，`false` 取消归档）。结果 `{thread}`，发 `thread/changed`；归档后 `archivedAt` 有值，取消归档后该字段消失。

归档要求会话空闲（`status` 是 `idle`）：没有当前一轮，也没有排队的一轮；取消归档没有这个要求。归档的会话不能开始新的一轮，`turn/start` 返回 `-32015`。

| 错误 | 什么时候 |
|---|---|
| `-32602` | 没给 `archived` |
| `-32004` | 会话不存在 |
| `-32016` | 归档时会话不空闲 |

### thread/delete

参数：`threadId`。删除会话，连同它的日志、子 agent 会话（外键 `ON DELETE CASCADE`）和它们的定时任务，无回收站。

结果 `{}`，发 `thread/changed`（`thread` 为 `null`）；为删掉的每个定时任务（含子会话的）发 `cron/changed`（`job` 为 `null`）；链到这些会话的待办被解绑——`threadId`、`workspaceId` 清空，`handed` 退回 `open`——每条发一条 `todo/changed`，见[待办](/zh/integrate/protocol/todos)。子 agent 会话随父会话删掉，不单独发 `thread/changed`。

会话删掉之后引擎再删它和子会话的附件（`app.Attachments.DeletePrefix`，前缀是会话 ID 加 `/`）；删附件失败时会话已删，客户端却收到 `-32000`。

| 错误 | 什么时候 |
|---|---|
| `-32004` | 会话不存在 |
| `-32016` | 会话不空闲 |
| `-32000` | 会话已删除，附件没删掉（详情只在服务端） |

## 通知

### thread/changed

载荷：`{threadId, thread: ThreadRow | null, seq}`。

会话行所在的一次提交只要改动了这个会话就发一条：日志追加（发消息、模型回答、工具调用的每一步、一轮结束），会话行被修改（改名、改权限、标记已读、归档），子 agent 的等待让它的状态变了，或者新建。`thread` 是提交之后的整行，删除时为 `null`；同一次提交还改动了轮次或条目时，`turn/changed`、`item/changed` 紧跟其后，带同一个 `seq`。

这条通知很频繁：一轮对话每一步都有一条，`updatedAt` 每次变，`status` 多数不变，客户端要容忍"值和上一次相同"的通知。子 agent 会话照样发，`thread.parentThreadId` 指向父会话。

::: info 演进
这条通知原来分新建、变化、状态三种；合并成一种并带上 `seq` 后，客户端只按 `seq` 一处分拣。
:::

## 类型

`?` 表示字段可能不出现：Go 端用 `omitempty`，空字符串、`0`、`false`、空数组都不发，客户端把"缺"当成零值。时间都是 RFC 3339 的 UTC 字符串，带纳秒。

### ThreadRow

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | string | 会话 ID |
| `workspaceId?` | string | 所属工作区。不出现时会话不属于任何工作区 |
| `environmentId?` | string | 执行环境，建会话时选定，之后不变。每个会话都有，所以总出现 |
| `title` | string | 标题，可以是空字符串。子 agent 会话取任务的短标题 |
| `settings` | `PermissionSettings` | 会话这一层的权限设置，见[权限](/zh/integrate/protocol/permissions) |
| `parentThreadId?` | string | 子 agent 会话的父会话。顶层会话没有 |
| `parentItemId?` | string | 启动这个子 agent 的调用条目 |
| `role?` | `AgentRole` | 会话的 agent 角色（`agent.Name`）：子 agent 会话带着启动它的角色名，例如 `general-sub-agent`；顶层会话没有这个字段，轮次角色在 `turn/start` 时按模型能力决定（`agent.MainRole`），hub 工作区的轮次用 `hub-main-agent`，见[中枢](/zh/engine/hub)，完整清单见[术语表](/zh/reference/glossary) |
| `status` | `ThreadStatus` | 会话状态，含子 agent 的等待，见[会话状态](#会话状态) |
| `createdAt` | string | 创建时间 |
| `updatedAt` | string | 最近一次有动静的时间：日志追加或会话行被修改。`thread/list` 按它倒序 |
| `archivedAt?` | string \| null | 归档时间。不出现表示未归档 |
| `repliedAt?` | string \| null | 最近一轮结束的时间，只有顶层会话有 |
| `readAt?` | string \| null | 最近一次 `thread/markRead` 的时间 |

`ThreadStatus` 是 `idle`、`active`、`waitingOnApproval`、`waitingOnUserInput`，含义见[会话状态](#会话状态)。用户 ID 不在行里：会话总属于连接所认出的那个用户。

## 错误与边界

- **参数解码严格，必填不强制。** 多余字段返回 `-32602`，标为必填的字段缺了按零值处理；`thread/archive` 的 `archived` 是例外，网关显式检查。
- **列表只看顶层。** 没有方法能列出一个会话的全部子会话，客户端从父会话的 `childThreadId`、`agentReport` 条目，或子会话 `thread/changed` 的 `parentThreadId` 找到它们，见[后台调用与报告](/zh/integrate/protocol/turns#后台调用与报告)。
- **排队的一轮挡住归档和删除。** 协议里没有取消排队一轮的方法，只能等它跑完，或在它成为当前一轮后中断它，见[排队](/zh/integrate/protocol/turns#排队)。

## 代码位置

| 仓库 | 路径 | 职责 |
|---|---|---|
| ollupi | `gateway/threads.go` | `thread/*` 处理函数、`thread/read` 分页与 4 MiB 截断、`thread/resume` 重发 |
| ollupi | `gateway/protocol.go`、`gateway/wire.go` | 参数、结果、通知类型，`ThreadRow` 和它从存储的转换 |
| ollupi | `gateway/server.go` | 变化到 `thread/changed` 的映射，`defaultItems`、`maxItems`、`defaultLimit`、`maxLimit` |
| ollupi | `app/threads.go` | `StartThread`、`Page`、`RenameThread`、`MarkThreadRead`、`ArchiveThread`、`DeleteThread` |
| ollupi | `conversation/view.go` | `View.Status`、`RollUp`：会话状态和子 agent 等待的汇总 |
| ollupi | `store/sqlite/conversations.go`、`store/sqlite/owned.go` | 追加时更新会话行与状态、`Page`、`Seq`、祖先状态重算；`Threads` 排序与过滤、`DeleteThread` 连带处理 |
| ollupi | `run/tools.go`、`app/turns.go` | `launch` 建子 agent 会话并带上角色；`role` 的取法 |
