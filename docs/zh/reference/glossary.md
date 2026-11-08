# 术语表

这是全站术语的权威页。每条给一句话定义和代码里的对应物；机制不在这里展开，点链接看详解。各页首次出现的术语都链到这里。

定义里的标识符、表名和字段名都在 `ollupi` 与 `ollupi-desktop` 源码里核对过。

## 执行与调度

- **会话**（thread）—— 一段对话，也是调度和持久化的归属单位。代码：`threads` 表、`repo.ThreadRow`。见 [核心概念](/zh/intro/concepts)
- **一轮**（轮次）—— 会话里的一次完整处理，可能多次调用模型和工具。代码：`turns` 表、`repo.TurnRow`。见 [执行模型](/zh/engine/execution)
- **条目**（item）—— 一轮里的一件已记录的事，界面时间线由它组成。代码：`items` 表、`repo.ItemRow`。见 [持久化](/zh/engine/persistence)
- **槽位**（slot）—— 执行池里的一个运行名额，占着它的一轮才在执行。代码：`agent.slot`（未导出）、`Agent.slotByThread`。见 [执行模型](/zh/engine/execution)
- **调度循环**（scheduler loop）—— 一个 goroutine 上的事件循环，调度状态只在它里面改。代码：`Agent.loop`。见 [引擎架构](/zh/engine/architecture)
- **admit** —— 每个事件之后按空闲槽位数从库里取就绪轮次。代码：`admit`（`agent/schedule.go`）。见 [执行模型](/zh/engine/execution)
- **reconcile** —— 让一个会话往前走一步的幂等函数。代码：`reconcile`（`agent/schedule.go`）。见 [执行模型](/zh/engine/execution)
- **运行**（runtime）—— 一轮占着槽位时的执行体：判断工具、执行工具、调用模型。代码：`runtime.Runtime`。见 [执行模型](/zh/engine/execution)
- **插话**（steer）—— 向进行中的一轮追加一条用户消息，不打断它。代码：`Agent.SteerTurn`、`turn/steer`。见 [执行模型](/zh/engine/execution)
- **中断**（interrupt）—— 结束会话的当前一轮，排队的轮次照常开始。代码：`Agent.InterruptTurn`。见 [执行模型](/zh/engine/execution)
- **轮次状态**（轮次 status）—— 一轮在调度里的位置，九个取值。代码：`repo.TurnStatus`。见 [执行模型](/zh/engine/execution)
- **子 agent**（subagent）—— 由 `Agent` 工具派生、替父轮次跑子任务的普通会话。代码：`threads.parent_thread_id`、`tools/subagent`。见 [执行模型](/zh/engine/execution)
- **定时任务**（scheduled task / cron job）—— 按 cron 表达式到点向会话发一条消息的任务。代码：`cron_jobs` 表、`tools/cron`。见 [定时任务](/zh/engine/cron)

## 会话与内容

- **工具调用**（toolCall）—— 一次工具调用，参数、结果和等待都记在这一条上。代码：`repo.ItemToolCall`。见 [工具系统](/zh/engine/tools)
- **压缩条目**（contextCompaction）—— 一次压缩留下的摘要记录。代码：`repo.ItemContextCompaction`。见 [上下文管理](/zh/engine/context)
- **一次回答**（response）—— 同一次模型调用产出的条目，共用 `response_id`。代码：`items.response_id`。见 [持久化](/zh/engine/persistence)
- **附件**（attachment）—— 随消息发送的图片或文本文件。代码：`repo.Attachment`、`agent/attachments.go`。见 [持久化](/zh/engine/persistence)

## 模型与上下文

- **连接**（connection）—— 一个 Base URL、一把密钥、一组模型和一份并发名额。代码：`llm.Client`、`Config.Connections`。见 [模型接入](/zh/engine/models)
- **上下文窗口**（context window）—— 模型一次能接收加生成的 token 上限。代码：`llm.Limits.Context`。见 [上下文管理](/zh/engine/context)
- **输入预算**（input budget）—— 窗口扣掉回答预留后，留给提示词的 token 数。代码：`llm.Limits.Input`。见 [上下文管理](/zh/engine/context)
- **压缩**（compaction）—— 把旧历史换成一份交接摘要，腾出窗口。代码：`NeedsCompaction`、`contextCompaction`。见 [上下文管理](/zh/engine/context)
- **精简模式**（compact mode）—— 输入预算不足 16384 token 时换用的短提示词与工具集。代码：`contextmanager.Manager.Compact`、`compactRules`。见 [上下文管理](/zh/engine/context)
- **系统提示词**（system prompt）—— 每次运行开头那段固定指令，按稳定程度拼接。代码：`systemprompt.Build`。见 [上下文管理](/zh/engine/context)
- **前缀缓存**（prefix cache）—— 服务商对请求开头相同部分的复用。代码：`cached_input_tokens` 列。见 [上下文管理](/zh/engine/context)
- **延迟加载**（deferred tools）—— 工具定义放不下时只列名字，用到时再载入。代码：`runtime.Offer`、`load_tools`。见 [工具系统](/zh/engine/tools)

