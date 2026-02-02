import DefaultTheme from 'vitepress/theme'
import type { Theme } from 'vitepress'
import { theme as OpenAPITheme, useOpenapi } from 'vitepress-openapi/client'
import 'vitepress-openapi/dist/style.css'
import './custom.css'
import VideoPlayer from './components/VideoPlayer.vue'
import spec from '../../src/openapi.json'

function sameOrigin(url: string) {
  try {
    const u = new URL(url, window.location.href)
    return u.origin === window.location.origin
  } catch {
    return true
  }
}

function attachOutboundTracking() {
  if (typeof window === 'undefined') return
  const anchors = Array.from(document.querySelectorAll<HTMLAnchorElement>('a[href]'))
  anchors.forEach((a) => {
    const href = a.getAttribute('href') || ''
    if (!href || a.dataset.umamiAttached === '1') return
    const isExternal = /^https?:/i.test(href) && !sameOrigin(href)
    if (!isExternal) return
    a.dataset.umamiAttached = '1'
    a.addEventListener('click', () => {
      const w = window as any
      if (w.umami?.track) {
        w.umami.track('outbound-link', { href: a.href })
      } else if (w.umami?.trackEvent) {
        w.umami.trackEvent(a.href, 'outbound-link')
      }
    })
  })
}

function attachHeroCtaTracking() {
  if (typeof window === 'undefined') return
  const selectors = [
    '.VPHero .actions a',
    '.VPHomeHero .actions a',
    '.VPButton.link',
  ]
  const anchors = Array.from(document.querySelectorAll<HTMLAnchorElement>(selectors.join(',')))
  anchors.forEach((a) => {
    if (a.dataset.umamiEvent) return // already tagged
    const label = (a.textContent || '').trim().toLowerCase()
    let event = ''
    if (label === 'get started') event = 'cta-get-started'
    else if (label === 'api reference') event = 'cta-api-reference'
    else if (label === 'github') event = 'cta-github'
    if (!event) return
    a.dataset.umamiEvent = event
    a.dataset.umamiEventLabel = (a.textContent || '').trim()
    a.dataset.umamiEventHref = a.href
    a.dataset.umamiEventLocation = 'home-hero'
  })
}

const theme: Theme = {
  ...DefaultTheme,
  enhanceApp(ctx) {
    DefaultTheme.enhanceApp?.(ctx)
    const { app, router } = ctx
    useOpenapi({
      spec,
      config: {
        spec: {
          groupByTags: true,
          defaultTag: 'General',
        },
      },
    })
    OpenAPITheme.enhanceApp?.({ app })
    app.component('VideoPlayer', VideoPlayer)
    if (typeof window !== 'undefined') {
      // Attach initial listeners after hydration
      setTimeout(() => {
        attachOutboundTracking()
        attachHeroCtaTracking()
      }, 0)
      // Track SPA navigations and re-bind outbound tracking
      router.onAfterRouteChange = () => {
        const w = window as any
        const url = window.location.pathname + window.location.search + window.location.hash
        if (w.umami?.trackView) {
          w.umami.trackView(url, document.referrer)
        } else if (w.umami?.track) {
          w.umami.track('pageview', { url })
        }
        attachOutboundTracking()
        attachHeroCtaTracking()
      }
    }
  },
}

export default theme
