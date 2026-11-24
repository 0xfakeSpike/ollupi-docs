# 扩展点

引擎留给宿主（host）接自己东西的地方，都是 `host.Config` 或 `gateway.Options` 里的一个字段，或者一个接口：填一个函数，或者给一个实现。全部字段见 [Config 参考](/zh/integrate/config)，最小宿主程序见[把引擎嵌进服务](/zh/integrate/embed)。

| 扩展点 | 填哪里 | 不填时 |
| --- | --- | --- |
| [每用户的模型客户端](#每用户的模型客户端) | `host.Config.ClientFor` | 所有用户共用 `Connections` 里的客户端和配额 |
| [自己实现模型客户端](#自己实现模型客户端) | `llm.Client` 接口，放进 `Connections` 或由 `ClientFor` 返回 | 用内置的 OpenAI、Anthropic、Gemini 客户端 |
| [自己的工具](#自己的工具) | `kit.Provider` 接口，放进 `host.Config.Tools` | 只有内置工具和用户自己的 MCP 服务器 |
| [云沙箱](#云沙箱) | `host.Config.Boxes`，工作区工具的 `workspace.Options.BoxFor` 或 `BoxIn`；`sandbox.Machine` 接口 | `Boxes` 必填；用户可以完全使用这台机器时填 `sandbox.Here()` |
| [附件存储](#附件存储) | `app.Attachments` 接口 | `host.New` 固定用 `<Home>/attachments` 目录 |
| [目录库](#目录库) | `catalog.Catalog` 接口，给 `shard.Member` 和 `router.NewLocator` | 用 `catalog.OpenSQL` 打开的 SQLite 文件 |
| [认证](#认证) | `gateway.Options.Authenticate`，路由器的 `router.NewLocator` | 用 `Token`，只有 `default` 一个用户 |

本页的代码都对着引擎 v0.17.1 编译并通过 `go vet`。云沙箱那段没有在真实容器里跑过；附件存储和目录库只给出接口的实现，没有接真实的服务。

## 每用户的模型客户端

`ClientFor(user, connection)` 给这个用户返回一个模型客户端，让他的请求用他自己的密钥和配额。返回值实现 `llm.Client`，三个内置客户端（`llm.NewOpenAI`、`NewAnthropic`、`NewGemini`）都是。按用户缓存客户端：

```go
type userClients struct {
	limits map[string]llm.Limits
	keyOf  func(user string) (string, error) // 宿主自己的密钥库

	mu     sync.Mutex
	byUser map[string]llm.Client
}

func (c *userClients) For(user, connection string) (llm.Client, error) {
	if connection != "openai" {
		return nil, fmt.Errorf("no per-user client for connection %q", connection)
	}
	c.mu.Lock()
	defer c.mu.Unlock()
	if client, ok := c.byUser[user]; ok {
		return client, nil
	}
	key, err := c.keyOf(user)
	if err != nil {
		return nil, err
	}
	client := llm.NewOpenAI("", key, 2, c.limits) // 这个用户自己的并发名额：2
	c.byUser[user] = client
	return client, nil
}

// Forget 在用户换了密钥后调用：之后的请求用新客户端，进行中的请求继续用旧的。
func (c *userClients) Forget(user string) {
	c.mu.Lock()
	defer c.mu.Unlock()
	delete(c.byUser, user)
}
```

装配时 `Connections` 仍然要填，因为窗口大小和角色读的是它的 limits：

```go
limits := map[string]llm.Limits{"gpt-5.2": {Context: 400_000, Output: 128_000}}
clients := &userClients{limits: limits, keyOf: keys, byUser: map[string]llm.Client{}}

cfg := host.Config{
	Models:      []llm.Model{{Name: "gpt-5.2", Connection: "openai"}},
	Connections: map[string]llm.Client{"openai": llm.NewOpenAI("", "", 4, limits)},
	ClientFor:   clients.For,
	// ...
}
```

**引擎保证：**

- 每次模型请求前，用这一轮的用户和模型连接调一次 `ClientFor`（`run/model.go` 的 `send`）。子 agent 和父会话是同一个用户。记忆提炼也经它取客户端（`host/host.go`），不再有单独的字段。
- `ClientFor` 返回错误时这次请求失败，轮次以 `run: model call: the model client of the user: ...` 失败。
- 窗口大小、角色选择、发消息时的长度检查读的都是 `Connections[connection].Limits`，不读 `ClientFor` 返回的客户端。

**宿主要保证：**

- **每次返回同一个客户端。** 并发名额属于客户端：`NewOpenAI` 的第三个参数建一个名额通道。每次新建客户端，名额通道也是新的，这个用户同时在途的请求就不受限制了。
- **用户客户端声明和 `Connections` 一样的 limits。** 引擎按 `Connections` 算窗口；客户端每次请求时还用自己声明的 limits 算回答上限，没声明这个模型时请求直接失败。
- **并发安全。** 多个槽位会同时调它。

用户客户端的并发名额（`calls`）：

| 参数 | 默认 | 调大 | 调小 |
| --- | --- | --- | --- |
| `calls` | 0 或负数时为 4 | 这个用户同时在途的模型请求变多，超过服务商给这个密钥的配额时遇到 429，每次请求最多重试 8 次，重试期间占着槽位 | 请求在名额上排队，排队的轮次占着槽位不干活 |

所有用户的名额之和不受分片限制，分片能同时跑多少轮只由 `Slots` 决定，见[容量规划与限流](/zh/integrate/capacity)。重试和名额的机制见[模型接入](/zh/engine/models)。

::: info 演进
v0.16.0 之前记忆提炼的客户端另由 `memory.Options.ClientFor` 给，不填时所有用户共用一个。`9fa9186` 起记忆提炼和对话走同一个 `ClientFor`。
:::

## 自己实现模型客户端

服务商不是 OpenAI、Anthropic、Gemini 兼容的接口时，自己实现 `llm.Client`：

```go
type Client interface {
	Chat(ctx context.Context, req ChatRequest, onDelta func(Delta)) (ChatResponse, error)
	Limits(model string) (Limits, error)
}
```

| 方法 | 引擎怎样用它 | 实现要做到 |
| --- | --- | --- |
| `Chat` | 每次模型请求调一次。`req.Messages` 第一条是系统提示词，`req.Tools` 是这次可用的工具，`req.ToolChoice` 是 `auto` 或 `none`，`req.InputTokens` 是引擎估算的输入 token | 流式的正文和思考通过 `onDelta` 交回（可以不流式，只在最后返回）；`ctx` 结束时尽快返回；并发安全。返回的回答要么带工具调用，要么有正文，否则这一轮失败（"the model returned neither a tool call nor an answer"）；`FinishReason` 为 `length` 且没有工具调用时也算失败。`Usage` 填上服务商报的 token 数 |
| `Limits` | 发消息时、每轮加载时算窗口 | 没声明的模型返回错误 |

并发名额和重试要自己做：内置客户端的名额通道和重试在 `pkg/llm/connection.go` 和各 SDK 的选项里，`llm.Client` 接口本身不带。`bench/main.go` 里的 `model` 类型是一个最小的实现，可作参照。

## 自己的工具

工具实现 `kit.Provider` 的三个方法，放进 `host.Config.Tools`，所有用户的注册表里都有它。`kit.Spec` 各字段、注册表、一次调用的生命周期见[工具](/zh/engine/tools)。

一个读、关工单的 provider：

```go
type Lookup struct {
	ID string `json:"id" jsonschema:"The ticket id, such as T-1024."`
}

type Close struct {
	ID     string `json:"id" jsonschema:"The ticket id."`
	Reason string `json:"reason" jsonschema:"One sentence the customer will read."`
}

// Tickets 是宿主自己的工单系统。provider ID 也是工具名 "__" 前面那一段。
type Tickets struct {
	backend TicketBackend
}

type TicketBackend interface {
	Get(ctx context.Context, user, id string) (map[string]any, error)
	Close(ctx context.Context, user, id, reason string) error
}

func (t *Tickets) Name() (string, string) {
	return "tickets", "Read and close the user's support tickets."
}

func (t *Tickets) Tools(context.Context) ([]kit.Spec, error) {
	return []kit.Spec{
		{
			Name:        "tickets__lookup",
			Description: "Read one ticket with its messages.",
			InputSchema: kit.InputSchema[Lookup](),
			// 只读、不出这台机器：三档策略下都不问，同一批里可以并行。
			Annotations: tool.Annotations{ReadOnlyHint: true, OpenWorldHint: new(false)},
		},
		{
			Name:        "tickets__close",
			Description: "Close a ticket and send the reason to the customer.",
			InputSchema: kit.InputSchema[Close](),
			Annotations: tool.Annotations{DestructiveHint: new(true), OpenWorldHint: new(true)},
			// 有了它，规则可以写 tickets__close(t-1*)，审批卡片显示 Text。
			Content: func(_ context.Context, c tool.Call) (policy.Content, error) {
				in, err := kit.DecodeArguments[Close](c.Arguments)
				if err != nil {
					return policy.Content{}, err
				}
				return policy.Content{Text: "close " + in.ID + ": " + in.Reason, Match: strings.ToLower(in.ID)}, nil
			},
		},
	}, nil
}

func (t *Tickets) Invoke(ctx context.Context, c tool.Call) (kit.Result, error) {
	switch c.Tool { // c.User 是这次调用的用户：只做他的事
	case "tickets__lookup":
		in, err := kit.DecodeArguments[Lookup](c.Arguments)
		if err != nil {
			return kit.Result{}, err
		}
		ticket, err := t.backend.Get(ctx, c.User, in.ID)
		return kit.Result{Output: ticket}, err
	case "tickets__close":
		in, err := kit.DecodeArguments[Close](c.Arguments)
		if err != nil {
			return kit.Result{}, err
		}
		return kit.Result{Output: "closed"}, t.backend.Close(ctx, c.User, in.ID, in.Reason)
	}
	return kit.Result{}, fmt.Errorf("tickets: no tool %q", c.Tool)
}
```

装配：`host.Config{Tools: []kit.Provider{&Tickets{backend: b}, ws}}`。

`Tools` 没有按用户区分的版本：`Config.Tools` 里的 provider 每个用户都有，用户自己的工具只来自他的 MCP 服务器（客户端用 `mcpServer/*` 方法配置，存在库里）。只有部分用户开通的系统，在 `Invoke` 里按 `c.User` 拒绝没开通的用户，或者做成一个 MCP 服务器让开通的用户自己加。

`kit.Result` 除了 `Output`，还可以带 `Artifacts`（给用户看的文件）、`Ask`（向用户提问，这次调用等回答）、`Launch`（启动子 agent），内置的提问和子 agent 工具就是这样实现的（`tool/builtin/ask`、`tool/builtin/subagent`）。

### 命名

| 规则 | 不遵守时 |
| --- | --- |
| provider ID 非空，所有 provider 之间不重复，也不和内置的重复（`plan`、`user_input`、`deferred_tools`、`subagents`、`context`、`memory`、`cron`、`skills`、`tool_registry`，以及 `workspace`、`web` 如果你也放了它们） | 建这个用户的注册表时出错（`tool registry: provider "x" twice`），他的每一轮都失败 |
| 工具名非空，在这个用户的整个注册表里不重复 | 同上（`tool registry: tool "x" twice`） |
| 工具名写成 `<provider ID>__<工具>` | 见下面两条 |

用 `__` 连接有两个作用：

- **默认权限里可以提它。** 部署层的规则提到一个带 `__`、但这个用户没有那个 provider 的工具时，不算错；不带 `__` 的工具名，规则一提而注册表里没有，每一轮都失败。
- **可以延迟加载。** 名字含 `__` 的工具算外部工具，全部工具定义超过输入预算的 10% 时，它们只列名字，模型用到时再载入，见[工具](/zh/engine/tools)。

注册表本身不限制字符。MCP 工具名按 `^[A-Za-z0-9_-]{1,64}$` 过滤，不合的跳过；自己的工具照这个规则写最稳妥，超出的名字可能被模型服务商拒绝（这一点是推断，引擎没有校验）。

### 标注决定审批

审批策略只看 `ReadOnlyHint` 和 `OpenWorldHint`。`OpenWorldHint` 不设时当作真。`DestructiveHint`、`IdempotentHint`、`Title` 原样交给客户端显示，不影响审批。

| 工具的标注 | 严格（`untrusted`） | 适中（`on-request`） | 宽松（`never`） |
| --- | --- | --- | --- |
| `ReadOnlyHint: true`，`OpenWorldHint: false` | 运行 | 运行 | 运行 |
| `ReadOnlyHint: true`，`OpenWorldHint` 不设或为真 | 问 | 运行 | 运行 |
| 不是只读 | 问 | 问 | 运行 |

适中策略下还有一个例外：`Prepare` 返回的 `tool.Plan` 标了 `Sandboxed` 且没有 `Escalated` 的调用不问，这是给在沙箱里跑的命令用的。

规则先于策略：`ask: ["tickets__close(t-1*)"]` 在宽松下也会问，`allow: ["tickets__close(t-1*)"]` 在严格下也直接运行。规则的说明符要靠 `Content` 才能写：没有它的工具，规则只能按工具名写，写了说明符会报 `takes no specifier`。说明符的第一个词会被转成小写，所以 `Match` 也写成小写；或者在 `policy.Content` 里设 `Folded: true`，整段按不分大小写比较。规则语法见[审批与权限](/zh/engine/permissions)。

标了只读、没标 `Serial` 的调用，同一批里会并发执行，最多 8 个。标错的工具会在适中策略下不问就运行，还可能被并行，引擎不核对标注。

### 引擎保证与宿主责任

**引擎保证：**

- 参数先按 `InputSchema` 校验，不合的调用不进 `Content`、`Prepare`、`Invoke`，原因作为工具结果交给模型。`kit.InputSchema[T]()` 生成的 schema 不允许多余字段，缺必填字段也会被拒绝。
- `Invoke` panic 时只让这一次调用失败（"the tool crashed: ..."），`Content` 和 `Prepare` 里的 panic 也一样，进程不受影响。
- 返回的 `Output` 编码成 JSON 超过 1 MiB 时截断，错误超过 16 KiB 时截断（`tool/kit/kit.go`），见[工具](/zh/engine/tools)。
- 这一轮被中断、被别人结束、会话被删、超过 `RunLimit`，或者进程关闭时，传给 `Invoke` 的 `ctx` 会结束。
- 一个用户的注册表建一次就复用：建的时候调每个 provider 的 `Tools`，之后只在这个用户的 MCP 服务器配置变了、或者有服务器断了时重建（`tool/mcp/servers.go`）。

**宿主要保证：**

- **按用户隔离。** 引擎不知道你的工具碰的是谁的数据。`tool.Call` 里嵌着 `tool.Caller`，给出 `User`、`Thread`、`Workspace`、`Environment`、`Root`（工作区目录）、`Subagent` 等，工具自己只做这个用户的事。
- **`Tools` 返回固定的列表。** 它的结果会被缓存，不要按时间或调用者变。
- **自己关闭 provider。** `h.Close` 只关用户的 MCP 服务器和库，不调 `Config.Tools` 里任何 provider 的 `Close`；`workspace.Provider` 这类有资源的 provider 由宿主在退出时关。
- **需要审批前冻结执行内容的工具实现 `Prepare`。** 只有执行内容可能在审批期间变化的工具才需要，比如命令和文件修改：`Prepare` 返回的 `tool.Plan.Data` 记在调用里，审批的就是它，执行时从 `tool.Call.Prepared` 读回。见[工具](/zh/engine/tools)。

::: info 演进
v0.16.0 之前工具实现的是 `tools.Provider`（`Name`、`ToolList`、`Invoke`），每个用户额外的工具由 `Config.ToolsFor` 返回一个 `tools.Set`，宿主还要自己维护 `Set.Unavailable`。`65e57cb`（v0.16.0）把工具层收进 `tool` 和 `tool/kit`：provider 的方法变成 `Tools` 和 `Invoke(ctx, tool.Call)`，`PermissionContent` 改名 `Content`，用户自己的工具只来自库里的 MCP 服务器，连不上的服务器由 `tool/mcp` 自己记成不可用。
:::

## 云沙箱

用户的命令、文件、附件来源和 stdio MCP 服务器都经 `sandbox.Box` 访问。接云沙箱只需要实现 `sandbox.Machine`，再用 `sandbox.Remote(machine, roots, summary)` 包成 `Box`。`Box` 的方法、`Remote` 和本机沙箱语义的区别见[沙箱](/zh/engine/sandbox)。

::: warning 还没有服务商实现
引擎仓库里 `Machine` 的实现只在测试里，没有接入任何云沙箱服务商。下面的实现用 `docker exec` 访问每个用户一个容器，编译通过，没有在真实容器里跑过。
:::

同一个按用户取 Box 的函数要填在两个地方：

| 位置 | 谁用它 | 不填时 |
| --- | --- | --- |
| `host.Config.Boxes` | 读附件的源文件、`workspace/add` 和 `workspace/move` 校验路径、启动这个用户的 stdio MCP 服务器 | 必填，`host.New` 失败 |
| `workspace.Options.BoxFor` 或 `BoxIn` | 每一次 `run_command`、文件工具、读取工具 | 所有用户都用 `Options.Box` |

只填了第一个时，工作区添加在用户的机器里，工具却在 `Options.Box` 里运行，两边对不上。

### 按会话选择环境

一个用户可以有几个执行环境，会话开始时选一个，之后不变，见[执行环境](/zh/integrate/protocol/workspaces)。`Boxes` 是用户在这台机器上的那个 Box，工作区校验和附件读取用它；配了 `workspace.Options.BoxIn` 时，每次工具调用在哪个 Box 里跑，由它按会话的环境决定。

| `BoxIn(caller)` 返回 | 这次调用 |
| --- | --- |
| `(box, nil)` | 在这个 Box 里运行 |
| `(nil, nil)` | 在 `Options.Box` 里运行。注意不是 `BoxFor` 给的 Box |
| `(nil, err)` | 失败，错误以 `workspace: the environment of the conversation:` 开头交给模型 |

配了 `BoxIn` 时，`BoxFor` 不参与工具调用。`caller.Environment` 是会话的环境 ID，`caller.User` 是用户。按环境找机器（`h` 是 `host.New` 返回的宿主，`b` 是下面的 `boxes`，`machines` 是宿主自己按环境找到或唤醒云沙箱的代码）：

```go
BoxIn: func(c tool.Caller) (sandbox.Box, error) {
	if c.Environment == "" {
		return b.For(c.User)
	}
	var env account.Environment
	err := h.Store.Read(context.Background(), func(r store.Reader) (err error) {
		env, err = r.Environment(c.User, c.Environment)
		return err
	})
	if err != nil {
		return nil, err
	}
	if env.Kind == account.Local {
		return b.For(c.User) // 和 Boxes 同一个
	}
	return machines.For(c.User, env.ID)
},
```

工作区工具要在 `host.New` 之前建好放进 `Tools`，而 `BoxIn` 要读 `h.Store`：闭包在调用时才读 `h`，先声明变量、建完宿主再赋值即可。`machines` 和下面的 `boxes` 一样要缓存、要在退出时关。环境只是库里的一行名字和种类（`local` 或 `machine`），引擎不知道它对应哪台机器，这个对应关系由宿主保存。配了 `BoxIn` 时，`run_command` 的描述会多一句：会话在它开始时选的环境里运行，那里的文件夹不一定是这台机器的。

::: info 演进
v0.12.0 之前没有执行环境，每个用户只有一个 Box。`b1baf49`（v0.12.0）加入执行环境和 `BoxIn`。没有配 `BoxIn` 的宿主，工具调用照旧走 `BoxFor`。
:::

按用户缓存 Box，并管理它的生命周期：

```go
const summary = "A Linux container of your own; network rules are set on the container"

var roots = []string{"/work"}

// boxes 给每个用户一个连好的 Box，并负责它的生命周期：workspace 包只关 Options.Box。
type boxes struct {
	containerOf func(user string) (string, error) // 找到或创建这个用户的容器

	mu     sync.Mutex
	byUser map[string]sandbox.Box
}

func (b *boxes) For(user string) (sandbox.Box, error) {
	b.mu.Lock()
	defer b.mu.Unlock()
	if box, ok := b.byUser[user]; ok {
		return box, nil
	}
	id, err := b.containerOf(user)
	if err != nil {
		return nil, err
	}
	box := sandbox.Remote(container{id: id}, roots, summary)
	b.byUser[user] = box
	return box, nil
}

func (b *boxes) Close() error {
	b.mu.Lock()
	defer b.mu.Unlock()
	var errs []error
	for _, box := range b.byUser {
		errs = append(errs, box.Close())
	}
	return errors.Join(errs...)
}
```

装配：

```go
b := &boxes{containerOf: containerOf, byUser: map[string]sandbox.Box{}}
defer b.Close()

ws, err := workspace.New(workspace.Options{
	Box:    sandbox.Remote(nil, roots, summary), // 只用来写工具描述
	BoxFor: b.For,                               // 每次调用用这个用户自己的
})
if err != nil {
	return err
}
defer ws.Close()

h, err := host.New(ctx, host.Config{
	Tools: []kit.Provider{ws},
	Boxes: b.For,
	// ...
})
```

`Machine` 的每个方法，引擎依赖的语义：

| 方法 | 必须做到 |
| --- | --- |
| `Run` | 命令结束才返回；到 `c.Timeout` 或 `ctx` 结束时停掉命令；退出码非 0 是一个带退出码的 `Result`，不是错误。在 `c.Cwd` 里运行，带上 `c.Env` |
| `Start` | 一直运行到 `ctx` 结束或返回的 `Process`（`io.ReadWriteCloser`）关闭，`Timeout` 不适用。stdio MCP 服务器用它，`Process` 是它的标准输入输出 |
| `Stat` | 跟随链接；路径不存在时返回的错误要能被 `errors.Is(err, fs.ErrNotExist)` 认出，`write_file` 靠它判断是新建文件 |
| `ReadDir` | 按名字排序返回，和 `os.ReadDir` 一样，`grep` 和 `glob` 的遍历顺序来自这里 |
| `Open` | 读整个文件 |
| `WriteFile` | 自己建上级目录，整个替换文件，读的人看不到写了一半的文件 |
| `Close` | 只断开连接，机器和文件留给下一次 |

`Remote` 还会在机器里运行 `rmdir` 和 `mv -f` 来实现 `workspace/move`，机器里要有这两个命令。

::: details 用 docker exec 实现的 Machine（完整代码）

```go
// container 是一台用 docker exec 访问的机器：一个用户一个容器，容器就是隔离边界。
type container struct{ id string }

// docker 在容器里运行 argv；flags 放在容器 ID 前面（-w、-e）。退出码非 0 不算错误。
func (m container) docker(ctx context.Context, stdin io.Reader, flags []string, argv ...string) (out, errOut []byte, code int, err error) {
	args := slices.Concat([]string{"exec", "-i"}, flags, []string{m.id}, argv)
	cmd := exec.CommandContext(ctx, "docker", args...)
	var o, e bytes.Buffer
	cmd.Stdin, cmd.Stdout, cmd.Stderr = stdin, &o, &e
	err = cmd.Run()
	if exit := (*exec.ExitError)(nil); errors.As(err, &exit) {
		return o.Bytes(), e.Bytes(), exit.ExitCode(), nil
	}
	return o.Bytes(), e.Bytes(), 0, err
}

func (m container) Run(ctx context.Context, c sandbox.Command) (sandbox.Result, error) {
	if c.Timeout > 0 {
		var cancel context.CancelFunc
		ctx, cancel = context.WithTimeout(ctx, c.Timeout)
		defer cancel()
	}
	var flags []string
	if c.Cwd != "" {
		flags = append(flags, "-w", c.Cwd)
	}
	for k, v := range c.Env {
		flags = append(flags, "-e", k+"="+v)
	}
	out, errOut, code, err := m.docker(ctx, nil, flags, append([]string{c.Program}, c.Args...)...)
	if ctx.Err() != nil {
		return sandbox.Result{}, fmt.Errorf("timed out after %s and was killed", c.Timeout)
	}
	if err != nil {
		return sandbox.Result{}, err
	}
	return sandbox.Result{Stdout: string(out), Stderr: string(errOut), ExitCode: code}, nil
}

func (m container) Start(ctx context.Context, c sandbox.Command, stderr io.Writer) (sandbox.Process, error) {
	cmd := exec.CommandContext(ctx, "docker", slices.Concat([]string{"exec", "-i", m.id, c.Program}, c.Args)...)
	cmd.Stderr = stderr
	in, err := cmd.StdinPipe()
	if err != nil {
		return nil, err
	}
	out, err := cmd.StdoutPipe()
	if err != nil {
		return nil, err
	}
	if err := cmd.Start(); err != nil {
		return nil, err
	}
	return process{in, out, cmd}, nil
}

type process struct {
	io.WriteCloser
	io.Reader
	cmd *exec.Cmd
}

func (p process) Close() error { p.WriteCloser.Close(); return p.cmd.Wait() }

func (m container) Open(ctx context.Context, name string) (io.ReadCloser, error) {
	out, errOut, code, err := m.docker(ctx, nil, nil, "cat", "--", name)
	if err == nil && code != 0 {
		err = pathError(name, errOut)
	}
	if err != nil {
		return nil, err
	}
	return io.NopCloser(bytes.NewReader(out)), nil
}

// WriteFile 自己建上级目录，先写临时文件再改名，读的人看不到半个文件。
func (m container) WriteFile(ctx context.Context, name string, data []byte, perm fs.FileMode) error {
	script := `mkdir -p "$(dirname "$1")" && t="$1.tmp.$$" && cat > "$t" && chmod "$2" "$t" && mv -f "$t" "$1"`
	mode := strconv.FormatUint(uint64(perm.Perm()), 8)
	_, errOut, code, err := m.docker(ctx, bytes.NewReader(data), nil, "sh", "-c", script, "sh", name, mode)
	if err == nil && code != 0 {
		err = fmt.Errorf("write %s: %s", name, strings.TrimSpace(string(errOut)))
	}
	return err
}

func (m container) Stat(ctx context.Context, name string) (fs.FileInfo, error) {
	infos, err := m.stat(ctx, "stat", "-L", "-c", statFormat, "--", name)
	if err != nil {
		return nil, err
	}
	if len(infos) != 1 {
		return nil, fmt.Errorf("stat %s: unexpected output", name)
	}
	return infos[0], nil
}

// ReadDir 按名字排序，和 os.ReadDir 一样；grep 和 glob 的遍历顺序来自这里。
func (m container) ReadDir(ctx context.Context, dir string) ([]fs.DirEntry, error) {
	infos, err := m.stat(ctx, "find", dir, "-mindepth", "1", "-maxdepth", "1", "-exec", "stat", "-L", "-c", statFormat, "{}", "+")
	if err != nil {
		return nil, err
	}
	entries := make([]fs.DirEntry, len(infos))
	for i, info := range infos {
		entries[i] = fs.FileInfoToDirEntry(info)
	}
	slices.SortFunc(entries, func(a, b fs.DirEntry) int { return strings.Compare(a.Name(), b.Name()) })
	return entries, nil
}

// statFormat：大小、十六进制的原始 mode、修改时间、路径，每个文件一行。
const statFormat = "%s %f %Y %n"

func (m container) stat(ctx context.Context, argv ...string) ([]fs.FileInfo, error) {
	out, errOut, code, err := m.docker(ctx, nil, nil, argv...)
	if err == nil && code != 0 {
		err = pathError(argv[len(argv)-1], errOut)
	}
	if err != nil {
		return nil, err
	}
	var infos []fs.FileInfo
	for line := range strings.Lines(string(out)) {
		f := strings.SplitN(strings.TrimSuffix(line, "\n"), " ", 4)
		if len(f) != 4 {
			continue
		}
		size, _ := strconv.ParseInt(f[0], 10, 64)
		raw, _ := strconv.ParseUint(f[1], 16, 32)
		secs, _ := strconv.ParseInt(f[2], 10, 64)
		mode := fs.FileMode(raw & 0o777)
		switch raw & 0o170000 {
		case 0o040000:
			mode |= fs.ModeDir
		case 0o100000: // 普通文件
		default:
			mode |= fs.ModeIrregular
		}
		infos = append(infos, fileInfo{path.Base(f[3]), size, mode, time.Unix(secs, 0)})
	}
	return infos, nil
}

// pathError 把"不存在"翻译成 fs.ErrNotExist：write_file 靠它判断是新建文件。
func pathError(name string, stderr []byte) error {
	if bytes.Contains(stderr, []byte("No such file")) {
		return &fs.PathError{Op: "stat", Path: name, Err: fs.ErrNotExist}
	}
	return fmt.Errorf("%s: %s", name, strings.TrimSpace(string(stderr)))
}

// Close 只断开连接，容器和文件留给下一次。
func (m container) Close() error { return nil }

type fileInfo struct {
	name string
	size int64
	mode fs.FileMode
	mod  time.Time
}

func (i fileInfo) Name() string       { return i.name }
func (i fileInfo) Size() int64        { return i.size }
func (i fileInfo) Mode() fs.FileMode  { return i.mode }
func (i fileInfo) ModTime() time.Time { return i.mod }
func (i fileInfo) IsDir() bool        { return i.mode.IsDir() }
func (i fileInfo) Sys() any           { return nil }

var _ sandbox.Machine = container{}
```

文件名里有换行时 `stat` 的逐行输出会解析错；容器里要有 `sh`、`stat`、`find`、`cat`、`mkdir`、`chmod`、`mv`、`rmdir`。

:::

**引擎保证：**

- `Remote` 包出来的 Box 里，命令不能以全权运行（`FullAccess` 的命令直接报错 `sandbox: this sandbox cannot give a command full access`）；写文件只要求在根目录内；HTTP 请求（比如 HTTP MCP 服务器）从引擎进程发出，只连公网地址。
- 机器慢或卡住时，只卡住用到它的那一次调用；附件在写进日志之前、在调度之外读完。
- 工具调用里 `BoxFor` 返回错误时，这次调用失败，错误以 `workspace: the sandbox of the user:` 开头，交给模型；`Boxes` 返回错误时，`workspace/add` 和带附件的消息返回错误，这个用户的 MCP 服务器连不上（`mcp: the sandbox of the user: ...`）。

**宿主要保证：**

- **缓存每个用户的 Box。** 每一次工具调用都会调 `BoxFor`，不要每次都去创建或唤醒机器。机器的创建、找回、唤醒、休眠都在它背后由宿主做。
- **关闭 Box。** `workspace` 包只关 `Options.Box`，用户的 Box 由宿主在退出时关。
- **网络规则设在机器上。** 引擎不管云沙箱里命令的网络。
- **所有用户用同样的 `roots` 和 `summary`。** 工具描述按 `Options.Box` 写，模型看到的目录和规则来自它；用户的 Box 和它不同时，描述和实际规则对不上。

## 附件存储

消息带的图片和文本文件存在一个实现了 `app.Attachments` 的存储里：

```go
type Attachments interface {
	Put(ctx context.Context, key string, data []byte) error // 一个键只写一次
	Get(ctx context.Context, key string) ([]byte, error)    // 不存在时返回 fs.ErrNotExist
	Delete(ctx context.Context, key string) error           // 已经不在了不算错
	DeletePrefix(ctx context.Context, prefix string) error  // 删掉这个前缀下的全部
}
```

`host.New` 固定用 `blob.Dir(<Home>/attachments)`，`host.Config` 没有换存储的字段。要把附件放进对象存储，只能不经 `host` 自己装配：照 `host/host.go` 调 `app.New` 和 `run.New`，把你的实现传给它们（`run.New` 只用 `Get`）。下面是包一个对象存储客户端的实现（`bucket` 是宿主手里的 SDK，这里只写出用到的调用）：

```go
type bucket interface {
	PutObject(ctx context.Context, key string, data []byte, ifNoneMatch bool) error
	GetObject(ctx context.Context, key string) ([]byte, error) // 不存在时返回 errNoSuchKey
	DeleteObject(ctx context.Context, key string) error
	DeleteObjects(ctx context.Context, prefix string) error
}

var errNoSuchKey = errors.New("no such key")

// objects 把对象存储包成 app.Attachments；prefix 区分这个分片，键里已经带着会话 ID。
type objects struct {
	bucket bucket
	prefix string
}

func (o objects) Put(ctx context.Context, key string, data []byte) error {
	return o.bucket.PutObject(ctx, o.prefix+key, data, true) // 一个键只写一次
}

func (o objects) Get(ctx context.Context, key string) ([]byte, error) {
	data, err := o.bucket.GetObject(ctx, o.prefix+key)
	if errors.Is(err, errNoSuchKey) {
		return nil, fmt.Errorf("%s: %w", key, fs.ErrNotExist)
	}
	return data, err
}

func (o objects) Delete(ctx context.Context, key string) error {
	err := o.bucket.DeleteObject(ctx, o.prefix+key)
	if errors.Is(err, errNoSuchKey) {
		return nil // 已经不在了不算错
	}
	return err
}

func (o objects) DeletePrefix(ctx context.Context, prefix string) error {
	return o.bucket.DeleteObjects(ctx, o.prefix+prefix)
}

var _ app.Attachments = objects{}
```

**引擎保证：**

| 时机 | 调用 | 键 |
| --- | --- | --- |
| 发消息时（`turn/start`、`turn/steer`） | `Put`，每个附件一次 | `<会话 ID>/<UUID>.<扩展名>`，图片是 `.png`、`.jpg`、`.gif`、`.webp`，文本文件是 `.txt` |
| 每次模型调用 | `Get`，这次请求里还带着的每个附件 | 同上 |
| 客户端读附件（`attachment/read`） | `Get` | 同上 |
| 存到一半失败 | `Delete`，已经存进去的那几个 | 同上 |
| 删除会话 | `DeletePrefix("<会话 ID>/")`，带结尾的 `/` | 失败时会话已经删掉，返回 `the conversation is deleted, but not its attachments: ...` |

- 附件的源文件从用户自己的 Box 里读（`Boxes`），不是从引擎所在的机器；路径必须是绝对路径。
- 一条消息最多 10 个附件；图片最大 20 MiB，文本文件最大 256 KiB。超出时消息被拒绝。类型按文件内容判断。
- 发消息时的存储、客户端读附件、删除各有 1 分钟超时；模型调用时的读取跟着这一轮的 `ctx`。

**宿主要保证：**

- **`Get` 要快、要可靠。** 每次模型调用都会重新读请求里的附件，延迟直接加在这一轮上，读不到时这次模型调用失败。需要的话自己加缓存。
- **键只写一次。** 引擎不会覆盖同一个键，`blob.Dir` 用 `O_EXCL` 打开；对象存储上用条件写入能挡住意外的覆盖。

## 目录库

多进程部署时，分片的租约和用户的放置记在目录库里，接口是 `catalog.Catalog`。`catalog.OpenSQL(path)` 打开的 SQLite 文件是现在唯一的实现，所有进程要能打开同一个文件；要让目录库不依赖某一台机器，就在协调服务（比如 etcd）或单独部署的数据库上实现这个接口（引擎 README）。怎样用它部署见[多用户与分片部署](/zh/integrate/deploy)，机制见[分片与租约](/zh/engine/sharding)。

```go
type Catalog interface {
	Acquire(ctx context.Context, shard, owner, address string, accepting bool, ttl time.Duration) (epoch int64, held bool, err error)
	Renew(ctx context.Context, shard, owner string, epoch int64, ttl time.Duration, load int64) error
	Release(ctx context.Context, shard, owner string, epoch int64) error

	Locate(ctx context.Context, user string) (shard, address string, err error)
	ShardOf(ctx context.Context, user string) (string, error)
	Place(ctx context.Context, user, shard string) error
}
```

实现要守住的约定，按 `catalog/sql.go` 的做法：

| 方法 | 谁调 | 必须做到 |
| --- | --- | --- |
| `Acquire` | `shard.Member`，拿到之前每 TTL/3 一次 | 只在没人持有、或租约已过期时给出；给出时 epoch 比这个分片以前的都大，同时写下持有者的地址和 `accepting`。是否过期只按目录库自己的时钟判断 |
| `Renew` | 持有者，每 TTL/3 一次 | 只有 owner 和 epoch 都对上时续上，同时记下负载；否则返回 `catalog.ErrLeaseLost` |
| `Release` | 持有者退出时 | 只放掉 owner 和 epoch 对得上的租约，让备用进程立刻能拿 |
| `Locate` | 路由器和负载均衡器的 callout，每个握手一次 | 用户还没放置时放置他：在接新用户的分片里随机抽两个，取负载小的，负载相同取用户少的；没有可放的分片时返回 `catalog.ErrNoShard`。返回分片和它持有者的地址；没人持有或租约已过期时地址为空 |
| `ShardOf` | `shard.Member.Admit` | 只查，不放置；没放置时返回空字符串 |
| `Place` | 运维 | 把用户钉在一个分片上；用户已在别的分片时报错。要在用户有任何数据之前做 |

`Locate` 的放置和查找要在一个事务里，否则两个路由器可能把同一个新用户放到两个分片上。

## 认证

Ollupi 不做登录。登录在它之前完成，`Authenticate(ctx, token)` 只回答"这是谁的令牌"。令牌从 `Authorization: Bearer` 读，浏览器放在 WebSocket 子协议 `ollupi.token` 后面，不能放在 URL 里，见[网关协议](/zh/integrate/protocol)。

核对登录系统发出的会话令牌，库里只存令牌的哈希：

```go
// sessions 核对登录系统发出的令牌：库里只存令牌的哈希。
func sessions(db *sql.DB) auth.Authenticate {
	return func(ctx context.Context, token string) (string, error) {
		if token == "" {
			return "", auth.ErrUnknownToken
		}
		sum := sha256.Sum256([]byte(token))
		var user string
		err := db.QueryRowContext(ctx,
			`SELECT user_id FROM sessions WHERE token_sha256 = ? AND expires_at > ?`,
			sum[:], time.Now().UTC()).Scan(&user)
		if errors.Is(err, sql.ErrNoRows) {
			return "", auth.ErrUnknownToken
		}
		return user, err // 库连不上时是别的错误：客户端收到 503，稍后再来
	}
}
```

装配：`gateway.Options{Authenticate: sessions(authDB)}`。多分片部署时路由器用同一个函数（`router.NewLocator(sessions(authDB), catalog)`），见[多用户与分片部署](/zh/integrate/deploy)。

**引擎保证：**

- 每个 WebSocket 握手调一次 `Authenticate`，之后的消息不再调。经路由器进来的连接，路由器和分片各调一次。每次调用带 10 秒超时。
- 先查 `Host`，再查令牌。令牌为空也会传给 `Authenticate`。返回 `auth.ErrUnknownToken` 时回 401 `invalid or missing gateway token`；返回别的错误时，网关回 503 加 `Retry-After`（`the token cannot be checked now; try again`），路由器回 503 `no shard can take this user now`。
- 返回的 `user` 就是引擎里的用户 ID：这个进程第一次见到他时 `EnsureUser` 建出他的几行记录，之后他的会话、工作区、记忆、设置都挂在这个 ID 上。

**宿主要保证：**

- **用户 ID 稳定、唯一、非空。** 不要用会变的东西（比如邮箱）做 ID：ID 一变，引擎里就是一个没有任何数据的新用户。引擎不检查空字符串。
- **快，并且并发安全。** 每个新连接都要等它返回，重启后很多连接会同时调它。
- **分清"不认识"和"查不了"。** 令牌无效返回 `auth.ErrUnknownToken`，协议让客户端不再重连；依赖的服务暂时不可用时返回别的错误，客户端会按 `Retry-After` 回来。
- **令牌作废要自己处理。** 令牌作废后，已经建立的连接不会断开，直到它到了寿命（15 到 20 小时）或因别的原因断开。

::: info 演进
v0.14.0 之前 `Authenticate` 是 `func(token string) (user string, ok bool)`，没有 ctx，也分不出"查不了"。`e36b07e` 改成现在的签名，令牌的读法和 `ErrUnknownToken` 在 v0.17.0 移进 `auth` 包。
:::

## 代码位置

| 路径 | 职责 |
|---|---|
| `host/host.go`、`host/models.go` | 扩展点字段，`ClientFor` 和 `Connections` 怎样选客户端，内置工具的装配 |
| `run/model.go` | 每次模型请求取客户端、读附件 |
| `pkg/llm/chat.go`、`connection.go` | `Client` 接口、并发名额、重试 |
| `tool/tool.go` | `Caller`、`Call`、`Annotations`、`Plan` |
| `tool/kit/kit.go`、`schema.go` | `Provider`、`Spec`、`Result`、注册表、`InputSchema`、`DecodeArguments`、输出截断 |
| `policy/checker.go`、`rules.go`、`validate.go` | 标注怎样决定审批、`__` 的处理、规则匹配 |
| `tool/builtin/workspace/tool.go`、`dirs.go` | `workspace.Options` 的 `Box`、`BoxFor`、`BoxIn` |
| `tool/mcp/servers.go` | 每个用户的注册表、MCP 工具名规则 |
| `pkg/sandbox/box.go`、`remote.go` | `Box`、`Machine`、`Remote` |
| `app/app.go`、`app/attachments.go`、`blob/blob.go` | `Attachments` 接口、附件的校验和存取、`blob.Dir` |
| `catalog/catalog.go`、`catalog/sql.go` | `Catalog` 接口和 SQLite 实现 |
| `auth/auth.go`、`gateway/auth.go`、`router/router.go` | `Authenticate`、令牌的读法、握手时的校验 |
