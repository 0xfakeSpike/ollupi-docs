# 工作区

工作区（workspace）是用户某个执行环境（environment）里的一个项目文件夹，会话挂在它上面；`workspace` 提供者的工具在这里跑命令、读写文件，在哪个目录运行、能写到哪里、过哪一层权限都由会话所在的工作区决定。它还带着自己的说明、provider 取舍和类型（`project` 或 `hub`）。见[持久化](/zh/engine/persistence#表和关系)、[网关协议](/zh/integrate/protocol/workspaces)、[沙箱](/zh/engine/sandbox)。

## 为什么这样设计

- **工作区是某个环境里的路径，不是本机路径。** 添加和每次调用都在工作区所在环境的 Box 里校验、解析目录，见[设计决策 1](/zh/reference/decisions#_1-池化-runtime)；代价是每次调用多一次往返。同一个路径在两个环境里是两个文件夹，所以工作区记着自己属于哪个环境，里面的会话也就在那个环境里运行。
- **数据挂在工作区 ID 上。** 会话、记忆、定时任务记的是 ID，`workspace/move` 只改根目录。
- **约定和工具取舍跟着项目走。** 项目约定写进 `Instructions`，哪些 provider 的工具可用也按工作区设，不用改部署配置。
- **只归档，不删除。** 归档后开不了新会话和新的一轮，数据都留着。
- **权限多一层，按项目区分。** 一个项目里批准的"总是允许"不影响别的项目，见[权限分层](/zh/engine/permissions#权限分层)。
- **改动先冻结再审批。** 程序、目录、diff 和哈希在判定之前算好，批准的就是这一份。

工作区只收窄命令目录和写入范围，不限制读取。

## 机制

### 一个工作区是什么

`account.Workspace` 记 ID、`Name`、所在的执行环境 `Environment`、根目录 `Root`、类型 `Kind`、说明 `Instructions`、provider 取舍 `Providers`、权限设置 `Settings` 和归档时间 `Archived`。根目录是那个环境的 Box 里规范化后的绝对路径；同一个用户在同一个环境里不会有两个指向同一文件夹的工作区（库里唯一的是用户、环境、根目录三者），同一个路径在两个环境里是两个工作区。工作区所在的环境之后不变，有工作区的环境不能删除，见[网关协议](/zh/integrate/protocol/workspaces#environment-delete)。

会话的工作区可以为空，界面上叫 general。会话的执行环境在开会话时定下（`app.newThread`）：在工作区里的会话用工作区的环境，`thread/start` 同时给了另一个环境时拒绝（`ErrInvalidEnvironment`）；不在工作区的会话用指定的环境，没指定时用用户的第一个环境。子 agent 继承父会话的工作区、执行环境和权限设置（`run.launch`）。

### 说明、provider 与类型

`workspaces` 表上有三列（迁移 `0006`、`0007`）：`instructions text NOT NULL DEFAULT ''`、`providers text NOT NULL DEFAULT '{}'`（检查 `json_valid`）、`kind text NOT NULL DEFAULT 'project'`。

| 协议方法 | 参数 | 校验 |
| --- | --- | --- |
| `workspace/updateInstructions` | `instructions` | 去首尾空白；超过 20000 字符（`maxInstructionsRunes`）报错 |
| `workspace/updateProviders` | `enabled[]`、`disabled[]` | 名字必须是用户能看到的 provider，否则 `policy.ErrInvalidSettings` |
| `workspace/setKind` | `kind` | `project` 或 `hub`；设成 hub 要部署开着 hub，且没有另一个 hub |

三个方法都在 `app/owned.go`，改完在 `workspace/changed` 里发出新的 `WorkspaceRow`。

**说明进系统提示词。** 非空的 `Instructions` 由 `run.input` 交给 `prompt.System`，在角色规则之后成为 `# WORKSPACE INSTRUCTIONS` 一节，所有角色（含子 agent）都有；它只是提示词，不参与权限判定，见[系统提示词](/zh/engine/context#系统提示词)。

**provider 取舍是一层权限。** `account.Layers` 在用户设置和会话之间插入 `"the providers of this workspace"`，`Without` 是部署的 opt-in 减 `enabled` 加 `disabled`，disabled 胜出；这一层只减不加，按 provider 算，禁掉一个 provider 会连它的全部工具一起去掉，见[权限分层](/zh/engine/permissions#权限分层)。

### hub 工作区

`Kind` 只有 `project`（`account.ProjectWorkspace`）和 `hub`（`account.HubWorkspace`）（`account.WorkspaceKinds`），新建的都是 project，`workspace/add` 不收类型参数。

hub 是部署开关：`host.Config.Hub` 为真时宿主才把 `hub` provider 加进内置工具，关着时设成 hub 报 `ErrNoHub`（`noHub`，`-32021`）。一个用户只能有一个 hub：`SetWorkspaceKind` 在同一事务里读这个用户的全部工作区，发现有另一个 `kind = hub` 就报 `ErrSecondHub`（`secondHub`，`-32020`），不看归档时间。

hub 里的会话以 `hub-main-agent` 运行：`app.queue`（`app/turns.go`）在会话属于 hub 工作区、且自己没有角色时选它。`HubMain` 是主 agent，`Own` 层去掉 `subagents` 和 `browser`，其余 provider（含工作区工具）照用户和工作区设置来，规则要求它把命令和文件限制在这个工作区的文件夹里。工具来自 `hub` provider：`list_workspaces`、`start_conversation`、`send_message`、`list_conversations`、`read_conversation`、`add_todo`、`update_todo`、`list_todos`。它把任务交给项目工作区里的会话（不能交给另一个 hub），再读回进展，见 [hub 工作区](/zh/engine/hub)。

### 添加

`workspace/add` 调到 `app.AddWorkspace(ctx, user, environment, path, name)`，限时 1 分钟：`environment` 为空时是用户的第一个环境；在这个环境的 Box 里用 `Box.Directory(path)` 规范化并确认路径存在、是目录（失败 `ErrInvalidPath`，协议上 `-32602`）；`name` 为空时取目录名，去掉首尾空白后 1 到 120 个字符；`Box.Same` 判断文件夹是否已加过，只和同一个环境里的工作区比，经不同链接到达的同一个文件夹算同一个。

同一个环境里的同一个文件夹已有工作区时复用它：没有就新建一个（`Kind` 是 `project`），未归档的原样返回、`name` 不生效，已归档的先取消归档。

### 一轮里的工作区

`run` 读出会话的工作区（`run.load`），用在：`tool.Caller` 的 `Workspace`、`Root` 和执行环境 `Environment`；系统提示词的 `# WORKSPACE INSTRUCTIONS`，以及能用工作区工具时的 `# ENVIRONMENT`（命令在哪个环境、环境文件夹、沙箱的限制、能否申请全权）和 `# PROJECT`（写明项目路径），见[系统提示词](/zh/engine/context#系统提示词)；权限分层的两层。

### 工具怎样用工作区

每次调用先由 `dirs.go` 算出 Box 和根目录：经 `Options.Boxes(ctx, caller.User, caller.Environment)` 取会话所在环境的 Box，失败时报 `workspace: the environment of the conversation: ...`。`Root` 为空（general）时根目录是 `Box.Roots()`；否则用 `Box.Directory(Root)` 解析，不等于 `Root` 就报错，让用户重新添加，再过 `Box.Check(Root)`。

| | 在工作区里 | 不在工作区 |
| --- | --- | --- |
| 相对路径的基准 | 工作区根目录 | `Box.Roots()` 的第一个 |
| 工具显示的路径 | 根目录之内相对工作区根，之外绝对 | 绝对路径 |
| 命令能在哪运行、文件能写哪里 | 工作区根目录之内，再受沙箱规则限制 | `Box.Roots()` 之内，再受沙箱规则限制 |

`Box.Roots()` 是环境自己的文件夹，本机提供者是 `Dir/<用户>/<环境 ID>`（见[提供者与执行环境](/zh/engine/sandbox#提供者与执行环境)），所以进工作区后命令目录从环境文件夹换成这个项目。Seatbelt 模式下 `Box.Check` 拒绝 `/`、主目录、`~/Library` 及包含它们的目录，`full-access` 和云沙箱里总是通过，见[沙箱](/zh/engine/sandbox#三种模式)。

### 权限

工作区在权限分层里占两层：工作区设置（`workspace/updatePermissions` 改它，先校验单层和合并后的结果）和 provider 取舍。审批时选"总是允许"，规则写进工作区设置；会话不在工作区时写进会话设置；子 agent 的调用写进子会话自己的工作区，不在工作区时写进子会话自己的设置，见[权限分层](/zh/engine/permissions#权限分层)。

### 归档与搬家

归档的工作区不能再开新会话，会话也不能再开始新的一轮（`account.ErrWorkspaceArchived`，协议上 `-32014`），数据还在，取消归档或重新添加同一个文件夹就恢复。`workspace/move` 经工作区所在环境的 `Box.Move` 把文件夹搬到已存在的空文件夹，再改根目录；工作区里还有没结束的轮次时拒绝（`ErrWorkspaceBusy`），因为那些轮次的调用里写着旧路径。

### 别处怎样用工作区

| 功能 | 怎样用 |
| --- | --- |
| 记忆 | 范围 `workspace` 的记忆只进这个工作区的会话，见[记忆](/zh/engine/memory) |
| 搜索 | `search` 带 `workspaceId` 只搜一个工作区，见[搜索](/zh/engine/search) |
| 会话、待办 | `thread/list` 按 `workspaceId` 过滤，待办可挂到工作区，见[网关协议](/zh/integrate/protocol/threads) |
| 用量 | `usage` 表按 `workspace_id` 记账，`groupBy` 可为 `workspace`，见[模型接入](/zh/engine/models#用量) |

## 工作区工具

两段式的 `run_command`、`claude`、`edit_file`、`write_file` 有 `Content` 和 `Prepare`，判定前冻结执行内容；只读的三个只有 `Content`，按路径过权限、可并行。框架见[工具系统](/zh/engine/tools)。

`host.New` 自己用 `workspace.New(Options{Config, Boxes})` 建这个提供者，放进每个用户的内置工具，宿主不再往 `host.Config.Tools` 里加它。`Boxes` 是 `environment.Boxes.In`，按会话的环境给 Box；`Config` 来自 `host.Config.Commands`，只管所有环境共用的三项：

| 配置项 | 默认 | 作用 |
| --- | --- | --- |
| `command_timeout_sec` | 30 | 命令默认超时 |
| `max_command_timeout_sec` | `max(600, command_timeout_sec)` | 模型能要的最长超时，也是 `claude` 的默认值 |
| `command_blacklist` | 空 | 命中就在 `Prepare` 阶段拒绝，见[命令解析](/zh/engine/permissions#命令解析) |

命令在哪里跑、受什么限制（模式、网络、禁读路径、输出上限等）是环境的沙箱的事，由提供者的配置决定，本机见 [`sandbox.Config`](/zh/engine/sandbox#三种模式)。`AGENTS.md`、`CLAUDE.md`、`.mcp.json` 这类 agent 的文件在沙箱的默认保护名里，见[保护名](/zh/engine/sandbox#保护名)。

工具的描述对所有会话是同一份：`run_command` 说它在会话的环境里运行，`work_dir` 默认是项目根目录、不在项目里时是环境文件夹，具体是哪个环境、什么限制、能否申请全权，让模型看系统提示词的 `# ENVIRONMENT`（`workspace.Describe`）。

::: info 演进
以前这个提供者由宿主用 `workspace.New` 建好放进 `Tools`，配置里还有 `workspace_dirs`（不在工作区的命令目录，默认 `<home>/scratch`）和沙箱的各项（`sandbox_mode`、`network`、`allowed_domains`、`deny_read`、`max_output_bytes` 等），命令目录和沙箱规则直接写进 `run_command` 的描述。环境变成提供者的沙箱之后，这些都归了提供者，`scratch` 也不再用：不在工作区的命令在各自环境的文件夹里跑。
:::

### 命令

参数：`program`（argv0）、`args`、`work_dir`（在根目录之内）、`timeout_sec`（1 到 `max_command_timeout_sec`，不填用 `command_timeout_sec`）、`env`、`sandbox_permissions`（`use_default` 或 `require_escalated`，总在 schema 里，环境的沙箱给不了全权时调用被拒）、`justification`（要全权时必填）。

`Content` 给出 `Text`（整行）、`Match`（`程序名 参数...`）和 `Parts`（拆开的子命令）；`sh -c` 这类脚本按简单命令拆开，有展开或复合语句时标 `Opaque`，见[命令解析](/zh/engine/permissions#命令解析)。`Prepare` 解析 `work_dir`、比对 `command_blacklist`、检查全权调用、解析可执行文件的真实路径，再写冻结内容；执行时路径变了报 `approved executable now resolves to a different path`，全权的命令经 `Box.Run` 在沙箱之外运行。结果是 `CommandOutput`，退出码非 0 不算失败，输出超过沙箱的 `MaxOutputBytes`（默认 1 MiB）保留头尾。

### 读文件和搜索

三个只读工具不冻结、不需审批（除非规则要求）；路径过 `Box.CheckRead`，禁读路径在任何模式下都不读。

| 工具 | 参数 | 行为 |
| --- | --- | --- |
| `read_file` | `path`、`offset`（从 1 起）、`limit`（默认和上限 2000） | 带行号，每行最多 2000 字符，文本最多 256 KiB；扫描到 64 MiB 还没数完行时 `totalLinesAtLeast` 为真 |
| `glob` | `pattern`、`path` | 按修改时间新的在前，最多 500 个；命中更多或遍历被截断时 `truncated` 为真 |
| `grep` | `pattern`（RE2）、`path`、`include`、`ignore_case`、`files_only`、`context`（最大 10） | 最多 300 行或 500 个文件，每次出现的那行最多显示 500 字符，跳过大于 8 MiB 的文件 |

模式用 `doublestar` 校验和匹配；两个搜索共用一个遍历器（`walk.go`）：跳过 `.git`，不进目录链接，忽略规则从最近的含 `.git` 上层目录逐层读 `.gitignore` 和 `.git/info/exclude`。一次调用最多走 `maxWalkEntries` = 200,000 个条目，超过就停下并把 `truncated` 置真，已经找到的照常返回，不是报错；读不了的目录计入 `skipped`。

### 改文件与 claude

`edit_file` 收 `path` 和 `edits[]`（`old_text`、`new_text`、`replace_all`），`write_file` 收 `path` 和 `content`。两者都是两段式：路径过 `Box.CheckWrite`，目标已存在时必须是普通文件、不超过 2 MiB、合法 UTF-8，新内容用 `go-udiff` 算 diff（上下文 3 行）作为权限内容的 `Text`；执行时（`runFile`）重算，哈希都对上才经 `Box.WriteFile` 写入。

`edits` 按顺序应用，每一条作用在上一条的结果上；`old_text` 在文件里出现多次又没设 `replace_all` 时整批不写，错误里给出出现的行号，找不到时给出最接近的文本，两者都建议重读文件、逐字复制。`edit_file` 只能改已存在的文件，文件不存在时提示用 `write_file`；结果是 `FileOutput`，带 `created`、`added`、`removed` 和这次的 diff。

`claude` 把自包含的任务交给 Claude Code，在会话的 Box 里、项目目录下运行，参数是 `prompt`、`work_dir`、`timeout_sec`（默认 `max_command_timeout_sec`）。命令行固定带 `--permission-mode acceptEdits`、`--allowedTools "Bash(go test *)"`、`--max-budget-usd 2`；它要网络和主目录里的设置，沙箱不允许，所以 Box 能全权时总以全权准备，结果取 JSON 的 `result`、`is_error` 等字段加 `work_dir`。

### 审批前冻结的内容

冻结内容是 `workspace.Prepared`，编码成 JSON 记进 `ToolCall.Prepared`（协议里是 `preparedExecution`）；批准后不再判定，执行时由 `prepared.go` 的 `validatePrepared` 核对 `SettingsDigest`、`ArgumentsDigest`、`Cwd`、`Program` 和 `Files[].Before`/`After`，任何一项不一致就不执行。

## 边界与已知问题

- **添加时不查能不能作为命令目录。** Seatbelt 模式下把用户主目录加成工作区会成功，之后每次调用都失败。
- **工作区不限制读取。** 读取工具和命令能读禁读名单以外的任何路径，见[沙箱](/zh/engine/sandbox#边界与已知问题)。
- **说明只是提示词。** 写什么都不改变权限判定，模型不遵守时没有东西拦住它；上限 20000 字符。
- **provider 取舍只能减，而且按 provider 算。** `enabled` 只在部署列进 opt-in 时起作用，`disabled` 一定生效；不能只留某个 provider 的一部分工具。
- **归档的 hub 也占着位置。** 找"另一个 `kind = hub`"时不看归档时间，要换 hub 得先把旧的设回 project。
- **工作区换不了环境。** 一个工作区固定属于添加它的环境，想在另一个环境里做同一个项目，要在那个环境里再添加一次，得到另一个工作区；有工作区（包括已归档的）的环境永远删不掉，见[网关协议](/zh/integrate/protocol/workspaces#environment-delete)。

## 代码位置

| 仓库 | 路径 | 职责 |
| --- | --- | --- |
| ollupi | `account/account.go` | `Workspace`、`WorkspaceKinds`、`Providers`、`Instructions`、`Layers`、`ErrWorkspaceArchived` |
| ollupi | `app/owned.go`、`app/threads.go`、`app/turns.go`、`app/settings.go` | 工作区的增删改、说明、provider、类型；会话的环境；`queue` 选角色；"总是允许"的落点 |
| ollupi | `run/run.go`、`run/model.go`、`run/tools.go`、`prompt/system.go` | 组装权限层、`launch` 继承；`# WORKSPACE INSTRUCTIONS`、`# ENVIRONMENT` 与 `# PROJECT` |
| ollupi | `agent/agent.go`、`tool/builtin/hub/hub.go` | `HubMain` 角色、`HubProvider`；`hub` provider 的八个工具 |
| ollupi | `tool/builtin/workspace/`、`gateway/owned.go`、`gateway/protocol.go` | 工具、冻结与核对；`workspace/*` 方法、参数类型、`secondHub` 与 `noHub` |
| ollupi | `store/sqlite/migrations/0006_workspace_instructions_providers.sql`、`0007_workspace_kinds.sql`、`0023_environment_sandboxes.sql` | `instructions`、`providers`、`kind` 三列；`environment_id` 与唯一键 |
