# Models, tools and MCP

Listing the models, the tools of a user and their MCP servers; adding, changing and deleting a user's MCP servers with `mcpServer/set` and `mcpServer/delete` and following them with `mcpServer/changed`; how a turn picks its model; and the arguments and outputs of the ten built-in tools the contract types.

::: info Full page in Chinese
This page is being translated. The complete version, with every method, notification, type and real message, is [in Chinese](/zh/integrate/protocol/models-tools).
:::

The full page covers:

- Concepts and state: models, a user's tool registry, per-user MCP servers and their naming rules
- Typical flows
- Methods: `model/list`, `tool/list`, `mcpServer/list`, `mcpServer/set`, `mcpServer/delete`
- Notification: `mcpServer/changed`
- Arguments and outputs of the built-in tools
- Types: `Model`, `ToolDescriptor`, `Annotations`, `MCPServerConfig`, `MCPServer`, `MCPServerStatus`, providers
- Errors and limits
- Code locations
