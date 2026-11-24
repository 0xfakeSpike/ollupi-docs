import { defineConfig, type DefaultTheme, type MarkdownRenderer } from 'vitepress'

const base = '/ollupi-docs/'
const repository = 'https://github.com/0xfakeSpike/ollupi'

// The site is English first: docs/en/ is served at the root and docs/zh/ under
// /zh/, with the same paths. Each sidebar is written once with both titles and
// built per locale.
type Entry = { en: string; zh: string; link: string; zhOnly?: boolean }
type Group = { en: string; zh: string; items: Entry[] }

// One sidebar per reader group. The key is the URL folder; every page of a
// group lives in that folder, so the sidebar follows the reader around.
// `shared` gives a folder or page outside these the sidebar of a group.
const about: Group[] = [
  {
    en: 'About Ollupi',
    zh: '了解 Ollupi',
    items: [
      { en: 'Overview', zh: '项目概览', link: 'intro/overview' },
      { en: 'Core concepts', zh: '核心概念', link: 'intro/concepts' },
      { en: 'Why Ollupi', zh: 'agent 需要一个池子', link: 'intro/why' },
    ],
  },
  {
    en: 'Benchmarks',
    zh: '基准',
    items: [
      { en: 'Benchmarks', zh: '性能基准', link: 'benchmarks/' },
      { en: 'What we measure next', zh: '接下来要测的', link: 'benchmarks/plan' },
    ],
  },
]

const more: Group[] = [
  {
    en: 'Plans',
    zh: '计划',
    items: [{ en: 'Roadmap', zh: '路线图', link: 'roadmap' }],
  },
  {
    en: 'Reference',
    zh: '参考',
    items: [
      { en: 'Glossary', zh: '术语表', link: 'reference/glossary' },
      { en: 'Design decisions', zh: '设计决策', link: 'reference/decisions' },
      { en: 'History', zh: '开发历程', link: 'reference/history' },
      { en: 'Feature list', zh: '功能清单', link: 'reference/features', zhOnly: true },
    ],
  },
]

