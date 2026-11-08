# Roadmap

Ollupi is built in public, one step at a time. This page says what is done, what comes next and how each step will be judged finished. Every item has a check that can be run or read; when an item is done, its result moves into the manual or the benchmarks and the item leaves this page.

Last updated 2026-11-08, against engine v0.11.3 and desktop 0.7.24.

## Where things stand

| Area | State |
|---|---|
| Engine core | Turn queue, slot scheduling, write-before-run persistence, crash recovery, subagents and scheduled tasks as ordinary sessions. Stable since 2026-11-05: later commits only change edges. |
| Multi-user | One SQLite file is one shard, rows carry the user, a lease lets a standby process take over a shard, per-user slots and connections. Implemented; not yet measured. |
| Sandbox | macOS Seatbelt locally; a `sandbox.Machine` interface for cloud sandboxes, with no concrete provider yet. |
| Benchmarks | Nine experiments and a comparison with two other harnesses, on one machine and one shard, measured before the multi-user changes. See [Benchmarks](/benchmarks/). |
| Desktop app | macOS app on Apple silicon, 28 releases since 2026-10-28. Used daily by the author. |

## Next

### 1. Benchmarks, second round

The current numbers predate the multi-user, shard and sandbox changes, and the claims that matter most to a cloud provider have no numbers at all. This round re-measures and fills those gaps. The experiments and their status are on [What we measure next](/benchmarks/plan).

Done when: every number on the landing page and the benchmarks page comes from v0.11 or later, and lease takeover, noisy neighbours and multi-shard scaling each have a published result, whatever it shows.

### 2. Self-improvement from execution traces (RSI)

The engine writes every step of a run to the database before it happens: model output, reasoning, tool calls, approvals, plans, questions and answers, token use. Today that record feeds replay and long-term memory. The next step is to use it to measure the agent and then improve it, recursively.

The plan has three stages, each usable on its own:

1. **Traces as data.** Export runs in a stable, documented format, with redaction applied, so they can be read outside the engine.
2. **Evaluation.** Replay or re-run recorded tasks against a changed prompt, skill set, memory or model, and score the outcome. A change that scores worse does not ship.
3. **Improvement loop.** Let an agent propose changes to its own prompt, skills and memory from its traces, and accept them only through stage 2.

Done when, for each stage: (1) a trace export that round-trips; (2) an eval run that tells two prompt versions apart on recorded desktop tasks; (3) at least one accepted self-proposed change with its before-and-after scores published.

### 3. Reliability evidence from real use

The desktop app runs the same engine every day, which is evidence a benchmark cannot give. It will keep a local, content-free summary from its own database and logs: turns run, failures, interruptions and recoveries, queue waits, retries. A periodic report will be published from the author's own use.

Done when: the app can export the summary, and the first monthly report is on this site.

### 4. Observability

A framework meant for cloud providers needs metrics, not only logs. The engine will expose queue depth, slot use, per-user waits, lease state and model-call retries through a hook a host can wire to its own metrics system.

Done when: the benchmark runs read their numbers from these hooks instead of from bench-only code.

### 5. A runnable multi-user deployment

Shards, leases and per-user sandboxes are interfaces today. A reference deployment will make them something a reader can run: a gateway, a router and two shards, with one concrete `sandbox.Machine` implementation (a container to start with).

Done when: one command starts it, and the multi-shard benchmark runs against it.

## Desktop app

The desktop app keeps its own backlog, synced from its repository: [desktop backlog](/zh/reference/backlog) (Chinese). In short: editing, forking and rolling back messages (next), then Apple notarization, Linux and Windows, and remote access.

## Writing

Articles explain why the system is built the way it is, and how it compares with other approaches. They are listed under [Articles](/articles/). The manual is being translated into English page by page; until a page is done, it links to the Chinese version.
