# Scheduled tasks

A scheduled task (scheduled job; a cron job in the code) is a message sent to a session (thread) on a cron schedule. When it is due, it takes the same path as a message from the user: it queues a turn in the session, which waits for a slot in order alongside the user's turns. Tasks are stored in the `cron_jobs` table; the `cron` package's `Run` checks them once a minute, and the host runs it in `Host.Run` alongside the scheduler.

::: info Full page in Chinese
This page is being translated. The complete version, with every detail and code reference, is [in Chinese](/zh/engine/cron).
:::

The full page covers:

- Why it is designed this way
- Data model
- Schedule expressions
- The trigger path
- After a turn
- Protocol and interface
- Limits and known issues
