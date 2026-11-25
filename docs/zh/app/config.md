# 配置与数据

Ollupi 的配置和数据都在本机的 `~/.ollupi`。大多数设置在应用的 **设置** 里改就行；这一页给想手写配置文件、或者想知道数据存在哪的人。配置在应用内部怎样校验和生效，见[配置的实现](/zh/desktop/config)。

这个目录可以用环境变量 `OLLUPI_HOME` 换到别处。

## 数据在哪

| 位置 | 内容 |
|---|---|
| `~/.ollupi/config.yaml` | 后端的名字、提示词、工具白名单和同时运行的会话数。所有身份共用这一份 |
| `~/.ollupi/profiles.json` | 有哪些身份，每个身份的名字和颜色 |
| `~/.ollupi/data` | 数据库：模型服务和它们的 API 密钥，以及所有身份的会话、记忆、待办、技能和设置 |
| `~/.ollupi/attachments` | 随消息发送的文件的副本 |
| `~/Library/Logs/Ollupi/backend.log` | 后端日志 |

这些路径都能在 **设置 → 通用** 里打开。

后端起不来时，界面会显示原因和后端日志，改好配置后点 **重启后端**。

## 目录结构

```
~/.ollupi/
├── config.yaml          后端的配置，权限 0600
├── profiles.json        身份列表：名字和颜色
├── data/
│   └── store.sqlite     数据库，旁边有 -shm 和 -wal
├── attachments/         随消息发送的图片和文件的副本
├── scratch/             不属于工作区的会话的命令在这里执行
└── users/
    └── <身份>/           这个身份自己的文件，MCP 服务器在这里运行
        └── super-agent/ 这个身份的 Super Agent 的文件夹
```

默认身份的 Super Agent 文件夹也可能直接在 `~/.ollupi/super-agent`。以侧边栏 Super Agent 菜单里 **打开文件夹** 打开的为准。

沙箱对这个目录有专门的规则：`config.yaml` 和 `data/` 不可读，命令读不到 API 密钥和数据库。

应用自己的数据在 macOS 的标准位置，不在这个目录：

| 位置 | 内容 |
|---|---|
| `~/Library/Logs/Ollupi/backend.log` | 后端日志，超过 10 MB 时换新文件，上一份是 `backend.log.old` |
| `~/Library/Application Support/Ollupi/profile.json` | 这台 Mac 上的窗口用哪个身份 |
| `~/Library/Application Support/Ollupi/remote.json` | 连接另一台机器上的后端时的地址和密钥，加密保存 |
| `~/Library/Application Support/Ollupi/bookmarks.json` | 浏览器收藏 |
| `~/Library/Application Support/Ollupi/history.json` | 浏览器历史 |
| `~/Library/Application Support/Ollupi/Partitions/browser` | 内置浏览器的 Cookie 和登录状态 |
| `~/Library/Application Support/Ollupi/update` | 下载的更新，启动时清空 |
| `<系统临时目录>/Ollupi/attachments` | 待发送的粘贴文件，启动时清空 |

配色、语言、通知开关和面板宽度在渲染进程的 `localStorage` 里，见 [渲染进程](/zh/desktop/renderer)。

## 首次启动

`config.yaml` 不存在时，后端写入下面这份模板：

```yaml
# Ollupi desktop backend. Restart the backend from the app after editing.
# This file is the same for every profile. The models are not in it: they
# are set in the app, under Settings → Models. Which model a profile starts
# and learns with, its permissions, MCP servers, skills, and whether memory
# is on are its own, set in the app.
name: ollupi

# Empty uses ollupi's default system prompt.
prompt: ""

# How many threads may run at once (default 32).
# slots: 32
```

新安装的后端还没有模型。打开 **设置 → 模型** 添加一个模型服务，填上 API 密钥，就能开始会话，见[安装与上手](/zh/app/install)。

## 模型和 API 密钥 {#models}

模型服务（提供方）、它们的模型和 API 密钥都在 **设置 → 模型** 里添加和修改，存在后端的数据库里，不在 `config.yaml` 里。所有身份共用这一份模型列表：

| 想做的事 | 怎么做 | 会发生什么 |
|---|---|---|
| 添加一个模型服务 | **添加提供方**，选 API 类型，填 Base URL 和密钥，从拉到的列表里选模型 | 保存后马上能用，不重启后端 |
| 改密钥、地址或模型的设置 | 编辑这个提供方或模型 | 新的一轮马上用上；正在调用模型的那一轮用原来的设置跑完 |
| 删除提供方或模型 | 卡片上的删除 | 选过它的身份要重新选。删不掉最后一个模型 |
| 选本身份新会话默认用哪个模型 | 点模型右边的星标 | 只影响这个身份。没选过的身份用第一个提供方的第一个模型 |

每个模型能设的几项：

