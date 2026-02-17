type Env = {
  ASSETS: Fetcher;
};

const CANONICAL_REDIRECT_STATUS = 308;
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

function applySeoHeaders(response: Response, requestUrl: URL): Response {
  const headers = new Headers(response.headers);

  headers.set("Link", `<${requestUrl.origin}/sitemap.xml>; rel="sitemap"`);

  const contentType = headers.get("content-type") ?? "";
  if (response.status >= 400) {
    headers.set("X-Robots-Tag", "noindex, nofollow");
  } else if (contentType.startsWith(HTML_CONTENT_TYPE)) {
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
    const canonicalPath = getCanonicalPath(url.pathname);

    if (canonicalPath && canonicalPath !== url.pathname) {
      url.pathname = canonicalPath;
      return Response.redirect(url.toString(), CANONICAL_REDIRECT_STATUS);
    }

    // Delegate requests to Wrangler's static-asset server and normalize SEO headers.
    const response = await env.ASSETS.fetch(request);
    return applySeoHeaders(response, url);
  },
};
