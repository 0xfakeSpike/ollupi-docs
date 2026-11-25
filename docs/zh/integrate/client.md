# 写一个客户端

这一页讲怎样写一个正确的网关客户端：怎样连上、断了怎样重连、本地状态怎样和引擎保持一致、审批和提问怎样回答。线上有哪些方法、通知和错误码见[网关协议](/zh/integrate/protocol)，每个类型的字段见[协议类型索引](/zh/integrate/protocol-types)，这里只讲把它们用对。

桌面端是现成的参照实现：`packages/client` 是类型化的连接，`packages/core/src/timeline.ts` 把通知合进本地状态，`apps/desktop/src/renderer/src/gateway/session.ts` 管连接和重连。下文提到"桌面端的做法"都指这几个文件。

本页的代码和行为对着引擎 v0.17.1 实际跑过：一个最小宿主（`host.New` 配一个实现 `llm.Client` 的脚本化假模型和一个非只读工具 `deploy`，审批策略为适中，网关用单用户令牌）跑在本机，下面的客户端连上去，走通了普通回答、审批的接受和拒绝、结构化提问、错误令牌；标了"实测"的行为都来自对这个网关的脚本化试验。

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
const ended = new Set() // calls already reported
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
// so they are matched by threadId, not by waiting for replies.
const notifications = {
  'item/agentMessage/delta': (p) => p.threadId === threadId && process.stdout.write(p.delta),
  'item/changed': ({ threadId: t, item }) => {
    const over = ['completed', 'failed', 'declined'].includes(item.status)
    if (t !== threadId || item.type !== 'toolCall' || !over || ended.has(item.id)) return
    ended.add(item.id)
    console.log(`\n[tool] ${item.tool}: ${item.status}${item.error ? ' (' + item.error + ')' : ''}`)
  },
  'turn/changed': ({ threadId: t, turn }) => {
    if (t !== threadId || ['queued', 'inProgress'].includes(turn.status)) return
    console.log(`\n[turn] ${turn.status}${turn.error ? ': ' + turn.error : ''}`)
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
    const { thread } = await call('thread/start', { title: 'example' })
    threadId = thread.id
    await call('turn/start', { threadId, input: [{ type: 'text', text }] })
  } catch (err) {
    console.error(`failed: ${err.code ?? ''} ${err.message}`)
    ws.close(1000)
    process.exitCode = 1
  }
}
```

对上面那个网关，模型会调用 `deploy`，带 `--approve` 跑一次的输出（实测，回答是假模型把工具结果原样念出来）：

```text
$ node client.mjs ws://127.0.0.1:18787/ secret "please deploy" --approve
server ollupi (devel), contract 0e97e52f8337

[approval] deploy {"target":"prod"} -> accept

