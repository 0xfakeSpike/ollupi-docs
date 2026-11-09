# 扩展点

引擎留了五个口子给宿主（host）接自己的东西：每个用户自己的模型密钥、自己的工具、云沙箱、附件存储、登录系统。每个口子都是 `agent.Config` 或 `gateway.Options` 里的一个字段，填一个函数或一个接口实现。全部字段见 [Config 参考](/zh/integrate/config)，最小宿主程序见[把引擎嵌进服务](/zh/integrate/embed)。

| 扩展点 | 填哪里 | 不填时 |
| --- | --- | --- |
| [每用户的模型客户端](#每用户的模型客户端) | `Config.ClientFor`，记忆提炼另有 `memory.Options.ClientFor` | 所有用户共用 `Connections` 里的客户端和配额 |
| [自己的工具](#自己的工具) | `Config.Providers`（所有用户）、`Config.ToolsFor`（每个用户） | 只有引擎内置的工具 |
| [云沙箱](#云沙箱) | `Config.BoxFor`、`workspace.Options.BoxFor` 或 `BoxIn`、`mcp.NewUsers` 的 `boxFor` | 本机 `sandbox.Here()` |
| [附件存储](#附件存储) | `Config.Attachments` | 有 `AttachmentsDir` 时存本机目录，都没有时消息不能带附件 |
| [认证](#认证) | `gateway.Options.Authenticate` | 用 `Token`，只有 `default` 一个用户 |

本页的代码对着引擎 v0.11.3 编译并通过 `go vet`，用到的包到 v0.12.1 只增加了字段（`BoxIn`、`EnvironmentID`），没有删改；按会话选择环境那一段对着 v0.12.0 编译过。工具那一节的审批结果用 `permission.New` 和 `Decide` 实际跑过。云沙箱那段没有在真实容器里跑过。

## 每用户的模型客户端

`ClientFor(user, connection)` 给这个用户的轮次（turn）返回一个模型客户端，让他的请求用他自己的密钥和配额。返回值实现 `llm.Client`，三个内置客户端（`llm.NewOpenAI`、`NewAnthropic`、`NewGemini`）都是：

```go
type Client interface {
	Chat(ctx context.Context, req ChatRequest, onDelta func(Delta)) (ChatResponse, error)
	Limits(model string) (Limits, error)
}
```

按用户缓存客户端：

```go
// userClients 给每个用户一个自己的 OpenAI 客户端，按用户缓存。
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

// Forget 在用户换了密钥后调用：下一轮起用新客户端，进行中的调用继续用旧的。
func (c *userClients) Forget(user string) {
	c.mu.Lock()
	defer c.mu.Unlock()
	delete(c.byUser, user)
}
```

装配时 `Connections` 仍然要填，因为启动校验和窗口大小读的是它：

```go
limits := map[string]llm.Limits{"gpt-5.2": {Context: 400_000, Output: 128_000}}
clients := &userClients{limits: limits, keyOf: keys, byUser: map[string]llm.Client{}}

a := agent.New(agent.Config{
	Models:      []llm.Model{{Name: "gpt-5.2", Connection: "openai"}},
	Connections: map[string]llm.Client{"openai": llm.NewOpenAI("", "", 4, limits)},
	ClientFor:   clients.For,
	// ...
})
```

**引擎保证：**

- 一轮每次进槽位（slot）运行时，用这一轮的用户和模型连接调一次 `ClientFor`（`agent/run.go` 的 `runTurn`）。子 agent 和父会话是同一个用户，用同一个客户端。
- `ClientFor` 返回错误时这一轮失败，错误是 `agent: the model client of the user: ...`。它 panic 也只让这一轮失败，panic 的内容不写进轮次的错误，同一分片上别的会话照常运行（`TestACrashFailsTheTurnAndNothingElse`）。
- 窗口大小和启动时的提示词检查读的都是 `Connections[connection].Limits`，不读 `ClientFor` 返回的客户端。

**宿主要保证：**

- **每次返回同一个客户端。** 并发名额属于客户端：`NewOpenAI` 的第三个参数建一个名额通道。每次新建一个客户端，名额通道也是新的，这个用户同时在途的请求就不受限制了。`Config.ClientFor` 的注释写明了这一点。
- **用户客户端声明和 `Connections` 一样的 limits。** 引擎按 `Connections` 算窗口；Anthropic 和 Gemini 客户端每次请求时还会用自己声明的 limits 算回答上限，声明里没有这个模型时请求直接失败。
- **并发安全。** 多个槽位会同时调它。
- **记忆提炼另配。** 记忆管理器的 `memory.Options.ClientFor(user)` 是单独的字段，不填时所有用户的记忆提炼共用 `memory.New` 拿到的那个客户端，见[记忆](/zh/engine/memory)。

用户客户端的并发名额（`calls`）：

| 参数 | 默认 | 调大 | 调小 |
| --- | --- | --- | --- |
| `calls` | `llm.DefaultCalls`，4（传 0 或负数时） | 这个用户同时在途的模型请求变多，超过服务商给这个密钥的配额时遇到 429，每次请求最多重试 8 次，重试期间占着槽位 | 请求在通道上排队，排队的轮次占着槽位不干活 |

所有用户的名额之和不受分片限制，分片能同时跑多少轮只由 `Slots` 决定，见[容量规划与限流](/zh/integrate/capacity)。重试和名额的机制见[模型接入](/zh/engine/models#连接与并发限制)。

## 自己的工具

工具实现 `tools.Provider` 的三个方法，放进 `Config.Providers` 就是所有用户共有的；`Config.ToolsFor(user)` 返回某个用户额外的一组（`tools.Set`），比如他自己的 MCP 服务器。`Spec` 各字段、注册表、一次调用的生命周期见[工具](/zh/engine/tools)。

一个读、关工单的 provider：

```go
// Lookup 和 Close 是两个工具的参数，InputSchema 从它们生成。
type Lookup struct {
	ID string `json:"id" jsonschema:"The ticket id, such as T-1024."`
}

type Close struct {
	ID     string `json:"id" jsonschema:"The ticket id."`
	Reason string `json:"reason" jsonschema:"One sentence the customer will read."`
}

// Tickets 是宿主自己的工单系统。ID 是 provider 名，也是工具名 "__" 前面那一段。
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

func (t *Tickets) ToolList(context.Context) ([]*tools.Spec, error) {
	return []*tools.Spec{
		{
			Name:        "tickets__lookup",
			Description: "Read one ticket with its messages.",
			InputSchema: tools.InputSchema[Lookup](),
			// 只读、不出这台机器：三档策略下都不问，同一批里可以并行。
			Annotations: &tools.Annotations{ReadOnlyHint: true, OpenWorldHint: tools.Hint(false)},
		},
		{
			Name:        "tickets__close",
			Description: "Close a ticket and send the reason to the customer.",
			InputSchema: tools.InputSchema[Close](),
			Annotations: &tools.Annotations{DestructiveHint: tools.Hint(true), OpenWorldHint: tools.Hint(true)},
			// 有了它，规则可以写 tickets__close(T-1*)，审批卡片显示 Text。
			PermissionContent: func(_ context.Context, args map[string]any) (tools.Content, error) {
				c, err := tools.DecodeArguments[Close](args)
				if err != nil {
					return tools.Content{}, err
				}
				return tools.Content{Text: "close " + c.ID + ": " + c.Reason, Match: strings.ToLower(c.ID)}, nil
			},
		},
	}, nil
}

func (t *Tickets) Invoke(ctx context.Context, tool string, args map[string]any) (tools.Result, error) {
	user := tools.CallerOf(ctx).UserID // 只做这个用户的事
	switch tool {
	case "tickets__lookup":
		in, err := tools.DecodeArguments[Lookup](args)
		if err != nil {
			return tools.Result{}, err
		}
		ticket, err := t.backend.Get(ctx, user, in.ID)
		return tools.Result{Output: ticket}, err
	case "tickets__close":
		in, err := tools.DecodeArguments[Close](args)
		if err != nil {
			return tools.Result{}, err
		}
		return tools.Result{Output: "closed"}, t.backend.Close(ctx, user, in.ID, in.Reason)
	}
	return tools.Result{}, fmt.Errorf("tickets: no tool %q", tool)
}
```

只有部分用户开通工单系统时，用 `ToolsFor` 把它和用户的 MCP 服务器合成一个 `Set`：

```go
// userTools 把每个用户的工单工具和他的 MCP 服务器合成一个 Set。
// 两边都没变时返回同一个指针，引擎据此复用已经建好的注册表。
type userTools struct {
	mcp     *mcp.Users
	tickets func(user string) *Tickets // 没开通工单系统的用户返回 nil

	mu    sync.Mutex
	built map[string]builtSet
}

type builtSet struct {
	from    *tools.Set // 合成时用的 MCP Set
	tickets *Tickets
	set     *tools.Set
}

func (u *userTools) For(user string) (*tools.Set, error) {
	servers, err := u.mcp.Tools(user)
	if err != nil {
		return nil, err
	}
	t := u.tickets(user)
	u.mu.Lock()
	defer u.mu.Unlock()
	if b, ok := u.built[user]; ok && b.from == servers && b.tickets == t {
		return b.set, nil
	}
	set := &tools.Set{
		Providers:   append([]tools.Provider(nil), servers.Providers...),
		Unavailable: servers.Unavailable,
	}
	if t != nil {
		set.Providers = append(set.Providers, t)
	}
	u.built[user] = builtSet{from: servers, tickets: t, set: set}
	return set, nil
}
```

所有用户都有的话，直接放进 `Config.Providers: []tools.Provider{ws, tickets}`。

### 命名

| 规则 | 不遵守时 |
| --- | --- |
| provider ID 非空，所有 provider 之间不重复 | `tools.New` 报错。共用工具出错时 `Start` 失败；用户工具出错时这个用户的轮次失败，错误以 `agent: the tools of the user:` 开头 |
| 工具名非空，在这个用户的整个注册表里不重复，包括内置工具 | 同上 |
| 工具名写成 `<provider ID>__<工具>` | 见下面两条 |

用 `__` 连接有两个作用：

- **默认权限里可以提它。** `ToolsFor` 设了时，agent 默认那一层权限服务的是工具各不相同的用户。规则里写的 `tickets__close`，在没有 `tickets` 这个 provider 的用户那里不算错；名字里不带 `__` 的用户工具，默认规则里一提，没有它的用户就会报"不在注册表里"。
- **可以延迟加载。** 名字含 `__` 的工具算外部工具，全部工具定义超过输入预算的 10% 时，它们只列名字，模型用到时再载入，见[延迟加载](/zh/engine/tools#延迟加载)。

注册表本身不限制字符。MCP 工具名按 `^[A-Za-z0-9_-]{1,64}$` 过滤，不合的跳过；自己的工具照这个规则写最稳妥，超出的名字可能被模型服务商拒绝（这一点是推断，引擎没有校验）。

### 标注决定审批

审批策略只看 `ReadOnlyHint` 和 `OpenWorldHint`。`OpenWorldHint` 不设时当作真。`DestructiveHint`、`IdempotentHint` 原样交给客户端显示，不影响审批。

| 工具的标注 | 严格（`untrusted`） | 适中（`on-request`） | 宽松（`never`） |
| --- | --- | --- | --- |
| `ReadOnlyHint: true`，`OpenWorldHint: false` | 运行 | 运行 | 运行 |
| `ReadOnlyHint: true`，`OpenWorldHint` 不设或为真 | 问 | 运行 | 运行 |
| 不是只读，或没有标注 | 问 | 问 | 运行 |

规则先于策略：上例里 `ask: ["tickets__close(T-1*)"]` 在宽松下也会问，`allow: ["tickets__close(T-1*)"]` 在严格下也直接运行。规则的说明符要靠 `PermissionContent` 才能写：没有它的工具，规则只能按工具名写。说明符的第一个词会被转成小写，所以 `Match` 也写成小写。规则语法见[审批与权限](/zh/engine/permissions#规则语法)。

标了只读、没标 `Serial` 的调用，同一批里会并发执行。标错的工具会在适中策略下不问就运行，还可能被并行，引擎不核对标注。

### 引擎保证与宿主责任

**引擎保证：**

- 参数先按 `InputSchema` 校验，不合的调用不进 `Invoke`，原因作为工具结果交给模型。`tools.InputSchema[T]()` 生成的 schema 不允许多余字段，缺必填字段也会被拒绝。
- `Invoke` panic 时只让这一次调用失败（"the tool crashed"），进程不受影响。
- 返回的 `Output` 编码成 JSON 超过 1 MiB 时截断，见[输出截断](/zh/engine/tools#输出截断)。
- 用户中断这一轮、或者这一轮超过 `RunLimit` 时，传给 `Invoke` 的 `ctx` 会结束。

**宿主要保证：**

- **按用户隔离。** 引擎不知道你的工具碰的是谁的数据。`tools.CallerOf(ctx)` 给出 `UserID`、`ThreadID`、`WorkspaceID`，工具自己只做这个用户的事。
- **`ToolsFor` 没变就返回同一个 `*tools.Set`。** 引擎按指针缓存每个用户的注册表，指针变了才重建，重建时会调这个用户所有 provider 的 `ToolList`。`ToolsFor` 在每一轮运行、列工具、校验权限设置时都会被调，要便宜。
- **连不上的 provider 写进 `Set.Unavailable`。** 写 provider ID。它的工具不提供，但引用它们的权限规则不算错。不写的话，这个用户的工作区或会话规则里只要提到它的工具，每一轮都会因为规则引用了不存在的工具而失败。
- **自己关闭 provider。** 引擎不调任何 provider 的 `Close`。
- **需要审批前冻结执行内容的工具实现 `Local`。** 只有执行内容可能在审批期间变化的工具才需要，比如命令和文件修改，见[审批前冻结](/zh/engine/tools#审批前冻结)。

## 云沙箱

用户的命令、文件、附件来源和 stdio MCP 服务器都经 `sandbox.Box` 访问。接云沙箱只需要实现 `sandbox.Machine`，再用 `sandbox.Remote(machine, roots, summary)` 包成 `Box`。`Machine` 的定义、`Remote` 和本机沙箱语义的区别见[云沙箱接入点](/zh/engine/sandbox#云沙箱接入点)。

::: warning 还没有服务商实现
引擎仓库里 `Machine` 的实现只在测试里，没有接入任何云沙箱服务商，路线图上的参考部署打算先用容器。下面的实现用 `docker exec` 访问每个用户一个容器，编译通过，没有在真实容器里跑过。
:::

`BoxFor` 要填在三个地方，用同一个函数：

| 位置 | 谁用它 | 不填时 |
| --- | --- | --- |
| `agent.Config.BoxFor` | 读附件的源文件、`workspace/add` 和 `workspace/move` 校验路径 | `sandbox.Here()`，本机 |
| `workspace.Options.BoxFor` | 每一次 `run_command`、文件工具、读取工具 | 所有用户都用 `Options.Box` |
| `mcp.NewUsers` 的第四个参数 | 启动这个用户的 stdio MCP 服务器 | 必须传 |

只填了第一个时，工作区添加在用户的机器里，工具却在本机运行，两边对不上。

### 按会话选择环境

一个用户可以有几个执行环境，会话开始时选一个，之后不变，见[执行环境](/zh/integrate/protocol/workspaces#执行环境的方法)。`Config.BoxFor` 是用户在这台机器上的那个 Box，工作区校验和附件读取用它；配了 `workspace.Options.BoxIn` 时，每次工具调用在哪个 Box 里跑，由它按会话的环境决定。

| `BoxIn(caller)` 返回 | 这次调用 |
| --- | --- |
| `(box, nil)` | 在这个 Box 里运行 |
| `(nil, nil)` | 在 `Options.Box` 里运行。注意不是 `BoxFor` 给的 Box |
| `(nil, err)` | 失败，错误以 `workspace: the environment of the conversation:` 开头交给模型 |

配了 `BoxIn` 时，`BoxFor` 不参与工具调用。`caller.EnvironmentID` 是会话的环境 ID，新会话总会带上；`caller.UserID` 是用户。按环境找机器：

```go
BoxIn: func(c tools.Caller) (sandbox.Box, error) {
	if c.EnvironmentID == "" {
		return b.For(c.UserID) // 没有环境的调用，按用户在这台机器上的 Box 处理
	}
	env, err := db.EnvironmentOf(c.UserID, c.EnvironmentID)
	if err != nil {
		return nil, err
	}
	if env.Kind == repo.EnvironmentLocal {
		return b.For(c.UserID) // 和 Config.BoxFor 同一个
	}
	return machines.For(c.UserID, env.ID) // 宿主自己的：按环境找到或唤醒那台云沙箱
},
```

`machines` 是宿主自己的代码，和上面的 `boxes` 一样要缓存、要在退出时关。环境只是库里的一行名字和种类，引擎不知道它对应哪台机器，这个对应关系由宿主保存。配了 `BoxIn` 时，`run_command` 的描述会多一句：会话在它开始时选的环境里运行，那里的文件夹不一定是这台机器的。

桌面端是 `BoxIn` 的一个实际用法：它只有本机，所以 `local` 环境返回 `(nil, nil)`，`machine` 环境返回错误，让模型告诉用户换到 `This computer` 开会话（`ollupi-desktop/sidecar/internal/host/host.go`）。

::: info 演进
v0.12.0 之前没有执行环境，每个用户只有一个 Box，`workspace.Options.BoxFor` 同时决定工作区校验、附件和每次工具调用在哪里跑。`5f64857`（v0.12.0）加入执行环境和 `BoxIn`，`Config.BoxFor` 的意思收窄为用户在这台机器上的 Box。没有配 `BoxIn` 的宿主，工具调用照旧走 `BoxFor`，升级后行为不变。
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

servers := mcp.NewUsers(ctx, mcp.Client{}, mcpConfigOf, b.For)
defer servers.Close()

a := agent.New(agent.Config{
	Providers: []tools.Provider{ws},
	ToolsFor:  servers.Tools,
	BoxFor:    b.For,
	// ...
})
```

`Machine` 的每个方法，引擎依赖的语义：

| 方法 | 必须做到 |
| --- | --- |
| `Run` | 命令结束才返回；到 `c.Timeout` 或 `ctx` 结束时停掉命令；退出码非 0 是一个带退出码的 `Result`，不是错误。在 `c.Cwd` 里运行，带上 `c.Env` |
| `Start` | 一直运行到 `ctx` 结束或返回的 `Process` 关闭，`Timeout` 不适用。stdio MCP 服务器用它，`Process` 是它的标准输入输出 |
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

- `Remote` 包出来的 Box 里，命令不能提权（`Unsandboxed` 的命令直接报错），`run_command` 的参数里也不出现提权选项；写文件只要求在根目录内；HTTP 请求（比如 HTTP MCP 服务器）从引擎进程发出，只连公网地址。
- 机器慢或卡住时，只卡住用到它的那一次调用。附件在进调度循环之前就读完，一个用户的机器卡住不会拖住同一分片上别的会话（`agent/resilience_test.go` 的 `TestASlowSandboxDoesNotHoldUpOtherThreads`）。
- `BoxFor` 返回错误时，这次工具调用失败，错误以 `workspace: the sandbox of the user:` 开头，交给模型；`workspace/add` 返回错误。

**宿主要保证：**

- **缓存每个用户的 Box。** 每一次工具调用都会调 `BoxFor`，不要每次都去创建或唤醒机器。机器的创建、找回、唤醒、休眠都在 `BoxFor` 背后由宿主做。
- **关闭 Box。** `workspace` 包只关 `Options.Box`，用户的 Box 由宿主在退出时关。
- **网络规则设在机器上。** 引擎不管云沙箱里命令的网络。
- **所有用户用同样的 `roots` 和 `summary`。** 工具描述按 `Options.Box` 写，模型看到的目录和规则来自它；用户的 Box 和它不同时，描述和实际规则对不上。

## 附件存储

消息带的图片和文本文件存进 `blobs.Store`。默认实现 `blobs.Dir` 是本机的一个目录；接对象存储时实现同样的四个方法：

```go
type Store interface {
	Put(ctx context.Context, key string, data []byte) error   // 一个键只写一次
	Get(ctx context.Context, key string) ([]byte, error)      // 不存在时返回 fs.ErrNotExist
	Delete(ctx context.Context, key string) error             // 已经不在了不算错
	DeletePrefix(ctx context.Context, prefix string) error    // 删掉 prefix 这个"文件夹"下的全部
}
```

包一个对象存储客户端（`bucket` 是宿主手里的 SDK，这里只写出用到的调用）：

```go
type bucket interface {
	PutObject(ctx context.Context, key string, data []byte, ifNoneMatch bool) error
	GetObject(ctx context.Context, key string) ([]byte, error) // 不存在时返回 errNoSuchKey
	DeleteObject(ctx context.Context, key string) error
	DeleteObjects(ctx context.Context, prefix string) error
}

var errNoSuchKey = errors.New("no such key")

// objects 把对象存储包成 blobs.Store；prefix 区分这个分片，键里已经带着会话 ID。
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
	return o.bucket.DeleteObjects(ctx, o.prefix+prefix+"/")
}
```

装配：`agent.Config{Attachments: objects{bucket: store, prefix: "shard-1/"}}`。`prefix` 是这里的写法，不是引擎的要求。

**引擎保证：**

| 时机 | 调用 | 键 |
| --- | --- | --- |
| 发消息时（`turn/start`、`turn/steer`） | `Put`，每个附件一次 | `<会话 ID>/<UUID>.<扩展名>`，图片是 `.png`、`.jpg`、`.gif`、`.webp`，文本文件是 `.txt` |
| 每次模型调用 | `Get`，这次请求里还带着的每个附件 | 同上 |
| 客户端读附件（`attachment/read`） | `Get` | 同上 |
| 存到一半失败，或这条消息被拒绝 | `Delete`，已经存进去的那几个 | 同上 |
| 删除会话 | `DeletePrefix(会话 ID)` | 失败只写日志，会话照删 |

- 附件的源文件从用户自己的 Box 里读（`Config.BoxFor`），不是从引擎所在的机器。
- 一条消息最多 10 个附件；图片最大 20 MiB，文本文件最大 256 KiB。超出时消息被拒绝，协议上是 `-32602`。
- 发消息时的存储、客户端读附件、删除各有 1 分钟超时；模型调用时的读取跟着这一轮的 `ctx`。发消息时的存储在调度循环之外完成，慢的存储不会拖住别的会话。
- 没有 `Attachments` 也没有 `AttachmentsDir` 时，带附件的消息被拒绝："this agent takes no attachments"。

**宿主要保证：**

- **`Get` 要快、要可靠。** 每次模型调用都会重新读请求里的附件，延迟直接加在这一轮上，读不到时这次模型调用失败。需要的话在 `Store` 里自己加缓存。
- **键只写一次。** 引擎不会覆盖同一个键，`blobs.Dir` 用 `O_EXCL` 打开；对象存储上用条件写入能挡住意外的覆盖。
- **`DeletePrefix` 只删这个前缀下的。** 引擎传的是会话 ID，不带结尾的 `/`，实现时自己补上分隔符，避免删到别的前缀。

## 认证

Ollupi 不做登录。登录在它之前完成，`Authenticate(token)` 只回答"这是谁的令牌"。令牌怎样从客户端传过来（`Authorization: Bearer` 或 WebSocket 子协议），见[令牌认证](/zh/engine/sharding#令牌认证)。

核对登录系统发出的会话令牌，库里只存令牌的哈希：

```go
// sessions 核对登录系统发出的令牌：库里只存令牌的哈希。
func sessions(db *sql.DB) func(token string) (string, bool) {
	return func(token string) (string, bool) {
		if token == "" {
			return "", false
		}
		sum := sha256.Sum256([]byte(token))
		ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
		defer cancel()
		var user string
		err := db.QueryRowContext(ctx,
			`SELECT user_id FROM sessions WHERE token_sha256 = ? AND expires_at > ?`,
			sum[:], time.Now().UTC()).Scan(&user)
		if err != nil {
			return "", false
		}
		return user, true
	}
}
```

装配：`gateway.Options{Authenticate: sessions(authDB)}`。多分片部署时路由器用同一个函数（`gateway.NewRouter(authenticate, directory)`），分片进程用 `gateway.OnShard(shard, directory, authenticate)` 包一层，拒绝不属于这个分片的用户，见[分片与租约](/zh/engine/sharding#路由器)。

**引擎保证：**

- 每个 WebSocket 连接在握手前调一次 `Authenticate`，之后的消息不再调。经路由器进来的连接，路由器和分片各调一次。
- 先查 `Host`，再查令牌。令牌为空也会传给 `Authenticate`。返回 `ok == false` 时回 401 `invalid or missing gateway token`。
- 返回的 `user` 就是引擎里的用户 ID：第一次连上时 `EnsureUser` 建出这个用户的几行记录，之后他的会话、工作区、记忆、设置都挂在这个 ID 上。同一个用户的新连接取代旧连接。

**宿主要保证：**

- **用户 ID 稳定、唯一、非空。** 不要用会变的东西（比如邮箱）做 ID：ID 一变，引擎里就是一个没有任何数据的新用户。返回空字符串且 `ok == true` 时，`EnsureUser` 失败，连接收到 500。
- **快，并且并发安全。** 每个新连接都要等它返回，很多连接会同时调它。
- **令牌作废要自己处理。** 令牌作废后，已经建立的连接不会断开，网关没有按用户断开连接的方法。

## 代码位置

| 仓库 | 路径 | 职责 |
|---|---|---|
| ollupi | `agent/agent.go` | `Config` 里五个扩展点的字段与注释、`registryFor`、`buildTools` |
| ollupi | `agent/models.go` | `clientFor`、`windowFor` |
| ollupi | `agent/run.go` | 每轮运行时取客户端、注册表和权限 |
| ollupi | `agent/attachments.go` | 附件的校验、存取、清理 |
| ollupi | `agent/memory/manager.go` | `memory.Options.ClientFor` |
| ollupi | `pkg/llm/chat.go`、`connection.go` | `Client` 接口、并发名额、重试 |
| ollupi | `tools/provider.go`、`spec.go`、`registry.go`、`schema.go` | `Provider`、`Spec`、`Set`、注册表、`InputSchema`、`DecodeArguments` |
| ollupi | `agent/permission/policy.go`、`permission.go`、`rules.go` | 标注怎样决定审批、`__` 的处理、规则匹配 |
| ollupi | `tools/workspace/tool.go`、`dirs.go` | `workspace.Options` 的 `Box`、`BoxFor`、`BoxIn` |
| ollupi | `agent/environments.go`、`repo/environments.go` | 执行环境，`EnvironmentOf` |
| ollupi | `tools/mcp/servers.go` | `NewUsers`、`Users.Tools`、MCP 工具名规则 |
| ollupi | `pkg/sandbox/box.go` | `Box`、`Machine`、`Remote` 及各方法的约定 |
| ollupi | `pkg/blobs/blobs.go` | `Store`、`Dir` |
| ollupi | `gateway/serve.go`、`server.go`、`router.go` | `Options.Authenticate`、握手时的校验、`NewRouter`、`OnShard` |
| ollupi | `agent/users_test.go`、`agent/resilience_test.go`、`tools/workspace/box_test.go` | 每用户客户端、每用户工具、云沙箱的测试，也是接法的参考 |
