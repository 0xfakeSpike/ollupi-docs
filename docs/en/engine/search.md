# Search

Ollupi has three unrelated search paths: its own sessions and messages (the engine's `search` method), files in a workspace (the model's `grep` and `glob` tools), and the web (none). They differ in matching, indexing and permissions; when something cannot be found, first check which path was used.

::: info Full page in Chinese
This page is being translated. The complete version, with every detail and code reference, is [in Chinese](/zh/engine/search).
:::

The full page covers:

- Three paths
- Sessions, messages, tasks and memory: search
- Indexing and consistency
- File search: grep and glob
- Two ways into memory search
- Known limits
