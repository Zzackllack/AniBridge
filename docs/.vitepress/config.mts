import { defineConfig, type HeadConfig } from "vitepress";
import { useSidebar } from "vitepress-openapi";
import spec from "../src/openapi.json";

// https://vitepress.dev/reference/site-config
const siteUrl = "https://anibridge-docs.zacklack.de";
const apiSidebar = useSidebar({
  spec,
  linkPrefix: "/api/operations/",
  defaultTag: "General",
});
const apiOperationGroups = apiSidebar
  .generateSidebarGroups({
    linkPrefix: "/api/operations/",
  })
  .map((group) => ({
    ...group,
    collapsed: false,
  }));

export default defineConfig({
  head: [
    [
      "link",
      {
        rel: "icon",
        type: "image/png",
        href: "/favicon-96x96.png",
        sizes: "96x96",
      },
    ],
    ["link", { rel: "icon", type: "image/svg+xml", href: "/favicon.svg" }],
    ["link", { rel: "icon", type: "image/x-icon", href: "/favicon.ico" }],
    ["link", { rel: "shortcut icon", href: "/favicon.ico" }],
    // Explicit app/site names help Google use subdomain branding + favicon
    ["meta", { name: "application-name", content: "AniBridge Docs" }],
    ["meta", { name: "apple-mobile-web-app-title", content: "AniBridge Docs" }],
    [
      "link",
      {
        rel: "apple-touch-icon",
        sizes: "180x180",
        href: "/apple-touch-icon.png",
      },
    ],
    ["link", { rel: "manifest", href: "/site.webmanifest" }],
    [
      "link",
      {
        rel: "preconnect",
        href: "https://umami-analytics.zacklack.de",
        crossorigin: "",
      },
    ],
    [
      "script",
      {
        defer: "",
        src: "https://umami-analytics.zacklack.de/script.js",
        "data-website-id": "9694e5ab-5398-43e4-9a46-37d135bf7536",
      },
    ],
    // Use 6‑digit hex for broader UA compatibility
    ["meta", { name: "theme-color", content: "#092e3f" }],
    [
      "meta",
      {
        name: "robots",
        content:
          "index, follow, max-snippet:-1, max-image-preview:large, max-video-preview:-1",
      },
    ],
    ["meta", { name: "twitter:card", content: "summary_large_image" }],
    ["meta", { name: "twitter:site", content: "@zzackllack" }],
    ["meta", { property: "og:type", content: "website" }],
    ["meta", { property: "og:site_name", content: "AniBridge Docs" }],
    ["meta", { property: "og:locale", content: "en_US" }],
    ["meta", { property: "og:image", content: `${siteUrl}/logo.png` }],
    // Structured data: signal this subdomain as its own WebSite entity
    [
      "script",
      {
        type: "application/ld+json",
      },
      JSON.stringify({
        "@context": "https://schema.org",
        "@type": "WebSite",
        name: "AniBridge Docs",
        alternateName: "AniBridge Documentation",
        url: `${siteUrl}/`,
        inLanguage: "en",
      }),
    ],
  ],
  srcDir: "src",

  title: "AniBridge Documentation",
  description:
    "AniBridge: FastAPI bridge exposing Torznab feed and qBittorrent-compatible API to automate anime downloads via Prowlarr/Sonarr.",
  titleTemplate: ":title • AniBridge Docs",
  lastUpdated: true,
  ignoreDeadLinks: true,
  cleanUrls: true,
  sitemap: {
    hostname: siteUrl,
  },
  vite: {
    // Needed for ESM-only deps that may be used in VitePress config helpers.
    ssr: {
      noExternal: ["vitepress-openapi"],
    },
    optimizeDeps: {
      include: ["vitepress-openapi/client"],
    },
  },
  transformHead: ({ page, pageData, siteConfig, title, description }) => {
    const normalizedPage = page.replace(/^\//, "");
    const pagePath = normalizedPage
      .replace(/(^|\/)index\.md$/, "$1")
      .replace(/\.md$/, "")
      .replace(/\/+$/, "");
    const pathname = pagePath ? `/${pagePath}` : "/";
    const url = new URL(pathname, siteUrl).toString();
    const pageTitle = title || siteConfig.site.title || "AniBridge Docs";
    const pageDescription =
      description || siteConfig.site.description || "AniBridge documentation";
    const lastUpdated = pageData.lastUpdated;
    // Build breadcrumb list from path parts
    const path = url.replace(siteUrl, "");
    const parts = path.split("/").filter(Boolean);
    const breadcrumbItems = parts.map((p, i) => ({
      "@type": "ListItem",
      position: i + 1,
      name: p,
      item: `${siteUrl}/${parts.slice(0, i + 1).join("/")}`,
    }));
    const tags: HeadConfig[] = [
      ["link", { rel: "canonical", href: url }],
      ["link", { rel: "alternate", hreflang: "en", href: url }],
      ["meta", { property: "og:url", content: url }],
      ["meta", { property: "og:title", content: pageTitle }],
      ["meta", { property: "og:description", content: pageDescription }],
      ["meta", { name: "twitter:title", content: pageTitle }],
      ["meta", { name: "twitter:description", content: pageDescription }],
      // Page-level structured data: TechArticle + Breadcrumbs
      [
        "script",
        { type: "application/ld+json" },
        JSON.stringify({
          "@context": "https://schema.org",
          "@type": "TechArticle",
          headline: pageData.title || siteConfig.site.title || "AniBridge Docs",
          description: pageDescription,
          inLanguage: "en",
          url,
          dateModified: lastUpdated
            ? new Date(lastUpdated).toISOString()
            : undefined,
          mainEntityOfPage: url,
          publisher: {
            "@type": "Organization",
            name: "AniBridge",
            url: siteUrl,
            logo: {
              "@type": "ImageObject",
              url: `${siteUrl}/favicon.svg`,
            },
          },
        }),
      ],
      [
        "script",
        { type: "application/ld+json" },
        JSON.stringify({
          "@context": "https://schema.org",
          "@type": "BreadcrumbList",
          itemListElement: breadcrumbItems.length
            ? breadcrumbItems
            : [
                {
                  "@type": "ListItem",
                  position: 1,
                  name: "home",
                  item: `${siteUrl}/`,
                },
              ],
        }),
      ],
    ];
    return tags;
  },
  transformPageData: (pageData) => {
    if (!pageData.relativePath.startsWith("api/operations/")) return;
    const params = pageData.params as
      | { pageTitle?: string; pageDescription?: string }
      | undefined;
    if (!params) return;
    const update: Partial<typeof pageData> = {};
    if (params.pageTitle) update.title = params.pageTitle;
    if (params.pageDescription) update.description = params.pageDescription;
    return update;
  },
  themeConfig: {
    // https://vitepress.dev/reference/default-theme-config
    // Use a lightweight vector for header logo to improve LCP
    logo: "/favicon.svg",
    siteTitle: "AniBridge",
    nav: [
      { text: "Guide", link: "/guide/overview" },
      { text: "API", link: "/api/overview" },
      { text: "Integrations", link: "/integrations/prowlarr" },
      { text: "Developer", link: "/developer/running" },
      { text: "Legal", link: "/legal" },
      {
        text: "Changelog",
        link: "https://github.com/zzackllack/AniBridge/releases",
      },
    ],
    sidebar: {
      "/guide/": [
        {
          text: "Getting Started",
          items: [
            { text: "Overview", link: "/guide/overview" },
            { text: "Quickstart", link: "/guide/quickstart" },
            { text: "Configuration", link: "/guide/configuration" },
            { text: "Networking & Proxies", link: "/guide/networking" },
            { text: "Running", link: "/guide/running" },
            { text: "Troubleshooting", link: "/guide/troubleshooting" },
            { text: "FAQ", link: "/guide/faq" },
          ],
        },
      ],
      "/api/": [
        {
          text: "API Reference",
          items: [
            { text: "Overview", link: "/api/overview" },
            { text: "Torznab", link: "/api/torznab" },
            { text: "qBittorrent Shim", link: "/api/qbittorrent" },
            { text: "Jobs & Events", link: "/api/jobs" },
            { text: "STRM Proxy", link: "/api/strm-proxy" },
            { text: "Environment", link: "/api/environment" },
            { text: "Data Model", link: "/api/data-model" },
          ],
        },
        {
          text: "Operations",
          items: apiOperationGroups,
          collapsed: false,
        },
      ],
      "/integrations/": [
        {
          text: "Integrations",
          items: [
            { text: "Prowlarr", link: "/integrations/prowlarr" },
            { text: "Sonarr", link: "/integrations/sonarr" },
            { text: "Radarr", link: "/integrations/radarr" },
          ],
        },
      ],
      "/developer/": [
        {
          text: "Developer Guide",
          items: [
            { text: "Running Locally", link: "/developer/running" },
            { text: "Testing", link: "/developer/testing" },
            { text: "Contributing", link: "/developer/contributing" },
            { text: "Logging", link: "/developer/logging" },
            { text: "Testing with cURL", link: "/developer/testing-with-curl" },
          ],
        },
      ],
    },
    search: { provider: "local" },
    socialLinks: [
      { icon: "github", link: "https://github.com/zzackllack/AniBridge" },
    ],
    editLink: {
      pattern:
        "https://github.com/zzackllack/AniBridge/edit/main/docs/src/:path",
      text: "Edit this page on GitHub",
    },
    lastUpdated: { text: "Updated at" },
    footer: {
      message: "Released under the BSD 3 Clause License.",
      copyright: "Copyright © 2025–present AniBridge contributors",
    },
  },
});
