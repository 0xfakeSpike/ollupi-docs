# 协议类型索引

网关契约 `protocol.schema.json` 的全部 134 个命名类型（`$defs`，引擎 v0.17.1），以及讲它的模块页。字段、取值和例子在模块页里；所有模块共用的约定（可选字段、时间、ID）见[通用约定](/zh/integrate/protocol#通用约定)。

只做参数包装的类型（如 `ThreadRenameParams`）字段很少，模块页在对应方法的参数表里讲，没有单独的标题。几个类型的契约名和 Go 名不同，由生成器的 `defNames` 改名：`PermissionSettings`（`policy.Settings`）、`AgentRole`（`agent.Name`）、`PreparedExecution`（`workspace.Prepared`）、`UserInputRequest`（`ask.Request`）等，见[一张表分发和生成 schema](/zh/integrate/protocol#一张表分发和生成-schema)。

::: info 演进
v0.12.1 的契约有 129 个类型。之后删掉的有 `AttachmentKind`、`Await`、`AwaitBy`、`ContextArtifact`、`CronJobView`、`ItemNotification`、`ItemType`、`MemoryFailureCode`、`MemoryReport`、`MemoryRowStatus`、`MemoryScope`、`Prepared`、`ServerStatus`、`ThreadFilter`、`ThreadStatusNotification`、`ThreadSummary`、`ToolResult`、`TurnNotification`；有的改了名（`ItemType` 成了 `ItemKind`，`Prepared` 成了 `PreparedExecution`，`ToolResult` 成了 `Result`，`ThreadFilter` 成了 `ThreadListParams`，记忆的几个枚举去掉了 `Memory` 前缀），有的随机制一起消失（`Await` 被条目上的 `input` 和 `childThreadId` 取代，`ThreadSummary` 和 `ThreadStatusNotification` 随状态进入 `ThreadRow`）。大部分变化来自 v0.16.0 的网关重建（`9b5b50b`）。
:::

## 握手（总览页）

| 类型 | 见 |
|---|---|
| `ClientInfo` | [握手（总览页）](/zh/integrate/protocol#握手) |
| `Empty` | [握手（总览页）](/zh/integrate/protocol#握手)；空对象，用作没有参数的方法的参数和没有结果的方法的结果 |
| `InitializeParams` | [握手（总览页）](/zh/integrate/protocol#握手) |
| `InitializeResult` | [握手（总览页）](/zh/integrate/protocol#握手) |
| `ServerInfo` | [握手（总览页）](/zh/integrate/protocol#握手) |

## 会话

| 类型 | 见 |
|---|---|
| `ThreadArchiveParams` | [会话](/zh/integrate/protocol/threads#thread-archive) |
| `ThreadChangedNotification` | [会话](/zh/integrate/protocol/threads#thread-changed) |
| `ThreadCursor` | [会话](/zh/integrate/protocol/threads#threadcursor) |
| `ThreadDeleteParams` | [会话](/zh/integrate/protocol/threads#thread-delete) |
| `ThreadListParams` | [会话](/zh/integrate/protocol/threads#thread-list) |
| `ThreadListResult` | [会话](/zh/integrate/protocol/threads#thread-list) |
| `ThreadMarkReadParams` | [会话](/zh/integrate/protocol/threads#thread-markread) |
| `ThreadPageParams` | [会话](/zh/integrate/protocol/threads#thread-read-和-thread-resume) |
| `ThreadPageResult` | [会话](/zh/integrate/protocol/threads#thread-read-和-thread-resume) |
| `ThreadRenameParams` | [会话](/zh/integrate/protocol/threads#thread-rename) |
| `ThreadResult` | [会话](/zh/integrate/protocol/threads#参数和结果的包装) |
| `ThreadRow` | [会话](/zh/integrate/protocol/threads#threadrow) |
| `ThreadStartParams` | [会话](/zh/integrate/protocol/threads#thread-start) |
| `ThreadStatus` | [会话](/zh/integrate/protocol/threads#threadstatus) |

## 一轮与条目

| 类型 | 见 |
|---|---|
| `AgentRole` | [一轮与条目](/zh/integrate/protocol/turns#turnrow) |
| `Artifact` | [一轮与条目](/zh/integrate/protocol/turns#result-和-artifact) |
| `Attachment` | [一轮与条目](/zh/integrate/protocol/turns#attachment) |
| `AttachmentReadParams` | [一轮与条目](/zh/integrate/protocol/turns#attachment-read) |
| `AttachmentReadResult` | [一轮与条目](/zh/integrate/protocol/turns#attachment-read) |
| `ContextStats` | [一轮与条目](/zh/integrate/protocol/turns#contextstats) |
| `DeltaNotification` | [一轮与条目](/zh/integrate/protocol/turns#通知的包装) |
| `ErrorNotification` | [一轮与条目](/zh/integrate/protocol/turns#error) |
| `ItemChangedNotification` | [一轮与条目](/zh/integrate/protocol/turns#item-changed) |
| `ItemKind` | [一轮与条目](/zh/integrate/protocol/turns#条目) |
| `ItemRow` | [一轮与条目](/zh/integrate/protocol/turns#itemrow) |
| `ItemStatus` | [一轮与条目](/zh/integrate/protocol/turns#条目) |
| `MemoryStats` | [一轮与条目](/zh/integrate/protocol/turns#contextstats) |
| `ResponseRow` | [一轮与条目](/zh/integrate/protocol/turns#responserow) |
| `Result` | [一轮与条目](/zh/integrate/protocol/turns#result-和-artifact) |
| `TurnChangedNotification` | [一轮与条目](/zh/integrate/protocol/turns#turn-changed) |
| `TurnInterruptParams` | [一轮与条目](/zh/integrate/protocol/turns#turn-interrupt) |
| `TurnResult` | [一轮与条目](/zh/integrate/protocol/turns#turnrow) |
| `TurnRow` | [一轮与条目](/zh/integrate/protocol/turns#turnrow) |
| `TurnStartParams` | [一轮与条目](/zh/integrate/protocol/turns#turn-start) |
| `TurnStatus` | [一轮与条目](/zh/integrate/protocol/turns#一轮的状态) |
| `TurnSteerParams` | [一轮与条目](/zh/integrate/protocol/turns#turn-steer) |
| `TurnSteerResult` | [一轮与条目](/zh/integrate/protocol/turns#turn-steer) |
| `Usage` | [一轮与条目](/zh/integrate/protocol/turns#usage) |
| `UserInput` | [一轮与条目](/zh/integrate/protocol/turns#userinput) |

## 审批与提问

| 类型 | 见 |
|---|---|
| `Approval` | [审批与提问](/zh/integrate/protocol/approvals#approval) |
| `ApprovalRequestParams` | [审批与提问](/zh/integrate/protocol/approvals#approvalrequestparams) |
| `ApprovalResponse` | [审批与提问](/zh/integrate/protocol/approvals#approvalresponse) |
| `Decision` | [审批与提问](/zh/integrate/protocol/approvals#decision) |
| `FileChange` | [审批与提问](/zh/integrate/protocol/approvals#filechange) |
| `Input` | [审批与提问](/zh/integrate/protocol/approvals#input) |
| `PreparedExecution` | [审批与提问](/zh/integrate/protocol/approvals#preparedexecution) |
| `UserInputAnswer` | [审批与提问](/zh/integrate/protocol/approvals#userinputresponse) |
| `UserInputAnswers` | [审批与提问](/zh/integrate/protocol/approvals#userinputresponse) |
| `UserInputOption` | [审批与提问](/zh/integrate/protocol/approvals#userinputoption) |
| `UserInputQuestion` | [审批与提问](/zh/integrate/protocol/approvals#userinputquestion) |
| `UserInputRequest` | [审批与提问](/zh/integrate/protocol/approvals#userinputrequestparams) |
| `UserInputRequestParams` | [审批与提问](/zh/integrate/protocol/approvals#userinputrequestparams) |
| `UserInputResponse` | [审批与提问](/zh/integrate/protocol/approvals#userinputresponse) |

## 权限

| 类型 | 见 |
|---|---|
| `ApprovalPolicy` | [权限](/zh/integrate/protocol/permissions#approvalpolicy) |
| `PermissionRules` | [权限](/zh/integrate/protocol/permissions#permissionrules) |
| `PermissionSettings` | [权限](/zh/integrate/protocol/permissions#permissionsettings) |
| `SettingsPermissionsParams` | [权限](/zh/integrate/protocol/permissions) |
| `ThreadPermissionsParams` | [权限](/zh/integrate/protocol/permissions) |
| `WorkspacePermissionsParams` | [权限](/zh/integrate/protocol/permissions) |

## 工作区与执行环境

| 类型 | 见 |
|---|---|
| `EnvironmentAddParams` | [工作区与执行环境](/zh/integrate/protocol/workspaces) |
| `EnvironmentChangedNotification` | [工作区与执行环境](/zh/integrate/protocol/workspaces) |
| `EnvironmentDeleteParams` | [工作区与执行环境](/zh/integrate/protocol/workspaces) |
| `EnvironmentKind` | [工作区与执行环境](/zh/integrate/protocol/workspaces#environmentkind) |
| `EnvironmentListResult` | [工作区与执行环境](/zh/integrate/protocol/workspaces) |
| `EnvironmentRenameParams` | [工作区与执行环境](/zh/integrate/protocol/workspaces) |
| `EnvironmentResult` | [工作区与执行环境](/zh/integrate/protocol/workspaces) |
| `EnvironmentRow` | [工作区与执行环境](/zh/integrate/protocol/workspaces#environmentrow) |
| `WorkspaceAddParams` | [工作区与执行环境](/zh/integrate/protocol/workspaces) |
| `WorkspaceArchiveParams` | [工作区与执行环境](/zh/integrate/protocol/workspaces) |
| `WorkspaceListResult` | [工作区与执行环境](/zh/integrate/protocol/workspaces) |
| `WorkspaceMoveParams` | [工作区与执行环境](/zh/integrate/protocol/workspaces) |
| `WorkspaceRenameParams` | [工作区与执行环境](/zh/integrate/protocol/workspaces) |
| `WorkspaceResult` | [工作区与执行环境](/zh/integrate/protocol/workspaces)；也是 `workspace/changed` 的载荷 |
| `WorkspaceRow` | [工作区与执行环境](/zh/integrate/protocol/workspaces#workspacerow) |

## 模型、工具与 MCP

| 类型 | 见 |
|---|---|
| `Annotations` | [模型、工具与 MCP](/zh/integrate/protocol/models-tools#annotations) |
| `CommandOutput` | [模型、工具与 MCP](/zh/integrate/protocol/models-tools#commandoutput) |
| `FileOutput` | [模型、工具与 MCP](/zh/integrate/protocol/models-tools#fileoutput) |
| `Glob` | [模型、工具与 MCP](/zh/integrate/protocol/models-tools#glob-和-globoutput) |
| `GlobOutput` | [模型、工具与 MCP](/zh/integrate/protocol/models-tools#glob-和-globoutput) |
| `Grep` | [模型、工具与 MCP](/zh/integrate/protocol/models-tools#grep、grepoutput、grepfile、grepline) |
| `GrepFile` | [模型、工具与 MCP](/zh/integrate/protocol/models-tools#grep、grepoutput、grepfile、grepline) |
| `GrepLine` | [模型、工具与 MCP](/zh/integrate/protocol/models-tools#grep、grepoutput、grepfile、grepline) |
| `GrepOutput` | [模型、工具与 MCP](/zh/integrate/protocol/models-tools#grep、grepoutput、grepfile、grepline) |
| `MCPServer` | [模型、工具与 MCP](/zh/integrate/protocol/models-tools) |
| `MCPServerChangedNotification` | [模型、工具与 MCP](/zh/integrate/protocol/models-tools) |
| `MCPServerConfig` | [模型、工具与 MCP](/zh/integrate/protocol/models-tools)；也是 `mcpServer/set` 的参数和结果 |
| `MCPServerDeleteParams` | [模型、工具与 MCP](/zh/integrate/protocol/models-tools) |
| `MCPServerListResult` | [模型、工具与 MCP](/zh/integrate/protocol/models-tools) |
| `MCPServerStatus` | [模型、工具与 MCP](/zh/integrate/protocol/models-tools) |
| `Model` | [模型、工具与 MCP](/zh/integrate/protocol/models-tools#model) |
| `ModelListResult` | [模型、工具与 MCP](/zh/integrate/protocol/models-tools) |
| `Plan` | [模型、工具与 MCP](/zh/integrate/protocol/models-tools#plan-和-planstep) |
| `PlanStep` | [模型、工具与 MCP](/zh/integrate/protocol/models-tools#plan-和-planstep) |
| `PlanStepStatus` | [模型、工具与 MCP](/zh/integrate/protocol/models-tools#plan-和-planstep) |
| `ReadFile` | [模型、工具与 MCP](/zh/integrate/protocol/models-tools#readfile-和-readfileoutput) |
| `ReadFileOutput` | [模型、工具与 MCP](/zh/integrate/protocol/models-tools#readfile-和-readfileoutput) |
| `SubagentCall` | [模型、工具与 MCP](/zh/integrate/protocol/models-tools#subagentcall) |
| `SubagentLaunched` | [模型、工具与 MCP](/zh/integrate/protocol/models-tools)；子 agent 工具的输出，也见[子 agent 会话](/zh/integrate/protocol/threads#子-agent-会话) |
| `ToolDescriptor` | [模型、工具与 MCP](/zh/integrate/protocol/models-tools#tooldescriptor) |
| `ToolListResult` | [模型、工具与 MCP](/zh/integrate/protocol/models-tools) |

## 定时任务

| 类型 | 见 |
|---|---|
| `CronChangedNotification` | [定时任务](/zh/integrate/protocol/cron) |
| `CronCreateParams` | [定时任务](/zh/integrate/protocol/cron) |
| `CronDeleteParams` | [定时任务](/zh/integrate/protocol/cron) |
| `CronJobRow` | [定时任务](/zh/integrate/protocol/cron) |
| `CronListParams` | [定时任务](/zh/integrate/protocol/cron) |
| `CronListResult` | [定时任务](/zh/integrate/protocol/cron) |
| `CronPauseParams` | [定时任务](/zh/integrate/protocol/cron) |
| `CronResult` | [定时任务](/zh/integrate/protocol/cron) |

## 记忆

| 类型 | 见 |
|---|---|
| `FailureCode` | [记忆](/zh/integrate/protocol/memory)；记忆提取失败的原因代码；名字没有前缀 |
| `Kind` | [记忆](/zh/integrate/protocol/memory)；记忆的种类；名字没有前缀 |
| `MemoryFailure` | [记忆](/zh/integrate/protocol/memory) |
| `MemoryForgetParams` | [记忆](/zh/integrate/protocol/memory) |
| `MemoryListParams` | [记忆](/zh/integrate/protocol/memory) |
| `MemoryListResult` | [记忆](/zh/integrate/protocol/memory) |
| `MemoryMoveParams` | [记忆](/zh/integrate/protocol/memory) |
| `MemoryReference` | [记忆](/zh/integrate/protocol/memory#memoryreference) |
| `MemoryResult` | [记忆](/zh/integrate/protocol/memory)；也是 `memory/changed` 的载荷 |
| `MemoryRow` | [记忆](/zh/integrate/protocol/memory#memoryrow) |
| `MemorySkip` | [记忆](/zh/integrate/protocol/memory) |
| `MemorySource` | [记忆](/zh/integrate/protocol/memory#memorysource) |
| `MemoryStatus` | [记忆](/zh/integrate/protocol/memory#memorystatus) |
| `MemoryUpdateParams` | [记忆](/zh/integrate/protocol/memory) |
| `Scope` | [记忆](/zh/integrate/protocol/memory)；记忆的范围；名字没有前缀 |
| `Status` | [记忆](/zh/integrate/protocol/memory)；记忆的状态；名字没有前缀 |

## 搜索

| 类型 | 见 |
|---|---|
| `MessageHit` | [搜索](/zh/integrate/protocol/search#messagehit) |
| `SearchParams` | [搜索](/zh/integrate/protocol/search) |
| `SearchResult` | [搜索](/zh/integrate/protocol/search#searchresult) |

## 设置

| 类型 | 见 |
|---|---|
| `SettingsRow` | [设置](/zh/integrate/protocol/settings#类型-settingsrow)；也是 `settings/changed` 的载荷 |
| `SettingsUpdateParams` | [设置](/zh/integrate/protocol/settings) |