## 工具与能力

- **工具**（tool）—— 模型能调用的一次动作，由名称、描述和参数结构定义。代码：`tools.Spec`。见 [工具系统](/zh/engine/tools)
- **工具提供方**（provider）—— 提供一组工具并执行调用的对象。代码：`tools.Provider`。见 [工具系统](/zh/engine/tools)
- **工具注册表**（registry）—— 合并全部提供方后的工具目录，顺序固定。代码：`tools.Registry`。见 [工具系统](/zh/engine/tools)
- **两段式工具**（local tool）—— 先冻结执行内容、再执行的工具，命令和文件改动走它。代码：`tools.Local`。见 [工具系统](/zh/engine/tools)
- **冻结**（prepared execution）—— 审批前算好并落库的执行内容，执行时逐项比对。代码：`tools.Prepared`、`items.prepared_execution`。见 [工具系统](/zh/engine/tools)
- **等待**（await）—— 结果要等用户或子 agent 给出，此时条目留在进行中。代码：`tools.Await`。见 [工具系统](/zh/engine/tools)
- **技能**（skill）—— 一个含 `SKILL.md` 的文件夹，agent 按需激活。代码：`skills.Skill`、`skills.Catalog`。见 [技能与 MCP](/zh/engine/skills-mcp)
- **MCP** —— 让外部服务器以工具形式接入的协议，工具名带提供方前缀。代码：`tools/mcp`、`tools.ProviderSeparator`。见 [技能与 MCP](/zh/engine/skills-mcp)

## 安全

- **审批**（approval）—— 工具调用前请用户决定是否放行的请求。代码：`repo.Approval`。见 [审批与权限](/zh/engine/permissions)
- **审批策略**（approval policy）—— 规则没有结论时，默认放行还是询问的三档设置。代码：`permission.Policy`。见 [审批与权限](/zh/engine/permissions)
- **规则**（rule）—— 按工具名和调用内容匹配的 allow、ask、deny 条目。代码：`repo.PermissionRules`。见 [审批与权限](/zh/engine/permissions)
- **权限层**（layer）—— 一份可叠加的权限设置，agent、工作区、会话各一层。代码：`permission.Settings`。见 [审批与权限](/zh/engine/permissions)
- **沙箱**（sandbox）—— 限制模型的命令和文件操作能碰到什么的机制。代码：`sandbox.New`、`sandbox.Box`。见 [沙箱](/zh/engine/sandbox)
- **Box** —— 一个用户的命令运行与文件所在的地方，工具只经它访问系统。代码：`sandbox.Box`、`sandbox.Here`。见 [沙箱](/zh/engine/sandbox)
- **Machine** —— 云沙箱的最小接口：跑一条命令，按路径读写。代码：`sandbox.Machine`、`sandbox.Remote`。见 [沙箱](/zh/engine/sandbox)
- **提权**（escalation）—— 让一条命令离开沙箱、在宿主上运行。`untrusted` 和 `on-request` 下必须单独批准，`never` 下直接运行，只有 deny 规则能拦住它。代码：`Prepared.Escalated`、`Command.Unsandboxed`。见 [沙箱](/zh/engine/sandbox)
- **脱敏**（redaction）—— 发给模型前把敏感值换成占位符，回答回来再换回。代码：`redact.Redactor`。见 [脱敏](/zh/engine/redaction)
- **占位符**（placeholder）—— 敏感值的替身，形如 `<PHONE:a1b2c3d4>`。代码：`Redactor.placeholder`（未导出）、`settings.redaction_key`。见 [脱敏](/zh/engine/redaction)

## 存储与部署

