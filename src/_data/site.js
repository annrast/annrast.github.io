import settings from "./settings.json" with { type: "json" };
export default {
  ...settings,
  title: `${settings.siteTitle} ${settings.tagline}`,
  // Absolute URLs in sitemap.xml / robots.txt. Set SITE_URL for preview builds.
  url: (process.env.SITE_URL || "https://annrast.com").replace(/\/$/, ""),
};
