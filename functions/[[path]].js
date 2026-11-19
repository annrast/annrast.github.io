// Legacy-URL fallback for old iWeb links that arrive percent-encoded ("%26" instead of "&").
// Cloudflare Pages matches _redirects against the raw request path, so "%26" forms can't be
// expressed there. _routes.json sends ONLY those forms here; everything else is static and
// handled by _redirects. Same map as _redirects (src/_data/legacy.json).
import legacy from "../src/_data/legacy.json";

const MAP = new Map(legacy.map((r) => [r.old, r.new]));
const FOLDER = "/Ann_Rast_Dolls_&_Collectibles";
MAP.set(FOLDER, "/");
MAP.set(FOLDER + "/", "/");
MAP.set(FOLDER + "/index.html", "/");
MAP.set(FOLDER + "/feed.xml", "/feed.xml");

export async function onRequest(context) {
  const url = new URL(context.request.url);
  let path;
  try { path = decodeURIComponent(url.pathname); } catch { path = url.pathname; }
  const to = MAP.get(path);
  if (to) return Response.redirect(new URL(to, url.origin).toString(), 301);
  return context.next();
}
