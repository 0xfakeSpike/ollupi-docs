# Engine architecture

The Ollupi engine is a Go library, module path `github.com/0xfakeSpike/ollupi`. One process runs every session (thread) on a shard: each session is an append-only log in SQLite, turns, items and session status are all worked out from the log, and memory only records which sessions are holding a slot. This page covers the engine's layers, which way dependencies point, how the host assembles the parts, and which code a message passes through from the moment it arrives from the client until the answer is back in the interface.

::: info Full page in Chinese
This page is being translated. The complete version, with every detail and code reference, is [in Chinese](/zh/engine/architecture).
:::

The full page covers:

- Why it is designed this way
- Layers
- Dependency direction
- How the host assembles the engine
- The full path of one request
- The main objects in the process
- Limits and known issues
