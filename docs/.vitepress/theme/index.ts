import DefaultTheme from 'vitepress/theme'
import type { Theme } from 'vitepress'
import { defineAsyncComponent, type App, type Component } from 'vue'
import './custom.css'
import VideoPlayer from './components/VideoPlayer.vue'

const MERMAID_MODULE_URL =
  'https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs'

let mermaidModulePromise: Promise<any> | null = null
let mermaidRenderScheduled = false
let mermaidObserverAttached = false
let lastRoutePathKey = ''
let openApiClientPromise: Promise<void> | null = null

function isApiRoute(path: string) {
  return path === '/api' || path.startsWith('/api/')
}

async function ensureOpenApiClient(app: App) {
  if (!openApiClientPromise) {
    openApiClientPromise = (async () => {
      const [{ default: spec }, openApiClient] = await Promise.all([
        import('../../src/openapi.json'),
        import('vitepress-openapi/client'),
        import('vitepress-openapi/dist/style.css'),
      ])

      openApiClient.useOpenapi({
        spec,
        config: {
          spec: {
            groupByTags: true,
            defaultTag: 'General',
          },
        },
      })

      await openApiClient.theme.enhanceApp?.({ app })
    })()
  }

  return openApiClientPromise
}

function createOpenApiAsyncComponent(
  app: App,
  loader: () => Promise<Component>,
) {
  return defineAsyncComponent(async () => {
    await ensureOpenApiClient(app)
    return loader()
  })
}

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

  const renderNodes: HTMLElement[] = []
  for (const node of nodes) {
    const cachedSource = node.dataset.mermaidSource?.trim()
    const source = cachedSource || (node.textContent || '').trim()
    if (!source) continue

    // Preserve the original source once; Mermaid mutates node contents to SVG.
    if (!cachedSource) {
      node.dataset.mermaidSource = source
    }

    // Always restore source text before rendering to avoid parsing previous SVG.
    node.textContent = node.dataset.mermaidSource || source
    node.removeAttribute('data-processed')
    renderNodes.push(node)
  }
  if (!renderNodes.length) return

  await mermaid.run({ nodes: renderNodes })
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

function ensureMainLandmark() {
  if (typeof document === 'undefined') return
  const mainCandidate = document.querySelector<HTMLElement>(
    '.VPContent, main, [role="main"]'
  )
  if (!mainCandidate) return
  if (mainCandidate.tagName.toLowerCase() !== 'main' && !mainCandidate.hasAttribute('role')) {
    mainCandidate.setAttribute('role', 'main')
  }
  if (!mainCandidate.id) {
    mainCandidate.id = 'main-content'
  }
}

function normalizeTitles() {
  if (typeof document === 'undefined') return

  const anchors = Array.from(document.querySelectorAll<HTMLAnchorElement>('a[href]'))
  anchors.forEach((anchor) => {
    if (anchor.getAttribute('title')) return
    const label =
      anchor.textContent?.trim() ||
      anchor.getAttribute('aria-label') ||
      anchor.getAttribute('href') ||
      ''
    if (label) anchor.setAttribute('title', label)
  })

  const images = Array.from(document.querySelectorAll<HTMLImageElement>('img'))
  images.forEach((img) => {
    if (img.getAttribute('title')) return
    const alt = img.getAttribute('alt')?.trim()
    if (alt) img.setAttribute('title', alt)
  })
}

const theme: Theme = {
  ...DefaultTheme,
  async enhanceApp(ctx) {
    DefaultTheme.enhanceApp?.(ctx)
    const { app, router } = ctx
    if (typeof window === 'undefined') {
      const [{ default: ApiOperations }, { default: ApiOperationPage }] =
        await Promise.all([
          import('./components/ApiOperations.vue'),
          import('./components/ApiOperationPage.vue'),
        ])

      app.component('VideoPlayer', VideoPlayer)
      app.component('ApiOperations', ApiOperations)
      app.component('ApiOperationPage', ApiOperationPage)
      return
    }
    app.component('VideoPlayer', VideoPlayer)
    app.component(
      'ApiOperations',
      createOpenApiAsyncComponent(
        app,
        async () => (await import('./components/ApiOperations.vue')).default,
      ),
    )
    app.component(
      'ApiOperationPage',
      createOpenApiAsyncComponent(
        app,
        async () => (await import('./components/ApiOperationPage.vue')).default,
      ),
    )
    if (typeof window !== 'undefined') {
      if (isApiRoute(window.location.pathname)) {
        await ensureOpenApiClient(app)
      }
      lastRoutePathKey = window.location.pathname + window.location.search
      // Attach initial listeners after hydration
      setTimeout(() => {
        ensureMainLandmark()
        normalizeTitles()
        attachOutboundTracking()
        attachHeroCtaTracking()
        attachMermaidThemeObserver()
        scheduleMermaidRender()
      }, 0)
      // Track SPA navigations and re-bind outbound tracking
      router.onAfterRouteChange = () => {
        const w = window as any
        const routePathKey = window.location.pathname + window.location.search
        const isHashOnlyNavigation = routePathKey === lastRoutePathKey
        lastRoutePathKey = routePathKey
        const url = routePathKey + window.location.hash
        if (isApiRoute(window.location.pathname)) {
          void ensureOpenApiClient(app)
        }
        if (w.umami?.trackView) {
          w.umami.trackView(url, document.referrer)
        } else if (w.umami?.track) {
          w.umami.track('pageview', { url })
        }
        ensureMainLandmark()
        normalizeTitles()
        attachOutboundTracking()
        attachHeroCtaTracking()
        if (!isHashOnlyNavigation) {
          scheduleMermaidRender()
        }
      }
    }
  },
}

export default theme
