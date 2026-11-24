# Shards and leases

One SQLite database is one shard. The users on a shard share its tables, isolated by user. The engine itself knows nothing of shards: the `shard` package runs a process as one shard, holding that shard's lease in the deployment's catalog, so only one process runs a shard at a time; when the holder exits, a standby process waiting on the lease takes over and continues where it stopped. The number of shards sets the capacity. Clients connect to one address and never learn which shard they are on: a load balancer's callout or the router looks the user up in the catalog and sends the connection to the user's shard.

::: info Full page in Chinese
This page is being translated. The complete version, with every detail and code reference, is [in Chinese](/zh/engine/sharding).
:::

The full page covers:

- Why it is designed this way
- Isolation between users
- Shards
- Shard leases
- The router
- Token authentication
- Per-user slot limits
- Per-user resources
- Limits and known issues
