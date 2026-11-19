# 多用户与分片部署

这一页讲怎样把引擎部署成多进程、多分片的服务：分片进程、路由层和目录库各起几个，用户怎样被放到分片上，进程挂掉时备用进程怎样接管。机制的细节（租约、epoch 围栏、放置算法）见[分片与租约](/zh/engine/sharding)。

## 三个角色

一个库就是一个分片（shard）：一个 `Home` 目录下的 `data/store.sqlite`，里面住着放在这个分片上的所有用户，按用户隔离。引擎本身不知道分片：让一个进程作为分片运行的是 `shard` 包。`shard.Member` 在目录库里持有这个分片的租约（lease），同一时刻只有持有者运行引擎、对外服务；它退出后，等在租约上的备用进程接手，从停下的地方继续。

| 角色 | 起几个 | 用什么 |
|---|---|---|
| 分片进程 | 每个分片一个，另加备用 | `host.New` 装配引擎，`shard.Member.Run` 包住 `h.Run` 和 `h.Gateway.Serve`；网关的 `Admit` 填 `member.Admit` |
| 路由层 | 任意个，无状态 | 能用 Envoy 外部处理协议回调的负载均衡器（比如 Google Cloud 应用负载均衡器的 route extension）配 `router/extproc` 的 callout；没有这种负载均衡器、或 callout 放不下的连接，交给 `router.Router`。两者都用 `router.NewLocator(authenticate, catalog)` |
| 目录库 | 一个 | `catalog.Catalog`。现在的实现是 `catalog.OpenSQL(path)` 打开的 SQLite 文件，表 `shards`（地址、`accepting`、负载、租约）和 `placements`（用户在哪个分片） |

客户端只连一个地址，不知道自己在哪个分片。路由层每个握手查一次目录库：先认出用户，新用户就地放置，再拿到他的分片和持有者的地址。callout 把分片 ID 写进请求头 `x-ollupi-shard`，由负载均衡器按它转发并持有连接；`router.Router` 自己反向代理到持有者的地址。分片这边只核对连接是不是自己的用户（`Admit`），不是的回 503 加 `Retry-After`。

部署上的硬约束：

