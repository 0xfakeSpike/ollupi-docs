# Embed the engine

The Ollupi engine is a Go library, module `github.com/0xfakeSpike/ollupi`. It has no `main`: opening the database, building model clients and tools, constructing `agent.Agent` and `gateway.Server`, and deciding when the process exits are the host's job. The desktop sidecar is one host and `bench/main.go` is another.

```sh
go get github.com/0xfakeSpike/ollupi
```

The engine needs SQLite's FTS5: build and test with `-tags sqlite_fts5`.

::: info Full page in Chinese
This page is being translated. The complete version, with every detail and code reference, is [in Chinese](/zh/integrate/embed).
:::

The full page covers:

- What the host is responsible for
- A minimal host
- Multiple users and shards
- Capacity and rate limits
- Shutdown, backup and upgrades
- Start-up checks and common errors
