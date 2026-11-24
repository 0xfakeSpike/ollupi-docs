# 持久化与崩溃恢复

每个会话存成一份只追加的日志：记录写下后不再修改，轮次、条目、会话在等什么、能不能运行，都由日志折叠得出。日志和折叠结果在一个 SQLite 库里，一个库就是一个分片。每一步先追加进日志再执行，进程任何时刻退出，重启读日志就知道做到哪了。调度见[执行模型](/zh/engine/execution)。

## 为什么这样设计

- **会话是日志。** 变化都追加一条 `conversation.Entry`，状态由纯函数 `conversation.View.Apply` 算出，不另存可能对不上的状态。见[设计决策 3](/zh/reference/decisions#_3-无内存调度状态)。
- **一条写路径。** 写入都在 `store.Update` 的事务里，对会话只有 `Tx.Append`；追加前过 `conversation.Check`，不能接就整个事务失败（`conversation.ErrRefused`）。
- **物化只为查询。** `turns`、`items`、`responses` 和 `threads` 的状态列在同一事务里写下，供列表、分页、调度和搜索查询。
- **派生行不在写路径上。** `usage` 由 `usage.Recorder` 从 `modelResponded` 补，`tasks` 是后台调用执行前的占位。
- **恢复不是另一条路径。** 运行开始时关掉上次已开始却没结果的调用，然后照常走；崩溃、关闭、[租约接管](/zh/engine/sharding#启动和接管)都走这一条。
- **表结构按编号 migration 升级**，能改列、重建表、迁移数据。见[设计决策 17](/zh/reference/decisions#_17-编号-migration)。

代价：每步都写库，一次追加要写日志、物化行和会话头部；所有读写排在一条连接上；开始后进程退出的调用和任务不自动重做；日志和用量行只增不减。数字见[性能基准](/zh/benchmarks/#容量)。

::: info 演进
早期条目是 `items` 里原地更新的行，崩溃后分不清没跑过和跑到一半。v0.16.0 把引擎重建为以日志为中心（`conversation`、`store`、`store/sqlite`），`ToolStarted` 把两种情况分开；表结构也从 gorm 的 `AutoMigrate` 换成编号的 SQL 步骤。
:::

## 对话日志

一条记录是 `conversation.Entry`：`Seq`（会话内位置，由 `Tx.Append` 分配）、`Turn`、`Item`（属于轮次本身的为空）、`At`（UTC）、`Body`。`Body` 是下表二十一种之一，类型名与 `EntryKind` 只差首字母大小写：

| `EntryKind` | 含义 |
|---|---|
| `turnQueued` | 轮次排上：模型、角色、定时任务 |
| `turnEnded` | 结束：`completed`/`failed`/`interrupted` 和原因 |
| `userMessage` | 用户消息、附件、插话、子 agent 的任务 |
| `agentMessage`、`reasoning` | 回答正文、思考 |
| `modelResponded` | 一次回答：用量、上下文统计、`Native`、是否压缩 |
| `modelFailed` | 模型调用失败 |
| `toolCall` | 调用：参数、注解、冻结的 `Prepared` |
| `approvalAsked`、`decided` | 要审批的原因与建议规则；审批决定和决定者 |
| `toolStarted`、`inputAsked`、`answered` | 开始执行；工具提问；回答或跳过提问 |
| `toolResult` | 结果、错误，或被拒绝 |
| `childLaunched`、`childReported` | 启动了子 agent 会话；它的报告回到轮次 |
| `taskLaunched`、`taskReported` | 交给后台任务（`Task` 是 `tasks` 行 id）；结果回到轮次 |
| `compacted` | 压缩：摘要和覆盖位置 `Through` |
| `recalled`、`notice` | 这一轮召回的记忆；运行时告诉模型的话 |

记录不修改、不单独删除，会话删除时整份日志一起删。`conversation.View` 是折叠结果：`Active` 是第一个未结束的轮次，`Queued` 是它后面的，`Waiting` 是它等审批、回答还是报告，`Runnable` 是它什么都不等，`Status` 是会话自己的状态，`RollUp` 再加上子 agent 对用户的等待（审批优先）。`agent.Next` 读它决定下一步；运行每一步读物化的三张表（`Reader.View`），不重新折叠 `entries`。

## 条目

条目是轮次里的一步。消息、思考、报告各由一条记录写成；工具调用从 `ToolCall` 开始，可能经过审批、`ToolStarted`、提问、`ChildLaunched`，到 `ToolResult` 或 `Answered` 结束。类型是 `userMessage`、`agentMessage`、`reasoning`、`toolCall`、`agentReport`（由 `ChildReported`、`TaskReported` 折叠）、`contextCompaction`、`memoryContext`、`error`、`notice`；状态是 `pending`（未开始或等审批）、`inProgress`（已开始或等回答）、`completed`、`failed`、`declined`（被拒绝、跳过提问，或轮次结束时未结束）。判断靠字段：`Item.WaitsForApproval`、`Item.WaitsForInput`、`Item.AwaitsReport`（`Child` 或 `Task` 非空且未报告）、`Item.Open`。

一次模型调用写一个 `ModelResponded`，带回答 id；`reasoning`、`agentMessage` 和各个 `toolCall` 都记着这个 id。用量和原始记录只在这里，每次调用只计一次：折叠时分到轮次，也写进 `responses`。压缩的调用同样写 `ModelResponded`（带 `Compaction`），和 `Compacted` 同一次提交。

**写入约束。** `conversation.Check` 是唯一守门人：记录要有 `Body`；`TurnQueued` 用新轮次 id，其余指向已有且未结束的轮次；后面的轮次只能追加 `UserMessage` 和 `TurnEnded`；还有调用未结束时不能 `TurnEnded`；`ChildReported`、`TaskReported` 要指向启动了子会话或任务、还没收到报告的调用。每一步都得接在当前状态之后：只有等审批的能 `Decided` 且决定要在选项里，只有等回答的能 `Answered`，只有 `inProgress` 的能 `ChildLaunched` 且只能一次，`ToolResult` 要未结束且不在等回答。参数和执行内容就是 `ToolCall` 记下的那份，不会被换掉，见[审批与权限](/zh/engine/permissions)。

## 一条写路径

`store.Store` 有 `Update(ctx, fn)`（写事务，`fn` 出错整个回滚）、`Read(ctx, fn)`（同一快照内读）、`Feed()`、`Fence(epoch)`（记下分片 epoch，之后每次写入核对，见[分片与租约](/zh/engine/sharding#围栏)）；`Tx` 是 `Reader` 加各项写方法和 `Append`。

`Tx.Append` 是日志的唯一写法：读会话视图（同事务内的后续追加用缓存视图），给每条记录分配 `Seq = Head + 1`、补时间、`Check`、`Apply`、插入 `entries`；把写到的轮次、条目、回答按折叠结果写入物化表，轮次刚结束时 `ended_seq` 取本次提交序号；更新 `threads` 的 `head`、`own_status`、`updated_at`、`replied_at`（顶层会话轮次结束）和 `runnable_since`；沿父会话向上重算 `status`（`conversation.RollUp`），哪层没变就停。一个事务可以跨会话：子 agent 的 `TurnEnded` 与父会话的 `ChildReported`，或建子会话、排首轮、`ChildLaunched` 与 `ToolResult`，都一次写下。

## 后台调用

带 `tool.BackgroundOptional` 的工具可以在参数里写 `background: true` 交给后台（`run_command`、`claude`），`BackgroundAlways` 总是如此；一组调用只有第一个能后台。

- `runTools` 交给 `launchTask`：一个事务里 `tx.CreateTask` 写 `tasks` 行，追加 `ToolStarted`、`TaskLaunched{Task}` 和带 `Started{Task, Note}` 的 `ToolResult`，Note 说明结果会作为报告回来。
- `tasks.call` 是冻结的调用，行有 `user_id`、`thread_id`、`turn_id`、`item_id`、`created_at`、`started_at`。后台调度器由 `host.New` 单独建（`schedule.Tasks`）：默认 32 槽位、每用户 4 个、单任务 1 小时，与轮次槽位分开，按 `created_at, id` 取。
- `Runner.Task` 先读行：`Started` 已有值说明上次进程在运行中退出，直接报 `strandedTask`；否则 `StartTask` 后执行，结束时 `ReportTask`。
- `ReportTask` 在一个事务里读行、`DeleteTask`、追加 `TaskReported{Launch, Task, Output, Error}`：报告沿用原轮次，`Launch` 指回调用，该调用标为已报告，`tasks` 行删除。`run.End` 对仍在等报告的后台调用用 `stoppedWithParent` 报错；运行被取消时先不报，下次启动判成 stranded。

## feed 与 seq

两种序号：每个会话的 `Seq`（`threads.head` 最新，条目 `seq`、`updated`、分页 `beforeSeq` 用它）；整个分片的提交计数在 `feed` 表，有事件的事务提交前加一，本次事件都带它。事件是 `Change`（会话的记录、折叠后的条目与轮次、会话头部，或已删除）、`Owned`（设置、工作区、执行环境、MCP、定时任务、待办、记忆的新值或删除）、`Delta`（流式增量，不落库、不带序号）。`Subscribe(user, fn)` 给网关连接，`SubscribeAll(fn)` 给调度器、记忆提取和用量记录。feed 只在内存里，错过的不重发：客户端连上后读一次会话，`thread/read` 和 `thread/resume` 返回读取时的提交序号，之后按它判断新旧，见[会话协议](/zh/integrate/protocol/threads)。

## 先落库再执行

| 时机 | 一次提交里追加 | 代码 |
|---|---|---|
| 收到消息 / 定时任务到点 | `TurnQueued` 和 `UserMessage`，`CronJob` 记着任务 | `app.Send`、`app.Scheduled` |
| 插话 | 当前轮次加 `UserMessage`；在等的审批记拒绝，提问记跳过 | `app.Steer` |
| 运行开始 | 上次被切断的调用：带错误的 `ToolResult` | `run.Runner.closeStranded` |
| 召回 / 压缩 / 叫停 | `Recalled`；`ModelResponded`（压缩）和 `Compacted`；`Notice` | `run.callModel`、`run.compact` |
| 模型回答结束 | `ModelResponded`、`Reasoning`、`AgentMessage` 和每个 `ToolCall`；要审批的加 `ApprovalAsked`，被拒绝或无法准备的加带错误的 `ToolResult` | `run.callModel`、`run.decide` |
| 执行之前 | 这组调用的 `ToolStarted`，提交后才调用；后台调用换成 `tasks` 行加 `TaskLaunched` | `run.runTools` |
| 工具结束 | `ToolResult` 或 `InputAsked`；子 agent 是建会话、排首轮、`ChildLaunched` 和 `ToolResult` | `run.recordResult`、`run.launch` |
| 剩下的调用被叫停 | `ToolResult`，错误是 `skipped: ` 加原因 | `run.skip` |
| 后台任务结束 / 审批 / 回答 | `TaskReported`；`Decided`、`Answered` | `run.ReportTask`、`app.Decide`、`app.Answer` |
| 一轮结束 | 先结束未报告的子 agent 和后台任务，再关掉未结束的调用，最后 `TurnEnded` | `run.End` |

除了增量，客户端、调度器和记忆提取看到的变化都已在库里。

## 崩溃恢复

重启没有单独的流程：调度器从 `threads.runnable_since` 读出可运行的会话，在等审批、回答、报告的会话不依赖进程。每次运行开始时 `closeStranded` 在当前轮次里找已开始、没有结果、也不在等回答的调用，各追加 `ToolResult`，错误是 `the call was cut off when the run that made it stopped; it may have taken effect in part or in full, so check before trying it again`。于是已 `ToolStarted` 的记为 `failed`，交给模型决定是否先核实再重试，绝不自动重跑；还没 `ToolStarted` 的照常判定和执行，已有的审批决定保留；已开始的后台任务由 `Runner.Task` 报成 stranded。在等回答的不动；流式输出没有记录，恢复后重新调用；回答已提交、轮次没结束的由 `agent.Next` 直接结束。子 agent 正在启动时，建会话和父调用的结果同一次提交，要么都有，要么都没有。

执行前一定先提交 `ToolStarted`，所以没有它的一定没跑过，有的可能已生效；引擎不会把一个调用执行两次。运行出错或超时，调度器让出槽位前用 `run.End` 把轮次记为 `failed`。租约接管走同一份日志，见[分片与租约](/zh/engine/sharding#启动和接管)。

## SQLite 配置

库文件在 `<home>/data/store.sqlite`，目录以 `0755` 创建；打开由 `pkg/sqlitedb` 负责，store 和分片目录库共用，驱动是 `gorm.io/driver/sqlite`（`mattn/go-sqlite3`）。DSN 设 `_journal_mode=WAL`、`_busy_timeout=5000` 毫秒、`_foreign_keys=on`、`_txlock=immediate`（每个事务一开始就拿写锁，多进程共用的目录库需要它）；连接池 `SetMaxOpenConns(1)`，时间取 UTC。一条连接让进程内访问串行。构建必须带 `-tags sqlite_fts5`，`store/sqlite/fts5.go` 在没有标签时引用不存在的符号，让编译失败。

## 表和关系

`entries` 是日志，`turns`、`items`、`responses` 和 `threads` 的状态列是它的物化。外键：`threads.user_id`、`tasks.user_id` 是 `RESTRICT`（引擎没有删除用户的操作）；`threads.workspace_id`、`threads.environment_id` 也是 `RESTRICT`（工作区只归档，执行环境无人使用才能删，预先由 `EnvironmentInUse` 报错）；`entries`、`turns`、`items`、`responses`、`cron_jobs`、`tasks`、`todos` 和 `threads.parent_id` 是 `CASCADE`，删会话会带走日志、物化行、定时任务、任务行和子会话；其余指向 `users` 的表也是 `CASCADE`；`usage` 没有外键。

| 表 | 主键与列 |
|---|---|
| `entries` | `(thread_id, seq)`：`turn_id`、`item_id`、`at`、`kind`、`body` |
| `threads` | `id`：`workspace_id`、`environment_id`、`parent_id`、`parent_item`、`role`、`head`、`own_status`、`status`、`runnable_since`、`archived_at`、`replied_at`、`read_at` |
| `turns` | `(thread_id, id)`：`ord`、`ended_seq`、`cron_job`、`body` |
| `items` | `(thread_id, id)`：`turn_id`、`seq`、`updated`、`kind`、`status`、`at`、`text`（只有消息写）、`body` |
| `responses` | `(thread_id, id)`：每次回答一行，客户端分页不读它 |
| `tasks` | `id`：后台调用，`user_id`、`thread_id`、`turn_id`、`item_id`、`call`、`created_at`、`started_at` |
| `usage` | `id`（`<会话>:<seq>`）：`user_id`、`workspace_id`、`turn_id`、`item_id`、`at`、`source`、`model`、四个 token 列 |
| `todos` | `(user_id, id)`：`title`、`workspace_id`、`thread_id`、`status`、`notes`、`result`、`created_at`、`updated_at`、`ended_at` |
| `items_search` | 虚拟表：FTS5 外部内容表，`trigram` 分词，内容来自 `items.text`，两个触发器维护；`items` 重建或 `VACUUM` 后 rowid 错位，必须重建，见[搜索](/zh/engine/search) |

单用户网关的 `users` 是 `default`，`Tx.EnsureUser` 不存在时一起建 `settings`（脱敏开、随机密钥、记忆开）和本机执行环境（`local`、`This computer`）。`settings` 有 `redaction`、`redaction_key`、`memory`、`learn`、`permissions`；`workspaces` 的 `(user_id, root)` 唯一，有 `settings`、`instructions`、`providers`、`kind`、`archived_at`（见[工作区](/zh/engine/workspace)）；`cron_jobs`、`memories`、`memory_state`、`environments`、`mcp_servers` 见[定时任务](/zh/engine/cron)、[记忆](/zh/engine/memory)。`feed`、`shard_epoch` 各一行。

索引：`threads_user_list`（`user_id, updated_at DESC, created_at DESC, id DESC`，只收顶层会话）、`threads_workspace`、`threads_environment`、`threads_parent`、`threads_runnable`、`turns_open`、`turns_ended`、`turns_cron_job`、`items_thread_seq`、`items_calls`（按 `json_extract(body, '$.Call.Tool')` 和 `thread_id`，只收 `toolCall`）、`responses_thread_seq`、`cron_jobs_due`、`memories_topic`、`tasks_queue`、`tasks_thread`、`usage_at`、`usage_user_at`、`entries_model_responded`（只收 `modelResponded`）、`todos_status`、`todos_thread`。

## 用量与待办

**`usage`** 每行来自一条 `modelResponded`，由 `usage.Recorder` 在后台补，写日志的路径不写它。`Recorder` 用 `SubscribeAll` 听 feed，只对含 `ModelResponded` 的提交记下会话，一次最多 256 个，满了置 `stale`、下一轮全库扫；`MissingUsage` 用 `LEFT JOIN usage` 找还没有行的条目，每次 256 条；`PutUsage` 是 `INSERT … ON CONFLICT(id) DO NOTHING`；写失败把会话放回队列、30 秒后重试。`source` 是 `response` 或 `compaction`。行从不删除，删会话后仍在并计入总量。`usage/query` 按天（带 `OffsetMinutes`）、工作区或模型汇总四个 token 列，见[用量协议](/zh/integrate/protocol/usage)。

**`todos`** 的 `AddTodo` 取该用户最大 id 加一；标题最多 200 字、备注 2000、结果 500，校验失败包 `app.ErrInvalidTodo`。进入 `done` 或 `dropped` 写 `ended_at`，离开时清空；关联会话把 `workspace_id` 设成该会话的工作区，不改状态。协议有 `todo/list`、`todo/add`、`todo/update`，通知 `todo/changed`，列表按 `ended_at IS NULL DESC, ended_at DESC, id` 排序、未结束的在前；四个状态见[待办协议](/zh/integrate/protocol/todos)，它在中枢里怎么用见[中枢](/zh/engine/hub)。hub 工作区先前的 `TODO.md` 与 `done/<年-月>.md` 由 `app.importTodos` 每进程每用户导入一次：表里已有待办就不导入，读文件上限 1 MiB、超时 1 分钟，读不出的行跳过，导入后把 `TODO.md` 改名为 `TODO.md.imported-<日期>`。

## Migration

文件在 `store/sqlite/migrations/NNNN_<what>.sql`，用 `go:embed` 打进二进制，`sqlite.Open` 时由 `pkg/sqlitedb` 的 `Migrate` 执行（分片目录库也用）。编号从 1 起、不能有空洞；版本在 `PRAGMA user_version`，高于本程序知道的步数就拒绝打开；只往前走。步骤运行时外键关闭，每步提交前 `PRAGMA foreign_key_check`，`user_version` 与步骤同一事务；每步重新读版本，别的进程执行过就跳过。

| 编号 | 文件 | 做什么 |
|---|---|---|
| 0001 | `0001_init.sql` | 初始结构（除后加的列）；`feed` 插入 `seq = 0` |
| 0002 | `0002_task_runs_and_waits.sql` | `turns` 加 `cron_job` 并回填、建 `turns_cron_job`，`threads` 加 `own_status` 并重算 `status` |
| 0003 | `0003_learn.sql` | `settings` 加 `learn`，默认开 |
| 0004 | `0004_tasks.sql` | 建 `tasks` 和两个索引 |
| 0005 | `0005_thread_roles.sql` | `threads` 加 `role`，从首轮回填子会话，重建 `threads_user_list` |
| 0006 | `0006_workspace_instructions_providers.sql` | `workspaces` 加 `instructions`、`providers` |
| 0007 | `0007_workspace_kinds.sql` | `workspaces` 加 `kind`，默认 `project` |
| 0008 | `0008_call_index.sql` | 加 `items_calls` |
| 0009 | `0009_todos.sql` | 建第一版 `todos`（`done_at`） |
| 0010 | `0010_drop_todos.sql` | 删掉 0009 的 `todos` |
| 0011 | `0011_usage.sql` | 建 `usage`、两个用量索引和 `entries_model_responded` |
| 0012 | `0012_todos.sql` | 重建 `todos`（`ended_at`）和两个索引 |
| 0013 | `0013_thread_list_index.sql` | 重建 `threads_user_list`，只收顶层会话 |
| 0014 | `0014_drop_delegate_threads.sql` | 删 delegate 会话及其日志、物化行、任务、定时任务；交给它们的待办解绑并回到 `open` |

`sqlite.Open` 只打开 `data/store.sqlite`，不读 v0.16.0 之前的 `data/ollupi.sqlite`：只有旧库的 home 打开后是空的。

## 附件存储

附件不进数据库。`UserMessage.Attachments` 只记类型、名字、MIME、大小、图片尺寸、token 估算和键，文件在 `<home>/attachments`，由 `blob.Dir` 读写。键是 `<会话 id>/<附件 id>.<扩展名>`，必须是 `filepath.IsLocal` 的相对路径；`Put` 以 `O_EXCL` 新建、不覆盖，目录 `0700`、文件 `0600`。`app.Send` 和 `app.Steer` 先存文件再提交消息，提交失败就删掉；删会话时事务提交后 `DeletePrefix`，删不掉返回 `the conversation is deleted, but not its attachments`。大小和类型限制见[扩展点](/zh/integrate/extend)。

## 边界与已知问题

- **写放大和单连接。** 每一步都写库，一次追加要写日志、物化行和会话头部，所有读写排一条连接；活跃会话一多，一轮就慢在等连接，见[性能基准](/zh/benchmarks/#容量)。
- **`entries` 只写不读。** 读视图走物化的三张表，没有代码从 `entries` 重新折叠；物化与日志一致靠同一事务里同一次 `Apply` 保证，没有校验。
- **被切断的调用和任务不自动重做**，只报“可能已部分或全部生效”；**流式文本会丢**，已推给界面的增量没落库。
- **feed 不持久化**：断开期间的事件不重发；几乎同时提交的两个事务，事件到达订阅者的先后不一定与提交序号一致，客户端按 `seq` 判断新旧。
- **行只增不减**：日志留到会话删除；`usage` 连会话删除后都留着，没有保留期。
- **migration 只能往前走**，被新版本升级过的库旧版本拒绝打开；它在 `sqlite.Open` 里执行，早于拿分片租约，见[分片与租约](/zh/engine/sharding#边界与已知问题)。
- **附件和消息不同事务**：文件先存、消息后提交，中间退出会留下无人引用的文件，直到会话删除才清掉。

## 代码位置

| 仓库 | 路径 | 职责 |
|---|---|---|
| ollupi | `conversation/entry.go`、`conversation/check.go`、`conversation/view.go` | 记录种类、`Check`、`View.Apply`、条目判断、`RollUp` |
| ollupi | `store/store.go`、`store/feed.go` | `Store`、`Reader`、`Tx`、事件与订阅、`Task`/`Usage`/`Todo` 端口 |
| ollupi | `store/sqlite/sqlite.go`、`conversations.go` | 打开库、`Update`、`Read`、`Fence`；`Append`、物化、提交序号、分页、任务行 |
| ollupi | `store/sqlite/owned.go` | 用户、设置、工作区、执行环境、MCP、定时任务、待办、搜索 |
| ollupi | `store/sqlite/usage.go`、`memories.go` | `MissingUsage`、`UsageBuckets`、`PutUsage`；记忆与提炼进度 |
| ollupi | `store/sqlite/migrations/`、`pkg/sqlitedb/sqlitedb.go` | 十四个编号 migration；打开 SQLite 并执行 |
| ollupi | `usage/usage.go`、`app/todos.go`、`app/todos_import.go` | `Recorder`；待办读写与旧文件导入 |
| ollupi | `run/run.go`、`run/tools.go`、`run/end.go` | `closeStranded`、`launchTask`、`Runner.Task`、`ReportTask`、轮次结束 |
| ollupi | `schedule/schedule.go`、`host/host.go` | 轮次与后台任务的队列、槽位、时限 |
| ollupi | `blob/blob.go`、`app/attachments.go` | 附件文件与存读删 |
