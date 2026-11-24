# Sessions

A session (thread) is one continuous conversation. A client creates, lists, reads, renames, marks read, archives and deletes it with `thread/*`, and follows its changes with `thread/changed`. Turns and items are on [turns and items](/integrate/protocol/turns); connecting, authentication, the handshake and error codes on the [gateway protocol](/integrate/protocol); how to use `seq` to line up a page you read with the notifications that follow it on [writing a client](/integrate/client).

::: info Full page in Chinese
This page is being translated. The complete version, with every method, notification, type and real message, is [in Chinese](/zh/integrate/protocol/threads).
:::

The full page covers:

- Concepts and state, including session status
- Methods: `thread/start`, `thread/read` and `thread/resume`, `thread/list`, `thread/rename`, `thread/markRead`, `thread/updatePermissions`, `thread/archive`, `thread/delete`
- Notification: `thread/changed`
- Type: `ThreadRow`
- Errors and limits
- Code locations
