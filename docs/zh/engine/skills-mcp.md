# 技能与 MCP

技能和 MCP 都是把引擎之外的内容接进模型的方式：技能（skill）是一份写给模型看的说明，按角色装在技能目录里；MCP（Model Context Protocol）服务器是一个别人实现好的工具服务，每个用户在自己的设置里登记。两者都以工具提供者（`kit.Provider`）的身份进入这个用户的工具集，工具集、一次调用的生命周期和延迟加载见[工具系统](/zh/engine/tools)；这里写各自的格式、装配方式和边界。

## 为什么这样设计

- **系统提示词只列名字和一句描述，正文按需激活。** 技能目录每行一个 `- name: description`，正文由 `activate_skill` 返回，同样的预算能列更多技能；正文作为工具结果写进对话日志，重启和压缩之后仍然有效。
- **技能按角色安装，用到时才读。** 每个角色（见[执行模型](/zh/engine/execution)）只看自己目录里的技能；每次模型调用和每次技能工具调用都重新读目录，装上、改掉一个技能下一次就生效，不用重启。
- **坏技能在启动时暴露。** 启动时把整个技能目录检查一遍，任何一个技能解析失败，`host.New` 就失败，不会悄悄少一个技能，见[设计决策 18](/zh/reference/decisions#_18-出错即暴露)。
- **MCP 服务器是用户自己的设置，存在库里。** 每个用户通过协议增删自己的服务器，改动下一次用到时生效，不用重启，也不经过宿主（host）的配置。
- **MCP 工具名带服务器前缀，连不上的服务器跳过并报告原因。** 工具一律注册成 `<server>__<tool>`，服务器以后新增的工具不会和别的工具撞名；连不上的服务器不让轮次失败，状态里写明原因，引用它的规则保留但暂时不匹配任何调用。
- **每个用户的服务器在自己的沙箱里按需启动。** 用户第一次需要工具时，才在他第一个执行环境的 `Box` 里启动他的服务器，各用户的进程和连接互不共享。服务器属于用户、不属于某个会话，所以不跟着会话换环境。
- **服务器自己声明的只读不算数。** MCP 工具一律当作会改东西、会访问外部世界，审批策略不因服务器的标注放行。

代价：每个用户一组服务器进程；一台服务器掉线、或用户改了任一台的配置，这个用户的整组服务器都关掉重连；MCP 工具在 `on-request` 下每次都问，规则只能写到工具名；每次模型调用都要读一遍角色的技能目录。

::: info 演进
- 技能目录早期每个技能是一段缩进 JSON，工具名不带前缀；技能原来是所有角色共用一个目录、启动时读一次，MCP 服务器原来是宿主启动时读一次的配置。现在技能按角色安装、每次模型调用重读，MCP 服务器按用户存在库里、经协议增删。
:::

## 技能是什么

一个技能是一个目录，目录里必须有 `SKILL.md`，目录名必须等于 frontmatter 里的 `name`。技能目录按角色分一层：

```text
<SkillsDir>/
  full-main-agent/my-skill/{SKILL.md, references/detail.md}
  compact-main-agent/my-skill/SKILL.md
  hub-main-agent/ … research-sub-agent/
```

角色目录的名字就是 `agent.Names` 里的十一个：主 agent 三个（`full-main-agent`、`compact-main-agent`、`hub-main-agent`），子 agent 八个（`general-sub-agent`、`browser-sub-agent`、`design-sub-agent`、`codebase-sub-agent`、`frontend-sub-agent`、`backend-sub-agent`、`writing-sub-agent`、`research-sub-agent`）。普通主 agent 按模型输入大小在完整和精简之间选，hub 工作区的会话固定是 `hub-main-agent`，所以主 agent 的技能要在三个目录里各放一份。白名单见[执行模型](/zh/engine/execution)。

`SKILL.md` 是 YAML frontmatter 加正文，frontmatter 只读三个键：

| 键 | 必填 | 规则 |
| --- | --- | --- |
| `name` | 是 | 匹配 `^[a-z0-9]+(?:-[a-z0-9]+)*$`，不超过 64 个 rune |
| `description` | 是 | 不超过 1024 个 rune（`maxDescriptionRunes`）；列在系统提示词的 `# AVAILABLE SKILLS` 里 |
| `metadata.version` | 否 | 转成字符串，随 `activate_skill` 返回 |

正文是激活后进上下文的部分，上限 20000 rune（`maxInstructionRunes`）、500 行（`maxInstructionLines`），为空也报错。

其余文件是资源（resources），`read_skill_resource` 只能读列出来的这些：

| 规则 | 值 |
| --- | --- |
| 允许的扩展名 | `.md`、`.txt`、`.json`、`.yaml`、`.yml`、`.toml`、`.go`、`.py`、`.js`、`.ts`、`.sh` |
| 单个文件上限 | 1 MiB（`maxReadableResourceB`），读的时候检查 |
| 列出的文件数上限 | 200（`maxListedResources`），超过时这个技能解析失败 |
| 不进入、不列出 | 点开头的子目录、链接（指向目录或文件都算）、`SKILL.md` 本身、扩展名不在表里的文件 |

## 发现与加载

技能目录由 `host.Config.SkillsDir` 给出，空字符串表示不用技能：这时不检查目录，也不装 `skills` 提供者。

启动时 `host.New` 用 `agent.Names` 当角色名调 `skill.Check`；之后每次读这个角色的目录用 `skill.Load`。两者的规则合起来是：

| 阶段 | 情况 | 结果 |
| --- | --- | --- |
| `Check` | `SkillsDir` 读不出来（包括不存在） | 启动失败 |
| `Check` | 根目录下的子目录直接含 `SKILL.md` | 启动失败，提示移到 `<SkillsDir>/<role>/<name>` |
| `Check` | 根目录下的子目录不是角色名 | 启动失败，列出全部角色名 |
| `Check` | 角色目录里任何一个技能解析失败 | 启动失败 |
| `Load` | 角色目录不存在 | 返回空，不报错 |
| `Load` | 技能目录没有 `SKILL.md`，或名字以 `.` 开头 | 跳过这个目录 |
| `Load` | `SKILL.md` 是链接或不是普通文件，或不是合法 UTF-8 | 报错 |
| `Load` | 第一行不是 `---`、frontmatter 没闭合、YAML 解析失败 | 报错，`skills: parse "<文件>": ...` |
| `Load` | `name`、`description`、正文不合规，资源超过 200 个，目录名与 `name` 不同 | 报错；这几类的错误文本里没有文件路径 |
| 两者 | 根目录下的普通文件 | 跳过 |

目录按名字排序返回。启动之后没有缓存的目录：每次模型调用前，`run` 通过宿主给的 `run.Skills` 读这个轮次角色的技能，读失败时报 `run: the skills of <role>: ...`，轮次失败；四个技能工具每次调用都按调用者的角色（`tool.Caller.Role`）重新读目录。`activate_skill` 的 `name` 不是枚举，名字不对时返回 `skills: you have no skill named "<name>"; use a name from AVAILABLE SKILLS`。运行中放进一个坏技能，那个角色的轮次会在下一次模型调用时失败，直到修好。

桌面端怎样安装、暂存和校验技能，见[内置技能](/zh/desktop/sidecar#技能)和[配置的实现](/zh/desktop/config)。

## 技能如何进入上下文

1. 系统提示词在角色规则之后放 `# AVAILABLE SKILLS` 一节，每行 `- <name>: <description>`（描述里的空白折叠成一个空格）。预算是输入预算的 4%（`skillPercent`，不少于 256 token），放不下时从末尾删，并留一行 `[N more skills are not listed: the catalog is over its budget]`。每个角色都列自己目录里的技能；精简主 agent 的技能工具可能被延迟，要先 `load_tools`，见[工具系统](/zh/engine/tools)。节的顺序与预算分配见[上下文管理](/zh/engine/context)。
2. 四个工具都属于 `skills` 提供者，都标了只读、`OpenWorldHint` 为假，规则没命中时任何审批策略都不问用户。浏览器子 agent 的权限层也保留了 `skills` 提供者。

| 工具 | 参数 | 返回 |
| --- | --- | --- |
| `get_skills_root_dir` | 无 | `skills_root_dir`：这个角色的目录 `<SkillsDir>/<role>` |
| `list_skills` | 无 | `skills[]`：`name`、`description`、`source_file`（相对 `SkillsDir`，形如 `<role>/<name>/SKILL.md`）、`version`、`resources[]`、`byte_size` |
| `activate_skill` | `name` | `activated`、`description`、`version`、`digest`（`SKILL.md` 的 sha256）、`resources[]`，并带一个 `agent_skill` artifact |
| `read_skill_resource` | `skill`、`path`、`offset_runes`、`limit_runes` | 一页文本：`skill`、`path`、`text`、`offset_runes`、`limit_runes`、`total_runes`、`next_offset_runes`、`eof` |

3. `activate_skill` 的 artifact 是正文全文，`Kind` 是 `prompt.SkillArtifact` 即 `agent_skill`。`run` 记录结果前先过 `Window.CheckArtifacts`：正文不超过 20000 rune，渲染后的 token 数不超过 artifact 预算（输入预算的 15%，`artifactPercent`）。超了这次调用记为失败（`apply tool context: ...`），模型收不到技能内容。
4. 通过检查的 artifact 随工具结果写进 `ToolResult.Artifacts`，进程重启后仍在。拼上下文时按"同种同名只留最后一次"汇总，从最近的往前塞进 artifact 预算：放得下的拼在那次调用输出之后（`--- agent_skill: <name> ---` 加正文），后来又激活过的旧位置写一行"后面重新载入过"，放不下的写一行提示让模型重新激活；压缩时放得下的在摘要后面写成 `--- active agent_skill: <name> ---`。规则见[上下文管理](/zh/engine/context)。

`read_skill_resource` 只接受这个技能列出的路径。文件经 `os.OpenRoot` 在技能目录里打开：路径离开技能目录的拒绝，资源本身是链接的拒绝。`limit_runes` 默认 12000（`defaultResourceRunes`），schema 限定在 1 到 30000（`MaxResourceRunes`）；`offset_runes` 超过全文时返回空页。

## MCP 服务器的配置

MCP 服务器是用户的设置，按 `(user_id, name)` 一行存在 `mcp_servers` 表里（`account.MCPServer`）：

| 字段 | 含义 |
| --- | --- |
| `Name` | 提供者 ID，也是工具名前缀 |
| `Command`、`Args`、`Env` | stdio 服务器 |
| `URL`、`Headers` | Streamable HTTP 服务器 |

只有这两种传输。客户端用协议增删，参数与返回见[模型、工具与 MCP](/zh/integrate/protocol/models-tools)：

| 方法 | 做什么 |
| --- | --- |
| `mcpServer/list` | 每台服务器的配置，加上它的状态（见[失败、状态与清理](#失败、状态与清理)） |
| `mcpServer/set` | 新增或整体替换一台，返回写入的配置 |
| `mcpServer/delete` | 按 `name` 删掉一台 |
| `mcpServer/changed`（通知） | `name` 和 `server`；删掉时 `server` 为 `null` |

`app.SetMCPServer` 在写入的事务里用 `MCPServer.Check(providers)` 校验，不合格的报 `invalid MCP server`，网关映射成 `-32602`。传进去的是这个用户当前工具集里已有的提供者名（`box.Tools` 的 `Provider`），他自己的 MCP 服务器除外，所以同名再写一次就是替换：

| 规则 | 要求 |
| --- | --- |
| 名字 | 匹配 `^[A-Za-z0-9][A-Za-z0-9_-]{0,31}$`，不含 `__`（`policy.ProviderSeparator`） |
| 不撞提供者 | 不能和已有的提供者同名，例如 `workspace`、`skills`、`cron` |
| 传输 | `Command` 和 `URL` 恰好给一个 |
| 字段搭配 | `Args`、`Env` 只配 `Command`；`Headers` 只配 `URL` |

`Env` 和 `Headers` 的值按写入的原样保存和发送，不展开 `${NAME}` 一类的变量。存进库里的配置在启动服务器时不再校验一次。

写入（`PutMCPServer`）和删除都发一条 feed 事件。`mcp.Users` 订阅了 feed，听到某个用户的服务器变了，就把这个用户已连接的整组关掉；下一次有人要这个用户的工具时按库里的新配置全部重连。

## MCP 客户端

`tool/mcp` 用 `modelcontextprotocol/go-sdk` 的客户端。`host.New` 用 `mcp.NewUsers` 创建一个 `Users`，它同时负责内置工具和 MCP 工具。一个用户的工具集由四部分组成：

- 宿主给的 `Tools`：部署决定，桌面端与服务端注入 `tool/builtin/workspace`，提供者是 `workspace`（`run_command`、`claude`、`edit_file`、`write_file`、`read_file`、`glob`、`grep`）；
- 内置提供者：`plan`、`user_input`、`deferred_tools`、`subagents`、`context`、`memory`、`web`，配了技能目录时的 `skills`，开了中枢时的 `hub`，以及总是装的 `cron`；
- `kit.New` 自己追加的 `tool_registry`：`list_tool_providers` 和 `list_tools_for_provider`；
- 这个用户的每台 MCP 服务器。

客户端身份是 `host.Config.Name` 和构建版本（读不到时是 `unknown`）。连接在 `Users.Tools(ctx, user)` 或 `Users.Statuses(user)` 第一次用到这个用户时做，按用户缓存，同一用户的并发请求共用一次连接：

1. 从库里读这个用户的服务器，取他第一个执行环境的 `Box`（`environment.Boxes.In(ctx, user, "")`）；打不开时报 `mcp: the first environment of the user: ...`，这个用户的工具集建不起来。
2. 每台服务器一个 goroutine，各自限时 30 秒（`connectTimeout`），覆盖启动、initialize 握手和 `tools/list`。
3. 连上的服务器作为提供者，和内置提供者一起交给 `kit.New` 组成工具集；连不上的服务器名字记进工具集的 `Unavailable`。

| 步骤 | 实现 |
| --- | --- |
| stdio | 工作目录是 `Box.Roots()[0]`，即第一个环境的文件夹；`box.Executable` 解析命令，`box.Start` 起进程，Box 能给全权（`CanEscalate`）时以全权启动，stdin/stdout 接 `mcp.IOTransport`，stderr 收进一个 2048 字节（`tailBytes`）的环形缓冲 |
| HTTP | `mcp.StreamableClientTransport`，底层是 `box.Transport()` 外面包一层：`Headers` 只加在主机名和 `URL` 相同的请求上，关会话的 `DELETE` 限时 5 秒（`closeTimeout`） |
| 消息上限 | 一条消息最多 32 MiB（`maxMessageBytes`）：stdio 上每行必须是一条完整的 JSON 消息，HTTP 的 SSE 每个事件、其他响应体都不能超过；超过时会话以错误结束 |
| 握手 | `client.Connect`；`InitializeResult().ServerInfo.Name` 记作服务器标题，写进提供者的描述 |

工具名是 `<server>__<tool>`，分隔符 `policy.ProviderSeparator` 即 `__`。下面几种工具只跳过它自己，名字记进 `skippedTools`：

- 拼好的全名不匹配 `^[A-Za-z0-9_-]{1,64}$`（长度把前缀算在内）；
- 同一台服务器给出重复的名字；
- `inputSchema` 不是 JSON 对象，或编译不过（`kit.ResolveSchema`）。

因为带前缀，两台服务器之间不会撞名。撞的是提供者名：`kit.New` 遇到两个同名提供者报 `provider "<name>" twice`。保存时已经拦住了 MCP 服务器和内置提供者同名，但如果宿主后来加了一个同名的提供者（或者打开了技能，而用户早有一台叫 `skills` 的服务器），这个用户的工具集就装配失败，他的轮次以 `run: the tools of the user: ...` 失败。

`Session.Invoke` 在调用里带上 `ollupi/caller` 的 `_meta`：`threadId`，有工作区时加 `workspaceId`，子 agent 调用时加 `subagent: true`；调用者没有会话时不发。单次调用限时 5 分钟（`defaultCallTimeout`），不可配置。结果这样转换：

| 服务器返回 | 结果 |
| --- | --- |
| `isError` | 文本 content 拼起来，同时作输出和错误，条目以失败结束，模型能读到那段文本；没有文本时是 `tool error` |
| 有 `structuredContent` | 原样作输出 |
| 其他 | content 用换行拼接：文本原样；图片、音频写成 `[image: <mime>, <n> bytes, not shown]` 一类的占位；资源链接写名字和 URI；内嵌资源有文本就用文本 |

之后是工具集统一的处理：输出编码成 JSON 超过 1 MiB 截断，错误超过 16 KiB 截断，编码不了 JSON 的输出变成错误。

## 失败、状态与清理

`Users.Statuses(user)` 给这个用户的每台服务器一条状态，`mcpServer/list` 把它和配置放在一起返回。这个调用本身会触发连接：用户的服务器还没启动时，`mcpServer/list` 要等它们连完（每台最多 30 秒）。

| 字段 | 含义 |
| --- | --- |
| `name` | 配置里的名字 |
| `connected` | 没有失败原因时为真 |
| `tools` | 实际提供的工具数 |
| `skippedTools` | 被跳过的工具名 |
| `error` | 失败原因；连上之后掉线时是 `disconnected: ...` |

| 情形 | 结果 |
| --- | --- |
| 命令解析不到、进程起不来 | 这台服务器不可用，`box.Executable` 或 `box.Start` 的错误进 `error` |
| 进程启动后立刻退出 | `Connect` 失败，stderr 末尾最多 2048 字节以 `; stderr: ...` 附在 `error` 后面 |
| initialize 或 `tools/list` 失败，或 30 秒内连不上 | 会话关闭，这台服务器不可用 |
| 单个工具不合格 | 只跳过这个工具，`skippedTools` 里留名字 |

运行中掉线、消息超过 32 MiB 时 `sess.Wait()` 结束，`error` 记 `disconnected: ...`（带 stderr 末尾），`connected` 变假；下一次取这个用户的工具时 `gone()` 为真，整组关掉重连。用户改了或删了任一台服务器也一样。单次调用超时的错误是 `mcp: "<server>" did not answer within 5m0s; the call may still have taken effect, so check before repeating it`。

清理跟着连接走：stdio 进程用传给 `host.New` 的 context 启动，活到这个 context 结束；`Host.Close` 调 `Users.Close`，关掉每个用户的会话；连接失败时进程在 `connect` 返回前就关掉。

## 权限与沙箱

MCP 工具进工具集时字段是这样填的：

| 字段 | 值 |
| --- | --- |
| `Name` | `<server>__<tool>` |
| `Description` | 服务器给的描述 |
| `Schema` | 服务器给的 `inputSchema`，由工具集编译、校验参数 |
| `Annotations` | 只搬服务器的 `title`、`destructiveHint`、`idempotentHint`；`readOnlyHint` 和 `openWorldHint` 不搬 |
| `Content` | 没有，所以规则不能带说明符 |
| `Prepare` | 没有，不走审批前冻结 |
| `Serial` | 未设；但只有标了只读的调用才和别的调用并行，所以 MCP 调用总是单独执行 |

于是每个 MCP 工具在判定时都是"不是只读、开放世界"。审批判定只读这两项（`policy.Checker.requiresApproval`），`destructiveHint`、`idempotentHint` 只随描述发给模型：

| 审批策略 | `never` | `on-request` | `untrusted` |
| --- | --- | --- | --- |
| 任何 MCP 调用（规则没命中时） | 运行 | 问 | 问 |

规则只能写到工具名：`<server>__<tool>` 可以，带说明符的写法在保存时被拒（`takes no specifier`）。连不上的服务器的名字在工具集的 `Unavailable` 里：已有的规则保留、这次不匹配任何调用；新写一条引用它的规则会被拒，要等服务器连上再加。部署层的规则可以写到这个用户没有的 MCP 工具。完整规则和匹配算法见[审批与权限](/zh/engine/permissions)。

沙箱边界分三处：stdio 服务器在用户第一个环境的 `Box` 里启动，它是用户自己的程序，Box 能给全权时以全权运行，和在 ollupi 之外运行一样（本机的 `Sandbox` 不加 Seatbelt，环境变量只去掉 `HideEnv` 的前缀；远程 `Box` 给不了全权，交给它的 `Machine` 照常运行）；HTTP 请求用 `box.Transport()`（本机的 `Sandbox` 返回带系统代理的 `http.Transport`，远程 `Box` 用自己的 transport，请求从分片进程发出，只能到公网地址）；`activate_skill` 把技能的文件写进会话所在环境的文件夹 `.ollupi/skills/<名字>`（同一版本只写一次），技能的命令在那里能用到它们。沙箱的两种形态见[沙箱](/zh/engine/sandbox)。

## 工作区层

工作区有两处影响工具：一段指令和一组提供者开关，都存在 `workspaces` 表里（迁移 `0006_workspace_instructions_providers.sql` 加了 `instructions`、`providers` 两列），随工作区改名、移动、归档一起走。

**指令。** `app.UpdateWorkspaceInstructions` 经 `account.Instructions` 校验后写入：去掉首尾空白，最多 20 000 rune（`maxInstructionsRunes`），超了报 `account.ErrInvalidName`。非空时它进入这个工作区里每个会话、每个角色的系统提示词，位置在角色规则之后、`# AVAILABLE SKILLS` 之前，标题是 `# WORKSPACE INSTRUCTIONS`（`prompt/system.go` 的 `instructionsSection`）。

**提供者开关。** `account.Providers` 有 `Enabled` 和 `Disabled` 两个名字列表。`app.UpdateWorkspaceProviders` 要求每个名字在这个用户的工具集里有对应的提供者，否则报 `policy.ErrInvalidSettings`（`no tools come from a provider named ...`）。`account.Layers` 在部署层、用户层、工作区权限层之后加一层 `the providers of this workspace`：`Without` 是部署 `host.Config.OptIn` 里没被工作区 `enabled` 的提供者加上工作区的 `disabled`，所以 `disabled` 压过 `enabled`；这一层对所有角色生效，按提供者整块去掉工具，`skills`、`cron`、`hub`、`workspace` 本身都能这样关掉。

关掉 `skills` 只去掉四个技能工具：`run` 读技能目录时不看工具层，系统提示词里照样列 `# AVAILABLE SKILLS`，这时模型看得到目录却调不动 `activate_skill`。工作区的其余行为（移动、归档、中枢、待办）见[工作区](/zh/engine/workspace)，层怎么叠加见[审批与权限](/zh/engine/permissions)。

## 边界与已知问题

- **运行中放进的坏技能让这个角色的轮次失败。** 启动检查只在 `host.New` 时做；之后每次模型调用都重新读目录，读失败时那一轮失败，直到技能修好。
- **一个坏技能让整个宿主起不来，部分错误不带文件名。** 启动检查没有跳过坏技能继续跑的模式；`name`、`description`、正文的校验错误只说哪条规则不成立，frontmatter 的格式错误才带文件名。
- **frontmatter 只读三个键。** 其他键被忽略，包括 `allowed-tools`。
- **技能正文太大时激活失败。** 超过 20000 rune 或 artifact 预算时这次调用失败，模型拿不到正文；激活过的技能太多时，较早的那些在上下文里换成一行提示。
- **起初连不上的服务器不会自动重试。** 只有已经连上的服务器掉线才触发整组重连（`gone()` 只看连上过的会话）；起初就失败的那台要等同一用户的另一台掉线、用户改一次配置，或进程重启。
- **一台掉线，整组重连。** 这个用户的其他服务器进程也会被关掉重启，改任一台的配置也一样；按代码推断，正在跑的轮次手里还拿着关掉之前的工具集，这时调用那些服务器的工具会失败。
- **stdio 服务器要一个有根目录的 `Box`。** 工作目录取 `Box.Roots()[0]`。`sandbox.New`、`sandbox.Here` 和 `sandbox.Local` 建的 Box 至少有一个根目录；`sandbox.Remote` 不检查传进来的 `roots`，提供者给它空列表时 stdio 服务器会越界。

## 代码位置

| 路径 | 职责 |
| --- | --- |
| `skill/skill.go` | `Load`、`Check`、`Find`：按角色扫描目录、解析 frontmatter、各项校验、资源分页 |
| `tool/builtin/skills/tools.go` | `skills` 提供者和四个工具，每次调用按角色读目录 |
| `host/host.go` | `Config.SkillsDir`、启动检查、`skillsOf`、装配内置提供者和 `mcp.Users` |
| `prompt/system.go` | `# AVAILABLE SKILLS`、`# WORKSPACE INSTRUCTIONS` 两节 |
| `prompt/window.go`、`prompt/artifacts.go`、`prompt/observation.go`、`prompt/compaction.go` | 技能目录与 artifact 的预算、正文在上下文和压缩后的去留 |
| `run/model.go`、`run/tools.go` | 每次模型调用读技能；记录结果前检查 artifact |
| `agent/agent.go` | 角色名（`Names`）和各角色的提供者白名单；浏览器子 agent 的权限层保留 `skills` |
| `account/account.go` | `Workspace`、`Providers`、`Layers`、`MCPServer`、`MCPStatus`、`MCPServer.Check` |
| `app/owned.go` | `UpdateWorkspaceInstructions`、`UpdateWorkspaceProviders`、`MCPServers`、`SetMCPServer`、`DeleteMCPServer` |
| `tool/mcp/servers.go` | `Users`：按用户连接、缓存、feed 触发的关闭、状态、掉线重连 |
| `tool/mcp/session.go` | 传输、initialize、工具命名与跳过、调用、超时、结果转换、stderr 尾巴 |
| `tool/mcp/limits.go` | 单条消息 32 MiB 的上限 |
| `tool/kit/kit.go` | 工具集装配、重名检查、输出和错误的上限、`tool_registry` |
| `policy/checker.go`、`policy/validate.go` | 审批判定读哪两项；连不上的服务器与规则的关系 |
| `store/sqlite/migrations/0001_init.sql`、`0006_workspace_instructions_providers.sql` | `mcp_servers` 表；`workspaces.instructions` 与 `providers` 两列 |
| `gateway/owned.go`、`gateway/protocol.go`、`gateway/server.go` | `mcpServer/*`、`workspace/updateProviders`、`mcpServer/changed` |
