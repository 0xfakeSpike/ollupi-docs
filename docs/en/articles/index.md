# Articles

The manual says what Ollupi does. The articles say why: the problems behind the design, how it compares with other ways of running agents, and what the measurements showed, including where they went wrong.

Each article stands on its own and links to the manual for details.

## Published

- **[Head in the Cloud, Hands at Home](/articles/head-in-the-cloud)** · November 8, 2026. Why an agent's access layer, runtime and execution environment end up in different places: nine topologies, seven forces, the engineering problems at each boundary, and which topology fits which job. Includes a section on mainland China, where the same software often ships in a different shape.

## Planned

- **Personal agents mostly wait.** The cost of one container per agent, worked out with numbers.
- **Agent runtimes and durable execution.** What an agent runtime shares with durable execution engines such as Temporal, Restate and DBOS, and where it has to differ: non-deterministic model calls, tool calls that may already have taken effect, approvals that must bind to what actually runs.
- **Killing the process ninety times.** Crash semantics for agents: why `pending` and `inProgress` are different states, and why an interrupted tool call is marked rather than retried.
- **What an approval approves.** Permissions, sandbox and redaction as one trust boundary.
- **The missing 3.9 seconds.** Finding the slowdown past 3,000 active sessions.
