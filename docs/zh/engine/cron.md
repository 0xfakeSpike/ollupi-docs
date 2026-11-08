# 定时任务

定时任务（scheduled task）是一条按 cron 时间表发到某个会话的消息。到点时它走的路径和用户发一条消息相同：会话空闲就开一轮，忙就排队。任务存在 `cron_jobs` 表，检查由宿主里的一条 goroutine 每分钟做一次，引擎本身不带 `main`，也不自己起定时器。

## 数据模型

任务的行类型是 `repo.CronJobRow`（`repo/cron_jobs.go`），表名 `cron_jobs`。

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | text，主键 | `Create` 里用 `uuid.NewString()` 生成 |
| `thread_id` | text，外键 `ON DELETE CASCADE` | 所属会话，也就是消息发去的会话 |
| `name` | text | 同会话内唯一，须匹配 `^[a-z0-9][a-z0-9_-]{0,63}$` |
| `spec` | text | cron 表达式，原样保存，不规范化 |
| `prompt` | text | 到点发送的消息，1 到 4000 字符 |
| `times` | integer，可空 | 总次数；空表示一直重复到删除 |
| `runs` | integer，默认 0 | 已发送次数 |
| `paused` | numeric | 是否停用，`cron_jobs_due` 索引的第一列 |
| `next_run_at` | datetime，UTC | 下次运行时间，`cron_jobs_due` 的第二列 |
| `created_at` | datetime，UTC | 创建时间，`autoCreateTime:false`，由调用方写入 |

表里没有状态列。状态由三样东西表达：`paused` 表示停用；`next_run_at` 表示下次何时发；`times` 与 `runs` 一起表示还剩几次。跑到最后一次的任务直接被删除，所以"已结束"在库里不存在。`user_id` 也没有，任务经 `thread_id` 找到主人（见[多用户与分片](/zh/engine/sharding)）。建表和索引迁移见[持久化](/zh/engine/persistence)。

读取用视图 `repo.CronJobView`，由 `cronJobViews()` join 出来，不落库：

| 字段 | 来源 | 说明 |
|---|---|---|
| `threadTitle` | `threads.title` | 会话标题 |
| `workspaceId` | `threads.workspace_id` | 空字符串表示不在工作区里 |
| `parentThreadId` | `threads.parent_thread_id` | 非空说明是子 agent 会话 |
| `threadArchived` | 自身或父会话的 `archived_at` | 任一非空即为 true |
| `lastRunAt` | 该任务最近一个轮次的 `created_at` | 没发过时为空；`lastTurnId` 是同一行的 `id` |

一个会话最多 64 个任务（`maxJobs`），名字在会话内唯一。两条都在 `CreateCronJob` 的事务里检查，超限和重名返回的是普通错误，不是 `ErrInvalidJob`；网关只把 `ErrInvalidJob` 映射成 `-32602`，所以这两种失败经 `cron/*` 调用时客户端只看到 `-32000 the request could not be completed`，原因只进服务端日志。模型走工具调用时能拿到原文。

## 调度表达式

解析用 `github.com/robfig/cron/v3`，解析器是 `robfig.NewParser(robfig.Minute | robfig.Hour | robfig.Dom | robfig.Month | robfig.Dow | robfig.Descriptor)`。

| 支持 | 说明 |
|---|---|
| 五段 | `分 时 日 月 周`，必须正好 5 段，秒段和年段都不支持 |
| 描述符 | `@yearly`、`@annually`、`@monthly`、`@weekly`、`@daily`、`@midnight`、`@hourly` |
| `@every` | 不支持，报 `unsupported descriptor` |
| `CRON_TZ=`、`TZ=` 前缀 | 拒绝。任务的时区只有一个，就是 `cron.New(db, location, onChange)` 传进来的那个 |

桌面端传的是 `time.Local`（`sidecar/internal/host/host.go`），也就是宿主机本地时区；时区在 `cron.New` 时定下，代码里没有再读一次的路径。

