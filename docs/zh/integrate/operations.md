# 运维

这一页讲引擎上线之后的日常运维：怎样关闭、备份和升级，看哪些日志、盯哪些信号，出了问题怎样排查。

## 关闭、备份与升级

关闭顺序：先停网关，再停附属组件，最后关库。

| 顺序 | 动作 | 原因 |
|---|---|---|
| 1 | `http.Server.Shutdown`，或让 `gateway.Server.Serve` 的 ctx 结束 | 关掉入口，不再有新的 `turn/start` 写库；`Serve` 最多等 5 秒 |
| 2 | 取消 agent 和附属组件的 ctx，等它们返回 | 定时器不再发轮次，记忆提炼收尾 |
| 3 | `a.Wait()` | 等槽位里的 goroutine 退出，并释放分片租约 |
| 4 | `db.Close()` | 租约释放、所有写入结束之后才关库 |

顺序错了后果很具体：先关库会让槽位里的写入失败，轮次停在中间状态；租约没释放就关库，备用进程要等租约过期才接管。

备份：库是单个文件 `<home>/data/ollupi.sqlite`，WAL 模式下还有同目录的 `-wal` 和 `-shm`，要三个一起拷或先停进程；分片目录库是另一个文件，一起备份。不要用 `VACUUM` 做快照：`items` 没有 INTEGER PRIMARY KEY，`VACUUM` 会重编号 rowid，而 `items_search` 靠 rowid 回读，之后必须重建索引，见[持久化](/zh/engine/persistence)。

升级：`repo.Open` 会读 `PRAGMA user_version` 并按 `repo/migrations` 逐级升级，步骤只往前走，没有回滚。库版本高于程序知道的步数时 `Open` 直接失败：

```
the database is at schema version 3, from a newer ollupi; this one knows up to 2
```

所以升级前先备份库，也别指望换回旧二进制能打开新库。二进制必须带 `-tags sqlite_fts5` 构建，否则 `repo/fts5.go` 让编译直接失败。

## 日志

引擎只往 `log/slog` 的默认 logger 写，不自己决定格式、级别和输出位置，这些由宿主用 `slog.SetDefault` 设。桌面端的 sidecar 用文本格式写到 stderr（`sidecar/cmd/ollupid/main.go`），`bench` 只保留 WARN 及以上。

日志只记 ID、模型、耗时、token 数和状态，不记模型的输入输出、工具的输出，也不记工具的错误（它们可能引用文件内容和命令）。模型请求失败的错误不带服务商的响应正文，只留 HTTP 状态码（`pkg/llm/connection.go` 的 `safeRequestError`）。所以日志可以交给运维看，但只凭日志看不到一轮"说了什么"，那要去读库，见[执行轨迹](/zh/engine/traces)。

常见的日志，按来源分：

