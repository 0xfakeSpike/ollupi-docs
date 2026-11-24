# Sandbox

The sandbox decides what the model's commands and file operations can reach. Tools run commands and read and write files through `sandbox.Box`. In `pkg/sandbox`, the local `Sandbox` uses macOS Seatbelt (it runs a process under `sandbox-exec` with a set of rules), and `Remote` wraps a cloud sandbox's `Machine` as a `Box`. Permissions decide whether to ask the user; the sandbox decides what a call can do once it is allowed. See [Approvals and permissions](/engine/permissions).

::: info Full page in Chinese
This page is being translated. The complete version, with every detail and code reference, is [in Chinese](/zh/engine/sandbox).
:::

The full page covers:

- Why it is designed this way
- The Box interface
- Three modes
- Path rules
- Environment variables
- Network
- Process cleanup
- Reporting denials
- Full access
- Cloud sandbox entry point
- Limits and known issues
