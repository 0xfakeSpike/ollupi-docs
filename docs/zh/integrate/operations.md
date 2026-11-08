# 运维

这一页讲引擎上线之后的日常运维：怎样关闭、备份和升级，看哪些日志，出了问题怎样排查。

## 关闭、备份与升级

关闭顺序：先停网关，再停附属组件，最后关库。

| 顺序 | 动作 | 原因 |
|---|---|---|
| 1 | `http.Server.Shutdown`，或让 `gateway.Server.Serve` 的 ctx 结束 | 关掉入口，不再有新的 `turn/start` 写库；`Serve` 最多等 5 秒 |
| 2 | 取消 agent 和附属组件的 ctx，等它们返回 | 定时器不再发轮次，记忆提炼收尾 |
| 3 | `a.Wait()` | 等槽位里的 goroutine 退出，并释放分片租约 |
| 4 | `db.Close()` | 租约释放、所有写入结束之后才关库 |

顺序错了后果很具体：先关库会让槽位里的写入失败，轮次停在中间状态；租约没释放就关库，备用进程要等租约过期才接管。

备份：库是单个文件 `<home>/data/ollupi.sqlite`，WAL 模式下还有同目录的 `-wal` 和 `-shm`，要三个一起拷或先停进程；分片目录库是另一个文件，一起备份。不要用 `VACUUM` 做快照：`items` 没有 INTEGER PRIMARY KEY，`VACUUM` 会重编号 rowid，而 `items_search` 靠 rowid 回读，之后必须重建索引，见[持久化](/zh/engine/persistence)。

升级：`repo.Open` 会读 `PRAGMA user_version` 并按 `repo/migrations` 逐级升级，步骤只往前走，没有回滚。库版本高于程序知道的步数时 `Open` 直接失败：

```
the database is at schema version 3, from a newer ollupi; this one knows up to 2
```

所以升级前先备份库，也别指望换回旧二进制能打开新库。二进制必须带 `-tags sqlite_fts5` 构建，否则 `repo/fts5.go` 让编译直接失败。


## 日志

::: info 待写
引擎用 `log/slog` 输出的关键日志：轮次开始与结束、崩溃恢复、租约续约失败、客户端被替换等，以及运维该盯哪些。引擎目前没有指标和链路追踪，见[路线图](/zh/roadmap)。
:::

## 故障排查

::: info 待写
常见故障的现象、原因和处理。
:::
