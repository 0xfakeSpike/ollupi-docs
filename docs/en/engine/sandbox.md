# Sandbox

The sandbox decides what the model's commands and file operations can reach. Tools run commands and read and write files through the `sandbox.Box` interface, never the operating system directly. `pkg/sandbox` has two implementations: the local `Sandbox`, on macOS Seatbelt (the kernel sandbox, run through `sandbox-exec` with a profile), and `Remote`, which wraps a cloud sandbox's `Machine`. With a domain allowlist, a command reaches the network only through a proxy of its own, which serves HTTP CONNECT, plain HTTP and SOCKS5 on one port.

::: info Full page in Chinese
This page is being translated. The complete version, with every detail and code reference, is [in Chinese](/zh/engine/sandbox).
:::

The full page covers:

- The Box interface
- Three modes
- Path rules
- Environment variables
- Seatbelt profile
- Network
- Process cleanup
- Reporting denials
- Escalation
- Cloud sandbox entry point
