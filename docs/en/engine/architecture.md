# Engine architecture

The Ollupi engine is a Go library, module `github.com/0xfakeSpike/ollupi`. One process runs every session (thread) of a shard: each session is an append-only log in SQLite, its turns, items and status are folded from that log, and memory holds only which sessions occupy a slot. Every change is appended in one store transaction and reaches the gateway, the scheduler and memory extraction through the store's feed, numbered by commit. `host.New` assembles the store, app, run, schedule, extract, cron and the gateway from a `host.Config`.

::: info Full page in Chinese
This page is being translated. The complete version, with every detail and code reference, is [in Chinese](/zh/engine/architecture).
:::

The full page covers:

- Layers
- Dependency direction
- How the host assembles the engine
- The full path of one request
- The main objects in the process
