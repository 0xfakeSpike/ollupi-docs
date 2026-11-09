# 多用户与分片部署

这一页讲怎样把引擎部署成多进程、多分片的服务：分片进程、路由器和目录库各起几个，用户怎样被放到分片上，进程挂掉时备用进程怎样接管。机制的细节见[分片与租约](/zh/engine/sharding)。

## 三个角色

一个进程打开一个 SQLite 文件，这个文件就是一个分片。要让同一时刻只有一个进程运行它，靠库里 `shard_lease` 的一行租约保证。

`Config.Lease` 是一个时长，设了才启用租约。`Agent.Start` 在恢复之前调用 `claimShard`：没拿到就每 L/3 重试一次，一直阻塞到拿到或 ctx 结束；拿到后每 L/3 续约。失去租约时调用 `OnLeaseLost`，取消 agent 的 ctx。配了租约时 `Start` 可能长时间不返回。

多进程部署由三层组成：

| 角色 | 起几个 | 说明 |
|---|---|---|
| 分片进程 | 每个分片一个，另加备用 | 备用进程用同样的 `Lease` 等待接管 |
| 路由器 | 任意个，无状态 | `gateway.NewRouter(authenticate, directory)`，`repo.Catalog` 实现 `Directory` |
| 目录库 | 一个 | `repo.OpenCatalog(path)`，参数是文件路径；保存 `shards` 和 `placements` 两张表 |

`repo.Catalog` 负责用户放置：`ShardOf(user)` 把新用户放进 `accepting` 且用户最少的分片，`Place(user, shard)` 由运维在用户有数据之前指定。`Publish(shard, address, accepting)` 由拿到租约的进程在 `Start` 返回后调用。租约的时间参数、围栏、`OnShard` 校验、令牌读法都在[分片与租约](/zh/engine/sharding)。

部署上的硬约束：

- 备用进程要能打开同一个分片文件，路由器和所有分片进程要能打开同一个目录库文件。引擎只通过 SQLite 文件协调，没有别的通道。
- 客户端只连路由器。分片进程的地址只写在目录库里，给路由器用。
- 登录在 Ollupi 之外完成。路由器和分片网关用同一个 `authenticate` 认出用户，分片这边再包一层 `gateway.OnShard`。

## 最小的多进程部署

下面是一个二进制、两种角色：`-role router` 起路由器，`-role shard` 起分片进程。同一个分片起两次就是一主一备。这段代码对着引擎 v0.11.3 编译通过，并在一台机器上按下面的命令跑过：路由、错分片拒绝、`kill -9` 后接管、正常退出后交接都和本页描述一致。模型名和 limits 与[把引擎嵌进服务](/zh/integrate/embed)的最小宿主相同。

