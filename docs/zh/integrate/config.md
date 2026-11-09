# Config 参考

宿主装配引擎时要填两个结构：`agent.Config` 和 `gateway.Options`。这一页列出全部字段、默认值和不填时的行为。默认值在 `agent.Start` 里填上，`agent.New` 只补 `BoxFor`。

## agent.Config

| 字段 | 填什么 | 不填时 |
|---|---|---|
| `Name` | 实例名，出现在日志和部分错误里 | 启动失败 |
| `Prompt` | 系统提示词正文 | 空提示词 |
| `Models` | `[]llm.Model`，第一项是默认模型 | 启动失败 |
| `Connections` | 连接 ID 到 `llm.Client` 的映射 | 启动失败 |
| `ClientFor` | `func(user, connection string) (llm.Client, error)`：给每个用户自己的客户端，让他的轮次用他自己的密钥和配额；每次应返回同一个客户端 | 所有用户共用 `Connections` |
| `Settings`、`Tools` | 默认权限层（至少要设审批策略）、工具白名单 | `Settings` 没有设审批策略时启动失败：`approval policy "" must be one of [...]`；`Tools` 为 `nil` 表示全部工具可见 |
| `Slots`、`UserSlots`、`RunLimit` | 容量参数 | 32、等于 `Slots`、4 小时 |
| `Providers` | 所有用户共有的工具 provider | 只有引擎内置的 `plan`、`subagent`、`userinput` 等 |
| `ToolsFor` | `func(user string) (*tools.Set, error)`：某个用户额外的工具，比如他自己的 MCP 服务器 | 只有 `Providers` |
| `BoxFor` | `func(user string) (sandbox.Box, error)`：用户在这台机器上的沙箱，工作区校验和附件读取经它访问；云端在这里接入 `sandbox.Remote`。同一个函数还要填给 `workspace.Options.BoxFor`（或由 `BoxIn` 按会话的执行环境选）和 `mcp.NewUsers`，见[扩展点](/zh/integrate/extend#云沙箱) | `sandbox.Here()`，本机 |
| `DB` | `repo.DB` | 启动失败 |
| `OnEvent` | 把事件交给网关和别的客户端 | 事件只进日志 |
| `Lease` | 分片租约时长 | 不启用租约，进程假定自己是唯一的 |
| `OnLeaseLost` | 失去租约时的回调 | 只写日志 |
| `Attachments` | `blobs.Store`，存消息带的图片和文件，可以接对象存储 | 用 `AttachmentsDir` |
| `AttachmentsDir`、`SkillsDir`、`Memory` | 本机附件目录（`Attachments` 为空时用）、技能目录、记忆管理器 | 附件不接收，技能与记忆关闭 |

## gateway.Options

| 字段 | 填什么 | 不填时 |
|---|---|---|
| `DB` | 和 agent 同一个 `*repo.DB`，网关直接读它返回不需要 agent 逻辑的视图 | `NewServer` 报错 |
| `Token` | 单用户网关的令牌，属于默认用户 | 必须和 `Authenticate` 二选一 |
| `Authenticate` | `func(token string) (user string, ok bool)`：多用户时由它判断令牌属于谁；登录发生在 Ollupi 之外，这里只核对 | 用 `Token` |
| `AllowedHosts` | 客户端访问网关用的主机名，本机名字之外的 | 只接受本机名字 |
| `AllowedOrigins` | 浏览器客户端的来源 | 只接受 `localhost`、`127.0.0.1`、`[::1]` |
| `Memory`、`Jobs` | 记忆管理器、定时任务表，给 `memory/*`、`cron/*` 方法用 | 这两组方法返回 `-32000`，提示不可用 |
| `MCP` | 每用户的 MCP 服务器，给 `mcpServer/list` 用 | 列表为空 |

## 代码位置

| 仓库 | 路径 | 职责 |
|---|---|---|
| ollupi | `agent/agent.go` | `Config`、`New`、`Start` 里的默认值 |
| ollupi | `gateway/serve.go` | `Options`、`NewServer` |
