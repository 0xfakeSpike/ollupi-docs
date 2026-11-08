# CLAUDE.md

## 站点结构

源文件按语言分成两棵树：`docs/en/` 和 `docs/zh/`，两边目录和文件名一一对应（`docs/en/engine/x.md` ↔ `docs/zh/engine/x.md`）。网址上英文为主：`docs/en/` 由 `config.ts` 的 `rewrites` 映射到站点根路径（`/engine/x`），中文在 `/zh/engine/x`。目录在 `docs/.vitepress/config.ts` 的 `sections` 里，一处写两种语言。

先写中文，中文定稿后再照着写英文。英文页还没写时，页首写明并链接中文版。

每篇文章是一个目录：`docs/en/articles/<slug>/index.md` 和 `docs/zh/articles/<slug>/index.md`，插图和正文放在同一个目录里，用相对路径引用（`![…](./fig-1-intro.svg)`）。构建时图片会带上内容哈希，引用的文件不存在时构建直接失败。`config.ts` 的 `rewrites` 把文章目录映射成 `/articles/<slug>`，网址不带结尾斜杠，已经发出去的链接不要改。两边用同一个 slug，页首互相链接，发布后在两边的 `articles/index.md` 和 `sections.articles` 里登记。

插图如果是脚本生成的，脚本放在 `scripts/figures/<slug>.py`，按语言输出到对应的文章目录（`python3 scripts/figures/<slug>.py zh`、`... en`），生成结果提交进仓库。只有需要固定网址的文件（favicon、logo、给外站引用的社交卡片图）才放 `docs/public/`。文章的分享卡片图放在 `docs/public/og/<slug>.png`（1200×630），在两种语言的 frontmatter 里写 `image: /og/<slug>.png`，`config.ts` 的 `transformHead` 据此生成 og 和 twitter 标签；源文件放 `scripts/figures/<slug>-og.svg`。

## 目录按读者分

| 目录 | 读者 | 写法 |
|---|---|---|
| `intro/` | 所有人 | 为什么、是什么，不出现代码标识符 |
| `app/` | 桌面端用户 | "我想做 X → 怎么做 → 会发生什么"，不讲内部机制，不出现代码标识符 |
| `integrate/` | 嵌入引擎的后端工程师 | 能跑的代码和参数表，每个参数写默认值和调大调小的后果 |
| `engine/`、`desktop/` | 同行、贡献者、评估者 | 一句话定位 → 为什么这样设计 → 机制 → 边界与已知问题 → 代码位置 |
| `benchmarks/`、`articles/`、`roadmap` | 评估者、所有人 | 见各自页面 |
| `reference/` | 查阅 | 术语表、设计决策、开发历程、从代码仓库同步的清单 |

同一件事只在一页里讲透，其他页用一两句话加链接带过。

## 术语

全站统一，第一次出现时括号注英文：agent（不译，"代理"只指网络代理）、子 agent、会话（thread）、轮次（turn，口语可说"一轮"）、条目（item）、槽位（slot）、分片（shard）、租约（lease）、宿主（host）、审批策略（严格 / 适中 / 宽松）、提权（escalation）。

## 引擎页面与引擎版本

`engine/`、`integrate/`、`benchmarks/`、`intro/concepts.md`（中英两份）描述的是某一个引擎版本，这个版本记在 `docs/.vitepress/engine.json`：

- `version`：页面最后一次逐页对照代码时的引擎 tag
- `protocolSha256`：那个 tag 下 `gateway/protocol.schema.json` 的 sha256（`git show <tag>:gateway/protocol.schema.json | sha256sum`），和网关 `initialize` 回报的 `protocolSha256` 是同一个值

构建时 `scripts/drift.mjs` 拿它和引擎仓库比对：引擎有了更新的 tag，或者协议契约变了，就在构建日志里警告，页面顶部也会提示读者这一页可能落后。`DOCS_STRICT=1 pnpm build` 会让构建直接失败。

把页面更新到新的引擎版本时：

1. 看 `git log <旧版本>..<新版本>`，逐个提交判断影响哪些页面。权限（`agent/permission`）、沙箱（`pkg/sandbox`）、协议（`gateway/protocol.go`）、`agent.Config` 的改动最容易让页面说反话。
2. 改页面，引用提交哈希和代码位置。
3. 页面都对上之后，再改 `engine.json` 的两个字段。没核对完就不要改，这个文件的意义就是"核对过"。

## 写法

- 只写能从提交、代码或仓库文档找到依据的内容；找不到依据的推断不写，或明确写成推断。
- 基准数字必须能对应到 `bench/results/` 或 `bench/README.md` 里的原始输出，写明测量条件；推不出的结论不写。
