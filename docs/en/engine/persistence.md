# Persistence

All of Ollupi's run state is in SQLite. One database is one shard, and the users on a shard share its tables. Every step is written to the database before it runs, so whenever the process exits, the restarted process can read where it was. Scheduling does not depend on state in memory.

::: info Full page in Chinese
This page is being translated. The complete version, with every detail and code reference, is [in Chinese](/zh/engine/persistence).
:::

The full page covers:

- SQLite configuration
- Tables and relations
- The item model
- Write-before-run ordering
- Migrations
- The migration list
