# 侧边面板

侧边面板是会话右侧的一列，放和对话并排看的东西：浏览器、工作区文件、git 改动、用户的终端、agent 的计划、上下文用量、会话权限。它们不盖在对话上，和对话用一条分隔线并排，占窗口右侧的整列高度，标题栏和对话的标题栏对齐，也能拖动窗口。

## 停靠和宽度

同一时间只有一个面板。`navigation` store 里的 `panel` 字段决定显示哪个，`togglePanel` 打开或关闭。这个值不跟会话走，切换会话时面板保持打开，"像一块窗格"。

`SidePanel` 是所有面板共用的框架。

| 面板 | 组件 | 默认宽度 | 需要 |
|---|---|---|---|
| `browser` | `BrowserPanel` | `half`，50% | 总是可用，草稿页也有 |
| `files` | `FilesPanel` | `wide`，448px | 工作区 |
| `changes` | `ChangesPanel` | `wide`，448px | 工作区 |
| `terminal` | `TerminalPanel` | `half`，50% | 工作区 |
| `tasks` | `TasksPanel` | `normal`，320px | 会话 |
| `context` | `ContextPanel` | `normal`，320px | 会话 |
| `permissions` | `PermissionsPanel` | `normal`，320px | 会话，子 agent 会话没有 |

草稿页可以打开浏览器，选了工作区后还能打开文件、改动、终端，因为这些面板要的是文件夹而不是会话。工作区的面板不属于某个会话，组件用工作区 ID 做 key，同一工作区的会话和草稿共用展开状态和 shell。

### 调整宽度

面板左边缘是一个 `role="separator"` 的手柄。

| 常量 | 值 | 含义 |
|---|---|---|
| `MIN_WIDTH` | 260 | 面板最窄 |
| `CONVERSATION_ROOM` | 360 | 至少给对话留这么多 |
| `STEP` | 24 | 方向键一次移动的距离 |

`fit` 把宽度夹在 `MIN_WIDTH` 和父容器宽度减 `CONVERSATION_ROOM` 之间，CSS 的 `max-w-[calc(100%-22.5rem)]` 在窗口变窄时也守住这条线。

- **拖动**：用指针捕获。拖动时 `usePanelWidths.resizing` 为真。
- **方向键**：左键加宽，右键变窄。
- **双击**：删除记住的宽度，回到面板自己的默认值。
- **持久化**：每个面板的宽度分别存在 `localStorage` 的 `ollupi.panelWidths`，读取时丢掉小于 `MIN_WIDTH` 的值。

拖动有几个边界情况要处理：

- 鼠标在窗口拖动区松开时，窗口收不到 `pointerup`，所以每次 `pointermove` 都检查按键，发现已松开就结束拖动。
- 面板在拖动中被卸载（比如切换屏幕）时结束拖动，否则 `col-resize` 光标留在所有屏幕上。
- 浏览器页面和 PDF 阅读器会抢走指针。拖动时浏览器把页面视图隐藏，PDF 的 `iframe` 加 `pointer-events-none`。

主进程盖在面板上的内容从手柄右边开始（`CLEAR_OF_EDGE`，`ml-1.5`），不盖住手柄。

## 文件

只读浏览工作区。`main/files.ts` 负责读，路径由渲染进程相对根目录传入，`inside` 用 `realpath` 解析后确认仍在根目录内，所以符号链接也跳不出去。

**列表**：按 Finder 的方式排序，文件夹在前，用 `Intl.Collator` 的数字感知比较。隐藏 `.git` 和 `.DS_Store`。符号链接显示成它指向的东西，断开的链接不列出。文件夹在展开时才读。

**预览**：

| 类型 | 判断 | 上限 | 超过时 |
|---|---|---|---|
| PDF | 扩展名 `.pdf` | 50 MB | 只能用外部应用打开 |
| 图片 | 扩展名 `.png`、`.jpg`、`.jpeg`、`.gif`、`.webp`、`.svg` | 5 MB | 当作二进制 |
| 文本 | 前 8000 字节没有 NUL，和 git 的判断方式相同 | 256 KB | 只显示开头并提示 |
| 二进制 | 其余 | | 只显示大小 |

PDF 的字节经 IPC 传给渲染进程，转成 blob URL 放进 `iframe`，用 Chromium 自带的阅读器。这需要窗口的 `plugins: true` 和 CSP 的 `frame-src blob:`。

