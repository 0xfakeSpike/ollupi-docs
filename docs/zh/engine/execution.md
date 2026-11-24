# 执行模型

用户轮次、子 agent 轮次、定时任务轮次共用一个执行池，名额叫槽位（slot），默认 32 个；带 `background: true` 的工具调用另有一个池。调度器（`schedule`）决定哪个会话（thread）占槽位，运行（`run`）在槽位里推进当前轮次。

![两张池子：上面是会话池，下面是后台调用的工具池](/images/execution-pool.svg)

## 为什么这样设计

- **槽位只给正在干活的会话。** 等待时让出槽位，只剩日志，不占 goroutine 也不占模型并发。见[性能基准](/zh/benchmarks/#内存)。
- **队列就是数据库。** 排队的是 `threads.runnable_since`，调度器内存里只有槽位表。见[设计决策 3](/zh/reference/decisions#_3-无内存调度状态)。
- **下一步从日志读出来。** 重启接手和平常运行走同一段 `agent.Next`。
- **两层并发分开算。** 槽位限会话，模型名额限在途请求。见[设计决策 4](/zh/reference/decisions#_4-两层并发)。
- **长调用可以离开本轮。** `background: true` 的调用写成 `tasks` 记录交给第二个调度器，结果以报告回到会话。
- **子 agent 与定时任务不走特殊路径。** 同池排队。见[设计决策 5](/zh/reference/decisions#_5-子-agent-即普通会话)。

## 调度器和槽位

`schedule.Scheduler` 在一个 goroutine 上运行（`Run`），内存里只有 `runs`（会话 → 槽位）和 `ofUser`（用户 → 槽位数）；一个会话同时只运行当前轮次，最多占一个槽位。

`Run` 等容量为 1 的 `wake` 通道：启动、会话变得可运行（`Change.Header.Runnable`）、放出槽位各发一个信号。每个信号调一次 `admit`：`Reader.Runnable` 读出 `runnable_since` 不为空的行，普通会话排在子 agent 之前、同类按可运行的时刻排，跳过已在运行、槽位已满、用户已到份额的，再 `Runner.Run(ctx, thread)`。

| `host.Config` | `schedule.New` 的参数 | 默认值 | 含义 |
|---|---|---|---|
| `Slots` | `slots` | 32 | 槽位总数 |
| `UserSlots` | `userSlots` | 等于 `Slots` | 一个用户最多占的槽位数，子 agent 算在用户头上 |
| `RunLimit` | `limit` | 4 小时 | 一次占槽位的最长时间，超过后这一轮失败 |

`runnable_since` 由 store 在追加时维护，可运行时保留原值。参见[容量规划](/zh/integrate/capacity)。

## 轮次状态机

轮次没有状态列：结束的由 `TurnEnded` 记着状态和原因；没结束的里日志第一个是当前轮次（`View.Active`），其余排队（`View.Queued`）。当前轮次在不在等看 `View.Waiting`，优先级是审批、回答、汇报：

| 当前轮次的条目 | 等什么 | 会话状态 | 可运行 |
|---|---|---|---|
| 有调用在等审批 | 用户的审批 | `waitingOnApproval` | 否 |
| 有调用在等回答 | 用户的回答 | `waitingOnUserInput` | 否 |
| 已回答，它启动的子 agent 或后台调用还没全部汇报 | 汇报 | `active` | 否 |
| 都不是 | 不等 | `active` | 是 |

等汇报只在已经回答之后才算，回答之前子 agent 和父轮次一起跑；`Item.AwaitsReport` 认的是带 `Child` 或 `Task`、`Reported` 仍为假的工具调用。

## 一次运行

`Runner.Run` 在槽位的 goroutine 上执行。开头 `closeStranded` 把当前轮次里已开始（`ToolStarted`）、没有结果、也没在等回答的调用追加带错误的 `ToolResult`，记为被切断。之后每一步 `load` 重读会话与设置，按 `TurnQueued.Role` 取角色，建窗口、脱敏器和权限判定器，再问 `agent.Next`：`Wait` 返回、`Finish` 结束这一轮。见[审批与权限](/zh/engine/permissions)。

返回后 `nil` 放出槽位；轮次已中断、会话已删除、进程关闭时都不写；超过 `RunLimit` 或出错时 `run.End(failed)`，原因是时限或错误文本。

## 循环的每一步

`agent.Next` 按顺序检查：

| 条件 | 动作 | `run` 做什么 |
|---|---|---|
| 没有当前轮次，或它在等审批、回答、汇报 | `Wait` | 返回，放出槽位 |
| 有 `pending` 调用，且工具使用已停止 | `SkipTools` | 每个调用追加 `ToolResult`，错误是 `skipped: ` 加停止原因 |
| 有 `pending` 调用 | `RunTools` | 执行，见下 |
| 已经回答 | `Finish` | `run.End(completed)` |
| 工具使用已停止 | `CallModel{NoTools, Notice}`；已告诉过模型则 `CallModel{NoTools}` | 先追加 `notice` 再调模型；已告知过就不给工具，直接再调一次 |
| 其他 | `CallModel` | 调模型 |

"已经回答"（`View.Answered`）是这一轮最近一次回答有正文、没有工具调用，之后也没有新消息或汇报，所以插话和报告让一轮继续。工具使用停止（`agent.stop`）的原因有四个：用户拒绝、调用数到上限、连续失败到上限、模型调用数到上限；停止后 `notice` 以 `[runtime] Tool use has stopped:` 开头写明原因，要求模型直接写回答，这次不给工具的调用仍要工具，这一轮就失败。

### 执行一组工具

调用在写进日志时就判定完了：`Prepare` 冻结执行计划，`Checker.Decide` 给出 `Deny`、`Ask`（追加 `ApprovalAsked`）或 `Run`，批准后不再重判，见[工具](/zh/engine/tools#一次调用的生命周期)。`RunTools` 从第一个 `pending` 调用起取一组可并行的（最多 8 个，`maxParallelCalls`，要求 `ReadOnlyHint`、不是 `Serial`、不在后台运行），追加 `ToolStarted`、并行 `Set.Invoke`（panic 变成失败结果），再把输出、`InputAsked` 或子会话一次写下；不可并行的单独执行。

### 后台调用

`run_command` 和 `claude` 声明了 `Background: tool.BackgroundOptional`，schema 里因此多一个布尔参数 `background`。第一个 `pending` 调用要后台时（`tool.Spec.InBackground`），`RunTools` 不取组，直接 `launchTask`：一个事务里建 `store.Task`（用户、会话、轮次、条目、调用与创建时间），并追加 `ToolStarted` → `TaskLaunched{Task}` → `ToolResult{Output: Started{Task, Note}}`。`Note` 说明它在后台运行、结束时以报告回到会话；本轮不等它，也不与别的调用并组或占本轮并发名额。

`tasks` 由第二个调度器（`schedule.Tasks`）执行，`TaskSlots` 默认 32、`UserTaskSlots` 默认 4、`TaskLimit` 默认 1 小时。执行前 `tx.StartTask` 记开始时间，超时记 `the task reached its time limit of …`；结束时 `run.ReportTask` 在同一事务里删掉这条 `Task`，并追加 `TaskReported{Launch, Task, Output, Error}`：新条目（新 item id），`Launch` 指回原调用，会话因此重新可运行。报告在提示词里是 `role=user` 的消息，头是 `[result of the run_command call <调用 ID>, run in the background: completed]`。进程在执行中被停掉时，任务下次被取出看到 `Started` 已有值，直接报告 `strandedTask`（可能已部分或全部生效，先核实）；当前轮次被中断时 `run.End` 对未汇报的后台调用 `ReportTask`，错误是 `stopped with the turn that launched it`。

### 运行次数上限

上限按角色分两档（`agent.Limits`）：

| 档 | 角色 | `MaxModelCalls` | `MaxToolCalls` | `MaxConsecutiveFailures` |
|---|---|---|---|---|
| `standard` | 三个主角色和其余子 agent | 200 | 400 | 10 |
| `deep` | `codebase-sub-agent`、`backend-sub-agent`、`research-sub-agent` | 400 | 1200 | 10 |

两个调用数是整个轮次的总数，从日志里数，让出槽位再回来时不清零。

主角色按模型的输入预算选：`agent.MainRole(limits.Input())` 在预算不足 `compactBelowTokens`（16384）时排 `compact-main-agent`，否则排 `full-main-agent`，两者都按 `standard` 限次；会话上存了 `Role`、或工作区是中枢时以它们为准（`hub-main-agent`）。

### 模型调用

`callModel` 需要时追加 `notice` 与记忆快照 `Recalled`，`Window.Build` 算出请求（超阈值先压缩），`send` 脱敏后调 `Chat`，最后把 `ModelResponded`、思考、正文和判定过的调用一次写下；空正文或 `finish_reason` 为 `length` 的回答被拒。见[上下文管理](/zh/engine/context)、[模型接入](/zh/engine/models#重试)。

## 让出槽位的条件

等模型名额、模型调用中、压缩、载入记忆、工具执行中、已启动子 agent 而这一轮还没回答，都占槽位；等审批、等回答、已回答等汇报、轮次结束就让出。让出就是 `Runner.Run` 返回，调度器删掉 `runs` 里的记录再 `admit` 一次；模型名额在 `Chat` 进来时取、返回时释放。

## 排队、插话和中断

- **排队**：会话有未结束的轮次时再 `turn/start`，`app.Send` 照样追加 `TurnQueued` 和 `UserMessage`，新轮次排在后面、返回 `queued`；最多排 20 个（`maxQueued`），满了返回 `threadBusy`。
- **插话**：`turn/steer` 必须带 `expectedTurnId`，对不上返回 `turnMismatch`，没有当前轮次返回 `noActiveTurn`；子会话接受插话。写入的 `UserMessage` 在下次调模型时带上；模型调用进行中写入的让这次回答作废——它连同其中的工具调用都不写进日志，下一步带新消息重新请求，在途请求不取消。等审批或等回答时代替用户的回答（`Decided{Decline}` 或 `Answered{Skipped}`），其余已允许的调用照常执行；等汇报时让它可运行。
- **中断**：`turn/interrupt` 走 `app.Interrupt`，`turnId` 对不上返回 `turnMismatch`，然后 `run.End(tx, id, conversation.Interrupted, "interrupted by the user")`：停掉这一轮启动的、还没汇报的子 agent 和后台调用，关掉没结束的调用（等回答的记为跳过，其余记为被拒绝），追加 `TurnEnded`，调度器随后取消运行的 `ctx`。

## 子 agent

子 agent 没有专门的运行机制：启动它是建一个普通会话、排一个普通轮次。工具由 `subagents` provider 一个角色一个，名字见表，参数是 `description`（1–80 字，子会话标题）和 `prompt`（最多 20000 字），标了只读，一次回答里的多个启动一起执行。

工具只返回要启动什么（`tool.Launch`），`run.launch` 在写结果的同一次提交里建子会话：`Parent`、`ParentItem` 指回父会话与调用，工作区、执行环境与 `Settings` 取启动它的会话（权限继承、之后各改各的），并追加 `TurnQueued`、任务消息、`ChildLaunched` 与 `Launched{Subagent, Description, Note}`。

子会话的轮次结束时 `run.End` 向父轮次追加 `ChildReported`，形成 `agentReport` 条目；父轮次写完回答后还有子 agent 没汇报就等汇报、让出槽位，全部汇报完才结束，见[性能基准](/zh/benchmarks/#混合负载与子-agent)。

八个角色的 provider 与限制都在 `agent/agent.go` 的 `roles` 表里，均 `Recalls: true`：

| 角色 | 可用的 provider | `Limits` |
|---|---|---|
| `general-sub-agent` | 除 `subagents`、`cron`、`hub` 以外的全部 | `standard` |
| `browser-sub-agent`、`design-sub-agent`、`frontend-sub-agent` | `workspace`、`browser`、`context`、`skills`、`plan` | `standard` |
| `codebase-sub-agent`、`backend-sub-agent`、`writing-sub-agent` | `workspace`、`context`、`skills`、`plan` | 前两个是 `deep`，`writing` 是 `standard` |
| `research-sub-agent` | `workspace`、`web`、`browser`、`context`、`skills`、`plan` | `deep` |

`browser` 子 agent 因此也能读写工作区的文件；它和其他子 agent 共用同一个浏览器，工具的说明要求一次只启动一个。

子 agent 的角色层没有 `subagents`、`cron`、`hub`，不能再派子 agent；`Role.Kind` 分 `main` 与 `reporting`，`agent.Launchable` 在没有非 `context` 工具可用时删掉同名工具。子会话之后和普通会话一样接受 `turn/start`、`turn/steer`，新开一轮沿用会话上的 `Role`；列表与搜索只看顶层会话（`parent_id IS NULL`）。要让工作在别的工作区里发生，用的是中枢的 `start_conversation`，见[中枢（hub）](/zh/engine/hub)。

## 定时任务与重启

定时任务到点时 `cron.Run`（每分钟查一次）在一个事务里调用 `app.Scheduled`，走和用户消息相同的 `queue`，`TurnQueued` 多记一个 `CronJob`；上一次的轮次还在排队时跳过。见[定时任务](/zh/engine/cron)。

重启没有单独的恢复流程：`admit` 从库里取出所有可运行的会话；`closeStranded` 把上一次已开始未结束的调用记为切断，`pending` 照常执行，`tasks` 里已开始的任务报告为 `strandedTask`。见[持久化与崩溃恢复](/zh/engine/persistence#崩溃恢复)。

## 错误处理与边界

模型调用失败追加 `ModelFailed`；读写库、取工具集、建权限判定器的错误让这一轮 `failed`；工具失败（含 panic）只算这个调用失败。

- **排在后面的轮次跟着前一个的位置。** `runnable_since` 不变，后面的轮次会紧接着拿回刚放出的槽位。
- **同类不轮转。** 先派出的子 agent 排在后来者前面，1000 个定时任务同时到期时子 agent 等第一次模型请求的 p99 是 62.3 s。
- **后台调用的输出不在本轮里。** 本轮只看到 `Started{task, note}`，结果以报告回到会话。

## 代码位置

| 仓库 | 路径 | 职责 |
|---|---|---|
| ollupi | `schedule/schedule.go`、`host/host.go` | 调度器 `Run`、`hear`、`admit`、`start`、`Tasks`；槽位与时限默认值、`Hub` 开关 |
| ollupi | `run/model.go`、`run/tools.go` | 模型调用与压缩；判定与执行调用、`launchTask`、`ReportTask`、`Runner.Task`、启动子 agent |
| ollupi | `store/sqlite/conversations.go` | `Runnable`、`runnable_since`、`tasks` 的读写（`0004_tasks.sql`） |
| ollupi | `run/run.go`、`run/end.go` | `Runner.Run`、`closeStranded`、`load`、`permit`；`End` 与子 agent、后台调用的汇报 |
| ollupi | `agent/agent.go`、`conversation/view.go` | 角色、`Limits`、`Next`、停止原因、`Launchable`；`Active`、`Waiting`、`AwaitsReport`、`Answered` |
| ollupi | `app/turns.go` | 发消息、插话、中断 |
| ollupi | `tool/builtin/subagent/subagent.go` | 子 agent 工具 |
| ollupi | `tool/builtin/workspace/execution.go` | `run_command`，后台可选 |
