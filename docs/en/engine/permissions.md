# Permissions and approvals

Every tool call the agent makes is decided as it is written to the conversation log: it runs, the user is asked, or it is refused. The decision is made in the `policy` package, a pure function of the approval policy, the rules and the content of the call. An approval is the wait when the user is asked: the question and the user's decision are entries in the log, and while a turn waits it holds no slot. An approval holds for the call as it was asked; it is not decided again before the call runs.

The three policies, by what the agent may do on its own:

| The agent wants to | Strict (`untrusted`) | Balanced (`on-request`, default) | Relaxed (`never`) |
|---|---|---|---|
| Read and search files | Runs | Runs | Runs |
| Edit project files, run commands inside the sandbox | Asks | Runs | Runs |
| Fetch web pages, change scheduled jobs, use MCP tools | Asks | Asks | Runs |
| Run a command outside the sandbox | Asks | Asks | Runs |

Rules (allow, ask, deny) are checked before the policy at every level. Settings stack in layers, deployment, user, workspace and conversation, and a lower layer can add rules but not lift a deny above it. Under Relaxed, a command too complex for the rules to read is refused when a deny rule might apply to it, rather than let through.

::: info Full page in Chinese
This page is being translated. The complete version, with every detail and code reference, is [in Chinese](/zh/engine/permissions).
:::

The full page covers:

- How each call is decided
- Decision order
- Approval policies
- Rule syntax
- Permission layers
- Command parsing
- The approval flow
- Writing "always allow"
- Structured questions
