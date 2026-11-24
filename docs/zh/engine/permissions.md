# 审批与权限

agent 的每个工具调用在写进对话日志时就已经判定：直接运行、问用户，还是拒绝。判定在 `policy` 包里，是不读库、不调工具的纯函数，依据审批策略、规则和调用内容；审批（approval）是判定为"问用户"时的等待，等待期间这一轮不占槽位。权限在整体安全设计里的位置见[安全总览](/zh/engine/security)。

## 为什么这样设计

- **规则先于策略，下层去不掉上层的 deny。** deny 和 ask 代表用户本人，三档策略下都先判定；规则在各层之间取并集。
- **按命令的结构匹配，读不懂就不算数。** 规则看拆开包装后的每个子命令：deny 命中任一部分就生效，allow 要覆盖全部；只有纯字面量的脚本读得懂，其余标为看不清，带说明符的 allow 不算数。
- **全权单独一档。** 全权（full access）指不受沙箱限制地运行，allow 规则不足以让它直接跑，只有 escalate 规则命中才放行，见[全权](#全权)。
- **`never` 是"不问"，不是"不许"。** 规则之外的一切都运行，全权调用也包括在内；规则读不懂又可能命中 deny 的命令直接拒绝，否则 deny 形同虚设。

## 判定顺序

`ruleSet.decide` 先给规则命中一个结论：

1. `deny` 命中 `Match` 或任一 `Part`：拒绝。
2. `ask` 命中：问，带上规则名。
3. 内容看不清（`Opaque`）且有带说明符的 `deny` 或 `ask`：无法证明规则不适用，结果是"看不清"。
4. `escalate` 覆盖这次调用：命中 escalate，直接运行。不带说明符的规则覆盖这个工具的每次调用，内容看不清、工具没有内容都算；带说明符的规则要覆盖每个 `Part`（没有拆分时 `Part` 就是 `Match`），看不清或工具没有内容时不覆盖。
5. `allow` 与 `escalate` 的合集按同样的方式覆盖这次调用：通过。
6. 都没有：没有结论。

`Checker.decide` 再叠上策略和会话状态（`policy/checker.go`）：deny 拒绝，ask 问，escalate 运行；allow 只在调用不申请全权时直接运行，`needsFullAccess` 成立就继续往下；看不清时本会话允许过就运行，`never` 且带说明符的 deny 可能命中就拒绝，其余问；没有结论时 `never` 运行，本会话允许过运行，申请全权或策略要求审批就问，否则运行。

`requiresApproval` 把沙箱与只读条件叠到策略上，明细见[审批策略](#审批策略)。拒绝的原因交给模型：被规则拒绝的告诉它不要重试、换个办法；`never` 下读不懂的命令告诉它写清楚。规则触发的询问带规则名，看不清的说明为什么要问。

## 全权

`needsFullAccess` 是策略不是 `never`、且 `Call.Escalated` 为真。`Escalated` 由工具的准备阶段给出（`tool.Plan`，`run/tools.go` 和 `Sandboxed` 一起交给判定），`run_command` 带 `sandbox_permissions: "require_escalated"`、本机沙箱下运行 `claude` 都会置位（`tool/builtin/workspace/claude.go`）。

- allow 规则命中不直接运行，`on-request` 和 `untrusted` 下转为询问；escalate 规则命中就直接运行，申请全权的调用因此以全权跑完，deny 仍然优先。
- `never` 下不问，全权调用直接运行。
- "本会话允许"对全权调用只覆盖全权调用：`coveredBySuggestion` 用 escalate 规则匹配，还要求调用本身不申请全权才算 allow 覆盖。

协议上这个状态是审批请求的 `escalated` 字段（`gateway/protocol.go` 的 `ApprovalRequestParams`）；执行结果里 `sandbox` 写成 `escalated: ran with full access, without the sandbox's limits`。沙箱什么时候能给全权、给不了怎么报错，见[沙箱](/zh/engine/sandbox#全权)。

## 审批策略

策略只有三档，取 `untrusted`、`on-request`、`never`，在规则没有给出结论时起作用；部署层不设时默认 `on-request`。

| 调用 | `never` | `on-request` | `untrusted` |
| --- | --- | --- | --- |
| 只读且封闭：`read_file`、`glob`、`grep`、`update_plan`、`request_user_input`、`load_tools`、`read_tool_output`、记忆搜索、派生子 agent | 运行 | 运行 | 运行 |
| 只读但没关 `openWorldHint` | 运行 | 运行 | 问 |
| 在沙箱内执行（`Sandboxed`，没有申请全权） | 运行 | 运行 | 问 |
| 其他非只读：`web_fetch`、定时任务的增删改、MCP 工具、沙箱关闭时的命令和文件修改 | 运行 | 问 | 问 |
| 申请全权：带 `require_escalated` 的命令、本机沙箱下的 `claude` | 运行 | 问 | 问 |
| 看不清、工具上有带说明符的 deny | 拒绝 | 问 | 问 |
| 看不清、工具上只有带说明符的 ask | 问 | 问 | 问 |

`on-request` 免问的依据是 `Prepared.Sandboxed`：沙箱已经限制了命令能做什么。`claude` 要网络和主目录里自己的设置，在能给全权的本机沙箱下总是以全权运行，见[工作区工具](/zh/engine/workspace)。

`never` 是"不问任何人"：规则之外的一切都运行，包括全权调用；读不懂又可能命中 deny 的命令直接拒绝，否则把 `rm` 包进 `sh -c "$X"` 就能绕过 `run_command(rm:*)`。

## 规则语法

规则分 `allow`、`escalate`、`ask`、`deny` 四组，每条是 `工具` 或 `工具(说明符)`。

| 写法 | 匹配 |
| --- | --- |
| `edit_file`、`edit_file(*)` | 这个工具的所有调用 |
| `run_command(git status)` | 内容完全等于 `git status` |
| `run_command(git:*)`、`run_command(git *)` | `git`，或 `git` 后接空格和任意内容 |
| `read_file(src/*)` | 相对项目根的路径以 `src/` 开头，`*` 跨目录；不在工作区的会话里路径是绝对路径，见[工作区](/zh/engine/workspace#工具怎样用工作区) |
| `web_fetch(example.com)` | 主机名 |

`*` 编译成 `.*`，可以跨 `/` 和换行，结尾的 `:*` 或空格加 `*` 表示后面的部分可有可无；命令的说明符只把第一个词转小写，其余大小写敏感，路径和主机名的内容整体小写（`Content.Folded`）。空说明符、缺右括号、工具名为空或含空格和括号都报错；工具没有内容（`Spec.Content` 为空）就不能写说明符，MCP 工具都属此类。

### 命令解析

`run_command` 的内容不是简单拼字符串（`tool/builtin/workspace/command.go`）：`Match` 是 `程序名 参数...`，程序名取路径最后一段并转小写；`commandParts` 递归拆开 `sh -c`、`env`、`nohup`、`nice`、`caffeinate`、`time`、`timeout` 这类包装放进 `Parts`，脚本用 `mvdan.cc/sh` 解析出每个简单命令。带 `c` 以外选项的 shell、带选项的包装、`env A=B cmd`、`xargs`、`sudo`、`doas`、不在系统目录下的程序、嵌套超过 4 层、参数里带 `env` 都看不清；程序名不含 `/` 算可信。

`splitScript` 只认简单命令、管道、`;`、`&&`、`||`、`&`、字面量的词和重定向：解析失败、任何展开、引号外的非 ASCII 字符或 `{`、`}`、`~`、`!`、`#`、子 shell 与复合语句、赋值、非字面量重定向、保留字都让整条命令看不清。`command_blacklist` 与规则分开，`Prepare` 阶段比对 `Match` 和全部 `Parts` 里的连续词序列，命中直接报错。

## 权限分层

每一层的设置格式相同：`Settings{ApprovalPolicy, Rules}`，`Rules` 的四个字段是 `Allow`、`Escalate`、`Ask`、`Deny`。一个调用按这些层判定，从上到下（`account.Layers`，角色层由 `run/run.go` 放在最前）：

| 层 | 来源 | 存在哪 | 怎么改 |
| --- | --- | --- | --- |
| 角色 | `agent.Role.Own` | 代码里 | 不能改 |
| 部署 | `host.Config.Permissions` | 宿主的配置 | 改配置后重启 |
| 用户 | `account.Settings.Permissions` | `settings.permissions` | `settings/updatePermissions` |
| 工作区 | `account.Workspace.Settings` | `workspaces.settings` | `workspace/updatePermissions` |
| 会话 | `account.Thread.Settings` | `threads.settings` | `thread/updatePermissions` |

会话不在工作区里时没有工作区这一层。`policy.Resolve` 按顺序合并：策略取最后一个非空的，四组规则各自取并集去重；deny 先判定，所以下层能加规则，去不掉上层的 deny。`host.New` 给部署层补上默认策略 `on-request`。

层上还能限定工具（`policy.Layer` 的 `Providers`、`Without`，不存库），例如通用子 agent 去掉派生子 agent 和定时任务的工具。工具要每一层都留着（`policy.Kept`）、在宿主的 `Allowlist` 里、且没被不带说明符的 deny 去掉，才发给模型。子 agent 用自己的会话层和工作区：创建时从父会话拷贝一份会话设置和工作区（`run/tools.go` 的 `launch`），之后各管各的。修改由 `policy.Validate` 校验，失败返回 `policy.ErrInvalidSettings`（`-32602`）。

## 建议规则与"总是允许"

`suggest` 在询问时给出建议规则（`policy/rules.go`），按拆开的每个 `Part` 生成：

| 内容 | 建议 |
| --- | --- |
| 工具没有内容 | 工具名本身 |
| `git status --short` | `run_command(git status:*)`，第二个词像子命令时 |
| 单段命令（`pwd`）或敏感程序（`rm`、`mv`、`sudo`、`python3`…） | 命令原文 |
| 第二个词不像子命令 | `run_command(程序:*)` |
| 多个子命令 | 每个一条，去重 |
| 任一 `Part` 含 `*`，或看不清 | 整批不建议 |
| 全权调用，第一个词是代码解释器 | 不建议 |

敏感程序是 `rm`、`rmdir`、`mv`、`dd`、`chmod`、`chown`、`sudo`、`kill`、`pkill`、`killall`、`launchctl`、`crontab`、`python`、`python3`、`node`、`ruby`、`perl`、`osascript`、`expect`，`git` 接 `push`、`reset`、`clean`、`checkout`、`restore`、`rebase` 也算；代码解释器是 `sh`、`bash`、`zsh`、`dash`、`python`、`python3`、`node`、`ruby`、`perl`、`osascript`、`expect`。子命令的判断标准是 `^[a-z][a-z0-9_-]*$`；建议规则会再解析一次，确认匹配这次调用才给出，只有不是由 ask 规则触发的询问才带建议。

`acceptAlways` 经 `app/settings.go` 的 `allowAlways` 写入：在工作区里写工作区设置，不在工作区写会话设置；子 agent 也一样，写进它自己的工作区或会话设置。全权调用的建议规则写进 `escalate`（`allowAlways` 看 `asked.Escalated`），其余写进 `allow`；写入与协议修改走同一校验，和 `Decided` 同一事务，校验不过决定也不生效。

## 审批流程

模型回答里 `ToolCall` 和 `ApprovalAsked` 一次提交，这一轮让出槽位；网关从 feed 看到条目发 `item/toolCall/requestApproval`，界面回决定后 `app.Decide` 追加 `Decided`，这一轮重新可运行。`ApprovalAsked` 带 `Suggested`、`Escalated`，`Decided` 带 `Decision`、`By`（`conversation/entry.go`）；请求里有 `preparedExecution`、`suggestedRules`、`escalated`、`availableDecisions`，连接恢复时按提问时间重发，字段见[审批协议](/zh/integrate/protocol/approvals)。

`Approval.Decisions` 算可选决定：ask 规则触发时只有 `accept`、`decline`；没有建议规则（看不清、含 `*`、全权调用以代码解释器开头）时加 `acceptForSession`；其余再加 `acceptAlways`。`Decisions` 不看 `Escalated`，全权调用有建议规则时照样给"总是允许"，写进去的是 escalate 规则。

`acceptForSession` 不存额外状态，判定时扫会话日志（`allowedForConversation`）：工具相同、`Prepared` 逐字节相同、`Content.Text` 也相同就算相同，或者这次调用被同一次"本会话允许"的建议规则覆盖（`coveredBySuggestion`）；MCP 工具一次"本会话允许"放行它在这个会话里的每次调用。被拒绝后这一轮停止用工具，其他调用以 "skipped: the user declined …" 结束，等审批时插话按拒绝处理。决定写下后不再判定，工具按 `Prepared` 运行并核对摘要、路径与文件哈希（`tool/builtin/workspace/prepared.go`），不一致就不执行；决定只在调用还在等时接受，否则 `ErrNoSuchRequest`。

## 边界与已知问题

- **escalate 规则是直通。** 命中即运行，不看审批策略和是否申请全权，只有 deny 排在它前面；写它等于预先批准这一类调用。
- **`never` 档下全权不问。** 规则没有给出结论的调用一律运行，全权调用也包括在内，能拦住它们的只有 deny 规则，见[审批策略](#审批策略)。
- **看不清的命令只在有带说明符的规则时才问。** 工具上没有这类规则时结论落到审批策略，`on-request` 下沙箱内的命令直接运行。
- **沙箱不生效时 `on-request` 每条命令都问。** 免问依据是 `Prepared.Sandboxed`；本机 `full-access` 下 `Sandboxed` 恒为假。
- **MCP 工具只能整体放行或禁止。** 规则不能带说明符，只读标注又不被采信，`on-request` 下每次调用都问，见[权限与沙箱](/zh/engine/skills-mcp#权限与沙箱)。
- **批准之后改的规则管不到已批准的调用。** 判定只在调用写下时做一次。

## 代码位置

| 位置 | 职责 |
| --- | --- |
| ollupi `policy/rules.go` | 规则解析、`ruleSet.decide`、`suggest` 与敏感程序、子命令、代码解释器名单 |
| ollupi `policy/checker.go` | `Checker.Decide`、判定顺序、`needsFullAccess`、`coveredBySuggestion` |
| ollupi `policy/policy.go`、`policy/validate.go` | `Settings`、`Rules`（含 `Escalate`）、三档策略、`Layer`、`Kept`、`Resolve`；`Validate` |
| ollupi `account/account.go`、`agent/agent.go`、`host/host.go` | 各层、角色层、`Launchable`；部署层的默认策略与校验 |
| ollupi `run/run.go`、`run/tools.go` | `step.permit`；`decide` 把 `Plan.Sandboxed`、`Plan.Escalated` 交给 `policy` |
| ollupi `tool/builtin/workspace/command.go`、`prepared.go`、`claude.go` | 命令解析与黑名单、执行前核对、`claude` 的全权条件 |
| ollupi `conversation/entry.go`、`view.go`、`check.go` | `ApprovalAsked.Escalated`、`Approval.Decisions`、追加检查 |
| ollupi `app/turns.go`、`app/settings.go`、`gateway/protocol.go`、`gateway/wire.go`、`gateway/server.go` | `Decide`、`Requests`、`allowAlways` 的 escalate 分支；`ApprovalRequestParams.escalated` 与请求发送 |
