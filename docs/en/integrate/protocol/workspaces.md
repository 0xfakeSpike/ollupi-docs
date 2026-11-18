# Workspaces and environments

A workspace is the project folder a session (thread) belongs to; an environment is the machine its command and file tools run on. Both are chosen by `thread/start` and never change after; a client manages them with `workspace/*` and `environment/*` and follows them with `workspace/changed` and `environment/changed`.

::: info Full page in Chinese
This page is being translated. The complete version, with every method, notification, type and real message, is [in Chinese](/zh/integrate/protocol/workspaces).
:::

The full page covers:

- Concepts and state: deduplicated folders, archiving, `local` and `machine` environments
- Typical flows
- Workspace methods: `list`, `add`, `rename`, `move`, `archive`, `updatePermissions`
- Environment methods: `list`, `add`, `rename`, `delete`
- Notifications
- Types: `WorkspaceRow`, `EnvironmentRow`, `EnvironmentKind`
- Errors and limits
- Code locations
