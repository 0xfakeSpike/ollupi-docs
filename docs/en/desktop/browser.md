# Built-in browser

The built-in browser is a Chromium tab inside the app, to the right of the conversation, shared by the agent and the user. The agent can open pages, read them, click, paste and upload files; the user sees what it is doing and can take over at any time, for example to sign in to a site the agent cannot get into.

The browser belongs to the desktop app, not the engine. The sidecar only supplies the tools' names and descriptions and forwards calls to the main process. The main process owns every `WebContentsView`; the agent's actions are carried out by Playwright in the main process, which reads the page and acts on it, reaching the tab through an in-process CDP proxy without opening a debugging port. The agent sees the same page the user sees, and the engine never touches the window.

::: info Full page in Chinese
This page is being translated. The complete version, with every detail and code reference, is [in Chinese](/zh/desktop/browser).
:::

The full page covers:

- Tab ownership
- Placing the view
- The path of a tool call
- Tools
- Snapshot format
- How Playwright reaches the tabs
- The address bar
- Device permissions
- Sign-in partitions
- History and bookmarks
- Limits and known issues
