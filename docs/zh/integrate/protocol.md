# 网关协议

网关（gateway）是引擎对外的唯一接口：WebSocket 上的 JSON-RPC 2.0。客户端用它管理会话（thread）、发起一轮（turn）、接收条目（item）的增量，并回答审批和提问。方法名对齐 Codex app-server。

协议由 `gateway/protocol.go` 里的一张表定义。这张表同时做请求分发，也是 `gateway/protocol.schema.json` 的生成来源，所以文档、类型和实际行为不会各走各的。下文的数字和名称对应引擎 v0.12.1：38 个方法、16 种通知、2 种服务端请求、1 种客户端通知、15 个错误码。

本页讲所有功能共用的约定：传输、认证、连接模型、握手、版本校验、消息的通用约定、错误码，以及契约怎样生成和测试。每个功能的方法、通知、类型和流程按模块分页，见下面的[模块](#模块)；怎样写一个能正确重连、跟上状态的客户端见[写一个客户端](/zh/integrate/client)。

::: info 演进
v0.12.1 的契约和 v0.12.0 相同，`protocolSha256` 一致；v0.12.1 只改了插话进等审批或提问的轮次时的行为（`c4899f5`），见[插话](/zh/integrate/protocol/turns#插话)。v0.12.0（`5f64857`）在 v0.11.3 的 34 个方法、15 种通知之上加了 `environment/*` 四个方法、`environment/changed` 通知和 `thread/start` 的 `environmentId`，契约的摘要随之改变。
:::

## 传输

每个 WebSocket 文本帧是一条 JSON-RPC 消息。网关接受任意路径的 `GET` 升级请求。

| 项 | 值 | 超出或失败时 |
|---|---|---|
| 帧类型 | 只收文本帧 | 回 `-32600`，`id` 为 `null`，连接保持 |
| 版本字段 | `jsonrpc` 必须是 `"2.0"` | 回 `-32600`，连接保持 |
| 解析失败 | | 回 `-32700`，`id` 为 `null`，连接保持 |
| 单条入站消息 | 32 MiB（`maxMessageBytes`） | 读取失败，连接关闭 |
| 单次写超时 | 10 秒（`writeTimeout`） | 关闭码 1011，reason `write failed` |
| 出站队列 | 16 MiB（`maxOutboxBytes`） | 关闭码 1008，reason `client is not reading fast enough` |
| HTTP 头读取超时 | 5 秒 | 升级失败 |
| 关停等待 | 5 秒 | 网关退出前用关闭码 1001 通知客户端 |

出站队列的上限也作用于单条消息。一条超过 16 MiB 的回复会被当成客户端读得太慢，连接直接关闭。这个边界影响 `attachment/read`：图片附件上限是 20 MiB，而 base64 之后约 1.33 倍，所以大约 12 MiB 以上的图片读不回来。实测读一张 14 MiB 的图片时，连接以 1008 关闭。

Go 客户端如果用 `coder/websocket`，默认读上限是 32768 字节，`tool/list` 的回复就可能超过它，需要先调用 `SetReadLimit`。

## 认证

一次升级请求依次经过四道检查。

| 顺序 | 检查 | 依据 | 失败 |
|---|---|---|---|
| 1 | Host | `localhost`、`127.0.0.1`、`::1`，加上 `Options.AllowedHosts` | 403 `host not allowed` |
| 2 | 令牌 | `Options.Authenticate`，单用户时用 `Options.Token` 做常量时间比较 | 401 `invalid or missing gateway token` |
| 3 | 用户 | `db.EnsureUser` 确保用户行存在 | 500 |
| 4 | Origin | 没有 Origin 头或与 Host 相同时放行；否则匹配 `localhost:*`、`127.0.0.1:*`、`[::1]:*`，加上 `Options.AllowedOrigins` | 403 |

令牌有两种传法，都不进 URL，因为访问日志会保留 URL：

- `Authorization: Bearer <token>`。
- 浏览器不能设置这个头，改用子协议：`new WebSocket(url, ["ollupi.token", token])`。网关读 `ollupi.token` 后面紧跟的那一项，握手只回 `ollupi.token`，不回显令牌。

`NewServer` 要求 `Token` 或 `Authenticate` 二选一，否则启动失败。令牌的签发不归引擎管：`Authenticate` 只回答"这个令牌是谁的"。

## 连接模型

- **每个用户一条连接。** 同一用户的新连接替换旧连接，旧连接以 1008 关闭，reason `replaced by a newer connection`。
- **请求串行处理。** 网关在读循环里同步执行方法，同一连接上的下一条请求要等上一条回复写入队列。
- **事件不缓存。** `Deliver` 只投给该用户当前已初始化的连接。断线期间的事件不补发，客户端重连后用 `thread/read` 或 `thread/resume` 读库里的状态。
- **读视图与事件有序。** `thread/read`、`thread/resume`、`cron/list` 在读库到回复入队之间持有 `deliver` 锁，事件不会抢在视图之前到达，客户端看到的变化总是发生在它读到的视图之后。
- **通知可能先于回复。** agent 在处理请求时同步发事件，所以 `thread/started` 排在 `thread/start` 的回复之前，`turn/started` 排在 `turn/start` 的回复之前。客户端不能假设先收到回复。
- **用户隔离。** 其他用户的会话对当前用户表现为不存在，返回 `-32004`。

## 握手

1. 客户端发 `initialize`，带 `clientInfo: {name, version}`。
2. 网关回 `serverInfo: {name: "ollupi", version}` 和 `protocolSha256`。
3. 回复入队之后，连接标记为已初始化，并把该用户所有待回答的审批和提问按请求时间重发一遍。
4. 客户端发 `initialized` 通知。

| 情况 | 结果 |
|---|---|
| 初始化之前调用任何其他方法，包括不存在的方法 | `-32002` `call initialize first` |
| 重复 `initialize` | `-32600` `already initialized` |
| 未知方法（已初始化） | `-32601` |
| 未知的客户端通知 | 记一条警告，不回复 |

网关不等 `initialized`：第 3 步在 `initialize` 回复之后就发生，收到这条通知也不做任何事。契约里保留它，客户端照发即可。这意味着客户端必须在 `initialize` 返回时已经能处理服务端请求。

`serverInfo.version` 取自 `debug.ReadBuildInfo().Main.Version`，也就是最终二进制主模块的版本，引擎被嵌入时不是引擎自己的版本，本地构建时是 `(devel)`。判断协议是否兼容要看 `protocolSha256`。

## 版本校验

`protocolSha256` 是嵌入二进制的 `protocol.schema.json` 的 SHA-256。客户端把它和自己生成类型时用的契约文件比较。

网关不做校验，也不拒绝不一致的客户端。怎么处理由客户端决定。桌面端的做法：`packages/protocol` 生成时把摘要写进常量 `PROTOCOL_SHA256`，连接后比较；不一致时显示一条提示横幅，连接继续工作。

## 模块

| 模块 | 方法 | 通知 | 服务端请求 |
|---|---|---|---|
| [会话](/zh/integrate/protocol/threads) | `thread/start`、`thread/read`、`thread/resume`、`thread/list`、`thread/rename`、`thread/archive`、`thread/delete`、`thread/updatePermissions` | `thread/started`、`thread/changed`、`thread/status/changed` | |
| [一轮与条目](/zh/integrate/protocol/turns) | `turn/start`、`turn/steer`、`turn/interrupt`、`attachment/read` | `turn/queued`、`turn/started`、`turn/completed`、`item/started`、`item/updated`、`item/completed`、`item/agentMessage/delta`、`item/reasoning/textDelta`、`error` | |
| [审批与提问](/zh/integrate/protocol/approvals) | | | `item/toolCall/requestApproval`、`item/tool/requestUserInput` |
| [权限](/zh/integrate/protocol/permissions) | `thread/updatePermissions`、`workspace/updatePermissions` 的权限部分，`thread/start` 的 `permissions` | | |
| [工作区与执行环境](/zh/integrate/protocol/workspaces) | `workspace/list`、`workspace/add`、`workspace/rename`、`workspace/move`、`workspace/archive`、`workspace/updatePermissions`、`environment/list`、`environment/add`、`environment/rename`、`environment/delete` | `workspace/changed`、`environment/changed` | |
| [模型、工具与 MCP](/zh/integrate/protocol/models-tools) | `model/list`、`tool/list`、`mcpServer/list` | | |
| [定时任务](/zh/integrate/protocol/cron) | `cron/list`、`cron/create`、`cron/pause`、`cron/delete` | `cron/changed` | |
| [记忆](/zh/integrate/protocol/memory) | `memory/list`、`memory/status`、`memory/update`、`memory/move`、`memory/forget` | | |
| [搜索](/zh/integrate/protocol/search) | `search` | | |
| [设置](/zh/integrate/protocol/settings) | `settings/read`、`settings/update` | `settings/changed` | |

`initialize` 和客户端通知 `initialized` 在上面的[握手](#握手)里。按类型名查它在哪个模块，见[类型索引](/zh/integrate/protocol-types)。

## 通用约定

**请求。** 参数全部用严格解码：多余字段返回 `-32602`。`params` 省略时按 `{}` 处理。契约里标为必填的字段，网关解码时并不检查它是否出现（Go 的 JSON 解码不强制必填），缺了按零值处理，例如 `thread/start` 省略 `permissions` 也能成功；客户端仍应按契约发送。各模块的参数表里 `?` 表示可选。

**字段。**

- 可选字段在 Go 端用 `omitempty`：空字符串、`0`、`false`、空数组都不发，客户端要把"缺"当成零值。
- 时间都是 RFC 3339 的 UTC 字符串，带纳秒，如 `2026-11-08T11:44:56.877645Z`。
- ID 是字符串，通常是 UUID。例外是 migration 0007 给已有用户补的本机执行环境，它的 ID 是 32 位十六进制（`lower(hex(randomblob(16)))`）。客户端不要假设 ID 的格式。
- 多数字段是 camelCase。直接给模型看的类型（工具描述、内置工具的参数和输出）用 snake_case，如 `input_schema`、`exit_code`、`work_dir`，这是模型那一侧的命名。

**通知。** `thread`、`turn`、`item` 通知带的是发出那一刻库里的完整行，客户端按 `id` 整行替换，不用做字段合并。`*/changed` 通知里对象为 `null` 表示它已被删除。

## 错误码

| 码 | 名称 | 来源 |
|---|---|---|
| `-32700` | `parseError` | 消息不是合法 JSON |
| `-32600` | `invalidRequest` | 非文本帧、版本不对、不是请求也不是响应、重复初始化 |
| `-32601` | `methodNotFound` | 方法不存在 |
| `-32602` | `invalidParams` | 参数解码失败、`ErrInvalidMessage`、`ErrInvalidAnswer`、`ErrInvalidDecision`、`ErrInvalidName`、`ErrInvalidPath`、`ErrEnvironmentInUse`、`permission.ErrInvalidSettings`、`memory.ErrInvalidChange`、`tools.ErrUnknownTool`、`tools.ErrInvalidArguments`、`cron.ErrInvalidJob` |
| `-32603` | `internalError` | 结果无法编码 |
| `-32000` | `serverError` | 其余所有错误 |
| `-32002` | `notInitialized` | 未初始化 |
| `-32004` | `notFound` | `repo.ErrNotFound`，包括别的用户的数据 |
| `-32010` | `noActiveTurn` | 会话没有进行中的一轮 |
| `-32011` | `turnMismatch` | 期望的一轮不是进行中的那一轮 |
| `-32012` | `noSuchRequest` | 会话没有在等这个请求 |
| `-32013` | `subagentThread` | 子 agent 会话不接受这个操作 |
| `-32014` | `workspaceArchived` | 工作区已归档 |
| `-32015` | `threadArchived` | 会话已归档 |
| `-32016` | `threadBusy` | 会话有进行中或排队的一轮；`workspace/move` 时指工作区里有会话的一轮还没结束（`ErrWorkspaceBusy`） |

`serverError` 把内部错误挡在服务端。`errorCodes` 表里的错误把原文发给客户端；不在表里的错误只写日志，客户端只收到 `the request could not be completed`，这样数据库路径之类的内容不会外泄。`TestAnUnknownErrorStaysOnTheServer` 守着这条。例外是 `cron/*` 和 `memory/*` 未配置时的提示，它们本身就是给客户端看的 `-32000`。

## 一张表分发和生成 schema

`protocol.go` 里的变量 `protocol` 声明所有消息：

```go
var protocol = struct {
	methods             map[string]method
	notifications       map[string]reflect.Type
	serverRequests      map[string]serverRequest
	clientNotifications map[string]reflect.Type
	errors              map[int]string
}{ /* ... */ }
```

每个方法用泛型 `handle` 注册：

```go
"thread/start": handle((*conn).threadStart),
```

`handle[P, R]` 同时做两件事：记下参数和结果的 `reflect.Type`，生成解码、调用、错误映射的闭包。`conn.Call` 在运行时查这张表分发。`gateway/schema_test.go` 里的生成器读同一张表写出 schema。一个方法只要能被调用，就一定在 schema 里。

| 契约段 | 来源 | 内容 |
|---|---|---|
| `methods` | `protocol.methods` | 38 个方法的 `params`、`result` |
| `notifications` | `protocol.notifications` | 16 种通知的载荷 |
| `serverRequests` | `protocol.serverRequests` | 2 种服务端请求 |
| `clientNotifications` | `protocol.clientNotifications` | `initialized` |
| `errors` | `protocol.errors` | 错误码到名称 |
| `builtinTools` | `schema_test.go` | 9 个内置工具的参数和输出 |
| `providers` | `schema_test.go` | `cron`、`skills`、`memory`。代码注释说它是 `ItemRow.server` 可取的引擎自带提供方 id，但并不完整，实际取值见[提供方](/zh/integrate/protocol/models-tools#提供方) |
| `$defs` | 从以上类型遍历得到 | 129 个命名类型，字段见[协议数据类型](/zh/integrate/protocol-types) |

`builtinTools` 收哪些工具、其余工具调用怎样显示、工具名的规则，见[模型、工具与 MCP](/zh/integrate/protocol/models-tools)。

生成器对协议类型有约束，违反时生成失败：

- 匿名结构体不能进协议，必须有名字并且导出。
- 命名字符串类型必须在 `enums` 里给出取值列表，或者列入 `plainStrings`。
- map 的键必须是字符串，命名切片要在 `special` 里给 schema。
- 两个类型重名时要在 `defNames` 里改名。

枚举的取值列表写在常量旁边，代码也在用：写库前按它校验。`TestEnumValuesMatchConstants` 解析 Go 源码，确认列表和常量一致。

`protocol.schema.json` 通过 `//go:embed` 编进二进制，`protocolSHA256` 在包初始化时算出。修改协议后重新生成：

```bash
GOFLAGS=-tags=sqlite_fts5 go generate ./gateway
```

这份文件是提交进仓库的跨语言契约。桌面端不解析 Go，`packages/protocol/scripts/generate.mjs` 用 `go list -m` 找到 sidecar 依赖的那个引擎版本，读它的契约，生成 `src/generated/` 下的 `types.ts`、`messages.ts`、`tools.ts`、`tools.validate.js`、`tools.validate.d.ts` 和契约副本。`pnpm protocol:check` 检查生成物是否过期。

## 契约测试

契约由三层测试守住，都用真实消息而不是手写样例。

| 层 | 位置 | 做什么 |
|---|---|---|
| 生成物一致 | `TestProtocolSchema` | 重新生成并和提交的文件逐字节比较 |
| 真实流量 | `TestTrafficMatchesContract` | 用假模型跑完整会话，校验每条消息 |
| 录制回放 | 桌面端 `packages/protocol/src/contract.test.ts` | 用当前 sidecar 录下的会话校验生成的类型 |

`TestTrafficMatchesContract` 起一个真实的网关和 agent，只把模型换成 `httptest` 假服务。测试客户端读到每条消息时：

- 按契约校验方法参数、结果、通知载荷、服务端请求和客户端回复；契约没声明的消息算失败。
- 校验 `initialize` 报告的摘要等于契约文件的 SHA-256。
- 校验内置工具调用的参数和输出。
- 记下见过的消息种类，结束时检查覆盖：每个方法都调过，每种通知和服务端请求都收到过，每个内置工具的参数和输出都校验过（`run_command` 的参数除外）。

新增一个方法而不写进测试流程，这个测试就失败。

桌面端的 `packages/protocol/scripts/record-session.mjs` 构建 sidecar，接脚本化的假模型，驱动一个覆盖 UI 所有消息种类的会话，把每条 JSON-RPC 消息连同方向存进 `fixtures/session.json`。`contract.test.ts` 用 Ajv 逐条校验，并要求录制时的摘要等于当前 `PROTOCOL_SHA256`。开发构建还在运行时把每条消息过一遍契约，不符时弹出提示。

## 路由

多分片部署时，客户端只连 `gateway.Router`。它用同样的方式读令牌，查 `Directory` 找到用户的分片（shard），再反向代理过去，自身不保存状态。

| 失败 | 状态码 |
|---|---|
| 令牌无效 | 401 |
| 用户无法放到分片上、分片地址查不到或不可用 | 503 |
| 分片连不上 | 503，客户端重试，此时新持有者已发布地址 |

`gateway.OnShard` 把 `Authenticate` 收窄到本分片的用户，连错分片的请求拿到 401，不会给用户开出第二个家。部署方式见 [分片](/zh/engine/sharding)。

## 代码位置

| 仓库 | 路径 | 职责 |
|---|---|---|
| ollupi | `gateway/protocol.go` | 协议表、错误码、全部参数和结果类型 |
| ollupi | `gateway/protocol.schema.json` | 生成的契约 |
| ollupi | `gateway/server.go` | 连接、事件到通知的映射、服务端请求、错误映射 |
| ollupi | `gateway/serve.go` | `Options`、`NewServer`、`Serve`、Host 和令牌检查 |
| ollupi | `gateway/router.go` | `Router`、`OnShard`、令牌读取 |
| ollupi | `gateway/threads.go`、`workspaces.go`、`environments.go`、`cron.go`、`memory.go`、`search.go`、`settings.go` | 各组方法的处理函数 |
| ollupi | `gateway/schema_test.go` | schema 生成器和枚举检查 |
| ollupi | `gateway/traffic_test.go` | 真实流量契约测试 |
| ollupi | `agent/environments.go`、`repo/environments.go` | 执行环境的增删改和校验 |
| ollupi | `pkg/jsonrpc/jsonrpc.go` | JSON-RPC 编解码、读循环、出站队列 |
| ollupi-desktop | `packages/protocol/scripts/generate.mjs` | 从契约生成 TypeScript 和校验器 |
| ollupi-desktop | `packages/protocol/scripts/record-session.mjs` | 录制真实会话 |
| ollupi-desktop | `packages/protocol/src/contract.test.ts` | 校验录制的会话 |
| ollupi-desktop | `packages/client/src/client.ts` | TypeScript 客户端 |
| ollupi-desktop | `apps/desktop/src/renderer/src/gateway/session.ts` | 连接、重连、协议摘要比较 |
