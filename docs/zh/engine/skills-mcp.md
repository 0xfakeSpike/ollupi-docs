# 技能与 MCP

技能和 MCP 都是把引擎之外的内容接进模型的方式：技能（skill）是一份写给模型看的说明，MCP（Model Context Protocol）服务器是一个别人实现好的工具服务。两者都通过 `tools.Provider` 进入注册表，注册表、一次调用的生命周期和延迟加载见[工具系统](/zh/engine/tools)；这里写各自的格式、装配方式和边界。

## 为什么这样设计

- **系统提示词只列名字和一句描述，正文按需激活。** 技能目录每行一个 `- name: description`，其余由 `activate_skill` 返回，同样的预算能列更多技能。正文作为工具结果的一部分存进条目，所以重启和压缩之后仍然有效。
- **坏技能让启动失败，不跳过。** 任何一个技能解析失败，整个 agent 起不来，错误写明是哪个文件，不会悄悄少一个技能，见[设计决策 18](/zh/reference/decisions#_18-出错即暴露)。所以改技能的一方要在写入之前先校验，桌面端就是这样做的。
- **MCP 工具名总带服务器前缀。** 工具一律注册成 `<server>__<tool>`，服务器以后新增的工具不会和别的工具撞名，也不会让启动失败，工具名也不随其他配置变化。
- **连不上的服务器跳过，并报告原因。** 配错或连不上的服务器不阻止启动，状态里写明原因。引用这些服务器工具的权限规则照样保留、本次不匹配任何调用，不会让 agent 起不来。
- **每个用户的服务器在自己的沙箱里按需启动。** 用户第一次需要时才在他的 `Box`（沙箱的运行环境）里启动，掉线后再启动。各用户的服务器和连接互不共享。

代价：每个用户一组服务器进程；一台服务器掉线时整组关掉重连；MCP 工具没有 `PermissionContent`，权限规则只能写到工具名，也没有审批前冻结；技能改动要重启才生效。

::: info 演进
- 技能目录早期每个技能是一段缩进 JSON，带源文件、版本、大小、资源和允许的工具；`7728a41` 改成每行一个 `- name: description`。
- 工具名一律带服务器前缀、连不上的服务器跳过并报告原因，来自 `0fb4289`。
- 以前引用连不上的服务器工具的权限规则会让 agent 起不来，或让相关会话每一轮都失败；`39e17df` 改成保留规则、本次不匹配。
- 每个用户的服务器在自己的 Box 里按需启动，来自 `f1ff694`。
:::

## 技能是什么

一个技能是一个目录，目录里必须有 `SKILL.md`，目录名必须等于 frontmatter 里的 `name`。

```text
<skills_dir>/
  my-skill/
    SKILL.md
    references/detail.md
    scripts/render.py
```

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

其余文件是 resources，`read_skill_resource` 只能读列出来的这些：

| 规则 | 值 |
| --- | --- |
| 允许的扩展名 | `.md`、`.txt`、`.json`、`.yaml`、`.yml`、`.toml`、`.go`、`.py`、`.js`、`.ts`、`.sh` |
| 单个文件上限 | 1 MiB |
| 列出的文件数上限 | 200，超过报错 |
| 不进入、不列出 | 点开头的子目录、指向目录或文件的链接、`SKILL.md` 本身、扩展名不在表里的文件 |

## 发现与加载

`skills.New(dir)` 调 `scanRoot`，读一层子目录，为每个目录解析 `SKILL.md`，结果按名字排序放进 `Catalog`；之后不再扫描。

| 情况 | 行为 |
| --- | --- |
| 目录名以 `.` 开头 | 跳过 |
| 没有 `SKILL.md` | 跳过这个目录，不报错 |
| `SKILL.md` 是链接或不是普通文件 | 报错 |
| `SKILL.md` 不是合法 UTF-8 | 报错 |
| 第一行不是 `---`，或 frontmatter 没有闭合 | 报错 |
| `name` 不合规则、`description` 为空、正文为空 | 报错 |
| 目录名与 frontmatter 的 `name` 不同 | 报错 |

任何一条报错都让 `skills.New` 失败，`Agent.Start` 跟着失败，整个过程起不来，错误形如 `agent: skills: skills: parse ".../SKILL.md": ...`（第二个 `skills:` 来自 `parseSkill`）。没有"跳过坏技能继续跑"这种模式。

`Agent.buildTools` 只在 `Config.SkillsDir` 非空时创建目录并加上 `skills` 提供者，所以空字符串表示技能关掉。`ToolList` 把当前目录里的名字做成枚举：`activate_skill` 的 `name`、`read_skill_resource` 的 `skill` 都只接受这些值（`agent/skills/provider.go`）。新增或改名技能要重启后端才生效。

桌面端的技能目录默认是 `<home>/skills`，首次启动装入随应用发布的技能；界面上的改动先暂存在以点开头的目录里，用后端同一个 `skills.New` 校验通过才换进去并重启后端，所以界面写不进一个会让后端起不来的技能。见[内置技能](/zh/desktop/sidecar#内置技能)、[界面怎么改配置](/zh/desktop/config#界面怎么改配置)和[不一致检测](/zh/desktop/config#不一致检测)。

## 技能如何进入上下文

技能的正文靠一次工具调用带进来。

1. 系统提示词的 `# AVAILABLE SKILLS` 一节，每行 `- <name>: <description>`。预算 `SkillBudget` 是输入预算的 4%（最少 256 token），放不下时从末尾删，并留一行 `[N more skills are not listed: the catalog is over its budget]`。精简模式（输入预算小于 16384 token）不列这一节，技能的四个工具也在那时被延迟。节的顺序与预算分配见[上下文管理](/zh/engine/context)。
2. 四个工具都是 `skills` 提供者的，都标了只读、`OpenWorldHint` 为假，规则没命中时任何审批策略都不问用户。

| 工具 | 参数 | 返回 |
| --- | --- | --- |
| `get_skills_root_dir` | 无 | `skills_root_dir` |
| `list_skills` | 无 | `skills[]`：`name`、`description`、`source_file`、`version`、`resources[]`、`byte_size` |
| `activate_skill` | `name` | `activated`、`description`、`version`、`digest`、`resources[]`，并带一个 `agent_skill` artifact |
| `read_skill_resource` | `skill`、`path`、`offset_runes`、`limit_runes` | 一页文本：`text`、`offset_runes`、`limit_runes`、`total_runes`、`next_offset_runes`、`eof` |

3. `activate_skill` 的 artifact 是正文全文，`Kind` 是 `agent_skill`。工具结果进上下文时，artifact 拼在输出之后，形如 `--- agent_skill: <name> ---` 加正文；它写进条目的 `Result.Artifacts`，所以进程重启后仍在。正文不算工具输出，不参与裁剪，也不进 `read_tool_output`。
4. artifact 要过 `CheckArtifacts`：正文不超过 20000 rune，整体不超过 `artifactBudget`（输入预算的 15%）。超了这次调用失败（`apply tool context: ...`），模型收不到技能内容。
5. 压缩历史时，放得下的 artifact 以 `--- active agent_skill: <name> ---` 重新写进摘要；放不下的换成一行提示，让模型需要时重新激活。

`read_skill_resource` 只接受 `list_skills` 里列出的路径：绝对路径、`.`、`..`、任何一段是链接都拒绝；`limit_runes` 默认 12000，上限 30000，超出报错。

## MCP 客户端

`tools/mcp` 用 `modelcontextprotocol/go-sdk` 的客户端。一个服务器由 `Server` 描述：

| 字段 | 含义 |
| --- | --- |
| `Name` | 提供者 ID，也是工具名前缀 |
| `Command`、`Args`、`Env` | stdio 服务器。命令经 `Box.Start` 启动，工作目录是 `Box.Roots()[0]` |
| `URL`、`Headers` | Streamable HTTP 服务器，`Headers` 随每个请求发出 |
| `Timeout` | 单次工具调用的超时，小于等于 0 时取 5 分钟 |

只有这两种传输。`checkTransport` 要求 `Command` 和 `URL` 恰好给一个；`Args`、`Env` 只能配 `Command`，`Headers` 只能配 `URL`，否则这台服务器被跳过。

连接在 `Users.For(user)` 里做，按用户缓存，同一用户并发调用共用一次连接。每个服务器一个 goroutine，`connectTimeout` 是 30 秒，覆盖 initialize 握手和 `tools/list`：

| 步骤 | 实现 |
| --- | --- |
| 名字校验 | `^[A-Za-z0-9][A-Za-z0-9_-]{0,31}$`，不含 `__`，同一份配置内不重名 |
| stdio | `box.Executable` 解析命令，`box.Start` 起进程，`mcp.IOTransport` 接 stdin/stdout，stderr 收进一个 2048 字节的环形缓冲 |
| HTTP | `box.Transport()` 包一层写 header 的 `RoundTripper`，交给 `mcp.StreamableClientTransport` |
| 握手 | `client.Connect`，`InitializeResult().ServerInfo.Name` 记作服务器标题；客户端身份默认 `ollupi` / `0.1`，嵌入方可以在 `NewUsers` 的 `Client` 里改（桌面端传 `ollupi-desktop` 和 sidecar 的构建版本） |

工具名是 `<server>__<tool>`，分隔符 `tools.ProviderSeparator` 即 `__`。拼好的全名要匹配 `^[A-Za-z0-9_-]{1,64}$`（长度把前缀算在内），否则这个工具不提供，工具名记进 `skippedTools`。因为带前缀，两台服务器之间不会撞名；`checkName` 还要求同一份配置里的名字唯一，第二台同名的直接跳过。撞的是提供者名：服务器叫 `workspace`、`skills` 这类内置名字时，装配这个用户的注册表会报 `duplicate provider`；注册表里两个提供者给出同一个工具名则报 `duplicate tool`。两种情况都让 `registryFor` 失败，错误交回那一轮。嵌入方可以在自己的配置校验里先拦一层，桌面端就不让服务器叫 `browser`，见[校验分三层](/zh/desktop/config#校验分三层)。

`Session.Invoke` 在调用里带上 `ollupi/caller` 的 `_meta`：`threadId`、`workspaceId`、`subagent`；没有 `threadId` 时不发，`Root` 不转发。

## 失败、状态与清理

`Servers.Statuses()` 给每个配置项一条状态，`mcpServer/list` 原样返回：

| 字段 | 含义 |
| --- | --- |
| `name` | 配置里的名字 |
| `connected` | 没有失败原因时为真 |
| `tools` | 实际提供的工具数 |
| `skippedTools` | 名字不合规、没提供的工具 |
| `error` | 失败原因；连接成功后掉线时是 `disconnected: ...` |

| 情形 | 结果 |
| --- | --- |
| 名字、传输组合不合规 | 跳过这台服务器，`error` 写明哪条规则 |
| 命令解析不到、进程起不来 | 跳过；`box.Executable` 的错误进 `error` |
| 进程启动后立刻退出 | `Connect` 失败，stderr 末尾最多 2048 字节附在 `error` 后面 |
| initialize 或 `tools/list` 失败 | 会话关闭，这台服务器跳过 |
| 30 秒内连不上 | 跳过 |
| 工具名不合规 | 只跳过这个工具，`skippedTools` 里留名字 |
| 运行中掉线 | `sess.Wait()` 结束，`down` 记 `disconnected: ...`，`connected` 变假；下次取工具时 `gone()` 为真，整组关掉重连，得到新的 `*tools.Set`，注册表跟着重建 |
| 单次调用超时 | 调用失败，错误是 `mcp: "<server>" did not answer within 5m0s; the call may still have taken effect, so check before repeating it` |
| 工具返回 `isError` | 文本同时进结果和错误，条目变 `failed`，模型能读到那段文本 |
| 结果不是 JSON | 不解析：`structuredContent` 原样当结果，否则把文本 content 用换行拼起来，非文本用 `fmt.Sprint` |
| 结果不能序列化成 JSON | 注册表的 `guard` 报 `output that cannot be encoded as JSON`，超过 1 MiB 则截断 |
| 工具没给 `inputSchema` | 注册表报 `missing schema`，这个用户的工具装配失败 |

清理跟着连接走：stdio 进程活到创建 `Users` 的那个 context 结束，`Users.Close` 关掉每个用户的会话；连接失败时进程在 `connect` 返回前就关掉。桌面端在 `host.New` 里连接全部服务器，耗在启动握手内，见 [sidecar 的握手](/zh/desktop/sidecar#握手)。

界面上的表现：能力页每张卡标 `stdio` 或 `HTTP`；连上显示工具数，连不上显示红色徽章和 `error` 原文，`skippedTools` 单独一行；后端不认识配置里的服务器时显示未启动。配置的形状与校验见[配置文件](/zh/app/config)。

## 权限与沙箱

MCP 工具进 `tools.Spec` 时字段是这样填的：

| 字段 | 值 |
| --- | --- |
| `Name` | `<server>__<tool>` |
| `Description` | 服务器给的描述 |
| `InputSchema` | 服务器给的 schema，原样交给注册表规范化 |
| `Annotations` | 服务器的 `title`、`readOnlyHint`、`destructiveHint`、`idempotentHint`、`openWorldHint` 逐项搬过来 |
| `PermissionContent` | 没有 |
| `Local` | 没有，所以没有 `Prepared`，不走审批前冻结 |
| `Serial` | 未设，只读的 MCP 调用可以和别的只读调用并行 |

没有 `PermissionContent` 意味着规则只能写到工具名：`<server>__<tool>` 可以，带说明符的写法在保存时被拒（`takes no specifier`）。审批判定只读 `ReadOnlyHint` 和 `OpenWorldHint`，`destructiveHint`、`idempotentHint` 只随描述发给模型：

| 调用 | `never` | `on-request` | `untrusted` |
| --- | --- | --- | --- |
| 标了只读、`openWorldHint` 为假 | 运行 | 运行 | 运行 |
| 标了只读、没给 `openWorldHint` | 运行 | 运行 | 问 |
| 没标只读 | 运行 | 问 | 问 |

服务器不给 `annotations` 时 `ReadOnlyHint` 为假、`OpenWorldHint` 为空（`tools.OpenWorld` 当作真），所以落在最后一行。完整规则和匹配算法见[审批与权限](/zh/engine/permissions)。

沙箱边界分两处：

- **进程在哪跑**：stdio 服务器在嵌入方为这个用户给出的 `Box` 里启动（`NewUsers` 的 `boxFor`），一直运行到创建 `Users` 的 context 结束。这个 `Box` 不必是工作区沙箱：桌面端给 MCP 服务器的是一个不受限的运行环境，见 [MCP 的运行环境](/zh/desktop/sidecar#mcp-的运行环境)。
- **HTTP 走哪条路**：请求用 `box.Transport()`。本机的 `Sandbox` 返回 `http.DefaultTransport`；远程 `Box` 用自己的 transport，连内网地址会被拒。
- **技能目录**：`SkillsDir` 作为只读路径交给沙箱，所以 `run_command` 改不了技能文件；技能自己的读取直接读目录，不经 `Box`。

工具调用本身不受 `Workspace` 的沙箱限制：`Invoke` 只是把参数交给服务器，引擎管不了服务器拿它做了什么。

## 边界与已知问题

- **技能改动要重启才生效。** 目录只在启动时扫描一次，`name` 的枚举也是那时定的，见[发现与加载](#发现与加载)。
- **一个坏技能让整个 agent 起不来。** 没有跳过坏技能继续跑的模式。
- **frontmatter 只读三个键。** 其他键被忽略，包括 `allowed-tools`。
- **技能正文太大时激活失败。** 超过 20000 rune 或输入预算的 15% 时这次调用失败，模型拿不到正文；精简模式下技能不列出，四个工具也被延迟。
- **起初连不上的服务器不会自动重试。** 只有已经连上的服务器掉线才触发整组重连（`gone()` 只看已连上的会话）；起初就失败的那台要等到同一用户的另一台掉线，或进程重启。
- **一台掉线，整组重连。** 这个用户的其他服务器进程也会被关掉重启。
- **MCP 工具只能按名字管。** 没有 `PermissionContent`，规则不能带说明符，也不走审批前冻结；只读标注由服务器自己声明，引擎不核对，见[权限与沙箱](#权限与沙箱)。
- **调用超时不代表没生效。** 5 分钟没回应时调用失败，但服务器那边可能已经做了，错误信息提醒模型先检查再重试。
- **引擎管不到服务器做了什么。** stdio 服务器在哪个 `Box` 里跑、HTTP 请求走哪条路由嵌入方决定，工具调用本身不经过工作区沙箱。

::: info 演进
`allowed-tools` 以前读过但从没执行，`701ac2a` 删掉了对它的解析。
:::

## 代码位置

| 仓库 | 路径 | 职责 |
| --- | --- | --- |
| ollupi | `agent/skills/catalog.go` | 扫描目录、解析 frontmatter、各项校验、资源分页 |
| ollupi | `agent/skills/provider.go` | `skills` 提供者、四个工具、`name` 与 `skill` 的枚举 |
| ollupi | `agent/systemprompt/systemprompt.go` | `# AVAILABLE SKILLS` 一节和预算裁剪 |
| ollupi | `agent/contextmanager/manager.go`、`compaction.go` | artifact 预算检查、压缩后保留或丢弃技能 |
| ollupi | `agent/agent.go` | `buildTools` 装配技能，`registryFor` 按 `tools.Set` 缓存注册表 |
| ollupi | `tools/mcp/servers.go` | `Server`、`ServerStatus`、`Users`、连接、状态、掉线重连 |
| ollupi | `tools/mcp/session.go` | 传输、initialize、工具命名、调用、超时、stderr 尾巴 |
| ollupi | `tools/spec.go`、`tools/registry.go` | `Spec`、`Annotations`、`tools.Set`、`Unavailable`、输出上限 |
| ollupi | `agent/permission/policy.go`、`permission.go` | 审批判定读哪两个 hint；连不上的服务器与规则的关系 |
| ollupi | `gateway/server.go` | `mcpServer/list` |
| ollupi-desktop | `sidecar/internal/host/host.go` | 桌面端怎么装配：`mcpBox`、`mcpServers`、客户端身份 |
| ollupi-desktop | `apps/desktop/src/renderer/src/views/capabilities/` | 能力页的技能列表与 MCP 状态 |

桌面端的技能目录、暂存校验和配置形状的代码位置见 [sidecar](/zh/desktop/sidecar#代码位置) 和[配置的实现](/zh/desktop/config#代码位置)。
