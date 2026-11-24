# 渲染进程

React 19 写的界面，运行在沙箱里。它把引擎的状态镜像到本地，再把镜像画出来：服务器状态都来自网关，按领域分成若干 Zustand store；纯逻辑放在 `@ollupi/core`，组件只读 store。

## 屏幕和路由

没有 URL 路由。当前屏幕是 `navigation` 里的 `Screen`（`draft`、`thread`、`search`、`memory`、`cron`、`capabilities`、`settings`），`App.tsx` 用 `switch` 选组件：`draft`（`DraftScreen`）是还没创建的会话，选工作区和模型，发第一条消息才创建；`thread`（`ConversationScreen`）是标题栏、时间线、输入框和侧边面板；`search` 是全局搜索，`memory`、`cron` 是记忆与定时任务，`capabilities` 是技能、MCP、内置工具，`settings` 是所有设置一页。`found` 是搜索带来的定位目标，列表就绪后滚到那一条并闪一下（`.found` 动画）。

- 第一次同步完成前，或后端 `failed` 时，显示 `BackendScreen`；同步过一次之后，重连和重启期间界面保持原样，连接状态只在侧边栏底部。
- 协议版本不一致时，窗口顶部加一条横幅。
- `Toasts` 最多 3 条（`MAX_SHOWN`），新的挤掉最旧的；info 4 秒消失，错误 1 分钟后消失（`ERROR_TTL_MS`），都能手动关。提示画在输入框上方（`ToastHost`，`absolute right-4 bottom-4 w-90`）：输入框是后面的定位元素，放在列的最底就会被它盖住。
- 对话框、菜单和 `Picker` 用 `createPortal` 画到根节点（带 `data-region`、`data-overlay`），在侧栏里打开的对话框因此不被遮罩和裁剪切掉；有对话框打开时（`useDialogOpen`），浏览器面板里的系统页面先让开。

`navigation` 还放客户端自己的状态：`model`（换会话时清空）、`environment`、`approval`（草稿页选的审批策略）、`panels`（每个会话的面板，见[侧边面板](/zh/desktop/side-panels)）、`focus`（`{ threadId, itemId }`）。`go()` 把当前会话写进 `sessionStorage` 的 `ollupi.openThread`，重载后回到原处。

## 状态管理

每块服务器状态是一个域（domain）：有自己的 store，并声明三个可选方法——`bind` 订阅网关事件（在 `sync` 之前跑，两者之间不漏事件）、`sync` 在新连接上加载状态、`disconnect` 丢弃只对刚结束的连接有效的状态。

| 域 | 镜像什么 | 同步方式 |
|---|---|---|
| `environments` | 环境列表 | `environment/list`，之后 `environment/changed` |
| `workspaces` | 工作区列表 | `workspace/list`，之后 `workspace/changed` |
| `threads` | 侧边栏会话 | 每个工作区一次 `thread/list`，每页 50 |
| `conversation` | 打开过的会话的时间线 | 重读当前会话，丢弃其他 |
| `requests` | 等用户的审批和提问 | 网关初始化后重发 |
| `notices`、`notifications` | 网关错误、系统通知 | 只收带 `itemId` 的 `error`；通知只订阅事件 |
| `models` | 模型列表和默认模型 | `model/list`，每条连接一次 |
| `tools` | 工具列表 | `tool/list` |
| `cron` | 定时任务 | `cron/list`，之后 `cron/changed` |
| `settings` | 脱敏开关 | `settings/read`，之后 `settings/changed` |
| `mcp` | MCP 服务器 | `mcpServer/list` 和 `tool/list`，之后 `mcpServer/changed` |
| `todos` | 待办 | `todo/list`（`LIMIT` 2000），之后 `todo/changed` |

同步按数组顺序串行执行，`workspaces` 必须在 `threads` 之前。工作区、定时任务和设置的写操作不直接改 store：结果不应用，等引擎的变更通知，所以别处发起的改动走同一条路径。用户动作包在 `run()` 里，失败变成一条 toast。用量不在域里，只读，设置页要用时自己问。

### 连接

`gateway/session.ts` 跟随主进程上报的后端状态：

