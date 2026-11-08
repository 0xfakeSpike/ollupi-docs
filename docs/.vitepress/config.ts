import { defineConfig, type MarkdownRenderer } from 'vitepress'

const base = '/ollupi-docs/'
const repository = 'https://github.com/0xfakeSpike/ollupi'

const guide = [
  {
    text: '开始',
    items: [
      { text: '项目概览', link: '/guide/overview' },
      { text: '核心概念', link: '/guide/concepts' },
      { text: '桌面端上手', link: '/guide/desktop-quickstart' },
      { text: '把引擎嵌进服务', link: '/guide/engine-quickstart' },
    ],
  },
]

const engine = [
  {
    text: '内核',
    items: [
      { text: '架构总览', link: '/engine/architecture' },
      { text: '执行模型', link: '/engine/execution' },
      { text: '持久化', link: '/engine/persistence' },
      { text: '多用户与分片', link: '/engine/sharding' },
      { text: '上下文管理', link: '/engine/context' },
    ],
  },
  {
    text: '能力',
    items: [
      { text: '模型接入', link: '/engine/models' },
      { text: '工具系统', link: '/engine/tools' },
      { text: '技能与 MCP', link: '/engine/skills-mcp' },
      { text: '记忆', link: '/engine/memory' },
      { text: '定时任务', link: '/engine/cron' },
      { text: '搜索', link: '/engine/search' },
    ],
  },
  {
    text: '安全',
    items: [
      { text: '权限与审批', link: '/engine/permissions' },
      { text: '沙箱', link: '/engine/sandbox' },
      { text: '脱敏', link: '/engine/redaction' },
    ],
  },
  {
    text: '接口与性能',
    items: [
      { text: '协议', link: '/engine/protocol' },
      { text: '性能基准', link: '/engine/benchmarks' },
    ],
  },
]

const desktop = [
  {
    text: '结构',
    items: [
      { text: '架构总览', link: '/desktop/architecture' },
      { text: 'Sidecar 后端', link: '/desktop/sidecar' },
      { text: '主进程', link: '/desktop/main-process' },
      { text: '界面', link: '/desktop/renderer' },
      { text: '配置与数据', link: '/desktop/config' },
    ],
  },
  {
    text: '功能',
    items: [
      { text: '侧边面板', link: '/desktop/side-panels' },
      { text: '内置浏览器', link: '/desktop/browser' },
      { text: '飞书机器人实现', link: '/desktop/feishu-bot' },
      { text: '飞书机器人设置', link: '/desktop/feishu' },
    ],
  },
  {
    text: '工程',
    items: [
      { text: '设计语言', link: '/desktop/design' },
      { text: '构建与发布', link: '/desktop/release' },
    ],
  },
]

const reference = [
  {
    text: '参考',
    items: [
      { text: '功能清单', link: '/reference/features' },
      { text: '路线图', link: '/reference/roadmap' },
      { text: '术语表', link: '/reference/glossary' },
    ],
  },
]

const notes = [
  {
    text: '沉淀',
    items: [
      { text: '设计决策', link: '/notes/decisions' },
      { text: '开发历程', link: '/notes/history' },
    ],
  },
]

// Runs in the build and in the browser, so it must not use anything from this
// module. The default tokenizer splits on spaces and cannot index Chinese.
function tokenize(text: string) {
  const segmenter = new Intl.Segmenter('zh', { granularity: 'word' })
  return Array.from(segmenter.segment(text))
    .filter((part) => part.isWordLike)
    .map((part) => part.segment)
}

function renderMermaidFences(md: MarkdownRenderer) {
  const fence = md.renderer.rules.fence!
  md.renderer.rules.fence = (tokens, index, options, env, self) => {
    const token = tokens[index]
    if (token.info.trim() !== 'mermaid') return fence(tokens, index, options, env, self)
    return `<MermaidDiagram code="${encodeURIComponent(token.content)}" />`
  }
}

export default defineConfig({
  base,
  title: 'Ollupi',
  cleanUrls: true,
  lastUpdated: true,
  sitemap: { hostname: `https://0xfakespike.github.io${base}` },
  head: [['link', { rel: 'icon', href: `${base}logo/favicon.svg` }]],
  locales: {
    root: {
      lang: 'zh-CN',
      label: '简体中文',
      description: '面向大规模个人 agent 服务的 Go 框架，以及基于它的 macOS 桌面端。',
      themeConfig: {
        nav: [
          { text: '指南', link: '/guide/overview', activeMatch: '^/guide/' },
          { text: '引擎', link: '/engine/architecture', activeMatch: '^/engine/' },
          { text: '桌面端', link: '/desktop/architecture', activeMatch: '^/desktop/' },
          { text: '参考', link: '/reference/features', activeMatch: '^/reference/' },
          { text: '沉淀', link: '/notes/decisions', activeMatch: '^/notes/' },
        ],
        sidebar: {
          '/guide/': guide,
          '/engine/': engine,
          '/desktop/': desktop,
          '/reference/': reference,
          '/notes/': notes,
        },
        outline: { label: '本页内容', level: [2, 3] },
        docFooter: { prev: '上一页', next: '下一页' },
        lastUpdated: { text: '最后更新' },
        editLink: {
          pattern: 'https://github.com/0xfakeSpike/ollupi-docs/edit/main/docs/:path',
          text: '修改这一页',
        },
        darkModeSwitchLabel: '外观',
        lightModeSwitchTitle: '切换到浅色',
        darkModeSwitchTitle: '切换到深色',
        sidebarMenuLabel: '目录',
        returnToTopLabel: '回到顶部',
        langMenuLabel: '切换语言',
      },
    },
    en: {
      lang: 'en',
      label: 'English',
      description:
        'A Go agent framework for massively concurrent personal agent services, and the macOS desktop app built on it.',
      themeConfig: {
        nav: [
          { text: 'Docs (Chinese)', link: '/guide/overview' },
          { text: 'Benchmarks (Chinese)', link: '/engine/benchmarks' },
        ],
      },
    },
  },
  themeConfig: {
    logo: { light: '/logo/mark.svg', dark: '/logo/mark.svg', alt: '' },
    socialLinks: [{ icon: 'github', link: repository }],
    footer: { message: 'MIT License' },
    search: {
      provider: 'local',
      options: {
        miniSearch: {
          options: { tokenize },
          searchOptions: { combineWith: 'AND', prefix: true },
        },
        translations: {
          button: { buttonText: '搜索', buttonAriaLabel: '搜索' },
          modal: {
            noResultsText: '没有结果',
            resetButtonTitle: '清除',
            displayDetails: '显示详情',
            footer: { selectText: '选择', navigateText: '切换', closeText: '关闭' },
          },
        },
      },
    },
  },
  markdown: { config: renderMermaidFences },
  vite: { optimizeDeps: { include: ['mermaid'] } },
})
