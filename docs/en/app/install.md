# Install and get started

Ollupi for macOS is an AI agent app. You talk to it in your own project folder; it reads and writes files, runs commands and looks things up online, and asks you before doing anything risky. This page takes you from the download to your first finished task.

1. Download `Ollupi-<version>-arm64.dmg` from [Releases](https://github.com/0xfakeSpike/ollupi-desktop/releases/latest) (macOS 12 or later, Apple silicon) and drag Ollupi into Applications. Open it from Applications: automatic updates replace the running copy and fail if it is anywhere else.
2. The app is not notarized yet, so macOS blocks the first launch. Open **System Settings → Privacy & Security** and click **Open Anyway**, or run `xattr -dr com.apple.quarantine /Applications/Ollupi.app`.
3. Ollupi brings no model of its own. Under **Settings → Models**, click **Add provider**, choose DeepSeek, Qwen, Kimi, Zhipu GLM, OpenAI, Anthropic or Gemini, or **Other…** to enter an API yourself, and paste your API key.
4. Add a workspace (a project folder), start a session and describe the task.

The approval policy has three levels. If unsure, keep Balanced: everyday coding and tests run without interruption, and the agent asks before touching anything outside the project.

| The agent wants to | Strict | Balanced (default) | Relaxed |
|---|---|---|---|
| Read and search files | Runs | Runs | Runs |
| Edit project files, run commands inside the sandbox | Asks | Runs | Runs |
| Fetch web pages, click or type in the browser, use external tools that change things | Asks | Asks | Runs |
| Run a command with full access | Asks | Asks | Runs |

::: info Full page in Chinese
This page is being translated. The complete version, with every detail and code reference, is [in Chinese](/zh/app/install).
:::

The full page covers:

- Download and install, and the first launch
- Updates
- Adding a model provider
- Your first session
- Where to go next
