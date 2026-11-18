# 配置与数据

Ollupi 的配置和数据都在本机的 `~/.ollupi`。大多数设置在应用的 **设置** 里改就行；这一页给想手写配置文件、或者想知道数据存在哪的人。配置在应用内部怎样校验和生效，见[配置的实现](/zh/desktop/config)。

这个目录可以用环境变量 `OLLUPI_HOME` 换到别处。

## 数据在哪

配置和数据都在本机的 `~/.ollupi`：

| 位置 | 内容 |
|---|---|
| `~/.ollupi/config.yaml` | 配置，API 密钥也在这里 |
| `~/.ollupi/data` | 会话和记忆的数据库 |
| `~/.ollupi/attachments` | 随消息发送的文件的副本 |
| `~/.ollupi/skills` | 技能 |
| `~/Library/Logs/Ollupi/backend.log` | 后端日志 |

这些路径都能在 **设置 → 通用** 里打开。

后端起不来时，界面会显示原因和后端日志，改好配置后点 **重启后端**。

想在手机上用，看[飞书机器人](/zh/app/feishu)。

## 目录结构

```
~/.ollupi/
├── config.yaml        配置，权限 0600
├── data/
│   ├── ollupi.sqlite  引擎的数据库，旁边有 -shm 和 -wal
│   └── feishu.json    飞书话题和会话的对应
├── attachments/       随消息发送的图片和文件的副本
├── skills/            技能文件夹，skills_dir 指向这里
└── scratch/           不属于工作区的会话的命令在这里执行
```

沙箱对这个目录有专门的规则：`config.yaml` 和 `data/` 不可读，命令读不到 API 密钥和数据库；技能文件夹只读。

应用自己的数据在 macOS 的标准位置，不在这个目录：

| 位置 | 内容 |
|---|---|
| `~/Library/Logs/Ollupi/backend.log` | 后端日志，上一份是 `backend.log.old` |
| `~/Library/Application Support/Ollupi/bookmarks.json` | 浏览器收藏 |
| `~/Library/Application Support/Ollupi/history.json` | 浏览器历史 |
| `~/Library/Application Support/Ollupi/Partitions/browser` | 内置浏览器的 Cookie 和登录状态 |
| `~/Library/Application Support/Ollupi/update` | 下载的更新，启动时清空 |
| `<系统临时目录>/Ollupi/attachments` | 待发送的粘贴文件，启动时清空 |

配色、语言、通知开关和面板宽度在渲染进程的 `localStorage` 里，见 [渲染进程](/zh/desktop/renderer)。

## 首次启动

