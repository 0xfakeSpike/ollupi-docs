# Tools

Tools are the actions a model can take. The `tool` package is the port a run calls tools through: how a user's set of tools is described, gives content to the permission rules, freezes what it will do, and runs. `tool/kit` is how the engine's own tools are built, with the built-in ones under `tool/builtin`. Every tool call is an item folded from the conversation log, written before it runs, so each stage of it can be read back after the process restarts.

::: info Full page in Chinese
This page is being translated. The complete version, with every detail and code reference, is [in Chinese](/zh/engine/tools).
:::

The full page covers:

- The tool interface
- The registry
- The life of one call
- Freezing before approval
- Built-in tools
- Output truncation
- Deferred loading
