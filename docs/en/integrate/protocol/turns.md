# Turns and items

A turn is one thing handed to the agent: it starts with a user message and lasts until the agent gives its answer. Every step in the turn is an item: the user message, the answer, reasoning, tool calls, subagent reports, compaction, memory loading, notices from the runtime, and errors. A client drives a turn with `turn/start`, `turn/steer` and `turn/interrupt`, and follows it with `turn/changed`, `item/changed` and the delta notifications.

Sessions themselves are on [sessions](/integrate/protocol/threads); approvals and questions, the two server requests the user must answer, are on [approvals and questions](/integrate/protocol/approvals); how to merge notifications into local state is on [writing a client](/integrate/client).

::: info Full page in Chinese
This page is being translated. The complete version, with every method, notification, type and real message, is [in Chinese](/zh/integrate/protocol/turns).
:::

The full page covers:

- Concepts and state: the status of a turn, items
- Typical flows: a whole conversation, queueing, steering, interrupting
- Methods: `turn/start`, `turn/steer`, `turn/interrupt`, `attachment/read`
- Notifications: `turn/changed`, `item/changed`, `item/agentMessage/delta` and `item/reasoning/textDelta`, `error`
- Types: `TurnRow`, `ResponseRow`, `Usage`, `ItemRow` (with the life of a tool call, and background calls and their reports), `UserInput`, `Attachment`, `ContextStats`, `Result` and `Artifact`, the notification wrapper
- Errors and limits
- Code locations
