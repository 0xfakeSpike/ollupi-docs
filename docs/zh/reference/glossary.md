# 术语表

这是全站术语的权威页。每条给一句话定义和代码里的对应物；机制不在这里展开，点链接看详解。各页首次出现的术语都链到这里。

引擎条目里的标识符、表名和字段名按 ollupi v0.17.1 核对；桌面端条目是此前按 `ollupi-desktop` 源码核对的，这次没有重新核对。

## 执行与调度

- **会话**（thread）—— 一段对话，也是调度和持久化的归属单位：日志按会话追加，调度器按会话取活。代码：`threads` 表、`store.Thread`、`account.Thread`。见 [核心概念](/zh/intro/concepts)
- **日志**（log）—— 一个会话只追加、不修改的记录序列；轮次、条目和会话状态都从它算出。代码：`entries` 表。见 [持久化](/zh/engine/persistence)
- **记录**（entry）—— 日志里的一条：一轮排上、一条消息、一次调用被提出、被批准、开始、给出结果……写下后不再修改。代码：`conversation.Entry`、`conversation.EntryKind`。见 [持久化](/zh/engine/persistence)
- **视图**（view）—— 从日志折叠出的当前状态：轮次、条目、当前轮次、在等什么；`turns`、`items` 表是它的物化，为了查询。代码：`conversation.View`、`View.Apply`。见 [持久化](/zh/engine/persistence)
- **写入检查**（check）—— 每条记录写入前判断它能不能接在当前日志后面，不能就整个事务失败。代码：`conversation.Check`、`conversation.ErrRefused`。见 [持久化](/zh/engine/persistence)
- **feed** —— 事务提交后发布变化的通道，同一次提交的事件共用一个序号；网关、调度器和记忆提炼都只从它得知变化。代码：`store.Feed`、`store.Event`、`feed` 表。见 [持久化](/zh/engine/persistence)
- **一轮**（轮次，turn）—— 交给 agent 的一件事，来自用户消息、定时任务或父 agent，可能多次调用模型和工具。代码：`conversation.Turn`、`TurnQueued`、`TurnEnded`、`turns` 表。见 [执行模型](/zh/engine/execution)
- **当前轮次**（active turn）—— 会话里第一个没结束的轮次，同一会话只运行它，其余排在后面。代码：`View.Active`、`View.Queued`。见 [执行模型](/zh/engine/execution)
- **轮次状态**（turn status）—— 协议里是 `queued`、`inProgress`、`completed`、`failed`、`interrupted`；日志里一轮只记是否结束、怎样结束，在等什么看它的条目。代码：`gateway.TurnStatus`、`conversation.End`。见 [执行模型](/zh/engine/execution)
- **等待**（wait）—— 当前轮次在等审批、等回答，或回答后等子 agent 或后台调用的报告；等待中不占槽位。代码：`conversation.Wait`、`View.Waiting`。见 [执行模型](/zh/engine/execution)
- **可运行**（runnable）—— 会话有当前轮次、且它不在等任何东西；store 记下它变成可运行的时刻，调度器按先后取。代码：`View.Runnable`、`threads.runnable_since`、`Reader.Runnable`。见 [执行模型](/zh/engine/execution)
- **槽位**（slot）—— 池里的一个运行名额。会话池的槽位：会话占着它才运行当前轮次；工具池的槽位：一个后台调用占着它才执行。总数和每用户上限由宿主设定。代码：`schedule.New`、`host.Config.Slots`、`host.Config.UserSlots`、`host.Config.TaskSlots`、`host.Config.UserTaskSlots`。见 [执行模型](/zh/engine/execution)
- **会话池**（session pool）—— 所有会话的当前轮次在这里按槽位排队运行，子 agent 和定时任务都是池里的普通会话；默认 32 个槽位。代码：`schedule.Threads`、`host.Config.Slots`。见 [执行模型](/zh/engine/execution)
- **工具池**（tool pool）—— 转入后台的工具调用（后台调用）在这里按槽位排队执行，和会话池分开调度；默认 32 个槽位、每个用户最多 4 个、每个最长 1 小时。调用开始后轮次继续，结果作为报告送回发起它的轮次。代码：`schedule.Tasks`、`host.Config.TaskSlots`、`host.Config.UserTaskSlots`、`host.Config.TaskLimit`、`tasks` 表。见 [执行模型](/zh/engine/execution)
- **调度器**（scheduler）—— 订阅 feed，有会话变得可运行就在槽位以内把它交给 runner，轮次结束或会话删除时取消对应的运行。代码：`schedule.Scheduler`。见 [执行模型](/zh/engine/execution)
- **runner** —— 会话占着槽位时的执行体：每一步重读日志、决定下一步、执行、把结果追加回日志，直到轮次要等或结束。代码：`run.Runner`。见 [执行模型](/zh/engine/execution)
- **下一步**（next action）—— 从视图和角色算出下一步：调模型、执行工具、跳过工具、结束或等待。代码：`agent.Next`、`agent.Action`。见 [执行模型](/zh/engine/execution)
- **角色**（role）—— 一轮由哪种 agent 跑：完整主 agent、精简主 agent、通用子 agent、浏览器子 agent，各有规则、权限层、工具和上限。代码：`agent.Role`、`agent.Name`、`TurnQueued.Role`。见 [执行模型](/zh/engine/execution)
- **插话**（steer）—— 向当前轮次追加一条用户消息，不另起一轮；在等的审批和提问随之作废。代码：`app.Steer`、`turn/steer`。见 [执行模型](/zh/engine/execution)
- **中断**（interrupt）—— 以 `interrupted` 结束会话的当前一轮，排在后面的轮次照常开始。代码：`app.Interrupt`、`run.End`。见 [执行模型](/zh/engine/execution)
- **子 agent**（subagent）—— 由 `general-sub-agent`、`browser-sub-agent` 工具启动、替父轮次跑任务的普通会话，结束时把报告写回父轮次。代码：`threads.parent_id`、`tool/builtin/subagent`、`ChildLaunched`、`ChildReported`。见 [执行模型](/zh/engine/execution)
- **定时任务**（scheduled job，代码里叫 cron job）—— 按 cron 表达式到点向会话发一条消息的任务，那一轮和用户的轮次一样排队。代码：`cron_jobs` 表、`cron` 包、`tool/builtin/cronjobs`。见 [定时任务](/zh/engine/cron)

