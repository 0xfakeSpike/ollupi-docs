# 设计决策记录

这一页记录 Ollupi 为什么长成现在这样。每条决策用同一个结构：背景、决定、放弃的方案、代价、依据。只收录能从提交、代码或仓库文档找到依据的内容。"放弃的方案"只写确实存在过或文档里明确对比过的做法，找不到记录的直接写"没有记录"。

引用约定：

- 引擎（ollupi）的提交直接写哈希，如 `acfb8e4`。桌面端（ollupi-desktop）的提交写成 `desktop@729225b`。
- 已删除的文档写成"文件名（提交）"，表示在该提交里还能读到，如 `docs/deepening-directions.md`（`05ef4b0` 的父提交）。
- 引用的基准数字都来自 `bench/README.md`。这些数字是模拟模型和模拟工具跑出来的，在多用户、分片和沙箱接口改动之前测的，之后没有重测。

| # | 决策 | 一句话 |
|---|---|---|
| 1 | 池化 runtime | 一个进程承载所有会话，不按 agent 隔离 |
| 2 | SQLite 与先落库再执行 | 状态全在库里，调用分 `pending` 和 `inProgress` |
| 3 | 无内存调度状态 | 内存只留槽位占用表，等槽位的会话从库里读 |
| 4 | 两层并发 | 槽位限一轮，连接限模型调用 |
| 5 | 子 agent 即普通会话 | `Agent` 是普通工具，子 agent 走同一条路 |
| 6 | 定时任务即消息 | 到点调用和用户一样的入口 |
| 7 | 协议对齐 Codex app-server | WebSocket 上的 JSON-RPC，界面只是一个客户端 |
| 8 | 协议契约从分发表生成 | 分发表同时是 schema 的来源 |
| 9 | 工具只给模型用 | 界面走明确的方法，不直接调工具 |
| 10 | 单库即分片与租约 | 一个 SQLite 文件是一个分片，一个进程持有 |
| 11 | sidecar 形态 | Go 后端内嵌引擎，渲染进程直连网关 |
| 12 | 原生 Anthropic 与 Gemini 接口 | 回放服务商自己的消息记录 |
| 13 | 精简模式 | 输入预算小的模型用短提示词和少量工具 |
| 14 | 记忆快照与稳定前缀 | 每个会话一份快照，不逐轮召回 |
| 15 | 脱敏只在模型边界 | 库里存真实值，发给模型前才遮 |
| 16 | 审批绑定执行内容 | 批准的是冻结的内容，执行前再算一遍 |
| 17 | 编号 migration | 不再靠 AutoMigrate，不再清库 |
| 18 | 出错即暴露 | 不做隐藏问题的回退 |
| 19 | 逻辑放在拥有它的层 | 每个概念一个主人 |
| 20 | Seatbelt 沙箱 | 基于 Codex 的 profile，macOS 专用 |
| 21 | 自建更新器 | ad hoc 签名下 Squirrel.Mac 不可用 |

## 1. 池化 runtime

**背景**

第一个提交里，所有会话的一轮（turn）就共用一条全局队列，暂停的一轮不占 worker（`acfb8e4` 的 README）。当时的定位是"本地 AI agent 的核心"。`4c2e9d7` 把定位改成给云服务商构建大规模并发的个人 agent 服务，对照物随之变成"每个 agent 一个 VM 或容器"：进程要么一直常驻，要么冷启动重建，等用户时进程挂起还占着内存。

![逐个隔离与 Ollupi 的对比](/images/cli-vs-ollupi.svg)

**决定**

一个进程承载所有会话。一轮只有在运行时才占槽位（slot，`Config.Slots`，默认 32）。等用户、审批或子 agent 的一轮离开执行池，只剩数据库记录，不占 goroutine，也不占模型并发。

**放弃的方案**

一个 agent 一个 VM 或容器。`bench isolated` 是这条路的对照组：每个会话一个 Ollupi 进程，每个会话 20.0 MB，不含容器开销。池化下一个活跃会话约 160 KB，5 万个停放的会话一共增加约 14 MB 常驻内存。

**代价**

隔离不再来自进程边界，要由代码自己守住：

- 入口检查调用方是否拥有所指的东西，别人的东西一律当不存在（`28adb4d`）。
- 命令、文件和 MCP 服务器经 `sandbox.Box` 访问（`aecfb63`、`f1ff694`）。
- 一个用户的故障不能波及整个分片，这一条是单独补的（`fb3e2d1`）：附件在进入事件循环之前读写并设超时，panic 只让这一轮失败，MCP 调用有超时，一轮在槽位里最多跑 `RunLimit`（默认 4 小时）。

**依据**

`acfb8e4`、`fec6d4d`、`4c2e9d7`、`fb3e2d1`，`README.md`，`bench/README.md`。

## 2. SQLite 与先落库再执行

**背景**

初版 README 就写"运行时没有隐藏状态"：模型文本、推理、工具调用、审批、计划、提问与回答，都先落成一条条目（item）再执行（`acfb8e4`）。问题出在工具调用上。调用从模型回复记下开始就是 `inProgress`，一直到结果返回，崩溃后分不清没跑过和跑到一半，恢复时只能猜：把这一轮第一条未结束的调用标成可能已生效，哪怕它根本没开始（`b52bde4`）。

