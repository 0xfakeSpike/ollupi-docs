# 定时任务

定时任务（scheduled job，代码里叫 cron job）是一条按 cron 时间表发到某个会话（thread）的消息。到点时它走的路径和用户发一条消息相同：在会话里排一个轮次（turn），和用户的轮次一起按先后等槽位（slot）。任务存在 `cron_jobs` 表，`cron` 包的 `Run` 每分钟检查一次，由宿主（host）在 `Host.Run` 里和调度器一起跑。

## 为什么这样设计

- **到点就是发一条消息。** 定时任务不在 agent 里：`cron.Run` 到点只调用宿主传入的 `Submit`，也就是 `app.App.Scheduled`，它和用户发消息共用 `app` 的排队逻辑。排队、槽位、审批、恢复全部沿用普通轮次的机制，调度时不区分轮次从哪里来，定时任务不降级，和用户的轮次同样先来先排。README 对比的另一种做法是外部 cron 启动进程，项目没有用过。见[设计决策 6](/zh/reference/decisions#_6-定时任务即消息)。
- **发送和记账在同一个事务里。** 要不要发、发出的消息、次数加一、下一次时间，在一次提交里一起写；事务里先重读任务，下一次时间已经变了就什么都不做。所以同一个到期时间不会发两次，崩溃也不会留下"发了没记"的窗口。
- **库里没有状态列。** 停用是 `paused`，下次何时发是 `next_run_at`，还剩几次由 `times` 和 `runs` 算出；跑完最后一次的任务直接删掉。
- **错过的触发只补一次。** 每次都从当前时刻算下一次，停机一周的 `@daily` 任务重启后只发一次，不会补发七次，也不会累积延迟。
- **会话拒收的一次不算数。** 消息被会话拒绝（工作区归档、排队已满等）时这一次跳过、不计次数，时间照样往前走，任务按计划继续，不会因为一次失败堆积。
- **一次性任务用写明日期的表达式加 `times: 1`。** cron 表达式没有年份，日期已过的一次性任务会在明年同一天跑。所以最后一次运行在 11 个月之后时拒绝创建或恢复。
- **界面走专门的方法，不调工具。** 模型用 `create_scheduled_job` 等工具，界面用 `cron/list`、`cron/create` 等方法，返回类型化的行，两者共用 `cron` 包的 `Create`、`Pause`、`Delete`。见[设计决策 9](/zh/reference/decisions#_9-工具只给模型用)。

代价：检查粒度是一分钟；会话拒收的那一次没有任何记录，只是次数不涨；大量任务同时到点时和用户消息在同一个队列里排队，[混合负载实验](/zh/benchmarks/#混合负载与公平)里 1000 个任务同时到期，峰值期间到达的用户轮次等第一次模型请求的 p50 是 44.1 s，峰值 59.4 s 排空（模拟模型，测于 2026-11-04，早于 v0.16.0 的日志重建，之后没有重测）。

::: info 演进
- 早期定时任务是 agent 的一部分：事件循环里有一个定时分支，`settle` 还要负责发送到期的任务。`ee7776c` 把这些全部移出 agent，改成到点调用 `send`。
- 日期在 11 个月之后的一次性任务被拒绝，来自 `8f1d5e2`。
- 以前先发送、再在另一步记账，两步之间崩溃会重发一次；发送失败也计为一次运行。`35bab6a` 把两步放进一个事务，会话拒收的一次不再计数。
:::

## 数据模型

任务是 `account.CronJob`，表名 `cron_jobs`。

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | text，主键 | 创建时用 `uuid.NewString()` 生成 |
| `thread_id` | text，外键 `ON DELETE CASCADE` | 所属会话，也就是消息发去的会话 |
| `name` | text | 同会话内唯一（`UNIQUE (thread_id, name)`），须匹配 `^[a-z0-9][a-z0-9_-]{0,63}$` |
| `spec` | text | cron 表达式，去掉首尾空白后保存，不规范化 |
| `prompt` | text | 到点发送的消息，1 到 4000 字符 |
| `times` | integer，可空 | 总次数；空表示一直重复到删除 |
| `runs` | integer，默认 0 | 已发送次数 |
| `paused` | integer，默认 0 | 是否停用 |
| `next_run_at` | datetime，UTC | 下次运行时间 |
| `created_at` | datetime | 创建时间 |

索引 `cron_jobs_due` 建在 `next_run_at` 上，只收 `paused = 0` 的行。表里没有状态列，也没有 `user_id`，任务经 `thread_id` 找到主人（见[分片与多用户](/zh/engine/sharding)）。建表见[持久化](/zh/engine/persistence)。

读取用视图 `store.CronJobView`，由 `cronJobViews()` join 出来，不落库：

| 字段 | 来源 | 说明 |
|---|---|---|
| `threadTitle` | `threads.title` | 会话标题 |
| `workspaceId` | `threads.workspace_id` | 空表示不在工作区里 |
| `threadArchived` | `threads.archived_at` | 会话归档时为 true |
| `lastTurnId`、`lastRunAt` | 这个任务发出的最后一个轮次 | 按 `turns.cron_job` 找，`lastRunAt` 是那个轮次的排队时间；没发过时为空 |

只有顶层会话能有任务：协议的 `cron/*` 用 `topThread` 取会话，子 agent 会话报 `ErrSubagentThread`；模型的工具只有主 agent 有，子 agent 的角色没有 `cron` 提供者。

`cron.Create` 在事务里查这个会话已有的任务：已满 64 个（`MaxJobs`）或重名都报 `invalid scheduled job`，和其他校验错误一样。

## 调度表达式

日历是 `cron.Calendar`，由 `cron.NewCalendar(location)` 建；`location` 是 `host.Config.Location`，不填时是 `time.Local`。解析用 `github.com/robfig/cron/v3`，解析器是 `robfig.NewParser(robfig.Minute | robfig.Hour | robfig.Dom | robfig.Month | robfig.Dow | robfig.Descriptor)`。

| 支持 | 说明 |
|---|---|
| 五段 | `分 时 日 月 周`，必须正好 5 段，秒段和年段都不支持 |
| 描述符 | `@yearly`、`@annually`、`@monthly`、`@weekly`、`@daily`、`@midnight`、`@hourly` |
| `@every` | 不支持，报 `unsupported descriptor` |
| `CRON_TZ=`、`TZ=` 前缀 | 拒绝。任务的时区只有一个，就是日历的时区 |

时区在 `host.New` 时定下，代码里没有再读一次的路径。模型的 `create_scheduled_job` 在描述里写明这个时区。

`Calendar.Next(spec, after)` 先把 `after` 转到该时区，取出墙上时间当作 UTC 交给 `Schedule.Next`，再把结果落回时区；如果落回后的墙上时间和算出来的不一致（夏令时跳变导致），按差值平移。最多回绕 1000 次，找不到下一次就报错。

所有不合法的任务都包成 `ErrInvalidJob`（`invalid scheduled job`），网关把它映射成 `-32602` 并把原文发给客户端；报错文本说明哪一条不成立：

| 情况 | 拒绝原因 |
|---|---|
| `name` 不匹配 `NamePattern` | 打印要求匹配的正则 |
| `prompt` 为空或超过 4000 字符 | 长度超限 |
| `times` 小于 1 | 至少跑一次 |
| 不是 5 段、描述符不认识、解析失败 | 打印 spec 和底层错误 |
| 带时区前缀 | 不允许，见上 |
| 最后一次运行在 11 个月之后 | 见下 |
| 会话里已有 64 个任务、或已有同名任务 | 打印原因 |

最后一次运行的检查是 `lastRun`：当 `times` 非空、`*times - runs == 1`、且下一次运行晚于 `now.AddDate(1, -1, 0)` 时报错。原因见[为什么这样设计](#为什么这样设计)：写明日期的一次性任务如果那天已经过去，它会在明年的同一天跑，日期必须还在前面。

## 触发链路

`Host.Run` 在一个 errgroup 里起 `cron.Run(ctx, store, calendar, app.Scheduled)`。`Run` 是一个 `time.NewTicker(time.Minute)` 的循环，先 `sendDue` 再等下一次 tick，所以进程起来后立刻检查一次，之后每分钟一次。

`sendDue` 先读 `Due(now)`：`paused = 0 AND next_run_at <= now AND 会话未归档`，按 `next_run_at, id` 排序。每个任务各开一个事务，在事务里（`cron.send`）：

1. 按 ID 重读任务。任务已经删掉、已停用、或 `next_run_at` 和读到的不同（别人已经处理过），什么都不做。
2. 读会话的视图，看排在当前轮次后面、还没开始的轮次里，有没有这个任务发出的（`Turn.CronJob` 相同）。
3. 有：这一次跳过，不发、不计数。
4. 没有：调用 `Submit(tx, thread, prompt, jobID)`，在同一个事务里把消息排进会话。
5. 用 `Calendar.Advance` 推进：发了就 `runs` 加一；`runs` 到了 `times` 就删掉任务，否则从 `now` 算下一次运行时间并写回。

`Submit` 返回错误时这个事务回滚，再开一个事务以"不发"重走一遍：任务不计数，只推进下一次时间。别的错误（读写库失败、算不出下一次时间）让 `sendDue` 返回，`cron.Run` 跟着返回。

`Submit` 是 `App.Scheduled`。它按 ID 取会话，不检查调用者，也没有附件，然后走和用户发消息同一个 `queue`：

| 检查 | 不通过时 |
|---|---|
| 消息合法 | 拒收 |
| 会话未归档 | `ErrThreadArchived` |
| 工作区可用（没归档、没在移动） | 拒收 |
| 排在后面的轮次少于 20 个 | `ErrQueueFull` |
| 有可用的模型：沿用会话上一轮的连接，没有就用第一个模型 | 连接不可用时拒收 |
| 消息放得进模型的输入 | 拒收 |

通过后追加两条日志条目：`TurnQueued`（带模型、按输入大小选的主 agent 角色、`CronJob` 任务 ID）和这条 `UserMessage`。会话空闲时它就是当前轮次；会话正忙时它排在后面，每条消息各自一个轮次，正在跑的那一轮不会被打断。轮次的 `CronJob` 也写进 `turns.cron_job`，界面据此标出消息来源、视图据此算 `lastRunAt`。

之后它和用户的轮次没有区别：调度器按会话变成可运行的先后（`runnable_since`）分配槽位，顶层会话排在子 agent 会话前面，不看轮次是谁发的。见[执行模型](/zh/engine/execution)。

同一个任务会不会堆起来：不会。上一次发出的轮次还在排队时，后续每一分钟都跳过；它一旦成为当前轮次（在跑、等审批、等用户），就不算"排在后面"，新的一轮会照常入队，于是同一任务最多"一个在当前、一个在排队"。

进程停机期间错过的触发不会补发多次。`Due` 不区分晚了多久，`Advance` 用本次 tick 的 `now` 算下一次，所以停机一周的 `@daily` 任务只发一次，然后从启动时刻重新对齐。tick 之间的延迟也不会累积。

## 一轮之后

| 情况 | `runs` | `next_run_at` | 备注 |
|---|---|---|---|
| 发出 | +1 | 前进到下一次 | |
| 会话拒收（`Submit` 返回错误） | 不变 | 前进到下一次 | 第二个事务里推进，不计数，不留记录 |
| 上一次的轮次还在排队，被跳过 | 不变 | 前进到下一次 | |
| 发出且到了最后一次（`runs + 1 >= times`） | — | — | 整行删除 |

一轮本身跑失败（模型报错、超时）完全不影响任务，`runs` 在排队时就已经加了。

停用与恢复：`Calendar.Pause(job, true)` 只置 `paused`，`next_run_at` 保持原值；恢复时从当前时间重算下一次，并重跑 `lastRun` 检查，所以一次性任务的日期已过就恢复不了，报 `ErrInvalidJob`。没有修改 `spec` 或 `prompt` 的方法，只能删了重建。

删除：删行并发 `cron/changed`；已经排进会话的轮次不受影响。

会话归档：任务行保留，`Due` 把它过滤掉，`next_run_at` 停在原处。取消归档后下一个 tick 就会补发一次（时间早已过期），`runs` 加一，然后重新对齐。

会话删除：`cron_jobs` 的外键是 `ON DELETE CASCADE`，行随会话消失；`DeleteThread` 在删除前读出这个会话的任务，为每个发一条删除事件，客户端收到 `job` 为 `null` 的 `cron/changed`。

## 协议与界面

`cron/list`、`cron/create`、`cron/pause`、`cron/delete` 四个方法和 `cron/changed` 一个通知，参数、返回值、错误码见[定时任务协议](/zh/integrate/protocol/cron)，此处不重复。

| 方法 | 走哪 |
|---|---|
| `cron/list` | `App.CronJobs`：用户的全部任务，按 `created_at, id` 排序；给了 `threadId` 时只列这个会话的，会话要属于调用者且是顶层会话 |
| `cron/create` | `App.CreateCronJob` → `cron.Create`，参数打包成 `cron.Draft`（`Name`、`Spec`、`Prompt`、`Times`） |
| `cron/pause` | `App.PauseCronJob` → `cron.Pause`，`paused` 必填 |
| `cron/delete` | `App.DeleteCronJob` → `cron.Delete` |

返回的都是带视图字段的行。通知不再分两条路：任务行的每次写入（`PutCronJob`：创建、停用/恢复、每次 tick 的推进）和删除都在提交时进 feed，网关把它们翻译成发给这个用户所有连接的 `cron/changed`，所以下一次运行时间的推进也会推给界面。会话归档不改任务行，不发 `cron/changed`，`threadArchived` 要等这个任务下一次有写入、或客户端重新 `cron/list` 才更新。

模型的四个工具属于 `cron` 提供者，作用于调用它的会话：

| 工具 | 标注 | 说明 |
|---|---|---|
| `create_scheduled_job` | 非只读，`destructiveHint` 假 | 参数 `name`、`spec`、`prompt`、`times`；描述里写明日历的时区 |
| `pause_scheduled_job` | 非只读，`destructiveHint` 假 | 参数 `name`、`paused` |
| `delete_scheduled_job` | `destructiveHint` 真 | 参数 `name` |
| `list_scheduled_jobs` | 只读 | 这个会话的任务：`name`、`spec`、`prompt`、`times`、`runs`、`paused`、`nextRun`、`lastRun` |

四个都标了 `OpenWorldHint` 为假。前三个不是只读，`on-request` 下规则没命中时会问用户，见[审批与权限](/zh/engine/permissions)。全局搜索也返回任务，协议字段是 `cronJobs`，见[搜索](/zh/engine/search)。

## 边界与已知问题

- **会话拒收没有记录。** 工作区归档或在移动、排队已满、连接不可用、消息放不进模型时，这一次被跳过、不计数，没有日志也没有通知说明原因，只能从 `runs` 和 `lastRunAt` 没变看出来。
- **库出错会停下整个宿主。** `sendDue` 遇到读写库失败就返回错误，`cron.Run` 和调度器、记忆提炼在 `Host.Run` 的同一个 errgroup 里，按代码推断会让 `Host.Run` 整体返回。
- **多进程与分片。** 发送和记账在一个事务里，事务开头重读 `next_run_at`，所以两个进程对同一个库跑 `cron.Run` 也只会发一次。分片的每次写入都检查租约的 epoch，丢了租约的进程写不进去，`cron.Run` 随写入失败返回（见[分片与多用户](/zh/engine/sharding)）。
- **时区与夏令时。** 表达式按日历时区的墙上时间解释，时区在 `host.New` 时定下，进程不重启就一直是它。跳变按 `Next` 的逻辑推算：在 `America/New_York`，春季 3 月 8 日 02:30 不存在，`30 2 * * *` 当天在 03:30 EDT 触发，也就是原本 02:30 的那个绝对时刻；秋季 11 月 1 日 01:30 出现两次，只在前一次（EDT）触发，后一次（EST）不跑。仓库里没有夏令时的测试。
- **并发和排队。** 检查粒度是一分钟，`sendDue` 串行处理所有到期任务，每个任务只做入队：真正的并发由槽位决定（默认 32 个，见[执行模型](/zh/engine/execution)）。同一任务最多一个在当前、一个在排队。一轮占槽位最长 `RunLimit`（默认 4 小时），超时这一轮失败，任务本身不受影响。
- **会话归档后恢复会补一次。** 归档期间任务停在原来的 `next_run_at`，取消归档后的第一个 tick 立刻发一次。
- **归档不推送任务的变化。** 见[协议与界面](#协议与界面)。
- **不能修改任务。** 没有改 `spec` 或 `prompt` 的方法，只能删了重建。

## 代码位置

| 路径 | 职责 |
|---|---|
| `cron/calendar.go` | `Calendar`、`Draft`、`NewJob`、`Pause`、`Advance`、`Next`、`lastRun`、各项校验和 `ErrInvalidJob` |
| `cron/jobs.go` | `Create`、`Pause`、`Delete`：在事务里查数量和重名、写行 |
| `cron/cron.go` | `Run`、`sendDue`、`send`：每分钟检查，发送和记账在一个事务里 |
| `app/cronjobs.go` | `CronJobs`、`CreateCronJob`、`PauseCronJob`、`DeleteCronJob`：只接受调用者的顶层会话 |
| `app/turns.go` | `Scheduled` 和 `queue`：定时任务的消息和用户消息同一条排队路径 |
| `tool/builtin/cronjobs/cronjobs.go` | `create_scheduled_job` 等四个工具 |
| `account/account.go` | `CronJob` |
| `store/store.go`、`store/sqlite/owned.go` | `CronJobView`、`cronJobViews`、`Due`、`PutCronJob`、`DeleteCronJob`、删会话时的删除事件 |
| `store/sqlite/migrations/0001_init.sql`、`0002_task_runs_and_waits.sql` | `cron_jobs` 表和索引；`turns.cron_job` |
| `host/host.go` | `Config.Location`、创建日历、`Host.Run` 里起 `cron.Run` |
| `gateway/owned.go`、`gateway/server.go`、`gateway/wire.go` | `cron/*` 方法、`cron/changed`、`CronJobRow` |