## 会话与内容

- **条目**（item）—— 一轮里的一步，由一条或几条记录折叠成，界面时间线由它组成。代码：`conversation.Item`、`items` 表。见 [持久化](/zh/engine/persistence)
- **工具调用**（toolCall）—— 一个条目，参数、审批、提问、启动的子 agent 和结果都折叠在它上面。代码：`conversation.ItemToolCall`、`ToolCall` 记录。见 [工具系统](/zh/engine/tools)
- **子 agent 报告**（agentReport）—— 子 agent 结束时写回启动它的那一轮的条目。代码：`conversation.ItemReport`、`ChildReported`。见 [执行模型](/zh/engine/execution)
- **提示**（notice）—— 运行时告诉模型的话，比如工具为什么停了。代码：`conversation.ItemNotice`、`Notice` 记录。见 [执行模型](/zh/engine/execution)
- **压缩条目**（contextCompaction）—— 一次压缩留下的摘要。代码：`conversation.ItemCompaction`、`Compacted` 记录。见 [上下文管理](/zh/engine/context)
- **一次回答**（response）—— 同一次模型调用产出的条目共用一个回答 id；这次调用的用量和上下文统计记在 `ModelResponded`。代码：`responses` 表、`AgentMessage.Response`。见 [持久化](/zh/engine/persistence)
- **附件**（attachment）—— 随消息发送的图片或文本文件，发送时复制进附件存储。代码：`conversation.Attachment`、`app.Attachments`、`blob.Dir`。见 [持久化](/zh/engine/persistence)

## 模型与上下文

- **连接**（connection）—— 一个 Base URL、一把密钥、一组模型和一份并发名额。代码：`llm.Client`、`host.Config.Connections`、`host.Config.ClientFor`。见 [模型接入](/zh/engine/models)
- **上下文窗口**（context window）—— 模型一次能接收加生成的 token 上限。代码：`llm.Limits.Context`。见 [上下文管理](/zh/engine/context)
- **输入预算**（input budget）—— 窗口扣掉回答预留后，留给提示词的 token 数，可再用最大输入压低。代码：`llm.Limits.Input`、`llm.Limits.MaxInput`。见 [上下文管理](/zh/engine/context)
- **压缩**（compaction）—— 把旧历史换成一份交接摘要，腾出窗口。代码：`prompt.Window.Compaction`、`Compacted`。见 [上下文管理](/zh/engine/context)
- **精简模式**（compact mode）—— 输入预算不足 16384 token 时，主 agent 换成精简角色：短提示词和更少的核心工具。代码：`agent.CompactMain`、`agent.MainRole`。见 [上下文管理](/zh/engine/context)
- **系统提示词**（system prompt）—— 每次请求开头那段指令，按稳定程度拼接。代码：`prompt.Window.System`。见 [上下文管理](/zh/engine/context)
- **前缀缓存**（prefix cache）—— 服务商对请求开头相同部分的复用。代码：`conversation.Usage.CachedInputTokens`。见 [上下文管理](/zh/engine/context)
- **延迟加载**（deferred tools）—— 工具定义放不下时只列名字，用到时再载入。代码：`prompt.Window.Offer`、`load_tools`。见 [工具系统](/zh/engine/tools)

