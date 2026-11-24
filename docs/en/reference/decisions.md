# Design decisions

This page records why Ollupi is built the way it is. Each decision has the same structure: context, decision, options dropped, cost, evidence. Only what can be traced to a commit, the code or a repository document is included. "Options dropped" lists only approaches that really existed or that a document explicitly compared; where no record can be found, it says "no record".

The bench numbers cited all come from `bench/README.md`. They were produced with a simulated model and simulated tools, measured before multiple users, shards, the sandbox interface and the log rebuild (decision 26), and have not been measured again since.

::: info Full page in Chinese
This page is being translated. The complete version, with every detail and code reference, is [in Chinese](/zh/reference/decisions).
:::

The full page covers these 27 decisions, and ends with their code locations:

1. Pooled runtime: one process hosts every session, with no isolation per agent
2. SQLite and write-before-run: all state is in the database, and calls are split into `pending` and `inProgress`
3. No scheduling state in memory: memory keeps only the table of held slots; sessions waiting for a slot are read from the database
4. Two layers of concurrency: slots limit turns, connections limit model calls
5. Subagents as ordinary sessions: `Agent` is an ordinary tool, and subagents take the same path
6. Scheduled tasks as messages: when one is due, it calls the same entry point as the user
7. A protocol aligned with the Codex app-server: JSON-RPC over WebSocket, with the interface as just one client
8. The protocol contract generated from the dispatch table: the dispatch table is also the source of the schema
9. Tools are for the model only: the interface uses explicit methods and never calls tools directly
10. One database per shard, with leases: one SQLite file is one shard, held by one process
11. The sidecar shape: a Go backend embeds the engine, and the renderer connects to the gateway directly
12. Native Anthropic and Gemini clients: replay each provider's own message history
13. Compact mode: models with a small input budget get a short prompt and few tools
14. Memory snapshots and a stable prefix: one snapshot per session, no recall on every turn
15. Redaction only at the model boundary: the database stores real values, masked only before they go to the model
16. Approvals bound to what runs: what is approved is the frozen content, which is computed again before it runs
17. Numbered migrations: no more AutoMigrate, no more wiping the database
18. Fail loudly: no fallbacks that hide problems
19. Logic lives in the layer that owns it: one owner for each concept
20. The Seatbelt sandbox: based on Codex's profile, macOS only
21. An in-house updater: Squirrel.Mac does not work with ad hoc signing
22. Stone and moss, an interface that gives the conclusion first: areas laid out like a guide map, one ochre signal, process and detail folded away
23. The mark is a small wolf before the moon: the name kept and given a meaning, the mark changed to a friendly small wolf, the icon on an oat ground
24. The browser driven by Playwright: a mature library reads and operates pages, reaching tabs through an in-process CDP proxy without opening a debugging port
25. Themes, and dusk beside stone and moss: a theme is a set of tokens; dusk's paper floats smoothly over a frosted ground, with accents only in empty space
26. Rebuilt around the session log: a session is an append-only log, state is folded from the log, and changes are announced through the feed
27. Liveness through WebSocket heartbeats, not counting stalled reads: through a load balancer only ping/pong is end to end; a read held back by rate limiting or a backlog does not count as a lost connection
