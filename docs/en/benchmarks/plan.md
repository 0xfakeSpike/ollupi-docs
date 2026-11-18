# What we measure next

The [current results](/benchmarks/) were measured on v0.8.3 to v0.8.5. They cover one process, one SQLite shard and one user, predate the multi-user, shard and sandbox interface changes and v0.16.0's log rebuild, and none was measured with `bench/run.sh`. This page lists what the next round will measure. Each experiment states the question first, so that a result counts whichever way it comes out.

The rules are those of `bench/README.md`: simulated model and tools unless stated; runs go through `bench/run.sh`, one experiment at a time on an idle machine, with any run the Mac slept through thrown away; raw output is kept in `bench/results/`, headed by the command, commit, time and machine, and every number on the site is traceable to a file there.

| # | Experiment | Question | Status |
|---|---|---|---|
| 1 | Re-run on v0.17.1 with run.sh | Do the first-round numbers still hold after the log rebuild? | Script ready, not measured |
| 2 | The slowdown past 3,000 sessions | On v0.8.5, at 4,096 active sessions a turn took 3.9 s longer than alone, yet CPU, memory and connection waits did not explain it. Is it still slow after the re-run, and where does the time go? | Planned |
| 3 | Lease takeover | When the process holding a shard is killed, how long until a standby serves it, and does any turn run a tool twice or get lost? | Written, not measured |
| 4 | Noisy neighbours | When one user fills their key, or their key goes over its limit at the provider, how much do other users' waits and turn times change? | Written, not measured |
| 5 | Cost of sandboxed commands | How much more does a tool call cost when it runs a real command through `run_command` and the sandbox than the fake tool? | Written, not measured |
| 6 | Cost of connections | How much memory, how many goroutines and descriptors, and how much CPU does each idle connection add to the shard and to the router? After the shard restarts, how long until every client is back? | Written, not measured |
| 7 | Multi-shard scaling | With 2 and 4 shard processes, does throughput grow in proportion, and what does the router add? | Planned |
| 8 | Long histories | The capacity table uses 3 turns of history. How do CPU, memory and latency grow at 100 and 1,000 turns? | Planned |
| 9 | Real model sample | With a real provider on a small scale, how far do turn times and failure modes differ from the simulation? | Planned |

## How each one will be run

**1. Re-run.** `bench/run.sh` with no arguments runs every experiment in the order `bench/run.sh -l` lists, each output carrying its command and commit and replacing the older files in `results/`. Among the questions: how many reads, writes and bytes of disk a turn takes under the log model (68 reads, 15 writes and about 11.6 KB on v0.8.5); whether parked sessions still use almost no memory; whether the new crash recovery (a run taking over a conversation marks calls that started without a result as cut off) still runs no tool twice. run.sh runs each experiment once and keeps one output; to give a number a spread, the same experiment has to be run several times with each output kept.

**2. The slowdown.** Profile the 4,096-session run: `steady` and `burst` take `-cpuprofile`, `soak` takes `-pprof`; add blocking and mutex profiles and SQLite busy time, and record when each turn is admitted, starts its model call and finishes. The first lead is the peak of in-flight model requests, 3,774 against 4,096 sessions on v0.8.5. First see whether the slowdown survives the re-run.

**3. Lease takeover.** `crash-lease` in run.sh (`crash -n 400 -kills 8 -lease 1500ms`) already has a standby process wait on the shard. Report the gap from the kill to the first turn served by the standby, and the same correctness checks as the crash test: every turn completes, no tool runs twice, interrupted calls are marked as possibly applied.

**4. Noisy neighbours.** `bench users` (`325792f`) puts 32 users on one shard, each on their own key and quota (`host.Config.ClientFor`), beside a heavy user who keeps more conversations busy than their key serves. It reports the others' wait for their first model request, turn times, the Jain fairness index, and 429s and failed turns per user. run.sh has three variants: `users`; `users-slots`, adding `-user-slots 64` to cap each user's slots with `host.Config.UserSlots`; and `users-limit`, which also has the heavy user's key go over its limit at the provider (`-heavy-calls 64 -heavy-limit 32`).

**5. Cost of sandboxed commands.** `steady -command` (`325792f`) makes each tool call a real `sleep` through `run_command` in the sandbox. run.sh has `steady-workspace-write` and `steady-full-access`, 1,024 sessions each, to compare p50, p99 and CPU per turn with `steady-1024`.

**6. Cost of connections.** `bench conns` (`ce11149`, v0.13.0) runs the shard, the router and the clients as separate processes, one idle connection per user, and reports per step the resident memory, heap, goroutines and descriptors each connection adds to the shard (and the router), and the CPU taken while only pings flow; `-storm` then kills the shard after the last step, starts it again and times the clients, reconnecting by the protocol's rules, until all are back. run.sh goes to 8,000 connections straight (`conns`) and 4,000 through the router (`conns-router`), limits set by descriptors and ephemeral ports on one machine; beyond them, raise the system limits or run on Linux.

**7. Multi-shard scaling.** Shards as separate processes, each with its own database, behind the router. Report throughput and p99 per shard count, and the router's added latency. No experiment exists for this yet.

**8. Long histories.** Sessions pre-filled with 100 and 1,000 turns, then the capacity test. Report CPU per turn, resident memory and p50. `resume` already times waking at 10, 100 and 1,000 turns of history; the capacity test has no option to pre-fill history yet.

**9. Real model sample.** A few dozen sessions on a real provider, so that the simulation's assumptions (constant latency with jitter, no first-token delay, no token limits) can be checked against reality.
