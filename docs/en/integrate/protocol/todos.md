# Todos

Todos are the user's own list. It spans every project and outlives any one session: the user says what needs doing, the hub records it as a todo, links the session when it hands the work out, and marks the result when the work is done. A client reads and writes todos with `todo/*` and follows changes with `todo/changed`; who writes them and why it is designed this way is on [hub](/engine/hub).

```jsonc
// Request
{"jsonrpc":"2.0","id":7,"method":"todo/list","params":{"limit":20}}
// Result: empty strings, false, and endedAt while the todo has not ended are not sent
{"jsonrpc":"2.0","id":7,"result":{"data":[
  {"id":3,"title":"Update the docs' engine pages to v0.26.2","status":"handed",
   "workspaceId":"4dc76ecd-1f0a-4c3e-9b52-7a1e0c2d9f41","threadId":"eb2c51e5-6a7d-4b18-8c3f-2d9e5a0b7c16",
   "notes":"Permissions first, then the sandbox","createdAt":"2026-11-23T01:12:04Z","updatedAt":"2026-11-23T01:20:11Z"}
]}}
```

::: info Full page in Chinese
This page is being translated. The complete version, with every method, notification, type and real message, is [in Chinese](/zh/integrate/protocol/todos).
:::

The full page covers:

- Concepts and state: the fields of a todo, its four statuses (`open`, `handed`, `done`, `dropped`), length limits
- Methods: `todo/list`, `todo/add`, `todo/update`
- Notification: `todo/changed`
- Type: `TodoRow`
- Errors and limits
- Code locations