- 后端每换一次状态 `epoch` 加一，旧循环看到就退出——重启后地址和令牌都换了。
- `ready` 就进 connect 循环：连接、`initialize`、比较 `protocolSha256`、各域 `bind` 后依次 `sync`，最后置 `connected`。
- 失败后退避 `min(5000, 250 * 2^attempt)` 毫秒。
- `watchClose` 在同步之后才挂：同步中途断开由它重试。此时再开一个循环，两条连接会在网关互相顶替（网关每个用户只留一条）。

断开后 `requests` 清空，新连接初始化时网关重发全部待处理请求。

## 协议类型

`packages/protocol/scripts/generate.mjs` 从 ollupi 的 `gateway/protocol.schema.json` 生成全部类型：`types.ts`、方法名与通知名（`messages.ts`，含 `PROTOCOL_SHA256`）、内置工具的 ajv 校验器（`tools.validate.js`，提前编译成普通 JS，因为 CSP 禁止 eval）和类型守卫（`tools.ts`）。契约与网关分发给客户端的是同一张表，见 [协议](/zh/integrate/protocol)；`pnpm protocol:generate` 写入，`pnpm protocol:check` 在过期时失败。

三道检查守着类型和实际流量：测试时 `contract.test.ts` 拿录下的 `fixtures/session.json` 校验两个方向；开发构建（`gateway/contract.ts`）用 `Inspector` 校验每条消息，不符就弹 toast，生产包不带；每次连接比较 `initialize` 的 `protocolSha256` 与 `PROTOCOL_SHA256`，不同就挂横幅。

## 时间线

`Timeline` 是客户端手里的一份会话副本（`thread`、`turns`、`items`、`hasMore`）。每个函数返回新对象，未变的部分保持引用，所以任何状态容器都能放，`memo` 也能生效。

### 事件归并

`applyEvent` 是唯一入口。通知带落库后的完整行，所以多是替换，不是打补丁：`turn/changed` 用 `upsertTurn`；`item/changed` 用 `upsertItem` 按 ID 替换再按 `seq` 排序，比手里那份更旧（`updated` 更小）的行不覆盖；三种 `changed` 都只应用 `seq` 比时间线新的。条目从开始、未完成时的变化（比如审批前冻结的执行内容）到结束都走 `item/changed`，每次带完整的一行。`item/agentMessage/delta` 和 `item/reasoning/textDelta` 用 `appendDelta`：增量不保证完整，条目还没到时先给它建一个临时条目往里写，直到 `item/changed` 带着全文把它替换掉。`thread/changed` 有行时 `setThread`，没行是会话已删除，从 store 移除并回草稿页。

### 分页

打开会话用 `thread/resume`，每页 100 条（`PAGE_SIZE`）；网关还会在约 4 MB 处截断并报 `hasMore`，这个调用同时让网关重发这个会话里还在等的请求。

| 情况 | 函数 |
|---|---|
| 首次打开 | `timelineFromPage` |
| 加载更早 | `thread/read` 带 `beforeSeq`，`prependPage` 合并去重 |
| 重连后 | `refreshFromPage`：新页替换活动尾部，更早的已加载条目保留 |
| 定位到某条 | `openThreadAt` 循环读更早的页，进入范围后设 `focus` |
| 导出 | `readWhole` |

### 从时间线到屏幕

`groupByTurn` 把条目挂到各自的轮次下（排队中的轮次用 `queuedTurns` 取）。`groupReads` 把相邻两个以上的 `read_file`、`glob`、`grep` 合成一行，等审批的调用不合并。`ItemView` 按 `item.type` 分派并 `memo` 包住。`callOf` 分 `command`、`file`、`read`、`glob`、`grep`、`plan`、`question`、`subagent`、`tool`，`views` 按种类穷举。

`run_command`、`edit_file`、`write_file` 读的是 `preparedExecution`（审批前冻结的内容），那才是实际执行的。每轮结果由 `TurnOutcome` 画：失败红字，停止灰字，完成时一行写模型、耗时和用量。

### 审批和提问

`requests` 域按条目 ID 存待处理请求，每项持有 JSON-RPC 请求的 `resolve`；工具调用的行用 `usePendingRequest(item.id)` 找到它，卡片画在行下面，`item/changed` 带来的条目不再等审批或回答时把它移除。子 agent 的请求画在父会话的 `Agent` 调用下面，子 agent 的会话只读。

需要全权（full access）的调用是危险级别（`fullAccess` 取自冻结执行里的 `escalated`）：不提供"这件事里都可以"，主按钮是"允许完全访问"，回车也不会替人确认这一下。

