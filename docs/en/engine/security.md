# Security overview

The agent reads and writes files, runs commands and reaches the network on the user's behalf, so the consequences of its mistakes, and of being steered by prompt injection (instructions hidden in web pages or files), land on the user. Ollupi constrains it with three independent mechanisms: permissions decide whether a tool call happens, the sandbox decides what it can reach once allowed, and redaction decides what the model provider can see. This page covers the trust boundaries, what each line of defence stops, what isolation between users relies on, and the known gaps. The mechanisms themselves are described in [Approvals and permissions](/engine/permissions), [Sandbox](/engine/sandbox), [Redaction](/engine/redaction) and [Shards and leases](/engine/sharding).

::: info Full page in Chinese
This page is being translated. The complete version, with every detail and code reference, is [in Chinese](/zh/engine/security).
:::

The full page covers:

- Why it is designed this way
- Whom to trust, and whom not to
- Three lines of defence
- Approvals bound to what runs
- Isolating users
- Known gaps
