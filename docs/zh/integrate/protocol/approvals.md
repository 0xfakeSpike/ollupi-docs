# 审批与提问

agent 要做一件需要用户点头的事，或者要用户回答一个问题时，网关向客户端发一个 JSON-RPC 请求，客户端回结果。这一页讲这两种服务端请求：什么时候发、怎样回复、各种回复的结果。

哪些调用要问由策略和规则决定，见[权限](/zh/integrate/protocol/permissions)；条目（`ItemRow`）字段见[一轮与条目](/zh/integrate/protocol/turns#itemrow)；客户端怎样保存待回答的请求，见[写一个客户端](/zh/integrate/client#审批和提问)。

## 为什么这样设计

等待只是日志里的一条记录，所以客户端断开很久再回来，请求还在，重新问一遍即可。回答也先写进日志，两条连接同时回答时先写进去的生效。「总是允许」要写什么规则由网关算好放在 `suggestedRules` 里。

## 概念与状态

两种等待都落在一条 `toolCall` 条目上：审批是 `pending` 且 `approval` 没有 `decision`，提问是 `inProgress` 且 `input.answered` 为 `false`。这一轮随之停下、让出槽位（slot），只剩日志里的记录；会话状态分别是 `waitingOnApproval` 与 `waitingOnUserInput`，请求方法分别是 `item/toolCall/requestApproval` 与 `item/tool/requestUserInput`，条目细节见[一轮与条目](/zh/integrate/protocol/turns#itemrow)。

同一次提交里有几个要问的调用时，请求一起发出，全部有了决定这一轮才继续。子 agent 的请求照样发给客户端，`threadId` 是子 agent 自己的会话，父会话状态同样是这两个值，见[会话状态](/zh/integrate/protocol/threads#会话状态)。

## 典型流程

### 审批一次调用

模型要调用非只读的 `deploy`，策略是适中（`on-request`）：条目先以 `pending` 出现并带着没有 `decision` 的 `approval`，同一次提交里 `item/changed` 之后紧跟着请求。命令的请求还带 `content` 和 `preparedExecution`；申请全权（full access）的调用带 `escalated: true`，执行内容里有 `escalated` 和模型给的理由 `justification`。`reason` 有两种来源：ask 规则触发（`Your permission rule ... asks before this call.`），或命令看不清、没法逐条对照规则。

回复 `{"decision": "accept"}` 之后 `approval.decision` 有值，条目变 `inProgress`，执行完 `completed`，`approval` 多出 `decidedBy`（回答者，单令牌部署是 `default`）与 `decidedAt`。

### 回答一个提问

模型问用哪种语言：条目从 `pending` 变 `inProgress`，带上 `input`。客户端回 `{"answers": {"lang": {"answers": ["Go"]}}}` 之后条目直接 `completed`，`input.answered` 为 `true`，答案原样成为 `result.output`，会话状态回到 `active`。

### 跳过与拒绝

跳过是回 `{"answers": {}, "skipped": true}`（带 `skipped` 时 `answers` 被忽略），拒绝是回 `decline`。两种都以 `declined` 结束，`error` 分别是 `the user skipped these questions; go on without their answers` 与 `the user declined this call`（后者 `approval.decision` 为 `decline`）。随后写一条 `notice`（`[runtime] Tool use has stopped: …`），模型读到后写最终回答，`turn/changed` 为 `completed` 而不是 `failed`。拒绝结束的只是这一轮的工具调用：模型之后仍然要调工具时，这次调用失败，这一轮以 `failed` 结束。

### 用一条消息代替回答

这一轮在等审批或提问时，用户直接发消息（`turn/steer`），这条消息就代替了回答：审批条目 `declined`，`error` 是 `the user declined this call`；提问条目也 `declined`，`error` 是 `the user skipped these questions; go on without their answers`；`decidedBy` 是发消息的用户。

之后再回复那条请求只会收到 `error` 通知（`the conversation does not wait on that request`）。这里没有「工具调用已停止」的 `notice`：模型读到被拒的结果和新消息，可以接着用工具，见[执行模型](/zh/engine/execution)。

## 请求

### item/toolCall/requestApproval

方向是服务端 → 客户端，参数是 [`ApprovalRequestParams`](#approvalrequestparams)，回复是 [`ApprovalResponse`](#approvalresponse)（`{"decision": "<Decision>"}`）。回复之后网关发 `thread/changed`、`item/changed`；选 `acceptAlways` 且规则写进工作区时同一次提交里还有 `workspace/changed`。

`availableDecisions` 由 `conversation.Approval.Decisions` 算出：`approval.rule` 非空（ask 规则触发）时只有 `accept`、`decline`；没有建议规则（命令看不清、含 `*`，或全权调用以代码解释器开头）时多一个 `acceptForSession`；有建议规则时四种都有。它不看 `escalated`：申请全权的调用只要有建议规则，一样给 `acceptAlways`，写入 escalate 规则。

| 决定 | 效果 |
|---|---|
| `accept` | 只放行这一次 |
| `acceptForSession` | 本会话内同工具的调用不再问：执行内容逐字节相同，或能被这条审批建议的规则覆盖到；申请全权的调用只被 escalate 规则覆盖（`policy/checker.go` 的 `coveredBySuggestion`） |
| `acceptAlways` | 把 `suggestedRules` 并进规则再放行：申请全权的调用写进 escalate，其余写进 allow；会话属于工作区时写进工作区那一层，否则写进会话那一层（`app/settings.go` 的 `allowAlways`） |
| `decline` | 条目 `declined`，这一轮停止用工具 |

`decision` 不在 `availableDecisions` 里时，引擎返回 `invalid decision: … is not one of …`，网关发 `error` 通知并立刻重发，见[回复的结果](#回复的结果)。

### item/tool/requestUserInput

方向是服务端 → 客户端，参数是 [`UserInputRequestParams`](#userinputrequestparams)，回复是 [`UserInputResponse`](#userinputresponse)：`{"answers": {"<问题 id>": {"answers": ["..."]}}}`，或 `{"answers": {}, "skipped": true}`。回复之后发 `thread/changed`、`item/changed`。

问题的约束：1 到 4 个；`id` 匹配 `^[a-z][a-z0-9_]{0,63}$` 且不重复；`header` 1 到 12 字符；`question` 1 到 600 字符；`options` 至多 4 个，`label` 1 到 60 字符，`description` 至多 200 字符。工具说明要求模型把推荐项放第一个、在 `label` 后加 ` (Recommended)`、不加「其他」选项，所以客户端应当总是允许用户写自己的答案。

引擎校验回复（`ask.Request.Check`）：每个问题至少一个非空回答，不能回答没问过的问题，合计不超过 4000 字符，不通过时 `message` 写明哪一条。答案可以是选项的 `label`，也可以是用户写的文字。

## 回复的结果

| 客户端 | 网关 | 之后 |
|---|---|---|
| 合法的 `result` | 写进日志，发 `thread/changed`、`item/changed` | 这一轮可以继续 |
| `result` 解析不了、有契约之外的字段，或决定、答案不合法 | 发 `error` 通知，带 `threadId`、`turnId`、`itemId` 和原因 | 立刻用新的 `id` 重发同一个请求 |
| 请求已经失效：这一轮被中断、被插话代答，或别处已经回答 | 发 `error` 通知，`message` 是 `the conversation does not wait on that request` | 不再重发 |
| JSON-RPC 错误回复 | 什么也不做，这条连接忘掉它问过 | 这一轮继续等；下一次 `thread/resume`、重连或条目再有变化时重发 |
| 不回复就断开 | 请求留在日志里 | 新连接 `initialize` 之后重发 |

回复的 `result` 严格解码，多余字段算不合法；反复回同样的内容会和网关来回打转，收到 `error` 通知应当停下。载荷 `ErrorNotification` 有 `threadId`、`turnId`、`itemId`、`message`，见[一轮与条目](/zh/integrate/protocol/turns#error)。这两种请求总伴随 `thread/changed`、`item/changed` 和 `error`，规则写进工作区时还有 `workspace/changed`。

## 重发

服务端请求的 `id` 是 JSON 数字，每条连接从 1 开始单独计数；网关按 `id` 的原始 JSON 文本找对应的请求，所以回复要原样带回。

同一个条目在一条连接上同一时刻只问一次：网关记着这条连接问过、还没收到回复的条目，回复到了才清掉（`conn.asked`）。发请求的时机有四种：一次提交让某个调用开始等用户时，发这条连接还没问过的在等调用；`initialize` 的回复入队之后，发这个用户所有在等的请求（包括子 agent 的，按发起时间排序，读不出来时以 1011 `pending requests could not be read` 关闭连接）；`thread/resume` 的回复之后，发这个会话和它的子 agent 会话里在等的请求，已经问过的不再发；回复不合法之后，同一个请求立刻重发，`id` 是新的。

所以同一个条目的请求会带着不同的 `id` 来好几次。客户端应以 `itemId`（审批另有 `approvalId`）为键保存待回答的请求，新来的替换旧的，回复时用最新的 `id`，见[写一个客户端](/zh/integrate/client#审批和提问)。一个用户最多四条连接，各自收到每个请求、各自计数 `id`；哪条先给出合法的回复就以它为准，别条随后收到 `item/changed`，再回复只会得到 `error` 通知。

网关不撤回请求，也没有「请求作废」的通知。失效只能从条目的变化看出来：另一条连接或宿主批准了（`approval.decision` 有值，执行完才 `completed`）、拒绝了（`declined`）、别处回答或跳过了提问（`completed` 或 `declined`）、这一轮被中断（条目 `declined`，审批是 `interrupted by the user`，提问按跳过记下，`turn/changed` 为 `interrupted`），或用户插话代答（`declined`，见[上文](#用一条消息代替回答)）。

## 类型

`?` 表示字段可能不出现。

### ApprovalRequestParams

`threadId`、`turnId`、`itemId`（子 agent 的审批是子 agent 会话）、`approvalId`（等于条目上 `approval.approvalId`）、`server`、`tool`、`arguments`（条目上没有参数时是 `{}`），可选的 `preparedExecution`（判定时算出的执行内容，审批的就是它）、`reason`、`content`（规则匹配的内容，比如命令行）、`suggestedRules`（选 `acceptAlways` 时写入的规则）、`escalated`（申请全权，为 `true` 时「总是允许」写进 escalate），以及 `availableDecisions`。

### ApprovalResponse

只有 `decision`，取值 `accept`、`acceptForSession`、`acceptAlways`、`decline`，必须是 `availableDecisions` 之一，含义见[上文](#item-toolcall-requestapproval)。

### Approval

条目上的审批记录：`approvalId`、`reason?`、`content?`、`suggestedRules?`、`escalated?`、`availableDecisions`、`askedAt` 与请求同名同值，另有 `rule?`（触发询问的 ask 规则，有它时只能 `accept` 或 `decline`）、`decision?`（不出现表示还在等）、`decidedBy?`（用户 ID）、`decidedAt?`。

### Input

条目上的提问记录：`request`（与请求里的 `questions` 相同）、`askedAt`、`answered`；答案在条目的 `result.output` 里，跳过时没有。

### PreparedExecution

判定时算出的执行内容，出现在请求和条目上，只有工作区的命令和改文件工具有；它和调用一起写进日志，之后不再改变，执行前工具重新核对，见[工具系统](/zh/engine/tools)。字段：`cwd`、`settingsDigest`（沙箱设置、超时、命令黑名单和根目录的摘要）、`argumentsDigest`、`program?`、`args?`、`env?`、`timeoutSec?`、`sandboxed?`、`escalated?`、`justification?`、`files?`（[`FileChange`](#filechange)[]）。

### FileChange

界面用它显示 diff：`path`（在工作区里时相对工作区根目录，客户端接到工作区现在的 `rootPath` 上，否则绝对路径）、`before?`（原内容的 **sha256**，新建文件时没有）、`after`（新内容的 sha256）、`diff`（unified diff）、`added`、`removed`（增删的行数）。

### UserInputRequestParams

`threadId`、`turnId`、`itemId` 指向这个 `request_user_input` 调用，`questions` 和条目上 `input.request.questions` 相同。`UserInputRequest` 只有 `questions` 一个字段，它也是工具的参数。

### UserInputQuestion

`id`（回答时用它对应问题）、`header`（短标签）、`question`（正文）、`options?`（互斥选项，每项是 `label` 加可选的 `description`，`label` 也是选它时的回答）。

### UserInputResponse

`answers` 以问题 `id` 为键，值是 `UserInputAnswer`（只有 `answers`：string[]）；`skipped?` 为 `true` 表示跳过，这时 `answers` 被忽略，传 `{}` 即可。整个 `answers` 对象原样成为条目的 `result.output`。

## 错误与边界

- **请求不撤回。** 请求失效只能从条目的变化看出来，见[重发](#重发)。
- **不合法的回复会立刻重发。** 反复回同样内容会和网关来回打转，遇到 `error` 通知应当停下。
- **插话代答只对当前一轮在等的调用生效。** 回答完在等子 agent 时插话，子 agent 正在等的审批不受影响。
- **「本会话允许」认两件事。** 执行内容逐字节相同的调用，和被建议规则覆盖到的调用；后半条对申请全权的调用只认 escalate 规则。沙箱配置变了，执行内容跟着变，旧的批准不再适用。
- **看不出是哪个客户端回答的。** `decidedBy` 只是用户 ID。

## 代码位置

| 仓库 | 路径 | 职责 |
|---|---|---|
| ollupi | `gateway/server.go` | `change`、`request`、`requests`、`resolve`：发请求、记已问过的条目、处理回复与重发 |
| ollupi | `gateway/protocol.go`、`gateway/wire.go` | 两种请求的参数与回复；条目上的 `Approval`、`Input` |
| ollupi | `pkg/jsonrpc/jsonrpc.go` | 服务端请求的 `id` 计数与回复匹配 |
| ollupi | `app/turns.go` | `Requests`、`Decide`、`Answer`、插话 `Steer` |
| ollupi | `app/settings.go` | `allowAlways`：建议规则写进会话或工作区，`asked.Escalated` 时写 escalate |
| ollupi | `conversation/view.go` | `Approval.Decisions`、`WaitsForApproval`、`WaitsForInput` |
| ollupi | `policy/checker.go`、`policy/rules.go` | 判定、`suggest` 建议规则、`coveredBySuggestion` |
| ollupi | `ask/ask.go`、`tool/builtin/workspace/plan.go` | 提问的类型、约束和 `Check`；`Prepared` 与 `FileChange` |