[tool] deploy: completed
Done: {
  "args": {
    "target": "prod"
  },
  "deployed": true
}
[turn] completed
```

不带 `--approve` 时这次调用以 `declined (the user declined this call)` 结束，模型收到"工具调用已停止"的提示后照常写完回答，这一轮仍是 `completed`。令牌错误时只打印 `cannot connect to ...`，退出码 1。

`ended` 集合是必要的：同一个调用条目可能收到不止一条状态已经结束的 `item/changed`（比如它启动的子 agent 回报时会再发一次）。

它故意省掉了重连、本地状态和多个会话，这些是下面各节的内容。真实客户端至少还要做到"[重连](#重连)"和"[用 seq 对齐](#用-seq-对齐)"两节。

## 连接

### 认证与握手

令牌只有两种传法：`Authorization: Bearer <token>` 头，或者浏览器和 Node 自带的 `WebSocket` 用的子协议 `["ollupi.token", token]`。两种都不进 URL，细节见[认证](/zh/integrate/protocol#认证)。

握手的顺序有一个要求：**在发 `initialize` 之前就把服务端请求的处理函数挂好。** 网关在 `initialize` 的回复入队之后立刻把这个用户所有在等回答的审批和提问发一遍（`gateway/server.go` 的 `initialize` 返回的 `after`），不等客户端的 `initialized` 通知。处理函数还没挂上时，客户端只能回一个错误，网关不做任何事，这些请求要等下一次 `thread/resume`、重连，或那个条目再有变化才会再来。上面的例子在建连接时就定好了 `requests` 表；桌面端在 `initialize` 返回后、让出事件循环之前同步挂上处理函数，效果一样。

`initialized` 通知照发：契约里有它，网关收到后什么也不做。

### 关闭码

网关会用的每个关闭码和握手拒绝状态都在契约的 `closes` 和 `handshakes` 两段里，各带一个 `reconnect`，表见[关闭与重连](/zh/integrate/protocol#关闭与重连)。客户端照 `reconnect` 做：

| `reconnect` | 用在 | 客户端该做的 |
|---|---|---|
| `soon` | 1001：网关关停，或连接到了 15 到 20 小时的寿命 | 随机等 0 到 10 秒再连，避免和同一时刻被切断的客户端挤在一起 |
| `backoff` | 1006、1008、1009、1011，握手 500 | 从 1 秒开始、每次加倍、到 60 秒为止，每次在上限以内随机等。1008（读得太慢）之后要先查清楚为什么积压 |
| `retryAfter` | 握手 503 | 等响应头 `Retry-After` 的秒数（1 到 5 秒）；拿不到就按 `backoff` |
| `never` | 4000，握手 401、403 | 不要自己重连。4000 表示同一用户开了第五条连接，这条被顶掉了，自动重连会去顶掉别人；401、403 重试也不会好 |

浏览器和 Node 自带的 `WebSocket` 拿不到握手的 HTTP 状态码，只给一个 `error` 事件；Node 22 实测连 `close` 事件都没有，只有 `error`。所以这类客户端分不出"令牌错了"和"分片在交接"，只能都按可重试处理、加上退避和上限，把最后一次失败显示给用户。Go 的 `coder/websocket` 的 `Dial` 会返回 `*http.Response`，能看到状态码，可以照 `handshakes` 表处理。

### 重连

网关不缓存事件：断线期间的通知不补发，连接只在 `initialize` 之后才订阅变化。所以重连不是"接着收"，而是"重新读一遍"：

1. 按上一节的 `reconnect` 等一会儿。
2. 连上、`initialize`，比较 `protocolSha256`（见[版本兼容](#版本兼容)）。发 `initialize` 之前挂好服务端请求的处理函数。
3. 挂上通知监听。
4. 重读每块状态：执行环境、工作区、会话列表、打开着的会话（`thread/resume`）、模型、工具、MCP 服务器、定时任务、设置。打开着的会话按下一节的[用 seq 对齐](#用-seq-对齐)合并。
5. 重读期间连接又断了，就整轮重来；只有全部读完才开始监视关闭。

同一时刻只能有一个重连循环。一个用户最多四条连接，两个循环各自开连接，很快就会顶掉自己的另一条连接（4000）。

打开着的会话用 `thread/resume` 而不是 `thread/read`：两者返回同样的一页，`thread/resume` 回复之后还会把这个会话和它的子 agent 会话里在等回答的请求再发一遍，这条连接上已经发过、还没回答的不重复发（`conn.asked`，实测）。

桌面端的退避是 `min(5000, 250 × 2ⁿ)` 毫秒（`session.ts` 的 `MAX_BACKOFF_MS`），比契约建议的 `backoff` 急；它是本机 sidecar 的客户端，连的是同一台机器上的网关。

## 本地状态

### 通知可能先于回复

一次调用提交的变化会立刻进入出站队列，而回复要等处理函数返回，所以通知常常比引起它的那个调用的回复先到。实测的顺序：

| 调用 | 回复之前已经收到 |
|---|---|
| `thread/start` | 新会话的 `thread/changed` |
| `turn/start`（会话空闲） | `thread/changed`（`active`）、`turn/changed`（`inProgress`）、用户消息的 `item/changed` |
| `turn/start`（已有进行中的一轮） | `thread/changed`、`turn/changed`（`queued`）、用户消息的 `item/changed` |
| `turn/steer`（这一轮在等审批） | `thread/changed`（`active`）、`turn/changed`、被拒调用的 `item/changed`、插话消息的 `item/changed` |
| `turn/interrupt` | `thread/changed`、`turn/changed`（`interrupted`），有排队的一轮时还有它变成 `inProgress` 的 `turn/changed` |
| `thread/markRead`、`thread/rename` 等 | `thread/changed` |

所以客户端不能"等回复到了再开始处理通知"，状态要按 `threadId`、`turnId`、`itemId` 归档，而不是按调用。上面的最小客户端在 `thread/start` 回复之前收到的 `thread/changed` 会被忽略，因为那时还不知道 `threadId`；对它没有影响，因为它只关心之后的事。

### 用 seq 对齐

`thread/read` 和 `thread/resume` 的一页在一个读事务里读出，同一个事务里还读出当时已经提交到的序号，放在回复的 `seq` 里。每条 `thread/changed`、`turn/changed`、`item/changed` 都带着产生它的那次提交的 `seq`。所以：

- **`seq` 不大于这一页的 `seq`** 的通知，那次变化已经在这一页里，丢掉。
- **`seq` 大于这一页的 `seq`** 的通知，是这一页之后的变化，合进去。

网关不保证通知排在读回复的前面还是后面：读的同时别的提交还在发生，它的通知可能先于回复到达，也可能晚于回复到达。所以发读请求之前就要开始接收这个会话的通知，回复到达之前先攒着，回复到了用 `seq` 过滤后再合并。反过来先读、再挂监听，读和挂之间的通知就丢了。

下面这段把一个会话的一页和之后的通知合成本地副本。它对着上面的网关跑过：在一轮正在流式输出时读这一页，等这一轮结束后，副本里的会话行、轮次和条目和再读一次得到的完全相同（实测）。

```js
// One thread's local copy: a page read at one commit (seq), plus every
// change committed after it.
class ThreadCopy {
  constructor(threadId) {
    this.threadId = threadId
    this.seq = null // null until the page arrives
    this.early = [] // notifications that came while the page was being read
    this.thread = null
    this.turns = new Map()
    this.items = new Map() // id -> ItemRow; streamed text uses updated: 0
  }

