# 技能与 MCP

技能和 MCP 都是把引擎之外的内容接进模型的方式：技能（skill）是一份写给模型看的说明，按角色装在技能目录里；MCP（Model Context Protocol）服务器是一个别人实现好的工具服务，每个用户在自己的设置里登记。两者都以工具提供者（`kit.Provider`）的身份进入这个用户的工具集，工具集、一次调用的生命周期和延迟加载见[工具系统](/zh/engine/tools)；这里写各自的格式、装配方式和边界。

## 为什么这样设计

- **系统提示词只列名字和一句描述，正文按需激活。** 技能目录每行一个 `- name: description`，正文由 `activate_skill` 返回，同样的预算能列更多技能。正文作为工具结果的一部分写进对话日志，所以重启和压缩之后仍然有效。
- **技能按角色安装。** 每个角色（agent 的种类，见[执行模型](/zh/engine/execution)）只看到自己目录里的技能，子 agent 不会被主 agent 的流程说明干扰。同一个技能要给几个角色用，就在几个目录里各放一份。
- **技能在用到时才读。** 每次模型调用和每次技能工具调用都重新读这个角色的目录，装上、改掉一个技能，下一次模型调用就生效，不用重启。
- **坏技能在启动时暴露。** 启动时把整个技能目录检查一遍，任何一个技能解析失败，`host.New` 就失败，不会悄悄少一个技能，见[设计决策 18](/zh/reference/decisions#_18-出错即暴露)。
- **MCP 服务器是用户自己的设置，存在库里。** 每个用户通过协议增删自己的服务器，改动下一次用到时生效，不用重启，也不经过宿主（host）的配置。
- **MCP 工具名总带服务器前缀。** 工具一律注册成 `<server>__<tool>`，服务器以后新增的工具不会和别的工具撞名。
- **连不上的服务器跳过，并报告原因。** 连不上的服务器不让这个用户的轮次失败，状态里写明原因；引用它的工具的权限规则照样保留，只是暂时不匹配任何调用。
- **每个用户的服务器在自己的沙箱里按需启动。** 用户第一次需要工具时，才在他的 `Box`（沙箱的运行环境）里启动他的服务器，各用户的进程和连接互不共享。
- **服务器自己声明的只读不算数。** MCP 工具一律当作会改东西、会访问外部世界，审批策略不因服务器的标注放行。

代价：每个用户一组服务器进程；一台服务器掉线、或用户改了任一台的配置，这个用户的整组服务器都关掉重连；MCP 工具在 `on-request` 下每次都问，规则只能写到工具名；每次模型调用都要读一遍角色的技能目录。

::: info 演进
- 技能目录早期每个技能是一段缩进 JSON，带源文件、版本、大小、资源和允许的工具；`7728a41` 改成每行一个 `- name: description`。
- 工具名一律带服务器前缀、连不上的服务器跳过并报告原因，来自 `0fb4289`；以前引用连不上的服务器工具的权限规则会让 agent 起不来，`39e17df` 改成保留规则、本次不匹配。
- 技能原来是所有角色共用的一个目录，`45a8799` 改成按角色安装；原来启动时读一次、改动要重启，`ac2824a` 改成用到时读。
- MCP 服务器原来是宿主在启动时读一次的配置，`1ae27b2` 把它们改成每个用户存在库里、经协议增删；服务器的只读和封闭世界标注从 `fdefa84` 起不再采信。
:::

## 技能是什么

一个技能是一个目录，目录里必须有 `SKILL.md`，目录名必须等于 frontmatter 里的 `name`。技能目录按角色分一层：

```text
<SkillsDir>/
  full-main-agent/
    my-skill/
      SKILL.md
      references/detail.md
      scripts/render.py
  compact-main-agent/
    my-skill/
      SKILL.md
  general-sub-agent/
  browser-sub-agent/
```

四个角色目录的名字就是 `agent.Names`：`full-main-agent`、`compact-main-agent`、`general-sub-agent`、`browser-sub-agent`。主 agent 按模型的输入大小在完整和精简两个角色之间选，所以给主 agent 的技能要在前两个目录里各放一份，会话换到另一种大小的模型时才不会丢。

`SKILL.md` 是 YAML frontmatter 加正文。frontmatter 只读三个键：

```markdown
---
name: my-skill
description: 什么时候用这个技能，一句话。
metadata:
  version: "1.0"
---

正文：激活后模型读到的完整说明。
```

| 键 | 必填 | 规则 |
| --- | --- | --- |
| `name` | 是 | 匹配 `^[a-z0-9]+(?:-[a-z0-9]+)*$`，不超过 64 个 rune |
| `description` | 是 | 不超过 1024 个 rune；列在系统提示词的 `# AVAILABLE SKILLS` 里 |
| `metadata.version` | 否 | 转成字符串，随 `activate_skill` 返回 |

正文是激活后进上下文的部分，上限 20000 rune、500 行。

其余文件是资源（resources），`read_skill_resource` 只能读列出来的这些：

| 规则 | 值 |
| --- | --- |
| 允许的扩展名 | `.md`、`.txt`、`.json`、`.yaml`、`.yml`、`.toml`、`.go`、`.py`、`.js`、`.ts`、`.sh` |
| 单个文件上限 | 1 MiB，读的时候检查 |
| 列出的文件数上限 | 200，超过时这个技能解析失败 |
| 不进入、不列出 | 点开头的子目录、链接（指向目录或文件都算）、`SKILL.md` 本身、扩展名不在表里的文件 |

## 发现与加载

技能目录由 `host.Config.SkillsDir` 给出，空字符串表示不用技能：这时不检查目录，也不装 `skills` 提供者。

**启动时检查。** `host.New` 调 `skill.Check(SkillsDir, 角色名)`，把整个目录过一遍：

| 情况 | 结果 |
| --- | --- |
| `SkillsDir` 读不出来（包括不存在） | 启动失败 |
| 根目录下的子目录直接含 `SKILL.md` | 启动失败，提示移到 `<SkillsDir>/<role>/<name>` |
| 根目录下的子目录不是角色名 | 启动失败，列出全部角色名 |
| 角色目录里任何一个技能解析失败 | 启动失败 |
| 点开头的目录、根目录下的普通文件 | 跳过 |

**解析一个角色的目录。** `skill.Load(root, role)` 读一层子目录，为每个目录解析 `SKILL.md`，按目录名排序返回；角色目录不存在时返回空，不报错。

| 情况 | 行为 |
| --- | --- |
| 目录名以 `.` 开头，或不是目录 | 跳过 |
| 没有 `SKILL.md` | 跳过这个目录，不报错 |
| `SKILL.md` 是链接或不是普通文件 | 报错 |
| `SKILL.md` 不是合法 UTF-8 | 报错 |
| 第一行不是 `---`，或 frontmatter 没有闭合，或 YAML 解析失败 | 报错，`skills: parse "<文件>": ...` |
| `name` 不合规则、`description` 为空或过长、正文为空或过长 | 报错，错误文本里没有文件路径 |
| 资源超过 200 个 | 报错 |
| 目录名与 frontmatter 的 `name` 不同 | 报错 |

**用到时读。** 启动之后没有缓存的目录：

- 每次模型调用前，`run` 通过 `host` 给它的 `run.Skills` 读这个轮次角色的技能，列进系统提示词。读失败时这一步报错 `run: the skills of <role>: ...`，轮次以失败结束。
- 四个技能工具每次调用都按调用者的角色（`tool.Caller.Role`）重新读目录，只在自己角色的技能里找。

所以运行中装上、删掉、改掉一个技能，下一次模型调用就生效；运行中放进一个坏技能，那个角色的轮次会在下一次模型调用时失败，直到修好，启动检查管不到这时候。`activate_skill` 的 `name` 不是枚举，名字不对时返回 `skills: you have no skill named "<name>"; use a name from AVAILABLE SKILLS`。

桌面端怎样安装、暂存和校验技能，见[内置技能](/zh/desktop/sidecar#内置技能)和[配置的实现](/zh/desktop/config)。

## 技能如何进入上下文

技能的正文靠一次工具调用带进来。

1. 系统提示词在角色规则之后放 `# AVAILABLE SKILLS` 一节，每行 `- <name>: <description>`（描述里的空白折叠成一个空格）。预算是输入预算的 4%（不少于 256 token），放不下时从末尾删，并留一行 `[N more skills are not listed: the catalog is over its budget]`。四个角色都列自己的技能；精简主 agent 的技能工具可能被延迟，要先 `load_tools`，见[工具系统](/zh/engine/tools)。节的顺序与预算分配见[上下文管理](/zh/engine/context)。
2. 四个工具都属于 `skills` 提供者，都标了只读、`OpenWorldHint` 为假，规则没命中时任何审批策略都不问用户。浏览器子 agent 的权限层也保留了 `skills` 提供者。

| 工具 | 参数 | 返回 |
| --- | --- | --- |
| `get_skills_root_dir` | 无 | `skills_root_dir`：这个角色的目录 `<SkillsDir>/<role>` |
| `list_skills` | 无 | `skills[]`：`name`、`description`、`source_file`（相对 `SkillsDir`，形如 `<role>/<name>/SKILL.md`）、`version`、`resources[]`、`byte_size` |
| `activate_skill` | `name` | `activated`、`description`、`version`、`digest`（`SKILL.md` 的 sha256）、`resources[]`，并带一个 `agent_skill` artifact |
| `read_skill_resource` | `skill`、`path`、`offset_runes`、`limit_runes` | 一页文本：`skill`、`path`、`text`、`offset_runes`、`limit_runes`、`total_runes`、`next_offset_runes`、`eof` |

3. `activate_skill` 的 artifact 是正文全文，`Kind` 是 `agent_skill`。`run` 记录结果前先过 `Window.CheckArtifacts`：正文不超过 20000 rune，渲染后的 token 数不超过 artifact 预算（输入预算的 15%，不少于 256）。超了这次调用记为失败（`apply tool context: ...`），模型收不到技能内容。
4. 通过检查的 artifact 随工具结果写进日志的 `ToolResult.Artifacts`，进程重启后仍在。拼上下文时，所有已完成调用里的 artifact 按"同种同名只留最后一次"汇总，从最近的往前塞进 artifact 预算：放得下的拼在那次调用的输出之后，形如 `--- agent_skill: <name> ---` 加正文；后来又激活过的，旧位置写一行"后面重新载入过"；放不下的写一行提示，让模型需要时重新激活。
5. 压缩历史时，压缩点之前放得下的 artifact 以 `--- active agent_skill: <name> ---` 写在摘要后面；放不下的换成一行提示，让模型需要时重新激活。

`read_skill_resource` 只接受这个技能列出的路径。文件经 `os.OpenRoot` 在技能目录里打开：路径离开技能目录的拒绝，资源本身是链接的拒绝。`limit_runes` 默认 12000，schema 限定在 1 到 30000；`offset_runes` 超过全文时返回空页。

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

`app.SetMCPServer` 在写入的事务里用 `MCPServer.Check` 校验，不合格的报 `invalid MCP server`，网关映射成 `-32602`：

| 规则 | 要求 |
| --- | --- |
| 名字 | 匹配 `^[A-Za-z0-9][A-Za-z0-9_-]{0,31}$`，不含 `__` |
| 不撞提供者 | 不能和这个用户工具集里已有的提供者同名（`workspace`、`skills`、`cron` 等），他自己的 MCP 服务器除外，所以同名再写一次就是替换 |
| 传输 | `Command` 和 `URL` 恰好给一个 |
| 字段搭配 | `Args`、`Env` 只配 `Command`；`Headers` 只配 `URL` |

`Env` 和 `Headers` 的值按写入的原样保存和发送，不展开 `${NAME}` 一类的变量。存进库里的配置在启动服务器时不再校验一次。

写入（`PutMCPServer`）和删除都发一条 feed 事件。`mcp.Users` 订阅了 feed，听到某个用户的服务器变了，就把这个用户已连接的整组关掉；下一次有人要这个用户的工具时按库里的新配置全部重连。

## MCP 客户端

`tool/mcp` 用 `modelcontextprotocol/go-sdk` 的客户端。`host.New` 用 `mcp.NewUsers` 创建一个 `Users`，它同时负责内置工具和 MCP 工具：一个用户的工具集是宿主给的 `Tools`、内置提供者（plan、ask、loader、subagent、outputs、memory、skills、cronjobs），再加上他的每台 MCP 服务器。客户端身份是 `host.Config.Name` 和构建版本（读不到时是 `unknown`）。

连接在 `Users.Tools(ctx, user)` 或 `Users.Statuses(user)` 第一次用到这个用户时做，按用户缓存，同一用户的并发请求共用一次连接。步骤：

1. 从库里读这个用户的服务器，用 `host.Config.Boxes(user)` 取他的 `Box`。
2. 每台服务器一个 goroutine，各自限时 30 秒（`connectTimeout`），覆盖启动、initialize 握手和 `tools/list`。
3. 连上的服务器作为提供者，和内置提供者一起交给 `kit.New` 组成工具集；连不上的服务器名字记进工具集的 `Unavailable`。

| 步骤 | 实现 |
| --- | --- |
| stdio | 工作目录是 `Box.Roots()[0]`；`box.Executable` 解析命令，`box.Start` 起进程，stdin/stdout 接 `mcp.IOTransport`，stderr 收进一个 2048 字节的环形缓冲 |
| HTTP | `mcp.StreamableClientTransport`，底层是 `box.Transport()` 外面包一层：`Headers` 只加在主机名和 `URL` 相同的请求上，关会话的 `DELETE` 限时 5 秒 |
| 消息上限 | 一条消息最多 32 MiB：stdio 上每行必须是一条完整的 JSON 消息，HTTP 的 SSE 每个事件、其他响应体都不能超过；超过时会话以错误结束 |
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
| initialize 或 `tools/list` 失败 | 会话关闭，这台服务器不可用 |
| 30 秒内连不上 | 不可用 |
| 单个工具不合格 | 只跳过这个工具，`skippedTools` 里留名字 |
| 运行中掉线、消息超过 32 MiB | `sess.Wait()` 结束，`error` 记 `disconnected: ...`（带 stderr 末尾），`connected` 变假；下一次取这个用户的工具时 `gone()` 为真，整组关掉重连 |
| 用户改了或删了任一台服务器 | 整组关掉，下一次取工具时按新配置重连 |
| 单次调用超时 | 调用失败：`mcp: "<server>" did not answer within 5m0s; the call may still have taken effect, so check before repeating it` |

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

沙箱边界分三处：

- **进程在哪跑**：stdio 服务器在 `host.Config.Boxes(user)` 给出的这个用户的 `Box` 里启动，按这个 `Box` 的规则运行。本机的 `Sandbox` 按它的沙箱配置起进程；远程 `Box` 交给它的 `Machine`。
- **HTTP 走哪条路**：请求用 `box.Transport()`。本机的 `Sandbox` 返回 `http.DefaultTransport`；远程 `Box` 用自己的 transport，请求从分片进程发出，只能到公网地址。
- **技能目录**：宿主把同一个目录作为 `workspace.AgentFiles.SkillsDir` 交给工作区工具时，它在沙箱里是只读路径，`run_command` 改不了技能文件；技能自己的读取直接读目录，不经 `Box`。

工具调用本身不受工作区沙箱的限制：`Invoke` 只是把参数交给服务器，引擎管不了服务器拿它做了什么。

## 边界与已知问题

- **运行中放进的坏技能让这个角色的轮次失败。** 启动检查只在 `host.New` 时做；之后每次模型调用都重新读目录，读失败时那一轮失败，直到技能修好。见[发现与加载](#发现与加载)。
- **部分技能错误不带文件名。** `name`、`description`、正文的校验错误只说哪条规则不成立，不说是哪个文件；frontmatter 的格式错误带文件名。
- **一个坏技能让整个宿主起不来。** 启动检查没有跳过坏技能继续跑的模式。
- **frontmatter 只读三个键。** 其他键被忽略，包括 `allowed-tools`。
- **技能正文太大时激活失败。** 超过 20000 rune 或 artifact 预算时这次调用失败，模型拿不到正文。激活过的技能太多时，较早的那些在上下文里换成一行提示。
- **起初连不上的服务器不会自动重试。** 只有已经连上的服务器掉线才触发整组重连（`gone()` 只看连上过的会话）；起初就失败的那台要等同一用户的另一台掉线、用户改一次服务器配置，或进程重启。
- **一台掉线，整组重连。** 这个用户的其他服务器进程也会被关掉重启；改任一台的配置也一样。按代码推断，正在运行的轮次手里还拿着关掉之前的工具集，这时调用那些服务器的工具会失败。
- **列状态会启动服务器。** `mcpServer/list` 和 `mcpServer/set` 都要这个用户的工具集，服务器还没启动时要等它们连完。
- **MCP 工具只能按名字管，并且总要问。** 没有 `Content`，规则不能带说明符，也不走审批前冻结；服务器声明的只读不采信，`on-request` 下每次调用都问，除非有规则放行。见[权限与沙箱](#权限与沙箱)。
- **调用超时不代表没生效。** 5 分钟没回应时调用失败，但服务器那边可能已经做了，错误信息提醒模型先检查再重试。
- **stdio 服务器要一个有根目录的 `Box`。** 工作目录取 `Box.Roots()[0]`。`sandbox.New` 和 `sandbox.Here` 建的 Box 至少有一个根目录；`sandbox.Remote` 不检查传进来的 `roots`，给它空列表时 stdio 服务器会越界。
- **引擎管不到服务器做了什么。** stdio 服务器在哪个 `Box` 里跑、HTTP 请求走哪条路由宿主决定，工具调用本身不经过工作区沙箱。

::: info 演进
`allowed-tools` 以前读过但从没执行，`701ac2a` 删掉了对它的解析。
:::

## 代码位置

| 路径 | 职责 |
| --- | --- |
| `skill/skill.go` | `Load`、`Check`、`Find`：按角色扫描目录、解析 frontmatter、各项校验、资源分页 |
| `tool/builtin/skills/tools.go` | `skills` 提供者和四个工具，每次调用按角色读目录 |
| `host/host.go` | `Config.SkillsDir`、启动检查、`skillsOf`、装配内置提供者和 `mcp.Users` |
| `prompt/system.go` | `# AVAILABLE SKILLS` 一节和预算裁剪 |
| `prompt/artifacts.go`、`prompt/observation.go`、`prompt/compaction.go` | artifact 检查、上下文里保留或替换技能正文、压缩后保留或丢弃 |
| `run/model.go`、`run/tools.go` | 每次模型调用读技能；记录结果前检查 artifact |
| `agent/agent.go` | 四个角色的名字；浏览器子 agent 的权限层保留 `skills` |
| `account/account.go` | `MCPServer`、`MCPStatus`、`MCPServer.Check` |
| `app/owned.go` | `MCPServers`、`SetMCPServer`、`DeleteMCPServer` |
| `tool/mcp/servers.go` | `Users`：按用户连接、缓存、feed 触发的关闭、状态、掉线重连 |
| `tool/mcp/session.go` | 传输、initialize、工具命名与跳过、调用、超时、结果转换、stderr 尾巴 |
| `tool/mcp/limits.go` | 单条消息 32 MiB 的上限 |
| `tool/kit/kit.go` | 工具集装配、重名检查、输出和错误的上限 |
| `policy/checker.go`、`policy/validate.go` | 审批判定读哪两项；连不上的服务器与规则的关系 |
| `store/sqlite/migrations/0001_init.sql` | `mcp_servers` 表 |
| `gateway/owned.go`、`gateway/protocol.go`、`gateway/server.go` | `mcpServer/*` 方法和 `mcpServer/changed` |
