# Extension points

The places the engine leaves for a host to plug in its own pieces are each a field of `host.Config` or `gateway.Options`, or an interface: fill in a function, or provide an implementation. All fields are in the [Config reference](/integrate/config), and a minimal host is on [embed the engine](/integrate/embed).

| Extension point | Where it goes | When left out |
| --- | --- | --- |
| Per-user model clients | `host.Config.ClientFor` | Every user shares the clients and quotas in `Connections` |
| Your own model client | The `llm.Client` interface, put in `Connections` or returned by `ClientFor` | The built-in OpenAI, Anthropic and Gemini clients |
| Your own tools | The `kit.Provider` interface, put in `host.Config.Tools` | Only the built-in tools and the user's own MCP servers |
| Cloud sandboxes | `host.Config.Boxes`, the workspace tools' `workspace.Options.BoxFor` or `BoxIn`; the `sandbox.Machine` interface | `Boxes` is required; fill in `sandbox.Here()` when users may use this machine fully |
| Attachment storage | The `app.Attachments` interface | `host.New` always uses the `<Home>/attachments` folder |
| Catalog | The `catalog.Catalog` interface, given to `shard.Member` and `router.NewLocator` | A SQLite file opened with `catalog.OpenSQL` |
| Authentication | `gateway.Options.Authenticate`, and the router's `router.NewLocator` | `Token`, with a single user, `default` |

The code on the full page compiles against engine v0.17.1 and passes `go vet`. The cloud sandbox part has not been run in a real container; for attachment storage and the catalog the page gives only implementations of the interfaces, not connected to real services.

::: info Full page in Chinese
This page is being translated. The complete version, with code that compiles against v0.17.1, is [in Chinese](/zh/integrate/extend).
:::

The full page covers:

- Per-user model clients
- Implementing a model client
- Your own tools: naming, annotations decide approval, what the engine guarantees and what the host is responsible for
- Cloud sandboxes, including choosing an environment per session
- Attachment storage
- The catalog
- Authentication
- Code locations