  async load(call) {
    this.seq = null
    this.early = []
    const page = await call('thread/resume', { threadId: this.threadId })
    this.thread = page.thread
    this.turns = new Map(page.turns.map((t) => [t.id, t]))
    this.items = new Map(page.items.map((i) => [i.id, i]))
    this.seq = page.seq
    for (const [method, params] of this.early) this.apply(method, params)
    this.early = []
  }

  apply(method, p) {
    if (p.threadId !== this.threadId) return
    if (this.seq === null) return void this.early.push([method, p])
    if (method === 'item/agentMessage/delta' || method === 'item/reasoning/textDelta') return this.stream(p, method)
    if (p.seq <= this.seq) return // already in the page
    if (method === 'thread/changed') this.thread = p.thread // null: deleted
    if (method === 'turn/changed') {
      this.turns.set(p.turn.id, p.turn)
      if (!['queued', 'inProgress'].includes(p.turn.status)) this.dropStreamed(p.turn.id)
    }
    if (method === 'item/changed') {
      const known = this.items.get(p.item.id)
      if (!known || known.updated <= p.item.updated) this.items.set(p.item.id, p.item)
      if (p.item.type === 'error') this.dropStreamed(p.item.turnId)
    }
  }

  stream(d, method) {
    const known = this.items.get(d.itemId)
    if (known && known.updated !== 0) return // already kept whole
    const type = method === 'item/reasoning/textDelta' ? 'reasoning' : 'agentMessage'
    const text = (known?.text ?? '') + d.delta
    this.items.set(d.itemId, { id: d.itemId, turnId: d.turnId, seq: Infinity, updated: 0, type, status: 'inProgress', text })
  }

