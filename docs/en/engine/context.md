# Context management

Context management decides what each model call sends: the request stays within the length the model accepts, the session can go on indefinitely, and the start of the request stays the same so that the provider's prefix cache (a cache keyed on identical request openings) hits. The prompt is compiled again from the session log before every model call; log items keep their full content, and clipping and compaction affect only the view sent to the model.

The code is in the `prompt` package (`Window`, `Build`, `Compaction`, `System`); when to compact, and how the result is written to the log, is in `run/model.go`.

::: info Full page in Chinese
This page is being translated. The complete version, with every detail and code reference, is [in Chinese](/zh/engine/context).
:::

The full page covers:

- Why it is designed this way
- The window budget
- Assembling messages
- Clipping tool output
- Automatic compaction
- The system prompt
- Deferred tools
- Compact mode
- Prefix cache stability
- Limits and known issues
