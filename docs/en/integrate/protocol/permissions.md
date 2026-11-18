# Permissions

Permission settings decide which of the agent's tool calls run at once, which ask the user first and which are refused. A client reads and writes three layers: the user's, a workspace's and a session's, each replaced whole by its own `*/updatePermissions` method; the deployment's default layer sits beneath them and is not in the protocol. Accepting a call with "always allow" also writes its suggested rule into the workspace's or the session's layer.

::: info Full page in Chinese
This page is being translated. The complete version, with every method, notification, type and real message, is [in Chinese](/zh/integrate/protocol/permissions).
:::

The full page covers:

- Concepts and state: the four layers, how they merge, subagents, the approval policies
- Typical flows: changing the user's, a session's and a workspace's permissions; always allow
- Methods: `settings/updatePermissions`, `thread/updatePermissions`, `workspace/updatePermissions`, validation
- Notifications
- Types: `PermissionSettings`, `PermissionRules`, `ApprovalPolicy`
- Rule syntax
- Errors and limits
- Code locations
