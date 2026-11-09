# 权限

权限设置决定 agent 的哪些工具调用直接运行、哪些先问用户、哪些拒绝。协议里能读写的是两层：工作区的设置和会话的设置，各由一个 `*/updatePermissions` 方法整体替换；用户在审批时选"总是允许"，也会把规则写进其中一层。

一次调用要不要问、问了之后怎样回答，见[审批与提问](/zh/integrate/protocol/approvals)；规则怎样判定、命令怎样解析，见引擎的[权限与审批](/zh/engine/permissions)，这里只讲客户端看得到的部分。

本页按引擎 v0.12.1 写。示例有两个来源：桌面端仓库录制的会话 `packages/protocol/fixtures/session.json`（录制时的协议摘要等于 v0.12.1 的 `protocolSha256`），以及对 v0.12.1 网关的脚本试验，标为"实测"。ID 和时间是当时的临时值。

## 概念与状态

### 三层设置

每层的格式都是 [`PermissionSettings`](#permissionsettings)：一个可选的审批策略，加 allow、ask、deny 三组规则。

| 层 | 存在哪里 | 客户端能否读写 |
|---|---|---|
| agent 默认 | 宿主装配引擎时给的 `Config.Settings` | 都不能。协议里没有读它的方法 |
| 工作区 | `WorkspaceRow.settings` | `workspace/list` 等读，`workspace/updatePermissions` 写 |
| 会话 | `ThreadRow.settings` | `thread/read` 等读，`thread/start` 时给，`thread/updatePermissions` 写 |

一次调用按三层合并后的结果判定：

- **策略取最后一个非空的。** 会话没设就用工作区的，工作区也没设就用 agent 默认的。默认层必须有策略，否则引擎启动不了，所以合并后总有策略。
- **规则取并集。** deny 永远先判定，所以下层可以加规则，去不掉上层的 deny。

客户端读不到默认层，所以两层都没设策略时，它不知道实际生效的是哪一档；桌面端由它自己的配置文件给默认层，界面知道这个值。

子 agent 会话不用自己的设置：它的层是 agent 默认、工作区、父会话的设置，再加一条 `Deny: ["Agent"]`，所以子 agent 不能再派生子 agent。子 agent 会话也不能改权限，`thread/updatePermissions` 对它返回 `-32013`。

修改在下一次模型回答之后生效：正在运行的一轮在每次回答后重读设置，所以改动可能赶不上这一轮已经在执行的那批调用。

### 审批策略

`ApprovalPolicy` 有三档，只在规则没有给出结论时起作用：

| 档 | 值 | agent 可以自己做的事 |
|---|---|---|
| 严格 | `untrusted` | 只有只读且不接触外部的调用：读文件、搜索、更新计划 |
| 适中 | `on-request` | 再加上在沙箱里执行的命令和文件修改，以及声明只读的 MCP 工具 |
| 宽松 | `never` | 规则之外的一切，包括离开沙箱的命令 |

其他调用都会问：严格档下是沙箱内命令和声明只读但可能接触外部的 MCP 工具；适中档下是网页读取、定时任务的增删、没声明只读的 MCP 工具和提权（escalation）的命令。完整的判定表见[审批策略](/zh/engine/permissions#审批策略)。宽松档并不是"什么都放行"：规则读不懂的命令遇到可能适用的 deny 规则时直接拒绝，不会放行。

## 典型流程

### 改会话的权限

录制的会话里，客户端把会话设成宽松档，并禁止 `rm`：

```json
{ "jsonrpc": "2.0", "id": 28, "method": "thread/updatePermissions", "params": { "threadId": "9f311e1e-e8d6-47b8-a5f5-2e49f0d1be23", "approvalPolicy": "never", "permissions": { "deny": ["run_command(rm:*)"] } } }
```

网关先发 `thread/changed`，再回复，两者带的都是更新后的整行会话：

```json
{ "jsonrpc": "2.0", "id": 28, "result": { "thread": { "id": "9f311e1e-e8d6-47b8-a5f5-2e49f0d1be23", "workspaceId": "ab146065-d40b-4f19-bdda-d2c4ea51a3ae", "environmentId": "3792e905695b164d7e281e236fc20963", "title": "", "settings": { "approvalPolicy": "never", "permissions": { "deny": ["run_command(rm:*)"] } }, "createdAt": "2026-11-08T11:44:54.505636Z", "updatedAt": "2026-11-08T11:45:07.487543Z" } } }
```

### 改工作区的权限，以及一次被拒的修改

同一个会话里，客户端给工作区加一条 ask 规则，没给策略，所以工作区沿用默认层的策略：

```json
{ "jsonrpc": "2.0", "id": 29, "method": "workspace/updatePermissions", "params": { "workspaceId": "ab146065-d40b-4f19-bdda-d2c4ea51a3ae", "permissions": { "ask": ["run_command"] } } }
```

网关先发 `workspace/changed`，再回复整行工作区，`settings` 是 `{"permissions": {"ask": ["run_command"]}}`。

接着它再加一条规则，指向一个没连上的 MCP 服务器的工具，被拒绝，设置不变：

```json
{ "jsonrpc": "2.0", "id": 30, "method": "workspace/updatePermissions", "params": { "workspaceId": "ab146065-d40b-4f19-bdda-d2c4ea51a3ae", "permissions": { "ask": ["run_command", "broken__new_tool"] } } }
```

```json
{ "jsonrpc": "2.0", "id": 30, "error": { "code": -32602, "message": "agent: invalid permission settings: the permission settings of workspace \"Demo\": permission rule \"broken__new_tool\": the MCP server \"broken\" is not connected, so its tools cannot be checked now; add this rule once it is connected" } }
```

### 总是允许

实测，一个不属于工作区的会话（general），在严格档下运行 `echo hi`。请求带着建议规则：

```json
{ "jsonrpc": "2.0", "id": 2, "method": "item/toolCall/requestApproval", "params": { "threadId": "df3b579e-163e-4485-b146-42cf85985971", "server": "workspace", "tool": "run_command", "arguments": { "program": "echo", "args": ["hi"] }, "content": "echo hi", "suggestedRules": ["run_command(echo hi:*)"], "availableDecisions": ["accept", "acceptForSession", "acceptAlways", "decline"] } }
```

客户端回复 `{"decision": "acceptAlways"}` 之后，第一条通知就是会话设置的变化，然后才是条目：

```json
{ "jsonrpc": "2.0", "method": "thread/changed", "params": { "threadId": "df3b579e-163e-4485-b146-42cf85985971", "thread": { "id": "df3b579e-163e-4485-b146-42cf85985971", "environmentId": "5550ae798a212fd2f7aecf521dd9a4f5", "title": "", "settings": { "permissions": { "allow": ["run_command(echo hi:*)"] } }, "createdAt": "2026-11-09T05:30:30.58127Z", "updatedAt": "2026-11-09T05:30:30.582187Z" } } }
```

之后是 `item/updated`（`approval.decision` 为 `acceptAlways`）、`thread/status/changed`（`active`）、命令执行和 `item/completed`。

规则写到哪一层：

| 会话 | 写进 | 通知 |
|---|---|---|
| 在工作区里 | 工作区设置 | `workspace/changed` |
| 不在工作区 | 会话设置 | `thread/changed` |
| 子 agent | 先换成父会话，再按上面两条 | 同上 |

写入是在这一层原有的设置上追加 allow 规则，策略和别的规则不动，校验和 `*/updatePermissions` 相同。写入失败时这个决定也不生效，客户端收到 `error` 通知，请求重发。

建议规则怎么来：命令按子命令各给一条，第二个词像子命令时写成 `程序 子命令:*`（如 `git status --short` 建议 `run_command(git status:*)`），否则用原文；命令含 `*`、看不清或要提权时不给建议，这时也没有 `acceptAlways`。见["总是允许"的写入](/zh/engine/permissions#总是允许-的写入)。

## 方法

### thread/start 的权限参数

`thread/start` 的参数里内嵌了一份 `PermissionSettings`：`approvalPolicy?` 和 `permissions`，作为新会话的会话层。引擎按"默认层、工作区、这一层"合并校验，不合法时返回 `-32602`，会话不会建出来。契约里 `permissions` 标为必填，但网关不检查，省略时就是没有规则。会话的其他参数见[会话](/zh/integrate/protocol/threads)。

新会话不能带指向没连上的 MCP 服务器的规则，因为校验时没有"已有设置"可以保留。

### thread/updatePermissions

| | |
|---|---|
| 参数 | `threadId`，加内嵌的 `approvalPolicy?`、`permissions` |
| 结果 | `{"thread": ThreadRow}`，更新后的整行 |
| 通知 | `thread/changed`，在回复之前 |

**整体替换。** 新设置替换会话层的全部内容，不是合并：没写的策略就是不设，没写的规则就没了。实测，会话里先有"总是允许"写入的 `allow: ["run_command(echo hi:*)"]`，再用 `{"permissions": {"deny": ["run_command(rm:*)"]}}` 更新，结果只剩这条 deny。要加一条规则，先读出当前的设置，改好再整份发回去。

| 错误 | 什么时候 |
|---|---|
| `-32602` | 策略不是三档之一、规则写错、工具不存在等，见[校验](#校验) |
| `-32013` | 子 agent 会话 |
| `-32004` | 会话不存在或属于别的用户 |

已归档的会话也能改。改权限不刷新会话的 `updatedAt`，会话在 `thread/list` 里的位置不变。

### workspace/updatePermissions

| | |
|---|---|
| 参数 | `workspaceId`（必填），加内嵌的 `approvalPolicy?`、`permissions` |
| 结果 | `{"workspace": WorkspaceRow}`，更新后的整行 |
| 通知 | `workspace/changed`，在回复之前 |

同样是整体替换。工作区层按"默认层加这一层"校验，和这个工作区里的会话设置无关。

| 错误 | 什么时候 |
|---|---|
| `-32602` | `workspaceId` 为空（`workspaceId is required`），或设置不合法 |
| `-32004` | 工作区不存在或属于别的用户 |

已归档的工作区也能改。更新会刷新工作区的 `updatedAt`。

### 校验

两个方法和 `thread/start` 用同一套校验：先校验这一层自己，再把它和上面的层合并后校验一遍。错误信息的格式是 `agent: invalid permission settings: <哪一层>: <原因>`，层的名字是 `this conversation's permission settings` 或 `the permission settings of workspace "<名称>"`。实测和录制里的几种：

| 设置 | `message` 里的原因 |
|---|---|
| `approvalPolicy: "sometimes"` | `approval policy "sometimes" must be one of ["untrusted" "on-request" "never"]` |
| `allow: ["run_command("]` | `permissions.allow: permission rule "run_command(": a specifier must end with )` |
| `allow: ["no_such_tool"]` | `permission rule "no_such_tool": tool "no_such_tool" is not in the tool registry` |
| `ask: ["broken__new_tool"]`，服务器没连上 | `permission rule "broken__new_tool": the MCP server "broken" is not connected, so its tools cannot be checked now; add this rule once it is connected` |
| 给 MCP 工具写说明符 | `permission rule "...": <工具> takes no specifier; write "<工具>" to match every call` |

规则指向的 MCP 服务器暂时没连上时，这一层**已经有**的那条规则可以原样保留，新加的才会被拒。所以客户端整份发回设置时，不会因为某个服务器断开而丢掉旧规则。服务器被删掉或改了名，指向它的规则就会被拒，错误里提示删掉或改名这条规则。

## 通知

| 通知 | 什么时候 |
|---|---|
| `thread/changed` | `thread/updatePermissions` 成功，或"总是允许"写进了会话设置 |
| `workspace/changed` | `workspace/updatePermissions` 成功，或"总是允许"写进了工作区设置 |

两个通知都带整行，载荷见[会话](/zh/integrate/protocol/threads)和[工作区与执行环境](/zh/integrate/protocol/workspaces)。

## 类型

### PermissionSettings

会话和工作区的 `settings`，也是 `thread/start`、`thread/updatePermissions`、`workspace/updatePermissions` 内嵌的参数。

| 字段 | 类型 | 说明 |
|---|---|---|
| `approvalPolicy?` | [`ApprovalPolicy`](#approvalpolicy) | 这一层的审批策略；不出现表示沿用上一层 |
| `permissions` | [`PermissionRules`](#permissionrules) | 这一层的规则，总会出现，可以是 `{}` |

### PermissionRules

| 字段 | 类型 | 说明 |
|---|---|---|
| `allow?` | string[] | 直接运行 |
| `ask?` | string[] | 每次都问，不给"总是允许" |
| `deny?` | string[] | 拒绝；不带说明符的 deny 还会把工具从发给模型的列表里去掉 |

### ApprovalPolicy

`untrusted`（严格）、`on-request`（适中）、`never`（宽松），见[审批策略](#审批策略)。

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

- **读不到默认层。** 协议只暴露工作区和会话两层，客户端没法算出实际生效的策略，除非它自己知道宿主的默认设置。
- **整体替换，没有并发保护。** 两个客户端先后读、改、写同一层，后写的覆盖先写的；"总是允许"在中间写入的规则也可能被一次整份发回的旧设置覆盖掉。
- **修改赶不上正在执行的调用。** 新设置从下一次模型回答起生效。
- **MCP 工具只能整体放行或禁止。** 它们的审批依据是服务器自报的只读和外部标记，见[技能与 MCP](/zh/engine/skills-mcp#权限与沙箱)。
- **宽松档下离开沙箱的命令不问。** 只有 deny 规则拦得住，见[边界与已知问题](/zh/engine/permissions#边界与已知问题)。

## 代码位置

| 仓库 | 路径 | 职责 |
|---|---|---|
| ollupi | `repo/permissions.go` | `PermissionSettings`、`PermissionRules` 的线上格式 |
| ollupi | `gateway/protocol.go` | `ThreadStartParams`、`ThreadPermissionsParams`、`WorkspacePermissionsParams` |
| ollupi | `gateway/threads.go`、`gateway/workspaces.go` | `thread/updatePermissions`、`workspace/updatePermissions` 的处理函数 |
| ollupi | `agent/threads.go`、`agent/workspaces.go` | `UpdateThreadSettings`、`UpdateWorkspaceSettings`、`validateLayer` |
| ollupi | `agent/scope.go` | 三层的组装，层的名字 |
| ollupi | `agent/turns.go` | `allowAlways`：把建议规则写进工作区或会话 |
| ollupi | `agent/permission/permission.go` | `Resolve`、`ValidateLayer`、`ErrInvalidSettings` |
| ollupi | `agent/permission/policy.go` | 三档策略和取值校验 |
