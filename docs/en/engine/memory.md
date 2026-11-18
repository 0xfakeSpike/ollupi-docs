# Memory

Memory lets the agent remember a user's preferences, a project's decisions and verified facts across sessions. The `extract` package distils notes in the background from turns as they end, a session loads a snapshot before its first model call, and the model searches the rest on demand with `memory_search`. Each user has two switches: memory decides whether memories are used and learned, learning only whether they are learned.

::: info Full page in Chinese
This page is being translated. The complete version, with every detail and code reference, is [in Chinese](/zh/engine/memory).
:::

The full page covers:

- The two switches
- Types and scopes
- Tables
- The distillation pipeline
- Protecting user edits
- Snapshots
- Search
- Retries and skips
- Limits and known issues
