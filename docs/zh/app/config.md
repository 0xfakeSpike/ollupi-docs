# 配置与数据

Ollupi 的配置和数据都在本机的 `~/.ollupi`。大多数设置在应用的 **设置** 里改就行；这一页给想手写配置文件、或者想知道数据存在哪的人。配置在应用内部怎样校验和生效，见[配置的实现](/zh/desktop/config)。

这个目录可以用环境变量 `OLLUPI_HOME` 换到别处。

## 数据在哪

| 位置 | 内容 |
|---|---|
| `~/.ollupi/config.yaml` | 后端的配置：有哪些模型服务、它们的 API 密钥。所有身份共用这一份 |
| `~/.ollupi/profiles.json` | 有哪些身份，每个身份的名字和颜色 |
| `~/.ollupi/data` | 所有身份的会话、记忆、待办、技能和设置的数据库 |
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

`config.yaml` 不存在时，后端写入下面这份模板。它能直接运行，只是 `openai` 还没有密钥：在 **设置 → 模型** 里填上，或者换成别家的服务，见[安装与上手](/zh/app/install)。

```yaml
# Ollupi desktop backend. Restart the backend from the app after editing.
# This file is the same for every profile. Which model a profile starts and
# learns with, its permissions, MCP servers, skills, and whether memory is on
# are its own, set in the app.
name: ollupi

# Empty uses ollupi's default system prompt.
prompt: ""

# The models this backend serves, each provider an API account. Every profile
# runs on them and chooses which; a model is selected as provider/name. limits
# is the context window and the most an answer may take; calls caps
# concurrent requests to that model; images lets it receive images.
providers:
  - id: openai
    type: openai
    base_url: https://api.openai.com/v1
    api_key: ""
    models:
      - name: gpt-5.2
        images: true
        limits: { context: 400000, output: 128000 }

# How many threads may run at once (default 32).
# slots: 32
```

## 在应用里设置的

`config.yaml` 只写所有身份共用的东西。每个身份自己的选择由后端存在数据库里，在应用里改，保存后马上生效，不重启后端：

| 设置 | 在哪改 |
|---|---|
| 新会话默认用哪个模型 | **设置 → 模型**，点模型右边的星标。没选过的身份用第一个提供方的第一个模型 |
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
| 按身份写的模型：`models` 和 `memory.model`，或各带模型的 `profiles`，或 `credentials` | 所有身份用过的模型合并进 `providers`；每个身份原来的模型和学习模型变成它自己的选择，名字和颜色写进 `profiles.json`；原文件留一份 `config.yaml.pre-import` |
| `skills_dir` | 文件夹里的技能给每个已有身份，同名的合成一个、给原来有它的所有 agent（内容不同时以主 agent 那份为准），再去掉这一行；文件夹原样留在磁盘上，可以自己删 |
| `workspace` | 去掉这一块。命令和文件工具总是打开，见[顶层](#顶层)字段表下的说明 |

`permissions`、`mcp`、`memory.use` 和 `memory.generate` 不在自动处理之列。文件里还有它们时，后端会报字段不认识：删掉它们，再到应用里重新设置。

## 字段

表中"默认值"是不写这个字段时的行为，"模板"是首次生成的文件里的值。

### 顶层

| 字段 | 类型 | 默认值 | 模板 | 含义 |
|---|---|---|---|---|
| `name` | string | 必填 | `ollupi` | agent 的名字 |
| `prompt` | string | 空，用引擎默认的系统提示词 | `""` | 自定义提示词 |
| `providers` | list | 空 | 一个 `openai` | 模型服务和它们的模型，见下 |
| `tools` | string list | 不写时不限制 | 不写 | 引擎的工具白名单 |
| `slots` | int | `0`，取引擎默认的 32 | 注释掉 | 同时运行的会话数，不能为负 |

未知字段一律报错，比如写错的键。

命令和文件工具不在这个文件里配置：它们总是打开，命令只能写工作区、不能联网，默认 30 秒超时，单次最多 600 秒，见[沙箱](/zh/engine/sandbox)。

### providers

每项是一个提供方，也就是一个 API 账号。

| 字段 | 类型 | 默认值 | 含义 |
|---|---|---|---|
| `id` | string | 必填 | 提供方名称：1 到 64 个字符，前后不能有空格，不能含 `/`，不能重复 |
| `type` | string | 必填 | `openai`（任何 OpenAI 兼容 API）、`anthropic`、`gemini` |
| `base_url` | string | 该 API 的默认地址 | `openai` 要包含版本，如 `…/v1` |
| `api_key` | string | 空 | 写在文件里；API 不需要密钥时留空。`gemini` 必须填 |
| `models` | list | 必填，至少一个 | 这个提供方的模型，见下 |

### providers[].models {#models}

| 字段 | 类型 | 默认值 | 含义 |
|---|---|---|---|
| `name` | string | 必填 | API 识别的名称，同一提供方内不重复 |
| `calls` | int | `0`，取引擎默认的 4 | 对这个模型的最大并发请求数，不能为负 |
| `thinking` | bool | 不写时：`anthropic`、`gemini` 开启思考；`openai` 不发送这一项，由 API 自己决定 | 思考开关，`false` 关闭 |
| `images` | bool | `false` | 模型接受图片。引擎不给没有这个标记的模型发图片 |
| `limits.context` | int | 必填，大于 0 | 上下文窗口，token |
| `limits.output` | int | 必填，大于 0 | 一次回答的上限，token |
| `limits.input` | int | 不写时是窗口减去留给回答的部分（`output` 和窗口四分之一中较小的那个） | 模型的输入上限比这个小时填写 |

模型以 `提供方/模型名` 选择，比如 `openai/gpt-5.2`，所以两个提供方可以有同名的模型。改了提供方的名字，选过它的模型的身份要重新选。

要有至少一个模型，会话才能开始。在应用里删不掉最后一个模型。

### 改了文件之后

在 **设置 → 模型** 里保存的改动，应用先让后端检查，通过了才写进文件，然后直接交给正在运行的后端，不打断进行中的会话。

手改这个文件后要重启后端才生效。只改了模型时，**设置 → 模型** 会提示「config.yaml 中的模型与后端正在使用的不同。」，点旁边的 **重启后端**。改了其他字段，到 **设置 → 通用** 重启后端；有会话正在运行时，重启会打断正在执行的命令。
