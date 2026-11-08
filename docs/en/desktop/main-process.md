# Main process

The Electron main process manages three things: the backend process, the window, and the native operations the sandboxed renderer cannot do. The renderer has no general shell; it can call only the methods `DesktopApi` lists.

::: info Full page in Chinese
This page is being translated. The complete version, with every detail and code reference, is [in Chinese](/zh/desktop/main-process).
:::

The full page covers:

- Lifecycle
- Hosting the backend
- Window and Dock
- The IPC surface
- Notifications and badges
- Model lists
- Balance queries
- Temporary attachments
- Updates
