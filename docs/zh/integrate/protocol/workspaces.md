# 工作区与执行环境

工作区（workspace）是会话（thread）挂靠的项目文件夹，执行环境（environment）是会话的命令和文件工具在哪台机器上运行。两者都在 `thread/start` 时选定，之后不再改变，客户端用 `workspace/*` 和 `environment/*` 管理它们。工作区和执行环境在引擎里怎样落到沙箱，见[工作区](/zh/engine/workspace)和[按会话选择环境](/zh/integrate/extend#按会话选择环境)。

本页按引擎 v0.17.1 写。示例来自对 v0.17.1 网关的脚本试验（假模型、单用户、本机沙箱），路径和 ID 缩短了。

## 概念与状态

**工作区**是用户沙箱（`Box`）里的一个文件夹，在库里是一行 `WorkspaceRow`：名称、规范化之后的根目录、这一层的权限设置、归档时间。

- 同一个用户的工作区按"是不是同一个文件夹"去重：再添加同一个文件夹（经过不同链接也算）返回已有的那一行，不新建。
- 工作区只能归档，没有删除。归档后不能在里面开新会话，顶层会话也不能开始新的一轮；数据都留着，取消归档或重新添加同一个文件夹就恢复。
- 会话、记忆、定时任务记的是工作区 ID，不是路径，所以 `workspace/move` 搬文件夹时只改根目录这一列。

**执行环境**是一行名字和种类，没有地址、没有凭据，它对应哪台机器由宿主（host）决定：

| `kind` | 是什么 | 数量 | 能否删除 |
|---|---|---|---|
| `local` | 运行引擎的这台机器。工作区就是它里面的文件夹 | 每个用户正好一个，建用户时自动建出，默认名字 `This computer` | 不能 |
| `machine` | 用户的一台云沙箱，宿主在工作区工具的 `BoxIn` 里把它接到一台机器 | 用户自己登记，任意多个 | 没有会话在用时可以 |

一个会话属于至多一个工作区、正好一个执行环境：

| `thread/start` 参数 | 不传时 | 指向不存在或别人的 | 之后能否改 |
|---|---|---|---|
| `workspaceId` | 会话不属于任何工作区（general），命令在宿主配置的默认目录里运行 | `-32004` | 不能 |
| `environmentId` | 这个用户的 `local` 环境 | `-32004` | 不能 |

`workspaceId` 指向已归档的工作区时返回 `-32014`。子 agent 会话的工作区和执行环境都跟父会话相同。`thread/start` 的其余参数见[会话](/zh/integrate/protocol/threads)。

引擎不检查宿主能不能服务一个 `machine` 环境：在没有接入任何云沙箱的宿主上，`thread/start` 带一个 `machine` 环境也会成功，命令最后在哪里跑取决于宿主的 `BoxIn`，见[扩展点](/zh/integrate/extend#按会话选择环境)。

::: info 演进
执行环境是 v0.12.0 加入的（`5f64857`）。在此之前，命令在哪里跑是整个分片的属性，由宿主按用户决定；现在是每个会话开始时选一次。
:::

## 典型流程

下面的消息省略了 `"jsonrpc":"2.0"`。和别的模块一样，写操作的通知先于回复到达，见[连接模型](/zh/integrate/protocol#连接模型)。

添加工作区，得到 `workspace/changed`，再得到回复：

```json
→ {"id":18,"method":"workspace/add","params":{"path":"/var/folders/…/proj"}}
← {"method":"workspace/changed","params":{"workspace":{"id":"fff33a60-…","name":"proj","rootPath":"/private/var/folders/…/proj","settings":{"permissions":{}},"createdAt":"2026-11-18T12:18:42.820344Z","updatedAt":"2026-11-18T12:18:42.820344Z"}}}
← {"id":18,"result":{"workspace":{"id":"fff33a60-…","name":"proj","rootPath":"/private/var/folders/…/proj", …}}}
```

`rootPath` 是规范化之后的路径：macOS 上 `/var` 是到 `/private/var` 的链接，本机沙箱会解析链接。客户端要用返回的 `rootPath`，不要用自己传进去的 `path`。

再添加同一个文件夹，换个名字。返回的是已有的那一行，名字没变，也没有通知：

```json
→ {"id":19,"method":"workspace/add","params":{"path":"/var/folders/…/proj","name":"other"}}
← {"id":19,"result":{"workspace":{"id":"fff33a60-…","name":"proj", …}}}
```

登记一个云沙箱，在它里面开会话，再试图删除它：

```json
→ {"id":30,"method":"environment/add","params":{"name":"Build box"}}
← {"method":"environment/changed","params":{"environmentId":"7e8420cc-…","environment":{"id":"7e8420cc-…","name":"Build box","kind":"machine","createdAt":"2026-11-18T12:18:42.82286Z","updatedAt":"2026-11-18T12:18:42.82286Z"}}}
← {"id":30,"result":{"environment":{"id":"7e8420cc-…","name":"Build box","kind":"machine", …}}}
→ {"id":36,"method":"thread/start","params":{"environmentId":"7e8420cc-…"}}
← {"method":"thread/changed","params":{"threadId":"157e4388-…","thread":{"id":"157e4388-…","environmentId":"7e8420cc-…","title":"","settings":{"permissions":{}},"status":"idle", …},"seq":13}}
← {"id":36,"result":{"thread":{ … }}}
→ {"id":37,"method":"environment/delete","params":{"environmentId":"7e8420cc-…"}}
← {"id":37,"error":{"code":-32602,"message":"environment GPU box: a conversation runs in the environment"}}
```

（第 37 条之前这个环境被改名成了 `GPU box`。）

## 工作区的方法

以下方法的写操作成功时都发 `workspace/changed`，载荷是写之后的整行；工作区不存在或属于别的用户时都返回 `-32004`，比如 `store: workspace <id>: store: not found`。

### workspace/list

| 参数 | 无 |
|---|---|
| 结果 | `data: WorkspaceRow[]` |

列出这个用户的全部工作区，包括已归档的（看 `archivedAt`），按 `name` 排序，相同时按 `id`。

### workspace/add

| 参数 | 类型 | 说明 |
|---|---|---|
| `path` | string | 用户沙箱里的文件夹，经宿主 `host.Config.Boxes` 给这个用户的 Box 规范化：本机解析链接，云沙箱只做路径清理并要求绝对路径 |
| `name?` | string | 去掉首尾空白后 1 到 120 字符；不传时取文件夹名 |

结果是 `workspace: WorkspaceRow`。

| 情况 | 结果 |
|---|---|
| 没有同一个文件夹的工作区 | 新建，发 `workspace/changed` |
| 已有，未归档 | 返回已有的那一行，`name` 不生效，**不发**通知 |
| 已有，已归档 | 取消归档后返回，发 `workspace/changed` |
| 路径不存在或不是文件夹 | `-32602` `invalid path: directory "…" is unavailable: …` |
| 名称为空白或超过 120 字符 | `-32602` `invalid name: a workspace name must be 1 to 120 characters` |
| `Boxes` 返回错误 | `-32000`，详情只在服务端日志 |

添加时不检查这个文件夹能不能作为命令目录。本机 Seatbelt 沙箱下把用户主目录加成工作区会成功，但之后这个工作区里的每次工具调用都会失败，见[工作区的边界](/zh/engine/workspace#边界与已知问题)。

### workspace/rename

| 参数 | 类型 | 说明 |
|---|---|---|
| `workspaceId` | string | |
| `name` | string | 去掉首尾空白后 1 到 120 字符，否则 `-32602` |

结果是 `workspace`。只改名称，不动文件夹。

### workspace/move

| 参数 | 类型 | 说明 |
|---|---|---|
| `workspaceId` | string | |
| `path` | string | 目标文件夹，必须已经存在且为空 |

结果是 `workspace`，`rootPath` 换成新位置。

引擎按这个顺序处理，任何一步不满足就停下：

| 步骤 | 不满足时 |
|---|---|
| 规范化 `path`，它必须存在、是文件夹 | `-32602` `invalid path: …` |
| 工作区存在、属于这个用户 | `-32004` |
| 工作区里没有不空闲的会话（进行中、排队或在等审批、等回答），也没有另一次搬家在进行 | `-32016` `workspace <名称>: a conversation in the workspace has a turn in progress or queued; interrupt it first` |
| `path` 和当前根目录是同一个文件夹 | 直接返回当前这一行，什么都不做，**不发通知** |
| `path` 不在工作区自己里面 | `-32602` `… is inside the workspace` |
| `path` 为空 | `-32602` `… is not empty` |
| `path` 不是另一个工作区的文件夹 | `-32602` `… is the folder of the workspace …` |
| 经用户的 `Box.Move` 搬过去：本机是 `os.Rename`，云沙箱是机器里的 `mv` | `-32000` |
| 把库里的根目录改成新位置 | 引擎把文件夹搬回原处，返回 `-32000`；搬回也失败时，服务端日志里的错误同时写明文件夹现在在哪、工作区还指着哪 |

搬家期间，这个工作区里的会话不能开始新的一轮，`turn/start` 返回 `-32016` `workspace <名称> is moving: …`。最后两行的错误不在错误码表里，客户端只收到 `-32000` `the request could not be completed`，详情只在服务端日志里，见[错误码](/zh/integrate/protocol#错误码)。

::: info 演进
`workspace/move` 是 v0.11.0 加入的（`d63435b`）。在此之前根目录是工作区唯一改不了的列，用户在访达里挪了文件夹，所有会话就都指向一个不存在的路径。
:::

### workspace/archive

| 参数 | 类型 | 说明 |
|---|---|---|
| `workspaceId` | string | |
| `archived` | boolean | 必填，`true` 归档、`false` 取消归档；不传时 `-32602` `archived is required` |

结果是 `workspace`。归档后：

| 操作 | 结果 |
|---|---|
| `thread/start` 带这个 `workspaceId` | `-32014` `workspace Demo: the workspace is archived; restore it before starting new work` |
| 这个工作区里的顶层会话 `turn/start` | `-32014` |
| 这个工作区里的定时任务到点 | 开不了一轮，这次到点作废，见[定时任务](/zh/integrate/protocol/cron) |
| 子 agent 会话的轮次 | 不检查，照常运行 |
| 已有会话的读取、列表、搜索 | 不受影响 |

归档不要求工作区里的会话空闲。

### workspace/updatePermissions

| 参数 | 类型 | 说明 |
|---|---|---|
| `workspaceId` | string | |
| `approvalPolicy?` | `ApprovalPolicy` | |
| `permissions` | `PermissionRules` | |

整体替换工作区这一层的权限设置，结果是 `workspace`。设置先和部署默认层、用户层合并校验，不合法时 `-32602`，比如规则引用了一个还没连上的 MCP 服务器的工具：

```text
-32602 invalid permission settings: the permission settings of workspace "Demo": permission rule "broken__new_tool": the MCP server "broken" is not connected, so its tools cannot be checked now; add this rule once it is connected
```

字段的含义、各层怎样叠加、"总是允许"怎样写进这一层，见[权限](/zh/integrate/protocol/permissions)。

## 执行环境的方法

以下方法的写操作成功时都发 `environment/changed`。环境不存在或属于别的用户时返回 `-32004`。

### environment/list

| 参数 | 无 |
|---|---|
| 结果 | `data: EnvironmentRow[]` |

`local` 环境排第一，其余按 `createdAt` 排序，相同时按 `id`。

### environment/add

| 参数 | 类型 | 说明 |
|---|---|---|
| `name` | string | 去掉首尾空白后 1 到 120 字符，同一用户内不分大小写地唯一 |
| `kind?` | `EnvironmentKind` | 只能是 `machine`，不传时也是 `machine` |

结果是 `environment: EnvironmentRow`，`id` 是 UUID，发 `environment/changed`。

| 情况 | 结果 |
|---|---|
| 名称为空白或超过 120 字符 | `-32602` `invalid name: an environment name must be 1 to 120 characters` |
| 和已有环境同名，不分大小写（试验里 `build BOX` 对 `Build box`） | `-32602` `invalid name: you already have an environment called "Build box"` |
| `kind` 是 `local` | `-32602` `invalid name: this machine is one environment and every user has it; name a cloud sandbox instead` |
| `kind` 是别的值 | `-32602` `invalid name: an environment is "machine", not "cloud"` |

### environment/rename

| 参数 | 类型 | 说明 |
|---|---|---|
| `environmentId` | string | |
| `name` | string | 去掉首尾空白后 1 到 120 字符 |

结果是 `environment`。和这个用户的另一个环境同名（不分大小写）时 `-32602`，比如把云沙箱改名成 `this computer`：`invalid name: you already have an environment called "This computer"`。`local` 环境也可以改名。

### environment/delete

| 参数 | 类型 | 说明 |
|---|---|---|
| `environmentId` | string | |

结果是 `{}`。

| 情况 | 结果 |
|---|---|
| `machine` 环境，没有会话在用 | 删除，发 `environment/changed`，其中 `environment` 为 `null` |
| `local` 环境 | `-32602` `invalid name: This computer is this machine, whose folders the workspaces are`（名字是这个环境当前的名字） |
| 有会话在这个环境里，包括已归档的会话和子 agent 会话 | `-32602` `environment <名字>: a conversation runs in the environment` |

会话不会换环境，所以一个被用过的环境要等用它的会话全部删除之后才能删。

::: info 演进
v0.12.1 的 `environment/add` 遇到同名环境时返回已有的那一行，`environment/delete` 返回删掉的那一行，`workspace/add` 对已有的工作区也发通知。`d110977` 把每个操作改成一次检查加一个事务，同名环境直接拒绝；`9b5b50b` 让通知只来自存储的变更流，没写库就没有通知，`environment/delete` 也改成返回 `{}`。
:::

## 通知

| 通知 | 载荷 | 何时发 |
|---|---|---|
| `workspace/changed` | `workspace: WorkspaceRow` | `workspace/add`（真的新建或取消归档时）、`rename`、`move`（真的搬了时）、`archive`、`updatePermissions` 成功之后；`acceptAlways` 把规则写进工作区时也发，见[权限](/zh/integrate/protocol/permissions#总是允许) |
| `environment/changed` | `environmentId`、`environment: EnvironmentRow \| null` | `environment/add`、`rename`、`delete` 成功之后；`environment` 为 `null` 表示已删除 |

两种通知都来自存储的变更流，事务提交之后发给这个用户的每一条连接，载荷是写之后的整行，客户端按 `id` 整行替换。`workspace/changed` 没有"已删除"的形式，因为工作区不能删除。

## 类型

### WorkspaceRow

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | string | UUID |
| `name` | string | 1 到 120 字符，不能为空白 |
| `rootPath` | string | 用户沙箱里规范化之后的绝对路径，同一用户内唯一 |
| `settings` | `PermissionSettings` | 工作区这一层的权限设置：`approvalPolicy?` 和 `permissions`，见[权限](/zh/integrate/protocol/permissions#permissionsettings) |
| `createdAt`、`updatedAt` | string | RFC 3339 UTC |
| `archivedAt?` | string \| null | 归档时间，不出现表示未归档。归档时取那一刻的 `updatedAt` |

### EnvironmentRow

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | string | 格式不固定：新建的是 UUID；从旧版数据库导入的 `local` 环境可能是 32 位十六进制。客户端不要假设 ID 的格式 |
| `name` | string | 1 到 120 字符，同一用户内不区分大小写地唯一。`local` 环境默认叫 `This computer` |
| `kind` | `EnvironmentKind` | `local` 或 `machine`，见[概念与状态](#概念与状态) |
| `createdAt`、`updatedAt` | string | 精度不固定：导入的旧行可能只到毫秒，其余到纳秒 |

`EnvironmentRow` 不带地址或凭据。宿主要自己保存"哪个环境对应哪台机器"。

::: info 演进
ID 和时间精度不一，是因为升级到 v0.12.0 时 migration 0007 在 SQL 里给已有用户各补了一个 `local` 环境：ID 用 `lower(hex(randomblob(16)))`，时间用 `strftime` 写到毫秒。v0.16.1 在第一次打开旧数据时把这些行原样导入新库（`28ffcc8`，代码在 `store/sqlite/legacy.go`）。
:::

### EnvironmentKind

字符串枚举：`local`、`machine`。

### 参数类型

`WorkspaceAddParams`、`WorkspaceRenameParams`、`WorkspaceMoveParams`、`WorkspaceArchiveParams`、`WorkspacePermissionsParams`、`EnvironmentAddParams`、`EnvironmentRenameParams`、`EnvironmentDeleteParams` 的字段就是上面各方法的参数表；结果类型 `WorkspaceListResult`、`WorkspaceResult`、`EnvironmentListResult`、`EnvironmentResult` 只是包了一层 `data` 或 `workspace`、`environment`。通知类型是 `WorkspaceResult` 和 `EnvironmentChangedNotification`。

## 错误与边界

| 错误码 | 本模块里的触发条件 |
|---|---|
| `-32602` | 缺必填参数；路径无效、不为空、在工作区里面或已是别的工作区；名称不合法或重名；`kind` 不合法；删 `local` 环境或在用的环境；权限设置不合法 |
| `-32004` | 工作区或环境不存在，或属于别的用户（ID 为空也是这样）；`thread/start` 的 `workspaceId`、`environmentId` 也一样 |
| `-32014` | 在已归档的工作区里开会话或开始新的一轮 |
| `-32016` | `workspace/move` 时工作区里有会话不空闲，或另一次搬家在进行；搬家期间在这个工作区里开始新的一轮 |
| `-32000` | `Boxes` 失败、`Box.Move` 失败、搬家后改库失败 |

边界：

- **工作区按用户的 Box 校验。** `workspace/add` 和 `workspace/move` 经 `host.Config.Boxes(user)` 校验路径。会话在 `machine` 环境里运行时，它的工作区路径要在那台机器上也解析到同一个路径，否则每次工具调用都失败，见[工作区的边界](/zh/engine/workspace#边界与已知问题)。
- **"同一个文件夹"由 Box 判断。** 本机按文件身份判断，经过链接到达的同一个文件夹算一个；云沙箱只比较路径字符串。
- **环境不校验可达。** 引擎不知道 `machine` 环境对应哪台机器，也不检查宿主能不能服务它。宿主的 `BoxIn` 对一个环境返回错误时，这个会话的每次命令和文件调用都失败，错误前缀是 `workspace: the environment of the conversation:`。

## 代码位置

| 路径 | 职责 |
|---|---|
| `gateway/owned.go` | `workspace/*`、`environment/*` 的处理函数，`archived` 必填的检查 |
| `gateway/server.go` | 把变更流里的事件转成 `workspace/changed`、`environment/changed` |
| `gateway/protocol.go` | 参数和结果类型、方法表 |
| `gateway/wire.go` | `WorkspaceRow`、`EnvironmentRow` |
| `app/owned.go` | `AddWorkspace`、`RenameWorkspace`、`MoveWorkspace`、`ArchiveWorkspace`、`AddEnvironment`、`RenameEnvironment`、`DeleteEnvironment` |
| `app/settings.go` | `UpdateWorkspacePermissions` |
| `app/threads.go` | `StartThread` 选工作区和环境 |
| `app/turns.go` | `usableWorkspace`：归档和搬家中的工作区不能开始新的一轮 |
| `account/account.go` | `Workspace`、`Environment`、`EnvironmentKind`、名称规则 |
| `store/sqlite/owned.go` | `workspaces`、`environments` 两张表的读写和排序、`WorkspaceBusy`、`EnvironmentInUse` |
| `tool/builtin/workspace/dirs.go` | 工具按会话的环境经 `BoxIn` 选 Box |
