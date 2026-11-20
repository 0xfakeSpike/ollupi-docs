# What we measure next

The [current results](/benchmarks/) were measured on v0.18.0. This page lists what the next round will measure. Each experiment states the question first, so that a result counts whichever way it comes out. The rules are `bench/README.md`'s: run with `bench/run.sh`, one experiment at a time, on an idle machine; raw output stays in `bench/results/`, and every number on the site can be traced there.

| # | Experiment | Question | Status |
|---|---|---|---|
| 1 | SQLite connection | Capacity and the long run both slow down waiting for the store's one SQLite connection. With reads on a connection of their own, or fewer reads per turn, how far does the knee above 1536 sessions move? | Planned |
| 2 | Long history | The capacity table has 3 turns of history per session, and in the long run a turn already takes 15.7 s at 55. With 100 and 1000 turns of history filled in first, how do CPU, memory and latency grow? | Planned |
| 3 | Scaling over shards | With 2 and 4 shard processes, does throughput grow in proportion? What does the router add? | Planned |
| 4 | Real model sample | Run a small load against a real provider: how far are turn time and the ways turns fail from the simulation? | Planned |
| 5 | Spread | Each experiment ran once. Run the same one five times: how widely do the numbers spread? | Planned |

## How each one is done

**1. SQLite connection.** `steady` already reports the reads and writes per turn (126 and 44) and the time spent waiting for the connection (`conn_wait_ms_per_turn`). First use `-cpuprofile` to see which reads in a turn can be merged or cached, then try separate connections for reads and writes; after each change, run `steady-1536` to `steady-4096` and `soak-history` again and see how the wait and the knee move.

**2. Long history.** Give `steady` an option to fill in history first, writing 100 or 1000 turns into each session before the run, and report CPU per turn, resident memory, reads and writes, and p50. `resume` already times waking a session with 10, 100 and 1000 turns of history (3.7, 8.6 and 89 ms).

**3. Scaling over shards.** One process per shard, each with its own database, behind a router. Report throughput and p99 by the number of shards, and the latency the router adds. There is no experiment for this yet.

**4. Real model sample.** Run a few dozen sessions against a real provider, to see how far the simulation's assumptions (fixed latency with jitter, no time to first token, no token limits) are from reality.

**5. Spread.** run.sh keeps one output per experiment; run the key ones (`steady`, `burst`, `background`, `crash`) five times each, keeping every output, and give the median with the lowest and highest.