`next(spec, after)` 先把 `after` 转到该时区，取出墙上时间当作 UTC 交给 `Schedule.Next`，再把结果落回时区；如果落回后的墙上时间和算出来的不一致（夏令时跳变导致），按差值平移。最多回绕 1000 次，找不到下一次就报错。

所有不合法的任务都包成 `ErrInvalidJob`，网关把它映射成 `-32602` 并把原文发给客户端；报错文本说明哪一条不成立：

| 情况 | 拒绝原因 |
|---|---|
| `threadID` 为空 | 任务必须属于一个会话 |
| `name` 不匹配 `namePattern` | 打印要求匹配的正则 |
| `prompt` 为空或超过 4000 字符 | 长度超限 |
| `times` 小于 1 | 至少跑一次 |
| 不是 5 段、描述符不认识、解析失败 | 打印 spec 和底层错误 |
| 带时区前缀 | 不允许，见上 |
| 最后一次运行在近一年之外 | 见下 |

最后一条是 `lastRun`：当 `times` 非空、`*times - runs == 1`、且下一次运行晚于 `now.AddDate(1, -1, 0)` 时报 `ErrInvalidJob`。原因是 cron 表达式没有年份，写明日期的一次性任务如果那天已经过去，它会在明年的同一天跑。所以"只跑一次"的做法是写明日期的表达式加 `times: 1`，日期必须还在前面。

## 触发链路

宿主负责起定时器。桌面端在 `Host.Start` 里用 `cron.New(db, time.Local, onChange)` 构造 `Jobs`，再起一条 goroutine 调 `h.jobs.Run(ctx, h.agent.StartScheduledTurn)`；`Run` 是一个 `time.NewTicker(time.Minute)` 的循环，先 `sendDue` 再等下一次 tick，所以进程起来后立刻检查一次，之后每分钟一次。`Jobs` 里没有任何防止重入的字段或锁，同一个 `Jobs` 调两次 `Run` 就是两个定时器；"只起一个"由宿主保证。

`sendDue` 先取 `DueCronJobs(now)`，条件为 `paused = false AND next_run_at <= now AND 会话未归档 AND 父会话未归档`，按 `next_run_at, id` 排序。对每个任务：

1. `HasQueuedTurn(threadID, jobID)` 查这个任务是不是已经有一轮在排队（`turns` 里 `status = 'queued'` 且 `cron_job_id` 相同）。
2. 排队中：记日志 `cron task skipped while its last run is queued`，不发。
3. 否则调用 `send(threadID, prompt, jobID)`。
4. 除进程退出外，最后都调用 `ran` 记下这一轮（见下节）。

`send` 是 `Agent.StartScheduledTurn(threadID, text, jobID)`，它调 `startTurn` 再调 `submit`，和用户消息共用 `SubmitTurn`：

- 会话空闲：直接成为当前轮次，等槽位。
- 会话有未结束的轮次：新轮次落成 `queued`，发 `EventTurnQueued`。所以正在跑的那一轮不会被打断，任务消息排在它后面。

与普通轮次的区别只有三处：`StartScheduledTurn` 不接 `user` 参数，也不做 `owned` 检查，它按会话主人算（见[多用户与分片](/zh/engine/sharding)）；没有附件；`Input.CronJobID` 非空，写进 `turns.cron_job_id`，界面据此标出消息来源。另外 `startTurn` 会拒绝子 agent 会话（`ErrSubagentThread`）。

同一个任务会不会堆起来：不会。第一轮还在排队时，后续每一分钟都跳过；但第一轮已经在跑（`inProgress` 或等审批、等用户）时 `HasQueuedTurn` 为 false，新的一轮会照常入队，于是同一任务最多"一个在跑、一个在排队"。

进程停机期间错过的触发不会补发多次。`DueCronJobs` 不区分晚了多久，`ran` 用本次 tick 的 `now` 算下一次，所以停机一周的 `@daily` 任务只发一次，然后从启动时刻重新对齐。tick 之间的延迟也不会累积，因为每次都从 `now` 起算。

## 一轮之后

`ran(job, now, counted)` 负责推进：

