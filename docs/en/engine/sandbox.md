# Sandbox

The sandbox decides what the model's commands and file operations can reach. Every tool runs commands and reads and writes files through the `sandbox.Box` interface, never the operating system directly. The default implementation is macOS Seatbelt (the kernel sandbox, run through `sandbox-exec` with a profile); a cloud sandbox can take its place.

::: info Full page in Chinese
This page is being translated. The complete version, with every detail and code reference, is [in Chinese](/zh/engine/sandbox).
:::

The full page covers:

- The Box interface
- Three modes
- Path rules
- Seatbelt profile
- Network
- Process cleanup
- Reporting denials
- Escalation
- Cloud sandbox entry point
