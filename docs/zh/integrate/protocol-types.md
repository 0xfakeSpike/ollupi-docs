# 协议类型索引

网关契约 `protocol.schema.json` 的全部 166 个命名类型（`$defs`），以及讲它们的模块页。字段、取值和例子在模块页里；所有模块共用的约定（可选字段、时间、ID）见[通用约定](/zh/integrate/protocol#通用约定)。

只做参数包装、字段很少的类型（如 `ThreadRenameParams`）在模块页对应方法的参数表里讲，这里按模块登记归属。契约名和 Go 名不同的由生成器的 `defNames` 改名：`PermissionSettings`（`policy.Settings`）、`AgentRole`（`agent.Name`）、`WorkspaceProviders`（`account.Providers`）、`PreparedExecution`（`workspace.Prepared`）、`UserInputRequest`（`ask.Request`）、`HubWorkspace`（`hub.Workspace`）；两个类型撞名时生成器直接失败，要求在 `defNames` 里给其中一个写名字。见[契约的生成与测试](/zh/integrate/protocol#契约的生成与测试)。

## 握手（总览页）

| 类型 | 见 |
|---|---|
| `ClientInfo`、`InitializeParams`、`InitializeResult`、`ServerInfo` | [网关协议](/zh/integrate/protocol#握手) |
| `Empty` | [网关协议](/zh/integrate/protocol#握手)；空对象，用作没有参数的方法的参数和没有结果的方法的结果 |

## 会话

| 类型 | 见 |
|---|---|
| `ThreadStartParams` | [thread/start](/zh/integrate/protocol/threads#thread-start) |
| `ThreadPageParams`、`ThreadPageResult` | [thread/read 和 thread/resume](/zh/integrate/protocol/threads#thread-read-和-thread-resume) |
| `ThreadListParams`、`ThreadListResult` | [thread/list](/zh/integrate/protocol/threads#thread-list) |
| `ThreadRenameParams` | [thread/rename](/zh/integrate/protocol/threads#thread-rename) |
| `ThreadMarkReadParams` | [thread/markRead](/zh/integrate/protocol/threads#thread-markread) |
| `ThreadArchiveParams` | [thread/archive](/zh/integrate/protocol/threads#thread-archive) |
| `ThreadDeleteParams` | [thread/delete](/zh/integrate/protocol/threads#thread-delete) |
| `ThreadChangedNotification` | [thread/changed](/zh/integrate/protocol/threads#thread-changed) |
| `ThreadRow` | [ThreadRow](/zh/integrate/protocol/threads#threadrow)；`thread/list` 和 `thread/changed` 的行 |
| `ThreadStatus` | [会话状态](/zh/integrate/protocol/threads#会话状态) |
| `ThreadCursor` | [thread/list](/zh/integrate/protocol/threads#thread-list) 的 `after` |
| `ThreadResult` | [thread/start](/zh/integrate/protocol/threads#thread-start)；`thread/start`、`rename`、`markRead`、`archive`、`updatePermissions` 的结果 `{thread}` |

## 一轮与条目

| 类型 | 见 |
|---|---|
| `TurnStartParams` | [turn/start](/zh/integrate/protocol/turns#turn-start) |
| `TurnSteerParams`、`TurnSteerResult` | [turn/steer](/zh/integrate/protocol/turns#turn-steer) |
| `TurnInterruptParams` | [turn/interrupt](/zh/integrate/protocol/turns#turn-interrupt) |
| `AttachmentReadParams`、`AttachmentReadResult` | [attachment/read](/zh/integrate/protocol/turns#attachment-read) |
| `TurnStatus` | [一轮的状态](/zh/integrate/protocol/turns#一轮的状态) |
| `TurnRow`、`TurnResult`、`AgentRole` | [TurnRow](/zh/integrate/protocol/turns#turnrow) |
| `Usage` | [Usage](/zh/integrate/protocol/turns#usage)；一轮和一次模型回复各带一份 |
| `ItemKind`、`ItemStatus` | [条目](/zh/integrate/protocol/turns#条目) |
| `ItemRow` | [ItemRow](/zh/integrate/protocol/turns#itemrow) |
| `Result`、`Artifact` | [Result 和 Artifact](/zh/integrate/protocol/turns#result-和-artifact) |
| `Attachment` | [Attachment](/zh/integrate/protocol/turns#attachment) |
| `ResponseRow` | [ResponseRow](/zh/integrate/protocol/turns#responserow) |
| `ContextStats`、`MemoryStats` | [ContextStats](/zh/integrate/protocol/turns#contextstats) |
| `UserInput` | [UserInput](/zh/integrate/protocol/turns#userinput)；条目上等回答时的内容 |
| `TurnChangedNotification` | [turn/changed](/zh/integrate/protocol/turns#turn-changed) |
| `ItemChangedNotification` | [item/changed](/zh/integrate/protocol/turns#item-changed) |
| `DeltaNotification` | [通知的包装](/zh/integrate/protocol/turns#通知的包装) |
| `ErrorNotification` | [error](/zh/integrate/protocol/turns#error) |

## 审批与提问

| 类型 | 见 |
|---|---|
| `ApprovalRequestParams`、`Approval` | [ApprovalRequestParams](/zh/integrate/protocol/approvals#approvalrequestparams) |
| `ApprovalResponse`、`Decision` | [ApprovalResponse](/zh/integrate/protocol/approvals#approvalresponse) |
| `FileChange`、`PreparedExecution`、`Input` | [审批的内容](/zh/integrate/protocol/approvals#filechange) |
| `UserInputRequestParams`、`UserInputRequest` | [UserInputRequestParams](/zh/integrate/protocol/approvals#userinputrequestparams) |
| `UserInputQuestion`、`UserInputOption` | [UserInputQuestion](/zh/integrate/protocol/approvals#userinputquestion) |
| `UserInputResponse`、`UserInputAnswer`、`UserInputAnswers` | [UserInputResponse](/zh/integrate/protocol/approvals#userinputresponse) |

## 权限

| 类型 | 见 |
|---|---|
| `ApprovalPolicy` | [ApprovalPolicy](/zh/integrate/protocol/permissions#approvalpolicy) |
| `PermissionRules` | [PermissionRules](/zh/integrate/protocol/permissions#permissionrules) |
| `PermissionSettings` | [PermissionSettings](/zh/integrate/protocol/permissions#permissionsettings) |
| `ThreadPermissionsParams`、`WorkspacePermissionsParams`、`SettingsPermissionsParams` | [权限](/zh/integrate/protocol/permissions) |

## 工作区与执行环境

| 类型 | 见 |
|---|---|
| `WorkspaceAddParams`、`WorkspaceRenameParams`、`WorkspaceMoveParams`、`WorkspaceArchiveParams`、`WorkspaceListResult`、`WorkspaceResult` | [工作区的方法](/zh/integrate/protocol/workspaces#工作区的方法) |
| `WorkspaceRow` | [WorkspaceRow](/zh/integrate/protocol/workspaces#workspacerow) |
| `WorkspaceKind` | [工作区的种类](/zh/integrate/protocol/workspaces#工作区的种类) |
| `WorkspaceSetKindParams` | [workspace/setKind](/zh/integrate/protocol/workspaces#workspace-setkind) |
| `WorkspaceInstructionsParams` | [workspace/updateInstructions](/zh/integrate/protocol/workspaces#workspace-updateinstructions) |
| `WorkspaceProvidersParams`、`WorkspaceProviders` | [workspace/updateProviders](/zh/integrate/protocol/workspaces#workspace-updateproviders)；`WorkspaceProviders` 是 `{enabled?, disabled?}` |
| `EnvironmentAddParams`、`EnvironmentRenameParams`、`EnvironmentDeleteParams`、`EnvironmentResult`、`EnvironmentListResult`、`EnvironmentChangedNotification` | [执行环境的方法](/zh/integrate/protocol/workspaces#执行环境的方法) |
| `EnvironmentRow` | [EnvironmentRow](/zh/integrate/protocol/workspaces#environmentrow) |
| `EnvironmentKind` | [EnvironmentKind](/zh/integrate/protocol/workspaces#environmentkind) |

## 模型、工具与 MCP

| 类型 | 见 |
|---|---|
| `Model`、`ModelListResult` | [model/list](/zh/integrate/protocol/models-tools#model-list) |
| `ToolDescriptor`、`ToolListResult` | [tool/list](/zh/integrate/protocol/models-tools#tool-list) |
| `MCPServerConfig` | [mcpServer/set](/zh/integrate/protocol/models-tools#mcpserver-set) |
| `MCPServer`、`MCPServerStatus`、`MCPServerListResult`、`MCPServerDeleteParams`、`MCPServerChangedNotification` | [模型、工具与 MCP](/zh/integrate/protocol/models-tools) |
| `Annotations`、`Plan`、`PlanStep`、`PlanStepStatus`、`CommandOutput`、`FileOutput`、`ReadFile`、`ReadFileOutput`、`Glob`、`GlobOutput`、`Grep`、`GrepOutput`、`GrepFile`、`GrepLine` | [内置工具的参数和输出](/zh/integrate/protocol/models-tools#内置工具的参数和输出) |
| `SubagentCall` | [SubagentCall](/zh/integrate/protocol/models-tools#subagentcall) |
| `SubagentLaunched` | [SubagentLaunched](/zh/integrate/protocol/models-tools#subagentlaunched) |

## 定时任务

| 类型 | 见 |
|---|---|
| `CronCreateParams`、`CronPauseParams`、`CronDeleteParams`、`CronJobRow`、`CronListParams`、`CronListResult`、`CronResult`、`CronChangedNotification` | [定时任务](/zh/integrate/protocol/cron) |

## 记忆

`Kind`、`Scope`、`Status`、`FailureCode` 四个枚举属记忆，契约名没有 `Memory` 前缀。

| 类型 | 见 |
|---|---|
| `MemoryRow` | [MemoryRow](/zh/integrate/protocol/memory#memoryrow) |
| `MemoryReference` | [MemoryReference](/zh/integrate/protocol/memory#memoryreference) |
| `MemorySource` | [MemorySource](/zh/integrate/protocol/memory#memorysource) |
| `MemoryStatus` | [MemoryStatus](/zh/integrate/protocol/memory#memorystatus) |
| `MemoryFailure`、`MemorySkip`、`MemoryForgetParams`、`MemoryListParams`、`MemoryListResult`、`MemoryMoveParams`、`MemoryResult`、`MemoryUpdateParams`、`Kind`、`Scope`、`Status`、`FailureCode` | [记忆](/zh/integrate/protocol/memory) |

## 搜索

| 类型 | 见 |
|---|---|
| `SearchParams` | [搜索](/zh/integrate/protocol/search) |
| `SearchResult` | [SearchResult](/zh/integrate/protocol/search#searchresult) |
| `MessageHit` | [MessageHit](/zh/integrate/protocol/search#messagehit) |

## 设置

| 类型 | 见 |
|---|---|
| `SettingsRow` | [设置](/zh/integrate/protocol/settings#类型-settingsrow)；也是 `settings/changed` 的载荷 |
| `SettingsUpdateParams` | [设置](/zh/integrate/protocol/settings) |

## 待办

| 类型 | 见 |
|---|---|
| `TodoListParams`、`TodoListResult` | [todo/list](/zh/integrate/protocol/todos#todo-list) |
| `TodoAddParams` | [todo/add](/zh/integrate/protocol/todos#todo-add) |
| `TodoUpdateParams` | [todo/update](/zh/integrate/protocol/todos#todo-update) |
| `TodoResult` | [todo/changed](/zh/integrate/protocol/todos#todo-changed)；`todo/add`、`todo/update` 的结果 |
| `TodoRow` | [TodoRow](/zh/integrate/protocol/todos#todorow)；`id` 是整数，其他 ID 是字符串 |
| `TodoStatus` | [概念与状态](/zh/integrate/protocol/todos#概念与状态) |

## 用量

| 类型 | 见 |
|---|---|
| `UsageQueryParams`、`UsageQueryResult` | [usage/query](/zh/integrate/protocol/usage#usage-query) |
| `UsageRow` | [一行是什么](/zh/integrate/protocol/usage#一行是什么) |
| `UsageGroup` | [三种分组](/zh/integrate/protocol/usage#三种分组) |

## 中枢工具

这十六个类型是 hub 工具的参数和输出，只出现在工具描述里，不经过网关方法。工具本身见[中枢](/zh/engine/hub#工具)。

| 类型 | 见 |
|---|---|
| `HubWorkspaces`、`HubWorkspace` | [list_workspaces](/zh/engine/hub#工具) |
| `HubStartConversation`、`HubMessageSent` | [start_conversation](/zh/engine/hub#工具) |
| `HubSendMessage` | [send_message](/zh/engine/hub#工具) |
| `HubListConversations`、`HubConversations`、`HubConversation` | [list_conversations](/zh/engine/hub#工具) |
| `HubReadConversation`、`HubTurns`、`HubTurn`、`HubMessage`、`HubTurnEnded`、`End` | [read_conversation](/zh/engine/hub#工具)；`End` 是轮次怎么结束：`completed`、`failed`、`interrupted` |
| `HubTodo`、`HubTodoStatus` | [add_todo、update_todo、list_todos](/zh/engine/hub#工具)；比 `TodoRow` 窄，字段名是 `workspace`、`conversation`、`created` |

::: info 演进
这一页原先列 134 个类型。中枢的十五个 `Hub*`、待办的七个、用量的四个、工作区的五个和 `End` 后来进入契约，共 166 个；旧的 `HubAddTodo`、`HubListTodos`、`HubUpdateTodo`、`HubTodos` 四个已不在契约里。
:::

## 代码位置

| 仓库 | 路径 | 职责 |
|---|---|---|
| ollupi | `gateway/protocol.go` | 方法、通知、参数和结果类型 |
| ollupi | `gateway/wire.go` | 发给客户端的行：`ThreadRow`、`ItemRow`、`WorkspaceRow`、`TodoRow` 等 |
| ollupi | `gateway/schema_test.go` | `defNames` 改名表；生成 `protocol.schema.json` 并校验枚举 |
| ollupi | `tool/builtin/hub/hub.go` | hub 工具的参数和输出 |
