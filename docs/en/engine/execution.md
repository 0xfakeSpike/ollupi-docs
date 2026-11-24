# Execution model

User turns, subagent turns and scheduled-job turns share one execution pool. A place in it is called a slot; there are 32 by default. Tool calls marked `background: true` have a pool of their own. The scheduler (`schedule`) decides which session (thread) holds a slot, and the run (`run`) moves the current turn forward inside that slot.

::: info Full page in Chinese
This page is being translated. The complete version, with every detail and code reference, is [in Chinese](/zh/engine/execution).
:::

The full page covers:

- Why it is designed this way
- The scheduler and slots
- The turn state machine
- One run
- Each step of the loop
- When a session gives up its slot
- Queueing, steering and interrupting
- Subagents
- Scheduled jobs and restarts
- Error handling and limits
