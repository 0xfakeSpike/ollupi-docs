# Scheduled tasks

A scheduled task (a scheduled job in the engine's messages and tools, a cron job in the code) is a message sent to a session on a cron schedule. When it is due it takes the same path as a message from the user: it queues a turn in the session, which waits for a slot in order with the user's turns. Tasks live in the `cron_jobs` table; the `cron` package's `Run` checks them every minute, run by the host in `Host.Run` beside the scheduler. Sending a task and counting the run happen in one transaction.

::: info Full page in Chinese
This page is being translated. The complete version, with every detail and code reference, is [in Chinese](/zh/engine/cron).
:::

The full page covers:

- Data model
- Schedule expressions
- The trigger path
- After a run
- Protocol and interface
- Limits and known issues
