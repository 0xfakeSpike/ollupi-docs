# Benchmarks

This page answers how many sessions one Ollupi process serves at once, how it compares with pi and DeepSeek Harness, and whether it still finishes the work when the process is killed, the model fails, a command runs long or one user is heavy. It measures scheduling and persistence, not model quality.

**Conditions**: Ollupi v0.18.0, 2026-11-19, Apple M1 (8 cores, 8 GB), one SQLite database, one run per experiment. The engine is real (host, database, scheduler, gateway); only the model and the tools are simulated. The simulated model is reached through the real OpenAI client and answers 429 when more requests are in flight than its quota allows. Unless an experiment says otherwise, a model call takes 5 s ± 2 s, a tool call 1 s, and a turn makes 3 model calls and 2 tool calls: 17 s alone. Every number has its raw output in the engine repository's `bench/results/` and `bench/compare/results/`; the method and the commands are in `bench/README.md`.

What the next round measures is on [What we measure next](/benchmarks/plan).

## Answers

| Question | Answer |
|---|---|
| How does it compare with pi and DeepSeek Harness? | Least memory; the only one to finish all 3000 turns of a burst, and the only one to bring background results back after `kill -9`; slower than pi past 1024 sessions |
| How many sessions run at once before turns slow down? | At 1536, a turn takes 5% longer than alone; at 4096, 2.8 times as long, waiting for SQLite |
| What does a parked session cost? | 50,000 parked sessions hold 34 MB of resident memory, about 7 KB of disk each |
| 3000 turns submitted at once, quota 256? | All complete, no 429, in 1.04 times what the quota allows |
| Does a long command hold up other sessions? | Not in the background: new sessions wait 10 ms, against 144 s with the command in its turn |
| What survives `kill -9`? | Every turn; no tool call runs twice; a standby takes over in 1.3 s |
| Does one heavy user hold up the others? | Not with a per-user slot limit: the others wait 8 ms, against 206 s without |
| Do failing or slow model calls fail turns? | No: with 5% of requests failing, or a long tail, no turn fails |
| Does it slow down over a long run? | No: over 8 minutes and about 33,000 turns, turn time and memory hold |
| What does a long history cost? | From 8 to 55 turns of history, a turn goes from 3.6 s to 15.7 s, waiting for SQLite |

## Comparison

![Four harnesses under the same load](/images/bench-compare.svg)

The same simulated model and the same driver for all four. Ollupi runs as a process of its own and the driver reaches it over its protocol, with every 64 sessions belonging to one user on a connection of their own. Memory is phys_footprint of the process that hosts the sessions. Versions: pi-coding-agent 1.5.2, pi-durable 1.5.2, DeepSeek Harness 0.2.2-rc.5.

| | Ollupi | pi (SDK) | pi-durable | DeepSeek Harness |
|---|---|---|---|---|
| Memory per parked session | 14 KB | 90 KB | 64 KB | 147 KB |
| Memory, 2048 sessions running | 398 MB | 777 MB | 925 MB | 1371 MB |
| Turn p50 over alone, 2048 sessions running | +76% | +28% | +58% | +330% |
| 3000 turns at once, quota 256: completed | 3000 | 483 | 527 | 1764 |
| `kill -9` mid-run | Every turn completes; no tool call runs twice | Turns in progress stop | Every turn completes; no tool call runs twice | 980 of 1000 turns end interrupted |
| Background commands, `kill -9` while they run | 200 of 200 results come back | No background calls | No background calls | 0 of 200 come back |

Ollupi takes the least memory, and in the burst it is the only one to finish every turn: it holds the requests beyond the quota in its own queue, while the other three send them all and retry against the quota, and a turn whose retries run out fails. Its weak point is latency under heavy load: from 1024 sessions it is slower than pi, because every step is written before it runs, on the store's one SQLite connection (see [Capacity](#capacity)). Most of its 14 KB per parked session belongs to the signed-in users, about 0.56 MB of heap each; the same 2000 sessions under one user take 6.1 KB each. Every number and the method are in the engine repository's `bench/compare/README.md`.

## Capacity

![Sessions running at once and turn time](/images/bench-capacity.svg)

Closed loop: each session starts its next turn as soon as the last ends, 3 turns each; slots and model calls equal the sessions.

