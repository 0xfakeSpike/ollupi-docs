# Execution model

Every runnable session shares one execution pool: turns from users, from subagents and from scheduled jobs alike. A place in the pool is a slot; there are 32 by default. The scheduler learns from the store's feed which sessions can run and starts those that became runnable first, ordinary sessions before subagents, within the slots and each user's share. A session runs only while it holds a slot; each step, the run reads the session's log and asks `agent.Next` what to do: wait, run the pending tool calls, skip them, call the model or finish. While it waits on a user, an approval or its subagents it gives the slot up and remains only as its log, holding no goroutine and no model concurrency.

::: info Full page in Chinese
This page is being translated. The complete version, with every detail and code reference, is [in Chinese](/zh/engine/execution).
:::

The full page covers:

- The scheduler and slots
- The ready queue
- The turn state machine
- One run
- Each step of the loop
- When a session gives up its slot
- Model concurrency limits
- Steering, queueing and interrupting
- Resuming after approvals and questions
- Subagents
- Scheduled jobs
- Recovery after a restart
- Error handling
