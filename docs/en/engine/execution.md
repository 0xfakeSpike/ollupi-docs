# Execution model

Every runnable turn shares one execution pool: turns from users, from subagents and from scheduled tasks alike. A place in the pool is a slot; there are 32 by default. A turn runs only while it holds a slot. While it waits on a user, an approval or a subagent it gives the slot up and remains only as database rows, holding no goroutine and no model concurrency. When the wait ends, it queues again.

::: info Full page in Chinese
This page is being translated. The complete version, with every detail and code reference, is [in Chinese](/zh/engine/execution).
:::

The full page covers:

- The scheduling loop and slots
- The ready queue
- The turn state machine
- reconcile
- One run
- Each step of the loop
- When a turn gives up its slot
- Model concurrency limits
- Steering, queueing and interrupting
- Resuming after approvals and questions
- Subagents
- Scheduled tasks
