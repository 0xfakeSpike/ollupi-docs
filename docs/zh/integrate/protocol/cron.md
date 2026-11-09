# 定时任务

定时任务按调度表达式定时向一个会话发一条消息，到点时就是这个会话里普通的一轮。客户端用 `cron/*` 列出、新建、暂停和删除任务，用 `cron/changed` 跟上变化。调度表达式的语法和触发链路见[定时任务的实现](/zh/engine/cron)，这里只讲协议上看到的东西。

## 概念与状态

- **任务属于会话。** 一个任务挂在一个会话上，在这个会话里按 `(threadId, name)` 唯一，修改和删除都按这两个值找任务，不用 `id`。一个会话最多 64 个任务。
- **到点就是一轮。** 引擎每分钟检查一次到期的任务，到期就以任务的 `prompt` 在所属会话里开始一轮，这一轮的 `TurnRow.cronJobId` 是任务的 `id`。会话正在跑别的轮次时，这一轮照常排队（`turn/queued`）。轮次本身怎样跟踪见[一轮与条目](/zh/integrate/protocol/turns)。
- **时区归宿主。** 调度表达式按宿主传给 `cron.New` 的时区解释（桌面端是本机时区），不允许在表达式里写时区前缀；`nextRunAt` 总是 UTC。录制的会话里 `0 9 * * *` 在东八区算出的 `nextRunAt` 是 `01:00:00Z`。
- **次数。** `times` 是总共发几次，不写表示不限；`runs` 是已经发了几次。最后一次发出后任务被删除，客户端收到 `job` 为 `null` 的 `cron/changed`。
- **谁会改任务。** 客户端的 `cron/*` 方法、模型的定时任务工具（子 agent 不能用）、每次到点、会话归档和删除。每一种都发 `cron/changed`。

一个任务到点时的处理：

| 情况 | 结果 | 计入 `runs` |
|---|---|---|
| 正常 | 在会话里开始一轮，`nextRunAt` 前移 | 是 |
| 这个任务上一次发出的那一轮还在排队 | 这次跳过，`nextRunAt` 前移 | 否 |
| 开始一轮失败，比如会话是子 agent 会话 | 这次作废，`nextRunAt` 前移 | 是 |
| 已暂停，或所属会话（或子 agent 会话的父会话）已归档 | 不处理，`nextRunAt` 不动 | 否 |

由代码推断：归档的会话取消归档后，过期的 `nextRunAt` 会在下一次检查时立刻发一次。

## 典型流程

下面的消息来自桌面端仓库录制的真实会话 `packages/protocol/fixtures/session.json`（录制时的协议摘要等于 v0.12.1 的 `protocolSha256`），ID 是录制时的临时值。

新建一个每小时一次、总共三次的任务。`cron/changed` 先于回复到达：

```json
{"jsonrpc":"2.0","id":25,"method":"cron/create","params":{"threadId":"9f311e1e-…","name":"hourly-check","spec":"@hourly","prompt":"Anything new?","times":3}}
```

```json
{"jsonrpc":"2.0","method":"cron/changed","params":{"id":"fe78e575-…","threadId":"9f311e1e-…","job":{"id":"fe78e575-…","threadId":"9f311e1e-…","name":"hourly-check","spec":"@hourly","prompt":"Anything new?","times":3,"runs":0,"paused":false,"nextRunAt":"2026-11-08T12:00:00Z","createdAt":"2026-11-08T11:45:07.489514Z","threadTitle":"","workspaceId":"ab146065-…"}}}
```

```json
{"jsonrpc":"2.0","id":25,"result":{"id":"fe78e575-…","threadId":"9f311e1e-…","name":"hourly-check","spec":"@hourly","prompt":"Anything new?","times":3,"runs":0,"paused":false,"nextRunAt":"2026-11-08T12:00:00Z","createdAt":"2026-11-08T11:45:07.489514Z"}}
```

回复是 `CronJobRow`，比通知里的 `CronJobView` 少了会话相关的字段。暂停之后再删除：

