# Search

`search` looks up a user's session titles, messages, scheduled tasks and memories in one call and returns the four groups apart. Queries are bounded (200 characters, 8 words, 5 seconds), the scheduled-task group is named `cronJobs`, and a search within a workspace returns the global memories together with that workspace's.

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
