# Config reference

Every structure a host fills when it assembles the engine is on this page: `host.Config`, the `gateway.Options` inside it and its connection parameters `wshub.Options`, the parameters of model connections, and `shard.Member` for multi-process deployments. Each field lists its type, its default, and what happens when it is raised, lowered or left out. The defaults are all filled in by `host.New` and `gateway.NewServer`; a minimal host is on [embed the engine](/integrate/embed).

::: info Full page in Chinese
This page is being translated. The complete version is [in Chinese](/zh/integrate/config).
:::

The full page covers:

- `host.Config`: every field, its default, and the defaults that only replace zero
- Model connections: `llm.Model`, the `calls` and `limits` of the built-in clients, `llm.Limits`
- `gateway.Options`, including `Connections` (`wshub.Options`) and `Admit`
- `shard.Member`
- `schedule.New` and how `host.New` calls it
- Code locations
