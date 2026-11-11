# Ollupi Docs

The website and documentation for [ollupi](https://github.com/0xfakeSpike/ollupi) and [ollupi-desktop](https://github.com/0xfakeSpike/ollupi-desktop), published at <https://0xfakespike.github.io/ollupi-docs/>.

## Where things live

- Long-form documentation and the site are in this repository, under `docs/`.
- The figures and logos stay in `ollupi/docs`. `scripts/sync.mjs` copies them in at build time; the copies are not committed.

## Develop

Keep this repository next to the `ollupi` checkout.

```bash
pnpm install
pnpm dev
```

## Publish

A push to `main` deploys the site, and it rebuilds daily to pick up changes in the code repositories. To publish those changes right away:

```bash
gh workflow run deploy.yml -R 0xfakeSpike/ollupi-docs
```