const sections: Record<string, Group[]> = {
  intro: about,
  app: [
    {
      en: 'Desktop app guide',
      zh: '桌面端使用手册',
      items: [
        { en: 'Install and get started', zh: '安装与上手', link: 'app/install' },
        { en: 'Workspaces and sessions', zh: '工作区与会话', link: 'app/sessions' },
        { en: 'Approvals and permissions', zh: '审批与权限', link: 'app/permissions' },
        { en: 'Browser, files, terminal', zh: '浏览器、文件、环境与终端', link: 'app/panels' },
        { en: 'Skills, MCP and tools', zh: '技能、MCP 与工具', link: 'app/capabilities' },
        { en: 'Scheduled tasks and memory', zh: '定时任务与记忆', link: 'app/automation' },
        { en: 'Feishu bot', zh: '飞书机器人', link: 'app/feishu', zhOnly: true },
        { en: 'Configuration and data', zh: '配置与数据', link: 'app/config' },
        { en: 'Troubleshooting', zh: '常见问题', link: 'app/troubleshooting' },
      ],
    },
  ],
  integrate: [
    {
      en: 'Integration guide',
      zh: '引擎集成指南',
      items: [
        { en: 'Embed the engine', zh: '把引擎嵌进服务', link: 'integrate/embed' },
        { en: 'Multi-user deployment', zh: '多用户与分片部署', link: 'integrate/deploy' },
        { en: 'Capacity and rate limits', zh: '容量规划与限流', link: 'integrate/capacity' },
        { en: 'Extension points', zh: '扩展点', link: 'integrate/extend' },
        { en: 'Operations', zh: '运维', link: 'integrate/operations' },
        { en: 'Config reference', zh: 'Config 参考', link: 'integrate/config' },
      ],
    },
    {
      en: 'Gateway protocol',
      zh: '网关协议',
      items: [
        { en: 'Gateway protocol', zh: '网关协议', link: 'integrate/protocol' },
        { en: 'Writing a client', zh: '写一个客户端', link: 'integrate/client' },
        { en: 'Protocol type index', zh: '协议类型索引', link: 'integrate/protocol-types' },
      ],
    },
    {
      en: 'Protocol methods',
      zh: '协议方法',
      items: [
        { en: 'Sessions', zh: '会话', link: 'integrate/protocol/threads' },
        { en: 'Turns and items', zh: '一轮与条目', link: 'integrate/protocol/turns' },
        { en: 'Approvals and questions', zh: '审批与提问', link: 'integrate/protocol/approvals' },
        { en: 'Permissions', zh: '权限', link: 'integrate/protocol/permissions' },
        { en: 'Workspaces and environments', zh: '工作区与执行环境', link: 'integrate/protocol/workspaces' },
        { en: 'Models, tools and MCP', zh: '模型、工具与 MCP', link: 'integrate/protocol/models-tools' },
        { en: 'Scheduled tasks', zh: '定时任务', link: 'integrate/protocol/cron' },
        { en: 'Memory', zh: '记忆', link: 'integrate/protocol/memory' },
        { en: 'Search', zh: '搜索', link: 'integrate/protocol/search' },
        { en: 'Settings', zh: '设置', link: 'integrate/protocol/settings' },
        { en: 'Todos', zh: '待办', link: 'integrate/protocol/todos' },
        { en: 'Usage', zh: '用量', link: 'integrate/protocol/usage' },
      ],
    },
  ],
  engine: [
    {
      en: 'Runtime',
      zh: '运行时',
      items: [
        { en: 'Engine architecture', zh: '引擎架构', link: 'engine/architecture' },
        { en: 'Execution model', zh: '执行模型', link: 'engine/execution' },
        { en: 'Persistence and recovery', zh: '持久化与崩溃恢复', link: 'engine/persistence' },
        { en: 'Shards and leases', zh: '分片与租约', link: 'engine/sharding' },
        { en: 'Execution traces', zh: '执行轨迹', link: 'engine/traces' },
      ],
    },
    {
      en: 'What the agent can do',
      zh: 'agent 能力',
      items: [
        { en: 'Context management', zh: '上下文管理', link: 'engine/context' },
        { en: 'Models', zh: '模型接入', link: 'engine/models' },
        { en: 'Tools', zh: '工具系统', link: 'engine/tools' },
        { en: 'Skills and MCP', zh: '技能与 MCP', link: 'engine/skills-mcp' },
        { en: 'Memory', zh: '记忆', link: 'engine/memory' },
        { en: 'Scheduled tasks', zh: '定时任务', link: 'engine/cron' },
        { en: 'Search', zh: '搜索', link: 'engine/search' },
        { en: 'Hub', zh: '中枢', link: 'engine/hub' },
      ],
    },
    {
      en: 'Workspaces and safety',
      zh: '工作区与安全',
      items: [
        { en: 'Security overview', zh: '安全总览', link: 'engine/security' },
        { en: 'Workspaces', zh: '工作区', link: 'engine/workspace' },
        { en: 'Approvals and permissions', zh: '审批与权限', link: 'engine/permissions' },
        { en: 'Sandbox', zh: '沙箱', link: 'engine/sandbox' },
        { en: 'Redaction', zh: '脱敏', link: 'engine/redaction' },
      ],
    },
  ],
  desktop: [
    {
      en: 'Structure',
      zh: '结构',
      items: [
        { en: 'Desktop architecture', zh: '桌面端架构', link: 'desktop/architecture' },
        { en: 'Sidecar backend', zh: 'Sidecar', link: 'desktop/sidecar' },
        { en: 'Main process', zh: '主进程', link: 'desktop/main-process' },
        { en: 'Renderer', zh: '渲染进程', link: 'desktop/renderer' },
        { en: 'Configuration internals', zh: '配置的实现', link: 'desktop/config' },
      ],
    },
    {
      en: 'Features',
      zh: '功能',
      items: [
        { en: 'Side panels', zh: '侧边面板', link: 'desktop/side-panels' },
        { en: 'Built-in browser', zh: '内置浏览器', link: 'desktop/browser' },
        { en: 'Feishu bot', zh: '飞书机器人', link: 'desktop/feishu-bot' },
      ],
    },
    {
      en: 'Brand and release',
      zh: '品牌与发布',
      items: [
        { en: 'Brand', zh: '品牌', link: 'desktop/brand' },
        { en: 'Design language', zh: '设计语言', link: 'desktop/design' },
        { en: 'Build and release', zh: '构建与发布', link: 'desktop/release' },
      ],
    },
  ],
  articles: [
    {
      en: 'Articles',
      zh: '文章',
      items: [
        { en: 'All articles', zh: '全部文章', link: 'articles/' },
        { en: 'AI Knows You. Who Gets Paid?', zh: '你的用户画像会被谁赚走', link: 'articles/user-profile' },
        { en: 'Head in the Cloud, Hands at Home', zh: '水在青天云在瓶', link: 'articles/head-in-the-cloud' },
      ],
    },
  ],
  reference: more,
}

// Pages outside a section folder that show a section's sidebar.
const shared: Record<string, Group[]> = {
  'benchmarks/': about,
  roadmap: more,
}

function sidebar(lang: 'en' | 'zh'): DefaultTheme.SidebarMulti {
  const prefix = lang === 'en' ? '/' : '/zh/'
  const build = (groups: Group[]) =>
    groups.map((group) => ({
      text: group[lang],
      items: group.items
        .filter((item) => lang === 'zh' || !item.zhOnly)
        .map((item) => ({ text: item[lang], link: prefix + item.link })),
    }))
  const result: DefaultTheme.SidebarMulti = {}
  for (const [section, groups] of Object.entries(sections)) result[prefix + section + '/'] = build(groups)
  for (const [path, groups] of Object.entries(shared)) result[prefix + path] = build(groups)
  return result
}

