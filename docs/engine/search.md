# 搜索

Ollupi 有三条互不相干的搜索路径：查自己的会话和消息（引擎的 `search` 方法）、查工作区里的文件（模型用的 `grep` 和 `glob` 工具）、查网页（没有）。三者匹配方式、索引和权限各不相同，遇到“搜不到”先确认是哪一条。

## 三条路径

| 查什么 | 谁执行 | 入口 | 匹配方式 | 索引 |
| --- | --- | --- | --- | --- |
| 会话标题、消息正文、定时任务、记忆 | 引擎 `repo.DB.Search` | JSON-RPC `search` | 子串 `LIKE` | FTS5 表 `items_search`，只用于消息 |
| 工作区文件的内容和路径 | 工具层 `grep`、`glob` | 模型调用工具 | `grep` 用 Go RE2 正则，`glob` 用路径模式 | 没有，逐目录遍历 |
| 网页 | — | — | — | — |

网页这一行是空的：`tools/web` 只提供 `web_fetch`，读一个给定的 URL（见[工具系统](/engine/tools#网页)）；代码里没有搜索 API 的 provider，也没有搜索引擎的配置项和密钥。要让模型“搜网页”，只能先给它一个网址。

## 会话、消息、任务与记忆：`search`

一次 `search` 覆盖四类对象，没有按对象拆开的方法。它在连接所属的分片库上执行；一个用户只放在一个分片，不需要跨分片合并（见[分片与多用户](/engine/sharding)）。

### 参数

| 参数 | 类型 | 默认 | 约束 |
| --- | --- | --- | --- |
| `query` | string | 必填 | 按空白切成词（`strings.Fields`）；切不出词时返回 `-32602`（`query is required`） |
| `workspaceId` | string | 空 | 空等于不限定工作区 |
| `limit` | integer | 20 | 1 到 100（`defaultLimit` 与 `maxLimit`），越界返回 `-32602`；**每一类**各取这么多条 |

### 匹配条件

每个词各加一条条件，所以多个词是 AND：每个词都要命中。词内不做词干、不做近义词、不做前缀扩展。

| 类别 | 匹配的列 | 其他过滤 | 排序 | 上限 |
| --- | --- | --- | --- | --- |
| 会话 | `threads.title` | `user_id` 是调用者，`parent_thread_id IS NULL`（只要顶层会话；归档的也算） | `updated_at DESC, id` | `limit` |
| 消息 | `items.text` | `type` 是 `userMessage` 或 `agentMessage`，`status` 是 `completed`，所属会话属于调用者且是顶层会话 | `started_at DESC, id` | `limit` |
| 任务 | `cron_jobs.name \|\| ' ' \|\| cron_jobs.prompt` | 任务所属会话属于调用者（暂停的任务也在） | `created_at DESC, id` | `limit` |
| 记忆 | `memories.topic` 与 `memories.text`，在 Go 里打分 | `status` 是 `active` | 分数降序，同分按 `updated_at DESC, id` | `limit` |

`workspaceId` 非空时四类都再加一条 `COALESCE(<列>, '') = ?`：会话和任务看 `threads.workspace_id`，消息看所属会话的，记忆换成查这个工作区的记忆加全局记忆。不属于任何工作区（general）的会话、消息、任务在这个过滤下不出现。

### 返回

`SearchResult` 嵌入 `repo.Found`，所以四个数组是平铺的：`threads`、`messages`、`tasks`、`memories`。没有命中时是空数组，不是 `null`；没配置记忆时 `memories` 也为空。

| 数组 | 元素 | 带什么 |
| --- | --- | --- |
| `threads` | `ThreadRow` | 整行，含 `title`、`workspaceId`、`archivedAt`；没有命中片段 |
| `messages` | `MessageHit` | `threadId`、`threadTitle`、`itemId`、`turnId`、`seq`、`type`、`snippet`、`at` |
| `tasks` | `CronJobView` | 任务整行，加 `threadTitle`、`lastRunAt`、`threadArchived` |
| `memories` | `MemoryRow` | 记忆整行，含 `topic`、`text`、`kind`、`scope`、`status` |

`snippet` 由引擎生成，只围绕**第一个词**：在正文里按 Unicode 小写找到第一个词，取前后各 40 个字符（`snippetRunes`），把空白折叠成单个空格，两端被截断时加 `…`。所以片段一定含第一个词，其余词可能不在其中。

高亮不在引擎里。桌面端把查询按空白切出的词拼成一个大小写不敏感的 `RegExp`，给命中的文字套 `<mark>`（`views/search/Highlight.tsx`）。引擎只返回原样的 `snippet`。

## 索引与一致性

消息的索引是一张 FTS5 external content 表：

```sql
CREATE VIRTUAL TABLE `items_search` USING fts5(text, content='items', content_rowid='rowid', tokenize='trigram');
```

它只收 `type` 是 `userMessage` 或 `agentMessage`、`status` 是 `completed` 的条目，由三个触发器维护（`repo/migrations/0004_search_messages.sql`）：

| 触发器 | 时机 | 做什么 |
| --- | --- | --- |
| `items_search_insert` | `items` 插入 | 满足条件时写入 `rowid` 和 `text` |
| `items_search_delete` | `items` 删除 | 从索引里删掉这一行 |
| `items_search_update` | `items` 的 `text` 或 `status` 更新 | 旧状态是 `completed` 时先删旧文本，新状态是 `completed` 时写入新文本 |

- 正在流式输出的回答搜不到，等它结束、状态变成 `completed` 才进索引；改正文、改状态则立刻反映到索引。
- 删除会话时条目被级联删除，触发器把它们从索引里去掉（测试检查索引条数回到 0）。
- 重启不重建：索引和触发器都在库里，`Open` 只执行没跑过的 migration，0004 第一次执行时用 `INSERT ... SELECT` 回填已有消息。
- 例外写在 0004 的注释里：`items` 没有 `INTEGER PRIMARY KEY`，索引靠 `rowid` 回读原文，`VACUUM` 或重建 `items` 的 migration 会重新编号 `rowid`，之后必须重建索引；代码里既没有执行 `VACUUM`，也没有重建语句。

查询这样用索引，每个词一组：

```sql
i.rowid IN (SELECT rowid FROM items_search WHERE text LIKE ?) AND i.text LIKE ? ESCAPE '\'
```

子查询故意不带 `ESCAPE`：索引只能把结果缩成超集，词里的 `%` 和 `_` 会被当成通配符；第二个条件再由 `likePattern` 转义 `\`、`%`、`_`，精确定义命中。所以 `100%`、`super_agent` 这类词按字面匹配。

### 大小写、中文、宽度

- 大小写：匹配全部交给 `LIKE`，代码没有设置 `case_sensitive_like`，所以按 SQLite 的默认：ASCII 字母不区分大小写，其他字符的大小写不折叠。
- 中文：消息不需要分词，两个汉字的词也能命中（测试里 `池化`、`等待中` 都查到了）。索引的 tokenizer 是 `trigram`，按字符三元组切。
- 全角半角、繁体简体、拼音、变音符号：不归一化。`Ａ` 与 `A`、`臺` 与 `台` 互不命中，代码里没有这类处理。

## 文件搜索：`grep` 和 `glob`

这两个是模型用的工具，不属于 `search` 方法；参数见[工具系统](/engine/tools#读文件和搜索)。

| 工具 | 参数 | 匹配 |
| --- | --- | --- |
| `grep` | `pattern`（RE2）、`path`、`include`、`ignore_case`、`files_only`、`context`（0 到 10） | 逐行正则匹配，可返回上下文行 |
| `glob` | `pattern`、`path` | 路径模式：`*`、`**`、`?`、`[...]`、`{a,b}` |

| 上限 | 值 | 越过时 |
| --- | --- | --- |
| `glob` 返回的文件数 | 500（`maxGlobFiles`） | 标 `truncated` |
| `grep` 保留的匹配行 | 300（`maxGrepLines`） | 标 `truncated`，停止遍历 |
| `grep` 返回的文件数（`files_only`） | 500（`maxGrepFiles`） | 标 `truncated` |
| 单个文件大小 | 8 MiB（`maxGrepBytes`） | 跳过 |
| 每行字符数 | 500（`maxGrepRunes`） | 截断并加 `…` |
| 一次遍历的条目数 | 200000（`maxWalkEntries`） | 标 `truncated` |

两者共用一个 walker：跳过 `.git`、`.gitignore` 与 `.git/info/exclude` 忽略的文件、非文本文件、指向目录的链接；沙箱不让读的计入 `skipped`。

两者都标了只读、`OpenWorld` 为假，`requiresApproval` 在 `on-request` 和 `untrusted` 下都不提问，所以不需要审批（`agent/permission/policy.go`）。路径先规范化再过 `Box.CheckRead`，链接绕不过去；禁读路径在任何沙箱模式下都不读，工具提示模型改用 `run_command`。规则仍可按路径匹配，`Match` 是相对工作区根的小写路径，例如 `grep(src/*)`。

工具输出的截断分三层（工具层、`read_tool_output`、上下文预算），见[工具系统](/engine/tools#输出截断)。

## 记忆搜索的两个入口

`search` 的 `memories` 由 `Manager.Search` 填；模型另有一个 `memory_search` 工具，上限 20 条（`maxSearchResults`），`query` 至少 2 个字符。两者共用 `searchTerms`：连续汉字切成相邻两字的重叠组合（`等待中的` → `等待`、`待中`、`中的`），其他字符按字母、数字、`_`、`-` 组词，至少 2 个字符，去重，最多 512 个。打分与排序见[记忆](/engine/memory#搜索)。

## 桌面端

搜索页在侧边栏，⌘K 从任何界面打开（`views/App.tsx` 的 `useSearchShortcut`）。

- 输入停顿 250 ms 才发请求（`PAUSE_MS`），每组最多 20 条（`LIMIT`）；上一个结果保留到新结果到达，列表不会闪空。
- 结果按会话、消息、任务、记忆分组，只列非空分组并标出条数。点会话打开它，点消息打开会话并定位到那一条，点任务或记忆跳到列出它的页面（`focus` 与 `useFound`）。
- 记忆页的搜索框用同一个 `search` 方法，把 `workspaceId` 传成当前标签页的范围，返回的记忆再按 scope 过滤。

## 已知限制

| 限制 | 依据 |
| --- | --- |
| 消息只搜 `userMessage` 和 `agentMessage`，且必须 `completed` | 索引触发器的 `WHEN` 与查询条件 |
| 不搜工具调用、工具结果、思考内容、压缩摘要、错误、附件内容 | `type` 只允许两种，索引只有 `items.text` |
| 子代理会话和它里面的消息搜不到 | 条件里的 `parent_thread_id IS NULL` |
| 只搜调用者自己的数据，参数里没有用户 | `DB.Search` 的第一个参数来自连接令牌 |
| 不支持正则、模糊匹配、词形变化 | `LIKE '%词%'` |
| 会话只按标题匹配，不按会话内容匹配 | `title LIKE ?` |
| 没有分页、游标和命中总数 | `SearchParams` 只有 `query`、`workspaceId`、`limit` |
| 没有执行超时：处理函数不带 context（`writeTimeout` 只管发响应） | `func (c *conn) search(p SearchParams)` |
| 不做全角半角、繁简、拼音、变音符号归一化 | 代码里没有这类处理 |
| 单个汉字查不到记忆，也调不通 `memory_search` | `searchTerms` 只产出两字组合 |

## 代码位置

| 仓库 | 路径 | 职责 |
| --- | --- | --- |
| ollupi | `repo/search.go` | `Search`（四类查询）、`likePattern`、`snippet` |
| ollupi | `repo/migrations/0004_search_messages.sql` | `items_search` 表与三个触发器 |
| ollupi | `repo/fts5.go` | 没有 `sqlite_fts5` 标签时让编译失败 |
| ollupi | `repo/search_test.go` | 子串、两字中文、`%`/`_` 字面、删会话后清索引 |
| ollupi | `gateway/search.go` | `search` 方法的处理函数 |
| ollupi | `gateway/protocol.go`、`gateway/protocol.schema.json` | 方法表、`SearchParams`、`SearchResult` |
| ollupi | `gateway/server.go` | `defaultLimit`、`maxLimit` |
| ollupi | `agent/memory/search.go`、`recall.go` | `memory_search`、`Manager.Search`、切词与打分 |
| ollupi | `tools/workspace/read.go` | `grep`、`glob`、walker、各项上限 |
| ollupi | `tools/workspace/patterns.go` | `compilePattern`、`.gitignore` 解析 |
| ollupi | `tools/web/web.go` | `web_fetch`（没有搜索工具） |
| ollupi | `agent/permission/policy.go` | `requiresApproval`，只读工具不提问 |
| ollupi-desktop | `apps/desktop/src/renderer/src/domains/search.ts` | `useSearch`、250 ms 停顿、每组 20 条 |
| ollupi-desktop | `apps/desktop/src/renderer/src/views/search/SearchScreen.tsx`、`Highlight.tsx` | 分组展示、点击定位、渲染端高亮 |
| ollupi-desktop | `apps/desktop/src/renderer/src/views/memory/MemoryScreen.tsx` | 记忆页搜索框 |
| ollupi-desktop | `apps/desktop/src/renderer/src/views/common/found.ts` | 把命中的条目滚进视野并标出 |
