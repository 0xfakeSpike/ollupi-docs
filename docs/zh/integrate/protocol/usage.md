# 用量

用量记的是模型消耗的 token：每一次模型回复一行，按天、按工作区、按模型汇总成客户端能画的表。用 `usage/query` 读，没有写入方法——行由引擎从会话日志里算出来，客户端只能查。

```jsonc
// 请求：最近七天，按天
{"jsonrpc":"2.0","id":9,"method":"usage/query","params":{
  "from":"2026-11-17T00:00:00Z","to":"2026-11-24T00:00:00Z",
  "groupBy":"day","offsetMinutes":480}}
// 结果
{"jsonrpc":"2.0","id":9,"result":{"data":[
  {"key":"2026-11-20","inputTokens":184320,"cachedInputTokens":150210,
   "cacheWriteInputTokens":12900,"outputTokens":9320}
]}}
```

## 一行是什么

一次模型回复一行，包括普通的回答和一次上下文压缩。行里存的是服务商回报的 token 数：

| 字段 | 含义 |
|---|---|
| `inputTokens` | 这次请求的输入 token |
| `cachedInputTokens` | 其中命中提示缓存的输入 token，已经算在 `inputTokens` 里 |
| `cacheWriteInputTokens` | 这次请求写进缓存的输入 token |
| `outputTokens` | 模型输出的 token |

`cachedInputTokens` 和 `cacheWriteInputTokens` 是 `inputTokens` 的拆分，不是额外的量；不同服务商不一定都回报，没有回报时是 0。

## 为什么不在写日志的路径上算

每一条模型回复已经作为 `modelResponded` 条目写进会话日志，里面有 `Stats.Model` 和 `Usage`。用量表是这份日志的派生结果，由一个后台记录器补上：提交日志的一方只唤醒记录器，不在这里多写一次数据库。这样做的好处是慢的和错的都不影响轮次——记不下来就记不下来，下一轮再补；代价是刚结束的一轮可能晚一点才出现在用量里。

补齐的机制：记录器启动时把"所有还没有用量行的条目"扫一遍，之后按会话增量扫；一页 256 条，游标是 `(thread, seq)` 而不是 `rowid`（删掉最后一行时 SQLite 会重用 `rowid`，会漏条目）。写失败时记一条日志，30 秒后重试，期间事件积压到 256 个就退回全量扫。读 `modelResponded` 失败的那一条会跳过并记日志，不会让整页卡住。

## usage/query

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `from` | `string` | 是 | RFC 3339，闭区间起点 |
| `to` | `string` | 是 | RFC 3339，开区间终点；必须晚于 `from` |
| `groupBy` | `string` | 是 | `day`、`workspace` 或 `model` |
| `offsetMinutes` | `integer` | 否 | 按天分组时，一天从几点开始；东经为正，范围 -1440 到 1440，默认 0（UTC） |

返回 `{data: UsageRow[]}`，按 `key` 升序，没有数据时是空数组。区间是半开的：`[from, to)`，恰好落在 `to` 的那一次调用不算。

### 三种分组

| `groupBy` | `key` 是什么 |
|---|---|
| `day` | `YYYY-MM-DD`，按 `offsetMinutes` 换算后的日历日 |
| `workspace` | 工作区 `id`；不属于任何工作区的会话（general）是空字符串 |
| `model` | 模型 `id`，如 `claude-sonnet-4-5` |

`offsetMinutes` 只影响按天分组，按工作区和按模型分组时忽略。客户端要显示自己时区里的"今天"，就传本地的 UTC 偏移（例如北京 480）；不传就是 UTC 的日界。

按天分组的边界在 SQL 里用 `strftime('%Y-%m-%d', at, '<offset> minutes')` 算，`at` 存的是 UTC。所以跨时区的两个客户端查同一天，会得到不同的分组。

## 汇总的边界

- **只有模型调用。** 工具执行、沙箱命令、网关流量都不计入；一行的 token 只来自模型回复本身。
- **压缩也算一次。** 上下文压缩是一次真实的模型调用，它的 token 计进当天/工作区/模型，和普通回答一样。
- **删了会话，行还在。** 目前没有保留期和清理任务：会话被删除后它的用量行留在表里，仍然计入汇总；这一点和会话不同，历史对话删掉后用量的数字不会变小。
- **正在跑的一轮可能缺。** 记录器在条目提交后补行，读的时候一轮刚好在跑，它最后一两次模型调用可能还没进汇总。
- **小数没有。** 全部是整数 token；不同服务商计价不同，这里不做金额换算。

## 错误与边界

- `groupBy` 不是三种之一、`from`/`to` 缺失、`from` 不早于 `to`、`offsetMinutes` 超出 ±1440：都是 `invalidParams`。
- 用量按用户隔离：只能查自己的行，别人的会话和模型不会出现在结果里。
- 分组结果只给 `key` 和四个数，没有排名、没有百分比、没有上一周期对比；要这些由客户端自己算。

## 代码位置

| 路径 | 职责 |
|---|---|
| `usage/usage.go` | 后台记录器：听 feed、按会话补行、全量扫、30 秒重试、256 条一页 |
| `store/sqlite/usage.go` | `usage` 表读写；按三种方式分组汇总；时间区间 `[from, to)` |
| `store/sqlite/migrations/0011_usage.sql` | 表结构、索引，以及 `modelResponded` 条目的部分索引 |
| `app/usage.go` | `App.Usage`：校验 `groupBy`、`from`/`to`、`offsetMinutes` |
| `gateway/owned.go` | `usage/query` |
| `gateway/protocol.go`、`gateway/protocol.schema.json` | `UsageQueryParams`、`UsageRow`、`UsageGroup` |
| `host/host.go` | 创建并启动记录器 |
