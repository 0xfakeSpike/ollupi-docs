# Design decisions

This page records why Ollupi is built the way it is. Each decision has the same structure: context, decision, options dropped, cost, evidence. Only what can be traced to a commit, the code or a repository document is included.

::: info Full page in Chinese
This page is being translated. The complete version, with every detail and code reference, is [in Chinese](/zh/reference/decisions).
:::

The full page covers:

- Pooled runtime
- SQLite and write-before-run
- No scheduling state in memory
- Two layers of concurrency
- Subagents as ordinary sessions
- Scheduled tasks as messages
- A protocol aligned with the Codex app-server
- The protocol contract generated from the dispatch table
- Tools are for the model only
- One database per shard, with leases
- The sidecar shape
- Native Anthropic and Gemini clients
- Compact mode
- Memory snapshots and a stable prefix
- Redaction only at the model boundary
- Approvals bound to what runs
- Numbered migrations
- Fail loudly
- Logic lives in the layer that owns it
- The Seatbelt sandbox
- An in-house updater
