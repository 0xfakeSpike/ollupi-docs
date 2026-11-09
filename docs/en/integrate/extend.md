# Extension points

The engine leaves five places for the host to plug in its own pieces: each user's model keys, its own tools, a cloud sandbox, attachment storage and its login system. Each one is a field of `agent.Config` or `gateway.Options` that takes a function or an interface implementation. All fields are in the [Config reference](/integrate/config).

::: info Full page in Chinese
This page is being translated. The complete version, with code that compiles against the engine, is [in Chinese](/zh/integrate/extend).
:::

The full page covers:

- Per-user model clients
- Your own tools: naming, annotations and approval, what the engine and the host each guarantee
- Cloud sandboxes: the three places `BoxFor` goes, choosing a box per conversation with `BoxIn`, an example `sandbox.Machine`
- Attachment storage
- Authentication