| 消息 | 级别 | 字段 | 什么时候 |
|---|---|---|---|
| `shard claimed` | INFO | `owner` | 拿到分片租约 |
| `agent started` | INFO | `name`、`slots`、`models`、`tools` | `Start` 成功返回前 |
| `items cut off by the restart closed` | WARN | `thread`、`items` | 恢复时收拾了上个进程停在半路的条目 |
| `shard lease not renewed` | WARN | `err` | 续约失败，还在容忍期里 |
| `shard lost` | ERROR | `owner`、`err` | 失去租约，agent 随即停止 |
| `shard lease not released` | WARN | `err` | 退出时释放租约失败，下一个进程要等它过期 |
| `turn queued` | INFO | `thread`、`turn` | 会话里已有当前轮次，新的一轮排在后面 |
| `turn started` | INFO | `thread`、`turn`、`model`、`connection`、`subagent`、`cronJob` | 一轮成为会话的当前轮次（不是进槽位） |
| `run ended` | INFO | `thread`、`turn`、`ms`、`final`、`items` | 一次占用槽位结束；`ms` 是在槽位里的时长 |
| `turn waiting` | INFO | `thread`、`turn`、`on`（`user` 或 `subagents`）、`requests` 或 `subagents` | 一轮让出槽位去等 |
| `turn ended` | INFO | `thread`、`turn`、`status`、`input`、`output`、`ms` | 一轮结束；`ms` 从成为当前轮次算起 |
| `turn failed` | WARN | `thread`、`turn`、`err` | 一轮以失败结束 |
| `turn left in progress at shutdown` | INFO | `thread`、`turn`、`err` | 进程关闭时一轮还没跑完，留给下次启动恢复 |
| `model call` / `context compaction` | INFO | `thread`、`turn`、`model`、`ms`、`input`、`cached`、`output`、`finish`、`toolCalls` | 每次模型请求；`ms` 包括在名额上排队和重试 |
| `model call failed` / `context compaction failed` | WARN | `thread`、`turn`、`model`、`ms`、`err` | 模型请求在重试之后仍失败 |
| `tool call` | INFO | `thread`、`turn`、`item`、`tool`、`ms`、`failed`、`awaits` | 每次工具执行 |
| `approval requested` | INFO | `thread`、`turn`、`item`、`tool` | 工具调用要等审批 |
| `client connected` / `client disconnected` | INFO | `origin`（只有 connected 有） | 网关上的连接 |
| `client replaced by a newer connection` | INFO | | 同一用户的新连接顶掉了旧连接 |
| `client fell behind; connection closed` | WARN | `bytes` | 发给客户端的待发数据超过 16 MiB，连接被关 |
| `user not placed on a shard`、`shard not found`、`shard address not usable` | ERROR | `user` 或 `shard`、`address`、`err` | 路由器找不到用户的分片 |
| `shard not reached` | WARN | `shard`、`address`、`err` | 路由器连不上分片进程 |
| `connection refused on the wrong shard` | WARN | `user`、`shard`、`theirs` | 用户连到了不是他的分片 |
| `cron task sent` / `cron task not started` | INFO / WARN | `job`、`thread`、`err` | 定时任务到期 |
| `memory extracted` / `memory extraction failed` | INFO / WARN | `turn` 或 `user`、`err` | 记忆提炼 |
| `turn crashed`、`tool crashed`、`agent loop step crashed`、`cron tick crashed`、`memory extraction crashed` | ERROR | `panic`、`stack`，及所在的 `thread`、`turn` 或 `tool` | 代码里的 panic 被接住：只让这一轮、这次调用或这一步失败，进程继续 |
| `agent fault` | ERROR | `thread`、`turn`、`err` | 调度里的一步出错（多半是读写库），同时给客户端发一个 `error` 事件 |
| `thread cannot advance` | ERROR | `thread`、`err` | 会话的状态读写失败，当前这一轮被判失败 |

完整的列表在代码里：`git grep -n 'slog\.' <版本>` 列出所有调用。

## 监控

引擎目前没有指标接口和链路追踪，路线图第 4 项计划通过钩子暴露队列长度、槽位占用、每用户等待、租约状态和重试次数，见[路线图](/zh/roadmap)。在那之前能用的信号有三种。

**日志。** 该报警的：`shard lost`、反复出现的 `shard lease not renewed`、各种 `crashed`、`agent fault`、`thread cannot advance`。该看比例的：`turn failed`、`model call failed` 相对 `turn ended`、`model call` 的比例。

**`Config.OnEvent`。** 宿主拿到每一个 `agent.Event`，可以自己计数：`turn_started`、`turn_completed`（事件里的 `Turn` 带 `Status`、`Usage`、`Error`）、`approval_requested`、`user_input_requested`、`error`。`OnEvent` 是在调度路径上同步调用的，里面只能做很快的事，比如加计数器，不能做网络请求。

**库。** 调度状态全在库里，可以直接查。只读打开，不要在运行中的库上写：

```sh
sqlite3 "file:/srv/ollupi/data/ollupi.sqlite?mode=ro"
```

