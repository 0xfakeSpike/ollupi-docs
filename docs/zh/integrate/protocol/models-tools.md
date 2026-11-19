# 模型、工具与 MCP

客户端用 `model/list`、`tool/list`、`mcpServer/list` 知道这个用户能选哪些模型、agent 手上有哪些工具、他的 MCP 服务器配了什么、连上了没有，用 `mcpServer/set`、`mcpServer/delete` 增删改他的 MCP 服务器，用 `mcpServer/changed` 跟上。会话里的每条工具调用条目（item）按提供方和工具名解读，其中 10 个内置工具的参数或输出在契约里有类型，其余都是通用 JSON。模型怎样调用、工具怎样执行，见[模型接入](/zh/engine/models)、[工具](/zh/engine/tools)和[技能与 MCP](/zh/engine/skills-mcp)。

本页按引擎 v0.17.2 写。示例来自对 v0.17.1 网关的脚本试验（假模型 `m`、单用户、本机沙箱），省略了 `"jsonrpc":"2.0"`。

## 概念与状态

**模型**由宿主（host）在 `host.Config.Models` 里配好，所有用户看到同一份列表。每个模型绑一条连接（connection），一条连接只给一个模型用（`host.New` 启动时检查，重复时报 `connection "…" is listed twice`），所以客户端用 `connection` 指代模型。列表的第一个是默认模型。一轮（turn）排队时选定模型并记进 `TurnRow.model`，这一轮之后不再改变，见[一轮与条目](/zh/integrate/protocol/turns)。

**工具**按用户分：宿主内置的提供方、宿主在 `host.Config.Tools` 里加的提供方（比如工作区工具、网页读取），加上这个用户自己的 MCP 服务器，合成一张注册表。每个工具属于一个提供方（provider），条目和工具列表里都带着它的 id。注册表要求提供方 id 和工具名都唯一，重复时这个用户的注册表建不出来。

**MCP 服务器**按用户存在库里，每行是一份 `MCPServerConfig`：名字，加一个 stdio 命令或一个 HTTP 地址。服务器名就是它的提供方 id，它的工具名形如 `<服务器名>__<工具名>`。服务器在这个用户第一次需要工具时启动，stdio 服务器在用户自己的沙箱（`Box`）里运行，HTTP 服务器经这个 Box 的网络出去；连不上的服务器只是被跳过，它的工具不出现，状态里记下原因。增删改任何一个服务器后，这个用户的服务器全部关掉，下次需要时重新连。

| 名字 | 规则 | 不满足时 |
|---|---|---|
| MCP 服务器名 | `^[A-Za-z0-9][A-Za-z0-9_-]{0,31}$`，不含 `__`，不能和已有工具的提供方 id 重名（`workspace`、`memory` 等） | `mcpServer/set` 返回 `-32602` |
| MCP 工具的完整名 `<服务器>__<工具>` | `^[A-Za-z0-9_-]{1,64}$`，这是模型 API 接受的工具名；参数 schema 要是对象且能解析 | 这个工具不交给 agent，记进 `MCPServerStatus.skippedTools` |
| 内置工具名 | 不含 `__` | 生成契约时失败 |

因为内置工具名不含 `__`，而 MCP 工具名总含 `__`，客户端只看工具名就能分出是不是 MCP 工具；提供方另见条目的 `server`。

::: info 演进
v0.12.1 的 MCP 服务器由宿主在配置里给出，所有用户共用，协议里只能看状态。`1ae27b2` 把服务器按用户存进数据库，加了 `mcpServer/set`、`mcpServer/delete` 和 `mcpServer/changed`，`mcpServer/list` 改成同时给配置和状态；环境变量和请求头的值按原样使用，不再展开 `${NAME}`。
:::

## 典型流程

客户端连上之后读一次目录，之后按需刷新：

```json
→ {"id":10,"method":"model/list","params":{}}
← {"id":10,"result":{"data":[{"name":"m","connection":"main"}],"default":"main"}}
→ {"id":11,"method":"mcpServer/list","params":{}}
← {"id":11,"result":{"data":[]}}
```

