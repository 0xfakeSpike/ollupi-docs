# 搜索

Ollupi 有三条互不相干的搜索路径：查自己的会话、消息、定时任务和记忆（协议的 `search` 方法），查工作区里的文件（模型用的 `grep` 和 `glob` 工具），查网页（没有）。三者匹配方式、索引和权限各不相同，遇到“搜不到”先确认是哪一条。

## 为什么这样设计

- **一个方法查四类对象。** 界面的搜索框只发一次请求，引擎在同一个读事务里查会话标题、消息、定时任务和记忆，每类各取 `limit` 条，界面自己分组。
- **子串匹配，不做分词。** 消息用 `LIKE '%词%'` 定义命中，FTS5 的 trigram 索引只用来缩小范围。中文、代码片段、带 `%` 和 `_` 的词都按字面匹配，不依赖分词器。
- **查询有边界。** 查询长度、词数和执行时间都有上限，一次搜索不会长时间占着分片的库；短于 3 个字符的词不走索引，只扫调用者自己的消息。
- **只查调用者自己的数据。** 参数里没有用户，用户来自连接的身份；一个用户只放在一个分片，不需要跨分片合并（见[分片与多用户](/zh/engine/sharding)）。

代价：没有相关度排序、分页和命中总数；会话只按标题匹配；不搜工具输出和思考内容。

## 三条路径

| 查什么 | 谁执行 | 入口 | 匹配方式 | 索引 |
| --- | --- | --- | --- | --- |
| 会话标题、消息正文、定时任务、记忆 | `app.Search` → `store.Reader.Search` 加 `memory.Search` | JSON-RPC `search` | 子串 `LIKE`；记忆按词打分 | FTS5 表 `items_search`，只用于消息 |
| 工作区文件的内容和路径 | 工作区工具 `grep`、`glob` | 模型调用工具 | `grep` 用 Go RE2 正则，`glob` 用路径模式 | 没有，逐目录遍历 |
| 网页 | — | — | — | — |

网页这一行是空的：`tool/builtin/web` 只提供 `web_fetch`，读一个给定的 URL（见[工具系统](/zh/engine/tools)），请求经用户的 `Box` 发出——本机的 `Box` 走系统代理，先读 `HTTP_PROXY`/`HTTPS_PROXY`，没配时读系统的代理设置；代码里没有搜索 API 的提供者，也没有搜索引擎的配置项和密钥。要让模型“搜网页”，只能先给它一个网址。

## 会话、消息、任务与记忆：`search`

一次 `search` 覆盖四类对象，没有按对象拆开的方法。网关的 `conn.search` 先校验 `limit`，再调 `app.Search`；前三类在一个读事务里由 `store/sqlite` 的 `Search` 查，记忆在同一个事务里读出来后由 `memory.Search` 打分。

### 参数

| 参数 | 类型 | 默认 | 约束 |
| --- | --- | --- | --- |
| `query` | string | 必填 | 按空白切成词（`strings.Fields`）；切不出词时返回 `-32602`（`invalid query: query is required`）；超过 200 个字符或 8 个词时返回 `-32602` |
| `workspaceId` | string | 空 | 空等于不限定工作区 |
| `limit` | integer | 20 | 1 到 100（`defaultLimit` 与 `maxLimit`），越界返回 `-32602`；**每一类**各取这么多条 |

200 和 8 这两个上限（`app.MaxSearchRunes`、`app.MaxSearchTerms`）写在协议契约 `protocol.schema.json` 的 `limits.searchRunes`、`limits.searchTerms` 里，客户端可以照着在发送前拦住。

整次查询限时 5 秒（`searchTimeout`），读事务带着这个期限；超时返回 `-32017`（`searchTimedOut`），提示换更长或更少的词。

### 匹配条件

每个词各加一条条件，所以多个词是 AND：每个词都要命中。词内不做词干、不做近义词、不做前缀扩展。