```go
next, err := j.next(job.Spec, now)
if counted {
	_, err = j.db.CountCronJobRun(job.ID, job.NextRunAt, next)
} else {
	err = j.db.SetCronJobNextRun(job.ID, job.NextRunAt, next)
}
```

| 情况 | `runs` | `next_run_at` | 备注 |
|---|---|---|---|
| 发送成功 | +1 | 前进到下一次 | |
| 发送失败（`send` 返回错误） | +1 | 前进到下一次 | 计为一次运行，不重试 |
| 上一轮还在排队被跳过 | 不变 | 前进到下一次 | 本次不算运行 |
| 已是最后一次（`runs + 1 >= times`） | — | — | 整行删除 |

`CountCronJobRun` 和 `SetCronJobNextRun` 都带 `WHERE id = ? AND next_run_at = ?` 条件，即比较并交换，行已被删除或已被别人推进时静默不改。

失败不重试：`send` 出错只写 `slog.Warn("cron task not started")`，没有退避，也没有连续失败计数，下一次照计划来。一轮本身跑失败（模型报错、超时）完全不影响任务，`runs` 在发送时就已经加了。

停用与恢复：`SetPaused(true)` 只置 `paused`，`next_run_at` 保持原值，界面只显示"已暂停"不再显示下次时间；`SetPaused(false)` 从当前时间重算下一次，并重跑 `lastRun` 检查，所以一次性任务的日期已过就恢复不了，报 `ErrInvalidJob`。没有修改 `spec` 或 `prompt` 的方法，只能删了重建。

删除：`Delete` 删行并发 `cron/changed`；已经在跑的那一轮不受影响。

会话归档：任务行保留，`DueCronJobs` 把它过滤掉，`next_run_at` 停在原处。取消归档后下一个 tick 就会补发一次（时间早已过期），`runs` 加一，然后重新对齐。

会话删除：`cron_jobs` 的外键是 `ON DELETE CASCADE`，行随会话消失；`DeleteThread` 在删除前后读一次任务列表，为每个任务发 `EventCronJobChanged`，网关发出的 `cron/changed` 里 `job` 为 `null`，客户端据此移除。

## 协议与界面