**决定**

全部状态放 SQLite，一个库一条连接（`SetMaxOpenConns(1)`），WAL 模式，`_busy_timeout=5000`。调用记下时是 `pending`，校验、准备、等审批都在这个状态里，真正执行之前才写成 `inProgress`（`agent/runtime/execute.go` 的 `runJobs`）。重启时 `RecoverItems` 按状态处理：

| 条目 | 重启后 |
|---|---|
| `pending` 的调用 | 不动，照常往下走，已做出的审批决定保留 |
| `inProgress` 的调用，没有 `Await` | 标成 `failed`，错误写明可能已生效，要先核对再重复 |
| `inProgress` 的调用，在等用户或子 agent 回答 | 不动，继续等 |
| 未完成的 `reasoning`、`agentMessage`、`contextCompaction` | 标成 `failed`，错误写明应用在它完成前停了 |

**放弃的方案**

恢复时按位置猜测哪条调用可能已生效（`b52bde4` 删除）。选 SQLite 而不是其他存储，没有记录。

**代价**

- 写放大：每一轮约 68 次读、15 次写，约 11.6 KB 磁盘（三次模型调用、两次工具调用）。
- 读写都排在一条连接上。4096 个活跃会话时每轮等连接约 43 ms，不足以解释这一轮慢下来的 3.9 s，瓶颈还没找到。
- 成本随历史增长：长跑实验里历史从 8 轮到 138 轮，每轮 CPU 从 12.1 ms 涨到 34.8 ms，主要花在编码带完整历史的请求和重读历史上。
- `inProgress` 的调用不会自动重做，生效与否交给模型和用户判断。`tools.Annotations` 有 `IdempotentHint` 字段，但运行时不读它。`docs/deepening-directions.md`（`05ef4b0` 的父提交）把幂等键和按副作用分类列为最值得做深的方向，代码里目前没有。

**依据**

`acfb8e4`、`b52bde4`，`repo/db.go`，`repo/items.go`，`agent/runtime/execute.go`，`bench/README.md`。

## 3. 无内存调度状态

**背景**

`e407f17` 加全局槽位时，把等槽位的会话放进一个内存队列，只存会话和一轮的 ID。同一天 `021777e` 发现这份队列缓存的是数据库本来就能回答的问题，还要维护：`reconcile` 要查重，一轮结束要摘除。

**决定**

内存里只留 `slotByThread`，以及从它派生的每用户计数 `slotsOfUser`。理由写在 `021777e` 里：一个 goroutine 正在运行这件事只有进程知道。`05ef4b0` 之前的 README 补了一句：放进库里反而会留下没人释放的锁。README 现在说"no scheduling state lives in memory"，指的是这张表之外没有别的，而这张表随进程消失，不需要恢复。

其余一律从库里读：

- `reconcile(threadID)` 是唯一决定一个会话能否前进的函数，幂等。
- `admit` 在每个事件之后运行，按空闲槽位数查 `turns_ready` 索引，对候选逐个调 `reconcile`。
- 事件由一个循环串行处理（`agent/loop.go`），调度状态不需要锁。
- 启动时 `recover` 先关掉被中断的条目，再走同一套 `reconcile` 和 `admit`，没有另一条恢复路径。

**放弃的方案**

| 方案 | 加入 | 移除 | 移除时的说法 |
|---|---|---|---|
| 全局互斥锁加条件变量 | 早期 | `bca8b52` | 调度事件改成单一消费者 |
| 四个常驻 worker 和运行队列 | `acfb8e4` | `64f8593` | worker 数的是整个 step，长工具卡住所有会话 |
| 内存等待队列 | `e407f17` | `021777e` | 库已经能回答，还要维护 |
| 每分钟全量 reconcile 自愈 | `99ddde4` | `3593427` | 见第 18 条 |

**代价**

每个事件之后都要读库。`5a91c47` 之前，等待中的一轮也是 `inProgress`，每个事件都重新扫一遍它们，于是拆出 `ready` 和三个 `waitingOn*` 状态，`admit` 只读就绪的。事件循环里有数据库读写，所以循环里的任何慢操作都会卡住所有会话：`fb3e2d1` 为此把附件读写移出循环。

**依据**

`021777e`、`6fe9fcd`、`bca8b52`、`5a91c47`，`agent/loop.go`，`agent/schedule.go`，`repo/turns.go`。

## 4. 两层并发

**背景**

早期的 4 个 worker 数的是整个 step，agent 的时间又主要花在等模型上，于是 4 个长工具就能卡住所有会话（`64f8593`）。去掉 worker 池之后又没有任何上限：一轮派出几百个子 agent，就起几百个 goroutine，每个都把会话留在内存里等模型名额（`e407f17`）。

**决定**

上限分开算，互不代替：

| 上限 | 限什么 | 默认值 | 位置 |
|---|---|---|---|
| 模型并发 | 每个连接同时在途的模型请求，工具不占 | 4（`llm.DefaultCalls`） | `pkg/llm/connection.go` |
| 槽位 | 同时运行的一轮 | 32（`defaultSlots`） | `agent/agent.go` |
| 用户槽位 | 单个用户可占的槽位 | 等于 `Slots` | `Config.UserSlots` |

