# Memory

Long-term memories are notes the engine distills from turns that have ended; a running session loads the part of them that fits. A client uses `memory/*` to see the memories and the state of extraction, and to correct, move or forget one on the user's behalf, and follows changes with `memory/changed`; the `memoryContext` item in a session tells the client which memories a turn carried. How extraction gathers evidence, merges and retries is on [memory](/engine/memory) in the engine section; the switches are in [settings](/integrate/protocol/settings).

::: info Full page in Chinese
This page is being translated. The complete version, with every method, notification, type and real message, is [in Chinese](/zh/integrate/protocol/memory).
:::

The full page covers:

- Concepts and state: scopes, statuses, user edits, and what decides extraction and loading
- Memory in a turn: the `memoryContext` item
- Typical flows
- Methods: `memory/list`, `memory/status`, `memory/update`, `memory/move`, `memory/forget`
- Notification: `memory/changed`
- Types: `MemoryRow`, `MemorySource`, `MemoryReference`, `MemoryStatus`, parameter types
- Errors and limits
- Code locations
