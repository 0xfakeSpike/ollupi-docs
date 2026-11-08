<script setup lang="ts">
import { computed } from 'vue'
import { withBase } from 'vitepress'

const props = defineProps<{ locale: 'zh' | 'en' }>()

const engineRepo = 'https://github.com/0xfakeSpike/ollupi'
const desktopRepo = 'https://github.com/0xfakeSpike/ollupi-desktop'
const download = `${desktopRepo}/releases/latest`

const copy = {
  zh: {
    title: '大规模个人 agent 服务的运行时',
    lead: 'Ollupi 是一个 Go agent 框架。它不给每个 agent 开虚拟机或容器，而是池化 runtime，把每一步运行状态写进数据库。',
    home: '/zh/',
    actions: { docs: '为什么做 Ollupi', download: '下载桌面端', source: 'GitHub' },
    properties: [
      { title: '随时可恢复', body: '每一步先落库再执行，调度状态不留在内存。发版、重启或崩溃之后，会话从停下的地方继续。' },
      { title: '不活跃的会话没有成本', body: '等用户、等审批或等子代理的会话离开执行池，只剩数据库记录，不占内存和算力。' },
      { title: '并发受控', body: '执行池按槽位调度，模型调用按连接限流，和服务商账户配额对齐，突发请求排队。' },
    ],
    compareTitle: '和逐个隔离有什么不同',
    compareHead: ['', '每个 agent 一个虚拟机或容器', 'Ollupi'],
    compare: [
      ['一个进程承载', '一个会话', '所有会话'],
      ['不活跃的会话', '进程留着，或冷启动重建', '只有数据库记录'],
      ['等用户或审批', '进程挂起，仍占内存', '离开执行池，不占资源'],
      ['调度状态', '进程内存', 'SQLite'],
      ['重启之后', '进行中的工作中断', '从停下的地方继续'],
      ['子代理', '特殊机制或子进程', '普通会话，进同一个池'],
      ['定时任务', '外部 cron 启动进程', '到点给会话发消息，进同一个池'],
    ],
    numbersTitle: '测出来的数字',
    numbers: [
      { value: '14 MB', label: '5 万个闲置会话增加的常驻内存' },
      { value: '2.3 KB', label: '每个闲置会话占用的数据库空间' },
      { value: '160 KB', label: '每个活跃会话的内存；每会话一个进程时是 20.0 MB' },
      { value: '4096', label: '一台 8 GB 的 M1 上同时活跃的会话，p50 20.9 秒，单独运行约 17 秒' },
    ],
    numbersNote: '模型和工具都是模拟的，测的是调度和持久化，不是模型质量。这些数字在多用户、分片和沙箱接口改动之前测得，之后没有重测。',
    numbersLink: '方法和完整数据',
    productsTitle: '两个项目',
    products: [
      { name: '引擎 ollupi', body: 'Go 库。执行池、持久化、多用户分片、沙箱、记忆、MCP，通过 WebSocket 上的 JSON-RPC 对外提供。', link: '/zh/engine/architecture', linkText: '引擎文档', source: engineRepo },
      { name: '桌面端 ollupi-desktop', body: '基于引擎的 macOS 应用。内置浏览器、文件和改动面板、飞书机器人，状态存在本机。需要 macOS 12 或更新和 Apple 芯片。', link: '/zh/app/install', linkText: '上手指南', source: desktopRepo },
    ],
    notesTitle: '公开地做',
    notesBody: '接下来做什么、每一步怎样算做完，写在路线图里；做过哪些决定、放弃了什么、走过哪些弯路，按提交记录写了下来。',
    notesLinks: [
      { text: '路线图', link: '/zh/roadmap' },
      { text: '文章', link: '/zh/articles/' },
      { text: '设计决策', link: '/zh/reference/decisions' },
      { text: '开发历程', link: '/zh/reference/history' },
    ],
  },
  en: {
    title: 'A runtime for personal agent services at scale',
    lead: 'Ollupi is a Go agent framework. Instead of isolating each agent in its own VM or container, it pools the runtime and persists every step of each run.',
    home: '/',
    actions: { docs: 'Why Ollupi', download: 'Download for macOS', source: 'GitHub' },
    properties: [
      { title: 'Recoverable at any moment', body: 'Every step is written to the database before it runs, and no scheduling state lives in memory. After a release, restart or crash, sessions continue from where they stopped.' },
      { title: 'Inactive sessions cost nothing', body: 'A session waiting on a user, an approval or a subagent leaves the execution pool and remains only as database records.' },
      { title: 'Controlled concurrency', body: 'The execution pool schedules by slot, and model calls are limited per connection to match the provider\'s account quota. Bursts queue.' },
    ],
    compareTitle: 'How it differs from per-agent isolation',
    compareHead: ['', 'One VM or container per agent', 'Ollupi'],
    compare: [
      ['One process hosts', 'One session', 'All sessions'],
      ['Inactive sessions', 'Process stays up, or is rebuilt with a cold start', 'Database records only'],
      ['Waiting on a user or approval', 'Process sits suspended, still holding memory', 'Leaves the execution pool, using no resources'],
      ['Scheduling state', 'Process memory', 'SQLite'],
      ['After a restart', 'In-progress work is interrupted', 'Continues from where it stopped'],
      ['Subagents', 'Special mechanism or child process', 'Ordinary sessions, queued in the same pool'],
      ['Scheduled tasks', 'External cron starts a process', 'A message to the session when due, queued in the same pool'],
    ],
    numbersTitle: 'Measured',
    numbers: [
      { value: '14 MB', label: 'resident memory added by 50,000 parked sessions' },
      { value: '2.3 KB', label: 'database space per parked session' },
      { value: '160 KB', label: 'memory per active session, against 20.0 MB with one process per session' },
      { value: '4096', label: 'active sessions on one 8 GB M1, p50 20.9 s against about 17 s alone' },
    ],
    numbersNote: 'The model and tools are simulated, so these measure scheduling and persistence, not model quality. They predate the multi-user, shard and sandbox interface changes and have not been re-measured.',
    numbersLink: 'Method and full data',
    productsTitle: 'Two projects',
    products: [
      { name: 'Engine: ollupi', body: 'A Go library: execution pool, persistence, multi-user shards, sandbox, memory and MCP, served as JSON-RPC over WebSocket.', link: '/engine/architecture', linkText: 'Engine manual', source: engineRepo },
      { name: 'Desktop: ollupi-desktop', body: 'A macOS app built on the engine, with a built-in browser, file and diff panels and a Feishu bot. State stays on your Mac. Needs macOS 12 or later on Apple silicon.', link: '/app/install', linkText: 'Getting started', source: desktopRepo },
    ],
    notesTitle: 'Built in public',
    notesBody: 'What comes next and how each step will be judged done is on the roadmap. The decisions made, the options dropped and the wrong turns taken are written down from the commit history.',
    notesLinks: [
      { text: 'Roadmap', link: '/roadmap' },
      { text: 'Articles', link: '/articles/' },
      { text: 'Design decisions', link: '/reference/decisions' },
      { text: 'History', link: '/reference/history' },
    ],
  },
}

