# Scheduled tasks

A scheduled task sends a message to a session on a schedule, and when it falls due the result is an ordinary turn of that session. A client lists, creates, pauses and deletes tasks with `cron/*` and follows changes with `cron/changed`. The schedule syntax and the path from trigger to turn are on [scheduled tasks](/engine/cron) in the engine section; this page covers only what is visible in the protocol.

::: info Full page in Chinese
This page is being translated. The complete version, with every method, notification, type and real message, is [in Chinese](/zh/integrate/protocol/cron).
:::

The full page covers:

- Concepts and state: tasks per session, runs and what happens when one is due, the host's time zone
- Typical flows
- Methods: `cron/list`, `cron/create`, `cron/pause`, `cron/delete`
- Notification: `cron/changed`
- Types: `CronJobRow`, parameter types
- Errors and limits
- Code locations