`cron/list`、`cron/create`、`cron/pause`、`cron/delete` 四个方法和 `cron/changed` 一个通知，参数、返回值、错误码见[协议](/zh/integrate/protocol#定时任务)，此处不重复。未配置 `Options.Jobs` 时写方法返回 `-32000 scheduled tasks are unavailable`。

`cron/create` 和 `cron/pause` 返回的是 `repo.CronJobRow`，没有视图字段；桌面端不拿返回值更新列表，而是等 `cron/changed`。发通知有两条路径：

- `cron.Jobs` 的 `onChange` 回调，在创建、停用/恢复、删除、以及每次 `ran` 之后触发。它走 `Server.CronChanged`，先读会话拿到 `user_id`，再发给该用户当前的连接。所以下一次运行时间的推进也会推给界面。
- 会话归档或删除时由 agent 事件触发，连接直接把 `cron/changed` 发给自己的客户端。

界面（`views/cron/CronScreen.tsx`）是一页列出所有会话的任务，按工作区分组，未停用的按 `next_run_at` 升序、停用的排最后。每项显示 `name`、`spec` 的中文描述（形状认不出就原样显示）、`times`、`prompt`、发往的会话与工作区、停用标记或 `nextRunAt`、`lastRunAt`、`runs / times`。三个徽章对应三种"发了也不会到"：`parentThreadId` 非空、工作区已归档、`threadArchived`。开关调 `cron/pause`，删除按钮调 `cron/delete`。全局搜索也返回任务（`repo/search.go` 的 `Found.Tasks`）。

## 边界

**时区与夏令时。** 表达式按传入时区的墙上时间解释，时区在构造 `Jobs` 时定下，进程不重启就一直是它。跳变用 `America/New_York` 跑过 `next` 的逻辑：春季 3 月 8 日 02:30 不存在，`30 2 * * *` 当天在 03:30 EDT 触发，也就是原本 02:30 的那个绝对时刻；秋季 11 月 1 日 01:30 出现两次，只在前一次（EDT）触发，后一次（EST）不跑。仓库里没有夏令时的测试。

**并发。** 检查粒度是一分钟，`sendDue` 串行处理所有到期任务，而 `send` 只做入队：真正的并发由槽位决定（默认 32 个，见[执行模型](/zh/engine/execution)）。一个会话最多 64 个任务，同一任务最多一个在跑、一个在排队。一轮占槽位最长 `RunLimit`（默认 4 小时），超时这一轮失败，任务本身不受影响。

**多进程与分片。** 定时器在 `Agent.Start` 之后由宿主启动；配了 `Config.Lease` 时 `Start` 先等到租约才返回，所以同一个分片只有一个进程在跑定时器（见[多用户与分片](/zh/engine/sharding)）。`Jobs` 自己不认租约：`Run` 不读租约，租约丢失后要不要停由传进来的 `ctx` 决定，引擎里没有处理。也没有跨进程去重：`next_run_at` 的比较并交换只防止重复推进，而发送发生在记录之前，两个进程同时对同一个库跑定时器会各发一次。

**发送与记录之间的窗口。** `sendDue` 先发送再调 `ran`，两步之间崩溃，重启后同一个到期时间会再发一次。这是已知的取舍（见[决策记录](/zh/reference/decisions#_6-定时任务即消息)），代码顺序至今如此。

**一次 tick 里的崩溃。** `sendDue` 有 `recover`，panic 只写 `slog.Error`，这一分钟剩下的任务不处理、也不记账，下一分钟重来。`TestACrashInATickLeavesTheNextOne` 守着这条。

**工作区归档。** `DueCronJobs` 只看会话和父会话的 `archived_at`，不看工作区。工作区归档后任务仍会被选中，消息在 `submit` 里被 `ErrWorkspaceArchived` 拒绝，发送返回错误，这一轮照样计数、`times` 照样递减。所以界面文案"工作区已归档，期间不会发送"里，"不发送"对，"不消耗次数"不对。

**子 agent 会话。** 工具层拒绝子 agent 创建任务，`cron/create` 只校验会话属于调用者（`ThreadOf`）、不校验父子关系，所以经协议可以建。建了之后每一轮到点都被 `ErrSubagentThread` 拒绝，仍然计数，直到 `times` 用完被删。

## 代码位置

| 仓库 | 路径 | 职责 |
|---|---|---|
| ollupi | `tools/cron/cron.go` | `Jobs`、`schedule`/`next`（表达式与时区）、`Create`/`Delete`/`SetPaused`、`Run`/`sendDue`/`ran` |
| ollupi | `tools/cron/tools.go` | `create_scheduled_job` 等四个工具、参数 schema、`ErrInvalidJob` 的入口 |
| ollupi | `repo/cron_jobs.go` | `cron_jobs` 表、`CronJobView`、`DueCronJobs`、`CountCronJobRun`、`SetCronJobNextRun` |
| ollupi | `repo/turns.go` | `turns.cron_job_id`、`HasQueuedTurn`、`SubmitTurn` 的排队分支 |
| ollupi | `agent/turns.go` | `StartScheduledTurn`、`startTurn`、`submit` |
| ollupi | `agent/threads.go` | 归档、删除会话时发 `EventCronJobChanged` |
| ollupi | `gateway/cron.go` | `cron/*` 方法、`Server.CronChanged`、`cron/changed` |
| ollupi | `gateway/protocol.go`、`gateway/server.go` | 方法表、`CronJobView` 参数类型、事件翻译、`ErrInvalidJob` → `-32602` |
| ollupi-desktop | `sidecar/internal/host/host.go` | 构造 `cron.Jobs`、`Host.Start` 里起定时器 |
| ollupi-desktop | `apps/desktop/src/renderer/src/domains/cron.ts` | 客户端状态、`cron/changed` 的应用、`cron/*` 调用 |
| ollupi-desktop | `apps/desktop/src/renderer/src/views/cron/CronScreen.tsx` | 定时任务页 |