```go
package main

import (
	"context"
	"errors"
	"flag"
	"fmt"
	"log"
	"net"
	"net/http"
	"net/url"
	"os"
	"os/signal"
	"strings"
	"syscall"
	"time"

	"github.com/0xfakeSpike/ollupi/agent"
	"github.com/0xfakeSpike/ollupi/agent/permission"
	"github.com/0xfakeSpike/ollupi/gateway"
	"github.com/0xfakeSpike/ollupi/pkg/llm"
	"github.com/0xfakeSpike/ollupi/repo"
)

func main() {
	role := flag.String("role", "", "shard or router")
	catalogPath := flag.String("catalog", "", "目录库文件，所有进程打开同一个；绝对路径")
	listen := flag.String("listen", "", "监听地址，如 :9001")
	shard := flag.String("shard", "", "分片 ID（shard）")
	home := flag.String("home", "", "分片的 home 目录，绝对路径（shard）")
	advertise := flag.String("advertise", "", "路由器连这个进程用的地址，如 http://10.0.0.1:9001（shard）")
	flag.Parse()

	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()

	catalog, err := repo.OpenCatalog(*catalogPath)
	if err != nil {
		log.Fatal(err)
	}
	defer catalog.Close()

	switch *role {
	case "router":
		err = runRouter(ctx, *listen, catalog)
	case "shard":
		err = runShard(ctx, *shard, *home, *listen, *advertise, catalog)
	default:
		err = errors.New("-role must be shard or router")
	}
	if err != nil && !errors.Is(err, context.Canceled) {
		log.Fatal(err)
	}
}

// authenticate 只核对令牌属于谁；登录在 Ollupi 之外。示例从环境变量读 "令牌=用户,令牌=用户"。
func authenticate(token string) (string, bool) {
	for _, pair := range strings.Split(os.Getenv("OLLUPI_TOKENS"), ",") {
		t, user, ok := strings.Cut(pair, "=")
		if ok && t != "" && t == token {
			return user, true
		}
	}
	return "", false
}

func runRouter(ctx context.Context, listen string, catalog *repo.Catalog) error {
	router, err := gateway.NewRouter(authenticate, catalog)
	if err != nil {
		return err
	}
	server := &http.Server{Addr: listen, Handler: router, ReadHeaderTimeout: 5 * time.Second}
	go func() {
		<-ctx.Done()
		shutdown, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancel()
		_ = server.Shutdown(shutdown)
	}()
	if err := server.ListenAndServe(); !errors.Is(err, http.ErrServerClosed) {
		return err
	}
	return nil
}

func runShard(ctx context.Context, shard, home, listen, advertise string, catalog *repo.Catalog) error {
	public, err := url.Parse(advertise)
	if err != nil || public.Hostname() == "" {
		return fmt.Errorf("-advertise %q is not a URL", advertise)
	}
	db, err := repo.Open(home)
	if err != nil {
		return err
	}
	defer db.Close()

	// 失去租约时停掉这个进程里所有用这个库的东西：网关、附属组件、agent。
	ctx, lost := context.WithCancel(ctx)
	defer lost()

	var srv *gateway.Server
	a := agent.New(agent.Config{
		Name:   "shard-" + shard,
		Models: []llm.Model{{Name: "gpt-5.2", Connection: "openai"}},
		Connections: map[string]llm.Client{
			"openai": llm.NewOpenAI("", os.Getenv("OPENAI_API_KEY"), 4, map[string]llm.Limits{
				"gpt-5.2": {Context: 400_000, Output: 128_000},
			}),
		},
		Settings:    permission.Settings{ApprovalPolicy: string(permission.OnRequest)},
		DB:          db,
		Slots:       32,
		UserSlots:   4,
		Lease:       15 * time.Second,
		OnLeaseLost: lost,
		OnEvent:     func(e agent.Event) { srv.Deliver(e) },
	})
	srv, err = gateway.NewServer(a, gateway.Options{
		DB:           db,
		Authenticate: gateway.OnShard(shard, catalog, authenticate),
		AllowedHosts: []string{public.Hostname()},
	})
	if err != nil {
		return err
	}

	// 备用进程停在这里，直到持有者退出或租约过期。
	if err := a.Start(ctx); err != nil {
		return err
	}
	// 先让 agent 停下（取消 ctx），再等它退出、释放租约，最后才轮到 db.Close。
	defer func() { lost(); a.Wait() }()

	// 拿到租约之后才监听和发布地址：之前路由器不该把人送到这里。
	ln, err := net.Listen("tcp", listen)
	if err != nil {
		return err
	}
	if err := catalog.Publish(shard, advertise, true); err != nil {
		ln.Close()
		return err
	}
	return srv.Serve(ctx, ln)
}
```

在一台机器上起一个路由器、两个分片、分片 `s1` 的一个备用（构建要带 `-tags sqlite_fts5`）：

```sh
export OLLUPI_TOKENS="tok-a=alice,tok-b=bob" OPENAI_API_KEY=...
D=/srv/ollupi

./ollupi -role router -listen :8080 -catalog $D/catalog.sqlite &
sleep 1  # 让路由器先把目录库建好，见下文
./ollupi -role shard -shard s1 -home $D/s1 -listen :9001 -advertise http://127.0.0.1:9001 -catalog $D/catalog.sqlite &
./ollupi -role shard -shard s1 -home $D/s1 -listen :9011 -advertise http://127.0.0.1:9011 -catalog $D/catalog.sqlite &
./ollupi -role shard -shard s2 -home $D/s2 -listen :9002 -advertise http://127.0.0.1:9002 -catalog $D/catalog.sqlite &
```

