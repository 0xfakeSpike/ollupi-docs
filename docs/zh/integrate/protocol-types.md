# 协议类型索引

网关契约 `protocol.schema.json` 的全部 129 个命名类型（`$defs`，引擎 v0.12.1），以及讲它的模块页。字段、取值和例子在模块页里；所有模块共用的约定（可选字段、时间、ID）见[通用约定](/zh/integrate/protocol#通用约定)。

只做参数包装的类型（如 `ThreadRenameParams`）字段很少，模块页在对应方法的参数表里讲，没有单独的标题。

## 握手（总览页）

| 类型 | 见 |
|---|---|
| `ClientInfo` | [握手（总览页）](/zh/integrate/protocol#握手) |
| `Empty` | [握手（总览页）](/zh/integrate/protocol#握手) |
| `InitializeParams` | [握手（总览页）](/zh/integrate/protocol#握手) |
| `InitializeResult` | [握手（总览页）](/zh/integrate/protocol#握手) |
| `ServerInfo` | [握手（总览页）](/zh/integrate/protocol#握手) |

## 会话

| 类型 | 见 |
|---|---|
| `ThreadArchiveParams` | [会话](/zh/integrate/protocol/threads) |
| `ThreadChangedNotification` | [会话](/zh/integrate/protocol/threads) |
| `ThreadCursor` | [会话](/zh/integrate/protocol/threads#threadcursor) |
| `ThreadDeleteParams` | [会话](/zh/integrate/protocol/threads) |
| `ThreadFilter` | [会话](/zh/integrate/protocol/threads) |
| `ThreadListResult` | [会话](/zh/integrate/protocol/threads) |
| `ThreadPageParams` | [会话](/zh/integrate/protocol/threads) |
| `ThreadPageResult` | [会话](/zh/integrate/protocol/threads) |
| `ThreadRenameParams` | [会话](/zh/integrate/protocol/threads) |
| `ThreadResult` | [会话](/zh/integrate/protocol/threads) |
| `ThreadRow` | [会话](/zh/integrate/protocol/threads#threadrow) |
| `ThreadStartParams` | [会话](/zh/integrate/protocol/threads) |
| `ThreadStatus` | [会话](/zh/integrate/protocol/threads#threadstatus) |
| `ThreadStatusNotification` | [会话](/zh/integrate/protocol/threads) |
| `ThreadSummary` | [会话](/zh/integrate/protocol/threads#threadsummary) |

## 一轮与条目

| 类型 | 见 |
|---|---|
| `Attachment` | [一轮与条目](/zh/integrate/protocol/turns#attachment) |
| `AttachmentKind` | [一轮与条目](/zh/integrate/protocol/turns) |
| `AttachmentReadParams` | [一轮与条目](/zh/integrate/protocol/turns) |
| `AttachmentReadResult` | [一轮与条目](/zh/integrate/protocol/turns) |
| `Await` | [一轮与条目](/zh/integrate/protocol/turns#await) |
| `AwaitBy` | [一轮与条目](/zh/integrate/protocol/turns) |
| `ContextArtifact` | [一轮与条目](/zh/integrate/protocol/turns#toolresult-和-contextartifact) |
| `ContextStats` | [一轮与条目](/zh/integrate/protocol/turns#contextstats) |
| `DeltaNotification` | [一轮与条目](/zh/integrate/protocol/turns) |
| `ErrorNotification` | [一轮与条目](/zh/integrate/protocol/turns) |
| `ItemNotification` | [一轮与条目](/zh/integrate/protocol/turns) |
| `ItemRow` | [一轮与条目](/zh/integrate/protocol/turns#itemrow) |
| `ItemStatus` | [一轮与条目](/zh/integrate/protocol/turns) |
| `ItemType` | [一轮与条目](/zh/integrate/protocol/turns) |
| `ToolResult` | [一轮与条目](/zh/integrate/protocol/turns#toolresult-和-contextartifact) |
| `TurnInterruptParams` | [一轮与条目](/zh/integrate/protocol/turns) |
| `TurnNotification` | [一轮与条目](/zh/integrate/protocol/turns) |
| `TurnResult` | [一轮与条目](/zh/integrate/protocol/turns) |
| `TurnRow` | [一轮与条目](/zh/integrate/protocol/turns#turnrow) |
| `TurnStartParams` | [一轮与条目](/zh/integrate/protocol/turns) |
| `TurnStatus` | [一轮与条目](/zh/integrate/protocol/turns) |
| `TurnSteerParams` | [一轮与条目](/zh/integrate/protocol/turns) |
| `TurnSteerResult` | [一轮与条目](/zh/integrate/protocol/turns) |
| `Usage` | [一轮与条目](/zh/integrate/protocol/turns#usage) |

## 审批与提问

| 类型 | 见 |
|---|---|
| `Approval` | [审批与提问](/zh/integrate/protocol/approvals#item-toolcall-requestapproval) |
| `ApprovalRequestParams` | [审批与提问](/zh/integrate/protocol/approvals#approvalrequestparams) |
| `ApprovalResponse` | [审批与提问](/zh/integrate/protocol/approvals#approvalresponse) |
| `Decision` | [审批与提问](/zh/integrate/protocol/approvals#decision) |
| `FileChange` | [审批与提问](/zh/integrate/protocol/approvals#filechange) |
| `Prepared` | [审批与提问](/zh/integrate/protocol/approvals#prepared) |
| `UserInput` | [审批与提问](/zh/integrate/protocol/approvals#item-tool-requestuserinput) |
| `UserInputAnswer` | [审批与提问](/zh/integrate/protocol/approvals) |
| `UserInputAnswers` | [审批与提问](/zh/integrate/protocol/approvals) |
| `UserInputOption` | [审批与提问](/zh/integrate/protocol/approvals#userinputoption) |
| `UserInputQuestion` | [审批与提问](/zh/integrate/protocol/approvals#userinputquestion) |
| `UserInputRequest` | [审批与提问](/zh/integrate/protocol/approvals) |
| `UserInputRequestParams` | [审批与提问](/zh/integrate/protocol/approvals#userinputrequestparams) |
| `UserInputResponse` | [审批与提问](/zh/integrate/protocol/approvals#userinputresponse) |

## 权限

| 类型 | 见 |
|---|---|
| `ApprovalPolicy` | [权限](/zh/integrate/protocol/permissions#approvalpolicy) |
| `PermissionRules` | [权限](/zh/integrate/protocol/permissions#permissionrules) |
| `PermissionSettings` | [权限](/zh/integrate/protocol/permissions#permissionsettings) |
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
| `WorkspaceResult` | [工作区与执行环境](/zh/integrate/protocol/workspaces) |
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
| `MCPServerListResult` | [模型、工具与 MCP](/zh/integrate/protocol/models-tools) |
| `Model` | [模型、工具与 MCP](/zh/integrate/protocol/models-tools#model) |
| `ModelListResult` | [模型、工具与 MCP](/zh/integrate/protocol/models-tools) |
| `Plan` | [模型、工具与 MCP](/zh/integrate/protocol/models-tools#plan-和-planstep) |
| `PlanStep` | [模型、工具与 MCP](/zh/integrate/protocol/models-tools#plan-和-planstep) |
| `PlanStepStatus` | [模型、工具与 MCP](/zh/integrate/protocol/models-tools) |
| `ReadFile` | [模型、工具与 MCP](/zh/integrate/protocol/models-tools#readfile-和-readfileoutput) |
| `ReadFileOutput` | [模型、工具与 MCP](/zh/integrate/protocol/models-tools#readfile-和-readfileoutput) |
| `ServerStatus` | [模型、工具与 MCP](/zh/integrate/protocol/models-tools#serverstatus) |
| `SubagentCall` | [模型、工具与 MCP](/zh/integrate/protocol/models-tools#subagentcall) |
| `ToolDescriptor` | [模型、工具与 MCP](/zh/integrate/protocol/models-tools#tooldescriptor) |
| `ToolListResult` | [模型、工具与 MCP](/zh/integrate/protocol/models-tools) |

## 定时任务

| 类型 | 见 |
|---|---|
| `CronChangedNotification` | [定时任务](/zh/integrate/protocol/cron) |
| `CronCreateParams` | [定时任务](/zh/integrate/protocol/cron) |
| `CronDeleteParams` | [定时任务](/zh/integrate/protocol/cron) |
| `CronJobRow` | [定时任务](/zh/integrate/protocol/cron) |
| `CronJobView` | [定时任务](/zh/integrate/protocol/cron#cronjobview) |
| `CronListParams` | [定时任务](/zh/integrate/protocol/cron) |
| `CronListResult` | [定时任务](/zh/integrate/protocol/cron) |
| `CronPauseParams` | [定时任务](/zh/integrate/protocol/cron) |

## 记忆

| 类型 | 见 |
|---|---|
| `MemoryFailure` | [记忆](/zh/integrate/protocol/memory) |
| `MemoryFailureCode` | [记忆](/zh/integrate/protocol/memory) |
| `MemoryForgetParams` | [记忆](/zh/integrate/protocol/memory) |
| `MemoryListParams` | [记忆](/zh/integrate/protocol/memory) |
| `MemoryListResult` | [记忆](/zh/integrate/protocol/memory) |
| `MemoryMoveParams` | [记忆](/zh/integrate/protocol/memory) |
| `MemoryReference` | [记忆](/zh/integrate/protocol/memory#memoryreference) |
| `MemoryReport` | [记忆](/zh/integrate/protocol/memory) |
| `MemoryResult` | [记忆](/zh/integrate/protocol/memory) |
| `MemoryRow` | [记忆](/zh/integrate/protocol/memory#memoryrow) |
| `MemoryRowStatus` | [记忆](/zh/integrate/protocol/memory) |
| `MemoryScope` | [记忆](/zh/integrate/protocol/memory) |
| `MemorySkip` | [记忆](/zh/integrate/protocol/memory) |
| `MemorySource` | [记忆](/zh/integrate/protocol/memory#memorysource) |
| `MemoryStats` | [记忆](/zh/integrate/protocol/memory) |
| `MemoryStatus` | [记忆](/zh/integrate/protocol/memory#memorystatus) |
| `MemoryUpdateParams` | [记忆](/zh/integrate/protocol/memory) |

## 搜索

| 类型 | 见 |
|---|---|
| `MessageHit` | [搜索](/zh/integrate/protocol/search#messagehit) |
| `SearchParams` | [搜索](/zh/integrate/protocol/search) |
| `SearchResult` | [搜索](/zh/integrate/protocol/search#searchresult) |

## 设置

| 类型 | 见 |
|---|---|
| `SettingsRow` | [设置](/zh/integrate/protocol/settings#类型-settingsrow) |
| `SettingsUpdateParams` | [设置](/zh/integrate/protocol/settings) |
