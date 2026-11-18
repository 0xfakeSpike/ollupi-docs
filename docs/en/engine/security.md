# Security overview

The agent reads and writes files, runs commands and reaches the network on the user's behalf, so its mistakes, and what a prompt injection hidden in a page or a file makes it do, land on the user. Ollupi holds it with three independent mechanisms: permissions decide whether a tool call happens, the sandbox decides what it can reach once it runs, and redaction decides what the model provider sees. Each call is decided as the model's answer is written to the conversation log; an approval holds for the frozen call it was asked about, and the tool checks that frozen content still holds before it runs.

::: info Full page in Chinese
This page is being translated. The complete version, with every detail and code reference, is [in Chinese](/zh/engine/security).
:::

The full page covers:

- Why it is designed this way
- Whom to trust
- Three lines of defence
- Approvals bound to what runs
- Isolating users
- Known gaps
