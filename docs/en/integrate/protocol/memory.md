# Memory

Long-term memories are notes the engine learns from ended turns. A client lists them by scope, edits, moves and forgets them with `memory/*`, follows every write, the background extraction's included, with `memory/changed`, and reads extraction's progress with `memory/status`. The switches that turn memory and learning on and off are in the user's settings.

::: info Full page in Chinese
This page is being translated. The complete version, with every method, notification, type and real message, is [in Chinese](/zh/integrate/protocol/memory).
:::

The full page covers:

- Concepts and state: scopes, statuses, the host's extraction model and the user's `memory` and `learn` switches
- Memory in a turn: the `memoryContext` item
- Typical flows
- Methods: `memory/list`, `memory/status`, `memory/update`, `memory/move`, `memory/forget`
- Notification: `memory/changed`
- Types: `MemoryRow`, `MemorySource`, `MemoryReference`, `MemoryStatus`
- Errors and limits
- Code locations
