# Context management

Context management decides what each model call sends. It solves three problems: a request must not exceed what the model accepts; a session must be able to go on indefinitely without failing as its history grows; and the start of the request must stay the same, so that the provider's prefix cache hits. The prompt is compiled from the conversation log before every model call by the `prompt` package; the log keeps every item in full, and clipping and compaction change only what the model is sent.

::: info Full page in Chinese
This page is being translated. The complete version, with every detail and code reference, is [in Chinese](/zh/engine/context).
:::

The full page covers:

- The window budget
- Assembling messages
- Clipping tool output
- Automatic compaction
- The system prompt
- Deferred tools
- Compact mode
- Prefix cache stability
- Context statistics