一轮拿到槽位后一直跑，直到必须等待或给出最终回答（`ed426d6`）。两次模型调用之间重新读这一轮的条目和权限，插话和权限改动在下一次模型调用时生效。

**放弃的方案**

- 按 step 计数的 worker 池（`64f8593`）。
- 每次模型调用后让出执行权。这个让出来自四 worker 时代，当时是为了让别的会话进来，worker 池没了之后只剩成本：多一个概念，每次模型调用重建一次 Runtime，读一次整个会话（`ed426d6`）。

**代价**

- 跑长工具的一轮一直占着槽位。
- 重试期间调用继续占着槽位和模型名额（`a7bf0b2`）。
- 桌面端每个模型是一个独立连接，有自己的 `calls`（`desktop@ccc2bb8`），同一账号下多个模型的总并发是各模型之和。

**依据**

`64f8593`、`e407f17`、`ed426d6`、`585809f`、`a7bf0b2`，`pkg/llm/connection.go`，`agent/agent.go`。

## 5. 子 agent 即普通会话

**背景**

第一版就是这个思路：`Agent` 工具调用暂停父会话的这一轮，为每个调用开一个独立的子 agent 会话（`acfb8e4` 的 README）。README 的对比表把"特殊机制或子进程"列为另一种做法。

**决定**

`Agent` 是普通工具，它的结果是"由另一个 agent 回答"（`tools.Awaiting(tools.AwaitAgent, c)`）。`settle` 为每个这样的调用建一个 `ThreadRow`，填上 `ParentThreadID` 和 `ParentItemID`，把任务作为第一轮提交。之后子 agent 和普通会话走同一条路：同样的表、同样的 `reconcile`、同样的 `turns_ready`。子 agent 结束后，父会话的 `reconcile` 把它的最终回答写成那条调用的结果。

和普通会话的区别只有这些：

- 槽位不够时排在普通会话后面（`ReadyThreads` 的 `ORDER BY threads.parent_thread_id IS NOT NULL`）。
- 不收用户输入（`ErrSubagentThread`）。
- 权限沿用父会话，再多一层禁止 `Agent`，所以不能再派生子 agent。

**放弃的方案**

子 agent 结果的单独写入路径 `EndSubagentTurn` 及其事务。`d7a26a7` 改成从子会话最后一轮推导报告，只留一条写路径；子 agent 结束和父写入之间崩溃，由下一次 `reconcile` 补上。

**代价**

- 子 agent 不继承父对话，任务描述要自带全部信息（工具描述写明了这一点）。
- 同类按一轮的开始时间排队，不轮转。一轮派出的一批子 agent，会排在后来者派出的子 agent 前面。混合负载实验里，子 agent 等待的 p99 是 4.6 s。

**依据**

`acfb8e4`、`d7a26a7`、`28b9033`，`tools/subagent/subagent.go`，`agent/subagents.go`，`agent/scope.go`，`repo/turns.go`。

## 6. 定时任务即消息

**背景**

早期定时任务是 agent 的一部分：`agent/cron.go`，事件循环里有一个定时分支，`settle` 还要负责发送到期的任务（`99ddde4`、`bca8b52`）。

**决定**

`ee7776c` 把定时任务的知识全部移出 agent。`tools/cron` 自己每分钟检查一次，到点调用应用传入的 `send`，`send` 走的是和用户消息相同的路径（现在是 `Agent.StartScheduledTurn`，内部调 `startTurn`）。效果和用户发了一条消息一样：会话空闲就开一轮，忙就排队。一轮上的 `cron_job_id` 让界面能标出来源。同一个任务上一次还在排队时，这次跳过。

**放弃的方案**

- 定时分支放在 agent 事件循环里（`ee7776c` 删除）。
- 外部 cron 启动进程。这是 README 对比表里的另一种做法，项目没有用过。

**代价**

- `sendDue` 先发送，再记录运行。两步之间崩溃，重启后会再发一次。`ee7776c` 把它记为已知问题，代码顺序至今如此。
- 检查粒度是一分钟。
- 大量任务同时到点时，它们和用户消息在同一个队列里排队。混合负载实验里 1000 个任务同时到点，高峰期到达的一轮等第一次模型请求的 p50 是 44.1 s，高峰 59.4 s 排空。
- cron 表达式没有年份，"只跑一次"用写明日期的表达式加 `times: 1`，所以最后一次运行在近一年之后时，拒绝创建或恢复（`8f1d5e2`）。

**依据**

`ee7776c`、`8f1d5e2`，`tools/cron/cron.go`，`agent/turns.go`，`bench/README.md`。

## 7. 协议对齐 Codex app-server

**背景**

第一个提交的网关就写明对齐 Codex app-server（`acfb8e4`）。桌面端第一版 README 给的选型理由是："现成、有鉴权，和 Codex app-server 同构；UI 只是网关的一个客户端"（`desktop@729225b`）。桌面端的形态也对标 Codex 和 Claude 桌面端。

**决定**

