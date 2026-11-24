# Operations

Day-to-day operation of the engine once it is live: how to shut it down, back it up and upgrade it, where to see what it is doing given that the engine writes no logs of its own, and how to troubleshoot it.

::: info Full page in Chinese
This page is being translated. The complete version is [in Chinese](/zh/integrate/operations).
:::

The full page covers:

- Shutdown, backup and upgrades, including upgrading a shard that has a standby
- Logs: the engine writes none; what it hands the host instead
- Monitoring: counting from the store's feed, timing model calls, and read-only queries on the shard database and the catalog
- Troubleshooting: what each error and refused handshake means and what to do
- Code locations
