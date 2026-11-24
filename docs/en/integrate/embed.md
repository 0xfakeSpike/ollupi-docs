# Embed the engine

The Ollupi engine is a Go library, module path `github.com/0xfakeSpike/ollupi`. It has no `main`: building model clients, choosing tools, giving each user a sandbox, listening on a port and deciding when the process exits are all the host's job. The `host` package puts the parts of the engine together: the host fills a `host.Config`, calls `host.New`, then runs `Run` and `Gateway.Serve`. `bench/main.go` and `eval/main.go` in the engine repository are hosts of this kind.

This page is for backend engineers who want to embed the engine in their own service: a minimal host that runs, and the things to handle before going live. Layering and assembly are on [engine architecture](/engine/architecture); slot scheduling and how a turn runs are on [execution model](/engine/execution).

```sh
go get github.com/0xfakeSpike/ollupi@v0.17.2
```

The engine uses SQLite's FTS5: build and test with `-tags sqlite_fts5` (or set `GOFLAGS=-tags=sqlite_fts5`). Without it, `store/sqlite/fts5.go` makes the build fail.

::: info Full page in Chinese
This page is being translated. The complete version, with a minimal host and a preflight check that compile against v0.17.2, is [in Chinese](/zh/integrate/embed).
:::

The full page covers:

- What the host is responsible for: what `host.New` assembles, what `Run`, `Gateway.Serve` and `Close` do, and what is left to the host
- A minimal host, and what to watch for in it
- Before going live
- Start-up checks and common errors, including the three problems `host.New` does not catch, and a preflight run on a temporary directory
- Code locations
