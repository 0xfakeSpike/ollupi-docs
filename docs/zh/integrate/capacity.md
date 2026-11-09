# 容量规划与限流

这一页讲怎样设置引擎的并发参数：槽位、单用户限额、模型连接的并发名额和运行时长上限，以及调大调小各有什么后果。测出来的容量数字见[性能基准](/zh/benchmarks/)，调度机制见[执行模型](/zh/engine/execution)。

## 四个参数

槽位和模型并发是两个独立的上限，另外两个是单用户限额与时长：

| 参数 | 控制什么 | 默认 |
|---|---|---|
| `Config.Slots` | 这个进程同时运行的轮次数 | 32 |
| `Config.UserSlots` | 一个用户最多占几个槽位 | 等于 `Slots` |
| `llm` 客户端的 `calls` | 一条连接同时在途的模型请求数 | 4 |
| `Config.RunLimit` | 一次占用槽位的最长时间 | 4 小时 |

`Slots`、`UserSlots`、`RunLimit` 填 0 或负数时，`agent.Start` 换成默认值；`calls` 是 `llm.NewOpenAI`、`llm.NewAnthropic`、`llm.NewGemini` 的第三个参数，填 0 或负数时用 `llm.DefaultCalls`（4）。

一个轮次占着槽位时，要么在调用模型（占一个模型名额），要么在执行工具（不占名额），要么在两者之间读写库。名额满时，模型调用在通道上排队，这一轮仍占着槽位。所以 `Slots` 比 `calls` 大出来的部分，只对正在跑工具的轮次有用；工具都很快时，把 `Slots` 调到远大于 `calls` 不会提高吞吐，只会让更多轮次一边排队一边占着槽位。

## 调大调小的后果

