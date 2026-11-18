# Models

The engine talks to models through one `llm.Client` interface in `pkg/llm`, with native clients for OpenAI-compatible APIs, Anthropic and Gemini. Each connection declares its models' context and output limits and its own number of concurrent calls, sends only its own key and address, retries a failed try up to 8 times and gives up on a try once the provider has sent nothing for 3 minutes; the engine replays each provider's own message history, including reasoning signatures.

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
