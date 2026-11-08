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

`repo.Catalog` 负责用户放置：`ShardOf(user)` 把新用户放进 `accepting` 且用户最少的分片，`Place(user, shard)` 由运维在用户有数据之前指定。`Publish(shard, address, accepting)` 由拿到租约的进程在 `Start` 返回后调用。租约的时间参数、围栏、`OnShard` 校验、令牌读法都在[分片与多用户](/zh/engine/sharding)。
