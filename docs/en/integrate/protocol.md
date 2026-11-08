# Gateway protocol

The gateway is the engine's only external interface: JSON-RPC 2.0 over WebSocket. Clients use it to manage sessions (threads), start turns, receive item deltas, and answer approvals and questions. Method names follow the Codex app-server. The protocol is defined by one table in `gateway/protocol.go`, which both dispatches requests and generates `gateway/protocol.schema.json`: as of v0.11.3, 34 methods, 15 notifications, 2 server requests, 1 client notification and 15 error codes.

::: info Full page in Chinese
This page is being translated. The complete version, with every detail and code reference, is [in Chinese](/zh/integrate/protocol).
:::

The full page covers:

- Transport
- Authentication
- Connection model
- Handshake
- Version checks
- One complete conversation
- Client methods
- Server notifications
- Server requests
- Enums
- Error codes
- One table for dispatch and schema
