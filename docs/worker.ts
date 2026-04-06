type Env = {
  ASSETS: Fetcher;
};

const CANONICAL_REDIRECT_STATUS = 308;
const CACHE_REVALIDATE_HEADER = "public, max-age=0, must-revalidate";
const CANONICAL_HOST = "anibridge-docs.zacklack.de";
const LEGACY_WWW_HOST = "www.anibridge-docs.zacklack.de";
const HTML_CONTENT_TYPE = "text/html";

function getCanonicalPath(pathname: string): string | null {
  if (pathname === "/index.html") return "/";
  if (pathname.endsWith("/index.html")) {
    const withoutIndex = pathname.slice(0, -"/index.html".length);
    return withoutIndex || "/";
  }
  if (pathname.endsWith(".html")) {
    const withoutExt = pathname.slice(0, -".html".length);
    return withoutExt || "/";
  }
  if (pathname.length > 1 && pathname.endsWith("/")) {
    return pathname.replace(/\/+$/, "");
  }
  return null;
}

function getCanonicalUrl(requestUrl: URL): URL {
  const canonicalUrl = new URL(requestUrl.toString());
  canonicalUrl.protocol = "https:";
  canonicalUrl.hostname = CANONICAL_HOST;
  canonicalUrl.port = "";
  return canonicalUrl;
}

function applySeoHeaders(response: Response, requestUrl: URL): Response {
  const headers = new Headers(response.headers);
  const canonicalUrl = getCanonicalUrl(requestUrl);

  const contentType = headers.get("content-type") ?? "";
  headers.set("Strict-Transport-Security", "max-age=31536000; includeSubDomains");
  headers.set("Referrer-Policy", "strict-origin-when-cross-origin");
  if (response.status >= 400) {
    headers.set("X-Robots-Tag", "noindex, nofollow");
  } else if (contentType.startsWith(HTML_CONTENT_TYPE)) {
    headers.set("X-Robots-Tag", "index, follow");
    headers.set("Link", `<${canonicalUrl.origin}/sitemap.xml>; rel="sitemap"`);
    headers.set("Cache-Control", CACHE_REVALIDATE_HEADER);
  } else {
    headers.set("X-Robots-Tag", "index, follow");
  }

  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers,
  });
}

export default {
  async fetch(request: Request, env: Env, _ctx: ExecutionContext): Promise<Response> {
    const url = new URL(request.url);
    const needsCanonicalHostRedirect =
      url.protocol !== "https:" ||
      url.hostname === LEGACY_WWW_HOST ||
      url.hostname !== CANONICAL_HOST;
    const canonicalPath = getCanonicalPath(url.pathname);

    if (needsCanonicalHostRedirect || (canonicalPath && canonicalPath !== url.pathname)) {
      const canonicalUrl = getCanonicalUrl(url);
      canonicalUrl.pathname = canonicalPath ?? url.pathname;
      canonicalUrl.search = url.search;
      return Response.redirect(canonicalUrl.toString(), CANONICAL_REDIRECT_STATUS);
    }

    // Delegate requests to Wrangler's static-asset server and normalize SEO headers.
    const response = await env.ASSETS.fetch(request);
    return applySeoHeaders(response, url);
  },
};
