# Search

`search` is one method and one call: it looks up keywords in this user's session titles, messages, scheduled tasks and long-term memories at once, and returns them in four groups. It searches only data in the engine's database: not workspace files (that is the model's `grep` and `glob` tools), and not the web. Indexing, matching details and every limit are on [search](/engine/search) in the engine section; this page covers how a client calls it and reads the result.

::: info Full page in Chinese
This page is being translated. The complete version, with every method, notification, type and real message, is [in Chinese](/zh/integrate/protocol/search).
:::

The full page covers:

- Concepts
- Typical flow
- Method: `search`
- Matching details
- Types: `SearchResult`, `MessageHit`
- Errors and limits
- Code locations
