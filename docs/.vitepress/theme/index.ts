import DefaultTheme from 'vitepress/theme'
import type { Theme } from 'vitepress'
import { theme as OpenAPITheme, useOpenapi } from 'vitepress-openapi/client'
import 'vitepress-openapi/dist/style.css'
import './custom.css'
import VideoPlayer from './components/VideoPlayer.vue'
import ApiOperations from './components/ApiOperations.vue'
import spec from '../../src/openapi.json'

const MERMAID_MODULE_URL =
  'https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs'

let mermaidModulePromise: Promise<any> | null = null
let mermaidRenderScheduled = false
let mermaidObserverAttached = false

function currentMermaidTheme() {
  if (typeof document === 'undefined') return 'default'
  return document.documentElement.classList.contains('dark') ? 'dark' : 'default'
}

async function getMermaid() {
  if (!mermaidModulePromise) {
    mermaidModulePromise = import(/* @vite-ignore */ MERMAID_MODULE_URL).then(
      (mod: any) => mod.default ?? mod
    )
  }
  return mermaidModulePromise
}

async function renderMermaidDiagrams() {
  if (typeof window === 'undefined') return
  const nodes = Array.from(
    document.querySelectorAll<HTMLElement>('pre.mermaid')
  )
  if (!nodes.length) return

  const mermaid = await getMermaid()
  mermaid.initialize({
    startOnLoad: false,
    securityLevel: 'strict',
    theme: currentMermaidTheme(),
  })

  for (const node of nodes) {
    node.removeAttribute('data-processed')
  }

  await mermaid.run({ nodes })
}

function scheduleMermaidRender() {
  if (typeof window === 'undefined') return
  if (mermaidRenderScheduled) return
  mermaidRenderScheduled = true
  window.requestAnimationFrame(() => {
    mermaidRenderScheduled = false
    renderMermaidDiagrams().catch((error) => {
      console.warn('Mermaid render failed:', error)
    })
  })
}

function attachMermaidThemeObserver() {
  if (typeof window === 'undefined') return
  if (mermaidObserverAttached) return
  mermaidObserverAttached = true
  let previous = currentMermaidTheme()
  const observer = new MutationObserver(() => {
    const next = currentMermaidTheme()
    if (next !== previous) {
      previous = next
      scheduleMermaidRender()
    }
  })
  observer.observe(document.documentElement, {
    attributes: true,
    attributeFilter: ['class'],
  })
}

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
    app.component('ApiOperations', ApiOperations)
    if (typeof window !== 'undefined') {
      // Attach initial listeners after hydration
      setTimeout(() => {
        attachOutboundTracking()
        attachHeroCtaTracking()
        attachMermaidThemeObserver()
        scheduleMermaidRender()
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
        scheduleMermaidRender()
      }
    }
  },
}

export default theme
