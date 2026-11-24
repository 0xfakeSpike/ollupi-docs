# Writing a client

How to write a correct gateway client: how to connect, how to reconnect after a drop, how to keep local state consistent with the engine, and how to answer approvals and questions. The methods, notifications and error codes on the wire are on the [gateway protocol](/integrate/protocol) page and the fields of each type on the [protocol type index](/integrate/protocol-types); this page is only about using them correctly.

The desktop app is a ready-made reference implementation: `packages/client` is the typed connection, `packages/core/src/timeline.ts` merges notifications into local state, and `apps/desktop/src/renderer/src/gateway/session.ts` manages connecting and reconnecting. "The desktop app's approach" on the full page always means these files.

The code and behavior on the full page were run against engine v0.17.1: a minimal host (`host.New` with a scripted fake model implementing `llm.Client` and one tool that is not read-only, `deploy`, the balanced approval policy, and a gateway with a single-user token) ran on one machine, and the client connected to it and went through a plain answer, accepting and declining an approval, a structured question, and a wrong token. Behavior marked "measured" comes from scripted trials against this gateway.

::: info Full page in Chinese
This page is being translated. The complete version, with a minimal Node client and a thread copy that were run against a real v0.17.1 gateway, is [in Chinese](/zh/integrate/client).
:::

The full page covers:

- A minimal client
- Connecting: authentication and handshake, close codes, reconnecting
- Local state: notifications before replies, aligning with `seq`, replacing rows, deltas, pagination and `seq`, subagents, session status
- Approvals and questions
- Sending, steering, queueing and interrupting
- Version compatibility, including generating types from the contract
- Common mistakes
- Code locations
