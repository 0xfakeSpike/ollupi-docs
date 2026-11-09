# 设置

用户级的设置，目前只有一项：发给模型之前要不要脱敏。客户端用 `settings/read` 读、`settings/update` 改，用 `settings/changed` 跟上。脱敏识别什么、怎样替换和还原，见[脱敏](/zh/engine/redaction)。

## 概念与状态

- **每个用户一行。** 设置跟着用户走，同一分片上不同用户各有各的。建用户时就有这一行，`redaction` 默认是 `true`。
- **立即生效，包括正在跑的一轮。** 引擎每次调用模型之前都重新读这个开关，所以切换从下一次模型调用起生效，不用等下一轮。
- **记忆提炼也按它。** 后台提炼长期记忆时发给模型的请求，同样按这个用户的开关决定是否脱敏。
- **只影响以后发出去的请求。** 已经存下的模型回答不随开关改变，里面已有的占位符保持原样，见[开关](/zh/engine/redaction#开关)。
- **审批和权限不在这里。** 审批策略和规则按 agent 默认、工作区、会话三层设置，见[权限](/zh/integrate/protocol/permissions)。

## 典型流程

下面的消息来自桌面端仓库录制的真实会话 `packages/protocol/fixtures/session.json`。读一次，关掉，再打开：

```json
{"jsonrpc":"2.0","id":37,"method":"settings/read","params":{}}
{"jsonrpc":"2.0","id":37,"result":{"redaction":true}}
{"jsonrpc":"2.0","id":38,"method":"settings/update","params":{"redaction":false}}
{"jsonrpc":"2.0","id":38,"result":{"redaction":false}}
{"jsonrpc":"2.0","method":"settings/changed","params":{"redaction":false}}
{"jsonrpc":"2.0","id":39,"method":"settings/update","params":{"redaction":true}}
{"jsonrpc":"2.0","id":39,"result":{"redaction":true}}
{"jsonrpc":"2.0","method":"settings/changed","params":{"redaction":true}}
```

和大多数写方法不同，`settings/changed` 排在回复之后：网关在回复入队之后才发它。

## 方法

### settings/read

无参数，结果是 `SettingsRow`。不需要宿主额外配置。

### settings/update

| 参数 | 类型 | 说明 |
|---|---|---|
| `redaction` | boolean | 必填 |

结果是更新后的 `SettingsRow`，回复之后发 `settings/changed`。值没有变也照样发。

| 错误 | 什么时候 |
|---|---|
| `-32602` `redaction is required` | 没给 `redaction`，实测 `params` 为 `{}` 时如此 |

## 通知：settings/changed

载荷就是 `SettingsRow`。只由 `settings/update` 触发，发到这个用户当前的连接上。每个用户同一时刻只有一条连接，所以它总是发给刚刚调用 `settings/update` 的那个客户端；客户端可以直接用回复更新本地状态，不必等它。

## 类型：SettingsRow

| 字段 | 类型 | 说明 |
|---|---|---|
| `redaction` | boolean | 是否在发给模型之前脱敏 |

库里这一行还有脱敏占位符用的密钥，从不发给客户端。

## 代码位置

| 仓库 | 路径 | 职责 |
|---|---|---|
| ollupi | `gateway/settings.go` | `settings/read`、`settings/update`，回复之后发 `settings/changed` |
| ollupi | `gateway/protocol.go` | `SettingsUpdateParams` |
| ollupi | `repo/settings.go` | `SettingsRow`、`SetRedaction`，默认值 |
| ollupi | `agent/runtime/chat.go` | 每次调用模型前读开关 |
| ollupi | `agent/memory/manager.go` | 记忆提炼按同一个开关脱敏 |
