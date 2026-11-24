# 待办

待办是用户自己的一份清单，跨着所有项目，比任何一个会话活得长：用户说要做什么，中枢把它记成一条待办，派活时连着会话，做完再标上结果。客户端用 `todo/*` 读写，用 `todo/changed` 跟上变化；谁在写、为什么这样设计见[中枢](/zh/engine/hub)。

```jsonc
// 请求
{"jsonrpc":"2.0","id":7,"method":"todo/list","params":{"limit":20}}
// 结果：空字符串、false 和没结束的 endedAt 都不发
{"jsonrpc":"2.0","id":7,"result":{"data":[
  {"id":3,"title":"把 docs 的引擎页更新到 v0.26.2","status":"handed",
   "workspaceId":"4dc76ecd-1f0a-4c3e-9b52-7a1e0c2d9f41","threadId":"eb2c51e5-6a7d-4b18-8c3f-2d9e5a0b7c16",
   "notes":"先权限后沙箱","createdAt":"2026-11-23T01:12:04Z","updatedAt":"2026-11-23T01:20:11Z"}
]}}
```

## 概念与状态

一条待办有：`title`（标题）、`notes`（备注）、`result`（一行结果）、`status`（状态），以及它链到的会话和会话所在的工作区。

| 状态 | 含义 |
|---|---|
| `open` | 还没交出去 |
| `handed` | 已经交给一个会话在做 |
| `done` | 做完了，`result` 写一行结果 |
| `dropped` | 不做了，原因写在 `notes` |

进入 `done` 或 `dropped` 时记下 `endedAt`；从这两个状态退回 `open` 或 `handed` 时清掉 `endedAt`，行里不再有这个字段。链会话本身不改状态：一条 `open` 的待办也能链着会话，是不是"已交给"由 `status` 说了算；把 `threadId` 设成 `""` 会同时清掉 `workspaceId`。

标题和结果会被压成一行（连续空白并成一个空格），备注保留换行但去掉首尾空白。长度按字符计：标题 200、备注 2000、结果 500。`title` 不能为空，也不能只有空白。

待办的 `id` 在每个用户内从 1 递增，删不掉——只有完成和放弃，没有删除方法。

## 方法

三个方法都只作用于调用者自己的待办，别人的 `id` 与不存在的一样处理。

### todo/list

| 参数 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `statuses` | `TodoStatus[] \| null` | `["open","handed"]` | 要哪些状态；给 `null` 或空数组都是默认的前两种 |
| `limit` | `integer` | 500 | 1 到 2000；超出范围是 `invalidParams` |

返回 `{data, more?}`。顺序固定：没结束的在前，按 `id` 从小到大；结束的在后，按 `endedAt` 从近到远。`more` 为真表示还有没返回的，全部返回时不出现。

第一次读会顺带导入旧版放在 hub 工作区里的 `TODO.md` 与 `done/*.md`，见[中枢](/zh/engine/hub#待办的迁移)。

### todo/add

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `title` | `string` | 是 | 最多 200 字，压成一行 |
| `notes` | `string` | 否 | 最多 2000 字 |

新待办是 `open`，返回 `{todo}`。

### todo/update

| 参数 | 类型 | 说明 |
|---|---|---|
| `id` | `integer` | 要改的待办 |
| `title` | `string \| null` | 不给或给 `null` 表示不改；给空串是 `invalidParams` |
| `status` | `TodoStatus \| null` | 同上；改成 `done` 或 `dropped` 时记 `endedAt` |
| `notes` | `string \| null` | 给 `""` 清空 |
| `result` | `string \| null` | 给 `""` 清空 |
| `threadId` | `string \| null` | 链到一个会话，同时记下它所在的工作区；给 `""` 解除链接 |

只改给出的字段，返回 `{todo}`。`id` 不存在时是 `invalidParams`，错误信息里列出前 20 条待办的 `id` 和标题，方便调用方改正。`threadId` 指向别的用户的会话时同样报错。

## 通知

### todo/changed

任何一次写入之后，所有连着这个用户的客户端都会收到：

```jsonc
{"jsonrpc":"2.0","method":"todo/changed","params":{"todo":{ /* TodoRow */ }}}
```

写入的来源有两种：客户端的 `todo/add`、`todo/update`，以及中枢用工具改待办。事件由存储层在提交后发出，和哪条连接发起的无关，发起方也会收到一份。

## 类型

### TodoRow

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | `integer` | 用户内唯一 |
| `title` | `string` | 一行标题 |
| `status` | `TodoStatus` | `open`、`handed`、`done`、`dropped` |
| `workspaceId?` | `string` | 链着的会话所在的工作区；不链、或会话不在工作区时不出现 |
| `threadId?` | `string` | 链着的会话；不链时不出现 |
| `notes?` | `string` | 备注；为空时不出现 |
| `result?` | `string` | 一行结果；为空时不出现 |
| `createdAt`、`updatedAt` | `string` | RFC 3339 |
| `endedAt?` | `string` | 结束时间；没结束时不出现 |

除 `workspaceId`、`threadId`、`notes`、`result`、`endedAt` 外都是必填字段。

## 错误与边界

- 状态不合法、标题为空或超长、备注或结果超长、`id` 不存在、会话不存在：都是 `invalidParams`（-32602），消息里写清哪一条不对、上限是多少。
- `limit` 超出 1 到 2000 也是 `invalidParams`，不会悄悄夹到边界。
- 没有删除：不要的待办标 `dropped`，它会进"已结束"，仍然查得到。
- 完成不等于验证：`done` 只是一个状态，中枢的规则要求先读会话的答复再标。
- 待办不记录谁改的、什么时候改的细节，只有一个 `updatedAt`。

## 代码位置

| 路径 | 职责 |
|---|---|
| `app/todos.go` | `Todos`、`Todo`、`AddTodo`、`UpdateTodo`；200/2000/500 字上限；进出 `done`、`dropped` 时的 `endedAt` |
| `app/todos_import.go` | 旧 `TODO.md`、`done/*.md` 的一次性导入 |
| `store/sqlite/owned.go` | `todos` 表的读写；列表顺序 `ended_at IS NULL DESC, ended_at DESC, id`；写入后发事件 |
| `store/sqlite/migrations/0012_todos.sql` | 表结构与两个索引 |
| `gateway/owned.go` | `todo/list`、`todo/add`、`todo/update`；默认 500、上限 2000 |
| `gateway/protocol.go`、`gateway/server.go` | 方法注册、`todo/changed` 通知 |
| `tool/builtin/hub/hub.go` | 中枢的 `add_todo`、`update_todo`、`list_todos` |
