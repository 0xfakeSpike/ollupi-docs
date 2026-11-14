# 品牌

Ollupi 的名字、标识、图标和字标，以及它们在产品里出现的规矩。界面本身的视觉语言见 [设计语言](/zh/desktop/design)。完整准则在 ollupi-desktop 的 `apps/desktop/PRODUCT.md`（名字和定义）和 `packages/ui/DESIGN.md` 第 0 节（标识和用法）。

## 名字

| 项 | 写法 |
|---|---|
| 名字 | **Ollupi**。界面和文案里首字母大写；全小写的 ollupi 只出现在字标、代码、命令和路径里 |
| 读法 | 英文 /oʊˈluːpi/（oh-LOO-pee，重音在第二个音节）；中文第一次出现时注"读作'欧噜比'" |
| 中文 | 也写 Ollupi，不另起中文名、不音译 |
| 定义句 | Ollupi 是一直在干活的个人助手。/ Ollupi is a personal assistant that keeps working. |
| 标语 | 交给它，你走开。/ Hand it over. Walk away. |

**含义**（可以原样用在官网和"关于"里）：

> 名字里的 lupi，是意大利语的"狼"。狼在夜里也醒着，记得同伴，守着自己的地方。Ollupi 也是这样：你走开，它还在干活；它记得你；碰你的东西之前，先问你。
>
> The lupi in its name is Italian for wolves — awake at night, loyal to its own, keeping its ground. Ollupi works the same way: it keeps going when you walk away, it remembers you, and it asks before it touches anything of yours.

这三件事对应产品真有的能力：一轮工作在你离开后继续跑，记忆让它越用越懂你，审批让它碰你的东西之前先问你。

中文文案只在这段含义里说"狼"。别处不拿"狼"做形容，因为"狼性"在中文职场是贬义的过劳文化；讲的是"守着、醒着、记得你"。

::: info 演进
名字在 2026-11-13 审查过一次：公开搜索找不到用 "ollupi" 的产品或商标，ollupi.com、ollupi.ai 当时都未注册，GitHub 和 npm 上没有同名账号或包。它的短处是名字本身不说明产品是什么，所以由定义句补上；改名要动三个仓库约 2,200 处、App ID `dev.ollupi.desktop`、数据目录 `~/.ollupi`、引擎的 Go 模块路径和发布地址，代价大于收益，于是保留。
:::

## 标识

一只坐在月亮前的**小狼**：侧身、抬头看着前方，尾巴绕到前爪边，背上一块深色的"鞍"，尾巴尖是深色的，内耳和喉部颜色浅一些。画法参考非洲的黑背胡狼（大耳朵、细长、背鞍）。它守着、醒着、可亲，不嚎叫、不凶。

文案里只说"小狼"，不说胡狼：英文的 jackal 有"替人干脏活的走狗"的意思，中文的"豺狼"也是贬义。

| 颜色 | 值 | 用在 |
|---|---|---|
| 燕麦 | `#f4ecda` → `#e3d5b6` | 图标和圆形标识的底，上浅下深 |
| 月 | `#fffaf0`，边 `#e6d8bb` | 月亮，比底更浅，一圈细边 |
| 毛色 | `#c08a55` | 小狼；64px 以下的单色剪影用 `#a8733f` |
| 浅毛 | `#ead2ab` | 内耳、喉部 |
| 鞍 | `#3b3350` | 背鞍、尾巴尖 |
| 眼 | `#2b2541` | 眼睛 |

**和界面同一家。** 燕麦本来就是界面的区域色之一，图标和圆形标识用它做底，和石与苔（见 [设计语言](/zh/desktop/design)）是同一个色调；浅底在深色、浅色的 Dock 里都显眼。彩色的标识只在品牌时刻出现：App 图标、"关于"、第一次打开、官网首屏、README。

::: info 演进
标识刚定下时，图标和圆形标识是夜紫底（`#2b2541`），讲"夜里守着你"，规则是"白天归界面，夜晚归品牌"。用上以后，夜紫在 Dock 里太暗，夹在一排亮色图标中间不显眼。2026-11-13 比较了提亮的夜紫、苔绿、燕麦和黄昏几版，用户选了燕麦底配彩色小狼。
:::

::: info 演进
上一版标识是像素画的小狼（格墨方向：夜蓝墨色、像素网格、Bricolage Grotesque 字体），有咧嘴、眨眼、左右张望等表情，也用在界面里的加载和状态行上。2026-11-12 界面换成石与苔，2026-11-13 标识换成现在的小狼（`desktop@2bb5967`）。中间试过只画狼头，冷峻、像游戏战队标识，也试过圆头，读起来像猫；完整的、可亲的小狼是用户选的方向。
:::

## 图标与字标

