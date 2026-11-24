# Usage

Usage records the tokens that models consume: one row for each model reply, summed by day, by workspace or by model into tables a client can chart. It is read with `usage/query`; there is no method to write it. The engine computes the rows from session logs, and clients can only query them.

```jsonc
// Request: the last seven days, by day
{"jsonrpc":"2.0","id":9,"method":"usage/query","params":{
  "from":"2026-11-17T00:00:00Z","to":"2026-11-24T00:00:00Z",
  "groupBy":"day","offsetMinutes":480}}
// Result
{"jsonrpc":"2.0","id":9,"result":{"data":[
  {"key":"2026-11-20","inputTokens":184320,"cachedInputTokens":150210,
   "cacheWriteInputTokens":12900,"outputTokens":9320}
]}}
```

::: info Full page in Chinese
This page is being translated. The complete version, with every parameter, type and limit, is [in Chinese](/zh/integrate/protocol/usage).
:::

The full page covers:

- What a row is
- Why usage is not computed on the path that writes the log
- `usage/query`, including the three ways to group
- What the totals include and leave out
- Errors and limits
- Code locations
