export default {
  title: "Ann Rast Dolls & Collectibles",
  // Absolute URLs in sitemap.xml / robots.txt / feed.xml. Set SITE_URL for preview builds.
  url: (process.env.SITE_URL || "https://annrast.com").replace(/\/$/, ""),
  statcounter: { project: 8256649, security: "83e0345a" },
  nav: [
    { text: "Dolls For Sale", url: "/dolls-for-sale/" },
    { text: "How To Buy", url: "/how-to-buy/" },
    { text: "Contact", url: "/contact/" },
    { text: "About Me", url: "/about-me/" },
  ],
};
