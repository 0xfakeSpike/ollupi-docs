# 网关协议

网关（gateway）是引擎对外的唯一接口：WebSocket 上的 JSON-RPC 2.0。客户端用它管理会话（thread）、发起一轮（turn）、跟上条目（item）的变化，并回答审批和提问。方法名对齐 Codex app-server。

协议由 `gateway/protocol.go` 里的一张表定义。这张表同时做请求分发，也是 `gateway/protocol.schema.json` 的生成来源，所以文档、类型和实际行为不会各走各的。下文的数字和名称对应引擎 v0.17.2：42 个方法、12 种通知、2 种服务端请求、1 种客户端通知、17 个错误码，外加 6 个关闭码和 4 个握手拒绝状态各自的重连方式。

本页讲所有功能共用的约定：传输、认证、连接模型、关闭与重连、握手、版本校验、消息的通用约定、错误码，以及契约怎样生成和测试。每个功能的方法、通知、类型和流程按模块分页，见下面的[模块](#模块)；怎样写一个能正确重连、跟上状态的客户端见[写一个客户端](/zh/integrate/client)。

::: info 演进
v0.12.1 之后契约改过多次，客户端都要跟着改：v0.13.0 加了 `closes` 和 `handshakes` 两段，被新连接顶掉的关闭码从 1008 改成 4000（`ce11149`）；v0.16.0 把引擎重建为以对话日志为中心，`thread/started`、`thread/status/changed`、`turn/queued`、`turn/started`、`turn/completed`、`item/started`、`item/updated`、`item/completed` 八种通知换成带提交序号的 `thread/changed`、`turn/changed`、`item/changed`，`thread/read` 回报 `seq`，新增 `memory/changed`（`9b5b50b`）；同一版本加了 `settings/updatePermissions`、`mcpServer/set`、`mcpServer/delete` 和 `mcpServer/changed`（`1ae27b2`），`thread/start` 不再收权限参数（`13eafa9`）。`thread/markRead` 来自 `d6a80e8`，`-32017` 来自 v0.15.0（`bfcd398`），`-32018` 来自 `9b5b50b`。
:::

## 传输

每个 WebSocket 文本帧是一条 JSON-RPC 消息。网关接受任意路径的 `GET` 升级请求，`/healthz` 除外。

| 项 | 值 | 超出或失败时 |
|---|---|---|
| 帧类型 | 只收文本帧 | 回 `-32600`，`id` 为 `null`，连接保持 |
| 版本字段 | `jsonrpc` 必须是 `"2.0"` | 回 `-32600`，连接保持 |
| 解析失败 | | 回 `-32700`，`id` 为 `null`，连接保持 |
| 单条入站消息 | 4 MiB（`gateway/server.go` 的 `maxMessageBytes`） | 连接以 1009 关闭 |
| 入站速率 | 每秒 50 条，突发 200（`pkg/jsonrpc` 的 `messagesPerSecond`、`messageBurst`） | 不拒绝，读得慢下来 |
| 入站积压 | 64 条或 8 MiB（`maxInboxMessages`、`maxInboxBytes`） | 不拒绝，停止读取直到处理完 |
| 单次写超时 | 10 秒（`writeTimeout`） | 关闭码 1011，reason `write failed` |
| 出站队列 | 16 MiB（`maxOutboxBytes`） | 关闭码 1008，reason `client is not reading fast enough` |
| HTTP 头读取超时 | 5 秒 | 升级失败 |
| 关停等待 | 5 秒 | 网关退出前用关闭码 1001 通知客户端 |

出站队列的上限只在队列里已经有消息时才算：队列空着时，一条超过 16 MiB 的回复也会单独发出去；队列里还有别的消息时，它会让连接以 1008 关闭。`attachment/read` 读一张接近 20 MiB 的图片时，base64 之后约 27 MiB，能不能读回来取决于那一刻队列里有没有别的消息。

Go 客户端如果用 `coder/websocket`，默认读上限是 32768 字节，`tool/list` 和 `thread/read` 的回复都可能超过它，需要先调用 `SetReadLimit`。

::: info 演进
v0.12.1 的单条入站上限是 32 MiB，一条超过 16 MiB 的回复无论队列空不空都会让连接以 1008 关闭，所以大约 12 MiB 以上的图片附件读不回来。v0.14.0 让大回复在队列空时单独发出（`2caad43`），并限制每个客户端的入站速率（`c210a7d`）；v0.15.0 把入站上限降到 4 MiB（`fdefa84`）。
:::

## 认证

一次升级请求依次经过这些检查（`gateway/server.go` 的 `ServeHTTP`、`gateway/auth.go`）：

| 顺序 | 检查 | 依据 | 失败 |
|---|---|---|---|
| 0 | 健康检查 | 路径是 `/healthz` 时直接回 200，不要令牌 | |
| 1 | Host | `localhost`、`127.0.0.1`、`::1`，加上 `Options.AllowedHosts` | 403 `host not allowed` |
| 2 | 令牌 | `Options.Authenticate`，最多等 10 秒；单用户时用 `Options.Token` 做常量时间比较 | 不认识的令牌 401 `invalid or missing gateway token`；暂时查不了 503，带 `Retry-After` |
| 3 | 接纳速率 | `Options.Connections` 的 `Rate`、`Burst`，默认每秒 200 个、突发 400 | 503 `too many connections are starting; try again`，带 `Retry-After` |
| 4 | 用户在不在本分片 | `Options.Admit`（分片部署时是 `shard.Member.Admit`），最多等 10 秒 | 503 `this user is not served here now; try again`，带 `Retry-After` |
| 5 | 用户 | `app.EnsureUser` 确保用户行、设置和本机执行环境存在；同一进程里每个用户只做一次 | 500 |
| 6 | Origin | 没有 Origin 头或与 Host 相同时放行；否则匹配 `localhost:*`、`127.0.0.1:*`、`[::1]:*`，加上 `Options.AllowedOrigins` | 403 |

`Retry-After` 是 1 到 `RetryWithin` 秒之间的随机整数，默认 `RetryWithin` 是 5 秒，让一起被拒的客户端错开回来。

令牌有两种传法，都不进 URL，因为访问日志会保留 URL：

- `Authorization: Bearer <token>`。
- 浏览器不能设置这个头，改用子协议：`new WebSocket(url, ["ollupi.token", token])`。网关读 `ollupi.token` 后面紧跟的那一项，握手只回 `ollupi.token`，不回显令牌。

`NewServer` 要求 `Token` 或 `Authenticate` 二选一，否则启动失败。令牌的签发不归引擎管：`Authenticate` 只回答"这个令牌是谁的"，见[认证](/zh/integrate/extend#认证)。

## 连接模型

- **每个用户最多四条连接。** 一个用户可以同时开四条连接（`Connections.PerKey`，默认 4），比如每台设备一条，每条都收到这个用户的全部变化和全部服务端请求。第五条连上时，最早的那条以 4000 `replaced by a newer connection` 关闭。
- **心跳和寿命。** 网关每 30 秒 ping 一次。从 ping 发出起网关一直在等这条连接的下一条消息、15 秒内却什么也没收到，就直接断开（客户端看到 1006）；网关因入站限速或积压暂停读取、或还在处理已读进来的消息时不算，这时 pong 排在没读的请求后面，客户端照旧被读得慢下来。每条连接在打开后 15 到 20 小时之间的随机时刻以 1001 `connection reached its age; reconnect` 关闭，低于 Google Cloud 负载均衡器保持 WebSocket 的 24 小时，同时连上的客户端也不会同时被切断。这些值都在 `Options.Connections` 里，零值时取 `gateway.DefaultConnections`。
- **请求串行处理。** 网关在一个循环里按到达顺序同步执行方法，同一连接上的下一条请求要等上一条的回复写入出站队列。
- **事件不缓存。** 连接在 `initialize` 回复之后才订阅这个用户的变化，只收到订阅之后提交的变化；断线期间的变化不补发。客户端重连后用 `thread/read` 或 `thread/resume` 读库里的状态，用回复里的 `seq` 对齐之后的通知，见[写一个客户端](/zh/integrate/client#本地状态)。
- **通知可能先于回复。** 一次调用提交的变化在提交之后立刻进入每条连接的出站队列，而回复要等处理函数返回才入队，所以 `thread/start` 的 `thread/changed`、`turn/start` 的 `turn/changed` 和 `item/changed` 都排在各自的回复之前。客户端不能假设先收到回复。
- **用户隔离。** 其他用户的会话对当前用户表现为不存在，返回 `-32004`。

## 关闭与重连

契约的 `closes` 和 `handshakes` 两段列出网关会用的每个 WebSocket 关闭码和每个握手拒绝状态，以及客户端接下来该怎么做（`reconnect`）。

| 关闭码 | `name` | `reconnect` | 网关什么时候用 |
|---|---|---|---|
| 1001 | `goingAway` | `soon` | 网关关停（`server shutting down`）；连接到了寿命（`connection reached its age; reconnect`） |
| 1006 | `abnormal` | `backoff` | 没有关闭帧：网络断开、进程被杀、心跳超时 |
| 1008 | `policyViolation` | `backoff` | 出站队列超过 16 MiB（`client is not reading fast enough`） |
| 1009 | `messageTooBig` | `backoff` | 入站消息超过 4 MiB |
| 1011 | `internalError` | `backoff` | 写超时（`write failed`）、读循环出错（`connection error`）、初始化时读不出待回答的请求（`pending requests could not be read`） |
| 4000 | `replaced` | `never` | 同一用户的第五条连接顶掉了这一条 |

| 握手状态 | `name` | `reconnect` | 什么时候 |
|---|---|---|---|
| 401 | `unauthorized` | `never` | 令牌不认识 |
| 403 | `forbidden` | `never` | `Host` 或 `Origin` 不在名单里 |
| 500 | `internalError` | `backoff` | 用户行建不出来 |
| 503 | `unavailable` | `retryAfter` | 令牌暂时查不了、接纳速率超限、用户不在这个分片、路由器找不到或连不上分片 |

`reconnect` 的四个值：`soon` 是随机等 0 到 10 秒再连；`backoff` 是从 1 秒开始、每次加倍、到 60 秒为止的退避，每次在上限以内随机取；`retryAfter` 是等响应头 `Retry-After` 给的秒数，没有这个头时按 `backoff`；`never` 是不要自己重连，交给用户决定。重连之后要重新读状态，因为断线期间什么都没收到。浏览器和 Node 自带的 `WebSocket` 拿不到握手的 HTTP 状态码，怎样处理见[写一个客户端](/zh/integrate/client#关闭码)。

## 握手

1. 客户端发 `initialize`，带 `clientInfo: {name, version}`。
2. 网关回 `serverInfo: {name: "ollupi", version}` 和 `protocolSha256`。
3. 回复入队之后，这条连接订阅这个用户的变化，标记为已初始化，并把这个用户所有在等回答的审批和提问按发起时间重发一遍。读不出来时以 1011 关闭。
4. 客户端发 `initialized` 通知。

| 情况 | 结果 |
|---|---|
| 初始化之前调用任何其他方法，包括不存在的方法 | `-32002` `call initialize first` |
| 重复 `initialize` | `-32600` `already initialized` |
| 未知方法（已初始化） | `-32601` |
| 任何客户端通知，包括未知的 | 不回复，不记录 |

网关不等 `initialized`：第 3 步在 `initialize` 回复之后就发生，收到这条通知也不做任何事。契约里保留它，客户端照发即可。这意味着客户端必须在 `initialize` 返回时已经能处理服务端请求。

`serverInfo.version` 取自 `debug.ReadBuildInfo().Main.Version`，也就是最终二进制主模块的版本：引擎被嵌入时不是引擎自己的版本，本地构建时是 `(devel)`，读不到构建信息时是 `unknown`。判断协议是否兼容要看 `protocolSha256`。

## 版本校验

`protocolSha256` 是嵌入二进制的 `protocol.schema.json` 的 SHA-256，v0.17.2 是 `adb6760b0541dd43854c18b51780af476e68bc4528a611cdfa1e1df5ba268e0b`。客户端把它和自己生成类型时用的契约文件比较。

网关不做校验，也不拒绝不一致的客户端。怎么处理由客户端决定。桌面端的做法：`packages/protocol` 生成时把摘要写进常量 `PROTOCOL_SHA256`，连接后比较；不一致时显示一条提示，连接继续工作。

## 模块

| 模块 | 方法 | 通知 | 服务端请求 |
|---|---|---|---|
| [会话](/zh/integrate/protocol/threads) | `thread/start`、`thread/read`、`thread/resume`、`thread/list`、`thread/rename`、`thread/markRead`、`thread/archive`、`thread/delete`、`thread/updatePermissions` | `thread/changed` | |
| [一轮与条目](/zh/integrate/protocol/turns) | `turn/start`、`turn/steer`、`turn/interrupt`、`attachment/read` | `turn/changed`、`item/changed`、`item/agentMessage/delta`、`item/reasoning/textDelta`、`error` | |
| [审批与提问](/zh/integrate/protocol/approvals) | | | `item/toolCall/requestApproval`、`item/tool/requestUserInput` |
| [权限](/zh/integrate/protocol/permissions) | `thread/updatePermissions`、`workspace/updatePermissions`、`settings/updatePermissions` 的权限部分 | | |
| [工作区与执行环境](/zh/integrate/protocol/workspaces) | `workspace/list`、`workspace/add`、`workspace/rename`、`workspace/move`、`workspace/archive`、`workspace/updatePermissions`、`environment/list`、`environment/add`、`environment/rename`、`environment/delete` | `workspace/changed`、`environment/changed` | |
| [模型、工具与 MCP](/zh/integrate/protocol/models-tools) | `model/list`、`tool/list`、`mcpServer/list`、`mcpServer/set`、`mcpServer/delete` | `mcpServer/changed` | |
| [定时任务](/zh/integrate/protocol/cron) | `cron/list`、`cron/create`、`cron/pause`、`cron/delete` | `cron/changed` | |
| [记忆](/zh/integrate/protocol/memory) | `memory/list`、`memory/status`、`memory/update`、`memory/move`、`memory/forget` | `memory/changed` | |
| [搜索](/zh/integrate/protocol/search) | `search` | | |
| [设置](/zh/integrate/protocol/settings) | `settings/read`、`settings/update`、`settings/updatePermissions` | `settings/changed` | |

`initialize` 和客户端通知 `initialized` 在上面的[握手](#握手)里。按类型名查它在哪个模块，见[类型索引](/zh/integrate/protocol-types)。

## 通用约定

**请求。** 参数全部用严格解码：多余字段返回 `-32602`，比如还在给 `thread/start` 传 `permissions` 的旧客户端会被拒绝。`params` 省略时按 `{}` 处理。契约里标为必填的字段，网关解码时并不检查它是否出现（Go 的 JSON 解码不强制必填），缺了按零值处理；只有几处显式检查，比如 `thread/archive` 的 `archived`、`turn/steer` 的 `expectedTurnId`、`turn/interrupt` 的 `turnId`。各模块的参数表里 `?` 表示可选。

**字段。**

- 可选字段在 Go 端用 `omitempty`：空字符串、`0`、`false`、空数组都不发，客户端要把"缺"当成零值。
- 时间都是 RFC 3339 的 UTC 字符串，带纳秒，如 `2026-11-18T12:14:04.244635Z`。
- ID 是字符串，通常是 UUID。客户端不要假设 ID 的格式。
- 多数字段是 camelCase。直接给模型看的类型（工具描述、内置工具的参数和输出）用 snake_case，如 `input_schema`、`exit_code`、`work_dir`，这是模型那一侧的命名。

**通知。** 会话、轮次和条目的变化都来自对话日志的一次提交：同一次提交改变的会话行、轮次和条目各发一条 `thread/changed`、`turn/changed`、`item/changed`，带的是提交之后的完整行和这次提交的序号 `seq`。客户端按 `id` 整行替换，不用做字段合并；`seq` 不大于自己读到的那一页的 `seq` 的通知已经包含在那一页里，丢掉即可，见[写一个客户端](/zh/integrate/client#用-seq-对齐)。`*/changed` 通知里对象为 `null` 表示它已被删除。

`seq` 是这个分片的存储里所有提交共用的计数，每次提交加一，不是每个会话各自的计数；它和条目的 `seq`（条目在会话日志里的位置）是两回事。

## 错误码

| 码 | 名称 | 来源 |
|---|---|---|
| `-32700` | `parseError` | 消息不是合法 JSON |
| `-32600` | `invalidRequest` | 非文本帧、版本不对、不是请求也不是响应、重复初始化 |
| `-32601` | `methodNotFound` | 方法不存在 |
| `-32602` | `invalidParams` | 参数解码失败；处理函数的显式检查（`limit`、`beforeSeq`、`archived`、`expectedTurnId`、`turnId`、`paused`、`input` 的类型、`settings/update` 一项都没给）；`app.ErrInvalidMessage`、`ErrInvalidAnswer`、`ErrInvalidDecision`、`ErrInvalidPath`、`ErrInvalidQuery`、`ErrEnvironmentInUse`；`account.ErrInvalidName`、`ErrInvalidMCPServer`；`policy.ErrInvalidSettings`；`memory.ErrInvalidChange`；`kit.ErrUnknownTool`、`ErrInvalidArguments`；`cron.ErrInvalidJob` |
| `-32603` | `internalError` | 结果无法编码 |
| `-32000` | `serverError` | 其余所有错误 |
| `-32002` | `notInitialized` | 未初始化 |
| `-32004` | `notFound` | `store.ErrNotFound`，包括别的用户的数据 |
| `-32010` | `noActiveTurn` | 会话没有进行中的一轮 |
| `-32011` | `turnMismatch` | 指名的一轮不是进行中的那一轮 |
| `-32012` | `noSuchRequest` | 会话没有在等这个请求（`app.ErrNoSuchRequest`）。它只在客户端回答服务端请求时发生，网关把它的文字放进 `error` 通知，见[审批与提问](/zh/integrate/protocol/approvals#回复的结果) |
| `-32013` | `subagentThread` | 子 agent 会话不接受这个操作 |
| `-32014` | `workspaceArchived` | 工作区已归档 |
| `-32015` | `threadArchived` | 会话已归档 |
| `-32016` | `threadBusy` | 会话有进行中或排队的一轮；`workspace/move` 时指工作区里有会话没空闲（`ErrWorkspaceBusy`）；`turn/start` 时指这个会话已经有 20 条消息在排队（`ErrQueueFull`） |
| `-32017` | `searchTimedOut` | 搜索超过 5 秒，见[搜索](/zh/integrate/protocol/search) |
| `-32018` | `refused` | 要写的记录接不上会话日志（`conversation.ErrRefused`）：`conversation.Check` 拒绝了它，通常是两个操作赛跑 |

`serverError` 把内部错误挡在服务端。`errorCodes` 表里的错误把原文发给客户端；不在表里的错误客户端只收到 `the request could not be completed`，这样数据库路径之类的内容不会外泄。`TestAnUnknownErrorStaysOnTheServer` 守着这条。

## 一张表分发和生成 schema

`protocol.go` 里的变量 `protocol` 声明所有消息：

```go
var protocol = struct {
	methods             map[string]method
	notifications       map[string]reflect.Type
	serverRequests      map[string]serverRequest
	clientNotifications map[string]reflect.Type
	errors              map[int]string
	closes              map[int]Ending
	handshakes          map[int]Ending
	limits              Limits
}{ /* ... */ }
```

每个方法用泛型 `handle` 或 `handleThen` 注册：

```go
"thread/start":  handle((*conn).threadStart),
"thread/resume": handleThen(threadPage(true)),
```

`handleThen[P, R]` 同时做两件事：记下参数和结果的 `reflect.Type`，生成解码、调用、错误映射的闭包。处理函数还可以返回一个在回复入队之后才执行的函数：`initialize` 用它开始订阅，`thread/resume` 用它重发请求。`conn.Call` 在运行时查这张表分发。`gateway/schema_test.go` 里的生成器读同一张表写出 schema。一个方法只要能被调用，就一定在 schema 里。

| 契约段 | 来源 | 内容 |
|---|---|---|
| `methods` | `protocol.methods` | 42 个方法的 `params`、`result` |
| `notifications` | `protocol.notifications` | 12 种通知的载荷 |
| `serverRequests` | `protocol.serverRequests` | 2 种服务端请求 |
| `clientNotifications` | `protocol.clientNotifications` | `initialized` |
| `errors` | `protocol.errors` | 17 个错误码到名称 |
| `closes` | `protocol.closes` | 6 个关闭码的名称和 `reconnect`，见[关闭与重连](#关闭与重连) |
| `handshakes` | `protocol.handshakes` | 4 个握手拒绝状态的名称和 `reconnect` |
| `limits` | `protocol.limits` | 搜索的上限：`searchRunes` 200、`searchTerms` 8，见[搜索](/zh/integrate/protocol/search) |
| `builtinTools` | `schema_test.go` | 10 个内置工具的参数和输出 |
| `providers` | `schema_test.go` | `cron`、`skills`、`memory`：引擎自带的几个工具提供方 id，实际取值不止这些，见[模型、工具与 MCP](/zh/integrate/protocol/models-tools) |
| `$defs` | 从以上类型遍历得到 | 134 个命名类型，字段见[协议类型索引](/zh/integrate/protocol-types) |

`builtinTools` 收哪些工具、其余工具调用怎样显示、工具名的规则，见[模型、工具与 MCP](/zh/integrate/protocol/models-tools)。

生成器对协议类型有约束，违反时生成失败：

- 匿名结构体不能进协议，必须有名字并且导出。
- 命名字符串类型必须在 `enums` 里给出取值列表，或者列入 `plainStrings`。
- map 的键必须是字符串，命名切片要在 `special` 里给 schema。
- 两个类型重名时要在 `defNames` 里改名。`defNames` 也给几个类型起了契约里的名字，比如 `policy.Settings` 叫 `PermissionSettings`，`agent.Name` 叫 `AgentRole`，`workspace.Prepared` 叫 `PreparedExecution`。

枚举的取值列表写在常量旁边，代码也在用。`TestEnumValuesMatchConstants` 解析 Go 源码，确认列表和常量一致。

`protocol.schema.json` 通过 `//go:embed` 编进二进制，`protocolSHA256` 在包初始化时算出。修改协议后重新生成：

```bash
GOFLAGS=-tags=sqlite_fts5 go generate ./gateway
```

这份文件是提交进仓库的跨语言契约。桌面端不解析 Go，`packages/protocol/scripts/generate.mjs` 用 `go list -m` 找到 sidecar 依赖的那个引擎版本，读它的契约，生成 TypeScript 类型和方法表；`pnpm protocol:check` 检查生成物是否过期。

## 契约测试

| 层 | 位置 | 做什么 |
|---|---|---|
| 生成物一致 | `TestProtocolSchema` | 重新生成并和提交的文件逐字节比较 |
| 枚举一致 | `TestEnumValuesMatchConstants` | 契约里的取值列表和 Go 常量一致 |
| 错误不外泄 | `TestAnUnknownErrorStaysOnTheServer` | 不在表里的错误只给客户端一句固定的话 |
| 连接流程 | `TestAClientHearsWhatChangesAndAnswersWhatWaitsOnIt` | 用真实的 sqlite 存储和网关走一遍：初始化、建会话、发消息，收到带 `seq` 的 `item/changed`，`thread/read` 的 `seq` 不小于它；往日志里写一条要审批的调用，收到 `item/toolCall/requestApproval`，回答后收到带决定的 `item/changed` 和 `seq` 更大的 `thread/changed` |
| 录制回放 | 桌面端 `packages/protocol/src/contract.test.ts` | 用当前 sidecar 录下的会话校验生成的类型 |

引擎这边没有逐条按契约校验真实流量的测试：契约和实际消息一致，靠的是两者出自同一张表和同一组 Go 类型。桌面端的 `packages/protocol/scripts/record-session.mjs` 驱动 sidecar 录下一个会话的全部 JSON-RPC 消息，`contract.test.ts` 用 Ajv 逐条校验，并要求录制时的摘要等于当前 `PROTOCOL_SHA256`。

::: info 演进
v0.12.1 的 `gateway/traffic_test.go` 里有 `TestTrafficMatchesContract`：起真实网关和 agent，只把模型换成假服务，按契约校验每条消息，并检查每个方法、每种通知、每个内置工具都覆盖到。v0.16.0 重建网关时它被删掉（`06f08ab`），换成上表的连接流程测试（`9b5b50b`），覆盖面小了很多。
:::

## 路由

多分片部署时，客户端只连一个地址，不知道自己在哪个分片（shard）。有两条路把连接送到分片：负载均衡器能通过 Envoy 外部处理协议回调时（如 Google Cloud 应用负载均衡器的路由扩展），`router/extproc` 在握手的 `x-ollupi-shard` 头里告诉它分片，由负载均衡器持有连接；放不下的连接、以及没有这种负载均衡器的部署，由 `router.Router` 反向代理。两者都用 `router.Locator` 认令牌、查目录库，自身不保存状态。

| `router.Router` 的失败 | 状态码 |
|---|---|
| 令牌不认识 | 401 |
| 令牌查不了、用户放不到分片上 | 503 `no shard can take this user now` |
| 分片暂时没有持有者 | 503 `no process holds the user's shard now; try again` |
| 分片地址不对或连不上 | 503 |

分片这一侧用 `gateway.Options.Admit`（设成 `shard.Member.Admit`）只放行分到本分片的用户，别的用户拿到带 `Retry-After` 的 503。部署方式见[多用户与分片部署](/zh/integrate/deploy)，机制见[分片](/zh/engine/sharding)。

## 代码位置

| 仓库 | 路径 | 职责 |
|---|---|---|
| ollupi | `gateway/protocol.go` | 协议表、错误码、关闭码和握手状态、参数和结果类型、错误映射 |
| ollupi | `gateway/wire.go` | 发给客户端的行：`ThreadRow`、`TurnRow`、`ItemRow` 等，以及从存储类型的转换 |
| ollupi | `gateway/protocol.schema.json` | 生成的契约 |
| ollupi | `gateway/server.go` | 升级、连接、`initialize`、变化到通知的映射、服务端请求和回复 |
| ollupi | `gateway/auth.go` | Host 和令牌检查 |
| ollupi | `gateway/serve.go` | `Options`、`NewServer`、`Serve`、`DefaultConnections` |
| ollupi | `gateway/threads.go`、`gateway/owned.go` | 各组方法的处理函数 |
| ollupi | `gateway/schema_test.go` | schema 生成器和枚举检查 |
| ollupi | `gateway/gateway_test.go` | 错误映射和连接流程测试 |
| ollupi | `pkg/jsonrpc/jsonrpc.go` | JSON-RPC 编解码、读循环、速率、出站队列、服务端请求的 `id` |
| ollupi | `pkg/wshub/wshub.go` | 每用户连接数、接纳速率、心跳、寿命 |
| ollupi | `auth/auth.go` | `Authenticate`、`TokenOf`、`/healthz` |
| ollupi | `store/feed.go` | 把每次提交的变化交给订阅者 |
| ollupi | `router/router.go`、`router/extproc` | 多分片路由 |
| ollupi-desktop | `packages/protocol/scripts/generate.mjs` | 从契约生成 TypeScript 和校验器 |
| ollupi-desktop | `packages/protocol/src/contract.test.ts` | 校验录制的会话 |
| ollupi-desktop | `apps/desktop/src/renderer/src/gateway/session.ts` | 连接、重连、协议摘要比较 |
