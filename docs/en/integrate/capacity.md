# Capacity and rate limits

How to set the engine's concurrency: slots, the per-user limit, the model connections' concurrent calls and the run time limit, and what raising or lowering each one costs. Measured numbers are on [benchmarks](/benchmarks/) and the scheduling on [execution model](/engine/execution).

::: info Full page in Chinese
This page is being translated. The complete version is [in Chinese](/zh/integrate/capacity).
:::

The full page covers:

- The four parameters and their defaults
- What raising or lowering each one does
- How to choose values, with the related bench results and the conditions they were measured under
- Retries hold their slot
- Telling which limit is binding
- Code locations
