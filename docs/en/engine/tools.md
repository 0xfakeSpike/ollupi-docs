# Tools

Tools are the actions a model can take. The `tools` package defines what a tool is, who provides it, and which steps a call goes through. Every tool call is an item, written before it runs, so each stage of it can be read back after the process restarts.

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
