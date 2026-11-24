# 沙箱

沙箱决定模型的命令和文件操作能碰到什么。工具经 `sandbox.Box` 运行命令、读写文件；`pkg/sandbox` 的本机 `Sandbox` 用 macOS Seatbelt（用 `sandbox-exec` 加一段规则跑进程），`Remote` 把云沙箱的 `Machine` 包成 `Box`。权限决定要不要问用户，沙箱决定放行之后能做什么，见[审批与权限](/zh/engine/permissions)。

## 为什么这样设计

- **工具只经 `Box` 碰机器。** 命令、文件、附件、stdio MCP 服务器都走这个接口，本机与云沙箱是它的两种实现，见[设计决策 1](/zh/reference/decisions#_1-池化-runtime)。
- **用 Seatbelt。** 虚拟机隔离更强，但里面是 Linux，用不了 macOS 工具链；基础规则取自 OpenAI Codex，代理、拒绝日志和保护名参照 Anthropic 的 sandbox-runtime，见[设计决策 20](/zh/reference/decisions#_20-seatbelt-沙箱)。
- **挡住之后会被别的程序执行的文件。** 逃逸多是写钩子配置、git config 这类文件，不是攻破沙箱，所以保护名在可写目录的任意层级都不可写；`.git` 例外，否则 `git init`、`git clone` 在沙箱里必然失败。

## Box 接口

| 方法 | 作用 |
| --- | --- |
| `Run`、`Start` | 运行到结束；`Start` 跑 stdio MCP 服务器，直到 `ctx` 结束或 `Process` 关闭 |
| `Stat`、`ReadDir`、`Open`、`WriteFile`、`Move`、`Canonical`、`Directory`、`Executable`、`Same` | 按 Box 自己的路径读写、搬动、规范化与解析程序；整文件读取走 `sandbox.ReadFile(ctx, box, path, limit)` |
| `Enforced`、`CanEscalate`、`Summary`、`Roots`、`Fingerprint` | 命令是否受限、能否给全权、写进工具描述的规则、命令目录、规则指纹 |
| `Check`、`CheckRead`、`CheckWrite`、`Transport` | 工具自己读写要过的规则（不经 Seatbelt）；替用户发请求，见[本机请求走系统代理](#本机请求走系统代理) |

工作区工具从 `workspace.Options` 取 Box：`BoxIn(caller)` 按会话开始时选的执行环境给，`nil` 时退回 `Box`，再退回 `BoxFor(user)`；都没配时用 `sandbox.New` 建一个本机 `Sandbox`，所有用户共用。MCP 服务器、附件、工作区的增加和搬动走 `host.Config.Boxes(user)`。`sandbox.New(Config)` 要求至少一个命令目录（`Roots`）；`sandbox.Here()` 给的是 `full-access`、以主目录为根的本机 Box，引擎自带的 `bench`、`eval` 和测试用它。

## 三种模式

`sandbox_mode` 默认 `workspace-write`。

| 模式 | 读 | 写 | 命令 |
| --- | --- | --- | --- |
| `read-only` | 全部，禁读路径除外 | 只有 `/dev/null` | Seatbelt |
| `workspace-write` | 同上 | 命令目录、`extra_writable`、临时目录，保护路径除外 | Seatbelt |
| `full-access` | 全部 | 全部 | 直接运行 |

非 macOS 上 `read-only`、`workspace-write` 报错，提示改用 `full-access`；找不到 `/usr/bin/sandbox-exec` 也报错。`full-access` 下没有可解除的限制，`Enforced` 与 `CanEscalate` 都为假。Seatbelt 模式下 `/`、主目录、`~/Library` 及包含它们的目录都不能作命令目录（`validateRoot`）。

`seatbeltProfile` 每次现拼规则，经 `sandbox-exec -p` 传入：基础放开之后依次是读、写、网络，最后是拒绝段。

## 路径规则

路径在 `New` 时规范化（展开 `~`、绝对路径、解析已存在部分的符号链接）。macOS 和 Windows 上读写检查不区分大小写。

### 禁读路径

`defaultDenyRead` 内置在主目录下，再加 `deny_read`、`workspace.Options.DenyRead` 和 `<agent home>/data`；禁读路径也不可写。名单覆盖云凭据（`.aws`、`.kube`、`.config/gcloud`、`.netrc`）、代码托管与 AI 工具凭据（`.ssh`、`.git-credentials`、`.config/gh`、`.codex/auth.json`、`.claude/.credentials.json`）、包管理器凭据（`.npmrc`、`.pypirc`、`.cargo/credentials`、`.m2/settings.xml`）、数据库与命令历史（`.pgpass`、`.my.cnf`）、`Library` 下的钥匙串、Cookie 与浏览器数据；完整名单见 `pkg/sandbox/policy.go`。

### 保护名

保护名对每个可写目录的任意层级生效，是其他程序之后会自动运行的配置：编辑器与容器（`.vscode`、`.idea`、`.devcontainer`）、shell 环境（`.envrc`、`.mise`、`mise.toml`、`.bashrc`、`.zshrc`、`.profile`）、git 钩子类（`.husky`、`.githooks`、`.pre-commit-config.yaml`、`lefthook.yml`、`.gitconfig`、`.gitmodules`），工作区工具另加 `AGENTS.md`、`.agents`、`.codex`、`.claude`、`CLAUDE.md`、`.cursor`、`.mcp.json`。宿主追加的 `Config.ProtectedNames` 只能含字母、数字、`.`、`-`、`_`。Seatbelt 下 `node_modules`、`vendor`、`Pods` 里的保护名例外，文件工具的 `CheckWrite` 没有这个例外。

`.git` 不在名单里，`.git/config` 和 `.git/hooks` 都可写；写进去的钩子会在用户之后运行 git 时执行，不受沙箱限制。

### 其他写入规则

| 配置 | 默认 | 作用 |
| --- | --- | --- |
| `read_only` | 技能目录 | 只读路径 |
| `extra_writable` | `~/.npm/_cacache`、`~/.npm/_logs`、`~/Library/Caches/go-build` | 额外可写，配置的追加在默认之后 |
| `unix_sockets`、`env_passthrough` | 空 | 允许的 Unix socket（网络打开时生效）、额外传给命令的变量 |
| `max_output_bytes` | 1 MiB | stdout、stderr 各自的上限 |

临时目录是 `/private/tmp` 和 `os.TempDir()`，只对命令可写。`CheckWrite` 只认这次调用的命令目录：`read-only` 一律拒绝，其他模式要求在其中，Seatbelt 下还要不在禁读、只读路径里、路径上没有保护名。`full-access` 下读取仍过 `CheckRead`，写入只要求在命令目录内。

文件工具和附件读取不经 Seatbelt：Unix 上 `Open` 逐级打开目录、不跟随符号链接、只打开普通文件，路径上有链接时先解析再打开，再对实际路径做 `CheckRead`，FIFO 立刻拒绝；`WriteFile` 写到同目录临时文件再改名替换，拒绝把链接放在目录位置。

## 环境变量

环境变量是白名单（`environ`）：只取 `PATH`、`HOME`、`USER`、`LOGNAME`、`SHELL`、`TMPDIR`、`TERM`、`LANG`、`TZ`、`LC_*` 和 `env_passthrough`，再叠调用参数里的 `env`，全权运行时也一样；宿主进程的其他变量不传。每条命令带 `SANDBOX_RUN_ID` 用于[进程清理](#进程清理)。

## 网络

| 情况 | 条件 | 规则 |
| --- | --- | --- |
| 关闭 | `network: false` | 没有网络规则，`(deny default)` 生效 |
| 全开 | `network: true`，没有 `allowed_domains` | 放开出入站，再关 Unix socket，只留 mDNSResponder 和 `unix_sockets` |
| 代理 | `network: true`，有 `allowed_domains` | 只允许连本地代理的端口和 `unix_sockets` |

打开网络都加 `seatbelt_network.sbpl`（DNS、证书校验）和 `com.apple.TrustEvaluationAgent`。`denied_domains` 必须和 `allowed_domains` 一起用。

### 网络代理

每条命令有自己的代理，监听回环地址的随机端口，按第一个字节分流：`0x05` 走 SOCKS5（`go-socks5`，只开 CONNECT），其他走 HTTP（`CONNECT` 建隧道，默认 443；绝对 `http://` 请求经 `httputil.ReverseProxy` 转发，默认 80），其余回 502。地址写进 `HTTP_PROXY`、`HTTPS_PROXY`、`ALL_PROXY`（`socks5h`）、`GRPC_PROXY`（含小写）、`NODE_USE_ENV_PROXY`、`JAVA_TOOL_OPTIONS`，并清空 `NO_PROXY`；不读这些变量的程序连不上网。

### 域名放行

条目是主机名、`*.域名`、`*` 或 IP（可带 `:端口`），不接受协议、路径与空白，写错 `New` 报错；`*.github.com` 不含 `github.com` 本身。`denied_domains` 先于 `allowed_domains`：不在名单里的连接 HTTP 回 403、SOCKS 回 `0x02`，其他失败回 502、`0x05`。被拦的连接记成 `network: blocked <目标> (<原因>)`，去重后最多 20 条，并进[拒绝原因报告](#拒绝原因报告)。`proxy.dial` 连接时解析并跳过 `sensitiveAddr` 命中的地址：回环与未指定、私有与 `100.64/10` 共享、链路本地与组播；主机被条目原样写出时例外（配 `localhost` 能连本机，配 `*` 不能）。

### 本机请求走系统代理

`Box.Transport()` 给替用户发请求的地方用，比如 HTTP MCP 服务器和 `web_fetch`。本机 `Sandbox.Transport()` 返回 `machineTransport`（`pkg/sandbox/system_proxy.go`）：克隆 `http.DefaultTransport`，`Proxy` 换成 `systemProxy`——先看 `HTTP_PROXY`、`HTTPS_PROXY`，没有就用 `ieproxy` 读系统代理。请求因此走用户的网络，也不受 `allowed_domains` 约束。

`web_fetch` 另用 `sandbox.CheckPublic(ctx, host)` 拦回环、私有、链路本地地址，报 `web: fetch ...; use run_command to reach it`。云沙箱的 `Transport()` 是 `PublicTransport()`：拨号与 TLS 各 10 秒、`Proxy` 为空，`dialPublic` 只连公网地址，请求从引擎进程发出。

## 进程清理

`runProcess` 用 `Setpgid` 把命令放进自己的进程组并带上 `SANDBOX_RUN_ID`，超时、取消和正常结束都调 `killRun` 给进程组发 `SIGKILL`。macOS 上 `killTagged` 再按 `kern.proc.uid`、`kern.procargs2` 找带标记的进程，加上进程组成员沿父子关系扩展，先 `SIGSTOP` 再 `SIGKILL`，最多 200 轮；其他平台只杀进程组。退出码被信号杀死时是 `128 + 信号值`；超时返回 "timed out after ... and was killed" 加各自最后 2000 字节；输出用 `cappedBuffer` 保留头尾，中断处写 `[… N bytes omitted …]` 并标 `Truncated`。

## 拒绝原因报告

`New` 时（macOS、非 `full-access`）启动常驻 `log stream`，过滤一个随机后缀；每次运行的规则带标记 `OSBX<16 位十六进制>_<后缀>`，带标记的 `Sandbox: 进程(pid) deny(n) 操作 目标` 日志归到那次运行。只保留 `file-*`、`network-*`、`process-exec*`，去掉 mDNSResponder 噪音，去重后最多 20 条；`/dev/dtracehelper`、`/dev/tty` 是 `harmlessDenials`，只丢那一行，不清空真实拒绝。

命令失败时最多等 500 毫秒，成功的命令不报告；代理拦下的连接也算，结果在 `run_command` 输出里是 `sandbox_denials`。`log stream` 起不来不影响运行，全权运行没有这份报告。

## 全权

全权（full access）让一条命令在同一个 Box 里解除沙箱限制，本机就是不加 Seatbelt。模型在 `run_command` 里传 `sandbox_permissions: "require_escalated"`（默认 `use_default`）和一句 `justification`；工具描述要求只在命令因沙箱失败时才这样做。

| 情况 | 结果 |
| --- | --- |
| `Enforced` 为假 | `workspace: this sandbox puts no limits on commands, so they already have full access; omit sandbox_permissions` |
| `CanEscalate` 为假 | `workspace: this sandbox cannot give a command full access; omit sandbox_permissions` |
| 没有 `justification` | `workspace: sandbox_permissions %q needs a justification for the user` |

`CanEscalate` 为假时这两个参数不出现在 schema 里。`claude` 不带它们：在既受限又能给全权的 Box 上总是申请全权，理由是 `Claude Code needs the network and its own settings in your home folder`。

通过后 `Prepared.Escalated` 为真、`Sandboxed` 为假，再进入权限判定：allow 规则不算数，`on-request`、`untrusted` 下一律问；escalate 规则命中或 `never` 档下直接以全权运行。`acceptForSession` 只覆盖同样申请全权的调用，选"总是允许"写入 escalate 规则，判定细节见[审批与权限](/zh/engine/permissions#全权)。

批准后（`never` 下不经批准）`Command.FullAccess` 为真，不加 Seatbelt、不起代理，环境白名单仍生效，结果带 `sandbox: "escalated: ran with full access, without the sandbox's limits"`。`Remote` 拒绝 `FullAccess`，报 `sandbox: this sandbox cannot give a command full access`。

## 云沙箱接入点

实现 `Machine`（`Run`、`Start`、`Stat`、`ReadDir`、`Open`、`WriteFile`、`Close`），用 `sandbox.Remote(m, roots, summary)` 包成 `Box`；机器的创建和网络规则由调用方负责，`Close` 只断开连接。一台机器只放一个用户的东西，所以 `Enforced` 为真、`CanEscalate` 为假，`Check`、`CheckRead` 总是通过，`CheckWrite` 只要求命令目录内，`Move` 在机器里运行 `mv -f`。

## 边界与已知问题

- **只有 macOS。** 非 macOS 只能用 `full-access`，这时 `on-request` 下每条命令都要问。
- **云沙箱只有接口。** `Machine` 的实现只在测试里，没有接入服务商。
- **读取几乎不设限，`.git/hooks` 可写。** Seatbelt 是 `(allow file-read*)` 加禁读路径，不在名单里的文件命令都能读，而且不问用户；写进钩子的代码会在用户之后运行 git 时执行，不受沙箱限制。
- **`never` 档下全权不问，只有 deny 规则拦得住。**
- **MCP 服务器不一定在沙箱里。** 受不受限由宿主给的 Box 决定，见[权限与沙箱](/zh/engine/skills-mcp#权限与沙箱)；工作区工具不配 `BoxFor`、`BoxIn` 时，所有用户共用一个本机沙箱。
- **`web_fetch` 只看主机地址。** 走用户 Box 的 `Transport()`，不读 `allowed_domains`，也不受域名名单约束。

## 代码位置

| 仓库 | 路径 | 职责 |
| --- | --- | --- |
| ollupi | `pkg/sandbox/box.go`、`sandbox.go` | `Box`、`ReadFile`、`Transport`；`Config`、`New`、`Run`、`Summary` |
| ollupi | `pkg/sandbox/policy.go`、`paths.go`、`seatbelt.go` 与三个 `.sbpl` | 模式、禁读路径、保护名、可写缓存、`validateRoot`；路径规范化；Seatbelt 规则 |
| ollupi | `pkg/sandbox/proxy.go`、`domains.go`、`public.go`、`system_proxy.go` | 代理、域名规则、`CheckPublic` 与 `PublicTransport`、系统代理 |
| ollupi | `pkg/sandbox/denials.go`、`process*.go`、`remote.go`、`files_*.go`、`env.go` | 拒绝原因与 `harmlessDenials`；运行与清理；`Remote`、按检查过的路径读写、环境白名单 |
| ollupi | `tool/builtin/workspace/config.go`、`tool.go`、`dirs.go`、`execution.go`、`claude.go` | 配置项与默认值、选 Box、冻结命令、全权校验与执行、`claude` 的全权条件 |
| ollupi | `tool/builtin/web/web.go` | `web_fetch` 用用户的 Box、`CheckPublic`、30 秒超时、10 MiB 上限 |