Markdown（`.md`、`.markdown`、`.mdx`）默认渲染显示。切换到源码后的选择保留到之后打开的文件。其他文本走 `CodeBlock`，语言取扩展名，或文件名本身（比如 `Dockerfile`）。

**路径导航**：打开的文件上方显示从工作区起的路径。路径里的文件夹单击弹出 `popover` 列出它的内容，可以展开子文件夹、跳到别的文件。双击回到文件树，展开并定位到这个文件夹。

打开的文件存在 `navigation.file`，所以时间线里的路径能让这个面板打开文件。刷新按钮让全部已展开的文件夹和当前文件重新读。

## 改动

显示工作区相对上次提交的所有改动。代码注释写明了依据：ollupi 只通过命令改文件，不记录自己的编辑，所以 git 仓库才是一轮工作的体现。

`WorkspaceChanges` 调用系统的 `git`。环境用登录 shell 的，加 `GIT_OPTIONAL_LOCKS=0`（agent 可能同时在同一仓库里跑 git），`-c core.quotePath=off` 保留中文路径。

**读取**：

```
git status --porcelain=v1 -z --no-renames --untracked-files=all -- .
git diff <base> --numstat -z --no-renames -- .
```

`<base>` 是 `HEAD`。还没有提交时用空树 `4b825dc642cb6eb9a060e54bf8d69288fbee4904`。重命名显示成一个删除加一个新增。范围限定在工作区目录，工作区可以是仓库的子目录，路径前缀由 `rev-parse --show-prefix` 去掉。

文件状态由 porcelain 的两列算出：

| 字段 | 取值 | 规则 |
|---|---|---|
| `kind` | `untracked` | `??` |
| | `added` | X 是 `A` 且工作区还有这个文件 |
| | `deleted` | 在 HEAD 里，工作区没有 |
| | `modified` | 其余 |
| `staged` | `none` | X 是空格或 `?` |
| | `all` | Y 是空格 |
| | `part` | 其余，暂存后工作区又改过 |

暂存之后又删掉的新文件两边都没有，不显示。

**什么时候重新读**：一轮开始和结束（`ChangesPanel` 的 `turn` 属性变化）、每次 git 操作之后、手动刷新。

**diff**：超过 512 KB 截断。未跟踪的文件用 `git diff --no-index /dev/null <path>`，这时路径不在 git 索引里，所以要先确认在工作区内。

**操作**：

| 操作 | 命令 |
|---|---|
| 暂存 | `git add -A -- <paths>`，包括删除 |
| 取消暂存 | `git restore --staged`。还没有提交时用 `git rm --cached -q -r` |
| 丢弃（修改、删除） | `git restore --source=HEAD --staged --worktree` |
| 丢弃（新文件） | 已暂存的先 `git rm --cached`，然后移到废纸篓 |
| 提交 | `git commit -q -m`，用户的 git 身份，hooks 照常运行 |

丢弃前弹确认。没有提交过的内容进废纸篓而不是删掉，还能找回。

所有路径用 `:(literal)` 传给 git，不当 pathspec 模式解析。`..` 开头和绝对路径直接拒绝。

## 终端

用户自己的 shell，和 agent 无关：不经过 ollupi，不受权限和沙箱限制。

`Terminals` 用 `node-pty` 启动 `$SHELL -l`（默认 `/bin/zsh`），`TERM=xterm-256color`，`COLORTERM=truecolor`，工作目录是工作区根目录。每个工作区一个，key 是工作区 ID。

- 关闭面板只是隐藏。shell 继续运行，直到它自己退出或应用退出。
- 输出的最后 256 KB（`KEPT`）留在主进程。重新打开面板时 `open` 把它返回，先画出来，再接新内容。
- 重启按钮关掉 shell 再开新的。被替换的 shell 之后的输出和退出事件被忽略。

渲染进程用 `xterm.js`，字号 12，`scrollback` 5000，颜色从 token 读。配色或明暗变化时重建终端，内容由保留的输出恢复。

`node-pty` 不能放进 asar，打包时解包，见 [发布](/zh/desktop/release)。

## 任务

显示 agent 当前的计划和进度。ollupi 不单独存计划，每次 `update_plan` 调用替换整份计划，所以 `currentPlan` 从后往前找最后一个完成的 `update_plan`。被拒绝或无效的调用不算，它们没有改变任何东西。

