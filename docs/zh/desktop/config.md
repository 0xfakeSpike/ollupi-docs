# 配置的实现

桌面端的配置分在三处，字段说明见[配置与数据](/zh/app/config)：

| 在哪 | 放什么 | 谁改 |
|---|---|---|
| `~/.ollupi/config.yaml` | 部署的名字、提示词、工具白名单、槽位 | 手改文件，重启后端生效 |
| 引擎 store 里的模型目录（catalog） | 提供方、它们的模型和 API 密钥，所有身份共用 | 运营者经网关 `catalog/set` 整份替换，马上生效 |
| 引擎 store 里每个用户的数据 | 新会话默认的模型、学记忆的模型、权限、MCP 服务器、技能、记忆开关 | 这个身份自己，经网关改，马上生效 |

身份列表 `~/.ollupi/profiles.json` 不属于其中任何一处：本机部署里应用是身份提供方，列表是主进程的，后端不读。

## 为什么这样设计

引擎是多租户的：模型目录和密钥归部署的运营者，所有用户共用；用户只在目录里选。把目录放进 store、经网关读写，桌面端和服务器部署就是同一套做法：本机的应用以运营者身份连接，远端的后端也一样，只要拿着运营者的 token。改目录不重启后端，不打断正在跑的命令；文件和运行中的后端也不会再对不上，因为已经没有一份要和后端对照的文件。

剩在 `config.yaml` 里的四项只在启动时取一次，改动本来就要重启，留在文件里可以用编辑器、`cp`、git 管理。这个包"只描述，`host` 把它变成运行中的组件"，写在 `internal/config` 的包注释里。

## 文件里有什么

| 键 | 含义 | 默认或要求 |
|---|---|---|
| `name` | 部署的名字，引擎用它在 MCP 握手和日志里标识自己 | 必填，不能为空白 |
| `prompt` | 系统提示 | 省略时用引擎的默认系统提示 |
| `tools` | 工具白名单 | 省略即全部放开 |
| `slots` | 同时跑多少会话 | 省略用引擎默认的 32，不能为负 |

`config.Parse` 把 YAML 转成 JSON 后用 `DisallowUnknownFields` 解码，拼错的键报错而不是被忽略；`Config.Validate` 查 `name` 和 `slots`。`LoadFile` 在解析之前还会先看文件里有没有旧版本的键（按身份写的模型、`providers`、`skills_dir`、`workspace`），有就直接拒绝，错误里写明运行 `ollupid --import-config`，而不是报一个让人看不懂的"未知字段"。

主进程不读也不写这个文件。应用里没有编辑它的界面，手改后到设置 → 通用重启后端；有轮次在跑时，`domains/restart.ts` 的 `confirmRestart` 先问。

命令和文件工具（`run_command`、`edit_file`、`write_file`）也不在文件里：它们总是打开，沙箱用引擎 `workspace.Config` 的默认值，工作区可写、不联网、命令默认 30 秒超时（单次最多 600 秒），工作目录是 `<home>/scratch`。桌面端在此之外加两条：`config.yaml` 和 `<home>/data` 禁止读，命令读不到 API 密钥和数据库；环境变量标记是 `OLLUPI_SANDBOX`。引擎自己再让 `AGENTS.md`、`CLAUDE.md`、`.mcp.json` 这类文件名受保护。