库在运行时有 `-wal` 和 `-shm` 文件，这样打开没问题；进程停了、这两个文件不在时，`mode=ro` 打不开 WAL 模式的库（`unable to open database file`），这时查一份拷贝。

```sql
-- 各状态的轮次数。ready 是在等槽位，waitingOn* 是在等人或子 agent
SELECT status, count(*) FROM turns GROUP BY status;

-- 每个用户占着和等着的槽位
SELECT th.user_id, t.status, count(*) FROM turns t JOIN threads th ON th.id = t.thread_id
WHERE t.status IN ('ready', 'inProgress') GROUP BY th.user_id, t.status;

-- 在等审批或回答的用户
SELECT th.user_id, count(*) FROM turns t JOIN threads th ON th.id = t.thread_id
WHERE t.status IN ('waitingOnApproval', 'waitingOnUserInput') GROUP BY th.user_id;

-- 最近失败的轮次和原因
SELECT id, thread_id, error, completed_at FROM turns
WHERE status = 'failed' ORDER BY completed_at DESC LIMIT 20;

-- 租约：谁持有，还剩多少毫秒
SELECT owner, expires_at - CAST(strftime('%s', 'now') AS INTEGER) * 1000 AS ms_left FROM shard_lease;

-- 每个用户用掉的 token
SELECT th.user_id, sum(t.input_tokens), sum(t.cached_input_tokens), sum(t.output_tokens)
FROM turns t JOIN threads th ON th.id = t.thread_id GROUP BY th.user_id;
```