客户端连 `ws://<路由器>:8080/`，带 `Authorization: Bearer tok-a`，之后照[网关协议](/zh/integrate/protocol)握手。

这段代码里几处不能省：

| 地方 | 为什么 |
|---|---|
| `OnLeaseLost: lost` | 失去租约时，这个进程里其他用这个库的东西也要停，否则不走 `DB.Tx` 的写入还会成功，见[续约和失去租约](/zh/engine/sharding#续约和失去租约)。这里取消的 ctx 也是网关的，`Serve` 随之返回，进程退出 |
| `Start` 之后才 `Listen` 和 `Publish` | 备用进程在 `Start` 里等。先监听就会有连接直接打到它上面，而它还没在运行这个分片 |
| `gateway.OnShard` | 用户被放在别的分片时认证失败，绕过路由器直连错分片的连接不会在这里建出第二份用户数据 |
| `AllowedHosts` | 路由器转发时把 `Host` 改成分片地址的主机名；不在名单里时分片回 403 `host not allowed`。浏览器客户端还要在 `AllowedOrigins` 里写前端来源 |
| `Settings.ApprovalPolicy` | 默认权限层没有审批策略、别的层也没给时，`Start` 失败：`approval policy "" must be one of ["untrusted" "on-request" "never"]` |
| `defer func() { lost(); a.Wait() }()` | `Wait` 释放租约，下一个进程不用等它过期；`Wait` 之前必须先取消 agent 的 ctx，否则会一直等 |
| 绝对路径 | `repo.Open` 和 `repo.OpenCatalog` 拿路径拼 SQLite 的 `file:` URI，相对路径会失败：`storage: open run/catalog.sqlite: invalid uri authority: run` |

示例省掉的东西：工具 provider、定时任务和记忆这些附属组件（装法见[把引擎嵌进服务](/zh/integrate/embed)，它们都要在失去租约时一起停）、`ClientFor` 和 `BoxFor` 这些每用户资源（见[分片与租约的每用户资源](/zh/engine/sharding#每用户资源)），以及进程守护。失去租约的进程会正常退出，要靠 systemd 之类的守护把它重新拉起来，它重启后就成了新的备用。

## 目录库

`repo.OpenCatalog` 第一次打开文件时用 `AutoMigrate` 建表。v0.11.3 上实测，几个进程同时第一次打开同一个新文件时，有的会失败，报 ``table `shards` already exists`` 或 `database is locked`；表建好之后再并发打开没有出现这个问题。所以先单独起一个进程把目录库建好，再起其他进程，上面的启动命令就是这样做的。

| 操作 | 谁来做 | 时机 |
|---|---|---|
| `Publish(shard, address, accepting)` | 拿到租约的分片进程 | 每次 `Start` 返回之后；接管后新地址覆盖旧地址 |
| `Place(user, shard)` | 运维 | 用户有任何数据之前；用户已在别的分片时报错 `storage: user <user> is already on shard <shard>` |
| `ShardOf(user)` | 路由器（每个连接一次）、`OnShard`（每次认证一次） | 新用户在这里被放置 |
| 把分片设成不接新用户 | 运维，或分片进程以 `accepting = false` 发布 | 留给单个客户的分片 |

引擎不搬迁用户，也不会把用户从满了的分片移走。分片容量见[容量规划与限流](/zh/integrate/capacity)。

## 租约时长

`Config.Lease` 没有默认值，不设就不启用租约，进程假定自己是唯一的。设租约时长为 L：

| 设定 | 后果 |
|---|---|
| L 调大 | 续约写失败时容忍得更久，库短暂不可写不会让进程失去分片；但持有进程被 `kill -9` 或宕机后，备用要等更久才接管，最多约 L + L/3 |
| L 调小 | 接管更快；但每 L/3 一次的续约写更频繁，库稍有阻塞（续约失败超过 L）就失去分片，正在跑的轮次全部被取消，交给下一个持有者恢复 |
| 正常退出 | 与 L 无关的部分：`Wait` 释放了租约，备用最多等一次轮询，约 L/3 |

用上面的示例在一台机器上测过一次（L = 15 秒）：`kill -9` 持有者后，约 16 秒备用发布了新地址；`SIGTERM` 持有者后，约 4.3 秒备用发布了新地址。都在上表的上限之内。这是一次单机测量，没有负载，只说明时序和上表一致，不是接管耗时的基准。引擎自己的崩溃实验用 `-lease 1500ms`（`bench crash`，`bench/README.md`），接管耗时没有记录在结果里。

租约到没到期，是拿各进程自己的时钟比较的（见[租约行](/zh/engine/sharding#租约行)）。`expires_at` 由持有者按它的时钟写，备用按自己的时钟判断是否过期。由此推断：主备在不同机器上时，时钟偏差会直接加减到接管时间上；备用的时钟快了，会在持有者以为租约还有效时接管，这时只靠[围栏](/zh/engine/sharding#围栏)挡住旧持有者的事务写入。要保证机器之间时钟同步。

## 接管时客户端看到什么

| 阶段 | 客户端看到 |
|---|---|
| 持有者被杀或宕机 | WebSocket 断开 |
| 重连，新持有者还没发布地址 | 路由器仍按旧地址转发，连不上，回 503 `the user's shard cannot be reached now; try again`，路由器日志 `shard not reached` |
| 持有者正常退出 | 网关关掉连接（1001，`server shutting down`）；之后同上，直到备用发布地址 |
| 新持有者发布地址后重连 | 连接成功。`initialize` 之后，网关把这个用户所有待回答的审批和提问重发一遍 |
| 断线期间的事件 | 不补发。客户端用 `thread/read` 或 `thread/resume` 读库里的状态，见[连接模型](/zh/integrate/protocol#连接模型) |

断线那一刻正在跑的轮次留在库里，新持有者恢复它们：还没执行的工具调用照常执行，执行到一半的标成"可能已生效"而不重跑，见[崩溃恢复](/zh/engine/persistence#崩溃恢复)。所以客户端要做的只有一件事：遇到断线和 503 就退避重连。

## 还没有的

路线图第 5 项"可以跑起来的多用户部署"还没做：一条命令起一个网关、一个路由、两个分片，加一个具体的 `sandbox.Machine` 实现，多分片基准在它上面跑。在那之前，上面的示例只验证了路由和接管，没有验证多机部署、负载下的接管和多分片的容量；现有基准全部来自单分片，见[性能基准](/zh/benchmarks/)。见[路线图](/zh/roadmap)。

## 代码位置

| 仓库 | 路径 | 职责 |
|---|---|---|
| ollupi | `agent/lease.go` | `claimShard`、`keepShard`、失去租约 |
| ollupi | `agent/loop.go` | `Wait` 释放租约 |
| ollupi | `agent/agent.go` | `Config.Lease`、`OnLeaseLost`，`Start` 里先拿租约再恢复 |
| ollupi | `repo/shard.go` | `shard_lease`、`ClaimShard`、`ReleaseShard`、`Fence` |
| ollupi | `repo/catalog.go` | `OpenCatalog`、`Publish`、`Address`、`Place`、`ShardOf` |
| ollupi | `repo/db.go` | `openFile`：路径拼成 SQLite URI |
| ollupi | `gateway/router.go` | `Router`、`NewRouter`、`OnShard`、`tokenOf` |
| ollupi | `gateway/serve.go` | `Options`、`Serve`、`Host` 校验 |
| ollupi | `gateway/router_test.go` | 两个分片加路由器的测试，可作参照 |
| ollupi | `bench/crash.go` | 带 `-lease` 的崩溃与接管实验 |
