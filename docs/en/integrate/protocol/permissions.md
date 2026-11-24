# Permissions

Permission settings decide which of the agent's tool calls run at once, which ask the user first and which are refused. The protocol reads and writes three layers: the user's settings, a workspace's and a session's, each replaced whole by its own `*/updatePermissions` method. When the user chooses "always allow" in an approval, a rule is also written into the workspace's or the session's layer.

Whether a call needs asking, and how to answer once it does, is on [approvals and questions](/integrate/protocol/approvals); how rules are evaluated and commands parsed is on the engine's [permissions and approvals](/engine/permissions). This page covers only what a client can see.

::: info Full page in Chinese
This page is being translated. The complete version, with every method, notification, type and real message, is [in Chinese](/zh/integrate/protocol/permissions).
:::

The full page covers:

- Concepts and state: the four layers, the approval policies
- Typical flows: changing the user's permissions, a session's, and a workspace's (with an edit that is refused); always allow
- Methods: `settings/updatePermissions`, `thread/updatePermissions`, `workspace/updatePermissions`; why `thread/start` takes no permissions; validation
- Notifications
- Types: `PermissionSettings`, `PermissionRules`, `ApprovalPolicy`, parameter types
- Rule syntax
- Errors and limits
- Code locations