### 发送消息

空闲时 Enter 和 ⌥Enter 都是 `turn/start`；运行中 Enter 是 `turn/steer`（插话），⌥Enter 是 `turn/start`（排队）；插话输给轮次结束时（`noActiveTurn`、`turnMismatch`）改发 `turn/start`。

输入法组合期间的 Enter 不发送，Shift+Enter 换行。草稿页的顺序是 `thread/start`、把草稿的浏览器标签页交给这个会话、跳转、再发第一轮。`titleFromMessage` 取第一条非空行，空白折叠，最多 60 字符，没有文字时用第一个附件的文件名。

## 滚动

时间线没有虚拟化，靠 `ItemView` 的 `memo` 和分页控量。`useStickToBottom` 负责贴底：离底部 80 像素（`NEAR_PX`）以内算贴底，往上滚后不再跟随并出现"回到最新"；监听用 `ResizeObserver` 和 `MutationObserver`，流式文字、展开的输出、异步加载的图都跟得上。滚动区用 `.scroll-centered`（`scrollbar-gutter: stable both-edges`），让列内容和输入框对齐。

## Markdown

回复由 `Streamdown` 解析，流式时先把没闭合的代码块、表格、强调补全；样式只来自 `.markdown` 里基于 token 的规则。代码块用 Shiki，`github-light` 和 `github-dark` 同时生成（`defaultColor: false`），跟随明暗，语言用时才加载，用 JavaScript 正则引擎，因为 CSP 不允许 WebAssembly。diff 由 transformer 给 `+`、`-` 开头的整行着色；脚注每条消息都从 1 编号，id 会重复，点击时在当前 `.markdown` 内滚动。

### Mermaid

`flowchart`、`graph`、`stateDiagram`、`sequenceDiagram`、`classDiagram`、`erDiagram`、`xychart-beta` 由 `beautiful-mermaid` 同步绘制，颜色是 CSS 变量，换配色不用重画；其他类型和它画失败的交给 `mermaid`，用时动态加载，`securityLevel: 'strict'`，主题变量从 token 解析成不透明的 `#rrggbb`，换配色或明暗时重画。流式中（`useIsCodeFenceIncomplete`）显示源码；都解析不了时保留源码并写原因。

`balanceDecisions` 处理判断节点：按标签宽度定边长，没换行的标签按词断行（中文用 `Intl.Segmenter`），取接近最小正方形、行数最少的方案。

图按自身尺寸绘制：`mermaid` 初始化时各类图都传同一份 `natural` 选项（`useMaxWidth: false`），`fontSize: 13`，宽图不会为了塞进列而把字缩小、窄图也不会被放大。图能原地缩放：`ctrl` 或 `meta` 按住滚轮，以及触控板双指捏合（Chromium 报成带 `ctrlKey` 的 `wheel`），都在滚动容器上以 `passive: false` 监听 `wheel`，`exp(-deltaY * unit * 0.002)` 求倍率，夹在 `least`（0.5）到 `most`（4）之间；没有修饰键的滚轮直接放行，页面照常滚动。`paint` 改的是 SVG 的 `width`、`height` 而不是 `transform`，线条按最终尺寸重画，容器的滚动条覆盖整张图；指针落在图上的相对位置先换算成比例（`fx`、`fy`），缩放后据此修正 `scrollLeft`、`scrollTop`，指着哪里就停在哪里。`Block` 的动作区有百分比胶囊 `ScaleReadout`，100% 时也在，因为它是发现图能缩放的入口；点一下回 100%，双击图面同样复位。倍率不是 1 时容器改成 `overflow-auto` 并以 `maxHeight: 70vh` 限高，超出部分横竖滚动，按住左键拖动平移（`setPointerCapture`）；1× 时不拦指针，图里的文字仍可选中。换工作区配色或明暗会换一张新 SVG，`useEffect` 先量出原始尺寸再按保留的倍率重画，量出零尺寸时直接跳过。

### 工作区文件链接

`workspacePath` 判断一段文字是不是工作区路径：相对路径或根目录下的绝对路径，去掉开头的 `./` 和结尾的 `:行号`；不含 `/` 又没有扩展名的词不算。是否存在由 `files.kind` 问主进程，找到的记住，找不到的下次再问。单击在文件面板打开，⌘+点击用默认应用打开。