`config.yaml` 不存在时，sidecar 先写入自带技能，再写入模板。模板是可运行的最小配置，带注释说明。权限、MCP 服务器和记忆、学习两个开关不在这个文件里，见[在应用里设置的](#在应用里设置的)。

```yaml
name: ollupi
prompt: ""

models:
  - provider: openai
    type: openai
    base_url: https://api.openai.com/v1
    api_key: ""
    names:
      - name: gpt-5.2
        images: true
        limits: { context: 400000, output: 128000 }

workspace:
  enabled: true
  sandbox_mode: workspace-write # read-only | workspace-write | full-access
  command_timeout_sec: 60
  network: false

skills_dir: skills

# memory:
#   model: openai/gpt-5.2
```

## 在应用里设置的

这几项由后端自己保存，不写进 `config.yaml`，在应用里改，保存后马上生效，不重启后端：

| 设置 | 在哪改 |
|---|---|
| 所有会话默认的审批策略和例外规则 | **设置 → 权限**，见[审批与权限](/zh/app/permissions#选一档审批策略) |
| MCP 服务器 | **能力 → MCP**，见[技能、MCP 与工具](/zh/app/capabilities#mcp) |
| 记忆开关、从会话中学习 | **记忆 → 全局**，见[定时任务与记忆](/zh/app/automation#设置) |

从 0.7.53 之前的版本升级时，`config.yaml` 里的 `permissions`、`mcp`、`memory.use` 和 `memory.generate` 在第一次启动时自动搬进应用，再从文件里删掉，不用手改。`permissions` 只在你还没在应用里设过权限时才搬；`mcp` 里写成 `${NAME}` 的值，会换成那时登录 shell 里这个变量的值。

## 字段

表中"默认值"是不写这个字段时的行为，"模板"是首次生成的文件里的值。

### 顶层

| 字段 | 类型 | 默认值 | 模板 | 含义 |
|---|---|---|---|---|
| `name` | string | 必填 | `ollupi` | agent 的名字 |
| `prompt` | string | 空，用引擎默认的系统提示词 | `""` | 自定义提示词 |
| `models` | list | 必填，至少一个模型 | 见下 | 提供方和模型 |
| `tools` | string list | 不写时不限制 | 不写 | 引擎的工具白名单 |
| `slots` | int | `0`，取引擎默认的 32 | 注释掉 | 同时运行的轮次数，不能为负 |
| `workspace` | object | `enabled` 为假 | 见下 | 命令和文件工具 |
| `memory` | object | 不学习新记忆 | 注释掉 | 学习记忆用的模型 |
| `skills_dir` | string | 空，关闭技能 | `skills` | 技能文件夹，相对路径基于 home |
| `feishu` | object | 不启用 | 注释掉 | 飞书机器人 |

未知字段一律报错，比如写错的键，或旧版本的 `settings`。

### models

每项是一个提供方，也就是一个 API。

| 字段 | 类型 | 默认值 | 含义 |
|---|---|---|---|
| `provider` | string | 必填 | 提供方名称，不能含 `/`，不能重复 |
| `type` | string | 必填 | `openai`（任何 OpenAI 兼容 API）、`anthropic`、`gemini` |
| `base_url` | string | 该 API 的默认地址 | `openai` 要包含版本，如 `…/v1` |
| `api_key` | string | 空 | 写在文件里；API 不需要密钥时留空 |
| `names` | list | 必填，至少一个 | 模型 |

`names` 的每项：

| 字段 | 类型 | 默认值 | 含义 |
|---|---|---|---|
| `name` | string | 必填 | API 识别的名称，同一提供方内不重复 |
| `calls` | int | `0`，取引擎默认的 4 | 对这个模型的最大并发请求数，不能为负 |
| `thinking` | bool | 不写时不发送，用 API 默认 | 思考开关 |
| `images` | bool | `false` | 模型接受图片。引擎拒绝给没有这个标记的模型发图片 |
| `limits.context` | int | 必填 | 上下文窗口，token |
| `limits.output` | int | 必填 | 一次回答的上限，token |
| `limits.input` | int | 不写时按窗口算 | 模型的输入比窗口剩余的小时填写 |

模型以 `provider/name` 选择，这也是引擎的连接 ID。两个提供方可以有同名模型。顺序有意义：第一个提供方的第一个模型是默认模型。

### workspace

`enabled` 打开 `run_command`、`edit_file`、`write_file`，其余字段是引擎 `workspace.Config` 的 json 标签，直接平铺在这一层。沙箱行为见 [沙箱](/zh/engine/sandbox)。

| 字段 | 类型 | 默认值 | 模板 | 含义 |
|---|---|---|---|---|
| `enabled` | bool | `false` | `true` | 开关 |
| `workspace_dirs` | string list | 空，用 `<home>/scratch` | 不写 | 命令目录，相对路径基于 home |
| `command_timeout_sec` | int | 30 | 60 | 命令默认超时，秒 |
| `max_command_timeout_sec` | int | `max(600, command_timeout_sec)` | 不写 | 单次命令超时上限，不能小于默认超时 |
| `command_blacklist` | string list | 空 | 不写 | 匹配到时拒绝执行 |
| `sandbox_mode` | string | `workspace-write` | `workspace-write` | `read-only`、`workspace-write`、`full-access` |
| `network` | bool | `false` | `false` | 沙箱内是否可联网 |
| `allowed_domains` | string list | 空 | 不写 | 网络走代理，只放行这些域名 |
| `denied_domains` | string list | 空 | 不写 | 必须和 `allowed_domains` 一起用 |
| `deny_read` | string list | 空 | 不写 | 额外的不可读路径 |
| `read_only` | string list | 空 | 不写 | 额外的只读路径 |
| `extra_writable` | string list | 空 | 不写 | 额外的可写路径 |
| `unix_sockets` | string list | 空 | 不写 | 允许访问的 Unix 套接字 |
| `env_passthrough` | string list | 空 | 不写 | 透传给命令的环境变量名 |
| `max_output_bytes` | int | 1 MiB | 不写 | 命令输出上限，不能为负 |

### memory

| 字段 | 类型 | 默认值 | 模板 | 含义 |
|---|---|---|---|---|
| `model` | string | 空，不学习新记忆 | 注释掉 | 从结束的轮次学习记忆的模型，`provider/name`，必须是 `models` 里的一个。它和这个模型共用 `calls` |

记忆和学习的开关在记忆页，任一个关着时这个模型都不学习。在记忆页换模型会改写这一项并重启后端，见[定时任务与记忆](/zh/app/automation#设置)。

### feishu

存在这一节就启用机器人。行为见 [飞书机器人](/zh/desktop/feishu-bot)，开放平台的步骤见 [飞书配置](/zh/app/feishu)。

| 字段 | 类型 | 默认值 | 含义 |
|---|---|---|---|
| `app_id` | string | 必填 | 自建应用的 App ID |
| `app_secret` | string | 必填 | App Secret，写在文件里 |
| `domain` | string | `feishu` | `feishu`（open.feishu.cn）或 `lark`（open.larksuite.com） |
| `users` | string list | 空 | 机器人为谁操作，`open_id` 名单 |
| `workspace` | string | 空 | 飞书开始的会话所在工作区的文件夹 |