| 项 | 不填时 | 含义 |
|---|---|---|
| 并发调用 | 4 | 同时最多向这个模型发几个请求，所有身份共用这个上限 |
| 思考 | Anthropic、Gemini 开启；OpenAI 兼容的不发送这一项，由服务自己决定 | 是否请求模型的思考 |
| 支持图片 | 关 | 关着时不给这个模型发图片 |
| Token 上限：上下文 | 必填 | 模型的上下文窗口 |
| Token 上限：输出 | 必填 | 一次回答最多多少 token |
| Token 上限：最大输入 | 窗口减去留给回答的部分（输出和窗口四分之一中较小的那个） | 模型的输入上限比这个小时填写 |

提供方的名字不能含 `/`，也不能和别的重名，因为模型按 `提供方/模型名` 区分，比如 `openai/gpt-5.2`。Gemini 必须填密钥。保存时后端会检查，不通过就提示原因，原来的设置不变。

### 连接另一台机器上的后端时

在 **设置 → 连接** 里连到另一台机器上的后端时，能不能改模型取决于填的 token：

- 填的是那台机器的运营者 token（`OLLUPI_OPERATOR_TOKEN` 加 `.<身份>`）：和本机一样能添加、修改模型。
- 填的是普通的网关 token（`OLLUPI_GATEWAY_TOKEN` 加 `.<身份>`）：**设置 → 模型** 显示「这个连接只能从已有的模型里选。添加和修改模型由后端的运营者来做。」，只能点星标选默认模型。

连本机的后端时，应用自己就是运营者，不用填 token。

## 在应用里设置的

`config.yaml` 只写所有身份共用的东西。每个身份自己的选择由后端存在数据库里，在应用里改，保存后马上生效，不重启后端：

| 设置 | 在哪改 |
|---|---|
| 新会话默认用哪个模型 | **设置 → 模型**，点模型右边的星标 |
| 学习记忆用哪个模型 | **记忆 → 全局**，见[定时任务与记忆](/zh/app/automation#设置) |
| 记忆开关、从会话中学习 | **记忆 → 全局** |
| 所有会话默认的审批策略和例外规则 | **设置 → 权限**，见[审批与权限](/zh/app/permissions#选一档审批策略) |
| MCP 服务器 | **能力 → MCP**，见[技能、MCP 与工具](/zh/app/capabilities#mcp) |
| 技能和给哪些 agent | **能力 → 技能**，见[技能、MCP 与工具](/zh/app/capabilities#技能) |

身份本身在 **设置 → 身份** 里新建、改名、换颜色和删除，列表写在 `~/.ollupi/profiles.json`。这台 Mac 当前用哪个身份，记在应用自己的 `profile.json` 里。

## 升级时自动处理的

应用每次启动时，先检查 `config.yaml` 里有没有旧版本留下的写法，有就改成现在的样子，其余内容和注释原样保留：

| 旧文件里有 | 启动时怎么处理 |
|---|---|
| `workspace` | 去掉这一块。命令和文件工具总是打开，见[字段](#字段)下的说明 |
| 按身份写的模型：`models` 和 `memory.model`，或各带模型的 `profiles`，或 `credentials` | 所有身份用过的模型合并进数据库里的模型列表；每个身份原来的模型和学习模型变成它自己的选择，名字和颜色写进 `profiles.json`；原文件留一份 `config.yaml.pre-import` |
| `providers` | 整个搬进数据库，换掉数据库里原有的模型列表，再从文件里去掉。密钥从此不在文件里 |
| `skills_dir` | 文件夹里的技能给每个已有身份，同名的合成一个、给原来有它的所有 agent（内容不同时以主 agent 那份为准），再去掉这一行；文件夹原样留在磁盘上，可以自己删 |

`permissions`、`mcp`、`memory.use` 和 `memory.generate` 不在自动处理之列。文件里还有它们时，后端会报字段不认识：删掉它们，再到应用里重新设置。

## 字段

表中"默认值"是不写这个字段时的行为，"模板"是首次生成的文件里的值。

| 字段 | 类型 | 默认值 | 模板 | 含义 |
|---|---|---|---|---|
| `name` | string | 必填 | `ollupi` | agent 的名字 |
| `prompt` | string | 空，用引擎默认的系统提示词 | `""` | 自定义提示词 |
| `tools` | string list | 不写时不限制 | 不写 | 引擎的工具白名单 |
| `slots` | int | `0`，取引擎默认的 32 | 注释掉 | 同时运行的会话数，不能为负 |

未知字段一律报错，比如写错的键。

命令和文件工具不在这个文件里配置：它们总是打开，命令只能写工作区、不能联网，默认 30 秒超时，单次最多 600 秒，见[沙箱](/zh/engine/sandbox)。

这个文件只在后端启动时读。改完到 **设置 → 通用** 重启后端；有会话正在运行时，重启会打断正在执行的命令。
