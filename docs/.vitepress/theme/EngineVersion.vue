<script setup lang="ts">
// Says which engine release the engine pages were checked against, and whether
// the engine has moved on since. The numbers come from engine.json and from
// drift.json, which scripts/drift.mjs writes at build time.
import { computed } from 'vue'
import { useData } from 'vitepress'
import engine from '../engine.json'

type Drift = { verified: string; latest: string | null; protocolChanged: boolean; commits: string[] }

// drift.json is not committed; without it the page only names its version.
const found = import.meta.glob<Drift>('../drift.json', { eager: true, import: 'default' })
const drift: Drift | undefined = Object.values(found)[0]

const { page } = useData()
const repository = 'https://github.com/0xfakeSpike/ollupi'

const zh = computed(() => page.value.relativePath.startsWith('zh/'))
// The same page in either language.
const file = computed(() => page.value.relativePath.replace(/^zh\//, ''))
const shown = computed(() =>
  file.value.startsWith('engine/') ||
  file.value.startsWith('benchmarks/') ||
  file.value.startsWith('integrate/') ||
  file.value === 'intro/concepts.md',
)
const behind = computed(() => !!drift?.latest && drift.latest !== engine.version)
const protocolPage = computed(() => file.value === 'integrate/protocol.md')
const benchmarks = computed(() => file.value.startsWith('benchmarks/'))
const tree = `${repository}/tree/${engine.version}`
const compare = computed(() => `${repository}/compare/${engine.version}...${drift?.latest}`)
</script>

<template>
  <div v-if="shown" class="engine-version" :class="{ behind: behind || (protocolPage && drift?.protocolChanged) }">
    <template v-if="zh">
      <span>本页按引擎 <a :href="tree">{{ engine.version }}</a> 核对。</span>
      <span v-if="benchmarks">页内的数字测于更早的版本，见第一节。</span>
      <span v-if="behind">引擎已发布到 {{ drift!.latest }}，之后的 <a :href="compare">{{ drift!.commits.length }} 个提交</a>可能还没写进来。</span>
      <span v-if="protocolPage && drift?.protocolChanged">引擎的协议契约（protocol.schema.json）已经变了，本页可能和它不一致。</span>
    </template>
    <template v-else>
      <span>Checked against engine <a :href="tree">{{ engine.version }}</a>.</span>
      <span v-if="benchmarks">The numbers on this page were measured on an earlier version; see the first section.</span>
      <span v-if="behind">The engine has since released {{ drift!.latest }}; the <a :href="compare">{{ drift!.commits.length }} commits</a> after it may not be covered yet.</span>
      <span v-if="protocolPage && drift?.protocolChanged">The engine's protocol contract (protocol.schema.json) has changed; this page may not match it.</span>
    </template>
  </div>
</template>

<style scoped>
.engine-version {
  margin-bottom: 24px;
  padding: 8px 12px;
  border-left: 3px solid var(--vp-c-divider);
  font-size: 13px;
  line-height: 1.6;
  color: var(--vp-c-text-2);
}
.engine-version.behind {
  border-left-color: var(--vp-c-warning-1);
  background: var(--vp-c-warning-soft);
  color: var(--vp-c-text-1);
}
</style>
