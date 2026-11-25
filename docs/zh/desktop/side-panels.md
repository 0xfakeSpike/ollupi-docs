# 侧边面板

侧边面板是会话右侧的一列：浏览器、工作区文件、环境（git 改动）、终端、计划与待办、上下文用量、会话权限。它和对话并排，占窗口右侧整列，标题栏与对话对齐。

## 面板跟着会话

同一时间只显示一个面板，但**每个会话记着自己的那一个**：在 A 里开着文件面板，切到 B 时 B 露出 B 自己的（没有就收着），切回 A 原来那个还在原位，连打开的文件一起。

`navigation` store 的 `panels` 是 `Record<string, PanelState>`，键是面板的归属：会话是会话 ID，草稿是 `DRAFT_BROWSER`（`shared/ipc.ts` 里的 `'draft'`）。

```ts
export type Panel =
  | 'browser' | 'files' | 'environment' | 'terminal'
  | 'tasks' | 'permissions' | 'context' | 'todos'

interface PanelState {
  panel?: Panel
  file?: { workspaceId: string; path: string }
}
```

- `panelScope` 按当前屏幕算归属：会话取会话 ID，草稿取 `DRAFT_BROWSER`，搜索、记忆、定时任务、能力、设置没有面板。`shownPanel`、`shownFile` 先算 scope 再取值，所以组件看不到别的会话开着什么。
- `openPanel` 打开，已经开着就不动；`togglePanel` 再点一次关闭。
- 关闭面板时 `file` 留着（注释写 "outlives the panel"），下次从时间线里点文件链接直接打开它；`panel` 和 `file` 都没有时这条记录整个删掉。
- 状态只在内存里：窗口重载、退出都不保留；`localStorage` 只存宽度。
- 草稿发出第一条消息时，`conversation.ts` 调 `handOverPanel(DRAFT_BROWSER, thread.id)` 把草稿的面板交给新会话；浏览器标签页同时由 `desktop.browser.handOver` 交过去。
- 会话归档或删除时，`threads.ts` 的 `changed` 调 `forgetPanel(threadId)`，同时 `desktop.browser.forget`：归档的会话回来时面板收着，它的标签页也不再占着窗口。

::: info 演进
以前 `panel` 是 store 上的一个全局值，切换会话时面板保持打开，像一块窗格；浏览器面板先改成跟着自己的会话（`desktop@9f5f61c`），其余面板在 `desktop@623026f` 也按会话分开记。
:::

`SidePanel` 是所有面板共用的框架，下表列出各面板的组件、默认宽度和出现的条件。

| 面板 | 组件 | 默认宽度 | 需要 |
|---|---|---|---|
| `browser` | `BrowserPanel` | `half`，50% | 总是可用，草稿页也有；跟着自己的会话 |
| `files` | `FilesPanel` | `wide`，448px | 工作区 |
| `environment` | `EnvironmentPanel` | `wide`，448px | 工作区 |
| `terminal` | `TerminalPanel` | `half`，50% | 工作区 |
| `tasks` | `TasksPanel` | `normal`，320px | 会话 |
| `todos` | `TodosPanel` | `normal`，320px | Super Agent 的工作区 |
| `context` | `ContextPanel` | `normal`，320px | 会话 |
| `permissions` | `PermissionsPanel` | `normal`，320px | 会话，子 agent 会话没有；不占标题栏胶囊，从输入框的审批策略菜单进 |

草稿页可以打开浏览器，选了工作区后还能打开文件、环境、终端。**面板在哪个会话里显示由谁打开决定，内容按工作区共享**：文件、环境、终端用工作区 ID 做 key（`WorkspacePanels.tsx` 的注释 "One per workspace"），同一工作区的会话和草稿共用展开的文件夹、暂存的改动和同一个 shell；浏览器用会话 ID 做 key，每个会话一组标签页。

### 调整宽度