加一个 stdio 服务器。网关先发 `mcpServer/changed`，再原样回复这份配置：

```json
→ {"id":12,"method":"mcpServer/set","params":{"name":"broken","command":"ollupi-no-such-mcp-command","env":{"TOKEN":"abc"}}}
← {"method":"mcpServer/changed","params":{"name":"broken","server":{"name":"broken","command":"ollupi-no-such-mcp-command","env":{"TOKEN":"abc"}}}}
← {"id":12,"result":{"name":"broken","command":"ollupi-no-such-mcp-command","env":{"TOKEN":"abc"}}}
```

再列一次，这次引擎先去连它，状态里写着为什么没连上：

```json
→ {"id":13,"method":"mcpServer/list","params":{}}
← {"id":13,"result":{"data":[{"name":"broken","command":"ollupi-no-such-mcp-command","env":{"TOKEN":"abc"},
    "status":{"name":"broken","connected":false,"tools":0,"error":"workspace: executable \"ollupi-no-such-mcp-command\" is not on PATH"}}]}}
```

几种被拒的配置：

```json
→ {"id":14,"method":"mcpServer/set","params":{"name":"workspace","command":"x"}}
← {"id":14,"error":{"code":-32602,"message":"invalid MCP server: \"workspace\" names tools this agent already has"}}
→ {"id":15,"method":"mcpServer/set","params":{"name":"both","command":"x","url":"https://example.com/mcp"}}
← {"id":15,"error":{"code":-32602,"message":"invalid MCP server: give either a command (stdio) or a URL (HTTP)"}}
→ {"id":16,"method":"mcpServer/set","params":{"name":"a__b","url":"https://example.com/mcp"}}
← {"id":16,"error":{"code":-32602,"message":"invalid MCP server: the name \"a__b\" must be 1 to 32 letters, digits, '-' or '_', start with a letter or digit, and not contain \"__\""}}
```

删除，再删一次：

```json
→ {"id":80,"method":"mcpServer/delete","params":{"name":"broken"}}
← {"method":"mcpServer/changed","params":{"name":"broken","server":null}}
← {"id":80,"result":{}}
→ {"id":81,"method":"mcpServer/delete","params":{"name":"broken"}}
← {"id":81,"error":{"code":-32004,"message":"store: MCP server broken: store: not found"}}
```

`tool/list` 在这个宿主上返回 20 个工具，下面只留一个：

```json
{"provider":"workspace","name":"read_file","description":"Read a text file, its lines numbered. …",
 "annotations":{"title":"Read file","readOnlyHint":true,"destructiveHint":false,"openWorldHint":false},
 "input_schema":{"additionalProperties":false,"properties":{"limit":{…},"offset":{…},"path":{…}},"required":["path"],"type":"object"}}
```

## 方法

### model/list

无参数。

| 结果字段 | 类型 | 说明 |
|---|---|---|
| `data` | `Model[]` | 宿主配置的全部模型，按配置顺序 |
| `default` | string | 第一个模型的 `connection` |

不会失败，不发通知。列表在进程运行期间不变：宿主改了模型要重启引擎，客户端重连后再读一次。

客户端在 `turn/start` 的 `connection` 参数里选模型。引擎按这个顺序决定一轮用哪个模型：

| 顺序 | 用哪条连接 |
|---|---|
| 1 | `turn/start` 传了 `connection`，按原样比对，不去空白 |
| 2 | 没传时，这个会话最后一轮用的连接 |
| 3 | 新会话，用第一个模型的连接 |

定时任务发出的一轮没有 `connection`，按 2、3 选。选出的连接不在列表里时返回 `-32602`：

```text
invalid message: connection "nope" is unavailable; restore it in Settings or select another model
```

这种情况在宿主删掉一个模型之后最常见：老会话的上一轮还记着那条连接，`turn/start` 不带 `connection` 就会失败，客户端要让用户换一个模型。