| 类别 | 匹配的列 | 其他过滤 | 排序 | 上限 |
| --- | --- | --- | --- | --- |
| 会话 | `threads.title` | `user_id` 是调用者，`parent_id IS NULL`（只要顶层会话；归档的也算） | `updated_at DESC, id` | `limit` |
| 消息 | `items.text` | `text` 非空（只有 `userMessage` 和 `agentMessage` 写这一列），所属会话属于调用者且是顶层会话 | `at DESC, id` | `limit` |
| 定时任务 | `cron_jobs.name \|\| ' ' \|\| cron_jobs.prompt` | 任务所属会话属于调用者（暂停的任务、归档会话的任务也在） | `created_at DESC, id` | `limit` |
| 记忆 | `memories.topic` 与 `memories.text`，在 Go 里打分 | `status` 是 `active` | 分数降序，同分按 `updated_at DESC, id` | `limit` |

`workspaceId` 非空时前三类都再加一条 `<列> = ?`：会话看 `threads.workspace_id`，消息和任务看所属会话的；不属于任何工作区（general）的会话、消息、任务在这个过滤下不出现。记忆查全局记忆加这个工作区的记忆，不查 general 记忆，和这个工作区的会话实际载入的一致；不带 `workspaceId` 时查用户的全部记忆。

::: info 演进
`b9b330f` 重写搜索时，带 `workspaceId` 的记忆只查这个工作区，漏掉了用户在哪里都看得到的全局记忆。`8328c82` 让它同时查全局和这个工作区。
:::

### 返回

`SearchResult` 嵌入 `Found`，所以四个数组是平铺的：`threads`、`messages`、`cronJobs`、`memories`。没有命中时是空数组，不是 `null`。

| 数组 | 元素 | 带什么 |
| --- | --- | --- |
| `threads` | `ThreadRow` | 整行，含 `title`、`workspaceId`、归档时间；没有命中片段 |
| `messages` | `MessageHit` | `threadId`、`title`（会话标题）、`itemId`、`turnId`、`seq`、`type`、`snippet`、`at` |
| `cronJobs` | `CronJobRow` | 任务整行，加 `threadTitle`、`workspaceId`、`threadArchived`、`lastTurnId`、`lastRunAt` |
| `memories` | `MemoryRow` | 记忆整行，含 `topic`、`text`、`kind`、`scope`、`status`、`sources` |

`snippet` 由引擎生成，只围绕**第一个词**：在正文里按 Unicode 小写找到第一个词，取前后各 40 个字符（`snippetRunes`），把空白折叠成单个空格，两端被截断时加 `…`。所以片段一定含第一个词，其余词可能不在其中。高亮不在引擎里，引擎只返回原样的 `snippet`。字段的协议定义见[搜索协议](/zh/integrate/protocol/search)。

::: info 演进
- 以前查询没有长度、词数和时间的上限，短词也走索引。`6ecaaea` 加上 200 个字符、8 个词和 5 秒的上限，短于 3 个字符的词只扫调用者自己的消息。
- 定时任务那一组的协议字段以前叫 `tasks`，代码里早已叫 cron job（`store.Found.CronJobs`）。`d43d78b`（v0.17.2）把字段改成 `cronJobs`，协议契约的 sha256 随之改变，客户端要读新名字。
:::

## 索引与一致性

消息的索引是一张 FTS5 external content 表，和 `items` 一起建在 `0001_init.sql` 里：

```sql
CREATE VIRTUAL TABLE items_search USING fts5(text, content='items', content_rowid='rowid', tokenize='trigram');
```

`items.text` 只在条目第一次写入时填，而且只有 `userMessage` 和 `agentMessage` 填；其他条目这一列是空串。索引由两个触发器维护：

| 触发器 | 时机 | 做什么 |
| --- | --- | --- |
| `items_search_insert` | `items` 插入且 `text` 非空 | 写入 `rowid` 和 `text` |
| `items_search_delete` | `items` 删除且 `text` 非空 | 从索引里删掉这一行 |

没有更新触发器，也不需要：对话日志的条目写下就不变，条目行之后的更新只改状态和 `body`，不改 `text`（见[持久化](/zh/engine/persistence)）。

