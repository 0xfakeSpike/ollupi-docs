# Renderer

The renderer is the React 19 interface, running in a sandbox. It mirrors the engine's state locally and draws the mirror. Server state comes from the gateway into per-domain Zustand stores; pure logic lives in `@ollupi/core`, and components only read stores.

::: info Full page in Chinese
This page is being translated. The complete version, with every detail and code reference, is [in Chinese](/zh/desktop/renderer).
:::

The full page covers:

- Screens and routing
- State management
- Protocol types
- The timeline
- Scrolling
- Markdown
- Search
- Languages
- Local storage
