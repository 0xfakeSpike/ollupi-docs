# Sidecar backend

`ollupid` is the desktop app's backend. It is a Go executable that assembles the ollupi engine and serves the gateway on a loopback port. The engine is a library with no entry point, and it does not read configuration files; the sidecar takes care of that. The Electron main process starts it, reads one line of handshake and hands the address to the interface. The sidecar's `go.mod` pins the engine version, currently `v0.26.2`.

Besides running as a service, `ollupid` has a few one-off modes that the main process uses to validate configuration and skills. There is one set of validation rules, the backend's own; the interface does not write them a second time.

::: info Full page in Chinese
This page is being translated. The complete version, with every detail and code reference, is [in Chinese](/zh/desktop/sidecar).
:::

The full page covers:

- Command-line flags
- Handshake
- Start-up order
- Assembling the engine
- Start-up checks
- Skills
- Loading and validating configuration
- Host abilities
