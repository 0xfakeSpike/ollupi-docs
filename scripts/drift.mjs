// Compares the engine version the pages were last checked against
// (docs/.vitepress/engine.json) with the engine checkout, and writes what it
// finds to docs/.vitepress/drift.json for the theme to show on engine pages.
//
// It warns rather than fails, so a new engine release does not stop the site
// from publishing; set DOCS_STRICT=1 to fail instead. In GitHub Actions the
// warnings appear as annotations on the run.
import { createHash } from 'node:crypto'
import { execFileSync } from 'node:child_process'
import { readFile, writeFile } from 'node:fs/promises'
import path from 'node:path'

function git(repo, ...args) {
  try {
    return execFileSync('git', ['-C', repo, ...args], { encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] }).trim()
  } catch {
    return null
  }
}

function warn(message) {
  if (process.env.GITHUB_ACTIONS) console.log(`::warning title=Docs drift::${message}`)
  else console.warn(`docs drift: ${message}`)
}

export async function checkDrift(root, engine) {
  const verified = JSON.parse(await readFile(path.join(root, 'docs/.vitepress/engine.json'), 'utf8'))
  const latest = git(engine, 'describe', '--tags', '--abbrev=0', 'HEAD')

  let protocolSha256 = null
  try {
    const schema = await readFile(path.join(engine, 'gateway/protocol.schema.json'))
    protocolSha256 = createHash('sha256').update(schema).digest('hex')
  } catch {}

  const commits = latest && latest !== verified.version
    ? (git(engine, 'log', '--format=%h %s', `${verified.version}..${latest}`) ?? '').split('\n').filter(Boolean)
    : []

  const drift = {
    verified: verified.version,
    latest,
    protocolChanged: protocolSha256 !== null && protocolSha256 !== verified.protocolSha256,
    commits,
  }
  await writeFile(path.join(root, 'docs/.vitepress/drift.json'), JSON.stringify(drift, null, 2) + '\n')

  const problems = []
  if (latest === null) {
    warn('could not read the engine\'s tags; the pages cannot be compared with a release')
  } else if (latest !== verified.version) {
    problems.push(`the pages were checked against ${verified.version}, the engine is at ${latest} (${commits.length} commits since)`)
  }
  if (drift.protocolChanged) {
    problems.push('gateway/protocol.schema.json differs from the one the protocol page was checked against')
  }
  for (const problem of problems) warn(problem)
  if (problems.length && process.env.DOCS_STRICT === '1') {
    throw new Error('the pages are behind the engine; update them and docs/.vitepress/engine.json')
  }
  return drift
}
