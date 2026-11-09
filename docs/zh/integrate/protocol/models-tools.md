# 模型、工具与 MCP

客户端用三个只读方法知道这个用户能选哪些模型、agent 手上有哪些工具、MCP 服务器连上了没有；会话里的每条工具调用条目（item）按提供方和工具名解读，其中 9 个内置工具的参数和输出在契约里有类型，其余都是通用 JSON。模型怎样调用、工具怎样执行，见[模型接入](/zh/engine/models)、[工具](/zh/engine/tools)和[技能与 MCP](/zh/engine/skills-mcp)。

## 概念与状态

**模型**由宿主（host）在 `agent.Config.Models` 里配好，所有用户看到同一份列表。每个模型绑一条连接（connection），一条连接只给一个模型用（`checkModels` 在启动时检查），所以客户端用 `connection` 指代模型。列表的第一个是默认模型。一轮（turn）开始时选定模型并记进 `TurnRow.model`，这一轮之后不再改变，见[一轮与条目](/zh/integrate/protocol/turns)。

**工具**按用户分：所有用户共用的 `Config.Providers`，加上这个用户自己的 `Config.ToolsFor(user)`，比如他的 MCP 服务器，合成一张注册表。每个工具属于一个提供方（provider），条目和工具列表里都带着它的 id。注册表要求工具名在所有提供方之间唯一，重名时这个用户的注册表建不出来。

**MCP 服务器**是一种提供方，提供方 id 就是服务器名，它的工具名形如 `<服务器名>__<工具名>`。服务器在这个用户第一次需要工具时启动，在用户自己的沙箱里运行；连不上的服务器只是被跳过，它的工具不出现，状态里记下原因。

| 名字 | 规则 | 不满足时 |
|---|---|---|
| MCP 服务器名 | `^[A-Za-z0-9][A-Za-z0-9_-]{0,31}$`，且不含 `__` | 宿主装配 MCP 时报错 |
| MCP 工具的完整名 `<服务器>__<工具>` | `^[A-Za-z0-9_-]{1,64}$`，这是模型 API 接受的工具名 | 这个工具不交给 agent，记进 `ServerStatus.skippedTools` |
| 内置工具名 | 不含 `__` | 生成契约时失败 |

因为内置工具名不含 `__`，而 MCP 工具名总含 `__`，客户端只看工具名就能分出是不是 MCP 工具；提供方另见条目的 `server`。

## 典型流程

客户端连上之后读一次目录，之后按需刷新。下面的消息来自桌面端仓库录制的会话 `packages/protocol/fixtures/session.json`（假模型 `mock-model`，一个能用的 MCP 服务器 `mock`，一个故意配错的 `broken`；录制时的契约摘要等于 v0.12.1 的 `protocolSha256`），省略了 `"jsonrpc":"2.0"`。

```json
→ {"id":2,"method":"model/list","params":{}}
← {"id":2,"result":{"data":[{"name":"mock-model","connection":"mock/mock-model"}],"default":"mock/mock-model"}}
→ {"id":4,"method":"mcpServer/list","params":{}}
← {"id":4,"result":{"data":[
    {"name":"mock","connected":true,"tools":1},
    {"name":"broken","connected":false,"tools":0,"error":"workspace: executable \"ollupi-no-such-mcp-command\" is not on PATH"}]}}
```

`tool/list` 在这个会话里返回 20 个工具，下面只留两个：

```json
{"provider":"mock","name":"mock__echo","description":"Echoes the text back.",
 "annotations":{"readOnlyHint":true},
 "input_schema":{"properties":{"text":{"type":"string"}},"required":["text"],"type":"object"}}
{"provider":"workspace","name":"read_file","description":"Read a text file, its lines numbered. …",
 "annotations":{"title":"Read file","readOnlyHint":true,"destructiveHint":false,"openWorldHint":false},
 "input_schema":{"additionalProperties":false,"properties":{"limit":{…},"offset":{…},"path":{…}},"required":["path"],"type":"object"}}
```

之后这个 MCP 工具被调用，完成时的条目（省略了时间和 ID）：

```json
{"type":"toolCall","status":"completed","tool":"mock__echo","server":"mock",
 "annotations":{"readOnlyHint":true},
 "arguments":"{\"text\":\"hello from the MCP server\"}",
 "result":{"output":"hello from the MCP server"}}
```

`arguments` 是 JSON **文本**，要客户端自己解析；`result.output` 是工具返回的任意 JSON。MCP 工具不在 `builtinTools` 里，所以这两样都没有契约类型，按通用调用显示。

