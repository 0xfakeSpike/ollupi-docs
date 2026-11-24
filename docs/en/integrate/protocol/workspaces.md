# Workspaces and environments

A workspace is the project folder a session (thread) belongs to; an environment is the machine on which a session's command and file tools run. Both are chosen at `thread/start` and never change after; a client manages them with `workspace/*` and `environment/*`. How workspaces and environments map onto sandboxes inside the engine is on [workspace](/engine/workspace) and [extension points](/integrate/extend).

::: info Full page in Chinese
This page is being translated. The complete version, with every method, notification, type and real message, is [in Chinese](/zh/integrate/protocol/workspaces).
:::

The full page covers:

- Concepts and state: deduplicated folders, archiving, `local` and `machine` environments, the kinds of workspace (`project` and `hub`)
- Typical flows
- Workspace methods: `list`, `add`, `rename`, `move`, `archive`, `setKind`, `updatePermissions`, `updateInstructions`, `updateProviders`
- Environment methods: `list`, `add`, `rename`, `delete`
- Notifications
- Types: `WorkspaceRow`, `EnvironmentRow`, `EnvironmentKind`, `WorkspaceKind` and `WorkspaceProviders`, parameter types
- Errors and limits
- Code locations