const t = computed(() => copy[props.locale])
</script>

<template>
  <div class="landing">
    <section class="hero">
      <img class="logo logo-light" :src="withBase('/logo/logo.svg')" alt="Ollupi" />
      <img class="logo logo-dark" :src="withBase('/logo/logo-dark.svg')" alt="Ollupi" />
      <h1>{{ t.title }}</h1>
      <p class="lead">{{ t.lead }}</p>
      <div class="actions">
        <a class="action primary" :href="withBase(t.home + 'intro/why')">{{ t.actions.docs }}</a>
        <a class="action" :href="download">{{ t.actions.download }}</a>
        <a class="action" :href="engineRepo">{{ t.actions.source }}</a>
      </div>
    </section>

    <section class="properties">
      <div v-for="item in t.properties" :key="item.title">
        <h2>{{ item.title }}</h2>
        <p>{{ item.body }}</p>
      </div>
    </section>

    <section>
      <img class="figure" :src="withBase('/images/architecture.svg')" alt="" />
    </section>

    <section>
      <h2 class="section-title">{{ t.compareTitle }}</h2>
      <div class="table-scroll">
        <table>
          <thead>
            <tr>
              <th v-for="head in t.compareHead" :key="head">{{ head }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in t.compare" :key="row[0]">
              <td v-for="cell in row" :key="cell">{{ cell }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <section>
      <h2 class="section-title">{{ t.numbersTitle }}</h2>
      <div class="numbers">
        <div v-for="item in t.numbers" :key="item.value">
          <strong>{{ item.value }}</strong>
          <span>{{ item.label }}</span>
        </div>
      </div>
      <p class="note">
        {{ t.numbersNote }}
        <a :href="withBase(t.home + 'benchmarks/')">{{ t.numbersLink }}</a>
      </p>
    </section>

    <section>
      <h2 class="section-title">{{ t.productsTitle }}</h2>
      <div class="products">
        <div v-for="item in t.products" :key="item.name">
          <h3>{{ item.name }}</h3>
          <p>{{ item.body }}</p>
          <a :href="withBase(item.link)">{{ item.linkText }}</a>
          <a :href="item.source">GitHub</a>
        </div>
      </div>
    </section>

    <section class="notes">
      <h2 class="section-title">{{ t.notesTitle }}</h2>
      <p>{{ t.notesBody }}</p>
      <a v-for="item in t.notesLinks" :key="item.link" :href="withBase(item.link)">{{ item.text }}</a>
    </section>
  </div>
</template>

<style scoped>
.landing {
  max-width: 1040px;
  margin: 0 auto;
  padding: 0 24px 96px;
}

section {
  margin-top: 72px;
}

.hero {
  margin-top: 0;
  padding-top: 72px;
}

.logo {
  width: 240px;
  height: auto;
  margin-left: -12px;
}

.logo-dark {
  display: none;
}

h1 {
  margin-top: 28px;
  max-width: 760px;
  font-size: 44px;
  line-height: 1.2;
  font-weight: 650;
  letter-spacing: -0.01em;
  color: var(--vp-c-text-1);
}

.lead {
  margin-top: 16px;
  max-width: 680px;
  font-size: 18px;
  line-height: 1.7;
  color: var(--vp-c-text-2);
}

.actions {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 28px;
}

.action {
  padding: 9px 18px;
  border: 1px solid var(--vp-c-divider);
  border-radius: 8px;
  font-size: 14px;
  font-weight: 500;
  color: var(--vp-c-text-1);
  transition: border-color 0.2s;
}

.action:hover {
  border-color: var(--vp-c-brand-1);
}

.action.primary {
  border-color: #312e81;
  background: #312e81;
  color: #ffffff;
}

.properties {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 32px;
}

.properties h2,
.products h3 {
  font-size: 16px;
  font-weight: 600;
  color: var(--vp-c-text-1);
}

.properties p,
.products p,
.notes p {
  margin-top: 8px;
  font-size: 14px;
  line-height: 1.7;
  color: var(--vp-c-text-2);
}

.figure {
  width: 100%;
  padding: 16px;
  border: 1px solid var(--vp-c-divider);
  border-radius: 12px;
  background: #ffffff;
}

.section-title {
  margin-bottom: 20px;
  font-size: 22px;
  font-weight: 600;
  color: var(--vp-c-text-1);
}

.table-scroll {
  overflow-x: auto;
}

table {
  display: table;
  width: 100%;
  margin: 0;
  border-collapse: collapse;
  font-size: 14px;
}

th,
td {
  padding: 10px 14px;
  border: 0;
  border-bottom: 1px solid var(--vp-c-divider);
  background: transparent;
  text-align: left;
  line-height: 1.6;
}

th {
  font-weight: 600;
  color: var(--vp-c-text-1);
}

td {
  color: var(--vp-c-text-2);
}

td:first-child {
  color: var(--vp-c-text-1);
  white-space: nowrap;
}

td:last-child {
  color: var(--vp-c-text-1);
}

.numbers {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 24px;
}

.numbers strong {
  display: block;
  font-family: var(--vp-font-family-mono);
  font-size: 30px;
  font-weight: 600;
  line-height: 1.3;
  color: var(--vp-c-brand-1);
}

.numbers span {
  display: block;
  margin-top: 6px;
  font-size: 13px;
  line-height: 1.6;
  color: var(--vp-c-text-2);
}

.note {
  margin-top: 20px;
  font-size: 13px;
  line-height: 1.7;
  color: var(--vp-c-text-3);
}

.landing a:not(.action) {
  color: var(--vp-c-brand-1);
  font-size: 14px;
}

.products {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 20px;
}

.products > div {
  padding: 20px;
  border: 1px solid var(--vp-c-divider);
  border-radius: 12px;
}

.products a {
  display: inline-block;
  margin-top: 12px;
  margin-right: 16px;
}

.notes a {
  display: inline-block;
  margin-top: 12px;
  margin-right: 16px;
}

@media (max-width: 768px) {
  .landing {
    padding: 0 16px 64px;
  }

  section {
    margin-top: 48px;
  }

  .hero {
    padding-top: 40px;
  }

  h1 {
    font-size: 30px;
  }

  .lead {
    font-size: 16px;
  }

  .properties,
  .products {
    grid-template-columns: 1fr;
    gap: 20px;
  }

  .numbers {
    grid-template-columns: repeat(2, 1fr);
  }

  td:first-child {
    white-space: normal;
  }
}
</style>

<style>
.dark .landing .logo-light {
  display: none;
}

.dark .landing .logo-dark {
  display: block;
}

.dark .landing .action.primary {
  border-color: #a5b4fc;
  background: #a5b4fc;
  color: #1e1b4b;
}
</style>