## 工具与能力

- **工具**（tool）—— 模型能调用的一次动作，由名称、描述和参数结构定义。代码：`tool.Spec`、`kit.Spec`。见 [工具系统](/zh/engine/tools)
- **工具提供方**（provider）—— 提供一组工具并执行调用的对象。代码：`kit.Provider`。见 [工具系统](/zh/engine/tools)
- **工具注册表**（registry）—— 合并全部提供方后的工具目录，顺序固定。代码：`kit.Registry`。见 [工具系统](/zh/engine/tools)
- **冻结**（prepared execution）—— 审批前算好、随调用记进日志的执行内容，执行时逐项比对；命令和文件改动都走它。代码：`kit.Spec.Prepare`、`tool.Plan`、`ToolCall.Prepared`、`workspace.Prepared`。见 [工具系统](/zh/engine/tools)
- **技能**（skill）—— 一个含 `SKILL.md` 的文件夹，按角色安装，agent 按需激活。代码：`skill.Skill`、`skill.Load`。见 [技能与 MCP](/zh/engine/skills-mcp)
- **MCP** —— 让外部服务器以工具形式接入的协议，工具名带服务器前缀。代码：`tool/mcp`、`policy.ProviderSeparator`。见 [技能与 MCP](/zh/engine/skills-mcp)

## 安全

- **审批**（approval）—— 工具调用前请用户决定是否放行的请求。代码：`ApprovalAsked`、`Decided`、`conversation.Decision`。见 [审批与权限](/zh/engine/permissions)
- **审批策略**（approval policy）—— 规则没有结论时，默认放行还是询问的三档设置。代码：`policy.Policy`。见 [审批与权限](/zh/engine/permissions)
- **规则**（rule）—— 按工具名和调用内容匹配的 allow、ask、deny 条目。代码：`policy.Rules`。见 [审批与权限](/zh/engine/permissions)
- **权限层**（layer）—— 一份可叠加的权限设置：部署、用户、工作区、会话各一层，角色还可以带自己的一层。代码：`policy.Layer`、`policy.Settings`、`account.Layers`。见 [审批与权限](/zh/engine/permissions)
- **沙箱**（sandbox）—— 限制模型的命令和文件操作能碰到什么的机制。代码：`sandbox.New`、`sandbox.Box`。见 [沙箱](/zh/engine/sandbox)
- **Box** —— 一个用户的命令运行与文件所在的地方，工具只经它访问系统。代码：`sandbox.Box`、`sandbox.Here`、`host.Config.Boxes`。见 [沙箱](/zh/engine/sandbox)
- **Machine** —— 云沙箱的最小接口：跑一条命令，按路径读写。代码：`sandbox.Machine`、`sandbox.Remote`。见 [沙箱](/zh/engine/sandbox)
- **提权**（escalation）—— 让一条命令以完全访问运行：解除沙箱对它的限制（本机是 Seatbelt 规则），仍在同一个沙箱里；远程沙箱不能提权。`untrusted` 和 `on-request` 下必须单独批准，`never` 下直接运行，只有 deny 规则能拦住它。代码：`workspace.Prepared.Escalated`、`sandbox.Command.FullAccess`。见 [沙箱](/zh/engine/sandbox)
- **脱敏**（redaction）—— 发给模型前把敏感值换成占位符，回答回来再换回。代码：`redact.Redactor`（`pkg/redact`）。见 [脱敏](/zh/engine/redaction)
- **占位符**（placeholder）—— 敏感值的替身，形如 `<PHONE:a1b2c3d4>`。代码：`Redactor.placeholder`（未导出）、`settings.redaction_key`。见 [脱敏](/zh/engine/redaction)

## 存储与部署

