---
pageClass: roadmap
---

# Roadmap

Ollupi is built in public, one step at a time. This page says what is done, what comes next and how each step will be judged finished. Every item has a check that can be run or read; when an item is done, its result goes into the manual or the benchmarks and the item leaves this page.

Last updated 2026-11-24, against engine v0.27.0 and desktop 0.8.16.

## Where things stand

| Area | State |
|---|---|
| Engine core | Turn queue, slot scheduling, write-before-run persistence, crash recovery; subagents and scheduled tasks are ordinary sessions. State is folded from an append-only session log, and changes reach the scheduler, the gateway and memory extraction through the feed; see [design decision 26](/reference/decisions). v0.18.0 (2026-11-19) moves long-running tool calls to the background, where they queue in their own tool pool and their results return to the turn as reports; v0.20.0 adds the optional [hub](/engine/hub), which lets the user plan all their projects in one place and hand work to each project's sessions; v0.23.0 to v0.25.0 extend subagents to eight roles. |
| Multi-user | One SQLite file is one shard, rows carry the user, a lease lets a standby process take over a shard, and each user has their own slot limit; the engine itself does not know about shards, and the `shard` package runs a process as a shard. Since v0.26.6 each user also has their own models and connections, and the gateway accepts only users already in the database. Measured on v0.18.0: after `kill -9`, a standby process takes over in 1.3 s; with a per-user slot limit set, one heavy user does not hold up the others; on one machine, 4 shards complete 1.7 times as many turns per second as 1. Not yet measured across several machines. |
| Sandbox | macOS Seatbelt locally; cloud sandboxes plug in through the `sandbox.Machine` interface, which has no implementation in the repository yet. A command can ask for full access; web reads, like MCP, send their requests through the user's sandbox. The sandbox limits which files and network a command can reach, not how much memory and CPU it uses. |
| Benchmarks | Measured on v0.18.0 (2026-11-19): they answer 11 questions and compare Ollupi with pi, pi-durable and DeepSeek Harness under the same load; every number has its raw output in the engine repository's `bench/results/`. All on one 8 GB M1, each experiment run once. Above 1,536 sessions a turn starts to slow down, and almost all the extra time is spent waiting for the single SQLite connection. See [Benchmarks](/benchmarks/). |
| Evaluation | The engine repository's `eval/` runs the engine with real models on Terminal-Bench 2.0 tasks (through Harbor, in Docker) and compares two versions, to find what to change and to judge whether a change helped. The tasks are split into a 10-task smoke subset and a held-out subset kept for checking; so far only the smoke subset has been run, most recently on 2026-11-09, before the rebuild around the session log; no scores are published. |
| Desktop app | macOS app on Apple silicon, 82 stable releases since 2026-10-28, used daily by the author; 0.8.16 runs on engine v0.26.2. The beta 0.8.17-beta.3 runs on engine v0.26.6; one computer can have several identities, each with its own models, memory and sessions. |

## Next

### 1. Benchmarks, next round

The current numbers were measured on v0.18.0 and leave five questions unanswered. Capacity and long runs both slow down waiting for the single SQLite connection: how far can a different approach push the knee back? The capacity experiment gives each session only 3 turns of history: what happens when history grows to hundreds or thousands of turns? Shards have been measured on one machine only. How far is the simulated model from real providers? Each experiment ran only once: how much do the numbers vary? The experiments and their progress are on [What we measure next](/benchmarks/plan).

Done when: each of the five experiments on that page has a published result measured by `bench/run.sh`, whatever it shows.

### 2. Self-improvement from execution traces (RSI)

The engine appends every step to the session's log before it runs: model output, reasoning, tool calls, approvals, questions and answers, subagent reports, token use. Today that log is used to carry on after a crash, for the timeline in the interface, for extracting long-term memory and for usage statistics. The next step is to use it to evaluate the agent and then, in turn, to improve the agent, forming a recursive improvement loop.

The plan has three stages, each usable on its own:

1. **Traces as data.** Export runs in a stable, documented format, redacted before export, so programs outside the engine can read them.
2. **Evaluation.** Replay or re-run recorded tasks with a changed prompt, skill set, memory or model, and score the outcome. A change that scores worse does not ship. `eval/` can already compare two versions on Terminal-Bench tasks, but those are public tasks; it cannot yet re-run tasks recorded from real use.
3. **Improvement loop.** Let the agent propose changes to its own prompt, skills and memory from its own traces, and accept only those that pass stage 2.

Done when, for each stage: (1) exported traces can be imported back unchanged; (2) one evaluation run tells two prompt versions apart on real tasks recorded in the desktop app; (3) at least one change proposed by the agent itself is accepted, with its before-and-after scores published.

### 3. Reliability evidence from real use

The desktop app runs the same engine every day, which is evidence a benchmark cannot give. From its own database, on the local machine, it will build a summary that contains no conversation content: turns run, failures, interruptions and recoveries, queue waits, retries. Reports from the author's own use will then be published at regular intervals.

Done when: the app can export this summary, and the first monthly report is published on this site.

### 4. Observability

A framework meant for cloud providers needs metrics, not only logs. The engine will expose queue length, slot use, per-user waits, lease state and model-call retries through a hook that a host can wire to its own metrics system.

Done when: the benchmark experiments read their numbers from these hooks instead of relying on bench-only code.

### 5. A multi-user deployment you can run

The code for shards, leases and routing exists, but there is no deployment a reader can follow and run, and cloud sandboxes are still only the `sandbox.Machine` interface. A reference deployment will let readers run it themselves: a gateway, a router and two shards, plus one concrete `sandbox.Machine` implementation (a container to start with).

Done when: one command starts it, and the multi-shard benchmark runs on it.

### 6. Memory and CPU limits for commands

Slots limit how many sessions run at once, the tool pool's cap limits how many background tool calls run at once, and the model connection quota limits how many model requests are in flight at once; none of them governs the commands themselves. A session holding a slot can run a command that uses up the memory or CPU and crowds out other sessions on the same machine. So today the claim can only be "no more sessions run at once than the limit", not "the resources agents use stay within the limit", and the second is the point of putting agents in a pool; see [Why Ollupi](/intro/why).

The plan is to let the host set memory and CPU limits on commands: one for each command, plus one for the total of all of a user's commands. A command that goes over is ended, and the result goes to the model as a failure. The limits are enforced by the `sandbox.Box` implementation: cloud sandboxes run in containers and can use the containers' own limits; the mechanism for macOS on the local machine still needs research.

Done when: a benchmark experiment has sessions run commands that exceed the limits, the commands are ended, the model receives a failure result, and the turn times of other sessions on the same shard are unaffected, with the result published.

## Desktop app

The desktop app keeps its own backlog: [desktop backlog](/zh/reference/backlog) (Chinese). In short: editing the latest message is done; forking and rolling back come next, then Apple notarization, Linux and Windows, and remote access.

## Writing

Articles are about problems of agents themselves, such as how they are deployed and who uses them. They are listed under [Articles](/articles/). The manual is written in Chinese first and then translated into English page by page: an English page not yet translated links to the Chinese version, and an English page that lags behind the Chinese one says so at the top.