这些查询在 v0.11.3 的库上跑过。表结构见[持久化](/zh/engine/persistence)，表名和列名会随 migration 变。哪个容量上限在卡，见[容量规划与限流](/zh/integrate/capacity#判断哪个上限在卡)。

## 故障排查

启动阶段的报错（模型、提示词、工具白名单、令牌）列在[把引擎嵌进服务](/zh/integrate/embed#启动校验与常见错误)，这里不重复。

| 现象 | 原因 | 处理 |
|---|---|---|
| 启动报 `storage: open <路径>: invalid uri authority: ...` | `repo.Open` 或 `repo.OpenCatalog` 拿到的是相对路径 | 传绝对路径 |
| 启动报 `the database is at schema version N, from a newer ollupi; this one knows up to M` | 用旧二进制打开了新版本升级过的库 | 换回新二进制；没有回滚，见上文"升级" |
| 启动报 `approval policy "" must be one of ["untrusted" "on-request" "never"]` | 默认权限层 `Config.Settings` 没有审批策略 | 填 `ApprovalPolicy` |
| `Start` 一直不返回 | 配了 `Lease`，另一个进程持有租约：这个进程在当备用 | 正常的备用状态。查 `shard_lease`：持有者已经死了时，要等租约过期 |
| 几个进程同时启动，有的报 ``table `shards` already exists`` 或 `database is locked` | 并发第一次打开同一个新的目录库 | 先单独起一个进程把目录库建好，见[目录库](/zh/integrate/deploy#目录库) |
| 客户端 403 `host not allowed` | 请求的 `Host` 不在本机名字和 `AllowedHosts` 里；经路由器转发时是分片地址的主机名 | 把对外域名或分片地址的主机名加进 `AllowedHosts` |
| 客户端 401 `invalid or missing gateway token` | 没带令牌，令牌放在了 URL 里，或 `Authenticate` 不认 | 用 `Authorization: Bearer`，浏览器用 `ollupi.token` 子协议，见[认证](/zh/integrate/protocol#认证) |
| 401，分片日志 `connection refused on the wrong shard` | 连接绕过路由器打到了别的分片，或分片进程的 `shardID` 配错 | 客户端只连路由器；核对分片进程的 ID 和目录库 |
| 503 `no shard can take this user now`，路由器日志 `storage: no shard takes this user` | 新用户没有可放的分片：还没有分片发布，或全部 `accepting = false` | 起分片进程，或发布一个接新用户的分片 |
| 503 `the user's shard cannot be found now` | 用户被 `Place` 到了一个从没 `Publish` 过的分片 | 起那个分片，或改放置（只能在用户没有数据时） |
| 503 `the user's shard cannot be reached now; try again`，路由器日志 `shard not reached` | 分片进程死了、正在换手，或发布的地址不对 | 换手时等备用接管，客户端退避重连；持续出现时查 `shards.address` 和进程 |
| 日志 `shard lost`，进程退出 | 续约失败超过租约时长，或别的进程拿走了分片 | 让守护进程把它重启成备用；查库为什么写不进（磁盘、锁、卡住的进程） |
| 错误里出现 `storage: another process holds the shard` | 进程失去租约后还在写，被围栏挡住 | 说明 `OnLeaseLost` 之后还有组件在用库，宿主要把它们一起停掉 |
| 客户端连接被关，reason `replaced by a newer connection` | 同一用户开了第二条连接 | 每个用户一条连接，见[连接模型](/zh/integrate/protocol#连接模型) |
| 客户端连接被关，reason `client is not reading fast enough`，日志 `client fell behind` | 客户端读得太慢，待发数据超过 16 MiB | 客户端要持续读连接，不要在读循环里做慢操作 |
| 一轮失败：`agent: the turn reached its time limit of ...` | 一次占用槽位超过 `RunLimit` | 见[容量规划与限流](/zh/integrate/capacity#调大调小的后果) |
| 一轮失败：`model request failed (HTTP 429); check the selected connection and model` | 重试 8 次后仍被限流 | `calls` 超过了服务商配额，调小或提高配额 |
| 一轮失败：`model request failed (HTTP 401)` 或 `(HTTP 404)` | 密钥或模型名不对 | 核对连接的密钥、`baseURL` 和模型名 |
| 一轮失败：`model request failed; check the selected connection and try again` | 请求没拿到 HTTP 状态码，比如网络不通 | 查到服务商的网络 |
| 一轮失败：`the agent could not advance this turn: ...`，日志 `thread cannot advance` | 调度时读写库失败 | 查库：磁盘满、文件权限、是否被别的进程锁住 |
| 日志 `turn crashed` 或 `tool crashed`，带 `stack` | 引擎或工具代码 panic | 这一轮或这次调用失败，进程继续；带上 `stack` 报问题 |
| 重启后一些工具调用显示失败，提示核实 | 上个进程退出时它们正在执行，可能已生效，引擎不重跑 | 按设计如此，见[崩溃恢复](/zh/engine/persistence#崩溃恢复) |

## 代码位置

| 仓库 | 路径 | 职责 |
|---|---|---|
| ollupi | `agent/run.go`、`agent/events.go`、`agent/turns.go` | 轮次的日志，`OnEvent` 的调用 |
| ollupi | `agent/lease.go`、`agent/loop.go` | 租约日志，`Wait` 释放租约，panic 的接住 |
| ollupi | `agent/runtime/chat.go`、`agent/runtime/execute.go` | `model call`、`tool call` 日志 |
| ollupi | `agent/schedule.go` | 恢复时的日志，`thread cannot advance` 的来源 |
| ollupi | `pkg/llm/connection.go` | `safeRequestError`：模型错误不带响应正文 |
| ollupi | `pkg/jsonrpc/jsonrpc.go` | 待发数据上限 16 MiB |
| ollupi | `gateway/server.go`、`gateway/serve.go`、`gateway/router.go` | 连接、认证、路由的日志和 HTTP 错误 |
| ollupi | `repo/db.go`、`repo/migrate.go`、`repo/shard.go`、`repo/turns.go` | 打开库、版本检查、租约行、轮次状态 |
| ollupi-desktop | `sidecar/cmd/ollupid/main.go` | 一个宿主怎样设置 `slog` |