## 方法

三个方法都没有参数，`params` 省略或传 `{}`；都不发通知。

### model/list

| 结果字段 | 类型 | 说明 |
|---|---|---|
| `data` | `Model[]` | 宿主配置的全部模型，按配置顺序 |
| `default` | string | 第一个模型的 `connection` |

不会失败。列表在进程运行期间不变：宿主改了模型要重启引擎，客户端重连后再读一次。

客户端在 `turn/start` 的 `connection` 参数里选模型。引擎按这个顺序决定一轮用哪个模型：

| 顺序 | 用哪条连接 |
|---|---|
| 1 | `turn/start` 传了 `connection`（去掉首尾空白） |
| 2 | 没传时，这个会话上一轮用的连接 |
| 3 | 新会话，用第一个模型的连接 |

选出的连接不在列表里时返回 `-32602`，实测：

```text
agent: invalid message: connection "nope" is unavailable; restore it in Settings or select another model for a new turn
```

这种情况在宿主删掉一个模型之后最常见：老会话的上一轮还记着那条连接，`turn/start` 不带 `connection` 就会失败，客户端要让用户换一个模型。

选出的模型 `images` 不为真时，带图片的消息返回 `-32602` `model <名字> does not accept images; pick a model that does`；这个会话里已经有过图片时，不带图片的消息也会被拒：`this conversation shows the model images, and model <名字> does not accept them; pick a model that does`。因为之前的图片每一轮都会再发给模型。

### tool/list

| 结果字段 | 类型 | 说明 |
|---|---|---|
| `data` | `ToolDescriptor[]` | 这个用户能用的全部工具，包括 MCP 工具和延迟加载的工具，按 `provider`、再按 `name` 排序 |

这个用户第一次调用时，引擎要先连上他的 MCP 服务器才能建出注册表，所以可能等上几秒；`connectTimeout` 是每个服务器 30 秒。之后的调用直接返回。

`ToolsFor(user)` 返回错误时这个方法失败，错误前缀是 `agent: the tools of the user:`，不在错误码表里，客户端收到 `-32000`。

