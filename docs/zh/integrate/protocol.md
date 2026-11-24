# 网关协议

网关（gateway）是引擎对外的唯一接口：WebSocket 上的 JSON-RPC 2.0。客户端用它管理会话（thread）、发起一轮（turn）、跟上条目（item）的变化、回答审批和提问，也用它读写工作区、定时任务、记忆、待办和用量。

协议由 `gateway/protocol.go` 里的变量 `protocol` 声明：方法、通知、服务端请求、客户端通知、错误码、关闭码、握手状态都写在这一处。同一张表既做运行时分发，又是 `gateway/protocol.schema.json` 的生成来源，所以契约、类型和实际行为不会各走各的。当前有 49 个方法、13 种通知、2 种服务端请求、1 种客户端通知、18 个错误码、6 个关闭码、4 个握手拒绝状态。按模块看方法见[模块](#模块)，按类型名查归属见[类型索引](/zh/integrate/protocol-types)。

## 传输

每个 WebSocket 文本帧是一条 JSON-RPC 消息。网关接受任意路径的 `GET` 升级请求。

| 项 | 值 | 失败时 |
|---|---|---|
| 帧类型、版本 | 只收文本帧，`jsonrpc` 必须是 `"2.0"` | `-32600`，`id` 为 `null`，连接保持 |
| 单条入站消息 | 4 MiB（`maxMessageBytes`；`pkg/jsonrpc`） | 连接以 1009 关闭 |
| 入站速率、积压 | 每秒 50 条、突发 200；积压 64 条或 8 MiB | 不拒绝，读得慢下来 |
| 出站队列 | 16 MiB（`maxOutboxBytes`） | 关闭码 1008，`client is not reading fast enough` |

出站队列上限只在队列非空时才算：空队列时一条超过 16 MiB 的回复也能单独发出。用 `coder/websocket` 的客户端要先把默认 32768 字节的读上限调大。

## 认证

升级请求依次检查（`gateway/server.go` 的 `ServeHTTP`、`gateway/auth.go`）：

| 检查 | 依据 | 失败 |
|---|---|---|
| Host | `localhost`、`127.0.0.1`、`::1` 加 `Options.AllowedHosts` | 403 `host not allowed` |
| 令牌 | `Options.Authenticate`（最多等 10 秒）；单用户时比 `Options.Token` | 401 `invalid or missing gateway token`，暂时查不了 503 |
| 接纳速率 | `Options.Connections` 的 `Rate`、`Burst`，默认每秒 200、突发 400 | 503 `too many connections are starting; try again` |

之后 `app.EnsureUser` 建好用户行、设置和本机执行环境（失败回 500），再校验 Origin；分片部署时 `Options.Admit` 只放行分到本分片的用户，否则 503 `this user is not served here now; try again`。`/healthz` 直接回 200；503 都带 `Retry-After`，取值是 1 到 `RetryWithin` 秒之间的随机整数，默认上限 5 秒。

令牌不进 URL（访问日志会保留 URL），有两种传法：`Authorization: Bearer <token>`；浏览器改用子协议 `new WebSocket(url, ["ollupi.token", token])`，网关读 `ollupi.token` 后面紧跟的那一项。`NewServer` 要求 `Token` 或 `Authenticate` 二选一，否则启动失败；令牌的签发不归引擎管，见[认证](/zh/integrate/extend#认证)。

## 连接模型

- **每个用户最多四条连接**（`Connections.PerKey`，默认 4），每条都收到全部变化和全部服务端请求，请求按到达顺序串行执行；第五条连上时最早的那条以 4000 `replaced by a newer connection` 关闭。
- **心跳和寿命。** 每 30 秒 ping 一次，从 ping 发出起 15 秒内没收到任何消息就断开（客户端看到 1006；因限速或积压暂停读取时不算）。连接在打开后 15 到 20 小时之间的随机时刻以 1001 `connection reached its age; reconnect` 关闭。零值取 `gateway.DefaultConnections`。
- **事件不缓存。** 连接在 `initialize` 回复之后才订阅这个用户的变化，断线期间的变化不补发；重连后用 `thread/read` 或 `thread/resume` 读库里的状态，见[写一个客户端](/zh/integrate/client#本地状态)。
- **通知先于回复。** 变化在提交后立刻入队，回复要等处理函数返回，所以 `thread/start`、`turn/start` 的 `*/changed` 排在回复之前。
- **用户隔离。** 其他用户的会话对当前用户不存在，返回 `-32004`。

## 关闭与重连

契约的 `closes`、`handshakes` 段给出每个关闭码和握手拒绝状态的重连方式（`reconnect`）。

| 关闭码 | `name` | `reconnect` | 什么时候 |
|---|---|---|---|
| 1001 | `goingAway` | `soon` | 关停；连接到了寿命 |
| 1006 | `abnormal` | `backoff` | 没有关闭帧：网络断开、进程被杀、心跳超时 |
| 1008 | `policyViolation` | `backoff` | 出站队列超过 16 MiB |
| 1009 | `messageTooBig` | `backoff` | 入站消息超过 4 MiB |
| 1011 | `internalError` | `backoff` | 写超时、读循环出错、初始化时读不出待回答的请求 |
| 4000 | `replaced` | `never` | 同一用户的第五条连接顶掉了这一条 |

握手被拒按 HTTP 状态码区分：401 `unauthorized`、403 `forbidden` 是 `never`，500 `internalError` 是 `backoff`，503 `unavailable` 是 `retryAfter`，要等响应头 `Retry-After`。重连后要重新读状态；浏览器和 Node 自带的 `WebSocket` 拿不到握手的 HTTP 状态码，处理办法见[写一个客户端](/zh/integrate/client#关闭码)。

## 握手

1. 客户端发 `initialize`，带 `clientInfo: {name, version}`。
2. 网关回 `serverInfo: {name: "ollupi", version}` 和 `protocolSha256`。
3. 回复入队之后，这条连接订阅这个用户的变化，标记为已初始化，并把这个用户所有在等回答的审批和提问按发起时间重发一遍；读不出来时以 1011 关闭。
4. 客户端发 `initialized` 通知。

初始化之前调用其他方法（包括不存在的）回 `-32002` `call initialize first`；重复 `initialize` 回 `-32600` `already initialized`；已初始化后的未知方法回 `-32601`；客户端通知一律不回复。网关不等 `initialized`，第 3 步在 `initialize` 回复之后就发生，客户端必须在 `initialize` 返回时就能处理服务端请求。

`serverInfo.version` 取自 `debug.ReadBuildInfo().Main.Version`，引擎被嵌入时不是引擎自己的版本，本地构建时是 `(devel)`。判断兼容要看 `protocolSha256`，即嵌入二进制的 `protocol.schema.json` 的 SHA-256；网关不校验也不拒绝不一致的客户端，桌面端把摘要写进 `PROTOCOL_SHA256`，连接后比较，不一致时只提示一句。

## 模块

| 模块 | 方法 | 通知 | 服务端请求 |
|---|---|---|---|
| [会话](/zh/integrate/protocol/threads) | `thread/start`、`thread/read`、`thread/resume`、`thread/list`、`thread/rename`、`thread/markRead`、`thread/archive`、`thread/delete`、`thread/updatePermissions` | `thread/changed` | |
| [一轮与条目](/zh/integrate/protocol/turns) | `turn/start`、`turn/steer`、`turn/interrupt`、`attachment/read` | `turn/changed`、`item/changed`、`item/agentMessage/delta`、`item/reasoning/textDelta`、`error` | |
| [审批与提问](/zh/integrate/protocol/approvals) | | | `item/toolCall/requestApproval`、`item/tool/requestUserInput` |
| [权限](/zh/integrate/protocol/permissions) | `thread/updatePermissions`、`workspace/updatePermissions`、`settings/updatePermissions` | | |
| [工作区与执行环境](/zh/integrate/protocol/workspaces) | `workspace/list`、`add`、`rename`、`move`、`archive`、`setKind`、`updatePermissions`、`updateInstructions`、`updateProviders`；`environment/list`、`add`、`rename`、`delete` | `workspace/changed`、`environment/changed` | |
| [模型、工具与 MCP](/zh/integrate/protocol/models-tools) | `model/list`、`tool/list`、`mcpServer/list`、`set`、`delete` | `mcpServer/changed` | |
| [定时任务](/zh/integrate/protocol/cron) | `cron/list`、`create`、`pause`、`delete` | `cron/changed` | |
| [记忆](/zh/integrate/protocol/memory) | `memory/list`、`status`、`update`、`move`、`forget` | `memory/changed` | |
| [搜索](/zh/integrate/protocol/search) | `search` | | |
| [设置](/zh/integrate/protocol/settings) | `settings/read`、`update`、`updatePermissions` | `settings/changed` | |
| [待办](/zh/integrate/protocol/todos) | `todo/list`、`add`、`update` | `todo/changed` | |
| [用量](/zh/integrate/protocol/usage) | `usage/query` | | |

`initialize`、`initialized` 见[握手](#握手)。

## 通用约定

**请求。** 参数用严格解码：多余字段返回 `-32602`，比如还在给 `thread/start` 传 `permissions` 的旧客户端会被拒绝；`params` 省略按 `{}` 处理。契约里标为必填的字段解码时不检查是否出现，缺了按零值处理；显式检查的有 `thread/archive` 和 `workspace/archive` 的 `archived`、`cron/pause` 的 `paused`、`turn/steer` 的 `expectedTurnId`、`turn/interrupt` 的 `turnId`。参数表里 `?` 表示可选。

**字段。** 可选字段用 `omitempty`，空字符串、`0`、`false`、空数组都不发，客户端要把"缺"当成零值。时间是 RFC 3339 的 UTC 字符串，带纳秒；ID 是字符串，通常是 UUID，待办的 `id` 是整数。多数字段是 camelCase，给模型看的类型用 snake_case（`input_schema`、`exit_code`）。

**通知。** 会话、轮次和条目的变化都来自对话日志的一次提交：同一次提交改变的会话行、轮次、条目各发一条 `thread/changed`、`turn/changed`、`item/changed`，带提交之后的完整行和这次提交的序号 `seq`。客户端按 `id` 整行替换，不做字段合并；`seq` 不大于自己读到的那一页的 `seq` 的通知已包含在那一页里，丢掉即可，见[写一个客户端](/zh/integrate/client#用-seq-对齐)。`*/changed` 里对象为 `null` 表示已删除。`seq` 是整个分片的提交计数，和条目的 `seq`（条目在日志里的位置）不同。

## 错误码

| 码 | 名称 | 来源 |
|---|---|---|
| `-32700` | `parseError` | 消息不是合法 JSON |
| `-32600` | `invalidRequest` | 非文本帧、版本不对、不是请求也不是响应、重复初始化 |
| `-32601` | `methodNotFound` | 方法不存在 |
| `-32602` | `invalidParams` | 参数解码失败；`limit`、`beforeSeq`、`archived`、`expectedTurnId`、`turnId`、`paused` 等显式检查；`app.ErrInvalid*`（消息、回答、决定、路径、查询、待办）、`ErrEnvironmentInUse`、`account.ErrInvalidName`、`ErrInvalidMCPServer`、`policy.ErrInvalidSettings`、`memory.ErrInvalidChange`、`kit.ErrUnknownTool`、`kit.ErrInvalidArguments`、`cron.ErrInvalidJob` |
| `-32603` | `internalError` | 结果无法编码 |
| `-32000` | `serverError` | 其余所有错误 |
| `-32002` | `notInitialized` | 未初始化 |
| `-32004` | `notFound` | `store.ErrNotFound`，包括别的用户的数据 |
| `-32010` | `noActiveTurn` | 会话没有进行中的一轮 |
| `-32011` | `turnMismatch` | 指名的一轮不是进行中的那一轮 |
| `-32012` | `noSuchRequest` | 会话没有在等这个请求，只在回答服务端请求时发生，见[审批与提问](/zh/integrate/protocol/approvals#回复的结果) |
| `-32014` | `workspaceArchived` | 工作区已归档 |
| `-32015` | `threadArchived` | 会话已归档 |
| `-32016` | `threadBusy` | 会话有进行中或排队的一轮；`workspace/move` 时指工作区里有会话没空闲；`turn/start` 时指已有 20 条在排队 |
| `-32017` | `searchTimedOut` | 搜索超过 5 秒，见[搜索](/zh/integrate/protocol/search) |
| `-32018` | `refused` | 记录接不上会话日志（`conversation.ErrRefused`），通常是两个操作赛跑 |
| `-32020` | `secondHub` | 用户已有一个 `kind=hub` 的工作区，见 [workspace/setKind](/zh/integrate/protocol/workspaces#workspace-setkind) |
| `-32021` | `noHub` | 把工作区改成 `hub`，而这个部署没开 hub |

`errorCodes` 里的错误把原文发给客户端；不在表里的只回 `the request could not be completed`，数据库路径之类不会外泄（`TestAnUnknownErrorStaysOnTheServer`）。

## 契约的生成与测试

每个方法用泛型 `handle` 或 `handleThen` 注册，后者记下参数和结果的 `reflect.Type`。`conn.Call` 查这张表分发，`gateway/schema_test.go` 的生成器读同一张表写出 schema，所以能被调用的方法一定在 schema 里；`$defs` 从这些类型遍历得到 166 个命名类型，见[协议类型索引](/zh/integrate/protocol-types)。生成器要求协议类型命名并导出、命名字符串类型给全取值列表，重名时在 `defNames` 里改名（如 `policy.Settings` 叫 `PermissionSettings`）。

修改协议后跑 `GOFLAGS=-tags=sqlite_fts5 go generate ./gateway` 重新生成，schema 通过 `//go:embed` 编进二进制；桌面端 `packages/protocol/scripts/generate.mjs` 读同一份契约生成 TypeScript 类型。引擎不逐条校验真实流量，一致靠两者出自同一张表。

## 路由

多分片部署时客户端只连一个地址，不知道自己在哪个分片。负载均衡器能在 Envoy 外部处理协议回调时，`router/extproc` 在握手的 `x-ollupi-shard` 头里告诉它分片；其余情况走 `router.Router` 反向代理。两者都用 `router.Locator` 认令牌、查目录库，自身不保存状态；分片一侧用 `Options.Admit` 只放行分到本分片的用户。见[多用户与分片部署](/zh/integrate/deploy)。

## 代码位置

| 仓库 | 路径 | 职责 |
|---|---|---|
| ollupi | `gateway/protocol.go` | 协议表、错误码、关闭码和握手状态、参数和结果类型 |
| ollupi | `gateway/wire.go`、`gateway/protocol.schema.json` | 发给客户端的行；生成的契约 |
| ollupi | `gateway/server.go`、`gateway/auth.go` | 升级、连接、`initialize`、变化到通知的映射；Host 和令牌检查 |
| ollupi | `gateway/serve.go`、`gateway/threads.go`、`gateway/owned.go` | `Options` 与默认连接参数；会话、工作区、待办、用量的处理函数 |
| ollupi | `gateway/schema_test.go`、`gateway/gateway_test.go` | schema 生成器、枚举检查、错误映射和连接流程测试 |
| ollupi | `pkg/jsonrpc/jsonrpc.go`、`pkg/wshub/wshub.go` | JSON-RPC 编解码与出站队列；每用户连接数、心跳、寿命 |
| ollupi | `auth/auth.go`、`store/feed.go`、`router/` | `Authenticate` 与 `/healthz`；把提交的变化交给订阅者；多分片路由 |
| ollupi-desktop | `packages/protocol/scripts/generate.mjs`、`apps/desktop/src/renderer/src/gateway/session.ts` | 从契约生成 TypeScript；连接、重连、摘要比较 |