| 文件 | 用途 |
|---|---|
| `app-icon.svg` | macOS 图标：1024 画布，824 的圆角方块内缩 100，带阴影 |
| `app-icon-small.svg`、`app-icon-16.svg` | 64px 以下：小狼放大、单色、无阴影，小尺寸也认得出 |
| `mark.svg`、`favicon.svg` | 圆形标识：燕麦圆、月亮、小狼。头像、文档站导航、README |
| `mark-mono.svg` | 单色剪影，只在必须单色时用 |
| `wordmark.svg`、`wordmark-dark.svg` | 字标 |
| `logo.svg`、`logo-dark.svg` | 圆形标识加字标 |
| `poses/wolf-*.svg` | 小狼的六种姿势（见下） |
| `png/` | 各尺寸的图标、favicon、圆形标识和 logo 的 PNG |
| `Ollupi.icns` | macOS 图标，打包进应用 |
| `preview.png` | 品牌总览图 |

**字标**是小写的 "ollupi"，Manrope 750、字距 −3%，转成路径，不依赖字体。浅底用墨（`#22252a`），深底用纸色（`#ecedea`）。和标识并排时，字的 x 高居中对齐标识的中线，字高（1em）约为标识直径的 46%。应用里，字标在侧栏顶部、红绿灯那一行的右端。

品牌的一切都在 ollupi-desktop 的 `assets/brand/`，只此一处：`make.py` 从一处画法（`figure.py`、`poses.py`）和 Manrope 的字形生成全部 svg、各尺寸 png、macOS 图标 `Ollupi.icns` 和总览图，也把应用里用的姿势和圆形标识生成到 `views/common/wolfArt.ts`。应用打包直接用这里的图标；引擎的 README 用这里的 logo，引擎的配图从这里读圆形标识，本站构建时从这里同步标识。改画法只改一处，重新生成。

## 暮色版

暮色主题有一版自己的小狼（`assets/brand/dusk.py`）：同一只小狼，坐在黄昏的天空里（靛蓝、薰衣草、玫瑰、蜜桃），月亮发光；整幅带细颗粒，小狼和月亮的边缘溶解成颗粒，身上是从月亮那边打来的喷枪式明暗。周围是非洲草原的点缀：脚边两簇草，地平线上远远一棵金合欢，几点萤火，两只飞鸟，都很小，主角仍是小狼和月亮。

| 文件 | 用途 |
|---|---|
| `app-icon-dusk.svg`、`png/app-icon-dusk-1024.png` | 暮色主题下 Dock 里的图标（运行时切换） |
| `mark-dusk.svg`、`png/mark-dusk-1024.png` | 暮色的圆形标识，"关于"和第一次打开时 |

Dock 图标跟着主题在运行时换；Finder 和启动台里显示的是打包时的燕麦图标，运行中的应用改不了它。

## 小狼的姿势

六种姿势，同一个头、同一套比例，看得出是同一只。

| 姿势 | 意思 | 应用里用在 |
|---|---|---|
| 坐着 | 守着、等着 | 会话还没有消息；这个范围没有记忆、这里没有定时任务 |
| 竖耳听 | 在认识你 | 记忆为空 |
| 低头嗅 | 在找 | 搜索没结果 |
| 小跑 | 出发、学新本事 | 还没有技能 |
| 趴着 | 休息、没事可做 | 没有定时任务 |
| 蜷着睡 | 安静、关着 | 技能关着 |

**只在安静的时刻出现**：空状态和第一次。第一次打开、还没有任何会话时，新会话页问候上方放一次圆形标识；设置 → 通用最上面一行"关于 Ollupi"放圆形标识、定义句和标语。

**不出现在**对话流、审批和提问卡片、状态行、加载、按钮、侧栏会话行、提示框和出错页：这些地方每天看几百次，或者人正着急。

界面里的小狼只用单色剪影（`Wolf` 组件；暮色主题下脚边多两簇草和两点萤火），颜色跟随周围文字（通常 `fg-subtle`），镂空是所在的底色，64px；彩色的圆形标识（`Emblem`）只在品牌时刻。它不循环动、不代替文字，读屏软件跳过它（`aria-hidden`）。

::: info 演进
姿势和放置在 `desktop@c1bf458` 加入。放在哪、不放在哪按 impeccable 技能的 delight 一章判断：干活的界面把个性集中在第一次、完成、恢复这类时刻，其余时候靠可靠本身；重复一百次以后仍然不烦。
:::

## 代码位置

| 位置 | 职责 |
|---|---|
| ollupi-desktop `apps/desktop/PRODUCT.md` | 名字、读法、含义、定义句、标语 |
| ollupi-desktop `packages/ui/DESIGN.md` 第 0 节 | 标识、颜色、文件、姿势的用法 |
| ollupi-desktop `assets/brand/figure.py`、`poses.py` | 小狼的画法 |
| ollupi-desktop `assets/brand/make.py` | 生成全部标识、png、`Ollupi.icns`、总览图和 `wolfArt.ts` |
| ollupi-desktop `assets/brand/Ollupi.icns` | 打包进应用的图标（`electron-builder.yml` 的 `mac.icon`） |
| ollupi-desktop `apps/desktop/src/renderer/src/views/common/Wolf.tsx` | `Wolf`、`Emblem` 组件 |
| ollupi-desktop `apps/desktop/src/renderer/src/views/common/Wordmark.tsx` | 侧栏字标 |
