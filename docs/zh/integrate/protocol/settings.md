# 设置

用户级的设置：发给模型之前要不要脱敏，记忆开不开，要不要从新的轮次里学新记忆，以及用户自己的一层权限。客户端用 `settings/read` 读、`settings/update` 改三个开关、`settings/updatePermissions` 改权限，用 `settings/changed` 跟上。脱敏识别什么、怎样替换和还原，见[脱敏](/zh/engine/redaction)；记忆怎样提炼和载入，见[记忆](/zh/integrate/protocol/memory)。

本页按引擎 v0.17.1 写，示例来自对 v0.17.1 网关的脚本试验。

## 概念与状态

- **每个用户一行。** 设置跟着用户走，同一分片上不同用户各有各的。建用户时就有这一行：`redaction`、`memory`、`learn` 都是 `true`，`permissions` 是空的一层 `{"permissions":{}}`。
- **三个开关：**

| 开关 | 默认 | 关掉之后 |
|---|---|---|
| `redaction` | `true` | 发给模型的请求不再脱敏，包括后台提炼记忆时的请求 |
| `memory` | `true` | 会话不再载入记忆，模型拿不到 `memory_search` 工具，后台也不再提炼：这期间结束的轮次被跳过，以后也不会补学 |
| `learn` | `true` | 只停提炼：这期间结束的轮次被跳过，以后也不会补学；已有的记忆照样载入、照样能搜 |