面板左边缘是一个 `role="separator"` 的手柄。宽度夹在 `MIN_WIDTH`（260）和父容器宽度减 `CONVERSATION_ROOM`（360）之间，CSS 的 `max-w-[calc(100%-22.5rem)]` 在窗口变窄时也守住这条线。

- **拖动**：用指针捕获，拖动时 `usePanelWidths.resizing` 为真。**方向键**一次移 `STEP`（24）：左键加宽，右键变窄。**双击**删掉记住的宽度，回到面板自己的默认值。
- **持久化**：每个面板的宽度分别存在 `localStorage` 的 `ollupi.panelWidths`，读取时丢掉小于 `MIN_WIDTH` 的值。
- 浏览器页面和 PDF 阅读器会抢指针：拖动时浏览器隐藏页面视图，PDF 的 `iframe` 加 `pointer-events-none`。主进程盖在面板上的内容从手柄右边开始（`CLEAR_OF_EDGE`，`ml-1.5`）。

屏幕根（`@container/screen`）不到 768px 时，面板不再并排，改为从右边盖在对话上：绝对定位、左边 22px 圆角（`rounded-l-3xl`）、`shadow-lg`，最宽 `calc(100%-3rem)`，总给对话留出看得到的部分。

## 文件

只读浏览工作区。`main/files.ts` 负责读，路径由渲染进程相对根目录传入，`inside` 用 `realpath` 解析后确认仍在根目录内，所以符号链接也跳不出去。列表按 Finder 的方式排序，文件夹在前，用 `Intl.Collator` 的数字感知比较；隐藏 `.git` 和 `.DS_Store`；符号链接显示成它指向的东西，断开的链接不列出；文件夹在展开时才读。

预览分四类：PDF（`.pdf`，上限 50 MB，超过只能用外部应用打开）、图片（`.png`、`.jpg`、`.jpeg`、`.gif`、`.webp`、`.svg`，上限 5 MB，超过当作二进制）、文本（前 8000 字节没有 NUL，和 git 的判断方式相同；上限 256 KB，超过只显示开头并提示）、其余只显示大小。

PDF 的字节经 IPC 传给渲染进程，转成 blob URL 放进 `iframe`，用 Chromium 自带的阅读器；这需要窗口的 `plugins: true` 和 CSP 的 `frame-src blob:`。Markdown（`.md`、`.markdown`、`.mdx`）默认渲染显示，切到源码后的选择保留到之后打开的文件；其他文本走 `CodeBlock`，语言取扩展名或文件名（比如 `Dockerfile`）。打开的文件上方显示从工作区起的路径：单击文件夹弹出 `popover` 列内容，双击回到文件树并定位。打开的文件存在所属会话的 `panels[scope].file`，时间线里的路径能让这个面板打开文件；刷新按钮让全部已展开的文件夹和当前文件重新读。

## 环境

面板名是「环境」（`environment`），因为它不只列改动，还回答"在哪跑"：第一层一行字说改了几个文件（`headline`），`Where` 一行写环境（这台电脑就写"这台电脑"，否则是环境的名字）、文件夹、分支，点开才见细节，环境那一行旁边写它是哪个提供者的沙箱；文件行左侧的复选框直接暂存。

改动本身是工作区相对 `HEAD` 的所有内容（还没有提交时对比空树）。代码注释写明了依据：ollupi 只通过命令改文件，不记录自己的编辑，所以 git 仓库才是一轮工作的体现。

`WorkspaceChanges` 调用系统的 `git`，用登录 shell 的环境，加 `GIT_OPTIONAL_LOCKS=0`（agent 可能同时在同一仓库里跑 git）、`-c core.quotePath=off` 保留中文路径。范围限定在工作区目录（可以是仓库的子目录），重命名显示成一个删除加一个新增；所有路径用 `:(literal)` 传，不当 pathspec 模式解析，`..` 开头和绝对路径直接拒绝。

