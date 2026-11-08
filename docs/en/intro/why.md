# Why Ollupi

## Personal agents mostly wait

A personal agent spends most of its life waiting: for the user to reply, for an approval, for a subagent, for a scheduled task to come due. While it waits it does no work, yet the usual way to host it still pays for it.

The usual way is one VM or container per agent. Isolation is simple, but cost follows the number of sessions, not the amount of work:

- An inactive session either keeps its process running or is rebuilt from a cold start.
- A session waiting on the user keeps its process suspended, still holding memory.
- A restart or a deploy interrupts whatever was in progress.

For a provider serving many users, that means paying for idle processes, or making users wait for cold starts.

## Pool the runtime, persist the run

Ollupi takes the approach backend services take with requests: many sessions share one pooled runtime, and the state of each run lives in a database rather than in a process.

- **Every step is written before it runs.** Model output, tool calls, approvals and plans are recorded first and executed second. No scheduling state lives in memory, so the process can die at any moment and the restarted one continues where it stopped. A tool call that was interrupted mid-run is marked as possibly applied, not run twice.
- **Waiting costs nothing.** A session waiting on a user, an approval or a subagent leaves the execution pool and remains only as database rows.
- **Concurrency is controlled.** Runnable turns share one queue and run in a fixed number of slots. Model calls are limited per connection to match the provider's account quota, so bursts queue instead of failing.
- **One mechanism for everything.** Subagents and scheduled tasks are ordinary sessions in the same pool, not special cases.

## What it costs

The design has a price, and the manual states it rather than hiding it:

- Writing every step first means more database work per turn: about 68 reads and 15 writes in the benchmark's turn.
- Per-turn CPU grows with history, because each turn re-reads its history and encodes the full request.
- Isolation between users on a shard is done by the engine, not by the operating system. Commands and files still go through a sandbox per user.

## What has been measured

On one 8 GB M1, with a simulated model and tools: 50,000 parked sessions add about 14 MB of resident memory; each active session takes about 160 KB, against 20 MB for one process per session; 4,096 sessions are active at once with a median turn of 20.9 s against 17 s alone. The numbers, their conditions and what they do not show are on [Benchmarks](/benchmarks/). They predate the multi-user changes; the [second round](/benchmarks/plan) re-measures them and adds lease takeover, noisy neighbours and multi-shard scaling.

## Two projects

- **[ollupi](https://github.com/0xfakeSpike/ollupi)**, the engine: a Go library for hosts that serve many users. Start with [Embed the engine](/integrate/embed).
- **[ollupi-desktop](https://github.com/0xfakeSpike/ollupi-desktop)**, a macOS app built on the engine. It is the engine's simplest real deployment, one user with many sessions, and it is used every day. Start with the [desktop quickstart](/app/install).

What comes next is on the [roadmap](/roadmap).
