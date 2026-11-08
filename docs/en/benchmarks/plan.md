# What we measure next

The [current results](/benchmarks/) cover one process, one SQLite shard and one user, measured before the multi-user, shard and sandbox changes. This page lists what the second round will measure. Each experiment states the question first, so that a result counts whichever way it comes out.

The rules stay the same as the first round: simulated model and tools unless stated, one experiment at a time on an idle machine, raw output kept in `bench/results/`, and every number on the site traceable to a file there.

| # | Experiment | Question | Status |
|---|---|---|---|
| 1 | Re-run on v0.11 | Do the first-round numbers still hold after the multi-user, shard and sandbox changes? | Planned |
| 2 | The slowdown past 3,000 sessions | At 4,096 active sessions a turn takes 3.9 s longer than alone, yet CPU, memory and connection waits do not explain it. Where does the time go? | Planned |
| 3 | Lease takeover | When the process holding a shard is killed, how long until a standby serves it, and does any turn run a tool twice or get lost? | Planned |
| 4 | Noisy neighbours | When one user floods the shard or their model key fails, how much do other users' waits and turn times change? | Planned |
| 5 | Multi-shard scaling | With 2 and 4 shard processes, does throughput grow in proportion, and what does the router add? | Planned |
| 6 | Long histories | The capacity table uses 3 turns of history. How do CPU, memory and latency grow at 100 and 1,000 turns? | Planned |
| 7 | Real model sample | With a real provider on a small scale, how far do turn times and failure modes differ from the simulation? | Planned |

## How each one will be run

**1. Re-run.** The same commands as the first round, on the current engine, three runs each so that each number has a spread.

**2. The slowdown.** Profile the 4,096-session run (CPU, blocking and mutex profiles, SQLite busy time) and record when each turn is admitted, starts its model call and finishes. The peak of in-flight model requests, 3,774 against 4,096 sessions, is the first lead.

**3. Lease takeover.** The `crash -lease` mode already starts a standby process. Report the gap from the kill to the first turn served by the standby, and the same correctness checks as the crash test: every turn completes, no tool runs twice, interrupted calls are marked as possibly applied.

**4. Noisy neighbours.** Two groups of users on one shard. One group submits far beyond its slot share, or its connection returns errors; measure the other group's p50 and p99 against a run without it.

**5. Multi-shard scaling.** Shards as separate processes, each with its own database, behind the router. Report throughput and p99 per shard count, and the router's added latency.

**6. Long histories.** Sessions pre-filled with 100 and 1,000 turns, then the capacity test. Report CPU per turn, resident memory and p50.

**7. Real model sample.** A few dozen sessions on a real provider, so that the simulation's assumptions (constant latency with jitter, no first-token delay, no token limits) can be checked against reality.
