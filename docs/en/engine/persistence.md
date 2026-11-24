# Persistence and recovery

Each session is stored as an append-only log: records are never changed once written, and turns, items, what the session is waiting on and whether it can run are all folded from the log. The log and what is folded from it live in one SQLite database, and one database is one shard. Every step is appended to the log before it runs, so whenever the process exits, the restarted process reads the log and knows where it was. For scheduling, see [Execution model](/engine/execution).

::: info Full page in Chinese
This page is being translated. The complete version, with every detail and code reference, is [in Chinese](/zh/engine/persistence).
:::

The full page covers:

- Why it is designed this way
- The conversation log
- Items
- One write path
- Background calls
- The feed and `seq`
- Write before run
- Crash recovery
- SQLite configuration
- Tables and relations
- Usage and to-dos
- Migrations
- Attachment storage
- Limits and known issues