- **立即生效，包括正在跑的一轮。** 引擎每次调用模型之前都重新读这一行，所以 `redaction` 和 `memory` 的切换从这一轮的下一步起生效。重新打开 `memory` 或 `learn` 之后，提炼从那以后结束的轮次学起。
- **只影响以后发出去的请求。** 已经存下的模型回答不随 `redaction` 改变，里面已有的占位符保持原样，见[开关](/zh/engine/redaction#开关)。
- **开关之外还要宿主配置。** 记忆提炼要宿主在 `host.Config.Memory` 里给一个提炼用的模型，没给时 `memory` 和 `learn` 开着也不会提炼，见[记忆](/zh/integrate/protocol/memory)。
- **权限是四层中的一层。** `permissions` 夹在部署默认和工作区之间，怎样叠加、怎样校验见[权限](/zh/integrate/protocol/permissions)。

::: info 演进
v0.12.1 只有 `redaction` 一项，记忆的开关和权限都是宿主的配置。`1ae27b2` 把记忆开关和用户的一层权限存进每个用户的设置，加了 `settings/updatePermissions`。`1681a3d` 把"学新记忆"从记忆开关里拆出来，成了 `learn`，migration 0003 给每个用户补上 `learn = 1`。
:::

## 典型流程

读一次，关掉学习，再同时关掉记忆、打开脱敏：

```json
→ {"jsonrpc":"2.0","id":2,"method":"settings/read","params":{}}
← {"jsonrpc":"2.0","id":2,"result":{"redaction":true,"memory":true,"learn":true,"permissions":{"permissions":{}}}}
→ {"jsonrpc":"2.0","id":3,"method":"settings/update","params":{"learn":false}}
← {"jsonrpc":"2.0","method":"settings/changed","params":{"redaction":true,"memory":true,"learn":false,"permissions":{"permissions":{}}}}
← {"jsonrpc":"2.0","id":3,"result":{"redaction":true,"memory":true,"learn":false,"permissions":{"permissions":{}}}}
→ {"jsonrpc":"2.0","id":5,"method":"settings/update","params":{"memory":false,"redaction":true}}
← {"jsonrpc":"2.0","method":"settings/changed","params":{"redaction":true,"memory":false,"learn":false,"permissions":{"permissions":{}}}}
← {"jsonrpc":"2.0","id":5,"result":{"redaction":true,"memory":false,"learn":false,"permissions":{"permissions":{}}}}
```

一个开关都不给时被拒：

```json
→ {"jsonrpc":"2.0","id":4,"method":"settings/update","params":{}}
← {"jsonrpc":"2.0","id":4,"error":{"code":-32602,"message":"give redaction, memory or learn"}}
```

和别的写方法一样，`settings/changed` 排在回复之前。改权限的例子见[权限](/zh/integrate/protocol/permissions#改用户的权限)。

## 方法

### settings/read

无参数，结果是 [`SettingsRow`](#类型-settingsrow)。不需要宿主额外配置。

### settings/update

| 参数 | 类型 | 说明 |
|---|---|---|
| `redaction?` | boolean | 不给表示不改 |
| `memory?` | boolean | 不给表示不改 |
| `learn?` | boolean | 不给表示不改 |

至少给一个。只改给了的那几个，别的保持原样，所以两个客户端同时改不同的开关不会互相覆盖。结果是更新后的整个 `SettingsRow`，同时发 `settings/changed`。值没有变也照样写、照样发。

| 错误 | 什么时候 |
|---|---|
| `-32602` `give redaction, memory or learn` | 三个都没给，或都是 `null` |
| `-32602` | 给了不认识的字段 |

### settings/updatePermissions

整体替换用户这一层的权限，结果是 `SettingsRow`，发 `settings/changed`。参数、校验和错误见[权限](/zh/integrate/protocol/permissions#settings-updatepermissions)。

## 通知：settings/changed

载荷就是 `SettingsRow`。`settings/update` 和 `settings/updatePermissions` 成功后各发一条，在事务提交之后、回复之前，发给这个用户的每一条连接。一个用户默认最多同时有 4 条连接（`gateway.DefaultConnections`），别的客户端改了设置，这条通知也会到；客户端按载荷整行替换本地状态即可。

## 类型：SettingsRow

| 字段 | 类型 | 说明 |
|---|---|---|
| `redaction` | boolean | 是否在发给模型之前脱敏 |
| `memory` | boolean | 记忆开关：载入、搜索工具和提炼 |
| `learn` | boolean | 是否从结束的轮次里提炼新记忆；`memory` 关着时不起作用 |
| `permissions` | [`PermissionSettings`](/zh/integrate/protocol/permissions#permissionsettings) | 用户这一层的权限 |

`SettingsUpdateParams` 就是上面 `settings/update` 的参数表，三个字段都可以是 `null`。库里这一行还有脱敏占位符用的密钥，从不发给客户端。

## 错误与边界

- **`memory` 关掉不影响 `search` 和 `memory/*`。** 客户端照样能列出、搜索、编辑记忆，只是会话不再用它们。
- **跳过的轮次不补学。** `memory` 或 `learn` 关着时结束的轮次，提炼在读到时直接跳过，重新打开也不会回头去学。所以宿主配了提炼模型时，关着期间 `memory/status` 的 `unread` 也会回落到 0，见[记忆](/zh/integrate/protocol/memory#memorystatus)。
- **没有并发保护。** `settings/updatePermissions` 整体替换权限，两个客户端先后读、改、写，后写的覆盖先写的。

## 代码位置

| 路径 | 职责 |
|---|---|
| `gateway/owned.go` | `settingsRead`、`settingsUpdate`（至少一个开关）、`settingsPermissions` |
| `gateway/protocol.go` | `SettingsUpdateParams`、`SettingsPermissionsParams` |
| `gateway/wire.go` | `SettingsRow` |
| `app/settings.go` | `UpdateSettings`：只改给了的开关；`UpdateUserPermissions` |
| `account/account.go` | `Settings`；`memory` 关掉时用户层去掉 `memory` 提供方 |
| `store/sqlite/owned.go` | 建用户时的默认值，`SetSettings` 写行并发出 `settings/changed` 的事件 |
| `store/sqlite/migrations/0003_learn.sql` | `settings.learn`，默认 1 |
| `run/model.go` | 每次调用模型前按 `memory` 决定载不载入记忆，按 `redaction` 决定脱不脱敏 |
| `extract/extract.go` | `memory` 或 `learn` 关着时跳过结束的轮次；提炼请求按 `redaction` 脱敏 |
