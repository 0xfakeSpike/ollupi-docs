# 定时任务

定时任务按调度表达式定时向一个会话发一条消息，到点时就是这个会话里普通的一轮。客户端用 `cron/*` 列出、新建、暂停和删除任务，用 `cron/changed` 跟上变化。调度表达式的语法和触发链路见[定时任务的实现](/zh/engine/cron)，这里只讲协议上看到的东西。

本页按引擎 v0.17.2 写，示例来自对 v0.17.1 网关的脚本试验（时区 UTC，ID 缩短了）。

## 概念与状态

- **任务属于会话。** 一个任务挂在一个顶层会话上，在这个会话里按 `(threadId, name)` 唯一，暂停和删除都按这两个值找任务，不用 `id`。一个会话最多 64 个任务。子 agent 会话没有任务。
- **到点就是一轮。** 宿主每分钟检查一次到期的任务，到期就以任务的 `prompt` 在所属会话里排一轮，和用户发的消息走同一条路，这一轮的 `TurnRow.cronJobId` 是任务的 `id`。会话正在跑别的轮次时，这一轮排在后面等。轮次本身怎样跟踪见[一轮与条目](/zh/integrate/protocol/turns)。
- **时区归宿主。** 调度表达式按宿主 `host.Config.Location` 的时区解释，不给时用宿主进程的本地时区；不允许在表达式里写时区前缀；`nextRunAt` 总是 UTC。
- **次数。** `times` 是总共发几次，不写表示不限；`runs` 是已经发了几次。最后一次发出后任务被删除，客户端收到 `job` 为 `null` 的 `cron/changed`。
- **谁会改任务。** 客户端的 `cron/*` 方法、模型的定时任务工具（子 agent 拿不到）、每次到点、会话删除。每一种都发 `cron/changed`。

一个任务到点时的处理：

| 情况 | 结果 | 计入 `runs` |
|---|---|---|
| 正常 | 在会话里排一轮，`nextRunAt` 前移 | 是 |
| 这个任务上一次排的那一轮还没开始 | 这次跳过，`nextRunAt` 前移 | 否 |
| 会话拒绝这条消息：所在工作区已归档、已有 20 条消息在排队、模型连接不可用等 | 这次作废，`nextRunAt` 前移 | 否 |
| 已暂停，或所属会话已归档 | 不处理，`nextRunAt` 不动 | 否 |

由代码推断：归档的会话取消归档后，过期的 `nextRunAt` 会在下一次检查时立刻发一次。

::: info 演进
v0.12.1 里会话拒绝的那一次也计入 `runs`。`35bab6a` 把到点处理放进一个事务：发不发、跳过还是结束都在同一个事务里决定，同一个时间点不会发两次，被拒的那次不再计数。
:::

## 典型流程

新建一个每小时一次、总共三次的任务。`cron/changed` 先于回复到达，两者都是完整的 `CronJobRow`：

```json
→ {"jsonrpc":"2.0","id":46,"method":"cron/create","params":{"threadId":"bfbd192b-…","name":"hourly-check","spec":"@hourly","prompt":"Anything new?","times":3}}
← {"jsonrpc":"2.0","method":"cron/changed","params":{"id":"4afe8237-…","threadId":"bfbd192b-…","job":{"id":"4afe8237-…","threadId":"bfbd192b-…","name":"hourly-check","spec":"@hourly","prompt":"Anything new?","times":3,"runs":0,"paused":false,"nextRunAt":"2026-11-18T13:00:00Z","createdAt":"2026-11-18T12:19:29.291426Z","threadTitle":"general"}}}
← {"jsonrpc":"2.0","id":46,"result":{"job":{ …同上… }}}
```

同名再建一次被拒：

```json
→ {"jsonrpc":"2.0","id":47,"method":"cron/create","params":{"threadId":"bfbd192b-…","name":"hourly-check","spec":"@hourly","prompt":"Anything new?"}}
← {"jsonrpc":"2.0","id":47,"error":{"code":-32602,"message":"invalid scheduled job: this conversation already has a scheduled job named \"hourly-check\""}}
```

暂停之后再删除：

