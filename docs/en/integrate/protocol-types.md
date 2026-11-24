# Protocol type index

All 166 named types (`$defs`) in the gateway contract `protocol.schema.json`, and the module page that explains each. Fields, values and examples are on the module pages; the conventions every module shares (optional fields, times, IDs) are on the [gateway protocol](/integrate/protocol) page.

Types that only wrap parameters and have few fields (such as `ThreadRenameParams`) are explained in the parameter table of the matching method on the module page; this index records which module they belong to. Where the contract name differs from the Go name, the generator's `defNames` renames it: `PermissionSettings` (`policy.Settings`), `AgentRole` (`agent.Name`), `WorkspaceProviders` (`account.Providers`), `PreparedExecution` (`workspace.Prepared`), `UserInputRequest` (`ask.Request`), `HubWorkspace` (`hub.Workspace`). When two types collide on a name, the generator fails outright and asks for a name for one of them in `defNames`. See generating and testing the contract on the [gateway protocol](/integrate/protocol) page.

::: info Full page in Chinese
This page is being translated. The complete index is [in Chinese](/zh/integrate/protocol-types).
:::

The full page lists the types by module:

- Handshake (on the overview page)
- Sessions
- Turns and items
- Approvals and questions
- Permissions
- Workspaces and environments
- Models, tools and MCP
- Scheduled tasks
- Memory
- Search
- Settings
- Todos
- Usage
- Hub tools
- Code locations
