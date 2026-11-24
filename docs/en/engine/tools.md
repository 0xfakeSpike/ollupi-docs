# Tools

Tools are the actions a model can call. The `tool` package is the runtime port: a `tool.Set` describes a set of tools for one user, supplies content for the permission decision, freezes what is to run, and runs it. `tool/kit` is how tools are written: providers list and run their own tools, and the registry combines them into a `tool.Set`. Built-in tools are in `tool/builtin/*`, and the tools of MCP servers in `tool/mcp`.

One call is one item, folded from the call, approval, start and result records in the log, so every stage of it can be read back after a restart; see [Execution model](/engine/execution) and [Persistence and recovery](/engine/persistence).

::: info Full page in Chinese
This page is being translated. The complete version, with every detail and code reference, is [in Chinese](/zh/engine/tools).
:::

The full page covers:

- Why it is designed this way
- The tool interface
- Background calls
- The registry
- The life of one call
- Built-in tools
- Handing output to the model
- Deferred loading
- Limits and known issues
