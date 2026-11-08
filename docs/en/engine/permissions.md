# Permissions and approvals

Before the agent calls a tool, `agent/permission` decides whether the call runs, asks the user, or is refused. The decision rests on three things: the approval policy, the rules, and the content of the call. While a turn waits for an approval it gives up its slot and remains only in the database.

The three policies, by what the agent may do on its own:

| The agent wants to | Strict (`untrusted`) | Balanced (`on-request`, default) | Relaxed (`never`) |
|---|---|---|---|
| Read and search files | Runs | Runs | Runs |
| Edit project files, run commands inside the sandbox | Asks | Runs | Runs |
| Fetch web pages, use external tools that change things | Asks | Asks | Runs |
| Run a command outside the sandbox | Asks | Asks | Runs |

Rules (allow, ask, deny) are checked before the policy at every level. Under Relaxed, a command too complex for the rules to read is refused when a deny rule might apply to it, rather than let through.

::: info Full page in Chinese
This page is being translated. The complete version, with every detail and code reference, is [in Chinese](/zh/engine/permissions).
:::

The full page covers:

- Decision order
- Approval policies
- Rule syntax
- Three layers
- Command parsing
- The approval flow
- Writing "always allow"
- Structured questions
