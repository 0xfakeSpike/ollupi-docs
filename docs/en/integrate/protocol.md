# Gateway protocol

The gateway is the engine's only external interface: JSON-RPC 2.0 over WebSocket. Clients use it to manage sessions (threads), start turns, follow the changes to items, and answer approvals and questions. Method names follow the Codex app-server. The protocol is defined by one table in `gateway/protocol.go`, which both dispatches requests and generates `gateway/protocol.schema.json`: as of v0.17.2, 42 methods, 12 notifications, 2 server requests, 1 client notification and 17 error codes, plus 6 close codes and 4 refused-handshake statuses, each with what a client does next. Every change to a thread, turn or item reaches clients as `thread/changed`, `turn/changed` or `item/changed`, carrying the sequence number of the commit that made it.

::: info Full page in Chinese
This page is being translated. The complete version, with every detail and code reference, is [in Chinese](/zh/integrate/protocol).
:::

The full page covers what every module shares:

- Transport
- Authentication
- Connection model
- Closing and reconnecting
- Handshake
- Version checks
- The modules, and which page each method and notification is on
- Common conventions
- Error codes
- One table for dispatch and schema
- Contract tests
- Routing

Each feature has its own page: [sessions](/integrate/protocol/threads), [turns and items](/integrate/protocol/turns), [approvals and questions](/integrate/protocol/approvals), [permissions](/integrate/protocol/permissions), [workspaces and environments](/integrate/protocol/workspaces), [models, tools and MCP](/integrate/protocol/models-tools), [scheduled tasks](/integrate/protocol/cron), [memory](/integrate/protocol/memory), [search](/integrate/protocol/search), [settings](/integrate/protocol/settings).
