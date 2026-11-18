# 搜索

`search` 是一个方法、一次调用：按关键词同时查这个用户的会话标题、消息、定时任务和长期记忆，分四组返回。它只查引擎库里的数据，不查工作区文件（那是模型的 `grep`、`glob` 工具），也不查网页。索引、匹配的细节和全部限制见[搜索的实现](/zh/engine/search)，这里讲客户端怎样调用和解读结果。

本页按引擎 v0.17.1 写，示例来自对 v0.17.1 网关的脚本试验（假模型、单用户，ID 缩短了）。

## 概念

- **四组，各自独立。** 会话、消息、任务按"所有词都出现"匹配，新的在前；记忆按"出现了哪些词"打分，分高的在前。`limit` 对每组分别生效。
- **只查自己的。** 用户来自连接的令牌，参数里没有用户。
- **只查顶层会话。** 子 agent 会话和它里面的消息不出现在结果里。
- **有上限。** 查询最多 200 个字符、8 个词，超过 5 秒没查完就放弃。前两个数也写在契约的 `limits` 段（`searchRunes`、`searchTerms`）里，客户端可以在发请求之前自己检查。
- **没有状态，没有通知。** 结果是一次快照，不分页，不报总数。

## 典型流程

库里有一个标题为 `Deploy review` 的会话，里面发过一条消息 `Which deploy failed last week?`；另一个会话里有一个定时任务 `deploy-report`，`prompt` 是 `Summarize last week's deploys`；还有一条工作区记忆，主题是 `deploy target`。搜 `deploy`：

```json
→ {"jsonrpc":"2.0","id":68,"method":"search","params":{"query":"deploy"}}
← {"jsonrpc":"2.0","id":68,"result":{
  "threads":[{"id":"3f8c1952-…","workspaceId":"4dc76ecd-…","environmentId":"da29709a-…","title":"Deploy review","settings":{ … },"status":"active","createdAt":"2026-11-18T12:19:25.277559Z","updatedAt":"2026-11-18T12:19:27.287938Z"}],
  "messages":[{"threadId":"3f8c1952-…","title":"Deploy review","itemId":"64076a4b-…","turnId":"f92ad4cf-…","seq":2,"type":"userMessage","snippet":"Which deploy failed last week?","at":"2026-11-18T12:19:27.284544Z"}],
  "tasks":[{"id":"81af1173-…","threadId":"bfbd192b-…","name":"deploy-report","spec":"0 9 * * 1","prompt":"Summarize last week's deploys", … ,"threadTitle":"general"}],
  "memories":[{"id":"m1","scope":"workspace","workspaceId":"4dc76ecd-…","topic":"deploy target","kind":"fact","text":"Deploys go to staging first, then production.", … }]}}
```

`deploy` 匹配了标题里的 `Deploy`（大小写不敏感），也匹配了消息、任务和记忆。换成 `deploy week`，会话组变成空的，因为标题里没有 `week`；消息和任务仍然命中（任务的 `prompt` 里有 `week's`）；记忆按词打分，命中一个词也算：

```json
→ {"jsonrpc":"2.0","id":69,"method":"search","params":{"query":"deploy week","limit":5}}
← {"jsonrpc":"2.0","id":69,"result":{"threads":[],"messages":[ … ],"tasks":[ … ],"memories":[ … ]}}
```

再带上工作区。任务组变成空的，因为那个任务所在的会话不在这个工作区里：

```json
→ {"jsonrpc":"2.0","id":70,"method":"search","params":{"query":"deploy","workspaceId":"4dc76ecd-…"}}
← {"jsonrpc":"2.0","id":70,"result":{"threads":[ … ],"messages":[ … ],"tasks":[],"memories":[ … ]}}
```

点一条消息命中时，客户端用 `threadId` 打开会话，再按 `seq` 定位条目：先 `thread/read` 读到包含这个 `seq` 的那一页（`beforeSeq` 传 `seq + 1`），见[会话](/zh/integrate/protocol/threads)。

## 方法：search

| 参数 | 类型 | 说明 |
|---|---|---|
| `query` | string | 按空白切成词；最多 200 个字符、8 个词 |
| `workspaceId?` | string | 只查这个工作区；不给或给空字符串都表示不过滤 |
| `limit?` | integer | 每组最多几条，默认 20，范围 1 到 100。调大了每组多返回，但查询也更慢，更容易碰到 5 秒的上限 |