WebSocket 上的 JSON-RPC 2.0，方法名按 `thread/*`、`turn/*`、`item/*` 分层：`turn/start`、`turn/steer`、`turn/interrupt`，通知 `item/started`、`item/completed`，服务端请求 `item/toolCall/requestApproval` 和 `item/tool/requestUserInput`。Ollupi 自己的能力加在同样的命名方式下：`workspace/*`、`cron/*`、`memory/*`、`settings/*`、`search`。

连接模型改过一次：先是一个进程服务一个窗口，新连接顶掉旧连接（`9580752`）；多用户之后变成每个用户一条连接，新连接只顶掉本人的（`15a76c7`）。

**放弃的方案**

没有记录。

**代价**

提交里没有记录。从代码看，网关不依赖 Codex 的任何实现，对齐只到命名和分层，契约以 `gateway/protocol.schema.json` 为准。

**依据**

`acfb8e4`、`9580752`、`15a76c7`，`desktop@729225b`，`gateway/protocol.go`。

## 8. 协议契约从分发表生成

**背景**

桌面端要知道网关的全部消息。第一版在 `packages/protocol` 里手写类型（`desktop@729225b`）。第二版 `sidecar/cmd/protogen` 解析 ollupi 的 Go 源码生成 TS（`desktop@3821b99`），但界面仍然在解析 Go。

**决定**

网关用一张表声明所有消息：客户端方法及其参数、结果和处理函数，服务端通知，服务端请求，错误名。`Call` 从这张表分发，`go generate` 从同一张表写出 `gateway/protocol.schema.json`，`initialize` 报告它的 sha256（`0bbbe5e`）。桌面端从这个文件生成类型、方法表和校验器（`desktop@94bc7d2`）。两边都做真实流量校验：引擎用假模型跑一遍完整会话，按契约校验每条消息；桌面端录一段真实 sidecar 的会话（`fixtures/session.json`），按消息校验，再把通知回放一遍，结果要和 `thread/read` 一致。

**放弃的方案**

- 手写 `wire.ts`（`desktop@94bc7d2` 删除）。
- 用 Go 生成器解析 ollupi 源码（`desktop@94bc7d2` 删除 `sidecar/cmd/protogen`）。

**代价**

- 每次协议变动都要重新生成并重录 fixture，桌面端提交里反复出现这一步。
- 生成物也会出错：字符串有了长度约束后，ajv 生成的校验器带上 `require()`，渲染进程启动时就停了（`desktop@62b8c69`），现在长度函数内联，再出现 `require` 就让生成失败。

**依据**

`0bbbe5e`，`desktop@3821b99`、`desktop@94bc7d2`、`desktop@62b8c69`，`gateway/protocol.go`，`gateway/traffic_test.go`。

## 9. 工具只给模型用

**背景**

早期有 `tool/call`，界面可以直接调模型的工具。这把界面绑在写给模型看的工具输出上，还让工具层多了一个跳过权限、又拒绝本地和等待型工具的直调模式（`38c5a1c`）。

**决定**

删掉 `tool/call`、`Agent.CallTool` 和 `Registry.Call`。界面要做的事走明确的方法，比如 `cron/list`、`cron/create`，返回类型化的行。契约只给用户参与、界面专门显示的工具定类型（`0ae03bb`、`docs/ollupi-tool-contract.md`），其余工具调用按通用样式显示，它们的输出可以随时为模型调整。

**放弃的方案**

- 界面直接调用工具（`38c5a1c` 删除）。
- 把定时任务工具和 `memory_search` 也写进契约：`f21b104` 写进去，同一天的 `0ae03bb` 拿掉，桌面端需求文档也跟着收窄（`desktop@e0cb3c1`、`desktop@f6bd358`）。

**代价**

每个界面操作都要有一个专门的方法，桌面端不能依赖通用工具的输出结构。

**依据**

`38c5a1c`、`f21b104`、`0ae03bb`，`desktop@f6bd358`，`docs/ollupi-tool-contract.md`。

## 10. 单库即分片与租约

**背景**

`v0.9.0` 之前，一个数据库只属于一个使用者，网关只有一个令牌。`4c2e9d7` 把定位改成云服务之后，`v0.9.0` 引入了多用户。

**决定**

一个数据库是一个分片（shard），分片内的用户共用表（`28adb4d`，迁移 `0005_users`）：

| 机制 | 做法 |
|---|---|
| 归属 | 工作区、会话、记忆带 `user_id`，一轮、条目、定时任务经会话找到用户；设置和记忆游标每用户一行 |
| 持有 | `shard_lease` 只有一行（`CHECK (id = 1)`），`ClaimShard` 抢占或续租，每 `Lease / 3` 续一次 |
| 接管 | 备用进程等待租约释放或过期，然后按重启恢复 |
| 防旧主 | `Fence` 之后每个 `DB.Tx` 先核对租约持有者，不是自己就返回 `ErrShardLost` |
| 路由 | `gateway.Router` 无状态，认证后按 `repo.Catalog` 转发；`Catalog` 是单独的一个库 |
| 放置 | 新用户放到接受新用户的分片里人最少的一个；`OnShard` 让分片拒绝放在别处的用户 |

