import DefaultTheme from 'vitepress/theme'
import './custom.css'
import type { Theme } from 'vitepress'
import VideoPlayer from './components/VideoPlayer.vue'

const theme: Theme = {
  ...DefaultTheme,
  enhanceApp({ app }) {
    DefaultTheme.enhanceApp?.({ app })
    app.component('VideoPlayer', VideoPlayer)
  },
}

export default theme
