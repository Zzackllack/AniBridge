import { defineConfig } from "vitepress";

// https://vitepress.dev/reference/site-config
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
    [
      "link",
      {
        rel: "apple-touch-icon",
        sizes: "180x180",
        href: "/apple-touch-icon.png",
      },
    ],
    ["link", { rel: "manifest", href: "/site.webmanifest" }],
  ],
  srcDir: "src",

  title: "AniBridge Documentation",
  description:
    "AniBridge: FastAPI bridge exposing Torznab feed and qBittorrent-compatible API to automate anime downloads via Prowlarr/Sonarr.",
  lastUpdated: true,
  ignoreDeadLinks: true,
  themeConfig: {
    // https://vitepress.dev/reference/default-theme-config
    logo: "/logo.png",
    siteTitle: "AniBridge",
    nav: [
      { text: "Guide", link: "/guide/overview" },
      { text: "API", link: "/api/endpoints" },
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
            { text: "Endpoints", link: "/api/endpoints" },
            { text: "Torznab", link: "/api/torznab" },
            { text: "qBittorrent Shim", link: "/api/qbittorrent" },
            { text: "Jobs & Events", link: "/api/jobs" },
            { text: "Environment", link: "/api/environment" },
            { text: "Data Model", link: "/api/data-model" },
          ],
        },
      ],
      "/integrations/": [
        {
          text: "Integrations",
          items: [
            { text: "Prowlarr", link: "/integrations/prowlarr" },
            { text: "Sonarr", link: "/integrations/sonarr" },
            { text: "Docker Compose", link: "/integrations/docker" },
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
          ],
        },
      ],
    },
    search: { provider: "local" },
    socialLinks: [
      { icon: "github", link: "https://github.com/zzackllack/AniBridge" },
    ],
    editLink: {
      pattern: "https://github.com/zzackllack/AniBridge/edit/main/docs/:path",
      text: "Edit this page on GitHub",
    },
    lastUpdated: { text: "Updated at" },
    footer: {
      message: "Released under the BSD 3 Clause License.",
      copyright: "Copyright © 2025–present AniBridge contributors",
    },
  },
});