不设 `Lease` 时什么都不变，进程相信自己是唯一的（`cd8faee`）。桌面端就是这样，只有默认用户（`desktop@8356c82`）。

**放弃的方案**

没有记录。

**代价**

- 容量靠分片数堆，单个分片仍是一个 SQLite 文件和一条连接。
- 用户不能跨分片迁移：`repo/catalog.go` 写明有数据的用户留在原分片，这里不做搬行。
- 进程崩溃没释放租约时，接管要等租约过期。
- 备用进程要能打开同一个数据库文件。
- `Fence` 的检查在 `DB.Tx` 入口，每个事务多一次读；不走事务的单条写入（如 `Launch`）不经过它。
- `Catalog` 还在用 `AutoMigrate`，不走第 17 条的编号 migration。
- 这些改动之后基准没有重测（`d85f978`）。

**依据**

`28adb4d`、`15a76c7`、`585809f`、`cd8faee`、`583d20c`，`repo/shard.go`，`repo/catalog.go`，`agent/lease.go`，`gateway/router.go`。

## 11. sidecar 形态

**背景**

ollupi 是 Go 库，不是可执行程序，应用自己负责装配。桌面端的界面用 Electron（`desktop@729225b`）。

**决定**

`ollupid` 是一个 Go 进程，直接 import ollupi，在回环端口上提供网关。第一版 README 的理由是："agent、SQLite、沙箱都在本进程内，不需要再包一层"。

- 主进程启动它，令牌放在环境变量 `OLLUPI_GATEWAY_TOKEN` 里（不放 argv，别的用户能读到），从 stdout 读一行握手：`ready` 带网关地址，`fatal` 带原因。
- 渲染进程直接连网关。主进程不转发协议消息，只管进程和原生能力。
- 主进程独占 `config.yaml`。改配置先写候选文件，用 `ollupid --check-config` 按真实启动的流程校验，通过才替换并重启后端（`desktop@690ec3a`）。技能同理，用 `--check-skills`（`desktop@9d876a9`）。
- 引擎依赖从 `replace ../../ollupi` 改成带版本的模块（`desktop@68ecb2f`），克隆下来就能构建，发版也基于确定的引擎。

**放弃的方案**

浏览器工具做成主进程上的 MCP 服务器（`desktop@cce4633`）。同一天 `desktop@090f9f7` 把它改成 sidecar 里的工具提供方：调用带着会话，每个会话能有自己的标签页，权限内容能写成网页的主机名。

**代价**

- ollupi 只在启动时读一次配置，所以任何配置改动都要重启后端。
- 本地 `go.work` 曾让发版构建用上未发布的引擎：`0.7.8` 带着一个界面没有对应契约的 ollupi 发了出去（`desktop@eb2b8e1`），之后发版构建用 `GOWORK=off`。
- 界面和后端可能版本不一致，所以 `initialize` 报告契约摘要，不一致时界面出提示（`desktop@94bc7d2`）。

**依据**

`desktop@729225b`、`desktop@690ec3a`、`desktop@68ecb2f`、`desktop@090f9f7`、`desktop@eb2b8e1`，`sidecar/cmd/ollupid/main.go`，`sidecar/internal/handshake/handshake.go`，`apps/desktop/src/main/backend/supervisor.ts`。

## 12. 原生 Anthropic 与 Gemini 接口

**背景**

初版只有 OpenAI 兼容的 Chat Completions 客户端（`acfb8e4` 的 README）。思考内容的签名要原样送回，这是服务商自己的格式（`9ac61ec`）。

**决定**

`pkg/llm` 在 `NewOpenAI` 旁边加 `NewAnthropic` 和 `NewGemini`，agent 接受任何 `llm.Client`。每次回复保留一份服务商自己的消息（`ChatMessage.Native`），下一次请求发给同一服务商时回放，这样 Anthropic 的 thinking 签名和 Gemini 的 thought 签名能送回去。Anthropic 的 thinking 块绑定它之前的内容，前缀一变，变化之前的块就不再回放。

**放弃的方案**

没有记录。

**代价**

- `items` 多一个 `native` 列，体积大。会话分页和搜索跳过它（`701ac2a`），`0003_rebuild_turns_items` 把它放到最后。
- 三个客户端的行为要各自对齐。重试就是例子：OpenAI 和 Anthropic 的 SDK 只重试两次，Gemini 不重试，`a7bf0b2` 才统一成 8 次。
- Anthropic 和 Gemini 要声明回答上限，这个值要放得下 prompt，所以 `ChatRequest` 带上调用方估算的输入（`8d77f0c`）。
- `config.yaml` 里每个提供方都必须写 `type`（`desktop@dfb69ba`）。

**依据**

`9ac61ec`、`a7bf0b2`、`8d77f0c`，`pkg/llm/chat.go`，`pkg/llm/anthropic.go`，`pkg/llm/gemini.go`。

## 13. 精简模式

**背景**

完整的提示词和工具列表约 8k token。窗口小的模型起不来，而且启动时的 `checkPromptFits` 会检查每个模型，一个这样的模型就让整个 agent 停下（`f1382d1`）。

**决定**

