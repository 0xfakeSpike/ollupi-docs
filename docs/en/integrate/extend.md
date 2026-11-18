# Extension points

The places where a host plugs in its own pieces are fields of `host.Config` or `gateway.Options`, or interfaces: each user's model client (`ClientFor`), a model client of its own (`llm.Client`), its own tools (`kit.Provider`), cloud sandboxes (`Boxes`, `sandbox.Machine`), attachment storage (`app.Attachments`), the catalog (`catalog.Catalog`) and authentication (`Authenticate`). All fields are in the [Config reference](/integrate/config).

::: info Full page in Chinese
This page is being translated. The complete version, with code that compiles against v0.17.1, is [in Chinese](/zh/integrate/extend).
:::

The full page covers:

- Per-user model clients
- Implementing a model client
- Your own tools: naming, annotations and approval, what the engine and the host each guarantee
- Cloud sandboxes: where the box function goes, choosing a box per conversation with `BoxIn`, an example `sandbox.Machine`
- Attachment storage
- The catalog: the contract each `catalog.Catalog` method keeps
- Authentication
