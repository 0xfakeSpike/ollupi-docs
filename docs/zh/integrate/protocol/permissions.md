# 权限

权限设置决定 agent 的哪些工具调用直接运行、哪些先问用户、哪些拒绝。协议里能读写的是三层：用户的设置、工作区的设置和会话的设置，各由一个 `*/updatePermissions` 方法整体替换；用户在审批时选"总是允许"，也会把规则写进工作区或会话那一层。

一次调用要不要问、问了之后怎样回答，见[审批与提问](/zh/integrate/protocol/approvals)；规则怎样判定、命令怎样解析，见引擎的[权限与审批](/zh/engine/permissions)，这里只讲客户端看得到的部分。

本页按引擎 v0.17.2 写。示例来自对 v0.17.1 网关的脚本试验（假模型、单用户、本机沙箱），ID 缩短了，时间是当时的临时值。

## 概念与状态

### 四层设置

每层的格式都是 [`PermissionSettings`](#permissionsettings)：一个可选的审批策略，加 allow、ask、deny 三组规则。

| 层 | 存在哪里 | 客户端能否读写 |
|---|---|---|
| 部署默认 | 宿主（host）装配引擎时给的 `host.Config.Permissions`；没给策略时是 `on-request` | 都不能。协议里没有读它的方法 |
| 用户 | `SettingsRow.permissions` | `settings/read` 读，`settings/updatePermissions` 写 |
| 工作区 | `WorkspaceRow.settings` | `workspace/list` 等读，`workspace/updatePermissions` 写 |
| 会话 | `ThreadRow.settings` | `thread/read`、`thread/list` 等读，`thread/updatePermissions` 写。新会话这一层是空的 |

一次调用按这几层合并后的结果判定：

- **策略取最后一个非空的。** 会话没设就用工作区的，工作区没设就用用户的，用户也没设就用部署默认的。默认层总有策略（宿主不设时补成 `on-request`，设了读不懂的值时 `host.New` 直接失败），所以合并后总有策略。
- **规则取并集。** deny 永远先判定，所以上面的层可以加规则，去不掉下面那几层的 deny。
- **不属于工作区的会话**只有部署默认、用户、会话三层。

客户端读不到部署默认层，所以三层都没设策略时，它只能假定是 `on-request`，除非宿主另外告诉它。

**子 agent 会话**不用自己的设置：它的会话层换成父会话的设置，另外叠上它这种子 agent 自己的一层。通用子 agent 拿不到派生子 agent 和定时任务的工具；浏览器子 agent 只能用浏览器、读截断输出、技能和计划这几个提供方的工具。子 agent 会话也不能改权限，`thread/updatePermissions` 对它返回 `-32013`。

**用户的记忆开关**也作用在用户这一层：`settings/update` 把 `memory` 关掉后，这一层去掉 `memory` 提供方的工具，模型拿不到 `memory_search`，见[设置](/zh/integrate/protocol/settings)。

**生效时机。** 正在运行的一轮每走一步（调一次模型，或执行一批工具调用）都重新读会话、工作区和用户的设置，所以修改从下一步起生效，赶不上这一步已经判定过的调用。

::: info 演进
v0.12.1 只有三层：agent 默认、工作区、会话，用户没有自己的一层。`1ae27b2` 把每个用户的权限层、MCP 服务器和记忆开关存进数据库，加了 `settings/updatePermissions`，顺序变成部署、用户、工作区、会话。`13eafa9` 让 `thread/start` 不再带权限参数，新会话从空的一层开始。
:::

### 审批策略

`ApprovalPolicy` 有三档，只在规则没有给出结论时起作用：

| 档 | 值 | agent 可以自己做的事 |
|---|---|---|
| 严格 | `untrusted` | 只有声明只读且不接触外部的调用：读文件、搜索文件、更新计划、提问、派子 agent、搜记忆、列定时任务、读技能 |
| 适中 | `on-request` | 再加上在沙箱里执行的命令和文件修改 |
| 宽松 | `never` | 规则之外的一切，包括需要完全访问的命令 |

其他调用都会问：适中档下是网页读取、定时任务的新建暂停删除、所有 MCP 工具、`claude` 工具和要提权（escalation）的命令。MCP 服务器自报的只读和不接触外部的标注引擎不采信，所以 MCP 工具在严格档和适中档下每次都问。完整的判定表见[审批策略](/zh/engine/permissions#审批策略)。宽松档并不是"什么都放行"：规则读不懂的命令遇到可能适用的 deny 规则时直接拒绝。

::: info 演进
v0.12.1 的适中档放行声明只读的 MCP 工具。`fdefa84` 不再采信 MCP 服务器自报的只读和不接触外部的标注，MCP 工具因此在适中档下也要问。
:::

## 典型流程

### 改用户的权限

客户端把用户这一层设成严格档，并禁止 `rm`。网关先发 `settings/changed`，再回复，两者都是更新后的整个 `SettingsRow`：

```json
→ {"jsonrpc":"2.0","id":7,"method":"settings/updatePermissions","params":{"approvalPolicy":"untrusted","permissions":{"deny":["run_command(rm:*)"]}}}
← {"jsonrpc":"2.0","method":"settings/changed","params":{"redaction":true,"memory":true,"learn":true,"permissions":{"approvalPolicy":"untrusted","permissions":{"deny":["run_command(rm:*)"]}}}}
← {"jsonrpc":"2.0","id":7,"result":{"redaction":true,"memory":true,"learn":true,"permissions":{"approvalPolicy":"untrusted","permissions":{"deny":["run_command(rm:*)"]}}}}
```

### 改会话的权限

把一个会话设成宽松档：

```json
→ {"jsonrpc":"2.0","id":41,"method":"thread/updatePermissions","params":{"threadId":"2ad00bfd-…","approvalPolicy":"never","permissions":{"deny":["run_command(rm:*)"]}}}
← {"jsonrpc":"2.0","method":"thread/changed","params":{"threadId":"2ad00bfd-…","thread":{"id":"2ad00bfd-…","workspaceId":"fff33a60-…","environmentId":"47a473af-…","title":"Deploy review","settings":{"approvalPolicy":"never","permissions":{"deny":["run_command(rm:*)"]}},"status":"idle","createdAt":"2026-11-18T12:18:42.825485Z","updatedAt":"2026-11-18T12:18:42.825948Z"},"seq":15}}
← {"jsonrpc":"2.0","id":41,"result":{"thread":{ …同上… }}}
```

再发一次，只带一条 allow 规则。结果里的策略和 deny 规则都没了，因为这是整体替换：

```json
→ {"jsonrpc":"2.0","id":42,"method":"thread/updatePermissions","params":{"threadId":"2ad00bfd-…","permissions":{"allow":["run_command(git status:*)"]}}}
← {"jsonrpc":"2.0","method":"thread/changed","params":{"threadId":"2ad00bfd-…","thread":{ … "settings":{"permissions":{"allow":["run_command(git status:*)"]}}, … },"seq":16}}
← {"jsonrpc":"2.0","id":42,"result":{"thread":{ … }}}
```

### 改工作区的权限，以及一次被拒的修改

给工作区加一条 ask 规则，没给策略，所以工作区沿用用户层或部署默认的策略：

```json
→ {"jsonrpc":"2.0","id":23,"method":"workspace/updatePermissions","params":{"workspaceId":"fff33a60-…","permissions":{"ask":["run_command"]}}}
← {"jsonrpc":"2.0","method":"workspace/changed","params":{"workspace":{"id":"fff33a60-…","name":"Demo", … ,"settings":{"permissions":{"ask":["run_command"]}}, … }}}
← {"jsonrpc":"2.0","id":23,"result":{"workspace":{ … }}}
```

接着再加一条规则，指向一个没连上的 MCP 服务器 `broken` 的工具，被拒绝，设置不变：

```json
→ {"jsonrpc":"2.0","id":24,"method":"workspace/updatePermissions","params":{"workspaceId":"fff33a60-…","permissions":{"ask":["run_command","broken__new_tool"]}}}
← {"jsonrpc":"2.0","id":24,"error":{"code":-32602,"message":"invalid permission settings: the permission settings of workspace \"Demo\": permission rule \"broken__new_tool\": the MCP server \"broken\" is not connected, so its tools cannot be checked now; add this rule once it is connected"}}
```

### 总是允许

一个不属于工作区的会话里，模型要运行 `echo hi`，审批请求带着建议规则：

```json
← {"jsonrpc":"2.0","id":1,"method":"item/toolCall/requestApproval","params":{"threadId":"eb2c51e5-…","turnId":"ace2d2da-…","itemId":"c1","approvalId":"a1","server":"workspace","tool":"run_command","arguments":{"program":"echo","args":["hi"]},"content":"echo hi","suggestedRules":["run_command(echo hi:*)"],"availableDecisions":["accept","acceptForSession","acceptAlways","decline"]}}
→ {"jsonrpc":"2.0","id":1,"result":{"decision":"acceptAlways"}}
```

决定和规则在同一个事务里写下，所以随后的 `thread/changed` 已经带着新规则，`turn/changed` 和 `item/changed`（`approval.decision` 为 `acceptAlways`）跟在后面，三条的 `seq` 相同：

```json
← {"jsonrpc":"2.0","method":"thread/changed","params":{"threadId":"eb2c51e5-…","thread":{ … "settings":{"permissions":{"allow":["run_command(echo hi:*)"]}},"status":"active", … },"seq":20}}
```

工作区里的会话做同样的事，规则写进工作区：先是这个会话的 `thread/changed`、`turn/changed`、`item/changed`，最后是 `workspace/changed`，工作区原有的 ask 规则还在：

```json
← {"jsonrpc":"2.0","method":"workspace/changed","params":{"workspace":{"id":"4dc76ecd-…","name":"Demo", … ,"settings":{"permissions":{"allow":["run_command(git status:*)"],"ask":["run_command"]}}, … }}}
```

规则写到哪一层：

| 会话 | 写进 | 通知 |
|---|---|---|
| 在工作区里 | 工作区设置 | `workspace/changed` |
| 不在工作区 | 会话设置 | `thread/changed` |
| 子 agent | 先换成父会话，再按上面两条 | 同上 |

写入是把建议规则并进这一层原有的设置，策略和别的规则不动，已有的同一条规则不重复，校验和 `*/updatePermissions` 相同。用户层不会被"总是允许"写入。写入不合法时这个决定也不生效，客户端收到 `error` 通知，同一个审批请求重新发来。

建议规则怎么来：带内容的工具（命令、路径、主机名）按内容给，命令按子命令各给一条，第二个词像子命令时写成 `程序 子命令:*`（如 `git status --short` 建议 `run_command(git status:*)`），否则用原文；不带内容的工具（比如 MCP 工具）建议工具名本身。命令含 `*`、看不清或要提权时不给建议，这时也没有 `acceptAlways`；由某条 ask 规则引起的审批只有 `accept` 和 `decline`。见["总是允许"的写入](/zh/engine/permissions#总是允许-的写入)。

## 方法

三个方法都是整体替换：新设置替换这一层的全部内容，不是合并，没写的策略就是不设，没写的规则就没了。要加一条规则，先读出当前的设置，改好再整份发回去。

三个方法写之前都要拿到这个用户的工具清单来校验规则，第一次调用时可能要先连上他的 MCP 服务器，每个服务器最多等 30 秒，见 [mcpServer/list](/zh/integrate/protocol/models-tools#mcpserver-list)。

### settings/updatePermissions

| | |
|---|---|
| 参数 | 内嵌的 `approvalPolicy?`、`permissions`（[`SettingsPermissionsParams`](#参数类型)） |
| 结果 | 更新后的整个 [`SettingsRow`](/zh/integrate/protocol/settings#类型-settingsrow) |
| 通知 | `settings/changed`，载荷同结果 |

用户层按"部署默认加这一层"校验。

| 错误 | 什么时候 |
|---|---|
| `-32602` | 策略不是三档之一、规则写错、工具不存在等，见[校验](#校验) |
| `-32000` | 取这个用户的工具清单失败，详情只在服务端日志 |

### thread/updatePermissions

| | |
|---|---|
| 参数 | `threadId`，加内嵌的 `approvalPolicy?`、`permissions`（`ThreadPermissionsParams`） |
| 结果 | `{"thread": ThreadRow}`，更新后的整行，见 [ThreadRow](/zh/integrate/protocol/threads#threadrow) |
| 通知 | `thread/changed`，带这次提交的 `seq` |

会话层按"部署默认、用户、工作区（如果有）、这一层"校验。已归档的会话也能改。改权限会刷新会话的 `updatedAt`，会话在 `thread/list` 里排到前面。

| 错误 | 什么时候 |
|---|---|
| `-32602` | 设置不合法，见[校验](#校验) |
| `-32013` | 子 agent 会话 |
| `-32004` | 会话不存在或属于别的用户，比如 `store: thread nope: store: not found` |
| `-32000` | 取这个用户的工具清单失败 |

### workspace/updatePermissions

| | |
|---|---|
| 参数 | `workspaceId`，加内嵌的 `approvalPolicy?`、`permissions`（`WorkspacePermissionsParams`） |
| 结果 | `{"workspace": WorkspaceRow}`，更新后的整行 |
| 通知 | `workspace/changed` |

工作区层按"部署默认、用户、这一层"校验，和这个工作区里的会话设置无关。已归档的工作区也能改。更新会刷新工作区的 `updatedAt`。

| 错误 | 什么时候 |
|---|---|
| `-32602` | 设置不合法 |
| `-32004` | 工作区不存在或属于别的用户；`workspaceId` 为空也是这样：`store: workspace : store: not found` |
| `-32000` | 取这个用户的工具清单失败 |

### thread/start 不带权限

`thread/start` 只有 `workspaceId`、`environmentId`、`title` 三个参数，新会话的会话层是空的 `{"permissions":{}}`，按工作区、用户和部署默认运行。网关拒绝它不认识的参数，所以还在发 `approvalPolicy`、`permissions` 的客户端会收到 `-32602`。会话的其他参数见[会话](/zh/integrate/protocol/threads)。

### 校验

三个方法用同一套校验：先校验这一层自己，再把它和下面的层合并后校验一遍。错误信息的格式是 `invalid permission settings: <哪一层>: <原因>`，层的名字是 `your permission settings`、`the permission settings of workspace "<名称>"` 或 `this conversation's permission settings`。试验里的几种：

| 设置 | `message` 里的原因 |
|---|---|
| `approvalPolicy: "sometimes"` | `approval policy "sometimes" must be one of ["untrusted" "on-request" "never"]` |
| `allow: ["run_command("]` | `permissions.allow: permission rule "run_command(": a specifier must end with )` |
| `allow: ["no_such_tool"]` | `permission rule "no_such_tool": tool "no_such_tool" is not in the tool registry` |
| `ask: ["broken__new_tool"]`，服务器没连上 | `permission rule "broken__new_tool": the MCP server "broken" is not connected, so its tools cannot be checked now; add this rule once it is connected` |
| `allow: ["memory_search(x)"]`，给不收说明符的工具写说明符 | `permission rule "memory_search(x)": memory_search takes no specifier; write "memory_search" to match every call` |

规则指向的 MCP 服务器暂时没连上时，这一层**已经有**的那条规则可以原样保留，新加的才会被拒。所以客户端整份发回设置时，不会因为某个服务器断开而丢掉旧规则。服务器被删掉或改了名，指向它的规则就被拒，错误里写着 `no tool provider is named "<服务器>"; if that MCP server was removed or renamed, remove or rename the rule`。

第二步合并校验时，下面那几层的规则也会再检查一遍。所以下面某一层留着一条指向已删除服务器的规则时，改上面的层也会失败，错误里点名的是下面那一层。

## 通知

| 通知 | 什么时候 |
|---|---|
| `settings/changed` | `settings/updatePermissions` 成功（`settings/update` 也发它） |
| `thread/changed` | `thread/updatePermissions` 成功，或"总是允许"写进了会话设置 |
| `workspace/changed` | `workspace/updatePermissions` 成功，或"总是允许"写进了工作区设置 |

通知来自存储的变更流，事务提交之后才发，发给这个用户的每一条连接。发起修改的那条连接上，通知排在回复之前。载荷都是整行，见[设置](/zh/integrate/protocol/settings)、[会话](/zh/integrate/protocol/threads)和[工作区与执行环境](/zh/integrate/protocol/workspaces)。

::: info 演进
v0.12.1 由各个处理函数自己发通知，`settings/changed` 排在回复之后。`9b5b50b` 把网关改成只从存储的变更流发通知，所有写方法的通知都在提交之后、回复之前。
:::

## 类型

### PermissionSettings

用户的 `permissions`、会话和工作区的 `settings`，也是三个 `*/updatePermissions` 内嵌的参数。

| 字段 | 类型 | 说明 |
|---|---|---|
| `approvalPolicy?` | [`ApprovalPolicy`](#approvalpolicy) | 这一层的审批策略；不出现表示沿用下面的层 |
| `permissions` | [`PermissionRules`](#permissionrules) | 这一层的规则，总会出现，可以是 `{}` |

### PermissionRules

| 字段 | 类型 | 说明 |
|---|---|---|
| `allow?` | string[] | 直接运行 |
| `ask?` | string[] | 每次都问，不给"总是允许" |
| `deny?` | string[] | 拒绝；不带说明符的 deny 还会把工具从发给模型的列表里去掉 |

### ApprovalPolicy

`untrusted`（严格）、`on-request`（适中）、`never`（宽松），见[审批策略](#审批策略)。

### 参数类型

`SettingsPermissionsParams` 就是一份 `PermissionSettings`；`ThreadPermissionsParams` 是它加 `threadId`，`WorkspacePermissionsParams` 是它加 `workspaceId`。

## 规则语法

每条规则是 `工具` 或 `工具(说明符)`。说明符匹配这次调用的内容：命令行、路径或主机名。

| 写法 | 匹配 |
|---|---|
| `edit_file` | 这个工具的所有调用 |
| `run_command(git status)` | 命令完全等于 `git status` |
| `run_command(git:*)` | `git`，或 `git` 后接空格和任意内容 |
| `read_file(src/*)` | `src/` 开头的路径，`*` 跨目录 |
| `web_fetch(example.com)` | 主机名 |
| `github__create_issue` | MCP 工具：只能写工具名，不能带说明符 |

deny 命中命令的任何一部分就生效，allow 要覆盖命令的每一部分：允许了 `git:*`，`git status && rm -rf x` 不会因为这条 allow 放行，而是交给审批策略决定。大小写、通配符和看不清的命令怎样处理，见[规则语法](/zh/engine/permissions#规则语法)和[命令解析](/zh/engine/permissions#命令解析)。

## 错误与边界

- **读不到部署默认层。** 协议只暴露用户、工作区和会话三层，客户端算不出实际生效的策略，除非它自己知道宿主的默认设置。
- **整体替换，没有并发保护。** 两个客户端先后读、改、写同一层，后写的覆盖先写的；"总是允许"在中间写入的规则也可能被一次整份发回的旧设置覆盖掉。
- **修改赶不上已经判定的调用。** 新设置从这一轮的下一步起生效。
- **MCP 工具只能整体放行或禁止**，而且在严格档和适中档下总要问，见[技能与 MCP](/zh/engine/skills-mcp#权限与沙箱)。
- **删掉 MCP 服务器不会删掉指向它的规则。** 用户、工作区或会话层里留着这样的规则时，用到这一层的会话每一轮都会失败（`run: the permission settings: …`），直到客户端删掉或改名这条规则。部署默认层不受影响：它可以写某个用户没有的 MCP 工具。
- **宽松档下需要完全访问的命令不问。** 只有 deny 规则拦得住，见[边界与已知问题](/zh/engine/permissions#边界与已知问题)。

## 代码位置

| 路径 | 职责 |
|---|---|
| `gateway/protocol.go` | `ThreadPermissionsParams`、`WorkspacePermissionsParams`、`SettingsPermissionsParams`、方法表 |
| `gateway/threads.go`、`gateway/owned.go` | `threadPermissions`、`workspacePermissions`、`settingsPermissions` |
| `gateway/server.go` | 把变更流里的事件转成 `thread/changed`、`workspace/changed`、`settings/changed` |
| `app/settings.go` | `UpdateUserPermissions`、`UpdateWorkspacePermissions`、`UpdateThreadPermissions`、`allowAlways` |
| `app/turns.go` | `Decide`：决定和"总是允许"的写入在同一个事务里 |
| `account/account.go` | 各层的名字、`Deployment`、`Layers`、`ParentLayer`，记忆开关去掉 `memory` 提供方 |
| `agent/agent.go` | 子 agent 自己的一层 |
| `policy/policy.go` | `Settings`、`Rules`、三档策略、`Resolve`、`ErrInvalidSettings` |
| `policy/validate.go` | `Validate`：这一层和合并后的两步校验，没连上的 MCP 服务器 |
| `policy/checker.go` | 合并各层，判定一次调用 |
| `policy/rules.go` | 规则语法、建议规则 |
| `run/run.go` | `permit`：每一步重新组装各层 |
| `host/host.go` | 部署默认层的策略默认为 `on-request` |
