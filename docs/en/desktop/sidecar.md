# Sidecar backend

`ollupid` is the Go backend that hosts the engine for the desktop app. Besides running as a service it has one-off modes that the main process uses to validate configuration and skills, so the validation rules exist once, in the backend.

::: info Full page in Chinese
This page is being translated. The complete version, with every detail and code reference, is [in Chinese](/zh/desktop/sidecar).
:::

The full page covers:

- Command-line flags
- Handshake
- Start-up order
- Assembling the engine
- Start-up checks
- Loading and validating configuration
- Host abilities
- Built-in skills
