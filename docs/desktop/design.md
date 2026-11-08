# 设计

桌面端的界面是长时间使用的工具，一个人对着它看代理干活。设计的目标是让它不抢注意力，只在需要用户的时候才显眼。所有组件只用 `packages/ui/src/theme.css` 定义的语义 token，这页是那份规则的提炼，完整准则在仓库的 `docs/design-guidelines.md`。

## 四个关键词

拿不准的时候回到这四个词做取舍。

| 关键词 | 取舍时意味着 |
|---|---|
| **安静** | 默认中性灰。颜色、粗体、底色是预算，一屏之内只该有一处在说话 |
| **可扫读** | 每一块的第一行就说清它是什么、结果如何；细节靠展开，不靠堆字 |
| **诚实** | 状态准确。在跑就显示在跑，失败就显示失败，不做装饰性的忙碌 |
| **紧凑** | 行高和内边距偏小，但正文的阅读舒适度不让步 |

## 信息层级

从上到下越来越安静。

| 层 | 内容 | 表现 |
|---|---|---|
| 1. 需要你 | 审批、提问 | 全界面唯一浮起来的东西：`raised` 底、阴影、一圈淡淡的状态色描边。对话流之外还有回响：侧边栏标记、标题栏徽标 |
| 2. 对话内容 | 用户消息、代理的回复 | `fg`、`text-body`，页面的主体 |
| 3. 过程 | 思考、工具调用、子代理、计划 | `fg-muted`、`text-ui`，每项一行，默认折叠 |
| 4. 系统 | 压缩标记、记忆载入、每轮的模型和用量 | `fg-subtle`、`text-small`，一行或一条分隔线 |

对话流里的块只有三种重量：

| 档 | 样式 | 用于 |
|---|---|---|
| L0 行 | 无底无框，`text-ui`，悬停时整行 `hover` 底 | 思考、工具调用、记忆载入 |
| L1 块 | `bg-surface`、`rounded-lg`，无边框无阴影 | 代码块、工具输出、计划、用户消息气泡 |
| L2 行动 | `bg-raised`、`shadow-sm`，一圈状态色描边 | 审批、提问 |

描边的颜色就是危险分级：提问 accent，普通审批 warning，跑到沙箱外的审批 danger。

## 克制的规则

- **主按钮是墨色**（`ink`），浅色里近黑、深色里近白。颜色不承担"这是主操作"的意思，位置和墨色承担。一个区域最多一个主按钮。
- **强调色只用于**焦点环、表单控件的选中态、链接、进度填充、等待用户的信号。面积大于一个控件的地方不铺 accent。
- **成功是常态，不着色。** 只有失败、等待、被拒才有标记。例外是 diff 的 `+n −m` 和 diff 代码块的增删行底色。
- **拒绝不是错误，** 不用红色。
- **状态色** 只出现在图标、文字、描边和徽标上，不做块的底色。
- **不用单侧色条。** 圆角卡片上的色条会被裁成弧形，又和图标重复。
- **边框一律 1px。** `line` 做分隔，`line-strong` 做输入框和行动块。

## Token 体系

`theme.css` 里的 `@theme inline` 用 `initial` 清掉 Tailwind 默认的色板、字号、字重、圆角、阴影和缓动，只留这里定义的档位。越界的写法（`text-sm`、`bg-blue-500`、`font-bold`）不生成样式，一眼就能发现。

主题就是一组变量值，组件里没有深色专用的 class。语义类名映射到 `--ol-*` 变量：

```css
--color-canvas: var(--ol-canvas);
--color-fg-muted: var(--ol-fg-muted);
--color-accent: var(--ol-accent);
```

### 颜色

每套配色只写基础色，其余都由它们推出来。