```json
→ {"jsonrpc":"2.0","id":52,"method":"cron/pause","params":{"threadId":"bfbd192b-…","name":"hourly-check","paused":true}}
← {"jsonrpc":"2.0","method":"cron/changed","params":{"id":"4afe8237-…","threadId":"bfbd192b-…","job":{ … "paused":true,"nextRunAt":"2026-11-18T13:00:00Z", … }}}
← {"jsonrpc":"2.0","id":52,"result":{"job":{ … }}}
→ {"jsonrpc":"2.0","id":56,"method":"cron/delete","params":{"threadId":"bfbd192b-…","name":"hourly-check"}}
← {"jsonrpc":"2.0","method":"cron/changed","params":{"id":"4afe8237-…","threadId":"bfbd192b-…","job":null}}
← {"jsonrpc":"2.0","id":56,"result":{}}
```

客户端的本地状态只需要一张按 `id` 索引的 `CronJobRow` 表：`cron/list` 读一次，之后每条 `cron/changed` 按 `id` 替换，`job` 为 `null` 就删掉。

## 方法

定时任务总是可用，不需要宿主额外配置。

### cron/list

| 参数 | 类型 | 说明 |
|---|---|---|
| `threadId?` | string | 只列这个会话的任务；不给时列这个用户的全部任务 |

结果是 `{data: CronJobRow[]}`，按 `createdAt`、再按 `id` 排序。

| 错误 | 什么时候 |
|---|---|
| `-32004` | `threadId` 指向不存在或别人的会话：`store: thread nope: store: not found` |
| `-32013` | `threadId` 是子 agent 会话 |

### cron/create

