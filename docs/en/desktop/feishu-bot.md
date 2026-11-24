# Feishu bot

The Feishu (Lark) bot lets a user work with sessions away from the computer: send messages, follow progress, and handle approvals and questions from a phone. It runs inside the sidecar as another client of the engine: it calls the engine directly and subscribes to the store's event stream, so it receives the same changes the gateway does.

This page covers the implementation. The setup steps on the Feishu Open Platform are on [Feishu bot](/zh/app/feishu) (Chinese).

::: info Full page in Chinese
This page is being translated. The complete version, with every detail and code reference, is [in Chinese](/zh/desktop/feishu-bot).
:::

The full page covers:

- Long connection
- Concurrency model
- Allow lists
- Messages
- Mapping topics to sessions
- One card per turn
- Approval and question cards
- Syncing with the desktop
- Privacy