| 基础 token | 用于 |
|---|---|
| `ground` | 窗口底色：侧边栏、后端启动页 |
| `canvas` | 主画布 |
| `surface` | 代码块、工具输出、用户消息 |
| `raised` | 对话框、菜单、toast、行动块 |
| `knob` | 开关的圆钮 |
| `fg`、`fg-muted`、`fg-subtle` | 文字三档 |
| `ink`、`ink-fg` | 主按钮 |
| `accent`、`accent-fg` | 强调 |

派生色写在 `:root, [data-palette]` 里，用 `color-mix` 算出，所以换配色不用改它们：

| 派生 token | 浅色 | 深色 |
|---|---|---|
| `hover` | `fg` 4.5% | `fg` 5.5% |
| `selected` | `fg` 7% | `fg` 8.5% |
| `line` | `fg` 8% | `fg` 7.5% |
| `line-strong` | `fg` 14% | `fg` 13% |
| `scrim` | `fg` 32% | 黑 55% |
| `accent-soft` | `accent` 10% | `accent` 15% |
| `focus` | `accent` 30% | `accent` 40% |

状态色和图表色所有配色共用：

| token | 浅色 | 深色 |
|---|---|---|
| `success` | `#1b7f3c` | `#43b85c` |
| `warning` | `#a86400` | `#e0a237` |
| `danger` | `#d8323d` | `#f2615f` |
| `chart-1`（蓝） | `#2a78d6` | `#3987e5` |
| `chart-2`（橙） | `#eb6834` | `#d95926` |
| `chart-3`（青） | `#1baf7a` | `#199e70` |
| `chart-4`（黄） | `#eda100` | `#c98500` |

### 字号

| class | 字号 / 行高 / 字重 | 用在 |
|---|---|---|
| `text-caption` | 11 / 16 / 500 | 徽标、快捷键提示 |
| `text-small` | 12 / 18 / 400 | 元信息、系统信息、分组标题 |
| `text-ui` | 13 / 20 / 400 | 界面默认 |
| `text-body` | 15 / 24 / 400 | 对话正文 |
| `text-title` | 15 / 22 / 600 | 对话框和分区标题 |
| `text-display` | 20 / 28 / 600 | 新会话页标题、整页错误 |

字重只有 400、500、600。Markdown 的标题相对正文放大（h1 1.35em、h2 1.2em、h3 1.05em），它们属于内容，不用这张表。

### 其他尺度

| 尺度 | 档位 |
|---|---|
| 间距 | 基数 `--spacing: 4px` |
| 圆角 | `sm` 4、`md` 6、`lg` 8、`xl` 12、`2xl` 16 |
| 阴影 | `sm` 行动块和输入框外壳，`md` 菜单和 toast，`lg` 对话框 |
| 动效缓动 | `cubic-bezier(0.2, 0, 0, 1)` |
| 入场动画 | `enter` 160ms（上移 4px），`dialog` 240ms（0.98 缩放），`fade` 160ms |
| 容器宽度 | `thread` 800，`dialog` 480，`dialog-wide` 640 |

深色下阴影几乎看不见，层次靠更亮的 `raised` 底和边框，所以带阴影的东西都有 1px 边框。

动效遵守 `prefers-reduced-motion`：入场动画换成淡入，shimmer 关掉。

## 配色方案

六套配色，id 在 `@ollupi/ui` 的 `palettes`。默认是 `plum`。

| 名称 | id | 浅色 `ground` | 浅色 `accent` | 深色 `ground` | 深色 `accent` |
|---|---|---|---|---|---|
| 梅子 | `plum` | `#f7f5f4` | `#8a4a6b` | `#1b191a` | `#d08fb0` |
| 宣纸 | `paper` | `#f3f0e8` | `#3d6b4f` | `#1b1a17` | `#7fb08f` |
| 雾蓝 | `mist` | `#f4f5f7` | `#5a7fb0` | `#17181b` | `#8fb0dc` |
| 靛紫 | `indigo` | `#f6f6f7` | `#5b5bd0` | `#18181b` | `#9696f0` |
| 古铜 | `bronze` | `#f5f3ef` | `#9a7238` | `#191816` | `#c9a064` |
| 黛蓝 | `teal` | `#f2f4f3` | `#2f6a74` | `#161918` | `#79b3bc` |

