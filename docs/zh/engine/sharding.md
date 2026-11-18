# 分片与租约

一个 SQLite 库是一个分片（shard）。分片上的用户共用它的表，按用户隔离。引擎本身不知道分片：`shard` 包把一个进程作为某个分片运行，它在部署的目录（catalog）里持有这个分片的租约（lease），同一时间只有一个进程运行一个分片；持有者退出后，等着租约的备用进程接管，从上次停下的地方继续。分片的数量决定容量。客户端只连一个地址，不知道自己在哪个分片：负载均衡器的回调或路由器查目录，把每条连接送到用户所在的分片。这一页讲多用户怎样隔离、目录记什么、租约和 epoch 怎样占有和接管、新用户怎样放置、连接怎样找到分片，以及令牌认证和每用户资源。

```mermaid
flowchart LR
  C["客户端"] --> LB["负载均衡器"]
  LB -->|"握手头部"| X["router/extproc"]
  X -->|"x-ollupi-shard"| LB
  LB -->|"按头部转发"| P1
  LB -->|"放不了的连接"| R["router.Router"]
  R --> P1
  X -->|"Locate"| K[("目录 catalog")]
  R -->|"Locate"| K
  P1["分片进程 A（持有租约）"] -->|"Renew 和负载"| K
  P2["分片进程 B（等租约）"] -.->|"Acquire"| K
  P1 --> D1[("分片库 1")]
  P2 -.-> D1
  P3["分片进程 C"] --> D2[("分片库 2")]
```

## 为什么这样设计