输入预算不足 16384 token（`compactInputTokens`）的模型用精简版：`compactRules` 代替 `loopRules`，不列技能，只发 `read_file`、`run_command`、`load_tools`。其余工具走已有的延迟加载（`f195793`），只在 `DEFERRED TOOLS` 里列名字，用到时加载。

16384 这个门槛的来历写在常量注释里：完整内容约 8k，`Fits` 只允许系统提示词和工具定义占输入预算的一半（`fixedPercent = 50`）。

**放弃的方案**

没有记录。

**代价**

- 两份规则要一起维护。
- 模型一开始看不到大部分工具，用之前要多一次 `load_tools`，技能也看不到。

**依据**

`f1382d1`、`f195793`，`agent/contextmanager/manager.go`，`agent/systemprompt/systemprompt.go`，`agent/runtime/runtime.go`。

## 14. 记忆快照与稳定前缀

**背景**

记忆最早在每次迭代时召回。三步走到现在：

| 提交 | 改动 | 原因 |
|---|---|---|
| `635fdc3` | 只在一轮的第一次模型调用前召回 | 一轮内的 prompt 前缀保持稳定 |
| `6f94607` | 上一轮的 `memoryContext` 留在原位 | 丢掉它等于从上一轮起点重写 prompt，每轮都丢掉服务商的前缀缓存 |
| `db21f76` | 改成每个会话一份快照，压缩后刷新 | 召回不再堆积，压缩丢掉它们时也不会丢内容 |

**决定**

会话开始时载入一份快照：全局记忆和本范围记忆各占一半预算，按类型和新旧排序。放不下的由只读的 `memory_search` 查。同样的考虑贯穿 prompt 的其他部分：

- 系统提示词从最稳定到最不稳定排列，其他会话和子 agent 能共用更多缓存前缀（`98ff53f`）。
- 放不下时只缩最近一次模型回复的工具结果预算，更早的结果保持原样（`6f94607`）。
- 延迟加载的工具排在后面，工具列表只增不减（`f195793`）。

**放弃的方案**

每次迭代召回、每轮召回（`635fdc3`、`db21f76` 依次替换）。

**代价**

- 会话进行中新提炼的记忆，要到下一次压缩才进 prompt。
- 放不下快照的记忆要靠模型主动搜。

**依据**

`635fdc3`、`6f94607`、`db21f76`、`98ff53f`，`agent/memory/recall.go`，`agent/systemprompt/systemprompt.go`。

## 15. 脱敏只在模型边界

**背景**

第一版就是在模型边界统一脱敏（`acfb8e4`）。但记忆提取的请求曾把原始个人数据发出去（`31f9092` 修复），记忆另有一道自己的凭据过滤（`831b554` 删除）。

**决定**

脱敏只发生在发给模型的那一刻，回答在记录和交给工具之前还原。记忆只经模型调用到达模型，所以记忆本身可以存真实值，不再有单独的凭据过滤（`831b554`）。用户可以开关，默认开，运行时在每次模型调用前读这个开关（`2d7d064`）。占位符是 HMAC，密钥存在 `settings.redaction_key`，每用户一个，重启后占位符不变。

**放弃的方案**

- 记忆自己的凭据过滤（`831b554` 删除）。
- 进程启动时随机生成密钥（`e36dd28` 引入，`9ac61ec` 改成持久化，这样占位符在重启后保持一致）。

**代价**

- 数据库里是明文。
- 每次模型调用都要过一遍检测器。`bd16658` 让每轮的 `Redactor` 记住处理过的文本，同一段文本一轮只搜一次。
- 截断可能切开一个敏感值，留下脱敏认不出的半截。`31f9092` 加 `redact.Spans`，截断点要避开敏感区间。

**依据**

`acfb8e4`、`31f9092`、`e36dd28`、`2d7d064`、`831b554`、`9ac61ec`、`bd16658`，`pkg/redact/redact.go`，`repo/users.go`。

## 16. 审批绑定执行内容

**背景**

初版审批前冻结目录、命令和环境变量，批准后按冻结内容执行（`acfb8e4`）。这只防止命令被改。等审批期间环境也可能变：浏览器点击要作用的标签页可能已经跳到别的网站（`0f981f8`），要写的文件可能被改过（`9ac61ec`）。

**决定**

批准之后、执行之前，把调用的内容重新算一遍。内容变了就不执行，按新内容重新决定：再问一次、被规则拒绝，或者规则允许就跑。算不出来的直接拒绝。文件修改审批的是冻结的 diff。`acceptAlways` 只在有建议规则时提供，看不清的命令、跑出沙箱的调用不提供（`5ac0e03`）。

**放弃的方案**

批准后只按冻结内容执行，不再核对（`0f981f8` 替换）。

**代价**

内容变了的调用要重新决定，用户可能要再回答一次。工具要在 `tools.Spec` 上提供 `PermissionContent`，从会话上下文算出调用实际会做什么。

**依据**

`5ac0e03`、`0f981f8`、`9ac61ec`，`agent/runtime/calls.go`，`tools/spec.go`，`tools/workspace/files.go`，`sidecar/internal/browser/browser.go`。

## 17. 编号 migration

**背景**

