// Copies the figures and logos that are maintained in the engine repository
// into docs/public. OLLUPI_SOURCES is the folder holding the engine checkout:
// the parent folder when developing locally, .sources in CI.
import { cp, mkdir, readdir, rm } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { checkDrift } from './drift.mjs'

const root = path.dirname(path.dirname(fileURLToPath(import.meta.url)))
const sources = path.resolve(root, process.env.OLLUPI_SOURCES ?? '..')
const engine = path.join(sources, 'ollupi')

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
  syncSvgs(path.join(engine, 'docs/images'), 'images'),
  syncSvgs(path.join(engine, 'docs/logo'), 'logo'),
])
// After the copies, so that a strict failure never leaves them half done.
await checkDrift(root, engine)