::: info 演进
0.7.53 之前，默认权限、MCP 服务器和记忆的两个开关都写在 `config.yaml` 里，改它们也要重启后端；0.7.53 跟进引擎 v0.17.1 把它们搬进 store（`desktop@795ac1d`）。0.8.17-beta.5 把按身份写模型的键换成部署共用的 `providers`（`desktop@1c7ccf0`），界面改它时先用 `ollupid --check-config` 校验候选文件，再 SIGHUP 让后端重载。v0.31.0 让技能进 store，`skills_dir` 去掉（`desktop@41ea52e`）；之后 `workspace` 块也去掉了（`desktop@274e778`）。引擎 v0.32.0 把模型目录搬进 store，`providers` 离开文件，`--check-config`、`--config-schema`、`host.Check`、SIGHUP 重载和文件与后端的不一致检测一起去掉（`desktop@8033b6d`）。旧文件里的这些键都由 `--import-config` 在启动时拆掉，见[旧文件的导入](#旧文件的导入)。
:::

## 模型目录

目录存在 store 的 `providers` 和 `provider_models` 两张表里（引擎迁移 0021），按位置排序：没选过模型的用户用第一个提供方的第一个模型。后端启动时读目录，目录变了就换上新的模型客户端，正在调用模型的轮次用旧客户端跑完。

网关上的方法和通知：

| 名字 | 谁能用 | 做什么 |
|---|---|---|
| `catalog/read` | 运营者 | 读整份目录，带密钥和 `seq` |
| `catalog/set` | 运营者 | 整份替换。用户连接回 `forbidden`（-32022）；引擎的 `account.CheckCatalog` 不通过回 `invalidParams`，目录不变 |
| `catalog/changed` | 发给运营者连接 | 目录换了，带整份目录和 `seq` |
| `model/list` | 所有连接 | 目录展开的模型（不带密钥）、这个用户的默认模型、`seq` |
| `model/changed` | 发给所有连接 | 目录换了之后，这个用户能选的模型和现在的默认：`{data, default, seq}`。用户自己改选择不发这个，界面在设置变了时重读 `model/list` |

目录的每一项：

| 字段 | 含义 | 要求 |
|---|---|---|
| `id` | 提供方名字。模型按 `id/name` 选择，这也是引擎的连接 ID | 1 到 64 个字符，前后无空格，不带 `/`，不重复 |
| `api` | `openai`（任何 OpenAI 兼容接口）、`anthropic`、`gemini` | 三种之一 |
| `baseUrl` | API 地址 | 省略时用客户端的默认地址 |
| `apiKey` | API 密钥 | 不需要密钥的接口可省；`gemini` 必填 |
| `models[].name` | 模型名 | 必填，同一提供方内唯一；每个提供方至少一个模型 |
| `models[].calls` | 这个模型同时最多几个请求，所有用户共用 | 省略用 4，不能为负 |
| `models[].thinking` | 是否请求思考；OpenAI 兼容接口据此发 `enable_thinking` | `anthropic`、`gemini` 省略为开；`openai` 省略时不发 |
| `models[].images` | 模型接受图片，为假时引擎不发图片给它 | 省略为假 |
| `models[].limits` | `context`、`output`、可选的 `input` | `context`、`output` 为正，`input` 不为负 |

## 运营者和身份

sidecar 启动时要两个密钥，`OLLUPI_GATEWAY_TOKEN` 和 `OLLUPI_OPERATOR_TOKEN`，两个都要有，而且不能相同，否则每个用户都成了运营者。连接的 token 是 `<密钥>.<身份>`：

| token | 连上来是 |
|---|---|
| `<网关密钥>.<身份>` | 这个身份 |
| `<运营者密钥>.<身份>` | 这个身份，同时是运营者 |

`host.profileOf` 用常量时间比较认出是哪个密钥，返回 `auth.Identity{User, Operator}`；store 里还没有这个用户时当场建出来，给它自带的技能。

本机的后端由 supervisor 启动：每次启动生成两个随机密钥，交给渲染进程的是 `<运营者密钥>.<身份>`，所以本机的应用就是运营者；网关密钥不交给任何人。连另一台机器上的后端时，设置 → 连接里填什么 token，就是什么身份：填运营者 token 能改模型目录，填普通 token 只能在目录里选。远端怎么配这两个密钥，见 ollupi-desktop 仓库的 `docs/remote-mac-mini.md`。

## 界面怎么改模型

- `domains/catalog.ts` 在每次连接时 `snapshot('catalog/read', {}, ['catalog/changed'])`，按 `seq` 合并晚到的通知。回 `forbidden` 时记下 `operator: false`，不报错。`saveCatalog` 用 `catalog/set` 整份写回，被拒时提示原因，目录不变。
- `domains/providers.ts` 的每个编辑（加提供方、改模型、删除……）都返回改完后的整份目录，不碰文件。规则跟引擎一致：提供方带着模型一起加；删掉最后一个模型就删掉这个提供方；不能删目录里的最后一个模型（`cannotRemove`、`cannotRemoveProvider` 返回 `lastModel`）。改提供方的名字会改掉它所有模型的连接 ID，选过它们的身份要重新选，删除和改名前的确认里会说。
- `domains/models.ts` 读 `model/list`，再跟着 `model/changed`。
- 设置 → 模型（`ModelsSection.tsx`）：运营者连接显示可编辑的提供方卡片，保存后马上生效；非运营者连接显示一条说明和模型列表，只能点星标。星标是这个身份的 `settings/update` 的 `model`，不改目录。

## 旧文件的导入

应用每次启动时，在选身份之前运行一次 `ollupid --import-config`（`BackendConfig.importOlder`，同一次启动里只跑一次）。每一步都能重复运行，导入中途断了，下次启动接着做完。四步依次是：

| 步骤 | 处理什么 | 做法 |
|---|---|---|
| `dropWorkspace` | `workspace` 块 | 从文件里去掉，不保留任何值 |
| `runImport` | 按身份写模型的旧键（`config.Legacy`） | 所有身份用过的模型合并成一份目录，直接写进 store；每个身份变成 store 里的用户，`settings` 里记下原来的模型和学习模型；身份写进 `profiles.json`，名字和颜色取自文件或 `--names` 给的应用旧 `profiles.json`；原文件存为 `config.yaml.pre-import` |
| `importProviders` | `providers`（`config.Providers`） | 按 `CheckCatalog` 检查后用 `SetCatalog` 整份写进 store，再从文件里去掉 |
| `importSkills` | `skills_dir` | 读文件夹里各角色的技能，同名的合成一个、给所有有它的角色，内容不同时以主 agent 那份为准，写给 store 里的每个用户；去掉这一行，文件夹留着 |

输出是一行 JSON，比如 `{"ok":true,"workspace":true,"providers":["openai"]}`，没做的步骤不出现。

去掉一个键用的是 `config/older.go` 的 `takeKey`：在 `yaml.Node` 树上删掉这个键和它的值，其余节点和注释原样写回。`yaml.v3` 把一个键上方的所有注释段落都算作这个键的 `HeadComment`，段落之间隔着空行，所以只有最后一段是在说这个键的。`takeKey` 删键时只带走最后一段，前面的段落挪到下一个键上方，没有下一个键时挪到文件末尾。比如 `providers` 前面那段说明会跟着它走，而它下面 `# slots: 32` 那段注释留在原处。

## 技能

技能不在 `config.yaml` 里，也不在哪个文件夹里：每个身份的技能存在引擎的 store 里，渲染进程经网关读写（`skill/list`、`skill/read`、`skill/set`、`skill/delete`），`skill/changed` 把改动推给每个窗口。引擎在 `skill/set` 时检查技能，不通过就回 `invalidParams`，界面把原因显示在对话框里；agent 每一步开始时重读技能，所以改完不用重启。

主进程只做一件事：导入时让用户选一个文件夹，交给 `ollupid --read-skill` 读成字段，原样还给渲染进程（`BackendSkills.read`）。读 `SKILL.md` 的是 sidecar，和随应用发布的技能同一个读法，见 [sidecar 的技能](/zh/desktop/sidecar#技能)。

::: info 演进
引擎 v0.31.0 之前，技能是 `config.yaml` 的 `skills_dir` 指向的文件夹，按角色分目录，所有身份共用。主进程在文件夹里暂存改动，用 `ollupid --check-skills` 检查后 `rename` 进去，删除走回收站，复制给另一个 agent 是复制一份文件夹。v0.31.0 把技能搬进 store、改成每个用户自己的，桌面端跟着去掉了文件夹和这套暂存流程（`desktop@41ea52e`），旧文件夹里的技能由 `--import-config` 一次性搬进去。
:::

## config:generate

渲染进程需要知道 `--read-skill` 输出的类型，而这份类型由 Go 定义。`pnpm config:generate` 让 TypeScript 类型从 Go 生成，不手写第二份：

| 目标文件 | 类型名 | 来自 | 描述 |
|---|---|---|---|
| `src/shared/generated/backend-skills.ts` | `SkillFolder` | `ollupid --skill-schema` | `--read-skill` 的输出 |

过程：

1. `apps/desktop/scripts/generate-config.mjs` 在 `sidecar/` 里执行 `go run -tags sqlite_fts5 ./cmd/ollupid <flag>`。
2. sidecar 用 `jsonschema.For[T]` 从 Go 类型得到 JSON Schema，字段名来自 json 标签。
3. `json-schema-to-typescript` 编译成 TypeScript，写上 `DO NOT EDIT` 的头。

`pnpm config:check` 比较现有文件和生成结果，过期时失败。模型目录的类型（`ModelProviderRow`、`ProviderModel`）来自引擎的协议契约，在 `@ollupi/protocol` 里，不经过这一步。

## 边界与已知问题

- API 密钥明文存在 `<home>/data/store.sqlite` 里，没有进 Keychain。沙箱里的命令读不到 `data/`，但数据库文件的权限是 0644，同一台 Mac 上的其他系统用户读得到；`config.yaml` 是 0600，现在里面已经没有密钥。
- `name`、`prompt`、`tools`、`slots` 只能手改文件，改完要重启后端，界面看不出文件和运行中的后端是否一致。
- `--import-config` 只认得上面四类旧键。0.7.53 之前的 `permissions`、`mcp`、`memory.use`、`memory.generate` 不在导入之列，文件里还有它们时后端以未知字段拒绝启动，要手动删掉。

## 代码位置

| 仓库 | 路径 | 职责 |
|---|---|---|
| ollupi-desktop | `sidecar/internal/config/config.go` | 类型、`Parse`、`Validate`、`Load`/`LoadFile`、首次写入 |
| ollupi-desktop | `sidecar/internal/config/template.go` | 首次启动写入的模板 |
| ollupi-desktop | `sidecar/internal/config/legacy.go` | 按身份写模型的旧文件（`Legacy`） |
| ollupi-desktop | `sidecar/internal/config/older.go` | `Providers`、`SkillsDir`、`Workspace` 和它们共用的 `takeKey` |
| ollupi-desktop | `sidecar/cmd/ollupid/main.go` | 两个密钥、各种模式的入口 |
| ollupi-desktop | `sidecar/cmd/ollupid/import.go` | `--import-config`：`dropWorkspace`、`runImport`、`importProviders`、写 `profiles.json` |
| ollupi-desktop | `sidecar/cmd/ollupid/skills.go` | `importSkills`，`--read-skill`、`--skill-schema` 的输出类型 |
| ollupi-desktop | `sidecar/internal/host/host.go` | `New` 里的装配和工作区沙箱，`profileOf` |
| ollupi-desktop | `apps/desktop/src/main/backend/config.ts` | `BackendConfig`：`importOlder`、`deleteProfile` |
| ollupi-desktop | `apps/desktop/src/main/backend/supervisor.ts` | 生成两个密钥，给渲染进程运营者 token |
| ollupi-desktop | `apps/desktop/src/main/backend/skills.ts` | 导入时用 `--read-skill` 读一个技能文件夹 |
| ollupi-desktop | `apps/desktop/src/main/profile.ts` | `profiles.json` 和这台 Mac 的选择 |
| ollupi-desktop | `apps/desktop/scripts/generate-config.mjs` | 类型生成 |
| ollupi-desktop | `apps/desktop/src/renderer/src/domains/catalog.ts` | `catalog/read`、`catalog/changed`、`saveCatalog` |
| ollupi-desktop | `apps/desktop/src/renderer/src/domains/providers.ts` | 目录改动的规则 |
| ollupi-desktop | `apps/desktop/src/renderer/src/domains/models.ts` | `model/list`、`model/changed` |
| ollupi-desktop | `apps/desktop/src/renderer/src/domains/restart.ts` | 重启前确认 |
| ollupi-desktop | `apps/desktop/src/renderer/src/views/settings/ModelsSection.tsx` | 模型编辑，非运营者只能选 |
| ollupi-desktop | `apps/desktop/src/renderer/src/domains/skills.ts` | 技能列表跟着 `skill/changed`，`skill/read`、`skill/set`、`skill/delete` |
| ollupi | `account/models.go` | `ProviderModel`、`CheckCatalog` |
| ollupi | `store/sqlite/migrations/0021_catalog.sql` | 目录的两张表 |
| ollupi | `pkg/llm/limits.go` | `limits` 的含义与取值检查 |
| ollupi | `tool/builtin/workspace/config.go` | 工作区工具的默认值和沙箱配置 |
