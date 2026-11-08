# Desktop app quickstart

Ollupi for macOS is an AI agent app. You talk to it in your own project folder; it reads and writes files, runs commands and looks things up online, and asks you before doing anything risky.

1. Download `Ollupi-<version>-arm64.dmg` from [Releases](https://github.com/0xfakeSpike/ollupi-desktop/releases/latest) (macOS 12 or later, Apple silicon) and drag Ollupi into Applications.
2. The app is not notarized yet, so macOS blocks the first launch. Open **System Settings → Privacy & Security** and click **Open Anyway**, or run `xattr -dr com.apple.quarantine /Applications/Ollupi.app`.
3. Add a model provider under **Settings → Models**: OpenAI-compatible, Anthropic or Gemini, with your own API key.
4. Add a workspace (a project folder), start a session and describe the task.

The approval policy has three levels. If unsure, keep Balanced: everyday coding and tests run without interruption, and the agent asks before touching anything outside the project.

| The agent wants to | Strict | Balanced (default) | Relaxed |
|---|---|---|---|
| Read and search files | Runs | Runs | Runs |
| Edit project files, run commands inside the sandbox | Asks | Runs | Runs |
| Fetch web pages, click or type in the browser, use external tools that change things | Asks | Asks | Runs |
| Run a command outside the sandbox | Asks | Asks | Runs |

::: info Full page in Chinese
This page is being translated. The complete version, with every detail and code reference, is [in Chinese](/zh/app/install).
:::

The full page covers:

- Download and install
- Add a model provider
- Your first session
- Approvals
- Working with workspaces
- Keyboard shortcuts
- Where your data is
