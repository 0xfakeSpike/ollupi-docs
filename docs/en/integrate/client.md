# Writing a client

How to write a correct gateway client: connecting, reconnecting, keeping local state in step with the engine, and answering approvals and questions. The wire contract is on the [gateway protocol](/integrate/protocol) page and the fields of each type on [protocol data types](/integrate/protocol-types).

::: info Full page in Chinese
This page is being translated. The complete version, with a minimal Node client that was run against a real gateway, is [in Chinese](/zh/integrate/client).
:::

The full page covers:

- A minimal client
- Connecting: authentication and handshake, close codes, reconnecting
- Local state: subscribe before reading, notifications before replies, replacing rows, deltas, pagination and `seq`, subagents, session status
- Approvals and questions
- Sending, steering, queueing and interrupting
- Version compatibility and generating types
- Common mistakes