function nav(lang: 'en' | 'zh'): DefaultTheme.NavItem[] {
  const p = lang === 'en' ? '/' : '/zh/'
  const t = (en: string, zh: string) => (lang === 'en' ? en : zh)
  const more: DefaultTheme.NavItemWithLink[] = [
    { text: t('Roadmap', '路线图'), link: p + 'roadmap' },
    { text: t('Glossary', '术语表'), link: p + 'reference/glossary' },
    { text: t('Design decisions', '设计决策'), link: p + 'reference/decisions' },
    { text: t('History', '开发历程'), link: p + 'reference/history' },
  ]
  if (lang === 'zh') more.push({ text: '功能清单', link: p + 'reference/features' })
  return [
    { text: t('About', '了解'), link: p + 'intro/overview', activeMatch: `^${p}(intro|benchmarks)/` },
    { text: t('Desktop app', '使用'), link: p + 'app/install', activeMatch: `^${p}app/` },
    { text: t('Integrate', '接入'), link: p + 'integrate/embed', activeMatch: `^${p}integrate/` },
    {
      text: t('Internals', '原理'),
      activeMatch: `^${p}(engine|desktop)/`,
      items: [
        { text: t('Engine design', '引擎设计'), link: p + 'engine/architecture' },
        { text: t('Desktop app design', '桌面端设计'), link: p + 'desktop/architecture' },
      ],
    },
    { text: t('Articles', '文章'), link: p + 'articles/', activeMatch: `^${p}articles/` },
    { text: t('More', '更多'), activeMatch: `^${p}(reference/|roadmap)`, items: more },
  ]
}

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
  // Link previews on X, LinkedIn, Slack and the like. A page can set `image`
  // in its frontmatter to a file in docs/public; it needs a fixed URL, so it
  // lives there rather than beside the page.
  transformHead({ pageData }) {
    const fm = pageData.frontmatter
    const title = fm.title ?? pageData.title
    const description = fm.description ?? pageData.description
    const path = pageData.relativePath.replace(/(^|\/)index\.md$/, '$1').replace(/\.md$/, '')
    const site = `https://0xfakespike.github.io${base}`
    const tags: [string, Record<string, string>][] = [
      ['meta', { property: 'og:type', content: path.includes('articles/') ? 'article' : 'website' }],
      ['meta', { property: 'og:url', content: site + path }],
      ['meta', { property: 'og:title', content: title }],
      ['meta', { name: 'twitter:title', content: title }],
    ]
    if (description) {
      tags.push(['meta', { property: 'og:description', content: description }])
      tags.push(['meta', { name: 'twitter:description', content: description }])
    }
    if (fm.image) {
      const image = site + String(fm.image).replace(/^\//, '')
      tags.push(['meta', { property: 'og:image', content: image }])
      tags.push(['meta', { name: 'twitter:image', content: image }])
    }
    tags.push(['meta', { name: 'twitter:card', content: fm.image ? 'summary_large_image' : 'summary' }])
    return tags
  },
  // Sources are split by language: docs/en/ and docs/zh/, one mirror of the
  // other. English is served at the root, so docs/en/x.md becomes /x.
  // An article is a folder holding index.md and its figures, named
  // <NN>-<slug> so the folders sort by publication order. It is served as
  // /articles/<slug>, without the number and without a trailing slash, so
  // published links keep working.
  rewrites(id) {
    const article = id.match(/^(en|zh)\/articles\/(?:\d+-)?([^/]+)\/index\.md$/)
    if (article) return `${article[1] === 'en' ? '' : 'zh/'}articles/${article[2]}.md`
    return id.startsWith('en/') ? id.slice('en/'.length) : id
  },
  locales: {
    root: {
      lang: 'en',
      label: 'English',
      description:
        'A Go agent runtime for cloud providers serving massively concurrent personal agents, and the macOS app built on it.',
      themeConfig: {
        nav: nav('en'),
        sidebar: sidebar('en'),
      },
    },
    zh: {
      lang: 'zh-CN',
      label: '简体中文',
      description: '面向大规模个人 agent 服务的 Go 框架，以及基于它的 macOS 桌面端。',
      themeConfig: {
        nav: nav('zh'),
        sidebar: sidebar('zh'),
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
  },
  themeConfig: {
    logo: { light: '/logo/mark.svg', dark: '/logo/mark.svg', alt: '' },
    socialLinks: [{ icon: 'github', link: repository }],
    footer: { message: 'MIT License' },
    outline: { level: [2, 3] },
    editLink: {
      pattern: 'https://github.com/0xfakeSpike/ollupi-docs/edit/main/docs/:path',
      text: 'Edit this page',
    },
    search: {
      provider: 'local',
      options: {
        miniSearch: {
          options: { tokenize },
          searchOptions: { combineWith: 'AND', prefix: true },
        },
        locales: {
          zh: {
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
    },
  },
  markdown: { config: renderMermaidFences },
  vite: { optimizeDeps: { include: ['mermaid'] } },
})
