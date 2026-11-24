# Approvals and questions

When the agent wants to do something that needs the user's go-ahead, or needs the user to answer a question, the gateway sends the client a JSON-RPC request and the client replies with a result. This page covers these two server requests: when they are sent, how to reply, and what each kind of reply leads to.

Which calls need asking is decided by the policy and the rules, see [permissions](/integrate/protocol/permissions); the fields of an item (`ItemRow`) are on [turns and items](/integrate/protocol/turns); how a client keeps the requests waiting for an answer is on [writing a client](/integrate/client).

::: info Full page in Chinese
This page is being translated. The complete version, with every method, notification, type and real message, is [in Chinese](/zh/integrate/protocol/approvals).
:::

The full page covers:

- Why it is designed this way
- Concepts and state
- Typical flows: approving a call, answering a question, skipping and declining, answering with a message instead
- Requests: `item/toolCall/requestApproval`, `item/tool/requestUserInput`
- What each reply leads to
- Sending requests again
- Types: `ApprovalRequestParams`, `ApprovalResponse`, `Approval`, `Input`, `PreparedExecution`, `FileChange`, `UserInputRequestParams`, `UserInputQuestion`, `UserInputResponse`
- Errors and limits
- Code locations
