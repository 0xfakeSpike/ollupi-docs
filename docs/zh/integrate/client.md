# 写一个客户端

这一页讲怎样写一个正确的网关客户端：怎样连上、断了怎样重连、本地状态怎样和引擎保持一致、审批和提问怎样回答。线上有哪些方法、通知和错误码见[网关协议](/zh/integrate/protocol)，每个类型的字段见[协议类型](/zh/integrate/protocol-types)，这里只讲把它们用对。

桌面端是现成的参照实现：`packages/client` 是类型化的连接，`packages/core/src/timeline.ts` 把通知合进本地状态，`apps/desktop/src/renderer/src/gateway/session.ts` 管连接和重连。下文提到"桌面端的做法"都指这几个文件。

本页的代码和行为对着引擎 v0.12.0 实际跑过：一个最小宿主（网关加一个流式输出的假 OpenAI 服务，和引擎自己的 `TestTrafficMatchesContract` 同一做法）跑在本机，下面的客户端连上去，走通了普通回答、审批的接受和拒绝、结构化提问、错误令牌；"连接""审批和提问""发消息"几节里标了"实测"的行为，都来自对这个网关的脚本化试验。

## 最小客户端

Node 22 自带 `WebSocket`，不需要依赖。它连上网关，初始化，新建一个会话（thread），发一条消息，把回答的增量打印出来，按参数自动接受或拒绝审批，回答提问时选第一个选项，这一轮（turn）结束就退出。

```js
// node client.mjs <ws-url> <token> "<message>" [--approve]
// A minimal Ollupi gateway client: Node 22+, no dependencies.
const [url, token, text, flag] = process.argv.slice(2)
const approve = flag === '--approve'

// The token goes in the subprotocol, never in the URL.
const ws = new WebSocket(url, ['ollupi.token', token])
const pending = new Map() // our request id -> {resolve, reject}
let nextId = 0
let threadId

function send(msg) {
  ws.send(JSON.stringify({ jsonrpc: '2.0', ...msg }))
}

function call(method, params = {}) {
  const id = ++nextId
  send({ id, method, params })
  return new Promise((resolve, reject) => pending.set(id, { resolve, reject }))
}

// Server requests: approvals and questions. The reply carries the request's
// id exactly as it came (a JSON number).
const requests = {
  'item/toolCall/requestApproval': (p) => {
    const decision = approve ? 'accept' : 'decline'
    console.log(`\n[approval] ${p.tool} ${JSON.stringify(p.arguments)} -> ${decision}`)
    return { decision }
  },
  'item/tool/requestUserInput': (p) => {
    const answers = {}
    for (const q of p.questions) answers[q.id] = { answers: [q.options?.[0]?.label ?? 'yes'] }
    console.log(`\n[question] ${p.questions.map((q) => q.question).join(' / ')} -> ${JSON.stringify(answers)}`)
    return { answers }
  },
}

// Notifications may arrive before the reply to the call that caused them,
// so state is keyed by threadId, not by waiting for replies.
const notifications = {
  'item/agentMessage/delta': (p) => p.threadId === threadId && process.stdout.write(p.delta),
  'item/completed': (p) => {
    if (p.threadId === threadId && p.item.type === 'toolCall') console.log(`\n[tool] ${p.item.tool}: ${p.item.status}`)
  },
  'turn/completed': (p) => {
    if (p.threadId !== threadId) return
    console.log(`\n[turn] ${p.turn.status}${p.turn.error ? ': ' + p.turn.error : ''}`)
    ws.close(1000)
  },
  error: (p) => console.error(`\n[error] ${p.message}`),
}

ws.onmessage = ({ data }) => {
  const m = JSON.parse(data)
  if (m.method && m.id !== undefined) {
    const handle = requests[m.method]
    if (!handle) return send({ id: m.id, error: { code: -32601, message: `no handler for ${m.method}` } })
    return send({ id: m.id, result: handle(m.params) })
  }
  if (m.method) return notifications[m.method]?.(m.params)
  const p = pending.get(m.id)
  if (!p) return
  pending.delete(m.id)
  m.error ? p.reject(Object.assign(new Error(m.error.message), { code: m.error.code })) : p.resolve(m.result)
}

// A refused upgrade (401, 403, 503) shows up only as an error event: the
// WebSocket API does not expose the HTTP status.
ws.onerror = () => {
  if (ws.readyState !== WebSocket.OPEN) {
    console.error(`cannot connect to ${url}`)
    process.exitCode = 1
  }
}

ws.onclose = ({ code, reason }) => {
  for (const p of pending.values()) p.reject(new Error(`closed ${code} ${reason}`))
  if (code !== 1000) {
    console.error(`connection closed: ${code} ${reason}`)
    process.exitCode = 1
  }
}

ws.onopen = async () => {
  try {
    const init = await call('initialize', { clientInfo: { name: 'example-client', version: '0.1.0' } })
    send({ method: 'initialized', params: {} })
    console.log(`server ${init.serverInfo.name} ${init.serverInfo.version}, contract ${init.protocolSha256.slice(0, 12)}`)
    const { thread } = await call('thread/start', { title: 'example', permissions: {} })
    threadId = thread.id
    await call('turn/start', { threadId, input: [{ type: 'text', text }] })
  } catch (err) {
    console.error(`failed: ${err.code ?? ''} ${err.message}`)
    ws.close(1000)
    process.exitCode = 1
  }
}
```

