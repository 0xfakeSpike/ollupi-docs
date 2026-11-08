# Engine architecture

The Ollupi engine is a Go library, module `github.com/0xfakeSpike/ollupi`. It runs every session (thread) in one process: all run state is kept in SQLite, and only what is running right now is held in memory. A session that waits on a user, an approval or a subagent is a few rows in the database and uses no memory or CPU.

::: info Full page in Chinese
This page is being translated. The complete version, with every detail and code reference, is [in Chinese](/zh/engine/architecture).
:::

The full page covers:

- Layers
- Dependency direction
- The full path of one request
- The scheduling loop
- The main objects in the process