顶部写"已完成 n/m"。步骤用形状和字重区分状态，不用颜色。计划可能在还没加载的早期消息里，这时 `hasMore` 决定空状态的文案。

## 上下文

显示这个会话的模型调用用掉了多少上下文。数据来自引擎记录在条目上的 `ContextStats`：每次模型调用的统计只放在这次调用的一个条目上，依次是回答、思考、第一个工具调用；失败的调用放在错误条目上，压缩放在 `contextCompaction` 条目上。`modelCalls` 按顺序收集它们。

`contextUse` 算出最近一次调用（不含压缩）的组成：

```ts
function calibration(s: ContextStats): number {
  return s.estimatedTokens > 0 ? (s.calibratedTokens || s.estimatedTokens) / s.estimatedTokens : 1
}
```

引擎按文本估算每一部分，再用 API 报告的输入 token 校准总数。这里把系统提示词、工具定义、记忆都乘上这个系数，和引擎判断是否压缩时的算法一致。总量（`calibratedTokens`，没有时用 `estimatedTokens`）减去这三部分就是消息。

面板分三块：

| 块 | 内容 |
|---|---|
| 最近提示词 | 占输入预算的百分比；分段条，顺序是系统提示词、工具定义、记忆、消息；自动压缩点的刻度；每部分的 token 数和占比 |
| 最近调用 | API 报告的用量：缓存输入、写入缓存、未缓存输入、输出 |
| 模型调用 | 每次调用的时间、模型、token 数和占比，失败和压缩另外着色 |

分段的颜色固定跟部分走：系统提示词 `chart-2`、工具定义 `chart-3`、记忆 `chart-4`、消息 `chart-1`。占比低于 5%（`COLOURED_SHARE`）的部分在条上细得看不见，改用灰色。

记忆一行可以展开，列出这次提示词带的记忆快照，分全局和当前范围。`promptMemory` 从这次调用之前最后一个完成的 `memoryContext` 条目里找内容。快照在没加载的历史里时只显示数量。

## 会话权限

编辑会话这一层的审批策略和规则。权限分 agent 默认、工作区、会话三层，策略取最具体的那层，规则累加，下层去不掉上层的 deny。机制见 [权限](/zh/engine/permissions)。

`PermissionEditor` 同时用于工作区设置和这个面板。策略选"继承"时字段不写。保存调用 `thread/updatePermissions`，结果由 `thread/changed` 带回来。

进行中的轮次从下一批调用起使用新规则。子 agent 会话没有这个面板。

## 浏览器

单独成页，见 [内置浏览器](/zh/desktop/browser)。

## 代码位置

| 位置 | 职责 |
|---|---|
| ollupi-desktop `apps/desktop/src/renderer/src/views/conversation/SidePanel.tsx` | 面板框架、宽度、拖动 |
| ollupi-desktop `apps/desktop/src/renderer/src/views/conversation/WorkspacePanels.tsx` | 工作区面板的按钮和分派 |
| ollupi-desktop `apps/desktop/src/renderer/src/views/conversation/FilesPanel.tsx` | 文件树和预览 |
| ollupi-desktop `apps/desktop/src/renderer/src/views/conversation/ChangesPanel.tsx` | 改动列表、diff、提交 |
| ollupi-desktop `apps/desktop/src/renderer/src/views/conversation/TerminalPanel.tsx` | xterm 终端 |
| ollupi-desktop `apps/desktop/src/renderer/src/views/conversation/TasksPanel.tsx` | 计划 |
| ollupi-desktop `apps/desktop/src/renderer/src/views/conversation/ContextPanel.tsx` | 上下文用量 |
| ollupi-desktop `apps/desktop/src/renderer/src/views/conversation/PermissionsPanel.tsx` | 会话权限 |
| ollupi-desktop `apps/desktop/src/renderer/src/views/settings/PermissionEditor.tsx` | 权限编辑器 |
| ollupi-desktop `apps/desktop/src/main/files.ts` | 读工作区文件 |
| ollupi-desktop `apps/desktop/src/main/changes.ts` | git 操作 |
| ollupi-desktop `apps/desktop/src/main/terminal.ts` | pty |
| ollupi-desktop `packages/core/src/context.ts` | 上下文计算 |
| ollupi-desktop `packages/core/src/calls.ts` | `currentPlan` |