- **用户共用分片的表。** 一个库就是一个分片：工作区、会话、记忆、设置带用户，日志和定时任务经会话找到用户。分片上所有用户的会话由同一个调度器、同一组槽位运行。见[设计决策 10](/zh/reference/decisions#_10-单库即分片与租约)。
- **引擎不知道分片。** 宿主、调度、网关都不涉及租约；`shard.Member` 包在外面，拿到租约才运行引擎，失去租约就取消它。不作为分片运行时，什么都不用配：不调用 `Fence`，网关不设 `Admit`。
- **租约和地址在同一处。** 租约记在目录里分片的那一行上，和持有者的地址放在一起：地址指向的进程就是持有租约的进程，两者不会对不上。接管之后按重启恢复，没有专门的接管逻辑，因为调度状态本来就全在库里，见[崩溃恢复](/zh/engine/persistence#崩溃恢复)。
- **epoch 挡住卡住的旧持有者。** 一个进程可能卡得比租约还久，醒来时还不知道分片已经换了主人。每次占有分片都得到一个比之前都大的 epoch，分片的库记下它，每次写入都核对，所以旧持有者写不进新持有者的库。
- **租约按目录的时钟判定，持有者提前放弃。** 到期时间由目录用自己的时钟算；持有者从发出请求之前开始计时，并提前十分之一的租约时长放弃，这样它总在别的进程能接手之前停下，即使两边时钟有偏差。
- **路由不保存状态，分片自己再查一次。** 回调和路由器只做认证、查目录、转发，可以运行任意多个。分片在第一次服务一个用户之前确认这个用户放在自己这里，所以一个用户不会在第二个分片上再建一份数据。
- **放置看负载，两选一。** 新用户随机抽两个接收新用户的分片，放到负载较低的那个。新加的分片能分到一份，但不会把所有新用户都吸过去。

代价：容量靠分片数堆，单个分片仍是一个 SQLite 文件和一条连接；用户不能跨分片迁移；进程崩溃没有释放租约时，接管要等租约过期；备用进程要能打开同一个数据库文件和附件目录；目录是所有分片和路由共用的一个依赖；现有基准测于多用户和分片之前，这些开销还没有测过。

::: info 演进
- v0.9.0 之前一个库只属于一个使用者。`28adb4d` 让一个库成为一个分片，加了用户列，调度没有因此改动。有没有对比过一人一个库，没有记录。租约和"接管即重启恢复"来自 `cd8faee`；路由器和目录库来自 `583d20c`；令牌认证和 `default` 用户来自 `15a76c7`。
- 以前租约是分片库里 `shard_lease` 的一行，按持有者核对，引擎（`agent.Config.Lease`）自己占有和续约，地址由宿主另行发布。`180a26c` 把租约核对扩到每一次写入；`48c8454` 把租约移进目录、和地址放在一起，分片库只记 epoch，并新建 `shard` 包，让引擎不再知道分片；`de6eb86` 把目录做成接口，到期改由目录的时钟判定，持有者提前放弃。
- 以前新用户放到用户最少的分片，新加的分片会吸走所有新用户；`6282176` 改成按负载两选一，并让分片拒绝不归它的用户时回 503 和 `Retry-After`，而不是让客户端不再重试的 401。负载均衡器回调来自 `ce11149`。
:::

## 多用户隔离

用户隔离在同一张表里完成，不是一人一个库。

### 数据归属

| 数据 | 怎么归到用户 |
|---|---|
| `threads`、`workspaces`、`environments`、`mcp_servers`、`memories` | 自带 `user_id` 列，外键指向 `users` |
| `settings`、`memory_state` | 主键就是 `user_id`，每用户一行 |
| `entries`、`turns`、`items`、`responses`、`cron_jobs` | 经 `thread_id` 到 `threads.user_id` |

同一用户的工作区按 `(user_id, root)` 唯一，不同用户可以用相同的路径；执行环境按 `(user_id, name)` 唯一；记忆的主题按 `(user_id, scope, workspace_id, topic)` 唯一。表结构见[持久化](/zh/engine/persistence#表和关系)。

### 入口检查

调用方拥有什么，在 `app` 的入口检查。不属于这个用户的东西一律当作不存在，返回 `store.ErrNotFound`，到协议层是 `notFound`。

| 检查 | 用在 |
|---|---|
| `app.thread(r, user, id)` | 按用户读会话，别人的返回未找到 |
| `app.topThread` | 发消息、插话、中断、改名、归档、删除、改权限；同时拒绝子 agent 会话（`account.ErrSubagentThread`） |
| `Reader.Workspace(user, id)`、`Reader.Environment(user, id)` | 按用户读工作区和执行环境 |
| `Reader.Threads(user, ...)`、`Reader.Search(user, ...)`、`Reader.CronJobs(user, ...)` | 列表和搜索都带用户条件 |
| `Reader.Memories(user, ...)`、`Reader.Settings(user)`、`Reader.MCPServers(user)` | 记忆、设置、MCP 服务器按用户读 |

`read_tool_output` 只读调用者所在会话的视图，所以模型读不到别的会话的输出。定时任务的轮次没有调用方，它在所属会话里运行，按会话主人算。

### 事件和连接

网关的每条连接在 `initialize` 之后用 `Feed.Subscribe(user, ...)` 订阅自己用户的事件，所以事件只发给本人；没有用户的事件不发给任何人。一个用户最多同时有四条连接，每条都收到这个用户的全部事件，第五条顶替最早的一条。连接的上限和心跳见[接入客户端](/zh/integrate/client)。

一个用户第一次连到这个进程时，网关先做分片这一侧的校验（见下文），再调用 `EnsureUser`，建 `users`、`settings` 和这台机器的执行环境；之后这个进程记住这个用户，重连不再写库。

调度不区分用户：所有用户的可运行会话在同一个队列里，按相同的顺序取，只受单用户槽位限额约束。

## 分片

`sqlite.Open(home)` 打开的库就是一个分片。分片之间不共享数据，用户的会话、记忆和附件都留在自己的分片。

所有分片和路由共用一个目录，接口是 `catalog.Catalog`：

| 方法 | 行为 |
|---|---|
| `Acquire(shard, owner, address, accepting, ttl)` | 没有进程持有、或租约已过期时占有分片，写上持有者的地址和是否接收新用户，返回新的 epoch；有人持有时 `held` 为假 |
| `Renew(shard, owner, epoch, ttl, load)` | 续约并报告负载；持有者或 epoch 对不上时返回 `catalog.ErrLeaseLost` |
| `Release(shard, owner, epoch)` | 立即放弃租约，只在持有者和 epoch 都对上时生效 |
| `Locate(user)` | 返回用户的分片和当前持有者的地址；新用户在这时放置；没有进程持有时地址为空；没有能接收的分片时返回 `catalog.ErrNoShard` |
| `ShardOf(user)` | 只查用户的分片，不放置；没放置时返回空 |
| `Place(user, shard)` | 运维指定用户的分片，比如单独给一个客户的分片；用户已在别的分片时报错 |

`catalog.SQL` 是现在唯一的实现，用 `catalog.OpenSQL(path)` 打开一个独立的 SQLite 文件，表结构按自己的编号 migration（`catalog/migrations/`）升级。需要目录比任何一台机器活得久的部署，可以在协调服务（比如 etcd）或独立于分片的数据库上实现这个接口。

| 表 | 字段 | 说明 |
|---|---|---|
| `shards` | `id` | 分片 ID |
| | `address` | 当前持有者接受连接的地址 |
| | `accepting` | 是否接收新用户；留给单个客户的分片设为否 |
| | `load` | 持有者最近一次报告的负载 |
| | `owner` | 持有进程的 UUID；空表示没有进程持有 |
| | `epoch` | 最近一次占有的 epoch |
| | `expires_at` | 租约到期时间，Unix 毫秒，按目录的时钟 |
| `placements` | `user_id` | 用户，主键 |
| | `shard_id` | 所在分片，带索引 |

`catalog.SQL` 的每个事务一开始就拿写锁（见 [SQLite 配置](/zh/engine/persistence#sqlite-配置)），所以多个分片和路由进程可以同时打开、同时写同一个目录文件，同一个新用户不会被放两次。

引擎不搬迁用户：用户一旦在分片上有了数据就留在那里。`Place` 必须在用户有任何数据之前调用。

### 放置新用户

`Locate` 遇到没放置过的用户时，在同一个事务里放置：

1. 取出所有 `accepting` 的分片，连同各自的负载和已放置的用户数。
2. 只有一个时就放到它。多于一个时随机抽两个不同的。
3. 负载低的那个胜出；负载相同时用户少的胜出；再相同取先抽到的。
4. 写入 `placements`。

负载由各分片的持有者报告，见[负载上报](#负载上报)。测试里九个各有 50 个用户的空闲分片加上一个新分片，新分片分到 100 个新用户中的一部分，但少于 50 个（`TestAShardJustAddedTakesASharePerhapsLargerButNotAll`）。

## 分片租约

`shard.Member` 把一个进程作为一个分片运行：

| 字段 | 含义 |
|---|---|
| `ID` | 分片 ID |
| `Address` | 这个进程接受连接的地址，占有时写进目录 |
| `Accepting` | 是否接收新用户 |
| `Catalog` | 目录 |
| `TTL` | 租约时长，必须大于 0，没有默认值 |
| `Load` | 报告负载的函数，可空；度量由部署选择 |

`bench` 的崩溃实验用 `-lease 1500ms`。

### 租约行

租约就是目录里分片那一行的 `owner`、`epoch`、`expires_at`。`catalog.SQL` 的占有是一条语句：

```sql
INSERT INTO shards(id, address, accepting, owner, epoch, expires_at) VALUES (?, ?, ?, ?, 1, <now> + ?)
ON CONFLICT(id) DO UPDATE SET address = excluded.address, accepting = excluded.accepting, owner = excluded.owner,
  epoch = shards.epoch + 1, expires_at = excluded.expires_at
WHERE shards.owner = '' OR shards.expires_at <= <now>
```

`<now>` 是目录数据库自己的当前时间（由 `julianday('now')` 换算成 Unix 毫秒），所以到期只按目录的时钟判定，和发起请求的进程的时钟无关。两种情况能占有：没有这一行，或这一行没人持有、租约已过期。每次占有 epoch 加一，第一次是 1。

续约只在 `owner` 和 `epoch` 都对上时更新 `expires_at` 和 `load`；放弃把 `owner` 清空、`expires_at` 置 0。

### 时间参数

设租约时长为 T：

| 动作 | 间隔或期限 |
|---|---|
| 等待方尝试占有 | 每 T/3 一次 |
| 持有方续约 | 每 T/3 一次 |
| 持有方认为自己还持有到 | 最近一次成功的占有或续约**发出之前**的时刻加 0.9T |
| 每次访问目录的超时 | 10 秒 |
| 进程被杀后的接管延迟 | 最多约 T + T/3（租约到期，加一次尝试的间隔） |
| 进程正常退出后的接管延迟 | 最多约 T/3（租约已放弃，只等一次尝试） |

目录把租约延到"它收到请求时 + T"，而持有者从请求发出之前算起、只算到 0.9T，所以持有者认为的期限总早于目录判定的到期，差出的余量是 T/10 加上请求在路上的时间。这个余量覆盖两边时钟走速的差异，而不依赖两边时钟对齐。

### 启动和接管

`Member.Run(ctx, st, serve)`：

1. 生成这个进程的 `owner`（UUID）。
2. 循环调用 `Acquire`，没拿到就等 T/3 再试，直到拿到或 ctx 结束。目录出错也只是下一轮再试。
3. `st.Fence(epoch)` 把 epoch 记进分片的库，见[围栏](#围栏)。库里已有更大的 epoch 时返回 `store.ErrShardLost`，`Run` 失败。
4. 起续约的 goroutine，它持有一个租约结束时会被取消的 ctx。
5. 用这个 ctx 调用 `serve`。宿主在 `serve` 里运行引擎（`host.Run`）和网关。
6. `serve` 返回后放弃租约（带 10 秒超时，不受外层 ctx 取消影响）。

`serve` 里的流程和普通重启完全相同：调度器从库里读出可运行的会话，每次运行先关掉上一个进程切断的调用，接着往下走。接管不需要专门的逻辑，见[崩溃恢复](/zh/engine/persistence#崩溃恢复)。

`host.New` 打开 store 在 `Member.Run` 之前，所以备用进程启动时就打开了分片的库，只是不运行引擎、不服务连接。

### 续约和失去租约

续约的 goroutine 每 T/3 调用一次 `Renew`，同时带上 `Load()` 的结果：

| 结果 | 处理 |
|---|---|
| 成功 | 把期限更新为这次请求发出前的时刻加 0.9T |
| 失败（包括 `ErrLeaseLost`），还没到期限 | 下一轮再试 |
| 失败，已过期限 | 失去租约 |

失去租约时，续约的 goroutine 以 `store.ErrShardLost` 为原因取消 `serve` 的 ctx：调度器停下，所有运行的 ctx 结束，进行中的模型调用和工具随之取消，网关停止服务。`Run` 返回包了 `store.ErrShardLost` 的错误。这些会话留在库里原样的状态，由新的持有者接着运行。

### 围栏

进程可能卡住比租约还久：它既没续约，也还不知道自己失去了租约，而新持有者已经开始工作。epoch 防止旧进程写坏数据：

- `Store.Fence(epoch)` 写分片库的 `shard_epoch`，只在库里的值不大于这个 epoch 时生效，否则返回 `store.ErrShardLost`。
- 之后每个 `Store.Update` 在事务开始时读 `shard_epoch`，不等于自己的 epoch 就返回 `store.ErrShardLost`，事务不执行。事务一开始就拿写锁，核对和写入之间别的进程插不进来。

所有写入都走 `Update`，所以旧持有者在新持有者 `Fence` 之后的每一次写入都会被拒绝。被拒绝的写入里包括调度器想把出错的轮次记为失败的那一次，于是调度器带着错误退出，旧进程的引擎停下。`Read` 不核对 epoch。没有调用过 `Fence` 的 store（不作为分片运行时）不做这项检查。

旧进程里已经在沙箱中执行的工具，要等它的 ctx 被取消才停；在那之前工具的副作用照常发生，而它的结果写不进库。新持有者看到的是一个已开始、没有结果的调用，记为被切断。

### 负载上报

`Member.Load` 返回分片当前的负载，续约时一起写进目录，供[放置新用户](#放置新用户)比较。度量由部署选择，引擎提供几种现成的计数：

| 度量 | 来源 |
|---|---|
| 最近活跃的用户 | `Reader.Active(since)`：有会话在 `since` 之后更新过的用户数 |
| 进行中的会话 | `Reader.Busy()`：状态不是 `idle` 的会话数 |
| 连接数 | `gateway.Server.Connections()` |

`Load` 为空时报告 0；`Load` 返回错误时这一次也报告 0。负载只在续约时写，刚占有分片时目录里还是上一个持有者报告的值。

## 路由器

客户端只连一个地址。认证和查分片是 `router.Locator`：用 `auth.Authenticate` 认出用户，再 `catalog.Locate` 找到分片和持有者的地址，整个查找限时 10 秒，不缓存。它有两个用法：负载均衡器的回调，和路由器本身。

`router.Router` 实现了 `http.Handler`，不保存状态，可以运行任意多个：

| 步骤 | 失败时 |
|---|---|
| 认出用户 | 令牌不认识：401 `invalid or missing gateway token` |
| 查分片，新用户在此时放置 | 认证服务出错或目录出错：503 `no shard can take this user now` |
| 分片没有持有者 | 503 `no process holds the user's shard now; try again` |
| 解析地址 | 503 `the user's shard cannot be reached now` |
| `httputil.ReverseProxy` 转发，含 WebSocket 升级；等分片回应头部最多 30 秒 | 503 `the user's shard cannot be reached now; try again` |

路由器不解析 JSON-RPC，它只转发连接。转发时请求的 `Host` 换成目标地址的主机，所以分片网关的 `AllowedHosts` 要包含它。分片换手时，连在旧进程上的 WebSocket 断开，客户端重连，再次经路由器转到新地址；新持有者占有之前，客户端看到 503 并重试。客户端对各种关闭码和握手状态怎样重连，见[接入客户端](/zh/integrate/client)。

### 负载均衡器回调

能通过 Envoy 外部处理协议（ext_proc）回调的负载均衡器，比如 Google Cloud 应用负载均衡器的路由扩展，用 `router/extproc` 放置连接：

- 收到握手的请求头时，`extproc.Callout` 用同一个 `Locator` 找到用户的分片，设置 `x-ollupi-shard` 头（`extproc.ShardHeader`），覆盖客户端自己带来的同名头。负载均衡器按这个头路由，并自己持有连接。
- 认证或查找失败时，删掉这个头。连接落到负载均衡器的默认后端，也就是一个 `router.Router`，由它回 401 或 503。
- 其余阶段（响应头、请求体等）原样放行。

没有这样的负载均衡器时，全部连接都由 `router.Router` 转发。

### 分片这一侧的校验

路由的结果可能过时，或者连接绕过了路由。`gateway.Options.Admit` 设为 `shard.Member.Admit` 时，网关在第一次服务一个用户之前调用它：`Admit` 用 `ShardOf` 查这个用户的分片，不是自己（包括还没放置）就拒绝。网关回 503，带 1 到 `Connections.RetryWithin`（默认 5）秒之间随机的 `Retry-After`，正文 `this user is not served here now; try again`，客户端稍后重试。这样一个用户不会在第二个分片上再建一份数据。

`Admit` 只查不放：新用户的放置只发生在路由的 `Locate` 里。一个用户在这个进程里通过一次之后，同一进程不再查它。不设 `Admit` 时网关服务所有认证通过的用户。

### 健康检查

`/healthz`（`auth.HealthPath`）不要令牌，分片网关和路由器都直接回 200。分片进程只在 `serve` 里运行网关，也就是只在持有租约时服务；负载均衡器的健康检查因此只找得到持有者，把这个分片的连接送到它那里。

## 令牌认证

Ollupi 不做登录。登录在它之前完成，`auth.Authenticate(ctx, token)` 只回答"这是谁的令牌"：

| 返回 | 网关 | 路由器 |
|---|---|---|
| 用户 | 继续 | 继续 |
| `auth.ErrUnknownToken` | 401 | 401 |
| 其他错误（认证服务暂时不可用） | 503，带 `Retry-After`，`the token cannot be checked now; try again` | 503 `no shard can take this user now` |

网关的两个选项：

| 选项 | 含义 |
|---|---|
| `Options.Token` | 单用户网关的令牌，属于 `default` 用户，用 `subtle.ConstantTimeCompare` 比较 |
| `Options.Authenticate` | 多用户时取代 `Token` |

两者都没有时 `gateway.NewServer` 报错。认证限时 10 秒。

`auth.TokenOf` 按顺序读两个地方：

1. `Authorization: Bearer <token>`。
2. WebSocket 子协议。浏览器不能设置 `Authorization`，所以把令牌放在子协议列表里，紧跟在 `ollupi.token` 后面：

```js
new WebSocket(url, ["ollupi.token", token])
```

服务端握手时只声明支持 `ollupi.token` 这一个子协议，所以协商回去的是 `ollupi.token`，令牌不出现在响应里。

令牌不放在 URL 里，因为访问日志会记录 URL；`?token=` 不能用于认证。

网关在令牌之前还校验 `Host`：不在 `localhost`、`127.0.0.1`、`::1` 和 `AllowedHosts` 里时回 403。`Origin` 按 `localhost:*`、`127.0.0.1:*`、`[::1]:*` 和 `AllowedOrigins` 校验。

## 单用户槽位限额

`host.Config.UserSlots` 防止一个用户的会话占满分片的槽位，默认等于 `Slots`（32），即不限。调度器取可运行的会话时排除已到上限的用户，启动前再查一次；超额的会话留在可运行状态，不失败，这个用户的槽位释放后接着取。子 agent 会话和父会话是同一个用户，算在同一个限额里。调度的细节见[执行模型](/zh/engine/execution)。

## 每用户资源

`host.Config` 有几个按用户取资源的钩子：

| 钩子 | 取什么 | 没配时 |
|---|---|---|
| `ClientFor(user, connection)` | 这个用户调用这条连接时用的模型客户端；记忆提取也用它 | 共用 `Connections` |
| `Boxes(user)` | 这个用户的沙箱，命令、文件和本地 MCP 服务器都经它访问 | 必填 |

每个用户的 MCP 服务器存在库里（`mcp_servers`），由 `mcp.Users` 按用户连接，用户改了服务器后下次取工具时重新连接，见[技能与 MCP](/zh/engine/skills-mcp)。

- 模型并发名额在客户端内部，所以 `ClientFor` 应该每次返回同一个客户端，否则限制不生效。窗口预算和模型列表仍从共享的 `Connections` 里读，所以它始终要配。见[模型](/zh/engine/models)和[扩展点](/zh/integrate/extend)。
- `ClientFor` 返回错误时只有这一轮失败，其他用户不受影响。
- 沙箱见[沙箱](/zh/engine/sandbox)。

## 边界与已知问题

- **租约接管没有测量数据。** `bench crash -lease` 会启动备用进程，但没有保留结果。从 kill 到备用进程开始服务要多久，还没有数字，见[接下来要测的](/zh/benchmarks/plan)。上面的接管延迟是按时间参数算出来的上限，不是测量值。
- **多分片没有测量数据。** 现有基准全部是一个库、一个进程。吞吐是否随分片数增长、回调和路由器增加多少延迟，都没测。
- **吵闹邻居没有测量数据。** `UserSlots` 默认不限；不配 `ClientFor` 时所有用户共用连接上的模型并发名额。`bench users` 有对应的实验，还没有跑出结果。
- **旧持有者的工具停得晚。** epoch 挡住的是写库；旧进程槽位里正在执行的工具，要等它的 ctx 被取消才停，在那之前沙箱里的副作用照常发生。新持有者把这些调用记为被切断。
- **目录是共同依赖。** 路由对每条连接都查 `Locate`，查不到时回 503；分片的 `Admit` 也查目录，查不到时同样回 503，客户端按 `Retry-After` 重试。持有者连续续约失败超过期限就放弃分片，所以目录长时间不可用时，所有分片都会停下。
- **放置不看分片有没有持有者。** 新用户可能被放到一个 `accepting` 但暂时没有进程持有的分片上，在有进程占有它之前，这个用户的连接都回 503。
- **负载出错按 0 报。** `Load` 返回错误时报告 0，这个分片在放置时会显得空闲。
- **migration 和旧库导入早于占有租约。** 它们在 `sqlite.Open` 里执行，而 `Member.Run` 在之后。版本更新的备用进程一启动，就会在持有者还在运行时升级表结构，代码里没有挡住这种情况。
- **用户不能迁移。** 用户有了数据就留在原分片，`Place` 必须在用户有任何数据之前调用。

## 代码位置

| 仓库 | 路径 | 职责 |
|---|---|---|
| ollupi | `shard/shard.go` | `Member`：占有、续约、放弃租约，`Admit` |
| ollupi | `catalog/catalog.go` | `Catalog` 接口、`ErrNoShard`、`ErrLeaseLost` |
| ollupi | `catalog/sql.go` | `catalog.SQL`：租约、放置、两选一 |
| ollupi | `catalog/migrations/` | 目录库的 migration |
| ollupi | `store/sqlite/sqlite.go` | `Fence` 和每次写入的 epoch 核对 |
| ollupi | `router/router.go` | `Locator`、`Router` |
| ollupi | `router/extproc/extproc.go` | 负载均衡器回调，`x-ollupi-shard` |
| ollupi | `auth/auth.go` | `Authenticate`、`TokenOf`、`HealthPath` |
| ollupi | `gateway/serve.go`、`gateway/auth.go` | `Options`、Host 和令牌校验 |
| ollupi | `gateway/server.go` | `Admit` 的调用、`/healthz`、连接和订阅 |
| ollupi | `pkg/wshub/wshub.go` | 连接上限、`Refuse` 的 503 和 `Retry-After` |
| ollupi | `app/app.go` | 按用户读会话的入口检查 |
| ollupi | `schedule/schedule.go` | 单用户槽位限额 |
| ollupi | `host/host.go`、`host/models.go` | `ClientFor`、`Boxes`、`UserSlots` 的装配 |
| ollupi | `catalog/catalog_test.go` | 租约、放置、多进程共用目录的测试 |
| ollupi | `bench/crash.go` | 用 `shard.Member` 运行的崩溃和接管实验 |