**读取**用 `git status --porcelain=v1 -z` 和 `git diff <base> --numstat -z --no-renames`；文件状态由 porcelain 的两列算出：`kind` 是 `untracked`（`??`）、`added`（X 是 `A` 且工作区还有这个文件）、`deleted`（在 HEAD 里、工作区没有）或 `modified`（其余），`staged` 是 `none`（X 是空格或 `?`）、`all`（Y 是空格）或 `part`（暂存后工作区又改过）。暂存之后又删掉的新文件两边都没有，不显示。`turn` 属性变化（一轮开始和结束）、每次 git 操作之后、手动刷新时重读。diff 超过 512 KB 截断；未跟踪的文件用 `git diff --no-index /dev/null <path>`，这时路径不在 git 索引里，所以要先确认在工作区内。

**操作**：暂存 `git add -A`（包括删除）；取消暂存 `git restore --staged`，还没有提交时 `git rm --cached`；丢弃修改用 `git restore --source=HEAD --staged --worktree`，丢弃新文件先 `git rm --cached` 再移到废纸篓；提交 `git commit -q -m`，用用户的 git 身份，hooks 照常运行。丢弃前弹确认，没提交过的内容进废纸篓而不是删掉，还能找回。

## 终端

用户自己的 shell，和 agent 无关：不经过 ollupi，不受权限和沙箱限制。

`Terminals` 用 `node-pty` 启动 `$SHELL -l`（默认 `/bin/zsh`），`TERM=xterm-256color`，`COLORTERM=truecolor`，工作目录是工作区根目录，每个工作区一个，key 是工作区 ID。

- 关闭面板只是隐藏。shell 继续运行，直到它自己退出或应用退出。输出的最后 256 KB（`KEPT`）留在主进程，重新打开面板时 `open` 把它返回，先画出来，再接新内容。重启按钮关掉 shell 再开新的，被替换的 shell 之后的输出和退出事件被忽略。

渲染进程用 `xterm.js`，字号 12，`scrollback` 5000，颜色从 token 读。`macOptionClickForcesSelection` 打开：vim、less 或 agent 的 TUI 会接管鼠标、吃掉拖动，按住 Option 拖照样能选，和 Terminal、iTerm 一样。配色或明暗变化时重建终端，内容由保留的输出恢复。

`node-pty` 不能放进 asar，打包时解包，见 [发布](/zh/desktop/release)。

## 任务

显示 agent 当前的计划和进度。ollupi 不单独存计划，每次 `update_plan` 调用替换整份计划，所以 `currentPlan` 从后往前找最后一个完成的 `update_plan`；被拒绝或无效的调用不算，它们没有改变任何东西。

顶部写"已完成 n/m"和更新时间。步骤用形状和字重区分状态，不用颜色；画成列表（`PlanSteps`），不是 Markdown 原文。计划可能在还没加载的早期消息里，这时 `hasMore` 决定空状态的文案。

## 待办

只在 Super Agent 的工作区有：它没有项目文件，列的是分给各个会话的事。标题栏里它是第一个胶囊。

数据来自 `todo/list`（`LIMIT` = 2000；返回的 `more` 为真时面板说"待办比这里列出的更多"），之后跟着 `todo/changed`，哪条变了换哪行。读不出来时显示原因（`loadFailed`），不伪装成空列表。

**排序**：**进行中**（`handed`，或 `open` 但已经有会话）在前，**未分派**（`open` 且没有会话）在后，两组各带条数，空组不画。`todo/list` 也是这个顺序：没结束的按 id，已结束的按结束时间倒序。

每行两行：第一行复选框和标题（最多两行），第二行是项目区域色的标签、备注、结果、那个会话的状态胶囊和打开会话的按钮；指针停上去或聚焦时，右侧浮出完成、放弃、指派三个动作（指派是一个 `Picker`，选"不分派"就回到未分派）。

