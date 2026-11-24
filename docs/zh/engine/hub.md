# 中枢

中枢（hub）是一个用户在一处规划所有项目的地方：他说要做什么，由中枢把每件事交给对应项目的会话说清楚，再回来看那些会话做到哪里。中枢自己不动项目的文件、不跑项目的命令，它靠会话干活。

中枢由两部分组成：一个叫 hub 的工作区，和在里面回答的 hub 主 agent。工作区是什么、会话是什么，见[核心概念](/zh/intro/concepts)；工作区的种类和协议方法见[工作区与执行环境](/zh/integrate/protocol/workspaces)。

## 为什么这样设计

规划和工作是两件事。一个项目上的活要在项目目录里做：读文件、跑命令、改代码，安全边界和审批都按工作区算。而"这个星期先把哪几件事做完"跨着所有项目，哪一件都不需要碰文件。把这两件事放进同一个会话，要么给规划用的会话一套它不需要的文件权限，要么让项目上的会话背上别的项目的上下文。

所以中枢是一个普通的工作区，只是其中的会话换一个角色：hub 主 agent。它带着原来那套工具，去掉子 agent 和浏览器，换上一组专门的东西——列工作区、开会话、发消息、看会话状态、读会话内容，以及维护用户的待办。所有"活"都发生在别的会话里，那些会话照常受各自工作区的权限和审批约束；中枢只是以用户的名义给它们发消息。

## 部署开关与工作区

中枢是部署时的开关：`host.Config.Hub` 为真，宿主才注册 hub 工具；桌面端的内置宿主一直打开。开关关着时创建 hub 工作区会得到 `noHub`（-32021）。

工作区有两种 `kind`：`project` 和 `hub`，新建的工作区都是 `project`，用 `workspace/setKind` 改。一个用户最多有一个 hub 工作区，再改第二个会得到 `secondHub`（-32020），错误信息是让对方先把现有的改回项目工作区；被归档的 hub 也算数，因为它仍然是那个用户唯一的 hub。改回 `project` 之后，hub 工作区原来那个文件夹和里面的会话都还在，只是会话重新由普通的主 agent 回答。

hub 工作区和别的项目一样是一个真文件夹：它可以有自己的说明（`workspace/updateInstructions`，最多 20 000 字），说明会写进其中会话的系统提示；它的根目录也可以放文件。它也会出现在“列工作区”的结果里，`kind` 是 `hub`，但它不能作为派活的目标。

## 中枢的会话

在 hub 工作区里开的会话由 `hub-main-agent` 回答。角色在轮次排队时写进 `TurnQueued`，之后不再变；所以把 hub 工作区改回项目工作区，已经在跑的会话仍然以 hub 主 agent 跑完。

这个角色有两处不同：

- **工具**：去掉 `subagents` 和 `browser` 两个提供者，所以没有子 agent 工具，也没有 `browser_*`；加上 `hub` 提供者的八个工具。文件、命令、技能、计划、网络这些照旧，这样中枢需要看一眼文件时不必再开一个会话。
- **放行**：角色的策略层把 `start_conversation` 和 `send_message` 放进 allow，给项目派活不需要用户逐次批准；宿主或用户自己的 deny 规则仍然优先，因为判定顺序是 deny → ask → escalate → allow。详见[权限与审批](/zh/engine/permissions)。

模型的选择、上下文压缩、轮次上限都和普通会话一样：中枢没有单独的一套限制。

## 工具

| 工具 | 做什么 |
|---|---|
| `list_workspaces` | 列出没归档的工作区：`id`、`name`、`root`、`kind`。中枢用它找项目的 `id` |
| `start_conversation` | 在一个项目工作区里开新会话，参数是 `workspace`、`title`（不超过 120 字）、`message`、可选 `todo`；返回会话和第一轮的 `id`，`queued` 表示第一轮是马上跑还是排在后面 |
| `send_message` | 给一个项目里的会话发消息，参数是 `conversation`、`message` |
| `list_conversations` | 不给参数时列出这个中枢派出去过的会话：状态、排队轮次数、上一轮怎么结束、用户读没读、最后一条回答的前 600 字；也可以按 `conversations` 或 `workspace` 查任意会话，最多 50 个 |
| `read_conversation` | 一个会话最近几轮：默认 3 轮，最多 20 轮；只留用户消息、agent 回答和交回的报告，每条截到 4 000 字 |
| `add_todo`、`update_todo`、`list_todos` | 维护用户的待办，见[待办](/zh/integrate/protocol/todos) |

