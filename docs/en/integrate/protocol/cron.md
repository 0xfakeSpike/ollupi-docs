# Scheduled tasks

A scheduled task sends a message to a session on a cron schedule, and each run is an ordinary turn of that session. A client lists, creates, pauses and deletes tasks with `cron/*` and follows them with `cron/changed`.

::: info Full page in Chinese
This page is being translated. The complete version, with every method, notification, type and real message, is [in Chinese](/zh/integrate/protocol/cron).
:::

The full page covers:

- Concepts and state: tasks per session, the host's time zone, runs and what happens when one is due
- Typical flows
- Methods: `cron/list`, `cron/create`, `cron/pause`, `cron/delete`
- Notification: `cron/changed`
- Types: `CronJobRow`
- Errors and limits
- Code locations
