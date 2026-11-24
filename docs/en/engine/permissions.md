# Approvals and permissions

Every tool call the agent makes is decided as it is written to the conversation log: it runs, the user is asked, or it is refused. The decision is made in the `policy` package, a pure function that reads no database and calls no tool, based on the approval policy, the rules and the content of the call. An approval is the wait when the decision is to ask the user; while it waits, the turn holds no slot. For where permissions sit in the overall security design, see [Security overview](/engine/security).

::: info Full page in Chinese
This page is being translated. The complete version, with every detail and code reference, is [in Chinese](/zh/engine/permissions).
:::

The full page covers:

- Why it is designed this way
- Decision order
- Full access
- Approval policies
- Rule syntax
- Permission layers
- Suggested rules and "always allow"
- The approval flow
- Limits and known issues