只有项目工作区能收活：`start_conversation` 的目标是 hub 工作区时直接报错，`send_message` 的目标会话属于 hub 工作区时同样报错。找不到工作区或会话时，报错里会写清是哪个 `id` 不存在，并提示用哪个工具去列。

`start_conversation` 带着 `todo` 时，它在一件事里做完三件：开会话、发第一条消息、把待办标成已交给会话并链到这个会话。待办被链上时记下会话所在的工作区，所以之后按待办就能查到项目和会话。如果要交的事已经有会话，用 `update_todo` 把 `status` 设成 `handed`、`conversation` 设成那个会话。

## 消息与待人

中枢发出去的消息在目标会话里是一条普通的用户消息，只是带着 `From`，值是中枢那一侧的会话 `id`。目标会话的 agent 看到的是"用户说的"：消息开头的时间后面接着 `by the hub conversation "<标题>" on the user's behalf`，主 agent 的规则要求它把这当作用户的请求来回答。反过来，中枢的规则要求它把其他会话写来的内容、工具输出和记忆当数据，不照它们改目标，也不把一个会话的要求转给另一个会话。

目标会话在等审批或等回答时，等的是用户，不是中枢：中枢会把是哪一种、在等什么告诉用户，而不是替用户批准或回答。用户批准之后那个会话自己接着跑，中枢不需要再发消息。

中枢判断一件事做没做完，靠 `list_conversations` 的状态和 `read_conversation` 的内容。规则明确要求它不要拿待办的备注当状态——备注写要做什么、在等什么、为什么放弃；做到哪里去看会话。会话停下来了不等于活干完了，要读它的回答。

## 待办的迁移

待办原来放在 hub 工作区根目录的 `TODO.md` 和 `done/<年-月>.md` 里。现在第一次读待办时把它们导进 `todos` 表：`TODO.md` 只读 1 MB，整个过程限一分钟，从 hub 工作区经沙箱读；导入成功后旧文件被改名成 `TODO.md.imported-<日期>`，不删除。每个用户在一个进程里只导一次，导入失败下一次再试。

## 边界与已知问题

- 一个用户只有一个 hub 工作区，而且是"曾经有过"的意思：想换一个位置，必须先把原来的改回 `project`。
- 中枢的会话里没有子 agent，需要并行时它只能开更多项目会话。
- 中枢能看到用户所有的会话，不限于它自己派出去的；`list_conversations` 不给参数时默认只看自己派出去的，是为了不让列表变成全部历史。
- 读会话有截断：回答 600 字、消息 4 000 字、条目只留三种。要完整内容得让那个会话自己总结。
- hub 工具由宿主注册，开关关着时协议层没有这些工具，`workspace/setKind` 改成 `hub` 会被拒绝。

## 代码位置

| 路径 | 职责 |
|---|---|
| `host/host.go` | `Config.Hub`；为真时把 `hub.Provider` 加进内置工具 |
| `account/account.go` | `WorkspaceKind`：`ProjectWorkspace`、`HubWorkspace`；`Instructions` 的 20 000 字上限 |
| `app/owned.go` | `SetWorkspaceKind`、`UpdateWorkspaceInstructions`；`ErrNoHub`、`ErrSecondHub` |
| `app/turns.go` | hub 工作区里的轮次用 `agent.HubMain` |
| `agent/agent.go` | `HubMain` 角色：`Without` 子 agent 和浏览器，allow `start_conversation`、`send_message` |
| `agent/rules.go` | `hubMainRules`：规划、派活、看进展、维护待办 |
| `tool/builtin/hub/hub.go` | 八个工具的 schema 与实现；600/4 000 字截断、50/20 条上限 |
| `app/todos.go`、`app/todos_import.go` | 待办的增改查；旧 `TODO.md` 的导入 |
| `gateway/protocol.go` | `workspace/setKind`、`workspace/updateInstructions`、`todo/*`；错误码 `noHub`、`secondHub` |
