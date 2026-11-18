# Persistence

Ollupi keeps each conversation as an append-only log: entries are never changed once written, and turns, items, what a turn waits on and whether the conversation can run are all folded from that log. The log and what is folded from it live in one SQLite database, and one database is one shard, whose users share its tables. Every step is appended to the log before it runs, so whenever the process exits, the restarted process reads the log and knows where it was. No scheduling state lives in memory.

::: info Full page in Chinese
This page is being translated. The complete version, with every detail and code reference, is [in Chinese](/zh/engine/persistence).
:::

The full page covers:

- The conversation log: entries, and how they fold into a view
- The item model and the rules every entry must follow (`conversation.Check`)
- One write path: `store.Update` and `Tx.Append`
- The feed and its commit numbers
- Write-before-run ordering
- Crash recovery
- SQLite configuration
- Tables and relations
- Migrations
- The migration list
- Importing the old engine's database
- Attachment storage