结果是 [`SearchResult`](#searchresult)。四组都是数组，没有命中时是空数组。

| 组 | 查什么 | 怎样匹配 | 排序 |
|---|---|---|---|
| `threads` | 顶层会话的标题，包括已归档的 | 每个词都是标题的子串 | `updatedAt` 倒序 |
| `messages` | 顶层会话里的 `userMessage` 和 `agentMessage` 的正文 | 每个词都是正文的子串 | 条目开始时间倒序 |
| `tasks` | 定时任务的 `name` 加 `prompt` | 每个词都是子串 | `createdAt` 倒序 |
| `memories` | `active` 记忆的 `topic` 加 `text` | 按记忆自己的切词，出现的词越多越长、分越高；`preference`、`decision` 加分 | 分数倒序，同分时新的在前 |

`workspaceId` 对四组都起作用：会话、消息、任务按所属会话的工作区过滤；记忆只查这个工作区范围的记忆，不含全局记忆和不属于工作区的记忆。不给时，记忆查这个用户全部范围的。

记忆组不看用户的记忆开关：`memory` 关着时照样返回。

| 错误 | 什么时候 |
|---|---|
| `-32602` `invalid query: query is required` | `query` 为空或只有空白 |
| `-32602` `invalid query: query must be at most 200 characters and 8 words` | 查询太长或词太多 |
| `-32602` `limit must be 1 to 100` | `limit` 超出范围；`0` 或不给时按 20 |
| `-32017` `the search took too long; try longer or fewer words` | 5 秒内没查完 |

::: info 演进
v0.12.1 的查询没有长度上限，也不会超时；带 `workspaceId` 时记忆组还包括全局记忆。`fdefa84` 加了 200 个字符、8 个词的上限，`bfcd398` 把这两个数写进契约，超时有了自己的错误码 `searchTimedOut`。`d110977` 重写搜索时，带工作区的记忆组只查这个工作区范围。`9b5b50b` 把 `MessageHit.threadTitle` 改名为 `title`，`tasks` 的元素换成 `CronJobRow`。
:::

## 匹配的几处细节

- **子串，不是分词。** 会话、消息、任务用 SQL 的 `LIKE '%词%'`，所以 `deploy` 也匹配 `redeployed`。`%`、`_` 按字面匹配。大小写不敏感只对 ASCII 字母成立。消息组里三个字符以上的词还会经三元组索引 `items_search` 筛一遍，用来加快查询。
- **记忆的切词不同。** 连续的汉字切成相邻两字的组合，其他字符按字母、数字、`_`、`-` 组词，至少两个字符。所以只有一个汉字的查询在另外三组能命中，在记忆组里永远是空的。记忆组也不要求所有词都出现，命中一个词就可能返回。
- **片段。** `snippet` 取正文里第一个词第一次出现的位置，前后各 40 个字符，连续空白压成一个空格，截断处加 `…`。片段不标出命中位置，高亮由客户端自己做。

## 类型

### SearchResult

| 字段 | 类型 | 说明 |
|---|---|---|
| `threads` | `ThreadRow[]` | 命中的会话，字段见 [ThreadRow](/zh/integrate/protocol/threads#threadrow) |
| `messages` | [`MessageHit[]`](#messagehit) | 命中的消息 |
| `tasks` | `CronJobRow[]` | 命中的定时任务，字段见[定时任务](/zh/integrate/protocol/cron#cronjobrow)。字段名仍叫 `tasks` |
| `memories` | `MemoryRow[]` | 命中的记忆，字段见[记忆](/zh/integrate/protocol/memory#memoryrow) |

参数类型 `SearchParams` 的字段就是上面的参数表。

### MessageHit

| 字段 | 类型 | 说明 |
|---|---|---|
| `threadId`、`title` | string | 命中所在的会话和它的标题 |
| `itemId` | string | 命中的条目 |
| `turnId` | string | 条目所在的轮次 |
| `seq` | integer | 条目在会话里的序号，客户端用它定位 |
| `type` | `ItemKind` | 只会是 `userMessage` 或 `agentMessage` |
| `snippet` | string | 命中处前后的片段 |
| `at` | string | 条目的开始时间 |

## 错误与边界

- **搜不到的东西。** 工具调用和它的结果、推理、压缩摘要、错误条目、附件内容、子 agent 会话都不在搜索范围内；会话只按标题匹配，不按内容。完整的限制表见[已知限制](/zh/engine/search#已知限制)。
- **不能只搜不属于工作区的会话。** `workspaceId` 给空字符串等于不过滤，这和 `thread/list` 不同，那里空字符串表示"只列不属于工作区的"。
- **带工作区时看不到全局记忆。** 一个工作区的会话实际会载入全局记忆，但带 `workspaceId` 的搜索不返回它们；要连全局记忆一起搜，就不给 `workspaceId`。
- **没有分页。** 想看更多只能调大 `limit`，最多每组 100 条。
- **只用于展示。** `search` 不和变更通知排序，结果可能比刚收到的通知旧一点，不要拿来更新本地状态。

## 代码位置

| 路径 | 职责 |
|---|---|
| `gateway/owned.go` | `search` 的处理函数 |
| `gateway/server.go`、`gateway/threads.go` | `defaultLimit`（20）、`maxLimit`（100），`limit` 的检查 |
| `gateway/protocol.go`、`gateway/wire.go` | `SearchParams`、`SearchResult`、`Found`、`MessageHit`、契约的 `limits` |
| `app/memory.go` | `Search`：查询的上限、5 秒超时、记忆组的范围 |
| `store/sqlite/owned.go` | 会话、消息、任务三组的查询，`snippet` |
| `store/sqlite/migrations/0001_init.sql` | 消息的三元组索引 `items_search` |
| `memory/recall.go` | 记忆组：`Search`、切词、打分 |
