# Models, tools and MCP

A client uses `model/list`, `tool/list` and `mcpServer/list` to learn which models this user can choose, which tools the agent has, and what MCP servers the user has configured and whether they are connected; it adds, changes and deletes the user's MCP servers with `mcpServer/set` and `mcpServer/delete`, and follows them with `mcpServer/changed`. Each tool call item in a session is read by its provider and tool name; the arguments or outputs of 21 built-in tools are typed in the contract, and everything else is generic JSON. How models are called and tools run is on [models](/engine/models), [tools](/engine/tools) and [skills and MCP](/engine/skills-mcp).

::: info Full page in Chinese
This page is being translated. The complete version, with every method, notification, type and real message, is [in Chinese](/zh/integrate/protocol/models-tools).
:::

The full page covers:

- Concepts and state: models, a user's tool registry, per-user MCP servers and their naming rules
- Typical flows
- Methods: `model/list`, `tool/list`, `mcpServer/list`, `mcpServer/set`, `mcpServer/delete`
- Notification: `mcpServer/changed`
- Arguments and outputs of the built-in tools: `Plan` and `PlanStep`, `SubagentCall`, `SubagentLaunched`, `CommandOutput`, `FileOutput`, `ReadFile` and `ReadFileOutput`, `Glob` and `GlobOutput`, `Grep`, `GrepOutput`, `GrepFile`, `GrepLine`
- Types: `Model`, `ToolDescriptor`, `Annotations`, `MCPServerConfig`, `MCPServer`, `MCPServerStatus`, providers
- Errors and limits
- Code locations
