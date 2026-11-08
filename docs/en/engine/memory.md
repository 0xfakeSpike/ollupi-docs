# Memory

Memory lets the agent remember a user's preferences, a project's decisions and verified facts across sessions. A background job distils notes from finished turns, a new session loads a snapshot, and the model searches the rest on demand with `memory_search`.

::: info Full page in Chinese
This page is being translated. The complete version, with every detail and code reference, is [in Chinese](/zh/engine/memory).
:::

The full page covers:

- Types and scopes
- Tables
- The distillation pipeline
- Protecting user edits
- Snapshots
- Search
- Retries and skips