- **备用进程要能打开同一个分片库，所有分片进程和路由层要能打开同一个目录库。** `catalog.SQL` 是一个 SQLite 文件；要让目录库不依赖某一台机器，在协调服务或单独部署的数据库上实现 `catalog.Catalog`，见[扩展点](/zh/integrate/extend#目录库)。
- **只有持有者监听端口。** 备用进程在 `Member.Run` 里等租约，不监听，所以负载均衡器的健康检查（`GET /healthz`）只会在持有者那里得到 200。
- **登录在 Ollupi 之外完成。** 路由层和分片网关用同一个 `authenticate` 认出用户。

## 最小的多进程部署

下面是一个二进制、三种角色：`-role router` 起路由器，`-role callout` 起负载均衡器的 callout，`-role shard` 起分片进程。同一个分片起两次就是一主一备。这段代码对着引擎 v0.17.2 编译并通过 `go vet`；v0.17.1 时在一台机器上按下面的命令跑过：路由、放置、错分片拒绝、`kill -9` 后接管、正常退出后交接都和本页描述一致（callout 只编译过，没有接负载均衡器跑）。模型名和 limits 与[最小宿主](/zh/integrate/embed#最小宿主程序)相同。

```go
package main

import (
	"context"
	"errors"
	"flag"
	"log"
	"net"
	"net/http"
	"net/url"
	"os"
	"os/signal"
	"strings"
	"syscall"
	"time"

	"github.com/0xfakeSpike/ollupi/auth"
	"github.com/0xfakeSpike/ollupi/catalog"
	"github.com/0xfakeSpike/ollupi/gateway"
	"github.com/0xfakeSpike/ollupi/host"
	"github.com/0xfakeSpike/ollupi/pkg/llm"
	"github.com/0xfakeSpike/ollupi/pkg/sandbox"
	"github.com/0xfakeSpike/ollupi/policy"
	"github.com/0xfakeSpike/ollupi/router"
	"github.com/0xfakeSpike/ollupi/router/extproc"
	"github.com/0xfakeSpike/ollupi/shard"
	extprocv3 "github.com/envoyproxy/go-control-plane/envoy/service/ext_proc/v3"
	"golang.org/x/sync/errgroup"
	"google.golang.org/grpc"
)

func main() {
	role := flag.String("role", "", "shard, router or callout")
	catalogPath := flag.String("catalog", "", "目录库文件，所有进程打开同一个；绝对路径")
	listen := flag.String("listen", "", "监听地址，如 :9001")
	id := flag.String("shard", "", "分片 ID（shard）")
	home := flag.String("home", "", "分片的 home 目录，绝对路径（shard）")
	advertise := flag.String("advertise", "", "路由器连这个进程用的地址，如 http://10.0.0.1:9001（shard）")
	flag.Parse()

	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()

	cat, err := catalog.OpenSQL(*catalogPath)
	if err != nil {
		log.Fatal(err)
	}
	defer cat.Close()

	switch *role {
	case "router":
		err = runRouter(ctx, *listen, cat)
	case "callout":
		err = runCallout(ctx, *listen, cat)
	case "shard":
		err = runShard(ctx, *id, *home, *listen, *advertise, cat)
	default:
		err = errors.New("-role must be shard, router or callout")
	}
	if err != nil {
		log.Fatal(err)
	}
}

// authenticate 只核对令牌属于谁；登录在 Ollupi 之外。示例从环境变量读 "令牌=用户,令牌=用户"。
func authenticate(_ context.Context, token string) (string, error) {
	for pair := range strings.SplitSeq(os.Getenv("OLLUPI_TOKENS"), ",") {
		t, user, ok := strings.Cut(pair, "=")
		if ok && t != "" && t == token {
			return user, nil
		}
	}
	return "", auth.ErrUnknownToken
}

func runRouter(ctx context.Context, listen string, cat catalog.Catalog) error {
	locator, err := router.NewLocator(authenticate, cat)
	if err != nil {
		return err
	}
	server := &http.Server{Addr: listen, Handler: router.NewRouter(locator), ReadHeaderTimeout: 5 * time.Second}
	go func() {
		<-ctx.Done()
		shutdown, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancel()
		server.Shutdown(shutdown)
	}()
	if err := server.ListenAndServe(); !errors.Is(err, http.ErrServerClosed) {
		return err
	}
	return nil
}

func runCallout(ctx context.Context, listen string, cat catalog.Catalog) error {
	locator, err := router.NewLocator(authenticate, cat)
	if err != nil {
		return err
	}
	ln, err := net.Listen("tcp", listen)
	if err != nil {
		return err
	}
	server := grpc.NewServer()
	extprocv3.RegisterExternalProcessorServer(server, extproc.New(locator))
	go func() {
		<-ctx.Done()
		server.GracefulStop()
	}()
	return server.Serve(ln)
}

func runShard(ctx context.Context, id, home, listen, advertise string, cat catalog.Catalog) error {
	public, err := url.Parse(advertise)
	if err != nil || public.Hostname() == "" {
		return errors.New("-advertise must be a URL such as http://10.0.0.1:9001")
	}
	member := &shard.Member{ID: id, Address: advertise, Accepting: true, Catalog: cat, TTL: 15 * time.Second}

	h, err := host.New(ctx, host.Config{
		Home:   home,
		Name:   "shard-" + id,
		Models: []llm.Model{{Name: "gpt-5.2", Connection: "openai"}},
		Connections: map[string]llm.Client{
			"openai": llm.NewOpenAI("", os.Getenv("OPENAI_API_KEY"), 4, map[string]llm.Limits{
				"gpt-5.2": {Context: 400_000, Output: 128_000},
			}),
		},
		Permissions: policy.Settings{ApprovalPolicy: string(policy.OnRequest)},
		Boxes:       func(string) (sandbox.Box, error) { return sandbox.Here() },
		Gateway: &gateway.Options{
			Authenticate: authenticate,
			Admit:        member.Admit,
			AllowedHosts: []string{public.Hostname()},
		},
	})
	if err != nil {
		return err
	}
	defer h.Close()

	// 备用进程停在 Run 里，直到持有者退出或租约过期；拿到之后才监听。
	return member.Run(ctx, h.Store, func(ctx context.Context) error {
		ln, err := net.Listen("tcp", listen)
		if err != nil {
			return err
		}
		g, ctx := errgroup.WithContext(ctx)
		g.Go(func() error { return h.Run(ctx) })
		g.Go(func() error { return h.Gateway.Serve(ctx, ln) })
		return g.Wait()
	})
}
```

在一台机器上起一个路由器、两个分片、分片 `s1` 的一个备用（构建要带 `-tags sqlite_fts5`）：

```sh
export OLLUPI_TOKENS="tok-a=alice,tok-b=bob" OPENAI_API_KEY=...
D=/srv/ollupi

./ollupi -role router -listen :8080 -catalog $D/catalog.sqlite &
./ollupi -role shard -shard s1 -home $D/s1 -listen :9001 -advertise http://127.0.0.1:9001 -catalog $D/catalog.sqlite &
./ollupi -role shard -shard s1 -home $D/s1 -listen :9011 -advertise http://127.0.0.1:9011 -catalog $D/catalog.sqlite &
./ollupi -role shard -shard s2 -home $D/s2 -listen :9002 -advertise http://127.0.0.1:9002 -catalog $D/catalog.sqlite &
```

客户端连 `ws://<路由器>:8080/`，带 `Authorization: Bearer tok-a`，之后照[网关协议](/zh/integrate/protocol)握手。有负载均衡器时，把 callout 配成它的外部处理服务，按请求头 `x-ollupi-shard` 把连接路由到对应分片的后端组，默认后端指向路由器。

这段代码里几处不能省：

| 地方 | 为什么 |
|---|---|
| `member.Run` 包住 `Listen`、`h.Run` 和 `Serve` | 备用进程在 `Run` 里等租约。先监听就会有连接直接打到它上面，而它还没在运行这个分片；只在持有时监听，健康检查也就只认持有者 |
| `Admit: member.Admit` | 用户放在别的分片时回 503 加 `Retry-After`，绕过路由层直连错分片的连接不会在这里建出第二份用户数据 |
| `AllowedHosts` | `router.Router` 转发时把 `Host` 改成分片地址的主机名；不在名单里时分片回 403 `host not allowed`。浏览器客户端还要在 `AllowedOrigins` 里写前端来源 |
| `Address` 用路由层连得到的地址 | 它随租约写进目录库，`router.Router` 照它转发 |
| 绝对路径 | `Home` 和目录库路径都拼成 SQLite 的 `file:` URI，相对路径会失败：`storage: open run/catalog.sqlite: invalid uri authority: run` |
| 进程守护 | 失去租约时 `member.Run` 取消 `serve` 的 ctx，等它返回，然后返回 `shard s1: store: a later holder of the shard writes to it now`，进程以错误退出。要靠 systemd 之类的守护把它重新拉起来，它重启后就成了新的备用 |

示例省掉的东西：命令和文件工具、`ClientFor`、云沙箱这些每用户资源（见[扩展点](/zh/integrate/extend)），`Member.Load`（不填时报 0，新用户只按用户数在两个候选里选），以及记忆模型。

::: info 演进
v0.12.1 时，租约是 `agent.Config.Lease`，存在分片自己的库里（`shard_lease`），拿到租约的进程再调 `Catalog.Publish` 发布地址，分片网关用 `gateway.OnShard` 核对用户，错分片回 401。`6282176`（v0.13.0）把路由移进 `router` 包、按负载放置新用户，错分片改成 503；`48c8454`（v0.16.0）把租约移进目录库、和地址放在同一行，加上 epoch 围栏，`Publish` 随之消失，引擎不再知道分片，分片进程由 `shard.Member` 运行；`de6eb86` 把目录库换成 `catalog.Catalog` 接口，租约只按目录库的时钟判断。
:::

## 目录库

`catalog.OpenSQL(path)` 打开或新建目录库，按 `catalog/migrations` 建表和迁移。几个进程可以同时第一次打开同一个新文件（`catalog/catalog_test.go` 的 `TestProcessesShareACatalog`），不用先单独起一个进程建库。

| 操作 | 谁来做 | 时机 |
|---|---|---|
| `Acquire`：拿租约，同时写下地址和 `accepting` | `shard.Member.Run` | 启动时，没拿到就每 TTL/3 再试一次 |
| `Renew`：续约，同时报负载 | 持有者 | 每 TTL/3 一次 |
| `Release`：放掉租约 | 持有者 | `Member.Run` 返回前，有 10 秒超时 |
| `Locate`：认出用户后找分片，新用户就地放置 | 路由器和 callout | 每个握手一次 |
| `ShardOf`：只查不放 | `member.Admit` | 用户连到这个分片进程时，直到通过一次为止 |
| `Place(user, shard)`：把用户钉在某个分片 | 运维 | 用户有任何数据之前；用户已在别的分片时报错 `catalog: user <user> is already on shard <shard>` |

新用户放在随机抽出的两个 `accepting` 分片里负载较小的那个，负载相同时取用户少的；只有一个分片接新用户时就是它。负载是各持有者在续约时报的 `Member.Load()`，用什么量由部署决定。

让一个分片不再接新用户：把它的 `Member.Accepting` 设成 false，重启持有者，`Acquire` 会写下新值；已经放在上面的用户照常服务。引擎不搬迁用户，也不会把用户从满了的分片移走。分片容量见[容量规划与限流](/zh/integrate/capacity)。

::: info 演进
v0.12.1 时几个进程同时第一次打开同一个新目录库，有的会失败（``table `shards` already exists`` 或 `database is locked`），所以要先单独起一个进程把库建好。`0cfd5ca`（v0.14.0）让几个进程可以同时打开、同时写同一个目录库。
:::

## 租约时长

`shard.Member.TTL` 没有默认值，必须为正。设租约时长为 L：

- 备用进程每 L/3 试一次 `Acquire`。
- 持有者每 L/3 续约一次。目录库按自己的时钟把租约延到续约时刻加 L；持有者从发出续约请求之前开始算，只认 L 的 9/10，续约一直失败、过了这个时间就自己放弃（取消引擎），保证它在别的进程能拿到之前先停。

| 设定 | 后果 |
|---|---|
| L 调大 | 目录库短暂不可写时更不容易失去分片；但持有者被 `kill -9` 或宕机后，备用要等更久才接管，最长约 L + L/3 |
| L 调小 | 接管更快；但续约写更频繁，目录库稍有阻塞（续约失败超过 0.9 L）就失去分片，正在跑的轮次被取消，交给下一个持有者接着跑 |
| 正常退出 | 与 L 的关系只在轮询：持有者退出时 `Release` 放掉了租约，备用最多等一次轮询，约 L/3 |

用上面的示例在一台机器上测过一次（v0.17.1，L = 15 秒，没有负载）：`kill -9` 持有者后约 10 秒备用拿到租约；`SIGTERM` 持有者后约 4 秒。都在上表的上限之内。这只说明时序和上表一致，不是接管耗时的基准。引擎自己的接管实验是 `bench crash -lease 1500ms`，结果还没有用 `run.sh` 测过（`bench/README.md`）。

租约是否过期由目录库判断：`catalog.SQL` 在 SQL 里用 `julianday('now')` 取时间，也就是执行这条语句的进程所在机器的时钟。由此推断：所有进程在一台机器上时只有一个时钟；进程分在几台机器上、共用一个 SQLite 文件时，各机器的时钟偏差会加减到接管时间上，这时更该换成协调服务上的目录库。旧持有者在租约过期后还没停下时，它的写入被 epoch 围栏挡住（`store.ErrShardLost`），见[分片与租约](/zh/engine/sharding)。

## 接管时客户端看到什么

| 阶段 | 经 `router.Router` 时客户端看到 |
|---|---|
| 持有者被杀或宕机 | WebSocket 断开（或心跳超时后断开） |
| 重连，旧租约还没过期 | 路由器仍按旧地址转发，连不上，回 503 `the user's shard cannot be reached now; try again` |
| 旧租约已过期或已放掉，备用还没拿到 | 回 503 `no process holds the user's shard now; try again` |
| 持有者正常退出 | 网关以 1001 `server shutting down` 关掉连接；之后同上一行，直到备用拿到租约 |
| 新持有者拿到租约后重连 | 连接成功。`initialize` 之后，网关把这个用户所有待回答的审批和提问重发一遍 |
| 断线期间的变化 | 不补发。客户端重读它关心的会话，见[客户端](/zh/integrate/client) |

路由器的这两种 503 不带 `Retry-After`，客户端按协议退避重连；分片自己回的 503（`Admit` 拒绝、准入限流、令牌暂时查不了）带 `Retry-After`。

断线那一刻正在跑的轮次留在库里，新持有者的调度器接着跑它们：已经写下、还没开始的工具调用照常执行，开始了没有结果的标成被切断、提示先核实，不会重跑，见[持久化](/zh/engine/persistence)。所以客户端要做的只有一件事：遇到断线和 503 就退避重连。

## 还没有的

路线图第 5 项"可以跑起来的多用户部署"还没做：一条命令起一个网关、一个路由、两个分片，加一个具体的 `sandbox.Machine` 实现。在那之前，上面的示例只验证了单机上的路由和接管，没有验证多机部署、负载下的接管和多分片的容量。`bench` 的 `conns`（连接与重连风暴，含经路由器）和 `users`（一个分片上的多用户）实验已经写好，结果还没测；现有基准全部来自单分片，见[性能基准](/zh/benchmarks/)和[路线图](/zh/roadmap)。

## 代码位置

| 路径 | 职责 |
|---|---|
| `shard/shard.go` | `Member`：等租约、围栏、续约、失去租约、放掉租约、`Admit` |
| `catalog/catalog.go`、`catalog/sql.go`、`catalog/migrations/` | `Catalog` 接口、SQLite 实现、放置算法 |
| `router/router.go` | `Locator`、`Router`、路由器的 HTTP 回复 |
| `router/extproc/extproc.go` | 负载均衡器的 callout，`x-ollupi-shard` |
| `store/sqlite/sqlite.go` | `Fence`、每次写入检查 epoch |
| `gateway/server.go`、`gateway/serve.go` | `Admit`、`/healthz`、关闭时的 1001 |
| `bench/crash.go` | 带 `-lease` 的崩溃与接管实验，`shard.Member` 的一个用法 |
| `bench/conns.go` | 经路由器的连接实验，`router.NewLocator` 和 `router.NewRouter` 的一个用法 |
