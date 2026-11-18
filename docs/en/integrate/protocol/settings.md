# Settings

A user's settings: the `redaction`, `memory` and `learn` switches, read with `settings/read` and changed with `settings/update`, and the user's own permission layer, replaced with `settings/updatePermissions`. Every change is announced with `settings/changed`.

::: info Full page in Chinese
This page is being translated. The complete version, with every method, notification, type and real message, is [in Chinese](/zh/integrate/protocol/settings).
:::

The full page covers:

- Concepts and state: what each switch stops, defaults, when a change applies
- Typical flow
- Methods: `settings/read`, `settings/update`, `settings/updatePermissions`
- Notification: `settings/changed`
- Type: `SettingsRow`
- Errors and limits
- Code locations
