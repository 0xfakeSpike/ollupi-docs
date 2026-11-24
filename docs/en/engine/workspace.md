# Workspaces

A workspace is a project folder in the user's sandbox (`sandbox.Box`) that sessions belong to. The `workspace` provider's tools run commands and read and write files there, and which folder a call runs in, where it may write and which permission layer it goes through all follow from the session's workspace. A workspace also carries its own instructions, its choice of providers, and a kind (`project` or `hub`). See [Persistence and recovery](/engine/persistence), the [gateway protocol](/integrate/protocol/workspaces) and [Sandbox](/engine/sandbox).

::: info Full page in Chinese
This page is being translated. The complete version, with every detail and code reference, is [in Chinese](/zh/engine/workspace).
:::

The full page covers:

- Why it is designed this way
- Mechanism
- Workspace tools
- Limits and known issues