对一个审批策略为严格（`untrusted`）、模型会调用 `run_command` 的网关，带 `--approve` 跑一次的输出：

```text
$ node client.mjs ws://127.0.0.1:18787/ secret "run it" --approve
server ollupi (devel), contract 87fd0377b058

[approval] run_command {"program":"echo","args":["hi"]} -> accept

[tool] run_command: completed
Hello, world.
[turn] completed
```

不带 `--approve` 时这次调用以 `declined` 结束，agent 收到"工具使用已停止"的提示后照常写完回答，这一轮仍是 `completed`。令牌错误时只打印 `cannot connect to ...`，退出码 1。

它故意省掉了重连、本地状态和多个会话，这些是下面各节的内容。真实客户端至少还要做到"[重连](#重连)"和"[先订阅，再读](#先订阅-再读)"两节。

## 连接

### 认证与握手

令牌只有两种传法：`Authorization: Bearer <token>` 头，或者浏览器和 Node 自带的 `WebSocket` 用的子协议 `["ollupi.token", token]`。两种都不进 URL，细节见[认证](/zh/integrate/protocol#认证)。

握手的顺序有一个要求：**在发 `initialize` 之前就把服务端请求的处理函数挂好。** 网关在 `initialize` 的回复入队之后立刻把这个用户所有待回答的审批和提问重发一遍（`gateway/server.go` 的 `initialize` 返回的 `after`），不等客户端的 `initialized` 通知。处理函数还没挂上时，客户端只能回一个错误，网关只记日志，这些请求要等下一次 `thread/resume` 或重连才会再来（实测）。上面的例子在建连接时就定好了 `requests` 表；桌面端在 `initialize` 返回后、让出事件循环之前同步挂上处理函数，效果一样。

`initialized` 通知照发：契约里有它，网关收到后什么也不做。

### 关闭码

连接建立之后，网关这一侧关闭连接只用下面几种关闭码（`gateway/server.go`、`pkg/jsonrpc/jsonrpc.go`）：

| 关闭码 | reason | 什么时候 | 客户端该做的 |
|---|---|---|---|
| 1001 | `server shutting down` | 网关所在的 HTTP 服务正在关闭，比如发版或分片交接 | 退避重连。多分片时路由器在新进程发布地址之前回 503，见[接管时客户端看到什么](/zh/integrate/deploy#接管时客户端看到什么) |
| 1008 | `replaced by a newer connection` | 同一个用户开了新连接，旧的被换掉 | 不要自动重连，否则两个客户端会互相顶掉。这是本页的建议，引擎和桌面端都没有专门处理 |
| 1008 | `client is not reading fast enough` | 出站队列超过 16 MiB，见[传输](/zh/integrate/protocol#传输) | 重连并重读状态。期间的通知已经丢了 |
| 1011 | `write failed`、`connection error`、`pending requests could not be read` | 写超时（10 秒）、读循环出错、初始化时读待回答请求失败 | 退避重连 |
| 1006 | （无） | 网络断开、进程被杀，没有关闭帧 | 退避重连 |

握手阶段的拒绝是 HTTP 状态码：401 令牌不对，403 `Host` 或 `Origin` 不在名单里，500 用户行建不出来，路由器另有 503（分片暂时连不上）。浏览器和 Node 自带的 `WebSocket` 拿不到这个状态码，只给一个 `error` 事件；Node 22 实测连 `close` 事件都没有，只有 `error`。所以这类客户端分不出"令牌错了"和"分片在交接"，只能都按可重试处理、加上退避和上限，把最后一次失败显示给用户。Go 的 `coder/websocket` 的 `Dial` 会返回 `*http.Response`，能看到状态码，可以对 401、403 直接放弃。

### 重连

网关不缓存事件：断线期间的通知不补发（`Deliver` 只投给已初始化的当前连接）。所以重连不是"接着收"，而是"重新读一遍"。桌面端的做法：

1. 退避：第 n 次失败后等 `min(5000, 250 × 2ⁿ)` 毫秒，一直重试到后端换了地址或令牌（`session.ts` 的 `MAX_BACKOFF_MS`）。
2. 连上、`initialize`，比较 `protocolSha256`（见[版本兼容](#版本兼容)）。
3. 挂上所有通知监听和服务端请求处理函数。
4. 按顺序重读每块状态：执行环境、工作区、会话列表、打开着的会话（`thread/resume`）、模型、工具、定时任务、设置。
5. 重读期间连接又断了，就整轮重来；只有全部读完才开始监视关闭。

第 5 步还有一层用意：同一时刻只能有一个重连循环。两个循环会各自开连接，按"每个用户一条连接"互相替换（1008），永远停不下来。

打开着的会话用 `thread/resume` 而不是 `thread/read`：两者返回同样的一页，`thread/resume` 回复之后还会把这个会话和它正在等的子 agent 的待回答请求再发一遍（`gateway/threads.go` 的 `threadPage(true)`）。已经在这条连接上发过、还没回答的请求不会重复发（`conn.asked`，实测）。重连后的新一页怎样和已经加载的旧条目合并，见下一节的[分页](#分页和-seq)。

## 本地状态

### 先订阅，再读

`thread/read`、`thread/resume`、`cron/list` 在读库和回复入队之间持有这条连接的 `deliver` 锁，事件不会插到读和回复之间（`threadPage` 里的 `c.deliver.Lock()`）。由此得到的保证是：回复之后收到的通知，描述的都是回复里那份状态之后的变化。

要用上这个保证，客户端必须在发读请求之前就开始接收通知，并在回复到达后把它之后的通知依次合进去。反过来先读、再挂监听，读和挂之间的通知就丢了。桌面端的连接循环先 `bind`（挂监听）再 `sync`（读），就是这个原因。

### 通知可能先于回复

网关在处理请求时同步发事件，所以通知常常比引起它的那个调用的回复先到。实测的顺序：

| 调用 | 回复之前已经收到 |
|---|---|
| `thread/start` | `thread/started` |
| `turn/start`（会话空闲） | `turn/started`（`ready`）、用户消息的 `item/started` 和 `item/completed`、`thread/status/changed`（`active`） |
| `turn/start`（已有进行中的一轮） | `turn/queued` |
| `turn/interrupt`（这一轮在等审批） | 等审批的调用的 `item/completed`（`failed`）、`turn/completed`（`interrupted`）、`thread/status/changed`（`idle`） |

所以客户端不能"等回复到了再开始处理通知"，状态要按 `threadId`、`turnId`、`itemId` 归档，而不是按调用。上面的最小客户端在 `thread/start` 回复之前收到的通知会被忽略，因为那时还不知道 `threadId`；对它没有影响，因为它只关心之后的事。

回复里带的行也可能比已经收到的通知旧：比如一轮很快跑完，`turn/completed` 可能先于 `turn/start` 的回复入队。由代码推断，不是实测：两者分别由 agent 的调度循环和网关的读循环写进同一个出站队列，中间没有锁。稳妥的做法是用回复里的行只补本地还没有的记录，已有同 `id` 的行时以通知为准。

### 按行替换

`turn/*` 和 `item/*` 通知带的是发出那一刻库里的完整行，客户端直接按 `id` 替换，不需要自己推导状态变化。桌面端 `timeline.ts` 的 `applyEvent` 就是这样做的：

| 通知 | 合并方式 |
|---|---|
| `turn/queued`、`turn/started`、`turn/completed` | 按 `turn.id` 替换这一轮，并用通知里的 `thread` 替换会话行 |
| `item/started`、`item/updated`、`item/completed` | 按 `item.id` 替换条目 |
| `item/agentMessage/delta`、`item/reasoning/textDelta` | 把 `delta` 接到对应条目的 `text` 后面 |
| `thread/started`、`thread/changed` | 替换会话行；`thread/changed` 的 `thread` 为 `null` 表示已删除 |

### 增量

增量只走事件，不补发。网关保证先发条目的 `item/started` 再发它的增量，并在 `item/completed` 里带完整的 `text`。所以：

- 收到一条本地没有的条目的增量，直接丢掉，等 `item/completed` 的完整文本。桌面端的 `appendDelta` 就是这样做的。
- 断线重连后，正在输出的回答从 `thread/resume` 读到的 `text` 接着往下拼，读到的是落库那一刻的内容，之后的增量照常追加。

### 分页和 seq

`thread/read` 和 `thread/resume` 按条目的 `seq` 分页：`seq` 在一个会话内唯一递增（`items` 表的唯一索引 `(thread_id, seq)`），每页取最新的若干条、按 `seq` 升序返回，`beforeSeq` 取更早的一页。`turns` 不分页，每次都是全部。限额见[会话](/zh/integrate/protocol/threads)。

本地合并的三种情况，桌面端各有一个函数：

| 情况 | 做法 |
|---|---|
| 往上翻页（`beforeSeq` = 本地最早的 `seq`） | 新一页的条目去掉本地已有的 `id`，接在前面，`hasMore` 取新一页的（`prependPage`） |
| 重连后重读最新一页 | 用新一页替换本地的尾部；本地比新一页最早的 `seq` 还旧的条目保留，它们属于已经结束的轮次，不会再变（`refreshFromPage`） |
| 实时通知 | 按 `id` 替换或插入，再按 `seq` 排序（`merge`） |

### 子 agent

子 agent 的会话是普通会话：`thread/started` 照样发，行里的 `parentThreadId` 和 `parentItemId` 指向父会话和派生它的那次调用；它的轮次和条目也走同样的 `turn/*`、`item/*` 通知，`threadId` 是子会话自己的。`thread/list` 只列顶层会话，子会话要从父会话的调用条目（`Agent` 工具）找到。

子会话里的审批和提问，请求里的 `threadId` 是子会话的。要在父会话里提示用户，就按 `parentThreadId` 往上找。子会话不接受输入、改名、归档等操作，返回 `-32013`。

### 会话状态

`thread/status/changed` 只针对顶层会话，取值 `idle`、`active`、`waitingOnApproval`、`waitingOnUserInput`；子 agent 在等审批时，父会话的状态也是 `waitingOnApproval`。它适合驱动会话列表上的标记。想知道"这个会话自己是不是在等用户"，要看当前一轮的条目里有没有在等审批或回答的调用（桌面端的 `waitingOnUser`）。

## 审批和提问

审批（`item/toolCall/requestApproval`）和提问（`item/tool/requestUserInput`）是服务端发来的 JSON-RPC 请求，客户端用 `result` 回复。参数和可选决定见[服务端请求](/zh/integrate/protocol/approvals)。

**`id` 原样带回。** 服务端请求的 `id` 是 JSON 数字，每条连接从 1 开始。网关按 `id` 的原始 JSON 文本找对应的请求，回复里写成字符串 `"3"` 对不上 `3`。实测这样回复后网关只记一条 `response to unknown request`，这个请求在这条连接上一直算"已经问过"，`thread/resume` 也不会再发，只有重连才会重新问。

各种回复的结果，实测：

| 客户端回复 | 网关 |
|---|---|
| 合法的 `result` | 写入条目，发 `item/updated` 或 `item/completed`、`thread/status/changed` |
| `decision` 或答案不合法，比如 `"maybe"` | 发 `error` 通知（带 `itemId`，`message` 写明哪里不对），随即用新的 `id` 重发同一个请求 |
| JSON-RPC 错误回复 | 只记日志。这一轮继续等，下一次 `thread/resume` 或重连时重发 |
| 这一轮已经被中断或结束后才回复 | 发 `error` 通知：`the thread does not wait on this request`，不再重发 |
| 不回复就断开 | 请求留在库里，新连接 `initialize` 后重发 |

几点由此而来的要求：

- **按 `itemId` 去重。** 同一个条目的请求会在重连、`thread/resume`、回复不合法之后再来，每次 `id` 不同。客户端应以 `itemId`（审批另有 `approvalId`）为键保存待回答的请求，新来的替换旧的，回复时用最新的那个 `id`。桌面端的 `requests.ts` 就按 `itemId` 存。
- **网关不撤回请求。** 一轮被中断、或者另一个客户端（比如飞书机器人）先回答了，网关不会通知你"这个请求作废了"。被中断时这个条目直接以 `item/completed`（`failed`）结束；别处批准时先来 `item/updated`，条目的 `approval.decision` 有了值，工具跑完才有 `item/completed`。桌面端在 `item/completed` 时删掉对应的待回答请求；想更早收起，可以在 `approval.decision` 有值时就收起。
- **回答不必立刻给。** 等审批的一轮不占槽位，也不依赖连接，客户端可以把请求留给用户慢慢处理。

## 发消息、插话、排队、中断

| 想做的事 | 调用 | 要点 |
|---|---|---|
| 发一条消息 | `turn/start` | 会话空闲时开始一轮；已有进行中的一轮时排队，发 `turn/queued`，前一轮结束后才发 `turn/started` |
| 让正在跑的这一轮马上看到 | `turn/steer`，带 `expectedTurnId` | 没有进行中的一轮时 `-32010`，`expectedTurnId` 不是进行中的那一轮时 `-32011` |
| 停下这一轮 | `turn/interrupt`，带 `turnId` | 回复 `{}` 不代表已经停了，以 `turn/completed`（`interrupted`）为准；对已结束的一轮返回 `-32010` |

这一轮在等审批或提问时插话，消息代替回答：等着的调用和排在它后面的调用以 `declined` 结束，客户端收到它们的 `item/completed`，应当据此关掉对应的审批或提问界面，不要再回复那条服务端请求，回复了也只会收到 `error` 通知（`noSuchRequest`）。这一轮随后照常接着跑，模型会读到这条消息。机制见[插话](/zh/engine/execution#插话-steer)。

插话会和这一轮的结束赛跑：用户按下发送时这一轮可能刚好结束。桌面端遇到 `-32010` 或 `-32011` 时改用 `turn/start` 把这条消息作为新的一轮发出去，这正是用户要的效果。

`expectedTurnId` 和 `turnId` 取本地状态里"当前进行中的那一轮"：状态不是 `queued`、`completed`、`interrupted`、`failed` 的那一轮，一个会话最多一个（桌面端的 `activeTurn`）。

附件用 `{type: "file", path}`：`path` 是用户沙箱里的绝对路径，引擎从那里读文件并复制一份。协议里没有上传文件内容的方法，所以客户端和用户的沙箱不在同一台机器时，文件要先用别的途径放进沙箱。附件的数量和大小上限见[一轮](/zh/integrate/protocol/turns#turn-start)，读回用 `attachment/read`。

新建会话时 `environmentId` 选在哪个执行环境里运行，省略时是用户本机的那个，之后不能改；子 agent 会话跟随父会话。可选的环境用 `environment/list` 列出。

::: info 演进
插话代替回答是 v0.12.1（`c4899f5`）的行为。v0.12.0 及更早的引擎上，插话进等审批或提问的轮次只落库，这一轮一直停到请求被回答；连这些版本的客户端仍要回答那条服务端请求，这一轮才会继续。
:::

## 版本兼容

`initialize` 回复里的 `protocolSha256` 是网关编进二进制的 `protocol.schema.json` 的 SHA-256。客户端把它和自己生成类型时用的那份契约文件的 SHA-256 比较。网关不校验，也不拒绝不一致的客户端，怎么处理由客户端决定。桌面端不一致时显示一条横幅，连接照常工作。

`serverInfo.version` 是最终二进制主模块的版本，引擎嵌在别人的程序里时不是引擎的版本，本地构建是 `(devel)`，不能用来判断兼容。

类型从契约生成，不要手写。契约是 JSON Schema（2020-12），所有类型都在 `$defs` 下，方法、通知、服务端请求在另外几段里按名字引用它们，见[一张表分发和生成 schema](/zh/integrate/protocol#一张表分发和生成-schema)。桌面端的 `packages/protocol/scripts/generate.mjs` 用 `go list -m` 找到 sidecar 依赖的那个引擎版本，读它的契约，用 `json-schema-to-typescript` 生成类型，再从 `methods`、`notifications` 等段生成方法表。

TypeScript 的最小做法：把 `$defs` 包进一个列出所有类型的根对象，交给 `json-schema-to-typescript`。下面这段对 v0.12.0 的契约跑过（`json-schema-to-typescript` 16.0.0），生成 130 个导出类型：

```js
import { readFileSync, writeFileSync } from 'node:fs'
import { compile } from 'json-schema-to-typescript'

const contract = JSON.parse(readFileSync('protocol.schema.json', 'utf8'))
const root = {
  title: 'Protocol',
  type: 'object',
  additionalProperties: false,
  properties: Object.fromEntries(Object.keys(contract.$defs).map((n) => [n, { $ref: `#/$defs/${n}` }])),
  $defs: contract.$defs,
}
writeFileSync('protocol.ts', await compile(root, 'Protocol', { bannerComment: '', unreachableDefinitions: true }))
```

别的语言可以用同样的思路，交给该语言的 JSON Schema 代码生成器，比如 quicktype。这只是建议，没有试过。

生成时要注意契约和网关的一处差别：契约把 `thread/start`、`thread/updatePermissions`、`workspace/updatePermissions` 参数里的 `permissions` 标成必填，网关解码时省略也不报错（实测 `thread/start` 不带它能成功）。按契约生成的严格类型会要求它，传 `{}` 即可。

## 常见错误

| 现象 | 原因 | 做法 |
|---|---|---|
| 新建会话或发消息后，早到的通知被丢掉，界面缺了第一条用户消息 | 等调用的回复到了才开始处理通知 | 通知一到就按 `threadId` 归档，见[通知可能先于回复](#通知可能先于回复) |
| 重连后看不到断线期间的进展 | 以为网关会补发事件 | 重连后 `thread/resume` 重读，见[重连](#重连) |
| 重连后有些审批一直不出现 | 处理函数在 `initialize` 之后才挂上，重发的请求被回了错误 | 发 `initialize` 之前挂好处理函数 |
| 回答了审批却没有生效，也没有报错 | 回复的 `id` 写成了字符串 | 原样带回请求的 `id` |
| 同一个审批弹了两次 | 重连或 `thread/resume` 后网关重发，`id` 不同 | 按 `itemId` 去重 |
| 两个窗口或两个进程用同一个令牌，轮流断线 | 每个用户一条连接，新连接把旧的以 1008 换掉 | 一个用户只开一条连接；收到 `replaced by a newer connection` 不要自动重连 |
| Go 客户端读 `tool/list` 时断开 | `coder/websocket` 默认读上限 32768 字节 | 连上后 `SetReadLimit`，网关自己的上限是 32 MiB |
| 读大图片附件时连接以 1008 关闭 | 一条回复超过 16 MiB 出站队列上限 | 见[传输](/zh/integrate/protocol#传输)，约 12 MiB 以上的图片读不回来 |
| 处理通知时做了慢操作，连接以 1008 `client is not reading fast enough` 关闭 | 客户端读得慢，出站队列积压超过 16 MiB | 收消息和处理分开，处理放到队列里 |
| 浏览器里令牌错了，只看到连不上 | WebSocket API 拿不到握手的 HTTP 状态码 | 见[关闭码](#关闭码)，把失败原因和重试次数显示给用户 |

## 代码位置

| 仓库 | 路径 | 职责 |
|---|---|---|
| ollupi | `gateway/server.go` | 连接替换、`initialize` 后重发请求、事件到通知、服务端请求和回复的处理、`asked` 去重 |
| ollupi | `gateway/threads.go` | `thread/read` 和 `thread/resume` 的 `deliver` 锁与分页、`turn/*` 的处理函数 |
| ollupi | `gateway/serve.go` | 握手的 Host 和令牌检查、关停 |
| ollupi | `pkg/jsonrpc/jsonrpc.go` | 读循环、请求串行处理、服务端请求的 `id`、出站队列和写超时 |
| ollupi | `gateway/traffic_test.go` | 假模型加真实网关的契约测试，本页的试验照它搭建 |
| ollupi-desktop | `packages/client/src/client.ts`、`peer.ts`、`transport.ts` | 类型化连接、JSON-RPC 对端、子协议传令牌 |
| ollupi-desktop | `apps/desktop/src/renderer/src/gateway/session.ts` | 连接循环、退避、先挂监听再重读 |
| ollupi-desktop | `packages/core/src/timeline.ts` | 通知合并、增量、分页合并、当前一轮 |
| ollupi-desktop | `apps/desktop/src/renderer/src/domains/requests.ts` | 按 `itemId` 存待回答请求，`item/completed` 时删掉 |
| ollupi-desktop | `apps/desktop/src/renderer/src/domains/conversation.ts` | 打开会话用 `thread/resume`、插话失败改发新一轮、中断 |
| ollupi-desktop | `packages/protocol/scripts/generate.mjs` | 从契约生成 TypeScript 类型和方法表 |
