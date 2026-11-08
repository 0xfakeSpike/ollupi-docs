# Desktop architecture

The Ollupi desktop app wraps the engine as a macOS application. The engine is a Go library; the app gives it a process, an interface and abilities only a local machine has (a built-in browser, a terminal, Finder, system notifications). It is three processes and four front-end packages: a Go sidecar runs the engine, the Electron main process hosts the sidecar and provides native abilities, and the renderer connects to the sidecar's gateway directly to draw the interface.

::: info Full page in Chinese
This page is being translated. The complete version, with every detail and code reference, is [in Chinese](/zh/desktop/architecture).
:::

The full page covers:

- Three processes
- Four channels
- Four packages
- From engine events to the screen
- Which layer owns what
- Single user
