# 安装与上手

Ollupi 是 macOS 上的 AI agent 应用。你在自己的项目文件夹里和它对话，它能读写文件、跑命令、上网查资料，做有风险的事之前会先问你。这一页带你从下载到跑通第一个任务。

## 下载安装

需要 macOS 12 或更新，只支持 Apple 芯片（M 系列）。

1. 打开 [Releases](https://github.com/0xfakeSpike/ollupi-desktop/releases/latest)，下载 `Ollupi-<版本>-arm64.dmg`。
2. 打开 dmg，把 Ollupi 拖进"应用程序"。

### 第一次打开

应用还没有经过 Apple 公证，第一次打开时 macOS 会提示无法验证开发者。点"完成"，然后选一种方式放行：

- 打开 **系统设置 → 隐私与安全性**，拉到底部，点"仍要打开"。
- 或者在终端里执行：

  ```bash
  xattr -dr com.apple.quarantine /Applications/Ollupi.app
  ```

只需要做一次。之后有新版本时，侧边栏底部会提示，点 **下载并安装**，下载完点 **立即重启**。不重启的话，退出 Ollupi 时也会装上。

## 添加模型提供方

Ollupi 不自带模型，要接你自己的 API。

1. 打开 **设置 → 模型**，点 **添加提供方**。
2. 选 API 类型：OpenAI 兼容（OpenAI、DeepSeek、本地服务等）、Anthropic 或 Gemini。
3. 填名称、Base URL 和 API 密钥。Base URL 留空就用这个 API 的默认地址。OpenAI 兼容的地址要带版本，比如 `.../v1`。
4. 模型列表会自动拉取。勾选要用的模型。上下文和输出上限能自动填的都会填好，填不上的留空就用默认值。本地小模型请按实际窗口填写。
5. 点 **保存并重启**。

新安装的应用里已经有一个没填密钥的 `openai` 提供方。如果你要用 OpenAI，直接编辑它，填上密钥就行。如果用别的提供方，在模型旁边点星标把它设为默认，再删掉 `openai`。

## 第一个会话

1. 点侧边栏底部附近的 **添加工作区**，选一个项目文件夹。工作区就是一个项目文件夹，agent 的命令在里面运行。
2. 点 **新会话**，在输入框的工具栏选工作区和模型。
3. 描述任务，按 Enter 发送。可以粘贴或拖入图片和文件。

不选工作区也能聊天，这时命令在 `~/.ollupi/scratch` 里运行。

agent 工作时你可以继续输入，或者停止它，见[工作区与会话](/zh/app/sessions)。

## 接下来

- [工作区与会话](/zh/app/sessions)：插话、排队、附件、搜索、导出。
- [审批与权限](/zh/app/permissions)：三档审批策略怎么选，审批卡片怎么看。
- [面板：浏览器、文件、改动、终端](/zh/app/panels)：和对话并排的工具。
- [定时任务与记忆](/zh/app/automation)：让 agent 按时做事、记住你的习惯。
- [飞书机器人](/zh/app/feishu)：离开电脑时在手机上处理。
- [配置与数据](/zh/app/config)：手写配置、数据存在哪。

## 代码位置

| 位置 | 职责 |
|---|---|
| ollupi-desktop `README.md` | 安装和使用说明 |
| ollupi-desktop `apps/desktop/src/renderer/src/views/settings/ModelsSection.tsx` | 模型设置 |
| ollupi-desktop `apps/desktop/src/renderer/src/views/draft/DraftScreen.tsx` | 新会话页 |
| ollupi-desktop `apps/desktop/src/renderer/src/views/requests/ApprovalCard.tsx` | 审批卡片 |
