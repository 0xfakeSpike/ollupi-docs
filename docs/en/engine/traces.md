# Execution traces

An execution trace is the full record of a run: what the model said and thought, which tools it called with what arguments and results, who approved what, and how many tokens it used. Ollupi keeps no separate trace. Each session is an append-only log, every step is appended before it runs, and the log with the turns and items folded from it is the trace. The engine writes no process logs and has no OpenTelemetry tracing.

::: info Full page in Chinese
This page is being translated. The complete version, with every detail and code reference, is [in Chinese](/zh/engine/traces).
:::

The full page covers:

- What is recorded: log entries, items, each model call, turns
- What is not recorded
- Where values live before and after redaction
- How to read a trace back
- What traces are used for
