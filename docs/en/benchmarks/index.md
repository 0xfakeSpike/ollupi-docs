# Benchmarks

This page answers how many sessions one Ollupi process can serve, and whether it still finishes the work when the process is killed, the model fails or scheduled tasks pile up. The data comes from `bench/README.md` and `bench/results/` in the engine repository. It measures scheduling and persistence, not model quality. Read the first section before the numbers: which engine version each number was measured on, and under what conditions, matters more than the number itself.

What the next round measures is on [What we measure next](/benchmarks/plan).

## Method and limits

`bench` is a host program for the engine: real host assembly, a real SQLite database, real scheduling and persistence. Only the model and tools are simulated. In v0.17.2 it is assembled with `host.New` like any other host (`032b918`); the numbers below were measured on an earlier engine, assembled through the entry point of its day.

| Item | How |
|---|---|
| Model | `bench provider`, a fake OpenAI-compatible endpoint reached through the real OpenAI client: latency plus or minus jitter, and 429 when in-flight requests exceed the quota |
| Tools | A fake tool, `bench__work`, that returns after a set time; no files, no commands. `steady -command` is the exception; see [Written but not yet measured](#written-but-not-yet-measured) |
| One turn | 3 model calls and 2 tool calls; by default 5 s ± 2 s per model call and 1 s per tool call, about 17 s alone |
| Machine | Apple M1, 8 cores, 8 GB, one SQLite database |
| Engine version | See the table below; no number was measured on v0.17.2 |

| Numbers | Measured | Raw output |
|---|---|---|
| `steady` (six sizes, faults, long tail), `mix`, `fanout`, `soak` | Re-run on an idle machine on 2026-11-04 (`350df4b`), engine code identical to v0.8.5; output committed with `9a35769`, which is v0.8.5 | The `.txt` files and `soak.csv` in `results/` |
| `burst` | 2026-11-02, v0.8.4 (`c6da32f`) | Only the timeline, `results/burst.csv` (`7879e35`) |
| `parked`, `isolated`, `resume` | 2026-11-02, v0.8.4 (`c6da32f`) | Not kept |
| `crash` | 2026-11-02, v0.8.3 (`c326c52`) | Not kept |

Three things to read together:

1. **The numbers predate every architectural change since.** v0.9 to v0.11 added multiple users, shards and the sandbox interface, and v0.16.0 rebuilt the engine around the conversation log. The v0.16.0 tag says bench's numbers predate the rebuild and are to be measured again; `bench/README.md` says the numbers in `results/` predate the multi-user, shard and sandbox interface changes and have not been re-measured since. The [design decisions](/reference/decisions) record the same (`d85f978`).
2. **No number has been measured with run.sh yet.** `bench/run.sh` (`0fddf92`, 2026-11-12) runs the experiments one by one under fixed rules and heads each output with the command, commit, time and machine (the rules are under [Reproducing](#reproducing)). None of the files now in `results/` has that header; all of them are older. The README's table marks every experiment "not yet measured with run.sh" or "not yet measured".
3. **Each number is one run, and the simulation costs nothing real.** No repeats, no error bars: connection wait is 15.2 ms at 1,536 sessions and 6.3 ms at 2,048, and inconsistency between neighbouring rows is of that size. No first-token delay, no token billing, no model differences; the fake tool touches no disk, processes or network.

So the conclusions are about scheduling and storage only, and hold only for the version they were measured on: how many sessions fit, how much survives a kill, and whether queueing is fair. End-to-end response time needs its own measurement; whether any of this holds for v0.17.2 waits on a run.sh re-measurement.

## Experiments

Experiment names are those in `bench/run.sh`; `bench/run.sh -l` lists the command for each.

| Experiment | Command (after `bench`) | Measures | Result | Measured on | Raw output |
|---|---|---|---|---|---|
| `parked` | `parked -n 50000 -state waiting -latency 5s -rounds 3` | Memory and disk of parked sessions, and their effect on active turns in the same process | About 14 MB; active turns almost unchanged | v0.8.4 | Not kept |
| `isolated` | `isolated -k 20` | One process per session, for comparison | 20.0 MB per session | v0.8.4 | Not kept |
| `steady-512` … `steady-4096` | `steady -c N`, `slots` and `calls` follow `c` | Closed loop: the next turn starts when the last ends | p50 20.9 s at 4,096 | v0.8.5 | `results/steady-*.txt` |
| `steady-faults` | `steady -c 1024 -fail 0.05 -others 256` | Failing model requests, quota taken by others | 0 failures, p99 28.5 s | v0.8.5 | `results/steady-faults.txt` |
| `steady-lognormal` | `steady -c 1536 -sigma 0.6` | A long tail in model latency | 0 failures, p99 42.4 s | v0.8.5 | `results/steady-lognormal.txt` |
| `steady-workspace-write`, `steady-full-access` | `steady -c 1024 -command workspace-write` (or `full-access`) | Each tool call runs a real `sleep` through `run_command` in the sandbox | Not yet measured | — | None |
| `burst` | `burst -n 3000 -slots 512 -calls 256 -latency 5s -jitter 2s -tool 1s` | Queueing and quota when many turns arrive at once | No 429s, 1.03 times the floor | v0.8.4 | `results/burst.csv` |
| `resume` | `resume` (defaults `-history 10,100,1000 -waiting 10000 -running 500`) | Time from waking an idle session to its model request; restart time | Restart 448 ms | v0.8.4 | Not kept |
| `crash`, `crash-lease` | `crash -n 500 -kills 30`; `crash -n 400 -kills 8 -lease 1500ms` | Whether turns continue after random `kill -9`; with a lease, a standby takes over | 960 turns all complete (does not match these commands; see [Recovery](#recovery)); no result with a lease | v0.8.3 | Not kept |
| `mix` | `mix` (defaults `-c 256 -delegate 0.2 -peak 1000 -slots 512 -calls 256`) | Waits and fairness when user turns, subagents and scheduled tasks mix | Peak p50 44.1 s | v0.8.5 | `results/mix.txt` |
| `fanout` | `fanout` (defaults `-parents 64 -n 8 -slots 32 -calls 256`) | Whether parents give up slots when subagents outnumber slots | All 576 turns complete | v0.8.5 | `results/fanout.txt` |
| `soak` | `soak -c 256 -d 8m -every 30s -latency 1s -jitter 200ms -tool 200ms` | Whether latency, memory, goroutines, GC and database growth stay steady | Goroutines and WAL steady | v0.8.5 | `results/soak.csv` |
| `users`, `users-slots`, `users-limit` | `users`; with `-user-slots 64`; with `-heavy-calls 64 -heavy-limit 32` as well | Many users on one shard, each on their own key and quota, beside a heavy user who fills their key | Not yet measured | — | None |
| `conns`, `conns-router` | `conns -n 1000,2000,4000,8000 -storm`; `conns -n 1000,2000,4000 -router -storm` | The cost of idle client connections, straight to the shard or through a router; reconnection after the shard restarts | Not yet measured | — | None |

## Key numbers

Every number in this section was measured on the version the table above gives, not on v0.17.2.

### Memory and isolation

Measured on: `parked` and `isolated` on v0.8.4; the per-active-session row is derived from `steady` on v0.8.5.

| Item | Value | Conditions |
|---|---|---|
| Resident memory added by 50,000 parked sessions | About 14 MB | Sessions waiting on the user; includes the test program's own records |
| Disk per parked session | About 2.3 KB | Same |
| Memory per parked session | About 0.3 KB | From resident memory |
| p50 of active turns before and after parking | 5.04 s → 5.05 s | Active turns in the same process as the parked sessions |
| Per active session | About 160 KB | Slope of resident memory from 512 to 4,096 sessions: (692 − 132) MB ÷ 3,584 sessions. Dividing one row whole, 2,048 sessions give 407 MB ÷ 2,048 ≈ 204 KB, including the process baseline |
| One process per session, for comparison | 20.0 MB | Excluding container overhead |

![Parked sessions cost database rows, not process memory](/images/bench-memory.svg)

Sessions on the horizontal axis, resident memory on the vertical; the baseline is 20.0 MB per session with one process each.

### Capacity

Measured on: v0.8.5, 2026-11-04.

Closed loop: the next turn starts when the last ends. In every row, `slots`, `calls` and the quota equal the session count, with `refused_429=0` and `failed_turns=0`.

| Active sessions | p50 | p95 | p99 | Model calls/s | CPU (cores) | Resident memory | Connection wait per turn |
|---|---|---|---|---|---|---|---|
| 512 | 17.1 s | 20.4 s | 21.4 s | 72 | 0.39 | 132 MB | 2.9 ms |
| 1024 | 17.2 s | 20.5 s | 21.6 s | 147 | 0.60 | 223 MB | 4.5 ms |
| 1536 | 17.3 s | 20.7 s | 21.9 s | 219 | 0.81 | 315 MB | 15.2 ms |
| 2048 | 17.3 s | 20.8 s | 22.1 s | 296 | 1.03 | 407 MB | 6.3 ms |
| 3072 | 18.0 s | 22.5 s | 24.0 s | 416 | 1.39 | 570 MB | 22.8 ms |
| 4096 | 20.9 s | 26.1 s | 27.7 s | 477 | 1.67 | 692 MB | 43.0 ms |

One turn alone takes 17.0 s (`alone_s` in each output); at 4,096 active sessions a turn takes 3.9 s longer. Each turn does 68 reads and 15 writes and uses about 11.6 KB of disk. These read and write counts belong to v0.8.5's storage; since v0.16.0 every step writes log entries, and how much that reads and writes is unknown until it is re-measured.

![Active sessions against turn time](/images/bench-capacity.svg)

Active sessions on the horizontal axis; turn time and model calls per second on the vertical.

### Burst

Measured on: v0.8.4, 2026-11-02.

3,000 turns submitted at once with 512 slots and a quota of 256: in-flight requests never exceeded the quota (the timeline's peak is 256), there were no 429s, and the run took 1.03 times the theoretical floor.

### Mixed load and fairness

Measured on: v0.8.5, 2026-11-04.

256 sessions send turns continuously (20% delegated to subagents) and 1,000 scheduled tasks come due mid-run. Wait means the time from submission to the first model request:

| Case | p50 | p99 |
|---|---|---|
| User turns outside the peak | 7 ms | 274 ms |
| User turns arriving during the peak | 44.1 s | 58.6 s |
| Subagent turns | 5 ms | 4.6 s |
| Scheduled tasks coming due | 29.6 s | 58.3 s |

The peak drained in 59.4 s, close to the floor the quota allows; the Jain fairness index of turn time across sessions is 0.978.

![Waits and quota during the peak](/images/bench-mix.svg)

Wait distributions by where turns came from; the drain time is at the lower right.

### Subagent fan-out

Measured on: v0.8.5, 2026-11-04.

64 turns each start 8 subagents, so 512 subagents run on 32 slots: all 576 turns complete in 1.11 times the theoretical floor, and every parent waiting on subagents gave up its slot. At the time, a parent waited for its subagent's result on the launching call; since v0.14.0 a launch returns at once and the report comes back to the parent turn as an item, and this experiment has no result on that mechanism yet.

### Faults and long tails

Measured on: v0.8.5, 2026-11-04.

| Injected | Scale | Result |
|---|---|---|
| 5% of requests return 500; other clients on the same account take up to 256 of the quota | 3,072 turns over 1,024 sessions | 0 failures; p99 from 21.6 s to 28.5 s; 3,005 429s and 509 500s, all absorbed by backoff and retry |
| Same, before backoff and retry existed | Same load | 326 turns failed (output not kept) |
| Log-normal model latency, median 5 s, σ = 0.6 | 4,608 turns over 1,536 sessions | 0 failures; p50 19.0 s, p99 42.4 s |

Without faults or a long tail, the same row has p50 17.3 s and p99 21.9 s.

### Recovery

Measured on: `crash` on v0.8.3, `resume` on v0.8.4, both on 2026-11-02.

Under mixed load (tool calls, questions to the user, subagents), 90 random `kill -9`s in total: all 960 turns complete, no tool call runs twice, and every interrupted call is marked as possibly applied. This run shortens model calls to 200 ms and tool calls to 300 ms so that kills land in every phase of execution.

Where these numbers come from needs saying: they first appear in `c326c52` (Nov 2), before shard leases (`cd8faee`, Nov 5). The two `crash` commands in the README add up to 38 kills, not 90, and which runs produced the result was not recorded. The lease mode, where a standby process takes over (`-lease 1500ms`), has no reported result yet: takeover time and behaviour during takeover have no numbers. Since v0.16.0 crash recovery also works differently (there is no separate recovery pass; a run taking over a conversation marks calls that started without a result as cut off), and these numbers say nothing about that.

| Item | Value | Conditions |
|---|---|---|
| Restart | 448 ms | 10,000 parked sessions and 500 running turns |
| Waking an idle session to its model request, p50 | 73 ms | 1,000 turns of history |

![Restart and wake times](/images/bench-recovery.svg)

Left: wake time against history length. Right: restart time.

### Soak

Measured on: v0.8.5, 2026-11-04.

256 sessions for 8 minutes with 1 s model calls, about 35,000 turns:

| Item | Value |
|---|---|
| Goroutines | Steady at about 1,000 |
| GC pause p99 | Under 0.23 ms |
| WAL | Steady at 6.1 MB |
| Database growth | About 3.2 KB per turn |
| Turn p50 | 3.44 s to 3.60 s |
| CPU per turn | 12.1 ms to 34.8 ms (history from 8 to 138 turns) |
| Resident memory | 99 MB to 396 MB |

![Steady and growing quantities during the soak](/images/bench-soak.svg)

Steady goroutines and WAL drawn with growing CPU and memory.

### Against other harnesses

The same simulated provider and the same load, one run each. Memory: resident memory for Ollupi, `phys_footprint` for the other three.

| | Ollupi | pi (SDK) | pi-durable | DeepSeek Harness |
|---|---|---|---|---|
| Memory per parked session | About 0.3 KB | 91 KB | 23 KB | 181 KB |
| Increase in p50 at 2,048 active sessions | 2% | 2% | 314% | 77% |
| 3,000 turns at once, quota 256 | All complete | 2,534 failed | 2,181 failed | 2,190 failed |
| After `kill -9` mid-run | All continue, no tool runs twice | In-progress turns lost | All continue, no tool runs twice | Turns marked interrupted |

Versions: pi-coding-agent 1.4.0, pi-durable 1.4.0 (experimental), DeepSeek Harness 0.2.1-rc.5. Raw output is in `bench/compare/`. Ollupi's column comes from `parked`, `steady`, `burst` and `crash` above, on the same engine versions.

The table mixes some measures, and a reader should know where:

- **Dates differ.** The parked, burst and crash rows for the other harnesses were measured on 2026-11-02; their 2,048-session row was re-measured on 2026-11-04 (the last six lines of `compare/results/results.txt`), the same day as Ollupi's `steady`.
- **Parked counts differ.** Ollupi parked 50,000 sessions, pi-sdk and pi-durable 10,000 each, DeepSeek Harness 5,000.
- **Memory is read differently.** DeepSeek Harness runs as a separate process, read with `ps` and `footprint`: in the same run, RSS is 30.6 KB per session and `phys_footprint` 181 KB. The comparison uses footprint because macOS compresses pages when memory is short, which makes RSS read low; footprint counts compressed pages.
- **The burst row compares concurrency control, not only scheduling.** Ollupi limits in-flight requests per connection on the client side, so requests never exceed the quota. The other three do not limit concurrency and rely on their default retries (3 attempts with exponential backoff from 2 s for both pi harnesses; 5 attempts from 500 ms to 10 s for DeepSeek Harness); turns that run out of retries end with an error.

## Written but not yet measured

The code for these experiments is in v0.17.2. `go test -tags sqlite_fts5 ./bench` runs each experiment at a size that ends in seconds and checks what it exists to show (turns end, none fail, no tool runs twice, the users beside a heavy one draw no 429), but measures nothing. `bench/README.md` marks them "not yet measured".

| Experiment | Question | Output |
|---|---|---|
| `steady -command workspace-write`, `-command full-access` | Each tool call runs a real `sleep` through `run_command` in a sandbox of that mode; how much more does a sandboxed command cost than the fake tool? | The same line as `steady` |
| `users` | 32 users (by default) on one shard, each on their own key and quota with 8 conversations busy, beside one heavy user who keeps 1,024 conversations busy, more than their key serves. How long do the others wait for their first model request? | Waits and turn times for the others and for the heavy user, the Jain index among the others, 429s and failed turns per user |
| `users -user-slots 64` | Does a per-user slot cap (`host.Config.UserSlots`) keep the others' turns from waiting on the heavy user? | Same |
| `users -user-slots 64 -heavy-calls 64 -heavy-limit 32` | When the heavy user's key goes over its limit at the provider, do the 429s stay theirs? | Same |
| `conns -n 1000,2000,4000,8000 -storm` | Per idle connection (one user each), how much resident memory, heap, goroutines and file descriptors the shard process adds, and how much CPU pings take while nothing else happens; then the shard is killed and started again, and the clients, reconnecting as the protocol says, are timed until all are back | One `step` line per size, then a `storm` line |
| `conns -n 1000,2000,4000 -router -storm` | The same with clients reaching the shard through a router (`router.Router`), each of the two a process of its own, with the costs of each side given | Same, with the router's numbers added |

`conns` runs the clients on the same machine, so the operating system's limits stop it before ollupi does. Every connection takes a descriptor in the client and in the shard, and through a router two more in the router, which also dials the shard from one local address, using one ephemeral port per connection. On macOS a process may hold `kern.maxfilesperproc` descriptors (10,240 on the test machine), and the ephemeral ports of one address run from `net.inet.ip.portrange.first` to `.last` (16,384); on Linux the limits are `ulimit -n` and `net.ipv4.ip_local_port_range`. That is why run.sh takes the shard to 8,000 connections and the router to 4,000. Beyond them, raise these limits or run on Linux; `-sources` spreads the clients over more local addresses, which on macOS must first be added to `lo0`. A step a limit stops prints `stopped=not_all_connected` and its failure count, with the last error on stderr.

## What the numbers support

What follows is drawn from `steady` on v0.8.5 and `parked` and `burst` on v0.8.4; whether it still holds for v0.17.2 waits on re-measurement.

What follows from them:

- **Turns slow down from about 3,000 active sessions, and the cause is not yet known.** p50 is 17.3 s at 2,048, 18.0 s at 3,072 and 20.9 s at 4,096, against 17.0 s alone. That shows a slowdown, not a ceiling: at 4,096 the process uses 1.67 of 8 cores, 692 MB of memory and 43 ms of connection wait per turn, none of which explains the extra 3.9 s. One lead is the peak of in-flight model requests: equal to the session count up to 2,048, 3,053 at 3,072, and only 3,774 at 4,096. That may mean some sessions are stuck before their model call, or only that submissions did not all land at once (early turns finish before the last ones are submitted); the current output cannot tell which.
- **Memory is not the first limit.** 4,096 active sessions take 692 MB while CPU is at 1.67 cores (0.39 to 1.67 cores from 512 to 4,096).
- **Parked sessions use almost no memory.** 50,000 take about 14 MB of resident memory and about 2.3 KB of disk each; at 20.0 MB per process, one process per session is a different order of magnitude.
- **In a burst, the quota is the limit, not scheduling.** 3,000 turns under a quota of 256 in-flight requests take 1.03 times the floor the quota sets, and in-flight requests never exceed the quota.

![Pooling compared with one process per session](/images/cli-vs-ollupi.svg)

Two shapes on the same machine: on the left one process per session, still held while waiting on the user; on the right only turns holding slots are running.

What does not follow:

| Question | Why the numbers cannot answer it |
|---|---|
| Any number for v0.17.2 | Every number was measured on v0.8.3 to v0.8.5; the multi-user, shard and sandbox interface changes and v0.16.0's log rebuild have not been re-measured |
| Capacity with real model latency | Simulated latency is a constant plus jitter, with a long tail in only one run (σ = 0.6); no first-token delay, rate-limit windows or token-billed queueing |
| Real tool time | Tools take a fixed 1 s (0.2 s in the soak); files, commands, MCP, the browser and the sandbox are not in the load. The sandboxed-command experiment is written but not measured |
| Behaviour across shards | Every number comes from one database, one connection and one process; the catalog, lease renewal and standby takeover were not measured |
| Cost of multiple users | The results use one user; `users` is written but not measured |
| Cost of connections | The results do not go through the gateway; `conns` is written but not measured |
| Cost of long conversations | The capacity table has 3 turns of history per session; by 138 turns in the soak, CPU per turn is already 34.8 ms, which the capacity table does not include |

## Reproducing

Requires a Go toolchain and the `sqlite_fts5` build tag; run from the engine repository root. Measurements meant to be kept go through `bench/run.sh`:

```bash
bench/run.sh                     # every experiment, one after another
bench/run.sh -l                  # list the experiments and their commands
bench/run.sh steady-1024 crash   # only these
```

run.sh holds to these rules:

- Before each experiment it waits until Docker Desktop is not running, the lid is open, the CPU is at least 60% idle and no [comparison](#against-other-harnesses) is running, checking every 30 seconds and saying on stderr what it waits for.
- It runs one experiment at a time and leaves a lock file while it runs, which the comparison scripts wait on; `caffeinate` keeps the Mac from idle sleep.
- After each run it reads the system log; a run the Mac slept through is thrown away and run again, and if both tries slept it stops. Closing the lid sleeps the system, which `caffeinate` does not prevent.
- Each result goes to `results/<experiment>.txt`, headed by two lines: the command, and the commit (noting uncommitted changes), the start time and the machine.

The subcommands can also be run directly, for example `go run -tags sqlite_fts5 ./bench steady -c 3072`; such a run is not held to the rules above and its output has no header. Each experiment builds its database in a temporary directory and deletes it afterwards.

Durations (from the outputs kept): the six `steady` rows (512 to 4,096) took 63.7, 62.8, 63.0, 62.3, 66.4 and 77.3 s (`total_s`); `mix` 269 s (`run_s`); `fanout` 301.2 s (`total_s`); `soak -d 8m` runs the full 8 minutes plus setup. `parked`, `isolated`, `resume` and `crash` kept no output, so their durations were not recorded; `burst` kept only its timeline, `results/burst.csv`, which shows about 181 s.

`go test -tags sqlite_fts5 ./bench` measures nothing; it runs every experiment at a small size. `-short` skips it.

The comparison with other harnesses is in `bench/compare/`: `npm install --ignore-scripts`, `go build -tags sqlite_fts5 -o bench/compare/run/bench ./bench`, then `./run-all.sh` (about an hour); requires Node 22.19 or later.

## Known bottlenecks

All of these were measured on v0.8.5 (the 326 failures in the last row before backoff and retry existed). v0.16.0 rebuilt storage and runs and nothing has been re-measured since; the Status column speaks of the time of measurement.

| Symptom | Numbers | Status |
|---|---|---|
| The database has one connection, so reads and writes queue | 43.0 ms of connection wait per turn at 4,096 | A cost of the design; not the cause of the slowdown. v0.17.2 still opens one connection (`pkg/sqlitedb`) |
| Turns slow down with more active sessions, cause unknown | 3.9 s slower than alone at 4,096; in-flight peak 3,774 (below 4,096) | **Open**; the README states the bottleneck has not been found |
| CPU per turn grows with history | 12.1 ms to 34.8 ms (8 to 138 turns) | **Open**; mainly encoding the request with its full history and re-reading history every turn |
| Resident memory grows with history | 99 MB to 396 MB | **Open**; the other side of the same effect |
| 68 reads, 15 writes and about 11.6 KB per turn | Three model calls and two tool calls | A cost of the design (write before run); unknown after the log rebuild |
| A failed model request failed the whole turn | 326 failed turns under the same load before retries | Mitigated: 0 failures with retries |

[Design decision](/reference/decisions) 2 lists write amplification and cost growing with history as the price of this approach, and decision 10 records that nothing was re-measured after the shard changes.

## Code

| Repository | Path | Purpose |
|---|---|---|
| ollupi | `bench/README.md` | Method, results, limits, and for each experiment where its raw output is and whether it was measured |
| ollupi | `bench/run.sh` | Runs the experiments under the measurement rules and heads each output |
| ollupi | `bench/main.go` | Entry point, simulated model, the engine assembled through `host.New`, `parked` |
| ollupi | `bench/steady.go` | Capacity test; starts the simulated provider as a child process; `-command` goes through `run_command` |
| ollupi | `bench/burst.go` | Simulated provider (quota and 429), the fake tool, burst timeline |
| ollupi | `bench/mix.go` | Mixed-load wait statistics, Jain fairness index |
| ollupi | `bench/fanout.go` | Subagent fan-out, parents giving up slots |
| ollupi | `bench/crash.go` | Recovery after `kill -9`, takeover with a lease |
| ollupi | `bench/resume.go` | Wake and restart timing |
| ollupi | `bench/soak.go` | Soak sampling: latency, memory, goroutines, GC, database and WAL |
| ollupi | `bench/isolated.go` | One process per session baseline |
| ollupi | `bench/users.go` | Many users and one heavy user on one shard |
| ollupi | `bench/conns.go` | The cost of idle connections (straight or through a router) and the reconnection storm |
| ollupi | `bench/dbstats.go` | Reads and writes per turn, their timing, connection waits |
| ollupi | `bench/bench_test.go` | A smoke test for every experiment |
| ollupi | `bench/results/`, `bench/compare/` | Raw output kept, comparison with other harnesses |
| ollupi | `docs/images/bench-*.svg`, `cli-vs-ollupi.svg` | Figures on this page, synced to `/images/` at build time |