```json
{"jsonrpc":"2.0","id":26,"method":"cron/pause","params":{"threadId":"9f311e1e-…","name":"hourly-check","paused":true}}
{"jsonrpc":"2.0","id":27,"method":"cron/delete","params":{"threadId":"9f311e1e-…","name":"hourly-check"}}
```

删除时的通知是 `{"id":"fe78e575-…","threadId":"9f311e1e-…","job":null}`，随后回复 `{}`。

客户端的本地状态只需要一张按 `id` 索引的 `CronJobView` 表：`cron/list` 读一次，之后每条 `cron/changed` 按 `id` 替换，`job` 为 `null` 就删掉。

## 方法

### cron/list

| 参数 | 类型 | 说明 |
|---|---|---|
| `threadId?` | string | 只列这个会话的任务；不给时列这个用户的全部任务 |

结果是 `{data: CronJobView[]}`，按 `threadId`、`name` 排序。不需要配置 `Options.Jobs` 也能调用。`threadId` 指向不存在或别人的会话时返回空数组，不报错。

和 `thread/read` 一样，它在读库到回复入队之间持有投递锁，不会有 `cron/changed` 抢在回复之前，见[连接模型](/zh/integrate/protocol#连接模型)。

### cron/create

| 参数 | 类型 | 说明 |
|---|---|---|
| `threadId` | string | 所属会话 |
| `name` | string | 去掉首尾空白后匹配 `^[a-z0-9][a-z0-9_-]{0,63}$` |
| `spec` | string | 5 段 cron 表达式（分 时 日 月 周），或 `@yearly`、`@annually`、`@monthly`、`@weekly`、`@daily`、`@midnight`、`@hourly` 之一。语法细节见[调度表达式](/zh/engine/cron#调度表达式) |
| `prompt` | string | 到点发给会话的消息，去掉首尾空白后 1 到 4000 字符 |
| `times?` | integer | 总共发几次，至少 1；不给表示不限 |

结果是 `CronJobRow`。回复之前发一条 `cron/changed`。

| 错误 | 什么时候 |
|---|---|
| `-32000` `scheduled tasks are unavailable` | 宿主没有配置 `Options.Jobs` |
| `-32004` | 会话不存在或属于别人 |
| `-32602` | 名称、表达式、`prompt`、`times` 不合法；表达式带 `CRON_TZ=` 或 `TZ=` 前缀；`times` 为 1 的一次性任务算出的时间在将近一年以后（日期已经过去，表达式没有年份，否则会明年再发）。消息以 `cron: invalid scheduled task:` 开头，写明原因 |
| `-32000` `the request could not be completed` | 这个会话已有同名任务，或已有 64 个任务。原因只写在服务端日志里，见[错误与边界](#错误与边界) |

### cron/pause

| 参数 | 类型 | 说明 |
|---|---|---|
| `threadId`、`name` | string | 找到任务 |
| `paused` | boolean | 必填。`true` 暂停，`false` 恢复 |

结果是更新后的 `CronJobRow`，回复之前发 `cron/changed`。暂停只改 `paused`，`nextRunAt` 不变；恢复时按当前时间重新算 `nextRunAt`，一次性任务的时间已经过去时拒绝（`-32602`，同上）。

| 错误 | 什么时候 |
|---|---|
| `-32000` `scheduled tasks are unavailable` | 没有配置 `Options.Jobs` |
| `-32602` `paused is required` | 没给 `paused` |
| `-32004` | 会话不存在或属于别人；或者会话里没有这个名字的任务：`cron: this conversation has no task named "…": storage: not found` |

### cron/delete

参数 `threadId`、`name`，结果 `{}`。回复之前发 `job` 为 `null` 的 `cron/changed`。错误和 `cron/pause` 相同（没有 `paused` 那一条）。

## 通知

### cron/changed

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | string | 任务 ID |
| `threadId` | string | 所属会话 |
| `job` | `CronJobView` \| null | 任务现在的样子；`null` 表示已删除 |

什么时候发：

| 起因 | `job` |
|---|---|
| `cron/create`、`cron/pause`，或模型用工具新建、暂停任务 | 新的样子 |
| `cron/delete`，或模型用工具删除任务 | `null` |
| 到点处理过一次（发出、跳过或作废） | `runs`、`nextRunAt` 更新后的样子；最后一次发出后为 `null` |
| `thread/archive` 归档或取消归档会话 | 会话里每个任务各一条，`threadArchived` 随之变化 |
| `thread/delete` 删除会话 | 会话里每个任务各一条，`null` |

通知只发给任务所属用户当前的连接。

## 类型

### CronJobView

`cron/list`、`cron/changed` 和[搜索](/zh/integrate/protocol/search)结果的 `tasks` 用它。前十个字段就是 `CronJobRow`，`cron/create`、`cron/pause` 只返回这十个。

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | string | 任务 ID |
| `threadId`、`name` | string | 任务按 `(threadId, name)` 唯一 |
| `spec` | string | 调度表达式 |
| `prompt` | string | 到点发给会话的消息 |
| `times?` | integer \| null | 总共发几次；不出现表示不限 |
| `runs` | integer | 已经发了几次 |
| `paused` | boolean | 是否暂停 |
| `nextRunAt` | string | 下次到点时间（UTC）。暂停期间保持暂停前的值，不代表真的会在那时发出 |
| `createdAt` | string | 创建时间 |
| `threadTitle` | string | 所属会话的标题，可能是空字符串 |
| `workspaceId?` | string | 所属会话的工作区 |
| `parentThreadId?` | string | 所属会话是子 agent 会话时的父会话。这样的任务到点时会被拒绝但仍计数 |
| `threadArchived?` | boolean | 所属会话或它的父会话已归档。归档期间任务不会发出 |
| `lastRunAt?`、`lastTurnId?` | string | 这个任务最近一次开始的那一轮的创建时间和 ID |

## 错误与边界

- **重名和数量上限报不出原因。** 同名任务和"最多 64 个"这两种拒绝在引擎里是普通错误，不是 `cron.ErrInvalidJob`，所以按[错误码](/zh/integrate/protocol#错误码)的规则只给客户端 `-32000` `the request could not be completed`。对一个已有任务的名字调用 `cron/create` 实测就是这样。客户端要在发请求之前自己查重，或者把 `-32000` 当成"可能重名"提示用户。
- **`cron/list` 不要求 `Jobs`，写方法要求。** 没有配置 `Options.Jobs` 的宿主，列表总是空的，写方法返回 `-32000` `scheduled tasks are unavailable`。
- **子 agent 会话上的任务。** 模型在子 agent 里调用定时任务工具会被拒绝，`cron/create` 却不检查会话是不是子 agent 会话。这样建出的任务每次到点都开不了一轮，但仍计入 `runs`；归档父会话时也不会为它发 `cron/changed`。
- **到点精度是一分钟。** 引擎每分钟检查一次，发出的时间可能比 `nextRunAt` 晚不到一分钟。
- **跳过不补发。** 上一次的轮次还在排队时，这次到点直接跳过，不会之后补上。

## 代码位置

| 仓库 | 路径 | 职责 |
|---|---|---|
| ollupi | `gateway/cron.go` | `cron/*` 的处理函数、`cron/changed` 的组装 |
| ollupi | `gateway/protocol.go` | `CronListParams`、`CronCreateParams`、`CronPauseParams`、`CronDeleteParams`、`CronChangedNotification` |
| ollupi | `tools/cron/cron.go` | 校验、下次时间、每分钟的到点检查、计数 |
| ollupi | `tools/cron/tools.go` | 模型用的四个定时任务工具，子 agent 不能用 |
| ollupi | `repo/cron_jobs.go` | `CronJobRow`、`CronJobView`、数量和重名检查、最后一次发出后删除 |
| ollupi | `agent/threads.go` | 归档和删除会话时为它的任务发事件 |
| ollupi | `agent/turns.go` | `StartScheduledTurn`：以任务的 `prompt` 开始一轮，写上 `cronJobId` |
