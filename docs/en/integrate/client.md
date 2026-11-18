# Writing a client

How to write a correct gateway client: connecting, reconnecting, keeping local state in step with the engine, and answering approvals and questions. A thread is read as one page at one commit (`seq`), and every later change arrives as a notification carrying its commit's `seq`: a client drops the notifications the page already holds and applies the rest, and reads again after reconnecting, since nothing is resent. The wire contract is on the [gateway protocol](/integrate/protocol) page and the fields of each type on the [protocol type index](/integrate/protocol-types).

::: info Full page in Chinese
This page is being translated. The complete version, with a minimal Node client and a thread copy that were run against a real v0.17.1 gateway, is [in Chinese](/zh/integrate/client).
:::

The full page covers:

- A minimal client
- Connecting: authentication and handshake, close codes, reconnecting
- Local state: notifications before replies, aligning with `seq`, replacing rows, deltas, pagination and `seq`, subagents, thread status
- Approvals and questions
- Sending, steering, queueing and interrupting
- Version compatibility and generating types
- Common mistakes