| 参数 | 类型 | 说明 |
|---|---|---|
| `threadId` | string | 所属会话，必须是顶层会话 |
| `name` | string | 去掉首尾空白后匹配 `^[a-z0-9][a-z0-9_-]{0,63}$` |
| `spec` | string | 5 段 cron 表达式（分 时 日 月 周），或 `@yearly`、`@annually`、`@monthly`、`@weekly`、`@daily`、`@midnight`、`@hourly` 之一。语法细节见[调度表达式](/zh/engine/cron#调度表达式) |
| `prompt` | string | 到点发给会话的消息，去掉首尾空白后 1 到 4000 字符 |
| `times?` | integer | 总共发几次，至少 1；不给表示不限 |

结果是 `{job: CronJobRow}`，同时发 `cron/changed`。会话已归档也能建，只是归档期间不会发出。

| 错误 | 什么时候 |
|---|---|
| `-32602` | 名称、表达式、`prompt`、`times` 不合法；表达式带 `CRON_TZ=` 或 `TZ=` 前缀；`times` 只剩一次的任务算出的时间在将近一年以后（日期已经过去，表达式没有年份，否则会明年再发）。消息以 `cron: invalid scheduled job:` 开头，写明原因 |
| `-32602` | 这个会话已有同名任务，或已有 64 个任务：`invalid scheduled job: this conversation already has a scheduled job named "…"`、`invalid scheduled job: a conversation has at most 64 scheduled jobs` |
| `-32004` | 会话不存在或属于别人 |
| `-32013` | 子 agent 会话 |

### cron/pause

| 参数 | 类型 | 说明 |
|---|---|---|
| `threadId`、`name` | string | 找到任务 |
| `paused` | boolean | 必填。`true` 暂停，`false` 恢复 |

结果是更新后的 `{job: CronJobRow}`，同时发 `cron/changed`。暂停只改 `paused`，`nextRunAt` 不变；恢复时按当前时间重新算 `nextRunAt`，一次性任务的时间已经过去时拒绝（`-32602`，同上）。

| 错误 | 什么时候 |
|---|---|
| `-32602` `paused is required` | 没给 `paused` |
| `-32004` | 会话不存在或属于别人；或者会话里没有这个名字的任务：`this conversation has no scheduled job named "…": store: not found` |
| `-32013` | 子 agent 会话 |

### cron/delete

参数 `threadId`、`name`，结果 `{}`，同时发 `job` 为 `null` 的 `cron/changed`。错误和 `cron/pause` 相同（没有 `paused` 那一条）。

::: info 演进
v0.12.1 里同名任务和"最多 64 个"这两种拒绝是普通错误，客户端只收到 `-32000`；没配 `Options.Jobs` 的宿主上写方法返回 `scheduled tasks are unavailable`。`d110977` 把两种拒绝归入无效任务，返回 `-32602` 并写明原因。v0.16.0 的 `host.New` 总会装上定时任务，那个配置项已经没有了。`cron/create`、`cron/pause` 的结果由 `9b5b50b` 改成 `{job}`，`b02dbfd` 让它和 `cron/list`、通知一样带上会话标题和最近一次运行。
:::

## 通知

### cron/changed

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | string | 任务 ID |
| `threadId` | string | 所属会话 |
| `job` | `CronJobRow` \| null | 任务现在的样子；`null` 表示已删除 |

什么时候发：

| 起因 | `job` |
|---|---|
| `cron/create`、`cron/pause`，或模型用工具新建、暂停任务 | 新的样子 |
| `cron/delete`，或模型用工具删除任务 | `null` |
| 到点处理过一次（发出、跳过或作废） | `runs`、`nextRunAt` 更新后的样子；最后一次发出后为 `null` |
| `thread/delete` 删除会话 | 会话里每个任务各一条，`null` |

通知在事务提交之后发给任务所属用户的每一条连接。到点发出的那一次，任务的通知和新一轮的 `thread/changed`、`turn/changed`、`item/changed` 出自同一个事务。

## 类型

### CronJobRow

`cron/list`、`cron/create`、`cron/pause` 的结果，`cron/changed` 的 `job`，以及[搜索](/zh/integrate/protocol/search)结果的 `cronJobs` 都用它。

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
| `threadArchived?` | boolean | 所属会话已归档。归档期间任务不会发出 |
| `lastTurnId?`、`lastRunAt?` | string | 这个任务最近一次排的那一轮的 ID 和排队时间 |

### 参数类型

`CronListParams`、`CronCreateParams`、`CronPauseParams`、`CronDeleteParams` 的字段就是上面各方法的参数表；`CronListResult` 包了一层 `data`，`CronResult` 包了一层 `job`；通知是 `CronChangedNotification`。

## 错误与边界

- **归档会话不发通知。** `thread/archive` 归档或取消归档会话时不发 `cron/changed`，客户端手里的 `threadArchived` 会过时，要重新 `cron/list` 或者自己按会话的 `archivedAt` 推。
- **归档的工作区会吃掉到点。** 会话所在的工作区归档后，任务照样到点，只是开不了一轮，这次作废，`nextRunAt` 前移，不计入 `runs`。
- **到点精度是一分钟。** 宿主每分钟检查一次，发出的时间可能比 `nextRunAt` 晚不到一分钟。
- **跳过不补发。** 上一次的轮次还在排队时，这次到点直接跳过，不会之后补上。

## 代码位置

| 路径 | 职责 |
|---|---|
| `gateway/owned.go` | `cron/*` 的处理函数，`paused` 必填的检查 |
| `gateway/server.go` | 把变更流里的事件转成 `cron/changed` |
| `gateway/protocol.go`、`gateway/wire.go` | `CronListParams`、`CronCreateParams`、`CronPauseParams`、`CronDeleteParams`、`CronChangedNotification`、`CronJobRow` |
| `app/cronjobs.go` | `CronJobs`、`CreateCronJob`、`PauseCronJob`、`DeleteCronJob`：只认这个用户的顶层会话 |
| `app/turns.go` | `Scheduled`：以任务的 `prompt` 排一轮，写上 `cronJobId` |
| `cron/calendar.go` | `Calendar`：名称和表达式的校验、下次时间、`Pause`、`Advance` |
| `cron/jobs.go` | `Create`、`Pause`、`Delete`：数量和重名检查 |
| `cron/cron.go` | `Run`：每分钟的到点检查、跳过、计数、最后一次发出后删除 |
| `tool/builtin/cronjobs/cronjobs.go` | 模型用的四个定时任务工具 |
| `store/sqlite/owned.go` | `cron_jobs` 表、`CronJobView`、`Due`、删会话时为它的任务发事件 |
| `host/host.go` | 时区默认值，启动 `cron.Run` |