- **执行环境**（environment）—— 会话运行命令和文件工具的地方：这台机器（`local`），或宿主接入的云沙箱（`machine`）。会话开始时选定，之后不变。代码：`environments` 表、`account.Environment`、`workspace.Options.BoxIn`。见 [网关协议](/zh/integrate/protocol/workspaces#执行环境的方法)
- **工作区**（workspace）—— agent 工作的一个目录，权限规则可以按它设置。代码：`workspaces` 表、`account.Workspace`。见 [核心概念](/zh/intro/concepts)
- **记忆**（memory）—— 后台从已结束轮次提炼、跨会话使用的笔记。代码：`memories` 表、`memory.Memory`、`extract.Extractor`。见 [记忆](/zh/engine/memory)
- **记忆范围**（scope）—— 一条记忆对哪些会话可见：`global`、`general`、`workspace`。代码：`memory.Scope`。见 [记忆](/zh/engine/memory)
- **记忆状态**（memory status）—— 一条记忆现在是否在用：`active`、`retired`、`forgotten`。代码：`memory.Status`。见 [记忆](/zh/engine/memory)
- **记忆快照**（snapshot）—— 一轮开头载入上下文的一份记忆。代码：`memory.Recall`、`Recalled` 记录、`conversation.ItemMemory`。见 [记忆](/zh/engine/memory)
- **分片**（shard）—— 一个 SQLite 库，里面的用户共用同一组表；引擎本身不知道分片，`shard` 包把一个进程当作分片来跑。代码：`store/sqlite`、`shard.Member`。见 [分片与多用户](/zh/engine/sharding)
- **目录**（catalog）—— 和各分片数据分开的部署级记录：有哪些分片、谁持有租约、用户放在哪个分片。代码：`catalog.Catalog`、`catalog.SQL`。见 [分片与多用户](/zh/engine/sharding)
- **租约**（lease）—— 一个进程独占一个分片的凭据，由目录按自己的时钟判定，记在目录的 `shards` 表。代码：`shard.Member`、`catalog.Catalog`。见 [分片与多用户](/zh/engine/sharding)
- **epoch 与围栏**（fence）—— 每次接手分片得到一个更大的 epoch，分片库记下它并在每次写入时核对，挡住已失去分片的进程。代码：`Store.Fence`、`shard_epoch` 表、`store.ErrShardLost`。见 [分片与多用户](/zh/engine/sharding)
- **路由器**（router）—— 客户端唯一要连的地址背后，把连接转到用户所在分片的那一层：负载均衡器的回调或独立的路由器。代码：`router.Router`、`router.Locator`、`router/extproc`。见 [分片与多用户](/zh/engine/sharding)
- **迁移**（migration）—— 按编号升级表结构的 SQL 步骤，版本记在库里。代码：`store/sqlite/migrations`、`pkg/sqlitedb`、`PRAGMA user_version`。见 [持久化](/zh/engine/persistence)
- **宿主**（host）—— 组装引擎的进程：开库、建模型客户端和工具、启动调度器、记忆提炼和定时任务。代码：`host.Config`、`host.New`、`sidecar/internal/host`。见 [引擎架构](/zh/engine/architecture)
- **应用层**（app）—— 用户能做的每件事：一次检查加一个事务。网关只经它读写。代码：`app.App`。见 [引擎架构](/zh/engine/architecture)
- **网关**（gateway）—— 引擎对外的唯一接口：WebSocket 上的 JSON-RPC 2.0。代码：`gateway.Server`。见 [协议](/zh/integrate/protocol)
- **方法**（method）—— 客户端发给网关的一次请求，参数和结果都有类型。代码：`gateway/protocol.go` 的 `methods` 表。见 [协议](/zh/integrate/protocol)
- **通知**（notification）—— 网关主动推给客户端、不需要回应的消息；会话、轮次、条目的变化通知带着改它的那次提交的序号。代码：`gateway/protocol.go` 的 `notifications` 表。见 [协议](/zh/integrate/protocol)
- **服务端请求**（server request）—— 网关发给客户端、要它回应的请求，只有审批和提问两种。代码：`requestApproval`、`requestUserInput`。见 [协议](/zh/integrate/protocol)
- **事件**（event）—— 一次提交带来的变化，发在 feed 上，网关把它翻成协议消息。代码：`store.Event`、`store.Change`。见 [引擎架构](/zh/engine/architecture)

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

- [核心概念](/zh/intro/concepts)：四层数据结构、日志和状态表。
- [执行模型](/zh/engine/execution)：槽位、轮次怎样一步步运行、恢复。
- [功能清单](/zh/reference/features)：某项能力有没有。