最早靠 gorm 的 `AutoMigrate`。它只能加表加列，做不到的改动就要清库。`3593427`、`9580752`、`28b9033` 的提交信息都写着"rebuild development databases"，`b967d0e` 写着 repo 没有 schema 版本，格式变了就重建，`0166926` 写着现有数据库必须重建。`a885647` 的理由很直接：库里现在存的是用户的对话和记忆。

**决定**

表结构按步骤变：`repo/migrations/NNNN_<what>.sql`，每步只跑一次，按序，各自一个事务，已跑的步数记在 `PRAGMA user_version`。

- `0001_init.sql` 是当时 gorm 建出来的结构。迁移之前的库先用 `AutoMigrate` 补到这一步，保留数据，标记为版本 1。
- 库的版本比当前 ollupi 知道的新，拒绝打开。
- 只往前走。
- 迁移时关外键，这样一步可以重建被别的表引用的表而不触发级联删除；提交之前检查所有外键（`d1c6092`）。
- 测试比较迁移出来的库和 gorm 从行类型建出来的库，改了行类型不写 migration 就失败。

**放弃的方案**

`AutoMigrate` 加清库（`a885647` 替换）。

**代价**

结构有两份事实：行类型和 migration，靠测试保持一致。步骤不可回退。

**依据**

`a885647`、`d1c6092`，`repo/migrate.go`，`repo/migrate_test.go`，`repo/migrations/`。

## 18. 出错即暴露

**背景**

规则从第一个提交起就在 `.cursor/rules/coding-rules.mdc` 里：不写隐藏 bug 的回退，不吞错误，出错不返回默认值，不确定就报错，只在系统边界校验输入。

**决定**

| 情况 | 行为 | 提交 |
|---|---|---|
| 调度时读库失败、会话无法前进 | `halt` 让这一轮以失败结束，写明原因 | `3593427` |
| 结束一轮时存储失败、子 agent 报告送不到 | 发 `EventError`，不假装结束 | `28b9033` |
| 工作区或父会话设置读不出来 | 这一轮失败 | `28b9033` |
| 模型没声明上下文限额 | 启动报错，不按名字猜 | `cd0efe2` |
| `${NAME}` 引用的环境变量没设置 | 拒绝配置 | `desktop@9131f39` |
| 库的版本比引擎新 | 拒绝打开 | `a885647` |
| 书签或历史文件读不出来 | 不当成空文件，否则下次保存就覆盖了 | `desktop@4748a86` |
| 待处理请求读库失败 | 报错，不返回空列表 | `fb3e2d1` |

外部的暂时故障单独处理，它们有明确的边界：模型请求重试 8 次，仍失败就让这一轮失败（`a7bf0b2`）；MCP 服务器连不上就跳过，并在状态里报告原因（`0fb4289`）；记忆提取退避重试，多次失败后跳过这一批并记下原因（`3cc5749`）。

**放弃的方案**

- 每分钟全量 `reconcile` 自愈错过的状态转换。`99ddde4` 加上，同一天的 `3593427` 删掉，改成当场失败。
- 内置的常见模型限额表（`cd0efe2` 删除）。

**代价**

- 一次读库失败就结束一轮，没有后台修复。
- 用户要自己填模型限额。API 不给限额时表单存不了，`desktop@4660809` 改成界面填默认值并写进 `config.yaml`，所以这个值是看得见、能改的，引擎这边的规则没变。

**依据**

`.cursor/rules/coding-rules.mdc`，`3593427`、`28b9033`、`cd0efe2`，`desktop@4748a86`、`desktop@4660809`。

## 19. 逻辑放在拥有它的层

**背景**

`eedc2c8` 的标题是"Give each core concept a single owner"，之前工作区操作写在网关里，一轮和条目的状态转换写在 agent 里。`701ac2a` 又做了一次：网关在调用后补发通知，有一份定时任务校验的副本。`docs/roadmap.md` 把原则写明了："逻辑放在拥有它的那一层，desktop 只做展示和装配"。

**决定**

| 层 | 拥有 | 不做 |
|---|---|---|
| `repo` | 会话状态机：一轮和条目的转换及其约束 | |
| `agent` | 调度、权限解析、发出每一次变化 | 不管传输形状和响应大小（`c8cede9`） |
| `gateway` | 编解码、认证、分页的字节预算 | 不补通知，不复制校验（`701ac2a`） |
| `tools/*` | 自己的校验，如 `cron.ErrInvalidJob` | |
| sidecar | 装配，以及引擎不认识的东西（浏览器工具、飞书） | 不改 ollupi |
| 桌面端 | 展示、原生能力、`config.yaml` | 不推导引擎已有的事实 |

桌面端的例子：会话预览和更新时间最早在客户端猜，`dfe7766` 让通知带上存储后的会话行，`desktop@d19f40d` 删掉推导。配置能不能启动，由后端自己的 `--check-config` 判断，界面不做第二份校验。

**放弃的方案**

- 网关里的工作区逻辑（`eedc2c8` 移到 agent）。
- 网关补发通知、复制定时任务校验（`701ac2a` 删除）。
- 客户端推导预览和 `updatedAt`（`desktop@d19f40d` 删除）。

**代价**