| Sessions | Turn p50 | p99 | Model calls/s | CPU (cores) | Resident memory | Waiting for SQLite per turn |
|---|---|---|---|---|---|---|
| 512 | 17.4 s | 21.6 s | 74 | 0.64 | 129 MB | 0.2 s |
| 1024 | 18.4 s | 24.6 s | 137 | 1.23 | 215 MB | 1.4 s |
| 1536 | 17.8 s | 22.4 s | 215 | 1.64 | 308 MB | 0.8 s |
| 2048 | 21.5 s | 27.1 s | 236 | 1.77 | 368 MB | 4.2 s |
| 3072 | 32.0 s | 43.8 s | 241 | 1.88 | 456 MB | 14.2 s |
| 4096 | 48.2 s | 69.8 s | 216 | 1.84 | 531 MB | 29.8 s |

The bottleneck is the database: the store keeps one SQLite connection (`pkg/sqlitedb`), and a turn makes 126 reads and 44 writes on it; a longer history makes it worse (see [Long run](#long-run)). Above 1536 sessions, the time a turn loses against running alone is nearly all time spent waiting for that connection (the two lines on the right coincide). CPU stays under 2 cores and memory far from any limit. An active session takes about 112 KB (the slope of resident memory from 512 to 4096 sessions), and a turn about 14 KB of disk.

## Memory

50,000 sessions parked waiting on their user: 34 MB of resident memory (10 MB of heap) and 341 MB of database, about 7 KB each; the process idles at 0.1 ms of CPU a second, and turns run beside them take 5.10 s for 5 s of model latency. The control is one Ollupi process per session, the per-agent isolation Ollupi replaces: 17.7 MB a process, before any container.

## Burst

3000 turns submitted at once, with 512 slots and the connection and the provider both at 256 requests. Ollupi holds the requests beyond the quota in its own queue: requests in flight peak at exactly 256, the provider answers no 429, no turn fails, and all complete in 182.9 s, where the quota allows 175.8 s. Harnesses that do not limit their requests send them all and retry against the quota; see the [comparison](#comparison).

## Background calls

![A long command in the background or in its turn](/images/bench-background.svg)

256 sessions, spread over 64 users, each run one turn with a 30 s tool call; 32 slots, and at most 32 commands at a time either way. Every second a new session sends a turn that takes 5 s alone. With the commands in the background, the new session's first model request waits 10 ms at p50 and its turn takes 5.1 s; with the commands in their turns, the long turns hold all 32 slots, and the new session waits 144 s and its turn takes 149 s. The 256 commands finish in about the same time either way: 243 s and 257 s, where 32 at a time allow 240 s.

## Recovery

![Recovery after kill -9, and waking idle sessions](/images/bench-recovery.svg)

500 sessions run tool calls, questions to the user, subagents and background calls (model 200 ms, tools 300 ms), killed with `kill -9` 30 times at random: all 600 turns complete, no tool call runs twice, and none of the 110 calls cut off is run again; all 100 background calls report back, 58 of them that they were cut off. A restart takes 29 ms at p50. With a 1.5 s lease and a standby waiting on the shard, 8 kills: all 480 turns complete, and the standby takes over in 1.3 s at p50.

A restart with 10,000 sessions waiting and 500 running is ready in 8 ms and has every running turn's model request out again within 346 ms. Waking an idle session takes 3.7 ms with 10 turns of history, 8.6 ms with 100 and 89 ms with 1000.

## Users

![A per-user slot limit](/images/bench-users.svg)

One shard with 512 slots; 32 users keep 8 sessions busy each and one user keeps 1024 busy, each on a key of their own. With no per-user limit, the heavy user takes every slot and the others' turns wait 206 s at p50. With `UserSlots` at 64, the others wait 8 ms and their turns take 17.1 s, as alone. When the heavy user's key is over its quota at the provider, its 7,389 429s and 148 failed turns stay its own; the others get no 429.

## Faults and long tail

1024 sessions with 5% of model requests answered 500 and other clients of the account holding up to 256 of the quota: no turn fails, and p99 is 25.0 s against 24.6 s without faults. 1536 sessions with log-normal model latency (median 5 s, σ = 0.6): no turn fails, p50 20.2 s, p99 43.1 s.

## Commands in a sandbox

1024 sessions whose tool calls each run `sleep 1` through `run_command`, up to 1024 processes at a time on 8 cores. Without a sandbox (full access), turn p50 is 34.1 s; in the macOS sandbox (workspace write), 104.1 s, with 563 ms of CPU per turn spent starting sandboxed processes. The fake tool takes 18.4 s.

## Mixed load and subagents

256 sessions send turns, 20% of them handed to subagents, while 1000 scheduled jobs come due at once: off the peak, a user's turn waits 8 ms at p50 and 3.2 s at p99 for its first model request; the peak drains in 56.9 s; no turn fails, and the Jain fairness index of turn time across sessions is 0.975. 64 turns each spawning 8 subagents on 32 slots: all 576 turns complete in 1.19 times the floor, and every parent waiting on its subagents gives up its slot.

## Long run

![Turn time and memory over a long run](/images/bench-soak.svg)

256 sessions send turns back to back for 8 minutes, with 1 s model calls and 0.2 s tool calls (3.4 s alone). After 10 turns a session is replaced by a new one, so each turn's work stays the same and only time goes by. Over 32,982 turns, turn p50 stays between 3.5 and 3.8 s, resident memory between 100 and 124 MB, goroutines between 854 and 1060, the WAL at 4.1 MB, and GC pause p99 within 0.16 ms.

`soak-history` runs the same load without replacing sessions, so each turn carries a longer history than the last: from 8 to 55 turns of history, turn p50 goes from 3.6 s to 15.7 s, of which 12.2 s is waiting for the database connection. A turn re-reads its history, and its reads and writes queue on the same connection as every other turn's.

## Connections

Idle client connections, one user each. Each adds about 50 KB of resident memory, 4 goroutines and one file descriptor to the shard, and 0.008 ms of CPU a second for pings; 8000 take 421 MB. Through a router, each adds 27–43 KB, 4 goroutines and 2 descriptors to the router. After the shard is killed and started again, 8000 clients reconnecting as the protocol says are all back in 83 s, and 4000 through a router in 44 s. The clients run on the same machine as the shard, so its limits on descriptors and ephemeral ports stop the test at 8000.

## What these numbers do not show

| To know | Why these numbers cannot say |
|---|---|
| Capacity with a real model | The simulated model has no time to first token, no token-based queueing and no provider rate windows |
| Real tool times | Except for the sandbox commands, the tools are fake tools of fixed duration |
| Scaling over shards | Every number comes from one process and one database; whether throughput doubles with the shards is not measured |
| Spread | Each experiment ran once; there are no error bars |
| Other machines | Measured on one M1 only |

## Reproducing

From the engine repository's root:

```bash
bench/run.sh                     # every Go experiment, about 2 hours
bench/run.sh -l                  # list the experiments and their commands
bench/run.sh steady-1024 crash   # only these
bench/compare/run-all.sh         # the comparison with pi and DeepSeek Harness
```

run.sh runs one experiment at a time; before each, it waits until Docker Desktop is not running, the lid is open, the CPU is at least 60% idle and no comparison is running, and it throws away a run the machine slept through. Each result is written to `bench/results/<experiment>.txt`, headed by the command, the commit, the time and the machine. Setting up the comparison is in `bench/compare/README.md`. `go test -tags sqlite_fts5 ./bench` runs each experiment at a size that ends in seconds and checks what it exists to show, without measuring.

## Code

| Path | Role |
|---|---|
| `bench/README.md` | Method, every result, commands |
| `bench/run.sh` | Runs the experiments by the measuring rules and heads each output |
| `bench/main.go`, `bench/burst.go` | Entry point, `parked`, the simulated model and provider, the fake tool |
| `bench/*.go` | The other experiments, one file each (`steady.go`, `background.go`, `crash.go`, `users.go`, `conns.go` and so on) |
| `bench/serve.go` | Runs a shard as a process of its own, for the comparison to drive over the protocol |
| `bench/compare/` | The comparison with pi and DeepSeek Harness |
| `bench/results/`, `bench/compare/results/` | Raw output |
| `docs/images/figures.py` | The figures on this page |
