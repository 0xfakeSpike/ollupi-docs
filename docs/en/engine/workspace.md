# Workspaces

A workspace is a project folder in the user's sandbox (`sandbox.Box`) that sessions belong to. The workspace tools (`tool/builtin/workspace`) run commands and read and write files there: which folder a tool call runs in, where it may write and which permission layer applies all follow from the session's workspace. The page covers both the workspace and these tools: `run_command`, `claude`, reading and searching, editing files with diffs, and what they freeze before approval.

::: info Full page in Chinese
This page is being translated. The complete version, with every detail and code reference, is [in Chinese](/zh/engine/workspace).
:::

The full page covers:

- Why it is designed this way
- What a workspace is, and adding one
- The workspace within a turn
- How tools use the workspace
- Provider configuration
- Permissions
- Archiving and moving
- How other features use workspaces
- The workspace tools: commands, `claude`, reading and searching, editing files, what is frozen before approval
- Limits and known issues