- **工作区**（workspace）—— agent 工作的一个目录，权限规则可以按它设置。代码：`workspaces` 表、`repo.WorkspaceRow`。见 [核心概念](/zh/intro/concepts)
- **记忆**（memory）—— 后台从已结束轮次提炼、跨会话使用的笔记。代码：`memories` 表、`memory.Manager`。见 [记忆](/zh/engine/memory)
- **记忆范围**（scope）—— 一条记忆对哪些会话可见：`global`、`general`、`workspace`。代码：`repo.MemoryScope`。见 [记忆](/zh/engine/memory)
- **记忆状态**（memory status）—— 一条记忆现在是否在用：`active`、`retired`、`forgotten`。代码：`repo.MemoryRowStatus`。见 [记忆](/zh/engine/memory)
- **记忆快照**（snapshot）—— 会话开头放进上下文的一份记忆文本。代码：`repo.ItemMemoryContext`。见 [记忆](/zh/engine/memory)
- **分片**（shard）—— 一个 SQLite 库，里面的用户共用同一组表。代码：`repo.Open`、`repo.DB`。见 [分片与多用户](/zh/engine/sharding)
- **租约**（lease）—— 一个进程独占一个分片的凭据，库里一行。代码：`shard_lease` 表、`repo.ClaimShard`。见 [分片与多用户](/zh/engine/sharding)
- **围栏**（fence）—— 事务开始前核对租约持有者，挡住已失去分片的进程。代码：`DB.Fence`、`ErrShardLost`。见 [分片与多用户](/zh/engine/sharding)
- **路由器**（router）—— 客户端唯一要连的地址，把连接转到用户所在分片。代码：`gateway.Router`、`gateway.Directory`。见 [分片与多用户](/zh/engine/sharding)
- **迁移**（migration）—— 按编号升级表结构的 SQL 步骤，版本记在库里。代码：`repo/migrations`、`PRAGMA user_version`。见 [持久化](/zh/engine/persistence)
- **宿主**（host）—— 组装引擎的进程：开库、建模型客户端和工具、启动各组件。代码：`agent.Config`、`sidecar/internal/host`。见 [引擎架构](/zh/engine/architecture)
- **网关**（gateway）—— 引擎对外的唯一接口：WebSocket 上的 JSON-RPC 2.0。代码：`gateway.Server`。见 [协议](/zh/integrate/protocol)
- **方法**（method）—— 客户端发给网关的一次请求，参数和结果都有类型。代码：`gateway/protocol.go` 的 `methods` 表。见 [协议](/zh/integrate/protocol)
- **通知**（notification）—— 网关主动推给客户端、不需要回应的消息。代码：`gateway/protocol.go` 的 `notifications` 表。见 [协议](/zh/integrate/protocol)
- **服务端请求**（server request）—— 网关发给客户端、要它回应的请求，只有审批和提问两种。代码：`requestApproval`、`requestUserInput`。见 [协议](/zh/integrate/protocol)
- **事件**（event）—— 引擎内部的状态变化，网关把它翻成协议消息。代码：`agent.Event`、`agent.EventKind`。见 [引擎架构](/zh/engine/architecture)

## 桌面端

- **sidecar** —— 桌面端的后端进程 `ollupid`，装配引擎并提供网关。代码：`sidecar/cmd/ollupid`、`sidecar/internal/host`。见 [Sidecar](/zh/desktop/sidecar)
- **主进程**（main process）—— Electron 里拥有窗口、原生能力和 sidecar 的那一层。代码：`BackendSupervisor`。见 [主进程](/zh/desktop/main-process)
- **渲染进程**（renderer）—— 在沙箱里画界面，只经网关和 IPC 与外界说话的那一层。代码：`DesktopApi`。见 [渲染进程](/zh/desktop/renderer)
- **域**（domain）—— 渲染进程里镜像一块服务器状态、声明如何跟随连接的单元。代码：`Domain`、`renderer/src/domains`。见 [渲染进程](/zh/desktop/renderer)
- **时间线**（timeline）—— 一个会话的条目按轮次归并后的界面模型。代码：`@ollupi/core` 的 `Timeline`。见 [渲染进程](/zh/desktop/renderer)
- **后端状态**（backend state）—— 主进程对 sidecar 的四态描述：启动中、就绪、失败、已停止。代码：`BackendState`。见 [主进程](/zh/desktop/main-process)
- **内置浏览器**（built-in browser）—— 应用自带的 Chromium 标签页，agent 和用户共用。代码：`AgentBrowser`、`Strip`。见 [内置浏览器](/zh/desktop/browser)
- **聊天机器人客户端**（client）—— 网关之外跟着事件的前端，飞书机器人是一个。代码：`host.Client`。见 [Sidecar](/zh/desktop/sidecar)

## 相关页面

- [核心概念](/zh/intro/concepts)：四层数据结构和状态表。
- [执行模型](/zh/engine/execution)：槽位、状态机和恢复。
- [功能清单](/zh/reference/features)：某项能力有没有。
