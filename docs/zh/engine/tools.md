# 工具系统

工具是模型能调用的动作。`tool` 包是运行时端口：`tool.Set` 为一个用户描述一组工具——给权限判定提供内容、冻结要执行的内容、执行；`tool/kit` 是写工具的方式，提供者列出并执行自己的工具，注册表把它们合成 `tool.Set`。内置工具在 `tool/builtin/*`，MCP 服务器的工具在 `tool/mcp`。

一次调用是一个条目（item），由日志里的调用、审批、开始、结果几条记录折叠而成，重启后每个阶段都能读回来，见[执行模型](/zh/engine/execution)与[持久化](/zh/engine/persistence)。

## 为什么这样设计

- **工具只给模型用。** 协议有 `tool/list`，没有直接调用工具的方法；界面要做的事走专门方法（如 `cron/list`），工具层也没有跳过权限的直调路径。见[设计决策 9](/zh/reference/decisions#_9-工具只给模型用)。
- **审批绑定执行内容。** 两段式工具先 `Prepare` 冻结要执行的内容再判定，批准的就是这一份。见[设计决策 16](/zh/reference/decisions#_16-审批绑定执行内容)。
- **失败交还模型。** 参数无效、被规则拒绝、执行出错都变成工具结果；panic 由注册表接住，只让这次调用失败。
- **只读并行，其余按顺序。** 最多 8 个，只看 `ReadOnlyHint`，不看参数；MCP 服务器自己声明的只读不采信。
- **长调用可以离开本轮。** 标了后台可选的工具带 `background` 参数，为真的调用写成任务，结果以报告回到会话。

代价：界面操作都要有专门方法；工具要自己给 `Content` 和 `Prepare`，没有的只能按名字管、也不冻结；只读标注写错的内置工具会被错误地并行。

::: info 演进
早期协议有 `tool/call`，界面可以直接调模型的工具，`daf6ee9` 删掉了它。
:::

## 工具接口

写工具时实现 `kit.Provider`（`Name`、`Tools`、`Invoke`），每个工具用 `kit.Spec` 声明；`tool.Set` 的方法是 `Specs`、`Unavailable`、`Content`、`Prepare`、`Invoke`。下表是需要解释的字段（另有 `Name`、`Description`）。

| 字段 | 作用 |
| --- | --- |
| `InputSchema` | JSON Schema，参数校验和发给模型都用它；`kit.InputSchema[T]()` 从 Go 结构体生成，`Constrainer` 可补长度、范围、枚举 |
| `Annotations` | MCP 同款五个 hint；审批策略读 `ReadOnlyHint` 与 `OpenWorldHint`（未设时当作真），并行只读 `ReadOnlyHint` |
| `Content` | 把参数变成规则能匹配的内容（`policy.Content` 的 `Text`、`Match`、`Parts`、`Opaque`、`Folded`）；没有它的工具，规则只能按工具名写 |
| `Prepare` | 判定前冻结要执行的内容，得到 `tool.Plan`（`Data`、`Sandboxed`、`Escalated`），记进 `ToolCall.Prepared`、在审批卡片里显示（协议 `preparedExecution`）；批准后 `Invoke` 拿到的就是这份，见[工作区工具](/zh/engine/workspace#审批前冻结的内容) |
| `Serial` | 只读也不并行，桌面端的浏览器工具用它 |
| `Background` | `BackgroundNever`（零值）、`BackgroundOptional`、`BackgroundAlways`，见[后台调用](#后台调用) |

`tool.Call` 带参数、冻结内容与 `tool.Caller`（`User`、`Thread`、`Workspace`、`Environment`、`Root`、`Subagent`、`Role`、`Item`、`Deferred`）。`kit.Result` 的 `Output` 编码成 JSON 写进日志，`Artifacts` 放内容进上下文，`Ask` 要问用户，`Launch` 启动子 agent。

## 后台调用

`BackgroundOptional` 的工具在 schema 里多一个布尔参数 `background`（`kit.New` 用 `withBackground` 加上）；`tool.Spec.InBackground` 在 `BackgroundAlways` 或它为真时返回真。内置工具里 `run_command`（`tool/builtin/workspace/execution.go`）和 `claude`（`claude.go`）是 `BackgroundOptional`，没有工具用 `BackgroundAlways`。

为真的调用不在本轮执行：`run.runTools` 直接走 `run.launchTask`，一个事务里建 `store.Task` 并追加 `ToolStarted` → `TaskLaunched` → `ToolResult{Output: Started}`，本轮只拿到任务号与一句说明。任务由 `schedule.Tasks` 在另一个池子里跑，不占本轮的工具并发；结束时 `run.ReportTask` 追加 `TaskReported`，报告以 `role=user` 的消息回到会话。池子、时限与中断时的报告见[执行模型](/zh/engine/execution#后台调用)。

## 注册表

`kit.New(ctx, unavailable, providers...)` 把一组提供者合成 `kit.Registry`（实现 `tool.Set`），并加上自省提供者 `tool_registry`。提供者 ID 与工具名不能为空也不能重复；`InputSchema` 在装配时解析一次；工具按提供者 ID、再按工具名排序。`Content`、`Prepare`、`Invoke` 先检查工具与参数，失败分别是 `ErrUnknownTool`、`ErrInvalidArguments`；panic 被接住，只让这次调用失败（`the tool crashed: ...`）。

运行时按用户取工具：`mcp.Users.Tools` 交给 `run` 和 `app`，每个用户一个注册表，里面是共享内置提供者加该用户的 MCP 服务器；连不上的列在 `Unavailable` 里，引用它们的规则不算错；用户改了服务器后，`mcp.Users` 从 store 的 feed 得知并重建。一次运行只在第一步取一次工具。

`host.New` 把上表的内置提供者加进注册表：`hub` 只在 `host.Config.Hub` 为真时加，`skills` 只在配了 `SkillsDir` 时加；嵌入方自己的工具和 `workspace` 走 `host.Config.Tools`。

## 一次调用的生命周期

模型的一次回答可以带多个调用，`run` 在写下回答的同一个事务里逐个判定（`run.decide`），这一轮再按步骤执行：工具不可用或参数不是 JSON 对象时直接 `failed`；否则 `Content` → `Prepare` 冻结，再由 `Decide` 给出 `Deny`（`failed`）、`Ask`（先 `pending` 等用户，拒绝则 `declined` 并停掉本轮工具）或 `Run`（`pending`），进入执行时 `background: true` 的走任务，其余 `ToolStarted` 后 `Invoke`。

结果分四种：`completed`、`failed`、`Ask`（保持 `inProgress`，这一轮等回答）、`Launch`（启动子 agent，调用即完成）。只列了名字、还没载入的工具被调用时失败，提示先调 `load_tools`；不在这一轮列表里的，提示用列表里的确切名字。

### 并行

每一步取还在 `pending` 的调用：第一个只读、不是 `Serial`、也不在后台时，连着往后取同样的调用，最多 8 个（`maxParallelCalls`）一起执行，开始前一次写下 `ToolStarted`、结束后一次写下结果；否则只执行一个。`request_user_input`、子 agent 工具、`update_plan`、`load_tools`、`read_tool_output` 都标了只读，一次回答里的多个子 agent 调用会一起启动。

## 内置工具

| 提供者 | 工具 | 只读 | 说明 |
| --- | --- | --- | --- |
| `workspace` | `run_command`、`claude`、`edit_file`、`write_file` | 否 | 两段式；前两个后台可选 |
| `workspace` | `read_file`、`glob`、`grep` | 是 | 见[读文件和搜索](#读文件和搜索) |
| `web` | `web_fetch` | 否 | 见[网页](#网页) |
| `plan` | `update_plan` | 是 | `explanation`（≤500）、`plan[]`（1 到 12 步） |
| `user_input` | `request_user_input` | 是 | 1 到 4 个问题，见[提问的请求与类型](/zh/integrate/protocol/approvals#userinputrequestparams) |
| `subagents` | 8 个 `-sub-agent` 工具 | 是 | `description`（1 到 80）、`prompt`（1 到 20000） |
| `context` | `read_tool_output` | 是 | `output_id`、`offset`、`length`（默认 8000，上限 20000） |
| `deferred_tools` | `load_tools` | 是 | `names[]`，见[延迟加载](#延迟加载) |
| `memory` | `memory_search` | 是 | 见[记忆](/zh/engine/memory) |
| `hub` | `list_workspaces`、`start_conversation`、`send_message`、`list_conversations`、`read_conversation`、`add_todo`、`update_todo`、`list_todos` | `list_*`、`read_conversation` | 只在 `host.Config.Hub` 为真时装配，见[中枢](/zh/engine/hub) |
| `skills` | `get_skills_root_dir`、`list_skills`、`activate_skill`、`read_skill_resource` | 是 | 见[技能与 MCP](/zh/engine/skills-mcp) |
| `cron` | `create_scheduled_job`、`pause_scheduled_job`、`delete_scheduled_job`、`list_scheduled_jobs` | `list_scheduled_jobs` | 见[定时任务](/zh/engine/cron) |
| `tool_registry` | `list_tool_providers`、`list_tools_for_provider` | 是 | 自省 |

子 agent 工具只在这类子 agent 自己要用的工具（除 `context` 以外）还对当前角色可见时出现（`agent.Launchable`），否则删掉同名工具；子 agent 都看不到 `subagents`、`cron`、`hub`。

### 读文件和搜索

`read_file`、`glob`、`grep` 只读、不冻结，按 `ReadOnlyHint` 并行；参数、上限、`.gitignore` 处理和路径规则见[工作区工具](/zh/engine/workspace#读文件和搜索)。

`glob` 只走模式能到达的目录（`tool/builtin/workspace/patterns.go` 的 `reaches`）：花括号里出现 `/` 时不做这个判断；否则按 `/` 切段，逐段比对进入的目录名，某一段含 `**` 就放行，最后一段是文件名、不参与比对。所以 `cmd/**/*.go` 不会进 `docs/`，`*.go` 则直接跳过所有子目录。

`edit_file` 失败时告诉模型差在哪里：`old_text` 找不到时给最接近的位置与那一行的原文（`looseMatch`，至少要 8 个字符对得上），出现多次时给最多 5 个行号并提示 `replace_all`；一批里第几个编辑失败就停在第几个，后缀是 `; none of the N edits were applied`。编辑后内容没变时返回 `workspace: the edits leave … unchanged`。成功的返回带 `Path`、`Created`、`Added`、`Removed`，`edit_file` 另带 `Diff`；批准后执行时重算比对，文件在此期间变了就什么都不写。

### 网页

`web_fetch`（`tool/builtin/web`）的参数只有 `url`。同域跳转最多跟随 10 次，跨域不跟随、返回 `redirectedTo`，新域名按新调用过权限；超时 30 秒，响应体上限 10 MiB，文本上限 200000 字符；出站限制见[本机请求走系统代理](/zh/engine/sandbox#本机请求走系统代理)。它没有标只读：URL 能把数据带给网站，所以每个新站点都要批准，规则按主机名匹配。

## 输出交给模型

工具的输出原样进入提示词：`prompt.OutputText` 把字符串去掉首尾空白后照原样给出，其他 JSON 缩进排版后给出，不加引号与围栏。

写进日志的是完整结果，只在超出输入预算时才在提示词里裁剪（`prompt/observation.go`）：单条最多 6000 token，已结束轮次的最多 512，最少 256，超出时保留开头与结尾，中间换成一句写清楚怎么读回的提示：

```text
[... characters 8000-52000 of this output omitted; call read_tool_output with output_id "<条目 ID>" and offset 8000 to read them ...]
```

日志里的内容不变，同一个结果下次可以显示得更长；`read_tool_output` 按字符读完整结果，只接受当前会话的工具调用和子 agent 报告。切点怎么避开脱敏范围见[上下文管理](/zh/engine/context#工具输出裁剪)。工具层也截一次：命令的 stdout、stderr 各认 沙箱的 `MaxOutputBytes`（默认 1 MiB），保留头尾，中间换成 `[… N bytes omitted …]`。

## 延迟加载

工具定义占输入预算，工具太多时把一部分只列名字，用到再载入。每一步 `run` 先按权限算出看得见的工具，再由 `Window.Offer`（`prompt/tools.go`）分成发送的和只列名字的（deferred）：`load_tools` 不可见、或全部定义不超过输入预算的 10% 时全部发送；否则发送内置工具（名字里没有 `__`）、延迟 MCP 工具（名字是 `<服务器>__<工具>`）；内置工具还放不下时，只发送 `load_tools` 和 `Role.Core` 里的核心工具——只有精简主 agent 有核心工具（`read_file`、`run_command`），见[精简模式](/zh/engine/context#精简模式)。

被延迟的工具按提供者分组列在系统提示词的 `# DEFERRED TOOLS` 一节。`load_tools`（`tool/builtin/loader`）只接受这一轮延迟列表里的名字（`Caller.Deferred`）；它不改状态：`Offer` 从会话里已完成的调用读出已载入的名字，按顺序追加到发送列表末尾。工具列表因此只变长、前缀不变，服务商缓存继续有效（见[设计决策 14](/zh/reference/decisions#_14-记忆快照与稳定前缀)）。

## 边界与已知问题

- **只读标注由工具自己声明。** 引擎不核对；MCP 的标注不采信，所以 MCP 工具从不并行、`on-request` 下也要问，见[技能与 MCP](/zh/engine/skills-mcp#权限与沙箱)。
- **没有 `Content` 的工具只能按名字管。** 规则写不了说明符，也没有审批前冻结，MCP 工具都属于这一类。
- **注册表截断会切坏 JSON。** 超过 1 MiB 时按字节截前 1 MiB，结果变成一段不完整的 JSON 文本；错误信息超过 16 KiB 时同样截断。
- **一个回答里有调用要审批，整批都等。** 判定在写下回答时一起做，不需要审批的调用也要等全部有了决定才执行。
- **后台调用的结果不在本轮里。** 本轮只看到 `Started{task, note}`，输出在之后回来的报告里；载入过的延迟工具也不能卸下。

## 代码位置

| 位置 | 职责 |
| --- | --- |
| ollupi `tool/tool.go` | `Set`、`Spec`、`Background`、`Annotations`、`Caller`、`Call`、`Plan`、`Result`、`Launch` |
| ollupi `tool/kit/kit.go`、`tool/kit/schema.go`、`tool/mcp/` | `Provider`、`kit.Spec`、注册表、`background` 参数注入、输出上限、panic 保护、`tool_registry`；Schema 生成与校验；每个用户的 MCP 服务器 |
| ollupi `tool/builtin/workspace/`、`tool/builtin/web/` | 命令、文件、读取工具、`claude`、`web_fetch` 与 HTML 转 Markdown；`patterns.go` 的 `reaches` |
| ollupi `tool/builtin/plan/`、`ask/`、`subagent/`、`loader/`、`outputs/`、`hub/`、`cronjobs/` | 计划、提问、子 agent、`load_tools`、`read_tool_output`、中枢、定时任务工具 |
| ollupi `run/tools.go` | 判定调用、并行执行、`launchTask` 与 `ReportTask`、启动子 agent |
| ollupi `prompt/tools.go`、`prompt/render.go`、`prompt/observation.go` | `Offer` 与延迟加载、`OutputText`、输出裁剪 |
| ollupi `host/host.go` | 内置提供者的装配、`host.Config.Hub` |
