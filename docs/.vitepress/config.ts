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
const sections: Record<string, Group[]> = {
  intro: [
    {
      en: 'About Ollupi',
      zh: '了解 Ollupi',
      items: [
        { en: 'Why Ollupi', zh: '为什么做 Ollupi', link: 'intro/why' },
        { en: 'Overview', zh: '项目概览', link: 'intro/overview' },
        { en: 'Core concepts', zh: '核心概念', link: 'intro/concepts' },
      ],
    },
  ],
  app: [
    {
      en: 'Desktop app guide',
      zh: '桌面端使用手册',
      items: [
        { en: 'Install and get started', zh: '安装与上手', link: 'app/install' },
        { en: 'Workspaces and sessions', zh: '工作区与会话', link: 'app/sessions' },
        { en: 'Approvals and permissions', zh: '审批与权限', link: 'app/permissions' },
        { en: 'Browser, files, terminal', zh: '浏览器、文件、终端等面板', link: 'app/panels' },
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
        { en: 'Overview', zh: '总览', link: 'integrate/protocol' },
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
        { en: 'Type index', zh: '类型索引', link: 'integrate/protocol-types' },
        { en: 'Writing a client', zh: '写一个客户端', link: 'integrate/client' },
      ],
    },
  ],
  engine: [
    {
      en: 'Core',
      zh: '内核',
      items: [
        { en: 'Architecture', zh: '架构总览', link: 'engine/architecture' },
        { en: 'Execution model', zh: '执行模型', link: 'engine/execution' },
        { en: 'Persistence and recovery', zh: '持久化与崩溃恢复', link: 'engine/persistence' },
        { en: 'Shards and leases', zh: '分片与租约', link: 'engine/sharding' },
        { en: 'Execution traces', zh: '执行轨迹', link: 'engine/traces' },
      ],
    },
    {
      en: 'Model and tools',
      zh: '模型与工具',
      items: [
        { en: 'Context management', zh: '上下文管理', link: 'engine/context' },
        { en: 'Models', zh: '模型接入', link: 'engine/models' },
        { en: 'Tools', zh: '工具', link: 'engine/tools' },
        { en: 'Workspaces', zh: '工作区', link: 'engine/workspace' },
        { en: 'Skills and MCP', zh: '技能与 MCP', link: 'engine/skills-mcp' },
        { en: 'Memory', zh: '记忆', link: 'engine/memory' },
        { en: 'Scheduled tasks', zh: '定时任务', link: 'engine/cron' },
        { en: 'Search', zh: '搜索', link: 'engine/search' },
      ],
    },
    {
      en: 'Safety',
      zh: '安全',
      items: [
        { en: 'Security overview', zh: '安全总览', link: 'engine/security' },
        { en: 'Permissions and approvals', zh: '权限与审批', link: 'engine/permissions' },
        { en: 'Sandbox', zh: '沙箱', link: 'engine/sandbox' },
        { en: 'Redaction', zh: '脱敏', link: 'engine/redaction' },
      ],
    },
  ],
  desktop: [
    {
      en: 'Desktop app design',
      zh: '桌面端设计',
      items: [
        { en: 'Architecture', zh: '架构总览', link: 'desktop/architecture' },
        { en: 'Sidecar', zh: 'Sidecar', link: 'desktop/sidecar' },
        { en: 'Main process', zh: '主进程', link: 'desktop/main-process' },
        { en: 'Renderer', zh: '界面', link: 'desktop/renderer' },
        { en: 'Configuration internals', zh: '配置的实现', link: 'desktop/config' },
        { en: 'Side panels', zh: '侧边面板的实现', link: 'desktop/side-panels' },
        { en: 'Built-in browser', zh: '内置浏览器的实现', link: 'desktop/browser' },
        { en: 'Feishu bot', zh: '飞书机器人的实现', link: 'desktop/feishu-bot' },
        { en: 'Design language', zh: '设计语言', link: 'desktop/design' },
        { en: 'Build and release', zh: '构建与发布', link: 'desktop/release' },
      ],
    },
  ],
  benchmarks: [
    {
      en: 'Benchmarks',
      zh: '性能基准',
      items: [
        { en: 'Results', zh: '结果', link: 'benchmarks/' },
        { en: 'What we measure next', zh: '接下来要测的', link: 'benchmarks/plan' },
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
  reference: [
    {
      en: 'Reference',
      zh: '参考',
      items: [
        { en: 'Glossary', zh: '术语表', link: 'reference/glossary' },
        { en: 'Design decisions', zh: '设计决策', link: 'reference/decisions' },
        { en: 'History', zh: '开发历程', link: 'reference/history' },
        { en: 'Feature list', zh: '功能清单', link: 'reference/features', zhOnly: true },
        { en: 'Desktop backlog', zh: '桌面端待办', link: 'reference/backlog', zhOnly: true },
      ],
    },
  ],
}

function sidebar(lang: 'en' | 'zh'): DefaultTheme.SidebarMulti {
  const prefix = lang === 'en' ? '/' : '/zh/'
  const result: DefaultTheme.SidebarMulti = {}
  for (const [section, groups] of Object.entries(sections)) {
    result[prefix + section + '/'] = groups.map((group) => ({
      text: group[lang],
      items: group.items
        .filter((item) => lang === 'zh' || !item.zhOnly)
        .map((item) => ({ text: item[lang], link: prefix + item.link })),
    }))
  }
  return result
}

function nav(lang: 'en' | 'zh'): DefaultTheme.NavItem[] {
  const p = lang === 'en' ? '/' : '/zh/'
  const t = (en: string, zh: string) => (lang === 'en' ? en : zh)
  return [
    { text: t('About', '了解'), link: p + 'intro/why', activeMatch: `^${p}intro/` },
    {
      text: t('Docs', '文档'),
      activeMatch: `^${p}(app|integrate|engine|desktop)/`,
      items: [
        { text: t('Desktop app guide', '桌面端使用手册'), link: p + 'app/install' },
        { text: t('Integration guide', '引擎集成指南'), link: p + 'integrate/embed' },
        { text: t('Engine design', '引擎设计'), link: p + 'engine/architecture' },
        { text: t('Desktop app design', '桌面端设计'), link: p + 'desktop/architecture' },
      ],
    },
    { text: t('Benchmarks', '基准'), link: p + 'benchmarks/', activeMatch: `^${p}benchmarks/` },
    { text: t('Articles', '文章'), link: p + 'articles/', activeMatch: `^${p}articles/` },
    { text: t('Roadmap', '路线图'), link: p + 'roadmap', activeMatch: `^${p}roadmap` },
    { text: t('Reference', '参考'), link: p + 'reference/glossary', activeMatch: `^${p}reference/` },
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