选出的模型 `images` 不为真时，带图片的消息返回 `-32602` `invalid message: model <名字> does not accept images; pick a model that does`；这个会话里已经有过图片时，不带图片的消息也会被拒：`this conversation shows the model images, and model <名字> does not accept them; pick a model that does`，因为之前的图片每一轮都会再发给模型。一条消息估算超过这个模型输入上限的 25%（至少 256 token）时也返回 `-32602`，提示改用附件发送。

### tool/list

无参数。

| 结果字段 | 类型 | 说明 |
|---|---|---|
| `data` | `ToolDescriptor[]` | 这个用户注册表里的全部工具，包括 MCP 工具和延迟加载的工具，按 `provider`、再按 `name` 排序 |

列的是注册表，不按权限过滤：deny 规则去掉的工具、记忆开关关掉后的 `memory_search`、子 agent 才用得到的工具都在里面。模型实际拿到哪些，要再经过各层权限和角色，见[权限](/zh/integrate/protocol/permissions)。

这个用户第一次调用时，引擎要先连上他的 MCP 服务器才能建出注册表，各服务器并行连，每个最多等 30 秒。之后的调用直接返回，直到他增删改服务器或某个服务器断开。

取注册表失败时返回 `-32000`，比如两个提供方给出了同名工具；详情只在服务端日志里。回复可能很大：每个工具都带完整的 `input_schema`。用 `coder/websocket` 的 Go 客户端要先调大读上限，见[传输](/zh/integrate/protocol#传输)。

### mcpServer/list

无参数。

| 结果字段 | 类型 | 说明 |
|---|---|---|
| `data` | [`MCPServer[]`](#mcpserver) | 这个用户的 MCP 服务器，按名字排序，每个带配置和状态 |

和 `tool/list` 一样，第一次调用会先连这个用户的全部服务器，可能要等。结果里有 `env` 和 `headers` 的原值，令牌之类的秘密也在里面，客户端显示时要自己遮住。读库或取用户沙箱失败时返回 `-32000`。

### mcpServer/set

| 参数 | 类型 | 说明 |
|---|---|---|
| `name` | string | 服务器名，见[概念与状态](#概念与状态)的规则；已有同名的就整份替换 |
| `command?` | string | stdio 服务器的程序，在用户沙箱里按 `PATH` 找 |
| `args?` | string[] | 只能和 `command` 一起给 |
| `env?` | object | 程序的环境变量，只能和 `command` 一起给，值按原样传 |
| `url?` | string | HTTP 服务器的地址（Streamable HTTP） |
| `headers?` | object | 每个请求带上的头，只能和 `url` 一起给 |

`command` 和 `url` 必须正好给一个。结果是原样的这份 `MCPServerConfig`，同时发 `mcpServer/changed`。存下来不等于连得上：配置只检查格式，命令找不到、地址连不通都要等下一次 `mcpServer/list` 或一轮用到工具时才知道。

| 错误 | 什么时候 |
|---|---|
| `-32602` `invalid MCP server: …` | 名字不合规则或和已有提供方重名；`command` 和 `url` 都给或都没给；`args`、`env` 配了 `url`；`headers` 配了 `command` |
| `-32000` | 写之前取这个用户的工具清单失败 |

### mcpServer/delete

| 参数 | 类型 | 说明 |
|---|---|---|
| `name` | string | 服务器名 |

结果是 `{}`，同时发 `server` 为 `null` 的 `mcpServer/changed`。服务器不存在时返回 `-32004`。指向这个服务器的权限规则不会跟着删掉，见[权限的边界](/zh/integrate/protocol/permissions#错误与边界)。

## 通知：mcpServer/changed

| 字段 | 类型 | 说明 |
|---|---|---|
| `name` | string | 服务器名 |
| `server` | `MCPServerConfig` \| null | 写之后的配置；`null` 表示已删除 |

`mcpServer/set` 和 `mcpServer/delete` 成功后发，在事务提交之后、回复之前，发给这个用户的每一条连接。它不带状态：服务器连上、断开都没有通知，客户端要重新调 `mcpServer/list` 看。模型列表和工具列表变化时也不推送。

工具调用的过程走 `item/changed` 通知，见[一轮与条目](/zh/integrate/protocol/turns)。

## 内置工具的参数和输出

契约的 `builtinTools` 段给 10 个内置工具的参数（`arguments`，对应条目里 `arguments` 文本解析之后的对象）和输出（`output`，对应条目的 `result.output`）。只收界面要专门显示、用户要参与的工具：计划、两种子 agent、提问、命令和五个文件工具。

其余工具调用，包括定时任务、`memory_search`、技能、`read_tool_output`、`web_fetch`、`claude`、MCP 和宿主自己的工具，不进契约：客户端把它们当通用调用，显示参数和输出的原始 JSON，不要依赖它们的结构。这些输出是写给模型的，引擎可以随时为模型调整。

| 工具 | 提供方 | 参数 | 输出 |
|---|---|---|---|
| `update_plan` | `plan` | [`Plan`](#plan-和-planstep) | 不进契约，实际是字符串 `Plan updated` |
| `general-sub-agent`、`browser-sub-agent` | `subagents` | [`SubagentCall`](#subagentcall) | [`SubagentLaunched`](#subagentlaunched) |
| `request_user_input` | `user_input` | `UserInputRequest` | `UserInputAnswers`，见[审批与提问](/zh/integrate/protocol/approvals) |
| `run_command` | `workspace` | 不进契约，审批时看 `preparedExecution` | [`CommandOutput`](#commandoutput) |
| `edit_file`、`write_file` | `workspace` | 不进契约，审批时看 `preparedExecution` | [`FileOutput`](#fileoutput) |
| `read_file` | `workspace` | `ReadFile` | `ReadFileOutput` |
| `glob` | `workspace` | `Glob` | `GlobOutput` |
| `grep` | `workspace` | `Grep` | `GrepOutput` |

`builtinTools` 按工具名作键。条目里的 `arguments` 是 JSON **文本**，要客户端自己解析；`result.output` 是工具返回的任意 JSON。

::: info 演进
v0.12.1 只有一个子 agent 工具 `Agent`，输出不进契约。`d18618f` 把子 agent 工具按角色命名为 `general-sub-agent`、`browser-sub-agent`，`25d8a4d` 给派发的输出定了类型 `SubagentLaunched`。更早，定时任务的四个工具和 `memory_search` 曾经在契约里，`0ae03bb` 把它们移出去，改成通用调用。
:::

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

通用子 agent 能用父会话能用的工具，派生子 agent 和定时任务的除外；浏览器子 agent 只能用 `browser`、`context`、`skills`、`plan` 这几个提供方的工具。

### SubagentLaunched

派发立即完成，输出是：

| 字段 | 类型 | 说明 |
|---|---|---|
| `subagent` | string | 子 agent 会话的 ID，和条目的 `childThreadId` 相同 |
| `description` | string | 子 agent 会话的标题 |
| `note` | string | 给模型的说明：子 agent 自己工作，结束后报告回到这个会话 |

子 agent 的报告是父会话里的一条 `agentReport` 条目，见[一轮与条目](/zh/integrate/protocol/turns)。

### CommandOutput

| 字段 | 类型 | 说明 |
|---|---|---|
| `stdout`、`stderr` | string | 各自最多 `max_output_bytes`（默认 1 MiB），超出时保留头尾，中间换成省略提示 |
| `exit_code` | integer | 退出码 |
| `work_dir` | string | 实际的工作目录 |
| `signal?` | string | 被信号终止时的信号名 |
| `truncated?` | boolean | 输出被截过 |
| `sandbox_denials?` | string[] | 沙箱拦下的操作，见[拒绝原因报告](/zh/engine/sandbox#拒绝原因报告) |
| `sandbox?` | string | 关于沙箱的说明；在沙箱外运行时是 `escalated: ran on the host without the sandbox` |

### FileOutput

| 字段 | 类型 | 说明 |
|---|---|---|
| `path` | string | 改的文件，写法同 [`FileChange.path`](/zh/integrate/protocol/approvals#filechange) |
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
| `path` | string | 显示用的路径：会话在工作区里时，工作区根目录之内是相对路径，之外是绝对路径；不在工作区时是绝对路径 |
| `text?` | string | 带行号的文本，每行形如 `1\t# demo`；单行最多 2000 字符，总共读到约 256 KiB 为止 |
| `startLine?`、`endLine?` | integer | 读到的行范围 |
| `totalLines` | integer | 文件总行数 |
| `totalLinesAtLeast?` | boolean | 文件太大（扫过 64 MiB 后）没有数完，`totalLines` 只是下限 |
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
| `path` | string | 显示用的搜索目录，写法同 `ReadFileOutput.path`；`files` 里的路径也一样 |
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
| `path` | string | 显示用的搜索路径，写法同 `ReadFileOutput.path`；`GrepFile.path` 也一样 |
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
| `readOnlyHint?` | boolean | 只读。审批策略和并行执行都读它：连续的只读调用一起执行，最多 8 个 |
| `destructiveHint?` | boolean \| null | 可能删除或覆盖东西。引擎不读，只给客户端显示 |
| `idempotentHint?` | boolean | 重复调用结果相同。引擎不读 |
| `openWorldHint?` | boolean \| null | 接触外部世界。**不出现时当作 `true`**，审批策略读它 |

MCP 工具只带服务器给的 `title`、`destructiveHint`、`idempotentHint`；服务器自报的 `readOnlyHint` 和 `openWorldHint` 引擎不采信，不放进来，所以 MCP 工具在审批时总当作会写、会接触外部，见[审批策略](/zh/integrate/protocol/permissions#审批策略)。

### MCPServerConfig

`mcpServer/set` 的参数和结果，`mcpServer/changed` 的 `server`。字段见 [mcpServer/set](#mcpserver-set) 的参数表。

### MCPServer

`mcpServer/list` 的每一项：`MCPServerConfig` 的全部字段，加一个 `status?`。

### MCPServerStatus

| 字段 | 类型 | 说明 |
|---|---|---|
| `name` | string | 服务器名，也是它的提供方 id |
| `connected` | boolean | 是否连着；连上后又断开的也是 `false` |
| `tools` | integer | 交给 agent 的工具数 |
| `skippedTools?` | string[] | 名字不合规则、重复或参数 schema 不能用、因此没有交给 agent 的工具，列的是服务器自己给的短名 |
| `error?` | string | 没连上或断开的原因，带服务器 stderr 的末尾 |

`status` 在这个服务器还没被连过时不出现（比如列表和连接之间刚加进来的）。

### 提供方

条目的 `server` 和 `ToolDescriptor.provider` 是同一个东西：工具的提供方 id。

| 提供方 id | 工具 | 谁装 |
|---|---|---|
| `plan` | `update_plan` | 引擎总装 |
| `user_input` | `request_user_input` | 引擎总装 |
| `subagents` | `general-sub-agent`、`browser-sub-agent` | 引擎总装 |
| `context` | `read_tool_output` | 引擎总装 |
| `deferred_tools` | `load_tools` | 引擎总装 |
| `memory` | `memory_search` | 引擎总装 |
| `cron` | `create_scheduled_job`、`pause_scheduled_job`、`delete_scheduled_job`、`list_scheduled_jobs` | 引擎总装 |
| `tool_registry` | `list_tool_providers`、`list_tools_for_provider` | 引擎总装 |
| `skills` | `list_skills`、`activate_skill`、`read_skill_resource`、`get_skills_root_dir` | 宿主配了 `SkillsDir` 时 |
| `workspace` | `run_command`、`claude`、`read_file`、`glob`、`grep`、`edit_file`、`write_file` | 宿主在 `host.Config.Tools` 里加 |
| `web` | `web_fetch` | 宿主在 `host.Config.Tools` 里加 |
| 宿主自己的 id | 宿主加的提供方，比如桌面端的 `browser` | 宿主 |
| MCP 服务器名 | 这个服务器的工具 | 用户 |

客户端要按 `tool/list` 实际返回的来，不同宿主装的不一样。

契约里另有一个 `providers` 段，只有 `cron`、`skills`、`memory` 三个。它不是全部提供方：上表里的 `workspace`、`plan`、`web` 等都不在里面。客户端不要拿它判断一个 `server` 合不合法。

::: info 演进
`providers` 段原来只有 `cron` 和 `skills`，`db21f76` 加入 `memory`。
:::

## 错误与边界

| 错误码 | 本模块里的触发条件 |
|---|---|
| `-32602` | `turn/start` 选的连接不存在；选的模型不收图片而消息或会话里有图片；消息太长；MCP 服务器配置不合法 |
| `-32004` | `mcpServer/delete` 的服务器不存在 |
| `-32000` | 取这个用户的注册表失败（`tool/list`、`mcpServer/set`）、读库失败（`mcpServer/list`） |

边界：

- **状态不推送。** 引擎没有"MCP 服务器连上了""断开了"的通知，也没有"模型列表变了"的通知。客户端只能重新调 `mcpServer/list` 看。
- **列表共用，客户端按用户。** 模型列表所有用户相同，即使宿主配了 `ClientFor` 让每个用户用自己的密钥；工具列表和 MCP 服务器按用户。
- **秘密明文往返。** MCP 服务器的 `env` 和 `headers` 存在库里，`mcpServer/list`、`mcpServer/set` 的回复和 `mcpServer/changed` 都带原值。
- **改一个服务器，全部重连。** 增删改任何一个服务器都会关掉这个用户的全部 MCP 连接，下一次需要工具时重新连；正在进行的 MCP 调用随连接一起中断。
- **工具输出不稳定。** `builtinTools` 以外的输出随时可能为模型调整，客户端只当 JSON 显示。

## 代码位置

| 路径 | 职责 |
|---|---|
| `gateway/owned.go` | `modelList`、`toolList`、`mcpServerList`、`mcpServerSet`、`mcpServerDelete` |
| `gateway/server.go` | 把变更流里的事件转成 `mcpServer/changed` |
| `gateway/protocol.go`、`gateway/wire.go` | `ModelListResult`、`ToolDescriptor`、`MCPServer`、`MCPServerStatus`、`MCPServerConfig` |
| `gateway/schema_test.go` | `builtinTools`、`providers` 两段契约，内置工具名不含 `__` 的检查 |
| `app/app.go` | `Models`、`Tools`、`pickModel` |
| `app/turns.go` | `fits`：图片和消息长度的检查 |
| `app/owned.go` | `MCPServers`、`SetMCPServer`、`DeleteMCPServer` |
| `account/account.go` | `MCPServer`、`MCPStatus`、`MCPServer.Check`：服务器名和传输方式的规则 |
| `host/host.go`、`host/models.go` | 内置提供方的装配，模型列表的启动检查 |
| `tool/kit/kit.go` | 注册表：提供方和工具名唯一，按提供方和名字排序，`tool_registry` |
| `tool/tool.go` | `Spec`、`Annotations`、`OpenWorld` |
| `tool/mcp/servers.go`、`tool/mcp/session.go` | 按用户连服务器、改动后全部关掉、状态、工具名规则、`skippedTools`、不采信只读标注 |
| `pkg/llm/chat.go` | `Model` |
| `tool/builtin/plan/plan.go` | `Plan`、`PlanStep` 的校验 |
| `tool/builtin/subagent/subagent.go`、`run/tools.go` | `SubagentCall`、`Launched` |
| `tool/builtin/workspace/execution.go`、`files.go`、`read.go` | `CommandOutput`、`FileOutput`、读取和搜索工具的参数、输出和上限 |
