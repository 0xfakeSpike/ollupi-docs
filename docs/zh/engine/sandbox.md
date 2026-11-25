# 沙箱

沙箱决定模型的命令和文件操作能碰到什么。工具经 `sandbox.Box` 运行命令、读写文件；部署提供的每种沙箱是一个提供者（`sandbox.Provider`），用户的每个执行环境（environment）是某个提供者的一个沙箱。本机是其中一种提供者（`sandbox.Local`），它的 Box 是 `pkg/sandbox` 的 `Sandbox`，用 macOS Seatbelt（用 `sandbox-exec` 加一段规则跑进程）；云沙箱照同样的接口接入，它的机器由 `Remote` 包成 `Box`。权限决定要不要问用户，沙箱决定放行之后能做什么，见[审批与权限](/zh/engine/permissions)。

## 为什么这样设计

- **工具只经 `Box` 碰机器。** 命令、文件、附件、stdio MCP 服务器都走这个接口，本机与云沙箱是它的两种实现，见[设计决策 1](/zh/reference/decisions#_1-池化-runtime)。
- **本机和云沙箱是同一种提供者。** 引擎只认 `Provider`：建沙箱、找回沙箱、删沙箱都由提供者做，引擎记下它留的状态。接一家云沙箱就是写一个提供者，不用改工具，宿主也不用自己记"哪个环境对应哪台机器"。
- **用 Seatbelt。** 虚拟机隔离更强，但里面是 Linux，用不了 macOS 工具链；基础规则取自 OpenAI Codex，代理、拒绝日志和保护名参照 Anthropic 的 sandbox-runtime，见[设计决策 20](/zh/reference/decisions#_20-seatbelt-沙箱)。
- **挡住之后会被别的程序执行的文件。** 逃逸多是写钩子配置、git config 这类文件，不是攻破沙箱，所以保护名在可写目录的任意层级都不可写；`.git` 例外，否则 `git init`、`git clone` 在沙箱里必然失败。

## Box 接口

| 方法 | 作用 |
| --- | --- |
| `Run`、`Start` | 运行到结束；`Start` 跑 stdio MCP 服务器，直到 `ctx` 结束或 `Process` 关闭 |
| `Stat`、`ReadDir`、`Open`、`WriteFile`、`Move`、`Canonical`、`Directory`、`Executable`、`Same` | 按 Box 自己的路径读写、搬动、规范化与解析程序；整文件读取走 `sandbox.ReadFile(ctx, box, path, limit)` |
| `Enforced`、`CanEscalate`、`Summary`、`Roots`、`Fingerprint` | 命令是否受限、能否给全权、写进系统提示词的规则、命令目录、规则指纹 |
| `Check`、`CheckRead`、`CheckWrite`、`Transport` | 工具自己读写要过的规则（不经 Seatbelt）；替用户发请求，见[本机请求走系统代理](#本机请求走系统代理) |

`sandbox.New(Config)` 建一个本机 `Sandbox`，要求至少一个命令目录（`Roots`）。`sandbox.Here()` 给的是 `full-access`、以主目录为根的本机 Box，测试里用它。工具不直接拿 Box，而是拿一个 `sandbox.Boxes`（`func(ctx, user, environment) (Box, error)`），按用户和会话的环境去取；一个工具单独使用时，`sandbox.Fixed(box)` 对谁都给同一个 Box。

## 提供者与执行环境

`sandbox.Provider` 是部署提供的一种沙箱：

| 方法 | 作用 |
| --- | --- |
| `Name()` | 这种沙箱叫什么。用户的第一个环境就用这个名字 |
| `Check(config)` | 用户新建环境时给的设置（比如模板、地区）这个提供者能不能用；空表示提供者的默认 |
| `Open(ctx, env)` | 给出这个环境的 Box：环境还没有沙箱时建一个，已经有了就接回去。Box 由调用方关闭 |
| `Remove(ctx, env)` | 环境删掉之后清掉它的沙箱；沙箱已经不在了不算错 |

`sandbox.Env` 是提供者看到的一个环境：`User`、`ID`；`Config`，`Check` 认可过的设置；`State`，提供者上次留下的状态，比如云沙箱的 ID，沙箱还没建过时为 nil；`Keep`，在交出 Box 之前把新状态记下来，进程重启后 `Open` 凭它找回同一个沙箱。

**本机是一个提供者。** `sandbox.Local{Dir, Config}` 的每个环境是本机的一个文件夹 `Dir/<用户>/<环境 ID>`：`Open` 建好这个文件夹，把它作为唯一的命令目录交给 `sandbox.New(Config)`，命令按 `Config` 的限制运行（三种模式见下）。它的名字是 `sandbox.LocalName`（`This computer`）；不收设置，非空的设置被 `Check` 拒绝（`sandbox: this machine takes no settings`）；不留状态；`Remove` 不删文件夹，里面的东西归用户。用户 ID 或环境 ID 不能当文件夹名（空、`.`、`..`、带路径分隔符）时 `Open` 报错。

**环境由 `environment.Boxes` 打开。** 宿主把提供者按 ID 放进 `host.Config.Sandboxes`，用 `host.Config.Sandbox` 指定每个用户的第一个环境是哪个提供者的沙箱；一个提供者都没有，或 `Sandbox` 不在其中时，`host.New` 失败。

- 每个用户建出来时就带一个第一个环境（`EnsureUser`、`CreateUser` 在同一个事务里建），名字是那个提供者的 `Name()`。它删不掉，没有指定环境的地方都用它。
- 环境在库里只是一行（提供者 ID、设置、状态），沙箱第一次用到时才建：`In(ctx, user, environment)` 调提供者的 `Open`，之后同一个环境里的所有会话和工具共用这个 Box；`environment` 为空时是用户的第一个环境。
- 同一个环境的并发打开只做一次。打开在锁外进行，一个启动慢的云沙箱不挡别的环境；打开失败不缓存，下次用到时重试。
- 提供者经 `Keep` 交来的状态写进库（`environments.state`），客户端看不到它。
- 环境删除后，`environment.Boxes` 关掉它的 Box，再调提供者的 `Remove`；宿主停下（`h.Close`）时关掉所有打开的 Box。

**哪样东西用哪个环境。**

| 用途 | 用谁的 Box |
| --- | --- |
| `run_command`、`claude`、`read_file`、`glob`、`grep`、`edit_file`、`write_file` | 会话的环境 |
| `web_fetch` | 会话的环境，请求经它的 `Transport()` 发出 |
| `activate_skill` 放技能的文件 | 会话的环境，放在环境文件夹（`Roots()[0]`）下的 `.ollupi/skills/<名字>` |
| 系统提示词的 `# ENVIRONMENT` | 会话的环境，见[系统提示词](/zh/engine/context#系统提示词) |
| `workspace/add`、`workspace/move` | 工作区所在的环境 |
| 用户的 MCP 服务器 | 用户的第一个环境；stdio 服务器在能给全权的 Box 里以全权运行 |
| 按路径发来的附件 | 用户的第一个环境，也就是发消息的客户端所在的那台机器 |

会话在哪个环境里由应用层定：在工作区里的会话用工作区的环境，不在工作区的用开会话时指定的环境，默认是用户的第一个，见[工作区](/zh/engine/workspace#一个工作区是什么)。

::: info 演进
以前宿主填 `host.Config.Boxes`（`func(user) (Box, error)`），每个用户一个 Box；命令和文件工具由宿主自己用 `workspace.New` 建，配 `Box`、`BoxFor` 或 `BoxIn` 决定在哪个 Box 里跑；环境在库里只是一行名字和种类（`local` 或 `machine`），哪个环境对应哪台机器由宿主自己记。同一件事要在两处配，云环境也只能登记、接不上。现在宿主只给提供者，环境的沙箱由引擎建、记、关，命令和文件工具由 `host.New` 自己装。
:::

## 三种模式

`Config.Mode` 默认 `workspace-write`。

| 模式 | 读 | 写 | 命令 |
| --- | --- | --- | --- |
| `read-only` | 全部，禁读路径除外 | 只有 `/dev/null` | Seatbelt |
| `workspace-write` | 同上 | 命令目录、`ExtraWritable`、临时目录，保护路径除外 | Seatbelt |
| `full-access` | 全部 | 全部 | 直接运行 |

非 macOS 上 `read-only`、`workspace-write` 报错，提示改用 `full-access`；找不到 `/usr/bin/sandbox-exec` 也报错。`full-access` 下没有可解除的限制，`Enforced` 与 `CanEscalate` 都为假。Seatbelt 模式下 `/`、主目录、`~/Library` 及包含它们的目录都不能作命令目录（`validateRoot`）。

`seatbeltProfile` 每次现拼规则，经 `sandbox-exec -p` 传入：基础放开之后依次是读、写、网络，最后是拒绝段。

## 路径规则

路径在 `New` 时规范化（展开 `~`、绝对路径、解析已存在部分的符号链接）。macOS 和 Windows 上读写检查不区分大小写。

### 禁读路径

`defaultDenyRead` 内置在主目录下，再加 `Config.DenyRead`；禁读路径也不可写。名单覆盖云凭据（`.aws`、`.kube`、`.config/gcloud`、`.netrc`）、代码托管与 AI 工具凭据（`.ssh`、`.git-credentials`、`.config/gh`、`.codex/auth.json`、`.claude/.credentials.json`）、包管理器凭据（`.npmrc`、`.pypirc`、`.cargo/credentials`、`.m2/settings.xml`）、数据库与命令历史（`.pgpass`、`.my.cnf`）、`Library` 下的钥匙串、Cookie 与浏览器数据；完整名单见 `pkg/sandbox/policy.go`。引擎自己的库不在默认名单里，要由宿主写进 `DenyRead`，桌面端写的是 `<home>/data`。

### 保护名

保护名对每个可写目录的任意层级生效，是其他程序之后会自动运行的配置：编辑器与容器（`.vscode`、`.idea`、`.devcontainer`）、shell 环境（`.envrc`、`.mise`、`mise.toml`、`.bashrc`、`.zshrc`、`.profile`）、git 钩子类（`.husky`、`.githooks`、`.pre-commit-config.yaml`、`lefthook.yml`、`.gitconfig`、`.gitmodules`），以及 agent 的文件（`AGENTS.md`、`.agents`、`.codex`、`.claude`、`CLAUDE.md`、`.cursor`、`.mcp.json`）。宿主追加的 `Config.ProtectedNames` 只能含字母、数字、`.`、`-`、`_`。Seatbelt 下 `node_modules`、`vendor`、`Pods` 里的保护名例外，文件工具的 `CheckWrite` 没有这个例外。

`.git` 不在名单里，`.git/config` 和 `.git/hooks` 都可写；写进去的钩子会在用户之后运行 git 时执行，不受沙箱限制。

### 其他写入规则

| `Config` 字段 | 默认 | 作用 |
| --- | --- | --- |
| `ReadOnly` | 空 | 只读路径 |
| `ExtraWritable` | `~/.npm/_cacache`、`~/.npm/_logs`、`~/Library/Caches/go-build` | 额外可写，配置的追加在默认之后 |
| `UnixSockets` | 空 | 允许的 Unix socket，网络打开时生效 |
| `MaxOutputBytes` | 1 MiB | stdout、stderr 各自的上限 |

临时目录是 `/private/tmp` 和 `os.TempDir()`，只对命令可写。`CheckWrite` 只认这次调用的命令目录：`read-only` 一律拒绝，其他模式要求在其中，Seatbelt 下还要不在禁读、只读路径里、路径上没有保护名。`full-access` 下读取仍过 `CheckRead`，写入只要求在命令目录内。

文件工具和附件读取不经 Seatbelt：Unix 上 `Open` 逐级打开目录、不跟随符号链接、只打开普通文件，路径上有链接时先解析再打开，再对实际路径做 `CheckRead`，FIFO 立刻拒绝；`WriteFile` 写到同目录临时文件再改名替换，拒绝把链接放在目录位置。

## 环境变量

受限的命令（Seatbelt 下、没有全权）用白名单（`environ`）：只取 `PATH`、`HOME`、`USER`、`LOGNAME`、`SHELL`、`TMPDIR`、`TERM`、`LANG`、`TZ`、`LC_*` 和 `Config.EnvPassthrough`，再叠调用参数里的 `env`；后端进程的其他变量不传。

有完全访问的命令拿到后端进程的环境变量，只去掉名字以 `Config.HideEnv` 里某个前缀开头的（`fullEnviron`），再叠 `env`，和用户自己的程序拿到的一样。这包括 `full-access` 模式下的每条命令、批准了全权的命令，以及以全权启动的 MCP 服务器。后端的环境里有密钥时，把它们的前缀写进 `HideEnv`，桌面端写的是 `OLLUPI_`。

每条命令带 `<EnvMarker>_RUN_ID`（没设 `EnvMarker` 时是 `SANDBOX_RUN_ID`）用于[进程清理](#进程清理)。设了 `EnvMarker` 时，Seatbelt 下的命令还带 `<EnvMarker>=seatbelt`，不联网时再带 `<EnvMarker>_NETWORK_DISABLED=1`。

## 网络

| 情况 | 条件 | 规则 |
| --- | --- | --- |
| 关闭 | `Network: false`（默认） | 没有网络规则，`(deny default)` 生效 |
| 全开 | `Network: true`，没有 `Domains.Allowed` | 放开出入站，再关 Unix socket，只留 mDNSResponder 和 `UnixSockets` |
| 代理 | `Network: true`，有 `Domains.Allowed` | 只允许连本地代理的端口和 `UnixSockets` |

打开网络都加 `seatbelt_network.sbpl`（DNS、证书校验）和 `com.apple.TrustEvaluationAgent`。`Domains.Denied` 必须和 `Domains.Allowed` 一起用，否则 `New` 报 `denied_domains needs allowed_domains`。

### 网络代理

每条命令有自己的代理，监听回环地址的随机端口，按第一个字节分流：`0x05` 走 SOCKS5（`go-socks5`，只开 CONNECT），其他走 HTTP（`CONNECT` 建隧道，默认 443；绝对 `http://` 请求经 `httputil.ReverseProxy` 转发，默认 80），其余回 502。地址写进 `HTTP_PROXY`、`HTTPS_PROXY`、`ALL_PROXY`（`socks5h`）、`GRPC_PROXY`（含小写）、`NODE_USE_ENV_PROXY`、`JAVA_TOOL_OPTIONS`，并清空 `NO_PROXY`；不读这些变量的程序连不上网。

### 域名放行

条目是主机名、`*.域名`、`*` 或 IP（可带 `:端口`），不接受协议、路径与空白，写错 `New` 报错；`*.github.com` 不含 `github.com` 本身。`Denied` 先于 `Allowed`：不在名单里的连接 HTTP 回 403、SOCKS 回 `0x02`，其他失败回 502、`0x05`。被拦的连接记成 `network: blocked <目标> (<原因>)`，去重后最多 20 条，并进[拒绝原因报告](#拒绝原因报告)。`proxy.dial` 连接时解析并跳过 `sensitiveAddr` 命中的地址：回环与未指定、私有与 `100.64/10` 共享、链路本地与组播；主机被条目原样写出时例外（配 `localhost` 能连本机，配 `*` 不能）。

### 本机请求走系统代理

`Box.Transport()` 给替用户发请求的地方用，比如 HTTP MCP 服务器和 `web_fetch`。本机 `Sandbox.Transport()` 返回 `machineTransport`（`pkg/sandbox/system_proxy.go`）：克隆 `http.DefaultTransport`，`Proxy` 换成 `systemProxy`——先看 `HTTP_PROXY`、`HTTPS_PROXY`，没有就用 `ieproxy` 读系统代理。请求因此走用户的网络，也不受 `Domains` 约束。

`web_fetch` 另用 `sandbox.CheckPublic(ctx, host)` 拦回环、私有、链路本地地址，报 `web: fetch ...; use run_command to reach it`。云沙箱的 `Transport()` 是 `PublicTransport()`：拨号与 TLS 各 10 秒、`Proxy` 为空，`dialPublic` 只连公网地址，请求从引擎进程发出。

## 进程清理

`runProcess` 用 `Setpgid` 把命令放进自己的进程组并带上运行标记，超时、取消和正常结束都调 `killRun` 给进程组发 `SIGKILL`。macOS 上 `killTagged` 再按 `kern.proc.uid`、`kern.procargs2` 找带标记的进程，加上进程组成员沿父子关系扩展，先 `SIGSTOP` 再 `SIGKILL`，最多 200 轮；其他平台只杀进程组。退出码被信号杀死时是 `128 + 信号值`；超时返回 "timed out after ... and was killed" 加各自最后 2000 字节；输出用 `cappedBuffer` 保留头尾，中断处写 `[… N bytes omitted …]` 并标 `Truncated`。

## 拒绝原因报告

`New` 时（macOS、非 `full-access`）启动常驻 `log stream`，过滤一个随机后缀；每次运行的规则带标记 `OSBX<16 位十六进制>_<后缀>`，带标记的 `Sandbox: 进程(pid) deny(n) 操作 目标` 日志归到那次运行。只保留 `file-*`、`network-*`、`process-exec*`，去掉 mDNSResponder 噪音，去重后最多 20 条；`/dev/dtracehelper`、`/dev/tty` 是 `harmlessDenials`，只丢那一行，不清空真实拒绝。

命令失败时最多等 500 毫秒，成功的命令不报告；代理拦下的连接也算，结果在 `run_command` 输出里是 `sandbox_denials`。`log stream` 起不来不影响运行，全权运行没有这份报告。

## 全权

全权（full access）让一条命令在同一个 Box 里解除沙箱限制，本机就是不加 Seatbelt。模型在 `run_command` 里传 `sandbox_permissions: "require_escalated"`（默认 `use_default`）和一句 `justification`。这两个参数总在 schema 里，能不能用写在系统提示词的 `# ENVIRONMENT` 里：Box 能给全权时，它要求只在命令因沙箱的限制失败时才申请；不能时，它让模型不要传这个参数。

| 情况 | 结果 |
| --- | --- |
| `Enforced` 为假 | `workspace: this sandbox puts no limits on commands, so they already have full access; omit sandbox_permissions` |
| `CanEscalate` 为假 | `workspace: this sandbox cannot give a command full access; omit sandbox_permissions` |
| 没有 `justification` | `workspace: sandbox_permissions %q needs a justification for the user` |

`claude` 不带这两个参数：在既受限又能给全权的 Box 上总是申请全权，理由是 `Claude Code needs the network and its own settings in your home folder`。

通过后 `Prepared.Escalated` 为真、`Sandboxed` 为假，再进入权限判定：allow 规则不算数，`on-request`、`untrusted` 下一律问；escalate 规则命中或 `never` 档下直接以全权运行。`acceptForSession` 只覆盖同样申请全权的调用，选"总是允许"写入 escalate 规则，判定细节见[审批与权限](/zh/engine/permissions#全权)。

批准后（`never` 下不经批准）`Command.FullAccess` 为真，不加 Seatbelt、不起代理，环境变量按[有完全访问的命令](#环境变量)给，结果带 `sandbox: "escalated: ran with full access, without the sandbox's limits"`。`Remote` 拒绝 `FullAccess`，报 `sandbox: this sandbox cannot give a command full access`。

::: info 演进
以前 Box 不能给全权时，`run_command` 的 schema 里没有 `sandbox_permissions` 和 `justification`，怎样申请全权写在工具描述里；全权运行的命令也只拿到白名单里的环境变量。现在工具的定义对所有会话都一样，随环境变化的说明挪进系统提示词的 `# ENVIRONMENT`；全权的命令拿到后端的环境，用 `HideEnv` 去掉密钥。
:::

## 云沙箱接入点

写一个 `Provider`：`Open` 建出或找回这个环境的机器，用 `Keep` 记下机器的 ID，再把机器包成 Box 交出去；`Remove` 删掉机器。机器实现 `Machine`（`Run`、`Start`、`Stat`、`ReadDir`、`Open`、`WriteFile`、`Close`），用 `sandbox.Remote(m, roots, summary)` 包成 `Box`：`roots` 的第一个是环境文件夹，`summary` 写进系统提示词。机器的网络规则由提供者负责，`Close` 只断开连接。一台机器只放一个环境的东西，所以 `Enforced` 为真、`CanEscalate` 为假，`Check`、`CheckRead` 总是通过，`CheckWrite` 只要求命令目录内，`Move` 在机器里运行 `mv -f`。完整的例子见[扩展点](/zh/integrate/extend#云沙箱)。

## 边界与已知问题

- **只有 macOS。** 非 macOS 只能用 `full-access`，这时 `on-request` 下每条命令都要问。
- **还没有云沙箱提供者。** `Machine` 的实现只在测试里，引擎和桌面端都没有接入哪家服务商。
- **读取几乎不设限，`.git/hooks` 可写。** Seatbelt 是 `(allow file-read*)` 加禁读路径，不在名单里的文件命令都能读，而且不问用户；写进钩子的代码会在用户之后运行 git 时执行，不受沙箱限制。
- **`never` 档下全权不问，只有 deny 规则拦得住。**
- **MCP 服务器以全权运行。** 用户的 stdio 服务器在第一个环境里启动，Box 能给全权时就以全权运行，不受 Seatbelt 限制，只少了 `HideEnv` 去掉的变量，见[权限与沙箱](/zh/engine/skills-mcp#权限与沙箱)。
- **删环境不删本机的文件夹。** `Local.Remove` 什么都不做，文件夹和里面的文件留在 `Dir/<用户>/<环境 ID>`。
- **`web_fetch` 只看主机地址。** 走会话环境的 `Transport()`，不读 `Domains`，也不受域名名单约束。

## 代码位置

| 仓库 | 路径 | 职责 |
| --- | --- | --- |
| ollupi | `pkg/sandbox/box.go`、`sandbox.go` | `Box`、`ReadFile`、`Transport`、`Here`；`Config`、`New`、`Run`、`Summary` |
| ollupi | `pkg/sandbox/provider.go` | `Provider`、`Env`、`Boxes`、`Fixed`、`Local` |
| ollupi | `environment/environment.go` | `environment.Boxes`：按环境打开、共用、关闭 Box，记提供者的状态 |
| ollupi | `pkg/sandbox/policy.go`、`paths.go`、`seatbelt.go` 与三个 `.sbpl` | 模式、禁读路径、保护名、可写缓存、`validateRoot`；路径规范化；Seatbelt 规则 |
| ollupi | `pkg/sandbox/proxy.go`、`domains.go`、`public.go`、`system_proxy.go` | 代理、域名规则、`CheckPublic` 与 `PublicTransport`、系统代理 |
| ollupi | `pkg/sandbox/denials.go`、`process*.go`、`remote.go`、`files_*.go`、`env.go` | 拒绝原因与 `harmlessDenials`；运行与清理；`Remote`、按检查过的路径读写、两种环境变量 |
| ollupi | `tool/builtin/workspace/config.go`、`tool.go`、`dirs.go`、`execution.go`、`claude.go`、`environment.go` | 超时与黑名单、按会话的环境取 Box、冻结命令、全权校验与执行、`claude` 的全权条件、`# ENVIRONMENT` 的文字 |
| ollupi | `tool/builtin/web/web.go` | `web_fetch` 用会话环境的 Box、`CheckPublic`、30 秒超时、10 MiB 上限 |
