<script setup lang="ts">
import { computed } from 'vue'
import { withBase } from 'vitepress'

const props = defineProps<{ locale: 'zh' | 'en' }>()

const engineRepo = 'https://github.com/0xfakeSpike/ollupi'
const desktopRepo = 'https://github.com/0xfakeSpike/ollupi-desktop'
const download = `${desktopRepo}/releases/latest`

const copy = {
  zh: {
    title: '池化调度 agent 的运行时',
    lead: 'Ollupi 是一个 Go 运行时。交给它任意多个 agent 会话，它在固定的上限内调度执行，多出来的排队。每一步先写进数据库再执行，个人电脑和云上的服务都能用。',
    home: '/zh/',
    actions: { start: '了解 Ollupi', why: '为什么需要池子', download: '下载桌面端' },
    properties: [
      { title: '会话池化', body: '所有会话共享固定数量的槽位，每个用户可设上限，多出来的排队。等用户、审批或报告的会话让出槽位，只剩数据库记录。' },
      { title: '工具调用池化', body: '下载、编译这类耗时长的调用转入后台，在工具池里执行，有自己的槽位和上限；会话不必干等，结果作为报告送回。模型调用另按服务商配额限流。' },
      { title: '随时可恢复', body: '每一步先落库再执行。发版、重启或崩溃之后，会话从断点继续；中途断掉的工具调用标记为可能已生效，不会重复执行。' },
    ],
    compareTitle: '和逐个隔离有什么不同',
    compareHead: ['', '每个 agent 一个虚拟机或容器', 'Ollupi'],
    compare: [
      ['一个进程承载', '一个会话', '所有会话'],
      ['不活跃的会话', '进程留着，或冷启动重建', '只有数据库记录'],
      ['等用户或审批', '进程挂起，仍占内存', '让出槽位，不占资源'],
      ['调度状态', '进程内存', 'SQLite'],
      ['重启之后', '进行中的工作中断', '从停下的地方继续'],
      ['长时间运行的工具', '占着进程等它跑完', '转入后台的工具池，不占会话的槽位'],
      ['子 agent', '特殊机制或子进程', '普通会话，进同一个会话池'],
      ['定时任务', '外部 cron 启动进程', '到点给会话发消息，进同一个会话池'],
    ],
    numbersTitle: '测出来的数字',
    numbers: [
      { value: '34 MB', label: '5 万个停放会话的常驻内存，每个约 7 KB 磁盘' },
      { value: '5%', label: '1536 个会话同时跑时，一轮比单独跑慢的幅度' },
      { value: '3000', label: '同时提交 3000 个轮次、配额 256：全部完成，没有 429；pi 完成 483 个' },
      { value: '1.3 s', label: '进程被 kill -9 后备用进程接管；每一轮都完成，没有工具执行两次' },
    ],
    numbersNote: '模型和工具都是模拟的，测的是调度和持久化，不是模型质量。测于 v0.18.0，一台 8 GB 内存的 Apple M1，一个 SQLite 数据库。',
    numbersLink: '方法和完整数据',
    productsTitle: '两个项目',
    products: [
      { name: '引擎 ollupi', body: 'Go 库。会话池和工具池、持久化、多用户分片、沙箱、记忆、MCP，通过 WebSocket 上的 JSON-RPC 对外提供。', link: '/zh/integrate/embed', linkText: '接入指南', source: engineRepo },
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
    title: 'A runtime that schedules agents in a pool',
    lead: 'Ollupi is a Go runtime. Give it any number of agent sessions: it runs them within a fixed limit and queues the rest. Every step is written to the database before it runs. It serves a personal computer and a cloud service alike.',
    home: '/',
    actions: { start: 'About Ollupi', why: 'Why a pool', download: 'Download for macOS' },
    properties: [
      { title: 'A pool of sessions', body: 'All sessions share a fixed number of slots, each user can have a limit, and the rest queue. A session waiting on a user, an approval or a report gives up its slot and remains only as database records.' },
      { title: 'A pool of tool calls', body: 'Long calls such as downloads and builds move to the background and run in the tool pool, with its own slots and limit. The session does not sit waiting; the result comes back as a report. Model calls are limited separately to each provider\'s quota.' },
      { title: 'Recoverable at any moment', body: 'Every step is written to the database before it runs. After a release, restart or crash, sessions continue from where they stopped; a tool call cut off midway is marked as possibly done and never runs twice.' },
    ],
    compareTitle: 'How it differs from per-agent isolation',
    compareHead: ['', 'One VM or container per agent', 'Ollupi'],
    compare: [
      ['One process hosts', 'One session', 'All sessions'],
      ['Inactive sessions', 'Process stays up, or is rebuilt with a cold start', 'Database records only'],
      ['Waiting on a user or approval', 'Process sits suspended, still holding memory', 'Leaves the execution pool, using no resources'],
      ['Scheduling state', 'Process memory', 'SQLite'],
      ['After a restart', 'In-progress work is interrupted', 'Continues from where it stopped'],
      ['Long-running tools', 'Hold the process until they finish', 'Move to the background tool pool, outside the session\'s slot'],
      ['Subagents', 'Special mechanism or child process', 'Ordinary sessions, queued in the same pool'],
      ['Scheduled tasks', 'External cron starts a process', 'A message to the session when due, queued in the same pool'],
    ],
    numbersTitle: 'Measured',
    numbers: [
      { value: '34 MB', label: 'resident memory for 50,000 parked sessions, about 7 KB of disk each' },
      { value: '5%', label: 'how much longer a turn takes with 1536 sessions running than alone' },
      { value: '3000', label: 'turns submitted at once with a quota of 256: all complete, no 429; pi finishes 483' },
      { value: '1.3 s', label: 'for a standby to take over after kill -9; every turn completes, no tool call runs twice' },
    ],
    numbersNote: 'The model and tools are simulated, so these measure scheduling and persistence, not model quality. Measured on v0.18.0, one Apple M1 with 8 GB, one SQLite database.',
    numbersLink: 'Method and full data',
    productsTitle: 'Two projects',
    products: [
      { name: 'Engine: ollupi', body: 'A Go library: session and tool pools, persistence, multi-user shards, sandbox, memory and MCP, served as JSON-RPC over WebSocket.', link: '/integrate/embed', linkText: 'Integration guide', source: engineRepo },
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
      <h1>{{ t.title }}</h1>
      <p class="lead">{{ t.lead }}</p>
      <div class="actions">
        <a class="action primary" :href="withBase(t.home + 'intro/overview')">{{ t.actions.start }}</a>
        <a class="action" :href="withBase(t.home + 'intro/why')">{{ t.actions.why }}</a>
        <a class="action" :href="download">{{ t.actions.download }}</a>
      </div>
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

h1 {
  margin-top: 0;
  max-width: 760px;
  font-size: 44px;
  line-height: 1.2;
  font-weight: 650;
  letter-spacing: -0.015em;
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
  padding: 9px 20px;
  border-radius: 999px;
  background: var(--vp-c-bg-alt);
  font-size: 14px;
  font-weight: 600;
  color: var(--vp-c-text-1);
  transition: background-color 0.2s, opacity 0.2s;
}

.action:hover {
  background: var(--vp-c-gutter);
}

.action.primary {
  background: #263b30;
  color: #f3f5f1;
}

.action.primary:hover {
  opacity: 0.9;
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
.dark .landing .action.primary {
  background: #cfe0c9;
  color: #18241d;
}
</style>