  dropStreamed(turnId) {
    for (const [id, it] of this.items) if (it.turnId === turnId && it.updated === 0) this.items.delete(id)
  }

  ordered() {
    return [...this.items.values()].sort((a, b) => a.seq - b.seq)
  }
}
```

连接的 `onmessage` 把每条通知交给对应会话的 `apply`。刚用 `thread/start` 建的会话还没有页，可以直接从 `seq` 为 0 开始，收到的通知全部合进去。桌面端 `timeline.ts` 的 `applyEvent` 用的是同一套规则。

::: info 演进
v0.12.1 的网关在 `thread/read`、`thread/resume`、`cron/list` 读库到回复入队之间持有这条连接的 `deliver` 锁，保证回复之后的通知都是回复之后的变化，客户端只要"先订阅、再读"。v0.16.0 去掉了这把锁，改成每次提交编号、读回复带 `seq`，由客户端过滤（`499f96f`）。
:::

### 按行替换

`thread/changed`、`turn/changed`、`item/changed` 带的是提交之后的完整行，客户端直接按 `id` 替换，不需要自己推导状态变化：

| 通知 | 合并方式 |
|---|---|
| `thread/changed` | 替换会话行；`thread` 为 `null` 表示已删除 |
| `turn/changed` | 按 `turn.id` 替换或插入这一轮；结束了就丢掉这一轮还没落成条目的流式文本 |
| `item/changed` | 按 `item.id` 替换或插入；本地的 `updated` 更大时保留本地的；`error` 条目出现时丢掉这一轮的流式文本 |
| `item/agentMessage/delta`、`item/reasoning/textDelta` | 接到临时条目的 `text` 后面，见下一节 |

`updated` 是条目最近一次改动在会话日志里的位置，只增不减。不同提交的通知在网关里可能以和提交不同的顺序进入出站队列（由代码推断：提交之后各自发布，中间没有锁），按 `updated` 比较能挡住旧的那条。同一个条目也会收到 `updated` 不变的重复通知，替换了也无妨。

### 增量

增量只走通知，不进日志，不补发。它指向的 `itemId` 是这段文字将来要成为的条目，在模型回答完之前这个条目并不存在：

- 收到一个本地没有的 `itemId` 的增量，建一个临时条目来接它（上面的代码用 `updated: 0` 标记，`seq` 放到最后），按 `type` 区分回答和思考。
- 同一个 ID 的条目在 `item/changed` 里出现时，用它整个替换临时条目，`text` 以它为准。增量经过脱敏的缓冲，可能和最终文本不完全一致。
- 这一轮结束、或者出现 `error` 条目时，丢掉这一轮剩下的临时条目：模型调用失败或这一轮被中断，那段文字永远不会落成条目。
- 断线重连后，正在输出的回答不在读到的一页里，之前收到的增量也接不上；只能从重连之后的增量重新开始拼，等它的 `item/changed`。

### 分页和 seq

翻页用的是条目的 `seq`，不是提交的 `seq`。条目的 `seq` 是条目在会话日志里第一次出现的位置，会话内唯一递增、会跳号；`thread/read` 每页取最新的若干条、按它升序返回，`beforeSeq` 取更早的一页。一页的 `turns` 只有这一页的条目所属的轮次和还没结束的轮次。限额见[会话](/zh/integrate/protocol/threads#thread-read-和-thread-resume)。

本地合并的三种情况，桌面端各有一个函数：

| 情况 | 做法 |
|---|---|
| 往上翻页（`beforeSeq` = 本地最早的条目 `seq`） | 新一页的条目去掉本地已有的 `id`，接在前面，`hasMore` 取新一页的；轮次按 `id` 合并（`prependPage`） |
| 重连后重读最新一页 | 用新一页替换本地的尾部，`seq` 换成新一页的；本地比新一页最早的条目还旧的条目保留，它们属于已经结束的轮次，不会再变，它们的轮次也保留（`refreshFromPage`） |
| 实时通知 | 用 `seq` 过滤，按 `id` 替换或插入，再按条目 `seq` 排序（`applyEvent`） |

### 子 agent

子 agent 的会话是普通会话：它的 `thread/changed` 照样发，行里的 `parentThreadId` 和 `parentItemId` 指向父会话和启动它的那次调用；它的轮次和条目也走同样的 `turn/changed`、`item/changed`，`threadId` 是子会话自己的。`thread/list` 只列顶层会话，子会话要从父会话的调用条目（`childThreadId`）或 `agentReport` 条目找到。

子会话里的审批和提问，请求里的 `threadId` 是子会话的。要在父会话里提示用户，就按 `parentThreadId` 往上找。子会话和普通会话走同一套方法：能收输入（按它自带的角色跑）、改名、归档、改权限；归档同样要求会话空闲。

### 会话状态

`ThreadRow.status` 取值 `idle`、`active`、`waitingOnApproval`、`waitingOnUserInput`；子 agent 在等审批时，父会话的状态也是 `waitingOnApproval`。它适合驱动会话列表上的标记。想知道"这个会话自己是不是在等用户"，要看当前一轮的条目里有没有在等审批或回答的调用。

未读标记由客户端比较 `repliedAt` 和 `readAt` 得出；用户看过之后调 `thread/markRead`，同一用户的其他连接收到 `thread/changed`，标记一起消失。

## 审批和提问

审批（`item/toolCall/requestApproval`）和提问（`item/tool/requestUserInput`）是服务端发来的 JSON-RPC 请求，客户端用 `result` 回复。参数和可选决定见[审批与提问](/zh/integrate/protocol/approvals)。

**`id` 原样带回。** 服务端请求的 `id` 是 JSON 数字，每条连接从 1 开始。网关按 `id` 的原始 JSON 文本找对应的请求，回复里写成字符串 `"3"` 对不上 `3`。这样回复后网关直接忽略，这个请求在这条连接上一直算"已经问过"，`thread/resume` 也不会再发，只有重连才会重新问。

各种回复的结果见[回复的结果](/zh/integrate/protocol/approvals#回复的结果)。由此而来的几点要求：

- **按 `itemId` 去重。** 同一个条目的请求会在重连、`thread/resume`、回复不合法之后再来，每次 `id` 不同。客户端应以 `itemId`（审批另有 `approvalId`）为键保存待回答的请求，新来的替换旧的，回复时用最新的那个 `id`。桌面端的 `requests.ts` 就按 `itemId` 存。
- **按条目收起。** 网关不撤回请求。一轮被中断、用户插话、或者用户在另一台设备上先回答了，客户端看到的只是那个条目的 `item/changed`。条目不再满足"在等"的条件（审批：`pending` 且 `approval.decision` 为空；提问：`inProgress` 且 `input.answered` 为 `false`）时，就收起对应的界面。
- **回复严格。** 回复里不要带契约之外的字段，否则网关发 `error` 通知并立刻重发同一个请求。收到带 `itemId` 的 `error` 通知时，把原因告诉用户，让他重新回答，不要自动再回一遍同样的内容。
- **回答不必立刻给。** 等审批的一轮不占槽位，也不依赖连接，客户端可以把请求留给用户慢慢处理。

## 发消息、插话、排队、中断

| 想做的事 | 调用 | 要点 |
|---|---|---|
| 发一条消息 | `turn/start` | 会话空闲时这一轮马上开始（`inProgress`）；已有进行中的一轮时排队（`queued`），前面的结束后才开始。每条消息各排一轮，最多 20 个排队，再发返回 `-32016` |
| 让正在跑的这一轮马上看到 | `turn/steer`，带 `expectedTurnId` | 没有进行中的一轮时 `-32010`，`expectedTurnId` 不是进行中的那一轮时 `-32011` |
| 停下这一轮 | `turn/interrupt`，带 `turnId` | 回复到达时这一轮已经以 `interrupted` 结束；对已结束的一轮返回 `-32010`，对排队中的一轮返回 `-32011` |

这一轮在等审批或提问时插话，消息代替回答：等着的审批按拒绝、提问按跳过记下，调用以 `declined` 结束，客户端收到它们的 `item/changed`，应当据此关掉对应的审批或提问界面，不要再回复那条服务端请求，回复了也只会收到 `error` 通知。这一轮随后照常接着跑，模型会读到这条消息。见[插话](/zh/integrate/protocol/turns#插话)。

插话会和这一轮的结束赛跑：用户按下发送时这一轮可能刚好结束。桌面端遇到 `-32010` 或 `-32011` 时改用 `turn/start` 把这条消息作为新的一轮发出去，这正是用户要的效果。

`expectedTurnId` 和 `turnId` 取本地状态里"当前进行中的那一轮"：状态是 `inProgress` 的那一轮，一个会话最多一个。

附件用 `{type: "file", path}`：`path` 是用户第一个执行环境里的绝对路径，引擎从那里读文件并复制一份。协议里没有上传文件内容的方法，所以客户端和用户的第一个环境不在同一台机器时，文件要先用别的途径放进那里。附件的数量和大小上限见[一轮与条目](/zh/integrate/protocol/turns#turn-start)，读回用 `attachment/read`。

新建会话时 `environmentId` 选在哪个执行环境里运行，之后不能改；子 agent 会话跟随父会话。在工作区里的会话总在工作区的环境里，`environmentId` 省略即可，给了别的会被拒绝；不在工作区时省略是用户的第一个环境。可选的环境和部署提供的沙箱用 `environment/list` 列出，添加工作区时用 `environmentId` 指定文件夹在哪个环境里。

## 版本兼容

`initialize` 回复里的 `protocolSha256` 是网关编进二进制的 `protocol.schema.json` 的 SHA-256。客户端把它和自己生成类型时用的那份契约文件的 SHA-256 比较。网关不校验，也不拒绝不一致的客户端，怎么处理由客户端决定。桌面端不一致时显示一条提示，连接照常工作。

`serverInfo.version` 是最终二进制主模块的版本，引擎嵌在别人的程序里时不是引擎的版本，本地构建是 `(devel)`，不能用来判断兼容。

类型从契约生成，不要手写。契约是 JSON Schema（2020-12），所有类型都在 `$defs` 下，方法、通知、服务端请求在另外几段里按名字引用它们，见[契约的生成与测试](/zh/integrate/protocol#契约的生成与测试)。桌面端的 `packages/protocol/scripts/generate.mjs` 用 `go list -m` 找到 sidecar 依赖的那个引擎版本，读它的契约，用 `json-schema-to-typescript` 生成类型，再从 `methods`、`notifications` 等段生成方法表。

TypeScript 的最小做法：把 `$defs` 包进一个列出所有类型的根对象，交给 `json-schema-to-typescript`。下面这段对 v0.17.1 的契约跑过（`json-schema-to-typescript` 16.0.0），生成 135 个导出类型（134 个 `$defs` 加根对象）：

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

`closes`、`handshakes` 和 `limits` 三段不是类型，是值：重连策略和搜索上限可以直接从契约读出来，不必写死在客户端里。

## 常见错误

| 现象 | 原因 | 做法 |
|---|---|---|
| 新建会话或发消息后，早到的通知被丢掉，界面缺了第一条用户消息 | 等调用的回复到了才开始处理通知 | 通知一到就按 `threadId` 归档，见[通知可能先于回复](#通知可能先于回复) |
| 打开会话后偶尔少一步，或一个条目退回到旧状态 | 先读、后挂监听；或者没有用 `seq` 过滤，把读回复之前的旧通知又合了一遍 | 发读请求前挂好监听，回复到了按 `seq` 合并，见[用 seq 对齐](#用-seq-对齐) |
| 回答流式输出时界面上没有字，最后一下子出现 | 只在本地已有的条目上接增量 | 为增量的 `itemId` 建临时条目，见[增量](#增量) |
| 模型调用失败或中断后，界面上留着半截回答 | 临时条目没有清掉 | 这一轮结束或出现 `error` 条目时丢掉临时条目 |
| 重连后看不到断线期间的进展 | 以为网关会补发事件 | 重连后 `thread/resume` 重读，见[重连](#重连) |
| 重连后有些审批一直不出现 | 处理函数在 `initialize` 之后才挂上，重发的请求被回了错误 | 发 `initialize` 之前挂好处理函数 |
| 回答了审批却没有生效，也没有报错 | 回复的 `id` 写成了字符串 | 原样带回请求的 `id` |
| 回答后收到 `error`，同一个请求马上又来，来回打转 | 回复里带了契约之外的字段，或答案不合法，客户端又自动回了同样的内容 | 回复只带契约里的字段；收到 `error` 让用户重新回答 |
| 同一个审批弹了两次 | 重连或 `thread/resume` 后网关重发，`id` 不同 | 按 `itemId` 去重 |
| 多开几个窗口后，最早的那个断线不再回来 | 每个用户最多四条连接，第五条把最早的以 4000 顶掉 | 一个窗口一条连接；收到 4000 不要自动重连 |
| Go 客户端读 `tool/list` 或 `thread/read` 时断开 | `coder/websocket` 默认读上限 32768 字节 | 连上后 `SetReadLimit` |
| 处理通知时做了慢操作，连接以 1008 `client is not reading fast enough` 关闭 | 客户端读得慢，出站队列积压超过 16 MiB | 收消息和处理分开，处理放到队列里 |
| 浏览器里令牌错了，只看到连不上 | WebSocket API 拿不到握手的 HTTP 状态码 | 见[关闭码](#关闭码)，把失败原因和重试次数显示给用户 |
| 旧客户端建会话时报 `json: unknown field "permissions"` | `thread/start` 不再收权限参数 | 去掉 `approvalPolicy` 和 `permissions`，建好后用 `thread/updatePermissions` |

## 代码位置

| 仓库 | 路径 | 职责 |
|---|---|---|
| ollupi | `gateway/server.go` | `initialize` 之后订阅和重发请求、变化到通知、服务端请求和回复的处理、`asked` 去重 |
| ollupi | `gateway/threads.go` | `thread/read` 和 `thread/resume` 的分页与 `seq`、`turn/*` 的处理函数 |
| ollupi | `gateway/protocol.go` | `closes`、`handshakes` 两张表 |
| ollupi | `pkg/jsonrpc/jsonrpc.go` | 读循环、请求串行处理、服务端请求的 `id`、出站队列和写超时 |
| ollupi | `pkg/wshub/wshub.go` | 每用户四条连接、心跳、寿命 |
| ollupi | `store/sqlite/sqlite.go`、`store/sqlite/conversations.go` | 每次提交编号、提交之后发布变化、`Seq` |
| ollupi | `run/model.go` | 增量的发布：`itemId` 是将来的回答条目 |
| ollupi | `gateway/gateway_test.go` | 收到带 `seq` 的变化、回答审批的流程测试 |
| ollupi-desktop | `packages/client/src/client.ts` | 类型化连接 |
| ollupi-desktop | `apps/desktop/src/renderer/src/gateway/session.ts` | 连接循环、退避、协议摘要比较 |
| ollupi-desktop | `packages/core/src/timeline.ts` | 按 `seq` 合并通知、流式文本的临时条目、分页合并 |
| ollupi-desktop | `apps/desktop/src/renderer/src/domains/requests.ts` | 按 `itemId` 存待回答请求 |
| ollupi-desktop | `packages/protocol/scripts/generate.mjs` | 从契约生成 TypeScript 类型和方法表 |