界面的新能力常常要等引擎先发版。桌面端有 12 个"Run on ollupi vX"提交，专门把 sidecar 升到新引擎并重新生成契约。开发时靠本地 `go.work` 指向未发布的引擎，这也是第 11 条里 `0.7.8` 事故的来源。

**依据**

`eedc2c8`、`c8cede9`、`701ac2a`、`dfe7766`，`desktop@d19f40d`，`docs/roadmap.md`。

## 20. Seatbelt 沙箱

**背景**

agent 的命令在用户本机运行。`docs/sandbox-sources.md`（`05ef4b0` 的父提交）是 2026-10-14 的调研，整理了 Codex、Anthropic 的 sandbox-runtime 和其他 macOS 方案。

**决定**

用 macOS Seatbelt。`pkg/sandbox/seatbelt_base.sbpl` 的文件头写明派生自 OpenAI Codex 的 `seatbelt_base_policy.sbpl`（Apache-2.0）。按调研文档，代理、拦截日志和"之后会被执行的文件"三项功能主要参照 sandbox-runtime。Seatbelt 不能按域名过滤网络，所以网络走本地代理。

**放弃的方案**

调研文档列了另开用户账号和虚拟机两类方案，对虚拟机的评语是隔离最强，但里面是 Linux，用不了 macOS 工具链。文档没有写明放弃的决定，代码里也没有这些实现。

**代价**

只有 macOS。Linux 和 Windows 还在 `docs/roadmap.md` 的 P3 里。云端靠 `sandbox.Machine` 接入别的沙箱（`aecfb63`）：机器本身是隔离边界，命令受限且不能提权。

**依据**

`docs/sandbox-sources.md`（`05ef4b0` 的父提交），`pkg/sandbox/seatbelt_base.sbpl`，`pkg/sandbox/box.go`，`docs/roadmap.md`。

## 21. 自建更新器

**背景**

没有 Developer ID，应用用 ad hoc 签名（`desktop@fad6587`）。Squirrel.Mac 要求两个版本有相同的 designated requirement，ad hoc 签名的版本之间没有。

**决定**

主进程自己实现更新（`apps/desktop/src/main/update.ts`）：启动时和每六小时读最新 release 的 `latest-mac.yml`，用户同意后才下载 zip，校验大小和 sha512，用 `ditto` 解开并确认版本。立即重启，或在下次退出、后端停止后换入，移动失败就放回旧包。

**放弃的方案**

Squirrel.Mac（`desktop@63813b7` 写明不可用）。

**代价**

- 下载、校验、替换都要自己维护。
- 每次发版除了 dmg 还要上传 zip 和 `latest-mac.yml`。
- 应用仍未公证，第一次打开会被 Gatekeeper 拦下，公证在 `docs/roadmap.md` 的 P3 里。

**依据**

`desktop@fad6587`、`desktop@63813b7`，`apps/desktop/src/main/update.ts`。

## 代码位置

| 仓库 | 路径 | 职责 |
|---|---|---|
| ollupi | `agent/loop.go` | 事件循环、槽位占用表 |
| ollupi | `agent/schedule.go` | `reconcile`、`admit`、`recover` |
| ollupi | `agent/run.go` | 一轮的执行、停下后的判定、结束 |
| ollupi | `agent/lease.go` | 抢占和续租分片 |
| ollupi | `agent/subagents.go` | 派生子 agent、写回报告 |
| ollupi | `agent/runtime/` | 单轮 ReAct 循环、工具执行 |
| ollupi | `agent/contextmanager/manager.go` | 输入预算、压缩阈值、精简模式门槛 |
| ollupi | `agent/systemprompt/systemprompt.go` | 系统提示词的组装顺序 |
| ollupi | `repo/db.go`、`repo/items.go`、`repo/turns.go` | 连接、条目恢复、一轮的状态和索引条件 |
| ollupi | `repo/migrate.go`、`repo/migrations/` | 编号 migration |
| ollupi | `repo/shard.go`、`repo/catalog.go` | 租约、fence、用户放置 |
| ollupi | `gateway/protocol.go`、`gateway/protocol.schema.json` | 分发表和生成的契约 |
| ollupi | `gateway/router.go` | 无状态路由 |
| ollupi | `pkg/llm/` | 三种模型客户端、并发上限、重试 |
| ollupi | `pkg/redact/redact.go` | 检测、占位符、还原 |
| ollupi | `pkg/sandbox/` | `Box`、`Machine`、Seatbelt |
| ollupi | `tools/cron/cron.go` | 定时检查和发送 |
| ollupi | `tools/subagent/subagent.go` | `Agent` 工具 |
| ollupi | `.cursor/rules/coding-rules.mdc` | 编码规则 |
| ollupi | `bench/README.md` | 基准方法和结果 |
| ollupi-desktop | `sidecar/cmd/ollupid/main.go` | 后端入口和校验模式 |
| ollupi-desktop | `sidecar/internal/host/host.go` | 组件装配 |
| ollupi-desktop | `apps/desktop/src/main/backend/` | 托管后端、配置和技能的校验写入 |
| ollupi-desktop | `apps/desktop/src/main/update.ts` | 自建更新器 |
| ollupi-desktop | `docs/roadmap.md`、`docs/ollupi-tool-contract.md` | 分层原则、工具类型范围 |
