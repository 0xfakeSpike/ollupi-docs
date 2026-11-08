import { h } from 'vue'
import DefaultTheme from 'vitepress/theme'
import type { Theme } from 'vitepress'
import EngineVersion from './EngineVersion.vue'
import Landing from './Landing.vue'
import MermaidDiagram from './MermaidDiagram.vue'
import './style.css'

export default {
  extends: DefaultTheme,
  Layout: () => h(DefaultTheme.Layout, null, { 'doc-before': () => h(EngineVersion) }),
  enhanceApp({ app }) {
    app.component('Landing', Landing)
    app.component('MermaidDiagram', MermaidDiagram)
  },
} satisfies Theme
