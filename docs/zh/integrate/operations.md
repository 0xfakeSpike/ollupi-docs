# 运维

这一页讲引擎上线之后的日常运维：怎样关闭、备份和升级，引擎自己不写日志时从哪里看它在做什么，出了问题怎样排查。

## 关闭、备份与升级

关闭顺序：先让 `Run` 和 `Serve` 停下，再放掉分片租约，最后关库。用 [最小宿主](/zh/integrate/embed#最小宿主程序)和[分片部署](/zh/integrate/deploy#最小的多进程部署)的写法，取消一个 ctx 就按这个顺序走完：

| 顺序 | 动作 | 原因 |
|---|---|---|
| 1 | 取消 `h.Run` 和 `h.Gateway.Serve` 共用的 ctx | 网关关掉入口，以 1001 `server shutting down` 关掉现有连接，最多等 5 秒；调度器取消正在跑的轮次，等它们的 goroutine 退出；定时任务和记忆提炼停下 |
| 2 | 等两者都返回 | 被取消的轮次原样留在库里，下次启动由调度器接着跑；在 ctx 结束后才停下的运行不会把轮次判成失败 |
| 3 | `member.Run` 返回（分片部署时） | 它在返回前 `Release` 租约，备用进程最多等一次轮询（TTL/3）就能接管 |
| 4 | `h.Close()` | 关掉每个用户的 MCP 服务器，最后关库。`Config.Tools` 里有资源的 provider（比如 `workspace.Provider`）和用户的 Box 由宿主自己关 |

顺序错了后果很具体：先关库，还在跑的运行写不进去，以错误结束；不等 `member.Run` 返回就退出进程，租约没放掉，备用要等它过期才接管。

**备份。** 一个分片的数据是 `<Home>/data/store.sqlite`（WAL 模式，运行时同目录还有 `-wal` 和 `-shm`）和附件目录 `<Home>/attachments/`；目录库是另一个文件，一起备份。库要在停进程之后拷，或者用 `sqlite3` 的 `.backup` 在线拷，不要只拷主文件。不要用 `VACUUM` 做快照：`items` 没有 INTEGER PRIMARY KEY，`VACUUM` 可能重编号 rowid，而全文索引 `items_search` 靠 rowid 回读，之后要重建索引，见[持久化](/zh/engine/persistence)。

**升级。** 打开库时按 `PRAGMA user_version` 逐级迁移（`store/sqlite/migrations`，目录库是 `catalog/migrations`），只往前走，没有回滚。库版本高于程序知道的步数时打开直接失败：

```
store: /srv/ollupi/data/store.sqlite: the database is at schema version 3, from a newer version of this program; this one knows up to 2
```

所以升级前先备份库，也别指望换回旧二进制能打开新库。分片部署时还要注意：`host.New` 在 `member.Run` 拿租约之前就打开库并迁移，新版本的备用进程一启动就会迁移持有者正在用的库。由此推断，升级一个分片时应先停掉它的全部进程，再起新版本，而不是先起新版本的备用。

::: info 演进
v0.16.0 把引擎重建为以对话日志为中心，库换成 `data/store.sqlite`，不从旧库迁移。`b02dbfd`（v0.16.1）补上导入：一个 `Home` 第一次被新引擎打开、旁边有旧的 `data/ollupi.sqlite` 时，从它的只读快照里在一个事务中导入用户、设置、工作区、执行环境、MCP 服务器、定时任务、记忆和每个会话的日志，旧文件原样留着；旧引擎没结束的轮次以 interrupted 结束，不重跑。
:::

## 日志

引擎不写日志：整个代码里没有 `slog`，格式、级别、输出位置都不归引擎管。引擎把发生的事交给宿主的途径有三条：

- **返回的错误。** `host.New`、`h.Run`、`h.Gateway.Serve`、`member.Run` 的错误都要由宿主记下。`h.Run` 返回非 nil 多半是读写库失败，`member.Run` 返回 `store: a later holder of the shard writes to it now` 是失去了租约；这两种都该让进程退出、由守护重启，并报警。
- **库里的记录。** 一轮失败的原因写在它的 `TurnEnded` 里，模型调用失败写成一个 `error` 条目，被切断的工具调用写在它的结果里。它们和对话一起存着，客户端也看得到。
- **feed。** 每次提交改变了什么，都发到 `h.Store.Feed()` 上，见下一节。

模型请求失败的错误不带服务商的响应正文，只留 HTTP 状态码（`pkg/llm/connection.go` 的 `safeRequestError`），所以失败原因可以交给运维看，不会带出对话内容。

::: info 演进
v0.16.0 之前引擎往 `log/slog` 的默认 logger 写 `turn started`、`model call`、`shard lost` 等日志。`34d96a9`（v0.16.0）去掉了全部日志：只记日志、别无处理的错误改为忽略（释放租约、删附件、记一次定时任务等），被接住的 panic 不再留痕。
:::

## 监控

引擎没有指标接口，路线图第 4 项计划补上，见[路线图](/zh/roadmap)。在那之前能用的信号有三种。

**feed。** `h.Store.Feed().SubscribeAll(fn)` 收到每一次提交的事件（`store.Event`）：`Change.Entries` 是这次追加的日志条目，`Change.Header` 是会话的最新状态。回调在提交的那个 goroutine 里同步执行，只能做很快的事，比如加计数器，不能做网络请求，也不能阻塞。按条目类型计数：

```go
type counters struct {
	queued, completed, failed, interrupted, modelFailed, asked atomic.Int64
}

func (c *counters) hear(e store.Event) {
	if e.Change == nil {
		return
	}
	for _, entry := range e.Change.Entries {
		switch b := entry.Body.(type) {
		case conversation.TurnQueued:
			c.queued.Add(1)
		case conversation.TurnEnded:
			switch b.Status {
			case conversation.Completed:
				c.completed.Add(1)
			case conversation.Failed:
				c.failed.Add(1)
			case conversation.Interrupted:
				c.interrupted.Add(1)
			}
		case conversation.ModelFailed:
			c.modelFailed.Add(1)
		case conversation.ApprovalAsked, conversation.InputAsked:
			c.asked.Add(1)
		}
	}
}

// 装配后：sub := h.Store.Feed().SubscribeAll(c.hear)；退出时 sub.Close()
```

模型调用的耗时，在连接外面包一层：

```go
type timed struct {
	llm.Client
	observe func(model string, took time.Duration, err error)
}

func (t timed) Chat(ctx context.Context, req llm.ChatRequest, onDelta func(llm.Delta)) (llm.ChatResponse, error) {
	start := time.Now()
	resp, err := t.Client.Chat(ctx, req, onDelta)
	t.observe(req.Model.Name, time.Since(start), err)
	return resp, err
}
```

`Connections` 里放 `timed{Client: llm.NewOpenAI(...), observe: ...}`，配了 `ClientFor` 的话它返回的客户端也包上。内置客户端在 `Chat` 里先排队拿并发名额、再发请求、失败时重试，所以量到的时长包括排队和重试。这两段代码对着 v0.17.1 编译过。

**库。** 调度状态全在库里，可以直接查。只读打开，不要在运行中的库上写：

```sh
sqlite3 "file:/srv/ollupi/data/store.sqlite?mode=ro"
```

进程在运行时有 `-wal` 和 `-shm` 文件，这样打开没问题；进程停了、这两个文件不在时，`mode=ro` 打不开 WAL 模式的库（`unable to open database file`），这时查一份拷贝。

```sql
-- 顶层会话的状态：idle、active、waitingOnApproval、waitingOnUserInput（含子会话的等待）
SELECT status, count(*) FROM threads WHERE parent_id IS NULL GROUP BY status;

-- 可运行的会话（在槽位里跑的，加上等槽位的），按用户
SELECT user_id, count(*) FROM threads WHERE runnable_since IS NOT NULL GROUP BY user_id;

-- 调度器取会话的顺序：用户自己的会话在子会话前面，再按变成可运行的先后
SELECT id, user_id, parent_id IS NOT NULL AS subagent, runnable_since FROM threads
WHERE runnable_since IS NOT NULL ORDER BY parent_id IS NOT NULL, runnable_since LIMIT 20;

-- 自己在等审批或回答的会话，按用户
SELECT user_id, own_status, count(*) FROM threads
WHERE own_status IN ('waitingOnApproval', 'waitingOnUserInput') GROUP BY user_id, own_status;

-- 最近失败的轮次和原因
SELECT thread_id, id, json_extract(body, '$.Ended.Reason'), json_extract(body, '$.Ended.At') FROM turns
WHERE json_extract(body, '$.Ended.Status') = 'failed' ORDER BY ended_seq DESC LIMIT 20;

-- 还没结束的轮次（当前的加排队的）
SELECT count(*) FROM turns WHERE ended_seq IS NULL;

-- 这个库认的 epoch：最后一次拿到这个分片的持有者写下的
SELECT epoch FROM shard_epoch;
```

目录库：

```sql
-- 每个分片的地址、是否接新用户、报的负载、有没有持有者、租约还剩多少毫秒（只在有持有者时有意义）
SELECT id, address, accepting, load, owner <> '' AS held, epoch,
  expires_at - CAST((julianday('now') - 2440587.5) * 86400000 AS INTEGER) AS ms_left
FROM shards;

-- 每个分片放了多少用户
SELECT shard_id, count(*) FROM placements GROUP BY shard_id;
```

这些查询在 v0.17.1 建的库上跑过。表结构见[持久化](/zh/engine/persistence)，表名和列名会随迁移变。哪个容量上限在卡，见[容量规划与限流](/zh/integrate/capacity#判断哪个上限在卡)。

## 故障排查

启动阶段的报错（名字、沙箱、权限、模型、技能目录、网关令牌）列在[把引擎嵌进服务](/zh/integrate/embed#启动校验与常见错误)，这里不重复。

| 现象 | 原因 | 处理 |
|---|---|---|
| 启动报 `storage: open <路径>: invalid uri authority: ...` | `Home` 或目录库给的是相对路径 | 传绝对路径 |
| 启动报 `... the database is at schema version N, from a newer version of this program; this one knows up to M` | 用旧二进制打开了新版本升级过的库 | 换回新二进制；没有回滚，见上文"升级" |
| `member.Run` 一直不返回，进程不监听 | 另一个进程持有这个分片的租约，这个进程在当备用 | 正常的备用状态。查目录库的 `shards`：持有者已经死了时，要等租约过期 |
| `member.Run` 返回 `shard <id>: store: a later holder of the shard writes to it now`，进程退出 | 续约失败超过 0.9 TTL，或别的进程拿走了分片 | 让守护进程把它重启成备用；查目录库为什么写不进（磁盘、锁、卡住的进程） |
| `h.Run` 或某一轮的错误里出现 `store: a later holder of the shard writes to it now` | 进程失去租约后还在写，被 epoch 围栏挡住 | 说明 `member.Run` 取消 ctx 之后还有组件在用这个库，宿主要把它们放进 `serve` 里一起停 |
| 客户端 403 `host not allowed` | 请求的 `Host` 不在本机名字和 `AllowedHosts` 里；经路由器转发时是分片地址的主机名 | 把对外域名或分片地址的主机名加进 `AllowedHosts` |
| 客户端 401 `invalid or missing gateway token` | 没带令牌、令牌放在了 URL 里，或 `Authenticate` 返回 `auth.ErrUnknownToken` | 用 `Authorization: Bearer`，浏览器用 `ollupi.token` 子协议，见[网关协议](/zh/integrate/protocol) |
| 分片回 503 `the token cannot be checked now; try again` | `Authenticate` 返回了 `ErrUnknownToken` 以外的错误，或超过 10 秒 | 查登录系统 |
| 分片回 503 `this user is not served here now; try again` | `Admit` 拒绝：用户放在别的分片，或目录库查不了 | 客户端只连路由层；核对分片进程的 `ID` 和目录库 |
| 分片回 503 `too many connections are starting; try again` | 新连接超过准入速率（默认每秒 200，突发 400），常见于重启后 | 客户端按 `Retry-After` 回来即可；要更快可调 `Gateway.Connections`，见 [Config 参考](/zh/integrate/config#gateway-options) |
| 分片回 500 `the user could not be made ready` | 第一次连接时建用户的写入失败 | 查库：磁盘、文件权限、是否已失去租约 |
| 路由器回 503 `no shard can take this user now` | 新用户没有可放的分片（没有分片接新用户），或令牌查不了，或目录库查不了 | 起一个 `Accepting: true` 的分片进程；查登录系统和目录库 |
| 路由器回 503 `no process holds the user's shard now; try again` | 用户的分片没有持有者 | 起那个分片的进程，或等备用接管 |
| 路由器回 503 `the user's shard cannot be reached now; try again` | 持有者死了而租约还没过期，或地址不通 | 换手时等备用接管，客户端退避重连；持续出现时查 `shards.address` 和进程 |
| 连接被关，4000 `replaced by a newer connection` | 同一用户开了第 5 条连接，最老的一条被顶掉 | 协议规定客户端不自动重连，见[客户端](/zh/integrate/client) |
| 连接被关，1008 `client is not reading fast enough` | 发给客户端的待发数据超过 16 MiB | 客户端要持续读连接，不要在读循环里做慢操作 |
| 连接被关，1001 `connection reached its age; reconnect` | 连接到了寿命（15 到 20 小时之间随机） | 正常，客户端重连 |
| 发消息被拒：`the conversation has 20 messages waiting already; ...` | 这个会话已有 20 轮排在当前轮次后面 | 等前面的开始，或中断 |
| 一轮失败：`the turn reached its time limit of ...` | 一次占用槽位超过 `RunLimit` | 见[容量规划与限流](/zh/integrate/capacity#调大调小的后果) |
| 一轮失败：`run: model call: model request failed (HTTP 429); check the selected connection and model` | 重试 8 次后仍被限流 | `calls` 超过了服务商配额，调小或提高配额 |
| 一轮失败：`... (HTTP 401)` 或 `(HTTP 404)` | 密钥或模型名不对 | 核对连接的密钥、`baseURL` 和模型名 |
| 一轮失败：`run: model call: model request failed; check the selected connection and try again` | 请求没拿到 HTTP 状态码，比如网络不通 | 查到服务商的网络 |
| 一轮失败：`run: model call: llm: the provider sent nothing for 3m0s` | 服务商 3 分钟没有发回任何字节 | 查服务商状态；这次尝试被放弃 |
| 一轮失败：`run: the permission settings: ...` | 某一层权限规则提到了这个用户没有的工具 | 部署层的规则在 `Permissions` 里改；用户、工作区、会话层由客户端改 |
| 一轮失败：`run: the tools of the user: ...` | 建这个用户的工具注册表失败：provider 或工具重名，或 `Boxes` 对他返回错误 | 见[扩展点](/zh/integrate/extend#命名) |
| 重启后一些工具调用失败，提示 `the call was cut off when the run that made it stopped; ...` | 上个进程退出时它们正在执行，可能已生效，引擎不重跑 | 按设计如此，见[持久化](/zh/engine/persistence) |

## 代码位置

| 路径 | 职责 |
|---|---|
| `host/host.go` | `Run` 怎样把调度、定时任务、记忆提炼放进一个 errgroup，`Close` 关什么 |
| `schedule/schedule.go` | 关闭时等运行退出；运行失败或超时时把轮次判成失败 |
| `shard/shard.go` | 续约、失去租约、`Release` |
| `store/feed.go`、`store/store.go` | `Feed`、`Event`、`Change`、`ErrShardLost` |
| `store/sqlite/sqlite.go`、`store/sqlite/migrations/`、`store/sqlite/legacy.go` | 打开、迁移、epoch 检查、旧库导入 |
| `run/run.go`、`run/model.go` | 被切断的调用、模型失败的条目和轮次失败的原因 |
| `pkg/llm/connection.go`、`idle.go` | `safeRequestError`、3 分钟无响应 |
| `pkg/wshub/wshub.go`、`pkg/jsonrpc/jsonrpc.go` | 准入、顶替、寿命、心跳；待发数据上限 16 MiB |
| `gateway/auth.go`、`gateway/server.go`、`router/router.go` | 握手时各种 HTTP 回复 |
