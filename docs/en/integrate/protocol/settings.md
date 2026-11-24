# Settings

A user's own settings: whether to redact before anything is sent to the model, whether memory is on, whether to learn new memories from new turns, and the user's own permission layer. A client reads them with `settings/read`, changes the three switches with `settings/update` and the permissions with `settings/updatePermissions`, and follows them with `settings/changed`. What redaction detects and how it replaces and restores values is on [redaction](/engine/redaction); how memories are distilled and loaded is on [memory](/integrate/protocol/memory).

::: info Full page in Chinese
This page is being translated. The complete version, with every method, notification, type and real message, is [in Chinese](/zh/integrate/protocol/settings).
:::

The full page covers:

- Concepts and state
- Typical flow
- Methods: `settings/read`, `settings/update`, `settings/updatePermissions`
- Notification: `settings/changed`
- Type: `SettingsRow`
- Errors and limits
- Code locations