回复可能很大：每个工具都带完整的 `input_schema`。用 `coder/websocket` 的 Go 客户端要先调大读上限，见[传输](/zh/integrate/protocol#传输)。

### mcpServer/list

| 结果字段 | 类型 | 说明 |
|---|---|---|
| `data` | `ServerStatus[]` | 这个用户的 MCP 服务器状态 |

宿主没有配置 `gateway.Options.MCP` 时返回空数组，实测 `{"data":[]}`。取这个用户的服务器失败时返回 `-32000`。

## 内置工具的参数和输出

契约的 `builtinTools` 段给 9 个内置工具的参数（`arguments`，对应条目里 `arguments` 文本解析之后的对象）和输出（`output`，对应条目的 `result.output`）。只收界面要专门显示、用户要参与的工具：计划、子 agent、提问、命令和五个文件工具。`0ae03bb` 把定时任务的四个工具和 `memory_search` 移出了契约，文件工具由 `9ac61ec`、`74322be` 加入。

其余工具调用，包括定时任务、`memory_search`、技能、`read_tool_output`、`web_fetch`、MCP 和宿主自己的工具，不进契约：客户端把它们当通用调用，显示参数和输出的原始 JSON，不要依赖它们的结构。这些输出是写给模型的，引擎可以随时为模型调整。它们的参数类型仍然是发给模型的 `input_schema` 的来源。

| 工具 | 提供方 | 参数 | 输出 |
|---|---|---|---|
| `update_plan` | `plan` | `Plan` | 不进契约，实际是字符串 `Plan updated` |
| `Agent` | `subagents` | `SubagentCall` | 不进契约，实际是子 agent 最后一条回答的文本 |
| `request_user_input` | `user_input` | `UserInputRequest` | `UserInputAnswers`，见[审批与提问](/zh/integrate/protocol/approvals) |
| `run_command` | `workspace` | 不进契约，审批时看 `preparedExecution` | `CommandOutput` |
| `edit_file`、`write_file` | `workspace` | 不进契约，审批时看 `preparedExecution` | `FileOutput` |
| `read_file` | `workspace` | `ReadFile` | `ReadFileOutput` |
| `glob` | `workspace` | `Glob` | `GlobOutput` |
| `grep` | `workspace` | `Grep` | `GrepOutput` |

`builtinTools` 按工具名作键。契约测试（`TestTrafficMatchesContract`）校验每一次真实调用的参数和输出，`run_command` 的参数除外。

录制的会话里，一次计划、一次读文件、一次搜索和一次在沙箱外运行的命令，完成时的 `arguments` 和 `result`：

```json
{"tool":"update_plan","arguments":"{\"explanation\":\"Breaking the work down.\",\"plan\":[{\"step\":\"Read the gateway protocol\",\"status\":\"completed\"},{\"step\":\"Design the package layout\",\"status\":\"in_progress\"},{\"step\":\"Write the renderer\",\"status\":\"pending\"}]}",
 "result":{"output":"Plan updated"}}
{"tool":"read_file","arguments":"{\"path\":\"README.md\"}",
 "result":{"output":{"path":"README.md","text":"1\t# demo\n","startLine":1,"endLine":1,"totalLines":1,"size":7}}}
{"tool":"grep","arguments":"{\"pattern\":\"demo\",\"context\":1}",
 "result":{"output":{"path":".","files":[{"path":"README.md","matches":1,"lines":[{"line":1,"text":"# demo","match":true}]}],"matches":1}}}
{"tool":"run_command","arguments":"{\"program\":\"echo\",\"args\":[\"hello from the command\"],\"sandbox_permissions\":\"require_escalated\",\"justification\":\"Demonstrate a command that needs approval\"}",
 "result":{"output":{"stdout":"hello from the command\n","stderr":"","exit_code":0,"work_dir":"/private/var/folders/…/workspace","sandbox":"escalated: ran on the host without the sandbox"}}}
```

### Plan 和 PlanStep

| 字段 | 类型 | 说明 |
|---|---|---|
| `explanation?` | string | 最多 500 字符 |
| `plan` | `PlanStep[]` | 1 到 12 步 |

| `PlanStep` 字段 | 类型 | 说明 |
|---|---|---|
| `step` | string | 1 到 200 字符 |
| `status` | `PlanStepStatus` | `pending`、`in_progress`、`completed`，注意是下划线 |

最多一步是 `in_progress`，违反时这次调用失败。每次调用给出完整的计划，替换上一次的，不是增量，所以客户端只需显示最近一次成功的 `update_plan`。

### SubagentCall

| 字段 | 类型 | 说明 |
|---|---|---|
| `description` | string | 1 到 80 字符，显示给用户，也是子 agent 会话的标题 |
| `prompt` | string | 1 到 20000 字符，交给子 agent 的完整任务 |

子 agent 会话的 ID 在条目的 `await.threadId` 里，见[一轮与条目](/zh/integrate/protocol/turns)。

### CommandOutput

| 字段 | 类型 | 说明 |
|---|---|---|
| `stdout`、`stderr` | string | 各自最多 `max_output_bytes`（默认 1 MiB），超出时保留头尾，中间换成省略提示 |
| `exit_code` | integer | 退出码 |
| `work_dir` | string | 实际的工作目录 |
| `signal?` | string | 被信号终止时的信号名 |
| `truncated?` | boolean | 输出被截过 |
| `sandbox_denials?` | string[] | 沙箱拦下的操作，桌面端在命令失败时显示，见[拒绝原因报告](/zh/engine/sandbox#拒绝原因报告) |
| `sandbox?` | string | 关于沙箱的说明；在沙箱外运行时是 `escalated: ran on the host without the sandbox` |

### FileOutput

| 字段 | 类型 | 说明 |
|---|---|---|
| `path` | string | 改的文件 |
| `created?` | boolean | 新建的文件 |
| `added`、`removed` | integer | 增删的行数 |

`edit_file`、`write_file` 审批时看的 diff 在条目的 `preparedExecution` 里，见[审批与提问](/zh/integrate/protocol/approvals)。

### ReadFile 和 ReadFileOutput

| `ReadFile` 字段 | 类型 | 说明 |
|---|---|---|
| `path` | string | 相对项目根目录或绝对路径 |
| `offset?` | integer | 从 1 开始的行号，默认 1 |
| `limit?` | integer | 1 到 2000 行，默认 2000 |

| `ReadFileOutput` 字段 | 类型 | 说明 |
|---|---|---|
| `path` | string | 显示用的路径：根目录之内是相对路径 |
| `text?` | string | 带行号的文本，每行形如 `1\t# demo`；单行最多 2000 字符，总共读到约 256 KiB 为止 |
| `startLine?`、`endLine?` | integer | 读到的行范围 |
| `totalLines` | integer | 文件总行数 |
| `size` | integer | 字节数 |
| `binary?` | boolean | 不是文本的文件不给 `text`，只给 `binary: true` 和 `mimeType` |
| `mimeType?` | string | |

### Glob 和 GlobOutput

| `Glob` 字段 | 类型 | 说明 |
|---|---|---|
| `pattern` | string | 相对 `path` 的路径模式：`*` 匹配名字的一段，`**` 任意层文件夹，`{a,b}` 二选一 |
| `path?` | string | 搜索的文件夹，默认项目根目录 |

| `GlobOutput` 字段 | 类型 | 说明 |
|---|---|---|
| `path` | string | 显示用的搜索目录 |
| `files` | string[] | 按修改时间新的在前，最多 500 个 |
| `truncated?` | boolean | 超过 500 个，或遍历被截断 |
| `skipped?` | integer | 读不了或沙箱禁读而跳过的条目数 |

### Grep、GrepOutput、GrepFile、GrepLine

| `Grep` 字段 | 类型 | 说明 |
|---|---|---|
| `pattern` | string | Go RE2 正则，逐行匹配 |
| `path?` | string | 文件或文件夹，默认项目根目录 |
| `include?` | string | 只搜相对 `path` 匹配这个路径模式的文件 |
| `ignore_case?` | boolean | 不分大小写 |
| `files_only?` | boolean | 只返回匹配的文件，不返回行 |
| `context?` | integer | 匹配行前后各带几行，0 到 10 |

| `GrepOutput` 字段 | 类型 | 说明 |
|---|---|---|
| `path` | string | 显示用的搜索路径 |
| `files` | `GrepFile[]` | |
| `matches` | integer | 总匹配数 |
| `truncated?` | boolean | 显示的行超过 300 行（`files_only` 时文件超过 500 个），或遍历被截断 |
| `skipped?` | integer | 读不了或沙箱禁读而跳过的条目数；超过 8 MiB 的文件不搜 |

| `GrepFile` 字段 | 类型 | 说明 |
|---|---|---|
| `path` | string | |
| `matches` | integer | 这个文件里的匹配数 |
| `lines?` | `GrepLine[]` | `files_only` 时不给 |

| `GrepLine` 字段 | 类型 | 说明 |
|---|---|---|
| `line` | integer | 行号 |
| `text` | string | 这一行，最多 500 字符 |
| `match?` | boolean | `true` 是匹配行，否则是上下文行 |

## 通知

本模块没有自己的通知。工具调用的过程走 `item/*` 通知，见[一轮与条目](/zh/integrate/protocol/turns)；模型列表、工具列表和 MCP 状态变化时不推送，客户端在重连、或用户改了配置之后重新读。

## 类型

### Model

| 字段 | 类型 | 说明 |
|---|---|---|
| `name` | string | 发给服务商的模型名 |
| `connection` | string | 连接 ID，`turn/start` 的 `connection` 传它 |
| `thinking?` | boolean \| null | 不出现或 `true`：能关思考的服务商保持思考开着；`false`：关掉 |
| `images?` | boolean | 这个模型收图片 |

### ToolDescriptor

| 字段 | 类型 | 说明 |
|---|---|---|
| `provider` | string | 提供方 id，见[提供方](#提供方) |
| `name` | string | 工具名，权限规则用它，比如 `run_command(git:*)` 里的 `run_command` |
| `description` | string | 给模型看的描述 |
| `annotations` | `Annotations` | 见下表 |
| `input_schema` | object | 参数的 JSON Schema。注意是 snake_case，这是模型那一侧的命名 |

### Annotations

和 MCP 的工具注解同名同义。条目上的 `annotations` 是调用发生时这些注解的快照。

| 字段 | 类型 | 说明 |
|---|---|---|
| `title?` | string | 显示名 |
| `readOnlyHint?` | boolean | 只读。审批策略和并行执行都读它：只读的调用可以和别的只读调用并行 |
| `destructiveHint?` | boolean \| null | 可能删除或覆盖东西。引擎不读，只给客户端显示 |
| `idempotentHint?` | boolean | 重复调用结果相同。引擎不读 |
| `openWorldHint?` | boolean \| null | 接触外部世界。**不出现时当作 `true`**，审批策略读它 |

MCP 工具的注解是服务器自报的，引擎无法验证。注解怎样决定要不要审批，见[权限](/zh/integrate/protocol/permissions)。

### ServerStatus

| 字段 | 类型 | 说明 |
|---|---|---|
| `name` | string | 服务器名，也是它的提供方 id |
| `connected` | boolean | 是否连上 |
| `tools` | integer | 交给 agent 的工具数 |
| `skippedTools?` | string[] | 加上 `<服务器>__` 前缀后不匹配 `^[A-Za-z0-9_-]{1,64}$`、因此没有交给 agent 的工具，列的是服务器自己给的短名 |
| `error?` | string | 没连上的原因，带服务器的 stderr |

### 提供方

条目的 `server` 和 `ToolDescriptor.provider` 是同一个东西：工具的提供方 id。

| 提供方 id | 工具 |
|---|---|
| `workspace` | `run_command`、`read_file`、`glob`、`grep`、`edit_file`、`write_file` |
| `plan` | `update_plan` |
| `subagents` | `Agent` |
| `user_input` | `request_user_input` |
| `web` | `web_fetch` |
| `cron` | `create_scheduled_job`、`pause_scheduled_job`、`delete_scheduled_job`、`list_scheduled_jobs` |
| `memory` | `memory_search` |
| `skills` | `list_skills`、`activate_skill`、`read_skill_resource`、`get_skills_root_dir`，只在宿主配了技能目录时出现 |
| `context` | `read_tool_output` |
| `deferred_tools` | `load_tools` |
| `tool_registry` | `list_tool_providers`、`list_tools_for_provider` |
| MCP 服务器名 | 这个服务器的工具 |
| 宿主自己的 id | 宿主加的提供方，比如桌面端的 `browser` |

这些名字来自各提供方的 `Name()` 和录制的会话。宿主不一定装配全部提供方，比如不配 `workspace.New` 就没有 `workspace`，客户端要按 `tool/list` 实际返回的来。

契约里另有一个 `providers` 段，只有 `cron`、`skills`、`memory` 三个（`db21f76` 加入 `memory`）。生成它的代码注释说它是"`ItemRow.server` 取到的 ollupi 自带提供方 id"，但它不全：上表里的 `workspace`、`plan`、`web` 等都不在里面。客户端不要拿它判断一个 `server` 合不合法。桌面端生成了这个常量，但没有用到它。

## 错误与边界

| 错误码 | 本模块里的触发条件 |
|---|---|
| `-32602` | `turn/start` 选的连接不存在；选的模型不收图片而消息或会话里有图片 |
| `-32000` | `ToolsFor` 失败（`tool/list`）、取 MCP 服务器失败（`mcpServer/list`） |

边界：

- **目录不推送。** 引擎没有"模型列表变了""MCP 服务器连上了"的通知。MCP 服务器在后台断开、重连，客户端只能重新调 `mcpServer/list` 看。
- **列表共用，客户端按用户。** 模型列表所有用户相同，即使宿主配了 `ClientFor` 让每个用户用自己的密钥；工具列表和 MCP 状态按用户。
- **注解靠自报。** 只读、不接触外部是 MCP 服务器自己声明的，客户端显示时应当当作提示，不是保证。
- **工具输出不稳定。** `builtinTools` 以外的输出随时可能为模型调整，客户端只当 JSON 显示。

## 代码位置

| 仓库 | 路径 | 职责 |
|---|---|---|
| ollupi | `gateway/server.go` | `modelList`、`toolList`、`mcpServerList` |
| ollupi | `gateway/protocol.go` | `ModelListResult`、`ToolListResult`、`MCPServerListResult` |
| ollupi | `gateway/schema_test.go` | `builtinTools`、`providers` 两段契约，内置工具名不含 `__` 的检查 |
| ollupi | `agent/models.go` | `ListModels`、`conversationModel`：一轮用哪个模型 |
| ollupi | `agent/attachments.go` | `checkImages` |
| ollupi | `agent/agent.go` | `ListTools`、`registryFor`：第一次调用等 MCP 连接 |
| ollupi | `tools/registry.go` | 注册表、工具名唯一、`ProviderSeparator`、按提供方和名字排序 |
| ollupi | `tools/spec.go` | `ToolDescriptor`、`Annotations`、`OpenWorld` |
| ollupi | `tools/mcp/servers.go`、`session.go` | `ServerStatus`、服务器名和工具名规则、`skippedTools` |
| ollupi | `pkg/llm/chat.go` | `Model` |
| ollupi | `tools/plan/plan.go` | `Plan`、`PlanStep` 的校验 |
| ollupi | `tools/subagent/subagent.go` | `SubagentCall` |
| ollupi | `tools/workspace/execution.go`、`files.go`、`read.go` | `CommandOutput`、`FileOutput`、读取和搜索工具的参数、输出和上限 |