`<html data-palette>` 决定全应用的配色。任何元素带上 `data-palette` 就用那一套，设置页的预览色块就是这样画的。

明暗有跟随系统、浅色、深色三档。渲染进程通过 `desktop.setColorScheme` 设 Electron 的 `nativeTheme.themeSource`，`prefers-color-scheme` 和原生窗口一起变，所以 CSS 里只有媒体查询这一种深色写法。

要加一套配色：在 `theme.css` 加一个 `[data-palette='id']` 块，浅色深色各一份，把 id 加进 `palettes`，再在词表的 `appearance.palettes` 里给中英文名。组件不用改。

## 字体

| 用途 | 字体 | 来源 |
|---|---|---|
| 界面和正文 | Inter Variable | 打包进应用（OFL） |
| 代码 | JetBrains Mono Variable | 打包进应用（OFL） |
| 中文 | 苹方 | 系统回退 |

```css
--ol-font-sans: 'Inter Variable', 'PingFang SC', -apple-system, BlinkMacSystemFont, 'Hiragino Sans GB', sans-serif;
--ol-font-mono: 'JetBrains Mono Variable', ui-monospace, 'SF Mono', Menlo, 'PingFang SC', monospace;
```

**中文标点。** 界面语言是中文时，`:root:lang(zh)` 把 `CJK Punctuation` 放到字体栈最前。这个字体只覆盖弯引号、破折号和省略号（`unicode-range`），字形取自苹方，不让 Inter 画成西文的窄标点。英文界面不受影响。

**混排。** 不加 `letter-spacing`，不用全大写，中文不用斜体。用户和代理的文字原样显示，不在中英文之间自动加空格。

**等宽。** 命令、路径、文件名、模型 ID、环境变量、退出码用 `font-mono`。

**数字。** 表格、上下文面板、时长、token 数用 `tabular-nums`。

## 图标

用 lucide，全局 `strokeWidth` 是 1.75。14px 用于行内，16px 是默认，20px 用于空状态和整页错误。颜色继承文字，只有图标本身表达状态时才着色。纯图标按钮必须有 `label`，同时作为无障碍名称和提示。

## 文案语气

界面有英文和简体中文两份词表，语气一致。

- **平实直接。** 不用感叹号，不拟人卖萌，不堆砌道歉。
- **按钮动词开头，** 说出结果：`Run outside sandbox`，不写 `OK`、`Confirm`。中文同理：`在沙箱外运行`。
- **英文用 sentence case，** 不用 Title Case。专有名词保持原样。
- **进行中用现在分词加省略号，完成后用过去式。** `Thinking…`、`Thought for 3.8s`。省略号是单个字符 `…`。
- **出错提示三段：** 什么失败了，为什么，用户能做什么。不知道原因时给原始错误，不编造解释。
- **审批和提问的标题是一个问句，** 主语是动作：`允许运行这条命令？`。
- **空状态** 的标题说现状，说明说它是什么或怎么开始，不重复标题。

## 代码位置

| 位置 | 职责 |
|---|---|
| ollupi-desktop `docs/design-guidelines.md` | 完整设计准则 |
| ollupi-desktop `docs/design-brief.md` | 设计需求 |
| ollupi-desktop `packages/ui/src/theme.css` | token、配色、字体 |
| ollupi-desktop `packages/ui/src/theme.ts` | 配色 id 列表 |
| ollupi-desktop `packages/ui/src/` | 按钮、表单、浮层、对话流组件 |
| ollupi-desktop `apps/desktop/src/renderer/src/domains/appearance.ts` | 应用配色和明暗 |
| ollupi-desktop `apps/desktop/src/renderer/src/styles.css` | `.markdown` 等全局样式 |
| ollupi-desktop `apps/desktop/src/renderer/src/i18n/messages/` | 英文和中文词表 |