| 参数 | 调大 | 调小 |
|---|---|---|
| `Slots` | 更多轮次同时在跑：每个多占一个 goroutine 和它的内存，库的读写也更多。库只有一条连接，所有读写在它上面排队（见[已知瓶颈](/zh/benchmarks/#已知瓶颈)）。模型名额不跟着加时，多出的轮次只是在名额上排队 | 就绪的轮次留在 `ready` 等槽位，用户感到"发了消息迟迟不开始"。跑长工具的轮次会把槽位占满，其他会话全部等待 |
| `UserSlots` | 一个用户的轮次能占更多槽位；等于 `Slots` 时，一个发散出很多子 agent 的用户能占满整个分片 | 同一个用户的轮次互相排队。子 agent 和父会话算同一个用户，发散多的用户受影响最大。超额的轮次留在 `ready`，不失败 |
| `calls` | 在途的模型请求更多。超过服务商给账户的并发配额时 429 变多，请求进入重试（见下一节），重试期间名额和槽位都不释放 | 模型请求在名额上排队，轮次占着槽位等。名额比服务商配额小时，配额用不满 |
| `RunLimit` | 卡住的轮次占着槽位更久才被判失败。轮次里的模型请求没有别的超时（见下一节），一个不回应的请求最长占到 `RunLimit` | 正常的长任务也会被判失败，错误是 `agent: the turn reached its time limit of ...` |

几点补充：

- 等审批、等用户回答、等子 agent 的轮次不占槽位，也不计入 `UserSlots`，`RunLimit` 也不算这段时间：它按每次进槽位计时，回到槽位重新计。
- `checkModels` 要求一条连接只给一个模型用，所以 `calls` 实际是"这个模型同时在途的请求数"。可以给同名模型再建一条连接（如 `openai-2`）并带自己的配额，但它在 `Models` 里是另一个可选模型：一轮用的是它被提交时选定的那条连接，引擎不会在两条连接之间分摊。
- 配了 `ClientFor` 时，每个用户的轮次走这个函数返回的客户端，名额按那个客户端算；`ClientFor` 每次应返回同一个客户端，否则名额形同虚设。分片里同时在途的请求最多是"用户数 × 每用户客户端的 `calls`"。

## 怎样选值

先定 `calls`：它对应服务商给这个账户（或这个用户的密钥）的并发配额，不要超过它。突发请求在名额上排队，不会打爆配额，基准里的突发实验就是这样，见[突发](/zh/benchmarks/#突发)。

再定 `Slots`。从机制推出的起点是：所有连接的 `calls` 之和，加上预计同时在跑工具的轮次数。这是推断，不是测出来的；工具的耗时和阻塞不在现有基准的负载里，见[容量模型](/zh/benchmarks/#容量模型)的"不能推出的"。

`UserSlots` 按"一个用户最多该用掉分片的几分之一"来定。用户会大量使用子 agent 时，要给他留出父会话加子 agent 的余量；父会话等子 agent 时会让出槽位，所以不必按"父加子"成倍预留。

`RunLimit` 设成最长的正常任务再留余量。它同时也是轮次里一个卡住的模型请求或工具最长能占多久，所以不宜远大于需要。

单个分片的容量上限现在还没有测出来：[容量模型](/zh/benchmarks/#容量模型)写明了活跃会话变多后一轮变慢的原因还没找到，多分片和多用户也没测。要更多容量时，靠加分片，见[多用户与分片部署](/zh/integrate/deploy)。

## 重试会占着槽位

被 408、429、5xx 拒绝或中途断开的模型请求由客户端重试，最多 8 次（`pkg/llm/connection.go` 的 `retries`），退避从 0.5 秒翻倍到最多 8 秒，OpenAI 和 Anthropic 的客户端还遵守服务商的 `Retry-After`，代码注释估计总共约 40 秒。重试期间：

- 这一轮一直占着槽位，模型名额也不释放，所以在途请求数始终不超过 `calls`。
- 用户看到的是这一轮变慢，不是失败。8 次都失败时这一轮才失败，错误里带 HTTP 状态码，如 `model request failed (HTTP 429); check the selected connection and model`。

`llm` 客户端在 ctx 没有截止时间时给单次请求加 180 秒超时（`defaultChatTimeout`）。轮次里的 ctx 带着 `RunLimit` 的截止时间，所以这条默认超时在轮次里不生效，轮次内的模型请求只受 `RunLimit` 约束。见[执行模型的模型并发限制](/zh/engine/execution#模型并发限制)。

## 判断哪个上限在卡

引擎没有指标接口，能用的是日志和库里的状态（怎样读见[运维](/zh/integrate/operations)）。

| 想知道 | 看哪里 | 说明 |
|---|---|---|
| 槽位是否满了 | 库里 `status = 'ready'` 的轮次数持续大于 0 | `ready` 就是"在等槽位"。按 `threads.user_id` 分组：集中在少数用户、且这些用户的 `inProgress` 轮次数等于 `UserSlots`，是单用户限额在卡；分布在很多用户，是 `Slots` 在卡 |
| 一次运行在槽位里待了多久 | `run ended` 日志的 `ms` | 每次进槽位一条；`turn ended` 的 `ms` 是这一轮从成为当前轮次到结束的总时长，包括等审批和排队 |
| 模型名额或服务商是否在卡 | `model call` 日志的 `ms`，和 `input`、`output` 一起看 | `ms` 从发请求之前开始计，包括在名额上排队和重试的时间。token 数差不多而 `ms` 明显变长，是在排队或重试；日志分不出是哪一种 |
| 重试是否用完了 | `model call failed` 警告，和 `turn failed` 警告里的 `HTTP 429` | 重试用完才会有这两条 |
| `RunLimit` 是否太小 | `turn failed` 警告，`err` 是 `agent: the turn reached its time limit of ...` | |

`turn started` 日志不是"进了槽位"：它在一轮成为会话的当前轮次时写，那时这一轮可能还要在 `ready` 等槽位。引擎在轮次进槽位时不写日志。

## 代码位置

| 仓库 | 路径 | 职责 |
|---|---|---|
| ollupi | `agent/agent.go` | `Slots`、`UserSlots`、`RunLimit` 的定义和默认值 |
| ollupi | `agent/schedule.go` | `reconcile`、`admit`：槽位和单用户限额在哪里生效 |
| ollupi | `agent/run.go` | `RunLimit` 的计时，`run ended`、`turn ended`、`turn failed` 日志 |
| ollupi | `agent/models.go` | `checkModels`、`ClientFor` |
| ollupi | `agent/runtime/chat.go` | `model call` 日志 |
| ollupi | `pkg/llm/connection.go` | `DefaultCalls`、`retries`、`defaultChatTimeout`、名额的获取和释放 |
| ollupi | `pkg/llm/openai.go`、`anthropic.go`、`gemini.go` | 各客户端的重试设置 |
| ollupi | `repo/turns.go` | 轮次状态，`ReadyThreads` 的排序 |