勾选完成或放弃调 `todo/update` 改 `status`，再点一次恢复；指派只改 `threadId`，不改状态。结束的待办落在下面的**归档**里，按月分胶囊（`endedAt`，没有时用 `updatedAt` 的前 7 位），月份新的在前，点开才列。协议见 [待办](/zh/integrate/protocol/todos)。

::: info 演进
待办在 `desktop@8e32b1e` 之前不分组：被指派的和没人认领的混在一起按 id 排，现在是进行中在前、两组带计数。
:::

## 上下文

显示这个会话的模型调用用掉了多少上下文。数据来自引擎记录在条目上的 `ContextStats`：每次模型调用的统计只放在这次调用的一个条目上（依次是回答、思考、第一个工具调用），失败的调用放在错误条目上，压缩放在 `contextCompaction` 上；`modelCalls` 按顺序收集它们。

`contextUse` 取最近一次调用（不含压缩）的组成。引擎按文本估算每一部分，再用 API 报告的输入 token 校准总数；面板把系统提示词、工具定义、记忆都乘上 `(calibratedTokens || estimatedTokens) / estimatedTokens`，和引擎判断是否压缩时一致。总量（`calibratedTokens`，没有时用 `estimatedTokens`）减去这三部分就是消息。

| 块 | 内容 |
|---|---|
| 最近提示词 | 占输入预算的百分比；分段条，顺序是系统提示词、工具定义、记忆、消息；自动压缩点的刻度；每部分的 token 数和占比 |
| 最近调用 | API 报告的用量：缓存输入、写入缓存、未缓存输入、输出 |
| 模型调用 | 每次调用的时间、模型、token 数和占比，失败与压缩另外着色 |

分段的颜色固定跟部分走：系统提示词 `chart-2`、工具定义 `chart-3`、记忆 `chart-4`、消息 `chart-1`；占比低于 5%（`COLOURED_SHARE`）的部分细得看不见，改用灰色。

记忆一行可以展开，列出这次提示词带的记忆快照，分全局和当前范围。`promptMemory` 从这次调用之前最后一个完成的 `memoryContext` 条目里找内容；快照在没加载的历史里时只显示数量。

## 会话权限

编辑会话这一层的审批策略和规则。权限分 agent 默认、工作区、会话三层，策略取最具体的那层，规则累加，下层去不掉上层的 deny（机制见 [权限](/zh/engine/permissions)）。`PermissionEditor` 同时用于工作区设置和这个面板：策略选"继承"时字段不写，保存调用 `thread/updatePermissions`，结果由 `thread/changed` 带回来。进行中的轮次从下一批调用起使用新规则，子 agent 会话没有这个面板。

## 浏览器

单独成页，见 [内置浏览器](/zh/desktop/browser)。

## 代码位置

| 位置 | 职责 |
|---|---|
| ollupi-desktop `apps/desktop/src/renderer/src/domains/navigation.ts` | 屏幕、面板归属、打开与关闭 |
| ollupi-desktop `apps/desktop/src/renderer/src/views/conversation/` | `SidePanel.tsx` 面板框架与宽度；`WorkspacePanels.tsx` 工作区面板的挑选；`FilesPanel.tsx` 文件树与预览；`EnvironmentPanel.tsx` 环境；`TerminalPanel.tsx` 终端；`TasksPanel.tsx`／`PlanSteps.tsx` 计划；`TodosPanel.tsx` 待办；`ContextPanel.tsx` 上下文；`PermissionsPanel.tsx` 会话权限 |
| ollupi-desktop `apps/desktop/src/renderer/src/domains/todos.ts` | 待办 store、`todo/list` 与 `todo/changed` |
| ollupi-desktop `apps/desktop/src/renderer/src/views/settings/PermissionEditor.tsx` | 权限编辑器 |
| ollupi-desktop `apps/desktop/src/main/files.ts`、`changes.ts`、`terminal.ts` | 读工作区文件；git 操作；pty |
| ollupi-desktop `packages/core/src/context.ts`、`calls.ts` | 上下文计算；`currentPlan` |
