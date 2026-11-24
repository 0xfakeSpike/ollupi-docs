# Memory

Memory lets the agent remember a user's preferences, a project's decisions and verified facts across sessions. The `extract` package distils notes in the background from turns that have just ended, a session loads a snapshot before its first model call, and the model looks up the rest on demand with `memory_search`. Each user has two switches: memory (`memory`) decides whether memories are used and learned, and learning (`learn`) decides only whether they are learned.

::: info Full page in Chinese
This page is being translated. The complete version, with every detail and code reference, is [in Chinese](/zh/engine/memory).
:::

The full page covers:

- Why it is designed this way
- The two switches
- Types and scopes
- Tables
- The distillation pipeline
- Protecting user edits
- Snapshots
- Search
- Retrying and skipping failures
- Limits and known issues
