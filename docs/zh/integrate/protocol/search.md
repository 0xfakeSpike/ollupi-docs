# 搜索

`search` 是一个方法、一次调用：按关键词同时查这个用户的会话标题、消息、定时任务和长期记忆，分四组返回。它只查引擎库里的数据，不查工作区文件（那是模型的 `grep`、`glob` 工具），也不查网页。索引、匹配的细节和全部限制见[搜索的实现](/zh/engine/search)，这里讲客户端怎样调用和解读结果。

## 概念

- **四组，各自独立。** 会话、消息、任务按"所有词都出现"匹配，新的在前；记忆按"出现了哪些词"打分，分高的在前。`limit` 对每组分别生效。
- **只查自己的。** 用户来自连接的令牌，参数里没有用户。
- **只查顶层会话。** 子 agent 会话和它里面的消息不出现在结果里。
- **没有状态，没有通知。** 结果是一次快照，不分页，不报总数。

## 典型流程

下面的消息来自一个跑在本机的 v0.12 网关（假模型，没有配置记忆和定时任务），先建了标题为 `Deploy review` 的会话，发了一条消息，然后搜索：

```json
{"jsonrpc":"2.0","id":4,"method":"search","params":{"query":"deploy"}}
```

```json
{"jsonrpc":"2.0","id":4,"result":{
  "threads":[{"id":"1f9add60-…","environmentId":"c7af8aa2…","title":"Deploy review","settings":{"permissions":{}},"createdAt":"2026-11-09T05:30:08.77563Z","updatedAt":"2026-11-09T05:30:08.791725Z"}],
  "messages":[{"threadId":"1f9add60-…","threadTitle":"Deploy review","itemId":"a83db515-…","turnId":"b7b26538-…","seq":1,"type":"userMessage","snippet":"Which deploy failed last week?","at":"2026-11-09T05:30:08.778786Z"}],
  "tasks":[],
  "memories":[]}}
```

`deploy` 匹配了标题里的 `Deploy`（大小写不敏感），也匹配了消息。换成 `deploy week`，会话组变成空的，因为标题里没有 `week`，消息组仍然命中：

```json
{"jsonrpc":"2.0","id":5,"method":"search","params":{"query":"deploy week","limit":5}}
```

点一条消息命中时，客户端用 `threadId` 打开会话，再按 `seq` 定位条目：先 `thread/read` 读到包含这个 `seq` 的那一页（`beforeSeq` 传 `seq + 1`），见[会话](/zh/integrate/protocol/threads)。

## 方法：search

| 参数 | 类型 | 说明 |
|---|---|---|
| `query` | string | 按空白切成词；切完一个词都没有时报错 |
| `workspaceId?` | string | 只查这个工作区；不给或给空字符串都表示不过滤 |
| `limit?` | integer | 每组最多几条，默认 20，范围 1 到 100 |

结果是 `SearchResult`。四组都是数组，没有命中时是空数组。

| 组 | 查什么 | 怎样匹配 | 排序 |
|---|---|---|---|
| `threads` | 顶层会话的标题，包括已归档的 | 每个词都是标题的子串 | `updatedAt` 倒序 |
| `messages` | 顶层会话里已完成的 `userMessage` 和 `agentMessage` 的正文 | 每个词都是正文的子串 | 条目开始时间倒序 |
| `tasks` | 定时任务的 `name` 加 `prompt` | 每个词都是子串 | `createdAt` 倒序 |
| `memories` | `active` 记忆的 `topic` 加 `text` | 按记忆自己的切词，出现的词越多越长、分越高；`preference`、`decision` 加分 | 分数倒序 |

`workspaceId` 对四组都起作用：会话、消息、任务按所属会话的工作区过滤；记忆返回这个工作区的加上全局的。不给时，记忆查这个用户全部范围的。

宿主没有配置 `gateway.Options.Memory` 时，`memories` 总是空数组，其余三组照常。

| 错误 | 什么时候 |
|---|---|
| `-32602` `query is required` | `query` 为空或只有空白 |
| `-32602` `limit must be 1 to 100` | `limit` 超出范围；`0` 或不给时按 20 |

## 匹配的几处细节

- **子串，不是分词。** 会话、消息、任务用 SQL 的 `LIKE '%词%'`，所以 `deploy` 也匹配 `redeployed`。`%`、`_` 按字面匹配。大小写不敏感只对 ASCII 字母成立。
- **记忆的切词不同。** 连续的汉字切成相邻两字的组合，其他字符按字母、数字、`_`、`-` 组词，至少两个字符。所以只有一个汉字的查询在另外三组能命中，在记忆组里永远是空的。记忆组也不要求所有词都出现，命中一个词就可能返回。
- **片段。** `snippet` 取正文里第一个词第一次出现的位置，前后各 40 个字符，连续空白压成一个空格，截断处加 `…`。片段不标出命中位置，高亮由客户端自己做（桌面端在渲染时按查询词标出）。

## 类型

### SearchResult

| 字段 | 类型 | 说明 |
|---|---|---|
| `threads` | `ThreadRow[]` | 命中的会话，字段见[会话](/zh/integrate/protocol/threads) |
| `messages` | `MessageHit[]` | 命中的消息 |
| `tasks` | `CronJobView[]` | 命中的定时任务，字段见[定时任务](/zh/integrate/protocol/cron#cronjobview) |
| `memories` | `MemoryRow[]` | 命中的记忆，字段见[记忆](/zh/integrate/protocol/memory#memoryrow) |

### MessageHit

| 字段 | 类型 | 说明 |
|---|---|---|
| `threadId`、`threadTitle` | string | 命中所在的会话和它的标题 |
| `itemId` | string | 命中的条目 |
| `turnId` | string | 条目所在的轮次 |
| `seq` | integer | 条目在会话里的序号，客户端用它定位 |
| `type` | `ItemType` | 只会是 `userMessage` 或 `agentMessage` |
| `snippet` | string | 命中处前后的片段 |
| `at` | string | 条目的开始时间 |

## 错误与边界

- **搜不到的东西。** 工具调用和它的结果、推理、压缩摘要、错误条目、附件内容、子 agent 会话都不在搜索范围内；会话只按标题匹配，不按内容。完整的限制表见[已知限制](/zh/engine/search#已知限制)。
- **不能只搜不属于工作区的会话。** `workspaceId` 给空字符串等于不过滤，这和 `thread/list` 不同，那里空字符串表示"只列不属于工作区的"。
- **没有分页。** 想看更多只能调大 `limit`，最多每组 100 条。
- **不加锁。** `search` 不像 `thread/read` 那样和事件排序，结果可能比刚收到的通知旧一点。它只用于展示，不要拿来更新本地状态。

## 代码位置

| 仓库 | 路径 | 职责 |
|---|---|---|
| ollupi | `gateway/search.go` | `search` 的处理函数、参数校验、记忆组 |
| ollupi | `gateway/protocol.go` | `SearchParams`、`SearchResult` |
| ollupi | `gateway/server.go` | `defaultLimit`（20）、`maxLimit`（100） |
| ollupi | `repo/search.go` | `Found`、`MessageHit`，会话、消息、任务三组的查询，`snippet` |
| ollupi | `agent/memory/search.go`、`recall.go` | 记忆组：`Search`、切词、打分 |
| ollupi-desktop | `apps/desktop/src/renderer/src/domains/search.ts` | 桌面端的调用方式：停顿 250 ms、每组 20 条 |
