# Gateway protocol

The gateway is the engine's only external interface: JSON-RPC 2.0 over WebSocket. Clients use it to manage sessions (threads), start turns, follow the changes to items, and answer approvals and questions; they also use it to read and write workspaces, scheduled tasks, memory, todos and usage.

The protocol is declared by the variable `protocol` in `gateway/protocol.go`: methods, notifications, server requests, client notifications, error codes, close codes and handshake statuses are all written in this one place. The same table both dispatches at run time and generates `gateway/protocol.schema.json`, so the contract, the types and the actual behavior cannot go separate ways. There are currently 49 methods, 13 notifications, 2 server requests, 1 client notification, 18 error codes, 6 close codes and 4 refused-handshake statuses. The methods by module are on the pages listed below; to find which module a type belongs to, see the [type index](/integrate/protocol-types).

::: info Full page in Chinese
This page is being translated. The complete version, with every detail and code reference, is [in Chinese](/zh/integrate/protocol).
:::

The full page covers what every module shares:

- Transport
- Authentication
- Connection model
- Closing and reconnecting
- Handshake
- The modules, and which page each method and notification is on
- Common conventions
- Error codes
- Generating and testing the contract
- Routing
- Code locations

Each module has its own page: [sessions](/integrate/protocol/threads), [turns and items](/integrate/protocol/turns), [approvals and questions](/integrate/protocol/approvals), [permissions](/integrate/protocol/permissions), [workspaces and environments](/integrate/protocol/workspaces), [models, tools and MCP](/integrate/protocol/models-tools), [scheduled tasks](/integrate/protocol/cron), [memory](/integrate/protocol/memory), [search](/integrate/protocol/search), [settings](/integrate/protocol/settings), [todos](/integrate/protocol/todos), [usage](/integrate/protocol/usage).