## 搜索

⌘K 从任何界面打开（`useSearchShortcut`）。输入停顿 250 ms 才发请求（`PAUSE_MS`），每组最多 20 条（`LIMIT`）。结果按会话、消息、任务、记忆分组，只列非空分组并标条数；点会话打开它，点消息打开并定位，点任务或记忆跳到列出它的页面（`focus` 与 `useFound`）。记忆页的搜索框用同一个 `search`，`workspaceId` 传当前标签页的范围。

## 能力页

技能按 agent 分组，每个技能是一张卡片（`grid-cols-[repeat(auto-fill,minmax(17.5rem,1fr))]`），只写该 agent 实际收到的东西：名字，和它据以判断要不要用的描述；`SKILL.md` 旁边的文件用上才读，留在菜单里打开。内置工具按 provider 分组：`ToolsSection` 只从 store 选存储列表本身（`serverList`），再用 `useMemo` 造组，免得每次同步都重算；MCP 服务器名与 provider 名相同，一个组就是一台服务器，参数说明收在展开项里。

## 设置页

设置在一页（`SettingsScreen`），左侧列表按 `sections` 顺序：`general`、`redaction`、`notifications`、`appearance`、`language`、`permissions`、`models`、`usage`。等后端回答的几节排在后面，免得到位时把上方内容顶下去。

### 用量

`UsageSection` 只读引擎记下的用量，不写库也不缓存。`useUsage` 用同一段时间连发三次 `usage/query`，`groupBy` 分别是 `day`、`workspace`、`model`，三次覆盖同样的行，合计对得上。范围只有 7 天和 30 天（`periods`，默认 `d7`），今天算在内，按本地日期切（`offsetMinutes` 取 `-now.getTimezoneOffset()`）。

- 总量是一条四段条：缓存输入（`bg-chart-1/45`）、写入缓存的输入（`bg-chart-1/70`）、未缓存的输入（`bg-chart-1`）、输出（`bg-chart-2`）；`tokensOf` 只加输入和输出，缓存已算在 `inputTokens` 里。
- 每日柱按最忙的一天定高，输入在下、输出在上，最后一天标"今天"；30 天视图每 5 天标一次日期。按工作区、按模型两个列表按用量降序，空 key 表示没记下。
- 没有记录是空状态；后端没运行是离线提示加重启；查询失败可重试。

字段和错误码见 [用量协议](/zh/integrate/protocol/usage)。

## 语言与本地存储

界面有 `en` 和 `zh-CN` 两份词表，放在 `i18n/messages/` 下按区域分文件；中文词表的类型是 `typeof en`，少一个键编译不过。组件用 `useT()`，React 之外用 `t()`，切换立即生效。语言跟随系统时 `zh` 开头对应中文，其余英文。偏好只属于这台机器，存在 `localStorage`：`ollupi.theme`、`ollupi.colorScheme`、`ollupi.language`、`ollupi.notifications`、`ollupi.panelWidths`。

## 代码位置

| 位置 | 职责 |
|---|---|
| ollupi-desktop `apps/desktop/src/renderer/src/views/App.tsx` | 屏幕切换 |
| ollupi-desktop `apps/desktop/src/renderer/src/gateway/session.ts` | 连接、重连、跑各域 |
| ollupi-desktop `apps/desktop/src/renderer/src/domains/navigation.ts` | 屏幕、面板、重载去处 |
| ollupi-desktop `apps/desktop/src/renderer/src/domains/` | 各域 store 与动作（`conversation`、`requests`、`usage` 等） |
| ollupi-desktop `apps/desktop/src/renderer/src/views/conversation/`、`views/common/` | 时间线、工具视图、提示、贴底、Markdown 与图、定位 |
| ollupi-desktop `apps/desktop/src/renderer/src/views/settings/`、`views/capabilities/`、`views/search/` | 设置、能力、搜索 |
| ollupi-desktop `apps/desktop/src/renderer/src/i18n/` | 词表 |
| ollupi-desktop `packages/core/src/timeline.ts`、`calls.ts` | 归并、工具分类 |
| ollupi-desktop `packages/protocol/scripts/generate.mjs` | 生成协议类型 |
| ollupi-desktop `packages/client/src/client.ts` | 类型化客户端 |