- 正在流式输出的回答搜不到：流式的片段不写进日志；回答写成 `AgentMessage` 条目时整段进索引。
- 删除会话时条目被级联删除，触发器把它们从索引里去掉。
- 重启不重建：索引和触发器都在库里。
- `items` 的主键是 `(thread_id, id)`，没有 `INTEGER PRIMARY KEY`，索引靠 `rowid` 回读原文。`VACUUM` 可能重新编号这类表的 `rowid`，之后必须重建索引；代码里不对 `store.sqlite` 执行 `VACUUM`，也没有重建语句。

查询这样用索引，每个词一组：

```sql
i.text LIKE ? ESCAPE '\'                                   -- 每个词都有
i.rowid IN (SELECT rowid FROM items_search WHERE text LIKE ?) -- 只有 3 个字符以上的词有
```

trigram 索引查不了短于 3 个字符的词，所以短词只靠第一个条件，在调用者自己的顶层会话的消息里逐行比较。索引子查询故意不带 `ESCAPE`：它只把结果缩成超集，词里的 `%` 和 `_` 会被当成通配符；第一个条件由 `likePattern` 转义 `\`、`%`、`_`，精确定义命中。所以 `100%`、`super_agent` 这类词按字面匹配。

`store/sqlite/fts5.go` 在没有 `sqlite_fts5` 或 `fts5` 构建标签时让编译失败，因为 `items_search` 需要 FTS5。

::: info 演进
以前索引由 `0004` 迁移建在旧库上，只收状态为 `completed` 的消息，另有一个更新触发器跟着改正文和状态。v0.16.0 换成以对话日志为中心的新库，`87702d3` 在新库的建表里重建了 `items_search`：条目写下不变，只剩插入和删除两个触发器。
:::

### 大小写、中文、宽度

- 大小写：命中由 `LIKE` 决定，代码没有设置 `case_sensitive_like`，所以按 SQLite 的默认：ASCII 字母不区分大小写，其他字符的大小写不折叠。
- 中文：消息不需要分词。两个汉字的词不走索引，逐行 `LIKE` 也能命中；三个字以上的词先过 trigram 索引再过 `LIKE`。
- 全角半角、繁体简体、拼音、变音符号：不归一化。`Ａ` 与 `A`、`臺` 与 `台` 互不命中，代码里没有这类处理。

## 文件搜索：`grep` 和 `glob`

这两个是模型用的工作区工具，不属于 `search` 方法；工具的总览见[工具系统](/zh/engine/tools)，工作区的读写见[工作区](/zh/engine/workspace)。

| 工具 | 参数 | 匹配 |
| --- | --- | --- |
| `grep` | `pattern`（RE2）、`path`、`include`、`ignore_case`、`files_only`、`context`（0 到 10） | 逐行正则匹配，可返回上下文行 |
| `glob` | `pattern`、`path` | 路径模式（doublestar）：`*`、`**`、`?`、`[...]`、`{a,b}`；结果新的在前 |

| 上限 | 值 | 越过时 |
| --- | --- | --- |
| `glob` 返回的文件数 | 500（`maxGlobFiles`） | 标 `truncated` |
| `grep` 保留的匹配行 | 300（`maxGrepLines`） | 标 `truncated`，停止遍历 |
| `grep` 返回的文件数（`files_only`） | 500（`maxGrepFiles`） | 标 `truncated` |
| 单个文件大小 | 8 MiB（`maxGrepBytes`） | 跳过 |
| 每行字符数 | 500（`maxGrepRunes`） | 截断 |
| 一次遍历的条目数 | 200000（`maxWalkEntries`） | 标 `truncated` |

两者共用一个 walker：跳过 `.git`、`.gitignore` 与 `.git/info/exclude` 忽略的文件（go-git 的匹配器）、非文本文件；`Box.CheckRead` 不让读的计入 `skipped`。凭据文件和 agent 自己的数据即使在全权（full access）下也不读。

两者都标了只读、`OpenWorldHint` 为假，审批策略在 `on-request` 和 `untrusted` 下都不提问（`policy.Checker.requiresApproval`）。它们给出 `Content`，规则可以按路径写说明符，路径按小写匹配，例如 `grep(src/*)`，见[审批与权限](/zh/engine/permissions)。

工具输出的截断分几层（工具自己的上限、工具集的 1 MiB、上下文预算），见[工具系统](/zh/engine/tools)和[上下文管理](/zh/engine/context)。

## 记忆搜索的两个入口

`search` 的 `memories` 由 `memory.Search` 填；模型另有一个 `memory_search` 工具，上限 20 条，`query` 至少 2 个字符，查全局和本会话范围。两者共用 `searchTerms`：连续汉字切成相邻两字的重叠组合（`等待中的` → `等待`、`待中`、`中的`），其他字符按字母、数字、`_`、`-` 组词，至少 2 个字符，去重，最多 512 个。打分与排序见[记忆](/zh/engine/memory#搜索)。

两者都带上全局记忆，差别在另一半：`memory_search` 查本会话所在的范围（它的工作区，或 general）；`search` 带 `workspaceId` 时查那个工作区，不带时查用户的全部范围。

## 桌面端

桌面端的搜索页和记忆页搜索框都调这个 `search` 方法，界面怎么发请求、怎么分组、怎么高亮和定位见[渲染进程](/zh/desktop/renderer#搜索)。

## 已知限制

| 限制 | 依据 |
| --- | --- |
| 消息只搜 `userMessage` 和 `agentMessage` | `items.text` 只为这两类填写，查询要求 `text <> ''` |
| 不搜工具调用、工具结果、思考内容、压缩摘要、错误、附件内容 | 同上，索引只有 `items.text` |
| 子 agent 会话和它里面的消息搜不到 | 会话和消息的条件里有 `parent_id IS NULL` |
| 只搜调用者自己的数据，参数里没有用户 | `app.Search` 的用户来自连接 |
| 不支持正则、模糊匹配、词形变化 | `LIKE '%词%'` |
| 会话只按标题匹配，不按会话内容匹配 | `title LIKE ?` |
| 查询最多 200 个字符、8 个词，超过直接拒绝 | `app.MaxSearchRunes`、`app.MaxSearchTerms` |
| 超过 5 秒返回 `searchTimedOut`，没有部分结果 | `searchTimeout` |
| 没有分页、游标和命中总数 | `SearchParams` 只有 `query`、`workspaceId`、`limit` |
| 不做全角半角、繁简、拼音、变音符号归一化 | 代码里没有这类处理 |
| 单个汉字查不到记忆，也调不通 `memory_search` | `searchTerms` 只产出两字以上的词；`memory_search` 的 `query` 至少 2 个字符 |

## 代码位置

| 路径 | 职责 |
| --- | --- |
| `app/memory.go` | `Search`：查询上限、5 秒期限、记忆的范围；`MaxSearchRunes`、`MaxSearchTerms` |
| `store/sqlite/owned.go` | `Search`（会话、消息、任务）、`likePattern`、`snippet` |
| `store/sqlite/conversations.go` | 写 `items` 时只给两类消息填 `text` |
| `store/sqlite/migrations/0001_init.sql` | `items_search` 表与两个触发器 |
| `store/sqlite/fts5.go` | 没有 FTS5 构建标签时让编译失败 |
| `store/sqlite/owned_test.go` | 标题、消息、任务都能查到，大小写，别的用户查不到 |
| `gateway/owned.go` | `search` 方法的处理函数 |
| `gateway/protocol.go`、`gateway/wire.go` | 方法表、`SearchParams`、`SearchResult`、`Found`（`cronJobs`）、`MessageHit`、`limits`、错误码 |
| `gateway/server.go` | `defaultLimit`、`maxLimit` |
| `memory/recall.go`、`tool/builtin/memory/memory.go` | `memory.Search`、切词与打分；`memory_search` |
| `tool/builtin/workspace/read.go`、`walk.go`、`patterns.go` | `grep`、`glob`、walker、各项上限、`.gitignore` 和路径模式 |
| `tool/builtin/web/web.go` | `web_fetch`（没有搜索工具） |
| `policy/checker.go` | `requiresApproval`，只读工具不提问 |
