// Copies the pages and assets that are maintained in the code repositories
// into docs/. OLLUPI_SOURCES is the folder holding both checkouts: the parent
// folder when developing locally, .sources in CI.
import { cp, mkdir, readFile, readdir, rm, writeFile } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { checkDrift } from './drift.mjs'

const root = path.dirname(path.dirname(fileURLToPath(import.meta.url)))
const sources = path.resolve(root, process.env.OLLUPI_SOURCES ?? '..')
const engine = path.join(sources, 'ollupi')
const desktop = path.join(sources, 'ollupi-desktop')

const pages = [
  { from: 'features.md', to: 'zh/reference/features.md' },
  { from: 'roadmap.md', to: 'zh/reference/backlog.md' },
  { from: 'feishu.md', to: 'zh/app/feishu.md' },
]
const routes = Object.fromEntries(
  pages.map(({ from, to }) => [from, `/${to.replace(/\.md$/, '')}`]),
)

function rewriteLinks(markdown, file) {
  return markdown.replace(/\]\((?!https?:|#)([^)]+)\)/g, (_, target) => {
    const route = routes[target]
    if (!route) throw new Error(`${file}: no site page for link "${target}"`)
    return `](${route})`
  })
}

async function syncPage({ from, to }) {
  const markdown = await readFile(path.join(desktop, 'docs', from), 'utf8')
  const page = `---\neditLink: false\n---\n\n${rewriteLinks(markdown, from)}`
  const target = path.join(root, 'docs', to)
  // The page is not committed, so its folder may not exist in a fresh clone.
  await mkdir(path.dirname(target), { recursive: true })
  await writeFile(target, page)
}

async function syncSvgs(from, to) {
  const target = path.join(root, 'docs/public', to)
  await rm(target, { recursive: true, force: true })
  await mkdir(target, { recursive: true })
  const names = (await readdir(from)).filter((name) => name.endsWith('.svg'))
  await Promise.all(
    names.map((name) => cp(path.join(from, name), path.join(target, name))),
  )
}

await Promise.all([
  ...pages.map(syncPage),
  syncSvgs(path.join(engine, 'docs/images'), 'images'),
  syncSvgs(path.join(engine, 'docs/logo'), 'logo'),
])
// After the copies, so that a strict failure never leaves them half done.
await checkDrift(root, engine)
