# Config 参考

宿主（host）装配引擎时要填的结构都在这一页：`host.Config`、它里面的 `gateway.Options` 和连接参数 `wshub.Options`，模型连接的参数，以及多进程部署时的 `shard.Member`。每个字段写类型、默认值，和调大调小或不填的后果。默认值都在 `host.New` 和 `gateway.NewServer` 里填上；最小宿主程序见[把引擎嵌进服务](/zh/integrate/embed)。

## host.Config

| 字段 | 类型 | 默认 | 说明与后果 |
|---|---|---|---|
| `Home` | `string` | 无 | 数据目录，用绝对路径。库在 `<Home>/data/store.sqlite`，附件在 `<Home>/attachments`。同一个 `Home` 同一时刻只该由一个进程运行，多进程时靠 `shard.Member` 保证 |
| `Name` | `string` | 必填 | 部署的名字。`Prompt` 为空时进默认系统提示词（以 `You are <Name>, a personal assistant` 开头），也是连 MCP 服务器时报的客户端名。为空时 `host.New` 失败 |
| `Prompt` | `string` | 空，用默认提示词 | 主 agent 系统提示词的开头，整个替换默认的那段；子 agent 不读它。角色规则、技能列表等仍由引擎接在后面，见[上下文](/zh/engine/context) |
| `Models` | `[]llm.Model` | 必填 | 可选的模型，每个一条连接（`Connection` 不能重复）。客户端发消息不指定连接时，用这个会话上一轮的模型，再没有就用第一个 |
| `Connections` | `map[string]llm.Client` | 必填 | 连接 ID 到客户端。上下文窗口、主 agent 的角色（输入预算不到 16,384 token 时用精简主 agent）都按这里的 `Limits` 算，配了 `ClientFor` 也一样 |
| `ClientFor` | `func(user, connection string) (llm.Client, error)` | nil，所有用户共用 `Connections` | 每次模型请求（包括记忆提炼）都调一次，让这个用户用自己的密钥和配额。要每次返回同一个客户端，否则并发名额失效，见[扩展点](/zh/integrate/extend#每用户的模型客户端) |
| `Memory` | `*llm.Model` | nil，不提炼记忆 | 记忆提炼用的模型，必须在 `Models` 的连接里，输入预算至少 8,192 token。nil 时不从对话里学新记忆，已有记忆的召回仍按每个用户的设置。见[记忆](/zh/engine/memory) |
| `Tools` | `[]kit.Provider` | nil，只有内置工具 | 所有用户共有的工具 provider，接在内置工具前面，每个用户的注册表里还有他自己的 MCP 服务器。命令与文件、网页工具不是内置的，要放在这里。见[扩展点](/zh/integrate/extend#自己的工具) |
| `Allowlist` | `[]string` | nil，全部可见 | 非 nil 时只有名单里的工具对模型可见，内置工具也要列上；空切片表示一个工具都没有。名单里不存在的名字被忽略 |
| `Permissions` | `policy.Settings` | 审批策略 `on-request`，没有规则 | 权限分层里最底下的部署层，所有用户共用。启动时只查语法；规则提到不存在的工具要到运行时才报错，见[启动校验](/zh/integrate/embed#启动校验与常见错误)和[审批与权限](/zh/engine/permissions) |
| `Boxes` | `func(user string) (sandbox.Box, error)` | 必填 | 用户在这台机器上的沙箱：工作区的添加与移动、附件的源文件、用户的 stdio MCP 服务器都经它。工作区工具要另外填同一个函数，见[扩展点](/zh/integrate/extend#云沙箱) |
| `SkillsDir` | `string` | 空，不开技能 | 技能目录，下面按角色分子目录（`<SkillsDir>/<角色>/<技能>/SKILL.md`）。启动时检查，不合规时 `host.New` 失败 |
| `Slots` | `int` | 32 | 这个进程同时运行的轮次数，见[容量规划](/zh/integrate/capacity) |
| `UserSlots` | `int` | 等于 `Slots` | 一个用户最多占几个槽位 |
| `RunLimit` | `time.Duration` | 4 小时 | 一次占用槽位的最长时间，超过时这一轮失败 |
| `Location` | `*time.Location` | `time.Local` | 定时任务的 cron 表达式按这个时区算 |
| `Gateway` | `*gateway.Options` | nil，不开网关 | 非 nil 时 `host.New` 建网关，`h.Gateway.Serve` 才可用 |

`Slots`、`UserSlots`、`RunLimit` 只有填 0 时换成默认值（`cmp.Or`），负数原样传给调度器：`Slots` 或 `UserSlots` 为负时没有轮次能运行，`RunLimit` 为负时每次运行立即超时。`host.New` 不检查这几项。

各参数调大调小的后果集中在[容量规划与限流](/zh/integrate/capacity#调大调小的后果)。

::: info 演进
v0.16.0 之前填的是 `agent.Config`（v0.14.0 到 v0.15.1 叫 `service.Config`），有 `DB`、`OnEvent`、`Lease`、`OnLeaseLost`、`Attachments`、`AttachmentsDir`、`ToolsFor`、`BoxFor` 等字段。`18d6757` 用 `host.Config` 取代它，默认值不变（32 个槽位、全部可给一个用户、4 小时）：库和附件目录由 `Home` 决定，工具 provider 换成 `tool/kit` 的接口，用户自己的工具只来自他的 MCP 服务器，`BoxFor` 改名 `Boxes`。`1ae27b2` 起每个用户的 MCP 服务器存进库里；租约移到 `shard.Member`（`48c8454`）。v0.16.1（`b02dbfd`）起审批策略不填时默认 `on-request`；更早的 `agent.Config` 不填会启动失败。
:::

## 模型连接

`Models` 的每一项：

| 字段 | 类型 | 说明 |
|---|---|---|
| `Name` | `string` | 发给服务商的模型名 |
| `Connection` | `string` | `Connections` 里的连接 ID，每个模型一条 |
| `Thinking` | `*bool` | 非 nil 时请求带上思考开关 |
| `Images` | `bool` | 这个模型能不能看图。false 时带图片附件的消息、以及发到已经有图片的会话里的消息都被拒绝 |

三个内置客户端的构造参数相同：`llm.NewOpenAI(baseURL, apiKey, calls, limits)`、`llm.NewAnthropic(...)`、`llm.NewGemini(...)`（多返回一个 error）。

| 参数 | 默认 | 调大 | 调小 |
|---|---|---|---|
| `baseURL` | 空，用服务商的地址 | | |
| `calls` | 0 或负数时为 4 | 这条连接同时在途的模型请求变多；超过服务商给这个密钥的配额时 429 变多，每次请求最多重试 8 次，重试期间占着槽位和名额 | 请求在名额上排队，排队的轮次占着槽位不干活 |
| `limits` | 无 | | 没声明的模型，选它发消息时被拒 |

`llm.Limits` 的三个字段：

| 字段 | 说明 | 填大了 | 填小了 |
|---|---|---|---|
| `Context` | 模型的上下文窗口，必须为正 | 请求超过服务商的真实上限，被服务商拒绝 | 窗口算小，更早压缩，长对话丢的细节更多 |
| `Output` | 回答的上限，必须为正 | 预留给回答的空间变大（最多 `Context/4`），输入预算相应变小 | 回答可能被截断 |
| `MaxInput` | 输入的上限，0 表示不另设 | | 比 `Context` 减去预留更紧时，按它算输入预算 |

输入预算是 `Context` 减去 `min(Output, Context/4)`，再受 `MaxInput` 限制（`pkg/llm/limits.go`）。窗口怎样分配见[上下文](/zh/engine/context)，客户端的重试与并发见[模型接入](/zh/engine/models)。

## gateway.Options

| 字段 | 类型 | 默认 | 说明与后果 |
|---|---|---|---|
| `Token` | `string` | 无 | 单用户网关的令牌，属于用户 `default`，按常数时间比较。和 `Authenticate` 二选一，都没有时 `NewServer` 失败 |
| `Authenticate` | `auth.Authenticate`，即 `func(ctx context.Context, token string) (user string, err error)` | nil，用 `Token` | 多用户时由它说出令牌属于谁。返回 `auth.ErrUnknownToken` 时回 401；返回别的错误时回 503 加 `Retry-After`（"the token cannot be checked now"）。有 10 秒超时。见[扩展点](/zh/integrate/extend#认证) |
| `AllowedHosts` | `[]string` | 只有 `localhost`、`127.0.0.1`、`::1` | 请求的 `Host`（去掉端口）不在其中时回 403 `host not allowed`。经路由器转发时是分片地址的主机名 |
| `AllowedOrigins` | `[]string` | 只有 `localhost:*`、`127.0.0.1:*`、`[::1]:*`，以及与 `Host` 相同的来源 | 浏览器客户端的来源，`coder/websocket` 的 Origin 模式 |
| `Connections` | `wshub.Options` | `gateway.DefaultConnections` | 连接的上限与心跳，见下表。整个结构为零值时用默认；只填一部分时其余字段是 0，`NewServer` 失败 |
| `Admit` | `func(ctx context.Context, user string) error` | nil，接收所有通过认证的用户 | 分片进程填 `shard.Member.Admit`，只服务放在这个分片上的用户。返回错误时回 503 加 `Retry-After`（"this user is not served here now; try again"）。一个用户在这个进程里通过一次之后，他之后的连接不再查 |

`wshub.Options`（`gateway.DefaultConnections` 的值）：

| 字段 | 默认 | 调大 | 调小 |
|---|---|---|---|
| `PerKey` | 4 | 一个用户能同时开更多连接（每台设备一条）；每条都收到这个用户的全部通知，网关的内存和推送量随之增加 | 多设备的用户更常被顶掉：超出时最老的一条以 4000 关闭 |
| `Rate` | 每秒 200 | 重启后客户端回来得更快，但握手、认证、`initialize` 后的重发一起压到进程和库上 | 回来的客户端更多收到 503，按 `Retry-After` 再来，全部回来更慢 |
| `Burst` | 400 | 同上，允许更大的一阵 | 同上 |
| `RetryWithin` | 5 秒，不能小于 1 秒 | 被拒的客户端分散到更长的时间里回来 | 被拒的客户端更集中地回来，`Retry-After` 在 1 秒到它之间随机 |
| `PingEvery` | 30 秒 | 死连接更晚被发现，占着的内存和推送更久 | 心跳开销变大；空闲连接的 CPU 主要花在这里 |
| `PongWithin` | 15 秒 | 慢网络上的客户端不容易被误断 | 对端稍慢就被断开重连。只在网关一直等着读这条连接时计时，因入站限速或积压暂停读取的时间不算 |
| `MaxAge` | 20 小时 | 连接活得更久；要低于负载均衡器的 WebSocket 时长上限（Google Cloud 是 24 小时），否则由负载均衡器同时切断 | 客户端更频繁地重连。实际寿命在 `MaxAge` 的 3/4 到 `MaxAge` 之间随机，让同时建立的连接不同时断开 |

按 `Rate` 和 `Burst` 的默认值，分片被杀再拉起后，8000 个客户端按协议重连 83 秒全部回来，经路由的 4000 个 44 秒（[连接](/zh/benchmarks/#连接)）。默认值本身是估计的，没有拿别的取值比较过。

::: info 演进
`fc3d064`（v0.13.0）把连接管理移进 `pkg/wshub`，加上心跳、准入限速和每用户多条连接；提交说明写明准入速率是估计值，当时还没有网关实验。`ce11149` 加上连接寿命 `MaxAge` 和 4000 关闭码。以前 `PongWithin` 内没收到 pong 就断开，一个一下发来大量请求的客户端，pong 排在被限速的请求后面，会被当成失联断开；`3e97634` 只在网关一直等着读这条连接时才这样判断。
:::

协议层还有几个不可配的上限：一条入站消息最多 4 MiB；每个连接每秒 50 条消息、可以突发 200 条；发给一个客户端的待发数据超过 16 MiB 时断开它（`gateway/server.go`、`pkg/jsonrpc/jsonrpc.go`）。客户端在各种关闭码之后该怎么做，见[客户端](/zh/integrate/client)。

## shard.Member

多进程部署时，每个分片进程填一个 `shard.Member`，用它的 `Run` 包住 `h.Run` 和 `h.Gateway.Serve`，见[多用户与分片部署](/zh/integrate/deploy)。

| 字段 | 类型 | 默认 | 说明与后果 |
|---|---|---|---|
| `ID` | `string` | 无 | 分片 ID，目录库里 `shards.id` |
| `Address` | `string` | 无 | 路由器连这个进程用的地址，如 `http://10.0.0.1:9001`；拿到租约时随租约写进目录库 |
| `Accepting` | `bool` | false | 新用户能不能放到这个分片上。false 时只服务已经放在这里的用户 |
| `Catalog` | `catalog.Catalog` | 无 | 目录库，`catalog.OpenSQL(path)` 或自己的实现 |
| `TTL` | `time.Duration` | 无，必须为正 | 租约时长，见[租约时长](/zh/integrate/deploy#租约时长)。不为正时 `Run` 返回 `shard: a lease needs a TTL` |
| `Load` | `func() (int64, error)` | nil，报 0 | 每次续约时报给目录库的负载，用什么量由部署决定（最近活跃的用户、进行中的轮次、连接数）。新用户放到随机抽两个接新用户的分片里负载较小的那个；负载相同时用户少的那个 |

## schedule.New

用 `host` 的宿主不直接调它：`host.New` 调 `schedule.New(store, runner, slots, userSlots, runLimit)`，三个数来自 `Slots`、`UserSlots`、`RunLimit` 填好默认之后的值。自己装配引擎、不经 `host` 时，`schedule.New` 不补默认值，传什么用什么。

| 参数 | `host.Config` 字段 | 作用 |
|---|---|---|
| `slots` | `Slots`（默认 32） | 同时运行的会话数上限 |
| `userSlots` | `UserSlots`（默认等于 `slots`） | 一个用户同时运行的会话数上限 |
| `limit` | `RunLimit`（默认 4 小时） | 每次运行的 ctx 截止时间；到时这一轮以 `the turn reached its time limit of <limit>` 失败 |

## 代码位置

| 路径 | 职责 |
|---|---|
| `host/host.go` | `Config`、默认值、`New` 里的校验 |
| `host/models.go` | 模型和连接的校验，`ClientFor` |
| `pkg/llm/chat.go`、`limits.go`、`connection.go` | `Model`、`Limits`、默认并发 4、重试 8 次 |
| `gateway/serve.go` | `Options`、`DefaultConnections`、`NewServer` |
| `gateway/auth.go`、`gateway/server.go` | Host、令牌、`Admit` 的检查与回复 |
| `pkg/wshub/wshub.go` | `wshub.Options` 的含义：准入、每用户连接数、心跳、寿命 |
| `shard/shard.go` | `Member` |
| `schedule/schedule.go` | `New` 的参数 |
