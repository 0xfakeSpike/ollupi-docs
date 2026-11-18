# Shards and users

One SQLite database is one shard. The users on a shard share its tables, isolated by user. The engine knows nothing of shards: package `shard` runs a process as one, holding the shard's lease in the deployment's catalog, so only one process runs a shard at a time; when the holder exits, a standby waiting on the lease takes over and continues where it stopped. The number of shards sets the capacity. Clients reach one address and never learn their shard: a load balancer's callout or the router looks the user up in the catalog and sends each connection to the user's shard.

::: info Full page in Chinese
This page is being translated. The complete version, with every detail and code reference, is [in Chinese](/zh/engine/sharding).
:::

The full page covers:

- Isolation between users
- Shards and the catalog, and how new users are placed
- Shard leases: timing, takeover, losing a lease, epochs and load reports
- The router, the load balancer callout and the shard's own check
- Token authentication
- Per-user slot limits
- Per-user resources
