# Execution traces

An execution trace is the full record a run leaves behind: what the model said and thought, which tools it called with which arguments and results, who approved what, and how many tokens it used. Ollupi does not write a separate copy for it: each session (thread) is already an append-only log, every step is written to the log before it runs, and the log, with the turns and items folded from it, is the trace. For the log's write rules and tables, see [Persistence and recovery](/engine/persistence).

::: info Full page in Chinese
This page is being translated. The complete version, with every detail and code reference, is [in Chinese](/zh/engine/traces).
:::

The full page covers:

- Why it is designed this way
- What is recorded
- How to read it back
- What it is used for
- Limits and known issues
