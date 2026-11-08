# Scheduled tasks

A scheduled task is a message sent to a session on a cron schedule. When it is due it takes the same path as a message from the user: an idle session starts a turn, a busy one queues it. Tasks live in the `cron_jobs` table and a goroutine in the host checks them every minute; the engine has no `main` and starts no timers of its own.

::: info Full page in Chinese
This page is being translated. The complete version, with every detail and code reference, is [in Chinese](/zh/engine/cron).
:::

The full page covers:

- Data model
- Schedule expressions
- The trigger path
- After a turn
- Protocol and interface
- Limits
