# Shards and users

One SQLite database is one shard. The users on a shard share its tables, isolated by user. Only one process runs a shard at a time, guaranteed by a lease row in the database; when that process exits, a standby takes over and continues where it stopped. The number of shards sets the capacity. Clients connect only to the router, which hands each connection to the shard its user lives on.

::: info Full page in Chinese
This page is being translated. The complete version, with every detail and code reference, is [in Chinese](/zh/engine/sharding).
:::

The full page covers:

- Isolation between users
- Shards
- Shard leases
- The router
- Token authentication
- Per-user slot limits
- Per-user resources
