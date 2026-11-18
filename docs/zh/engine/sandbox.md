# 沙箱

沙箱决定模型的命令和文件操作能碰到什么。工具经 `sandbox.Box` 接口运行命令、读写文件，不直接碰操作系统。`pkg/sandbox` 给出两种实现：本机的 `Sandbox`，用 macOS Seatbelt（系统内核的沙箱机制，用 `sandbox-exec` 加一段规则运行进程）；以及把云沙箱的 `Machine` 包成 `Box` 的 `Remote`。

权限决定一次调用要不要问用户，沙箱决定调用放行之后实际能做什么，两者互相独立。`on-request` 策略下沙箱内的命令不用问，这正是因为沙箱已经限制了它们，见[审批与权限](/zh/engine/permissions)和[安全总览](/zh/engine/security)。

## 为什么这样设计

- **工具只经 `Box` 碰机器。** 命令、文件工具、附件读取、工作区的增加和搬动、stdio MCP 服务器都经 `sandbox.Box` 访问，本机 Seatbelt 和云沙箱是同一个接口的两种实现，一个进程能同时服务两类用户。池化之后用户之间没有进程边界，这是代码守住隔离的方式之一，见[设计决策 1](/zh/reference/decisions#_1-池化-runtime)。
- **用 Seatbelt，不用虚拟机或另开用户账号。** 调研文档列过这两类方案，对虚拟机的评语是隔离最强，但里面是 Linux，用不了 macOS 工具链。基础规则取自 OpenAI Codex，网络代理、拒绝日志和保护名主要参照 Anthropic 的 sandbox-runtime。见[设计决策 20](/zh/reference/decisions#_20-seatbelt-沙箱)。
- **网络走本地代理。** Seatbelt 不能按域名过滤网络，所以配了域名名单时，内核只放行到本地代理的那个端口，域名由代理判断，连接时再跳过解析到内网的地址。
- **挡住"之后会被别的程序运行"的文件。** 调研时参考的是 2026 年 7 月一批 agent 沙箱逃逸：多数案例没有攻破沙箱本身，而是写下一个之后会被沙箱外的程序执行的文件，比如钩子配置、git config。所以 `.vscode`、`.envrc`、shell 启动文件这类名字在可写目录的任意层级都不可写。
- **`.git` 是有意留的例外。** 整个 `.git` 可写。`git init`、`git clone` 是项目目录里最普通的命令，`.git` 禁写的话它们在沙箱里一定失败，只能每次提权；换来的代价是 `.git/hooks` 这个已知的口子。调研文档记录 Codex 把 `.git` 设为只读。

代价：本机沙箱只有 macOS，Linux 和 Windows 还在路线图上，非 macOS 只能用 `full-access`；读取几乎不设限，靠禁读名单挡凭据；`.git/hooks` 写进去的代码会在用户自己运行 git 时在沙箱外执行；不读代理环境变量的程序在域名名单模式下连不上网。

::: info 演进
- 所有访问都经 `Box` 来自 `aecfb63`、`f1ff694`。
- 沙箱逃逸的调研记录在 `docs/sandbox-sources.md`，见 `05ef4b0` 的父提交。
- Ollupi 起初也在每个可写根下禁写 `.git/config` 和钩子（`e36dd28`），结果 `git init`、`git clone` 在沙箱里一定失败。`5d4354d` 放开了整个 `.git`。
:::

## Box 接口

`Box` 是用户的命令运行和文件所在的地方。路径是 Box 自己的路径，不一定存在于本机。

```go
type Box interface {
	Run(ctx context.Context, c Command) (Result, error)
	Start(ctx context.Context, c Command, stderr io.Writer) (Process, error)
	Stat(ctx context.Context, path string) (fs.FileInfo, error)
	ReadDir(ctx context.Context, path string) ([]fs.DirEntry, error)
	Open(ctx context.Context, path string) (io.ReadCloser, error)
	WriteFile(ctx context.Context, path string, data []byte, perm fs.FileMode) error
	Move(ctx context.Context, from, to string) error
	Canonical(ctx context.Context, path string) (string, error)
	Directory(ctx context.Context, path string) (string, error)
	Executable(ctx context.Context, program, cwd string) (string, error)
	Same(ctx context.Context, a, b string) bool

	Enforced() bool
	CanEscalate() bool
	Summary() string
	Roots() []string
	Fingerprint() any
	Check(dir string) error
	CheckRead(path string) error
	CheckWrite(roots []string, path string) error
	Transport() http.RoundTripper
	Close() error
}
```

| 方法 | 作用 |
| --- | --- |
| `Run` | 运行到结束，受 `Command.Timeout` 限制，`Timeout` 必须大于 0 |
| `Start` | 让命令一直运行到 `ctx` 结束或 `Process` 关闭，给 stdio MCP 服务器用，`Timeout` 不适用 |
| `Move` | 在 box 内搬一个文件夹，给 `workspace/move` 用。`to` 必须不存在或为空，不合并 |
| `Executable` | 把程序名解析成要运行的文件，冻结命令和执行前核对都用它 |
| `Enforced` | 命令受限，可以不问用户 |
| `CanEscalate` | 命令可以离开限制，要用户同意 |
| `Summary` | 写进 `run_command` 工具描述，告诉模型这里的规则 |
| `Roots` | 命令目录。命令默认在第一个运行 |
| `Fingerprint` | 规则变了它就变，让按旧规则冻结的调用不被运行 |
| `Check` | 目录能否作为命令目录 |
| `CheckRead`、`CheckWrite` | 工具自己读写时要过的规则，不经 Seatbelt |
| `Transport` | 替用户发 HTTP 请求用，比如连 HTTP MCP 服务器 |

整文件读取走 `sandbox.ReadFile(ctx, box, path, limit)`，超过 `limit` 字节就拒绝，调用方各自给上限。

Box 从两处来：

- 工作区工具（`run_command`、文件工具）从 `workspace.Options` 拿：`BoxIn(caller)` 按会话开始时选的执行环境给 Box，返回 `nil` 时退回 `Box`；没配 `BoxIn` 时用 `BoxFor(user)`，每个用户一个；都没配就用 `Box`。`Box` 为空时，工作区工具按自己的配置用 `sandbox.New` 建一个本机 `Sandbox`，所有用户共用。`Box` 同时用来描述工具：工具描述里的目录和规则、`run_command` 的 schema 里有没有提权参数，都从它来。见[扩展点](/zh/integrate/extend#按会话选择环境)。
- MCP 服务器、附件读取、工作区的增加和搬动用 `host.Config.Boxes(user)`，宿主必须提供。

`Sandbox` 是本机实现，`sandbox.New(Config)` 创建。

::: info 演进
`BoxIn` 随 v0.12.0 加入（`5f64857`）。v0.16.0 起 `host.Config.Boxes` 必填，MCP 服务器和附件经它取得用户的 Box。
:::

## 三种模式

配置项 `sandbox_mode`，默认 `workspace-write`。

| 模式 | 读 | 写 | 命令 |
| --- | --- | --- | --- |
| `read-only` | 全部，禁读路径除外 | 除 `/dev/null` 外都不行 | Seatbelt |
| `workspace-write` | 同上 | 命令目录、`extra_writable`、临时目录，保护路径除外 | Seatbelt |
| `full-access` | 全部 | 全部 | 不用 Seatbelt，直接运行 |

非 macOS 上 `read-only` 和 `workspace-write` 报错，提示改用 `full-access`；macOS 上找不到 `/usr/bin/sandbox-exec` 也报错。`full-access` 下 `Enforced` 为假，`CanEscalate` 也为假，因为没有沙箱可离开。

Seatbelt 模式下，`/`、用户主目录、`~/Library`，以及任何包含它们的目录都不能作为命令目录（`validateRoot`），`New` 时和每条命令带来的命令目录都要过这一关。这样一来命令目录不会大到把保护路径包进去。找不到用户主目录时 `New` 报错，因为规则要用到它。

`full-access` 下工具自己的读取仍过 `CheckRead`，写入只要求在命令目录内。读取工具不需要审批，所以禁读路径在每种模式下都关闭。

## 路径规则

规则里的路径在 `New` 时规范化（展开 `~`、取绝对路径、解析已存在部分的符号链接）。在 macOS 和 Windows 上，`CheckRead`、`CheckWrite` 和命令目录检查都不区分大小写，和这两个系统的文件系统一致；Seatbelt 规则里的保护名在任何系统上都不区分大小写。

### 禁读路径

`defaultDenyRead` 内置在主目录下，再加配置的 `deny_read`、宿主给的 `workspace.Options.DenyRead` 和 `<agent home>/data`：

| 类别 | 路径 |
| --- | --- |
| 密钥与云凭据 | `.ssh`、`.gnupg`、`.aws`、`.azure`、`.kube`、`.netrc`、`.config/gcloud`、`.docker/config.json`、`.vault-token`、`.terraform.d/credentials.tfrc.json`、`.password-store`、`.config/op`、`.oci`、`.boto`、`.s3cfg`、`.databrickscfg`、`.config/doctl`、`.config/hcloud`、`.fly`、`.kaggle`、`.config/stripe` |
| 代码托管与 AI 工具 | `.git-credentials`、`.config/gh`、`.config/hub`、`.config/glab-cli`、`.config/git/credentials`、`.config/github-copilot`、`.codex/auth.json`、`.claude/.credentials.json`、`.huggingface/token`、`.cache/huggingface/token` |
| 包管理器 | `.cargo/credentials`、`.cargo/credentials.toml`、`.pypirc`、`.gem/credentials`、`.npmrc`、`.yarnrc`、`.yarnrc.yml`、`.config/configstore`、`.composer/auth.json`、`.config/composer/auth.json`、`.m2/settings.xml`、`.m2/settings-security.xml`、`.gradle/gradle.properties`、`.nuget/NuGet/NuGet.Config` |
| 数据库 | `.pgpass`、`.my.cnf` |
| 命令历史 | `.zsh_history`、`.bash_history`、`.python_history`、`.node_repl_history` |
| 个人数据 | `Library/Keychains`、`Library/Cookies`、`Library/Messages`、`Library/Mail`、`Library/Safari` |
| 浏览器 | `Library/Application Support/` 下的 `Google/Chrome`、`Firefox`、`BraveSoftware`、`Microsoft Edge`、`Arc` |

禁读路径也不可写。

### 保护名

保护名是一组文件或目录名，写规则对每个可写目录的任意层级生效。它们是其他程序之后会自动运行的配置，写进去等于留下一段在沙箱外运行的代码。

| 类别 | 名字 |
| --- | --- |
| 编辑器 | `.vscode`、`.idea`、`.zed`、`.fleet`、`.devcontainer` |
| shell 环境 | `.envrc`、`.mise.toml`、`mise.toml`、`.mise`、`.bashrc`、`.bash_profile`、`.zshrc`、`.zprofile`、`.zshenv`、`.profile` |
| git 钩子类 | `.husky`、`.githooks`、`.pre-commit-config.yaml`、`lefthook.yml`、`.lefthook.yml`、`lefthook.yaml`、`.gitconfig`、`.gitmodules` |
| 其他 | `.ripgreprc` |
| agent 配置（工作区工具追加） | `AGENTS.md`、`.agents`、`.codex`、`.claude`、`CLAUDE.md`、`.cursor`、`.mcp.json` |

宿主追加的保护名（`Config.ProtectedNames`）只能含字母、数字、`.`、`-`、`_`。

Seatbelt 规则里，`node_modules`、`vendor`、`Pods` 下的保护名例外：这些目录是依赖，规则在它们下面重新放开。文件工具的 `CheckWrite` 没有这个例外。

仓库自己的 `.git` 不在这张表里，和普通目录一样可写，包括 `.git/config` 和 `.git/hooks`，所以 `git init`、`git clone` 不会被沙箱的写规则挡住；克隆远端仓库仍然需要网络，网络关闭时照样失败。`.git/hooks` 和上表一样，是用户自己的命令之后会运行的代码，放开它的取舍见[为什么这样设计](#为什么这样设计)。

::: info 演进
`5d4354d` 之前，Seatbelt 在每个可写根下禁写 `.git/config`、`.git/hooks` 等路径，`.git` 本身不能删除或改名；文件工具（`CheckWrite`）则拒绝写整个 `.git`。
:::

### 其他写入规则

| 配置 | 默认 | 作用 |
| --- | --- | --- |
| `read_only` | 技能目录 | 只读路径 |
| `extra_writable` | `~/.npm/_cacache`、`~/.npm/_logs` | 额外可写路径，配置的追加在默认之后 |
| `unix_sockets` | 空 | 允许连接的 Unix socket，只在网络打开时生效 |
| `env_passthrough` | 空 | 额外传给命令的环境变量 |
| `max_output_bytes` | 1 MiB | stdout、stderr 各自的上限 |

临时目录是 `/private/tmp` 和规范化后的 `os.TempDir()`，只对命令可写。文件工具的 `CheckWrite` 只认这次调用的命令目录：`read-only` 下一律拒绝；其他模式要求路径在命令目录内；Seatbelt 模式下还要不在禁读和只读路径里、路径上没有保护名。

### 工具自己的读写

文件工具、附件读取不经 Seatbelt，由 `Box` 自己守规则。本机 `Sandbox` 在 Unix 上按检查过的路径打开文件：`Open` 逐级打开目录、不跟随符号链接，只打开普通文件，路径上有链接时先解析再同样打开一次，再对实际打开的路径做 `CheckRead`；FIFO 立刻拒绝，不会卡住。`WriteFile` 同样逐级创建和打开上级目录，拒绝把链接放在目录位置上，写到同目录的临时文件再改名替换。这样一条还在运行的命令就没法在检查和打开之间把目录换成指向 `~/.ssh` 或命令目录之外的链接。非 Unix 系统按名字打开，在规范化后的路径上做 `CheckRead`。

::: info 演进
`80aa076` 起 macOS 和 Windows 上的读写检查不区分大小写，此前 `read_file ~/.SSH/id_rsa` 能读到 `~/.ssh` 禁读的密钥。按检查过的路径打开来自 `b43d8b9`，整文件读取的上限来自 `185e608`。
:::

## 环境变量

命令的环境变量是白名单（`environ`）：从宿主进程只取 `PATH`、`HOME`、`USER`、`LOGNAME`、`SHELL`、`TMPDIR`、`TERM`、`LANG`、`TZ`、`LC_*` 和 `env_passthrough`，再叠上调用参数里的 `env`。宿主进程的其他变量不传给命令，提权运行时也一样。

Seatbelt 下运行的命令还会看到：

| 变量 | 条件 |
| --- | --- |
| `<marker>=seatbelt` | 宿主配了 `EnvMarker` |
| `<marker>_NETWORK_DISABLED=1` | 配了 `EnvMarker`，网络关闭 |
| 代理变量 | 走代理时，见[网络代理](#网络代理) |

每条命令（含提权的）还带一个随机标记 `<marker>_RUN_ID=<32 位十六进制>`，没配 marker 时是 `SANDBOX_RUN_ID`，用来[清理进程](#进程清理)。

## Seatbelt 配置

每次运行时 `seatbeltProfile` 现拼一段规则，经 `sandbox-exec -p` 传入。路径用 `-D KEY=VALUE` 参数传，规则里写 `(param "KEY")`，所以路径里的特殊字符不会破坏规则；含双引号、反斜杠或控制字符的路径不能写进正则，`New` 时报错。

Seatbelt 规则后面的覆盖前面的，所以顺序有讲究。

| 段 | 内容 |
| --- | --- |
| 基础 | `seatbelt_base.sbpl`：`(deny default)`，放开 `process-exec`、`process-fork`，只能给同沙箱的进程发信号，放开一批只读 `sysctl`，`/dev/null` 可写，`pty` |
| 读 | `(allow file-read*)`，加 `seatbelt_preferences.sbpl` 的偏好设置读取 |
| 写 | 只有 `workspace-write`：`(allow file-write* (subpath ...))`，覆盖命令目录、`extra_writable`、临时目录 |
| Unix socket | 允许创建 `AF_UNIX` socket |
| 网络 | 网络打开时二选一，见下节 |
| 拒绝（放最后） | 见下表 |

`seatbelt_base.sbpl`、`seatbelt_network.sbpl`、`seatbelt_preferences.sbpl` 取自 OpenAI Codex。

最后一段：

| 规则 | 目的 |
| --- | --- |
| `(deny mach-lookup (xpc-service-name-prefix ""))` | 不能查找 XPC 服务 |
| 保护名的 `(deny file-write* ...)` | 每个可写路径都生成，临时目录也包括在内 |
| 依赖目录的 `(allow file-write* ...)` | 放在保护名之后，重新放开 |
| `(deny file-clone (vnode-type DIRECTORY))` | 不能克隆目录 |
| `(deny file-read* file-write* (subpath ...))` | 禁读路径 |
| `(deny file-write* (subpath ...))` | 只读路径 |
| `(deny file-write-unlink ...)` | 保护路径在可写目录内的上级目录不能删除或改名 |
| `(deny system-fcntl (fcntl-command 80 110))` | 禁止这两个 fcntl 命令 |

前三条只在 `workspace-write` 下生成。保护路径上级目录那条规则针对的是绕路：把 `data` 的父目录改名再放一个新的，路径规则就管不到了。

保护名的正则都不区分大小写，前缀是 `^<可写路径>/(.*/)?`，所以任意层级都算。profile 里没有针对 `.git` 的规则，`TestTheProfileLeavesGitAlone` 守着这一点。

## 网络

`network`、`allowed_domains` 两项决定三种情况：

| 情况 | 条件 | Seatbelt 规则 |
| --- | --- | --- |
| 关闭 | `network: false` | 没有网络规则，`(deny default)` 生效 |
| 全开 | `network: true`，没有 `allowed_domains` | `(allow network-outbound)`、`(allow network-inbound)`，然后关闭 Unix socket，只留 mDNSResponder 和 `unix_sockets` |
| 代理 | `network: true`，有 `allowed_domains` | 只允许连 `localhost:<代理端口>` 和 `unix_sockets` |

打开网络的两种情况都加上 `seatbelt_network.sbpl`（DNS、证书校验等系统服务）和 `com.apple.TrustEvaluationAgent`。代理情况下进程没有别的出路，内核层面连不到代理以外的地址。`denied_domains` 必须和 `allowed_domains` 一起用，单独配置时 `New` 报错。

### 网络代理

每次 `Run` 或 `Start` 启动一个只属于这条命令的代理，监听 `127.0.0.1` 的随机端口，命令结束时关闭。同一个端口上看连接的第一个字节分流：

| 第一个字节 | 处理 |
| --- | --- |
| `0x05` | SOCKS5，交给 `go-socks5`，只开 CONNECT，不自己解析域名，名字原样进放行判断 |
| 其他 | HTTP，交给一个 `http.Server` |

HTTP 这一侧：`CONNECT` 接管连接建隧道（不写端口时是 443）；绝对 `http://` URL 的明文请求经 `httputil.ReverseProxy` 转发，它的连接同样经放行判断（不写端口时是 80），客户端连接可以保持；其他请求回 502，提示 HTTPS 要用 `CONNECT`。

代理的地址写进命令的环境变量：`HTTP_PROXY`、`HTTPS_PROXY`、`ALL_PROXY`（`socks5h`）及小写形式，`GRPC_PROXY` 及小写形式，`NODE_USE_ENV_PROXY=1`，`JAVA_TOOL_OPTIONS`（调用参数里的同名变量排在前面），并清空 `NO_PROXY`。不走环境变量的程序连不上网，内核规则挡住它们。

::: info 演进
v0.12.1 的代理是手写的 HTTP 和 SOCKS5 解析。`8ac5f3c` 改用 `httputil.ReverseProxy` 和 `go-socks5`，放行规则、内网规则和拦截记录不变；明文 HTTP 因此能保持客户端连接、转发分块的请求体。
:::

### 域名放行

域名条目是主机名、`*.域名`、`*` 或 IP 地址，可带 `:端口`，不接受协议、路径、`@`、`?`、`#` 和空白，在 `New` 时解析一次，写错就报错。比较前主机名转小写、去掉结尾的点。

| 条目 | 匹配 |
| --- | --- |
| `github.com` | 只有 `github.com` |
| `*.github.com` | 子域名，不含 `github.com` 本身 |
| `*` | 任意主机 |
| `example.com:8443` | 只有这个端口 |

`denied_domains` 先于 `allowed_domains`。不在放行名单里的连接被拒绝：HTTP 回 403，SOCKS 回 `0x02`（规则不允许）。其他失败（比如解析失败、连不上）HTTP 回 502，SOCKS 回 `0x05`（连接被拒）。

### 内网拦截

允许的域名可能解析到内网地址，这是 DNS 重绑定的入口。`proxy.dial` 在连接时解析（15 秒超时，IP 字面量不解析），逐个检查解析出的地址，命中 `sensitiveAddr` 的跳过，不去连接：

- 回环、未指定地址
- 私有地址，`100.64.0.0/10` 共享地址
- 链路本地、组播

例外是主机被条目原样写出：配 `localhost` 或 `127.0.0.1` 能连到本机，配 `*` 或 `*.example.com` 不行。

被拦下的连接记成 `network: blocked host:port (原因)`，原因是 "not in allowed_domains" 或解析到内网（提示 "allow it by name or address to reach it"），去重，最多 20 条，并进[拒绝原因报告](#拒绝原因报告)。

`PublicTransport` 是同一思路的 HTTP 客户端版本：`dialPublic` 只连公网地址，没有例外，不读环境变量里的代理。`web_fetch` 和云沙箱的 `Transport` 都用它；本机 `Sandbox.Transport` 是 `http.DefaultTransport`。

## 进程清理

命令结束不代表它启动的进程都结束了。`runProcess` 这样处理：

1. 用 `Setpgid` 把命令放进自己的进程组，环境变量里带上 `<marker>_RUN_ID` 标记。
2. 超时或取消时 `killRun` 杀掉整个进程组；命令正常结束后也调一次 `killRun`。
3. `killRun` 给进程组发 `SIGKILL`，再调 `killTagged`。

`killTagged`（只在 macOS 上有实现）处理脱离了进程组的后台进程：

- 用 `kern.proc.uid` 列出本用户进程，用 `kern.procargs2` 读环境，找到带标记的进程。
- 加上原进程组的成员，再沿父子关系和进程组扩展。
- 先全部发 `SIGSTOP`，再全部发 `SIGKILL`，让它们来不及派生新进程。
- 重复到找不到为止，最多 200 轮。

之后等输出管道排空，最多 2 秒。后台进程占着管道时，到时间就关掉管道。

`Start` 起的进程（stdio MCP 服务器）在 `Close` 时关掉标准输入，等它最多 2 秒，然后同样 `killRun`，再关掉代理；命令自己结束后最多 2 秒就不再等它的输出（`WaitDelay`）。

结果里退出码按以下规则：被信号杀死时是 `128 + 信号值`，`Signal` 字段是信号名。退出码非 0 是正常结果，不是错误。超时返回错误，内容是 "timed out after ... and was killed" 加上 stdout、stderr 各自最后 2000 字节；被取消时类似。

输出用 `cappedBuffer` 收集：保留前一半和后一半，丢弃的字节数写进中间的 `[… N bytes omitted …]`，结果标 `Truncated`。

::: info 演进
`77c2d72` 之前，`Start` 起的进程如果把 stderr 留给了自己的子进程，`Close` 会一直卡住，连带卡住用户的 MCP 服务器。
:::

## 拒绝原因报告

模型看到 "Operation not permitted" 时不知道是沙箱挡的还是别的原因。Seatbelt 的拒绝写在系统日志里，`denialLog` 把它们取回来。

1. `New` 时（macOS、非 `full-access`）启动一个常驻的 `log stream`，过滤条件是一个随机后缀，这个进程的 `Sandbox` 只听自己的日志。`Close` 时关掉它。
2. 每次运行生成标记 `OSBX<16 位十六进制>_<后缀>`，规则写成 `(deny default (with message "标记"))`，其他 deny 也带上这个 message。
3. 日志行匹配 `Sandbox: 进程(pid) deny(n) 操作 目标`，积累起来，遇到带标记的行时归到那次运行。
4. 只保留 `file-*`、`network-*`、`process-exec*` 操作，去掉 mDNSResponder 的噪音，同一条去重，每次最多 20 条。

命令失败（退出码非 0 或出错）时才等待：最多 500 毫秒，有拒绝且 200 毫秒没有新行就提前结束。成功的命令不报告拒绝，因为被挡掉的可能只是无关紧要的探测。

代理拦下的连接也加进来。结果写进 `Result.Denials`，`run_command` 的输出里是 `sandbox_denials`。命令以错误结束时，拒绝内容接在错误后面（"the sandbox denied: …"）。

`log stream` 启动失败不影响运行，只是没有这份报告。提权运行的命令不经 Seatbelt，也没有这份报告。

## 提权

提权指让一条命令离开沙箱运行。模型在 `run_command` 里传 `sandbox_permissions: "require_escalated"`（另一个取值是默认的 `use_default`）和一句 `justification`，说明命令需要沙箱不允许的什么，比如写 `/usr/local` 或连某个主机。工具描述告诉模型：只有命令因为沙箱失败时才这样做，不要用它绕过有意的禁止，不要给在沙箱里能跑的命令提权。

`escalation` 的前提：

| 情况 | 结果 |
| --- | --- |
| `Enforced` 为假 | 报错，本来就没有沙箱 |
| `CanEscalate` 为假 | 报错，这个沙箱不能离开 |
| 没有 `justification` | 报错 |

`CanEscalate` 为假时这两个参数根本不出现在工具的 schema 里。`claude` 工具不带这两个参数：在既受限又能提权的 Box 上它总是提权，理由是固定的一句（Claude Code 要网络和主目录里自己的设置）。

通过后 `Prepared.Escalated` 为真，`Sandboxed` 为假，进入权限判定：`untrusted` 和 `on-request` 下必须问用户，allow 规则不算数，也不提供"总是允许"，`acceptForSession` 只对完全相同的调用生效；`never` 下没有人可问，命令直接在沙箱外运行。`never` 下拦得住提权的只有 deny 规则。带说明符的 deny 读不懂某条命令时（比如 `sh -c "$X"`），这条命令被拒绝，而不是放行，见[审批与权限](/zh/engine/permissions#看不清的命令)。

批准后（`never` 下不经批准，直接这样执行）`Command.Unsandboxed` 为真，本机 `Sandbox` 不加 Seatbelt、不起代理，直接运行，环境变量白名单仍然生效。`run_command` 的结果带 `sandbox: "escalated: ran on the host without the sandbox"`。云沙箱的 `Remote` 拒绝 `Unsandboxed` 的命令。

::: info 演进
`never` 下提权直接运行来自 `7b6e720`。`4dde704` 起提权的审批不再带英文的理由，界面从冻结的执行内容自己说明；要模型写的说明也从"为什么必须在沙箱外"改成"需要沙箱不允许的什么"。
:::

## 云沙箱接入点

接入云沙箱只需实现 `Machine`，用服务商 SDK 的说法：一条命令加输出和退出码，按路径读写文件。

```go
type Machine interface {
	Run(ctx context.Context, c Command) (Result, error)
	Start(ctx context.Context, c Command, stderr io.Writer) (Process, error)
	Stat(ctx context.Context, path string) (fs.FileInfo, error)
	ReadDir(ctx context.Context, path string) ([]fs.DirEntry, error)
	Open(ctx context.Context, path string) (io.ReadCloser, error)
	WriteFile(ctx context.Context, path string, data []byte, perm fs.FileMode) error
	Close() error
}
```

`sandbox.Remote(m, roots, summary)` 把它包成 `Box`。创建、找回、唤醒、休眠机器由返回它的代码负责，网络规则也设在机器上。`Close` 只断开连接，机器和文件留给下一次。

`remote` 的语义和本机不同，因为一台机器只放一个用户的东西：

| 方法 | 行为 |
| --- | --- |
| `Enforced` | 真，机器本身就是限制 |
| `CanEscalate` | 假，`Unsandboxed` 的命令报错 |
| `CheckRead`、`Check` | 总是通过 |
| `CheckWrite` | 只要求在命令目录内 |
| `Canonical` | 只做路径清理，要求绝对路径 |
| `Executable` | 裸名字交给机器自己的 `PATH`；带路径的要存在且不是目录 |
| `Same` | 只认字符串相等 |
| `Move` | 先看目标：不存在就直接搬；是空目录就用 `rmdir` 删掉；非空就拒绝；看不到目标就停下。然后在机器里运行 `mv -f`，超时 10 分钟 |
| `Fingerprint` | 命令目录和 `summary` |
| `Transport` | `PublicTransport`，请求从引擎进程发出，这个进程的内网不是用户的 |

`machine` 传 `nil` 时只用来描述工具：工具描述里的目录和规则从这个 Box 来，实际运行由 `BoxFor` 或 `BoxIn` 给的 Box 完成。

命令、文件工具、附件读取、stdio MCP 服务器都经 Box，所以换成云沙箱后这些都在用户的机器里发生。

## 边界与已知问题

- **只有 macOS。** 非 macOS 上 `read-only` 和 `workspace-write` 报错，只能用 `full-access`，这时命令不受限制，`on-request` 下每条命令都要问。
- **云沙箱只有接口。** 仓库里 `Machine` 的实现只在测试里，没有接入任何服务商，见[云沙箱接入点](#云沙箱接入点)。
- **读取几乎不设限。** Seatbelt 规则是 `(allow file-read*)` 加禁读路径，`CheckRead` 只查禁读路径。不在[禁读名单](#禁读路径)里的文件，命令和读取工具都能读，而且不问用户。
- **`.git/hooks` 可写。** 写进去的钩子会在用户之后自己运行 git 时在沙箱外执行，见[保护名](#保护名)。
- **`never` 档下提权不问。** 离开沙箱的命令直接运行，能拦住它的只有 deny 规则，见[提权](#提权)。
- **不走代理的程序连不上网；只开网络时外网全开。** 域名名单模式下，不读代理环境变量的程序被内核挡住。`network: true` 但没配 `allowed_domains` 时，命令可以连任何地址，包括内网。
- **本机的 `Transport` 不拦内网。** 本机 `Sandbox.Transport` 返回 `http.DefaultTransport`，HTTP MCP 服务器的请求能到内网地址；只有云沙箱用 `PublicTransport`。
- **MCP 服务器不一定在沙箱里。** stdio 服务器经宿主给的 `Box` 启动，受不受限由那个 Box 决定，见[权限与沙箱](/zh/engine/skills-mcp#权限与沙箱)。
- **工作区工具不配 `BoxFor`、`BoxIn` 时所有用户共用一个本机沙箱。** 读写规则对所有用户相同，多用户部署要给每个用户自己的 Box。
- **找回脱离进程组的后台进程只在 macOS 上实现。** `killTagged` 在其他平台上没有实现，那里只杀进程组。

## 代码位置

| 位置 | 职责 |
| --- | --- |
| ollupi `pkg/sandbox/box.go` | `Box`、`ReadFile`、本机文件操作、`Executable`、`Move` |
| ollupi `pkg/sandbox/sandbox.go` | `Config`、`New`、`Run`、`Summary`、组装命令 |
| ollupi `pkg/sandbox/policy.go` | 模式、禁读路径、保护名、`validateRoot` |
| ollupi `pkg/sandbox/paths.go` | 路径规范化、不区分大小写的 `within` |
| ollupi `pkg/sandbox/seatbelt.go` | 拼接 Seatbelt 规则 |
| ollupi `pkg/sandbox/seatbelt_base.sbpl`、`seatbelt_network.sbpl`、`seatbelt_preferences.sbpl` | 固定规则 |
| ollupi `pkg/sandbox/proxy.go` | 网络代理 |
| ollupi `pkg/sandbox/domains.go` | 域名规则 |
| ollupi `pkg/sandbox/public.go` | 内网判断、`PublicTransport` |
| ollupi `pkg/sandbox/denials.go` | 从系统日志取拒绝原因 |
| ollupi `pkg/sandbox/process.go`、`process_unix.go`、`process_darwin.go` | 运行进程、`Start`、输出上限、进程清理 |
| ollupi `pkg/sandbox/files_unix.go`、`files_other.go` | 按检查过的路径打开和写入 |
| ollupi `pkg/sandbox/env.go` | 环境变量白名单 |
| ollupi `pkg/sandbox/read.go`、`write.go` | `CheckRead`、`CheckWrite` |
| ollupi `pkg/sandbox/remote.go` | `Machine`、`Remote` |
| ollupi `tool/builtin/workspace/config.go` | 配置项和默认值、agent 的保护名和禁读目录 |
| ollupi `tool/builtin/workspace/tool.go`、`dirs.go` | 选 Box：`Box`、`BoxFor`、`BoxIn` |
| ollupi `tool/builtin/workspace/execution.go` | 冻结命令、提权校验、执行 |
