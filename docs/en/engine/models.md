# Models

The engine talks to models through one `llm.Client` interface, with native clients for OpenAI-compatible APIs, Anthropic and Gemini. Each connection declares its context and output limits and its own concurrency, and the engine replays each provider's own message history, including reasoning signatures.

::: info Full page in Chinese
This page is being translated. The complete version, with every detail and code reference, is [in Chinese](/zh/engine/models).
:::

The full page covers:

- Three clients
- One call
- Connections and concurrency limits
- Retries
- Reasoning and signature replay
- Cache breakpoints
- Token counting
- Per-model settings
- Attachments
