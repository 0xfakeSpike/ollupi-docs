# Multi-user deployment

How to deploy the engine as a service of several processes and several shards: how many shard processes, routing layers and catalogs to run, how users are placed on shards, and how a standby process takes over when a process dies. The details of the mechanism (leases, epoch fencing, the placement algorithm) are on [shards and leases](/engine/sharding).

::: info Full page in Chinese
This page is being translated. The complete version, with a deployment that was run on one machine against v0.17.1, is [in Chinese](/zh/integrate/deploy).
:::

The full page covers:

- The three roles: shard processes, the routing layer (`router.Router` or a load balancer with the `router/extproc` callout), the catalog
- A minimal multi-process deployment: one binary as router, callout or shard
- The catalog: who acquires, renews, releases, locates and places
- Lease length: what a longer or shorter TTL costs
- What clients see during a takeover
- What is not there yet
- Code locations
