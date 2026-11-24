# Models

`pkg/llm` brings three model APIs together behind one interface. The rest of the engine sees only `Chat` and `Limits`: send a list of messages, get back streamed text and a result. Each API's differences in reasoning content, caching and answer limits stay inside its own client.

```go
type Client interface {
	Chat(ctx context.Context, req ChatRequest, onDelta func(Delta)) (ChatResponse, error)
	Limits(model string) (Limits, error)
}
```

One client is one connection: one base URL, one key, a set of models with declared limits, and one pool of concurrent calls. The host puts clients in `host.Config.Connections` under each connection's name and lists the models users can choose in `host.Config.Models`; each model points to one connection, and a connection may appear only once. `host/models.go` combines the two into the set of models that `run` and `app` use.

::: info Full page in Chinese
This page is being translated. The complete version, with every detail and code reference, is [in Chinese](/zh/engine/models).
:::

The full page covers:

- Why it is designed this way
- Three clients
- One call
- Connections and concurrency limits
- Retries
- Reasoning and signature replay
- Cache breakpoints
- Token counting
- Usage
- Per-model settings
- Attachments
- Limits and known issues
