import markdownIt from "markdown-it";
import fs from "node:fs";

// width="" height="" for local images so pages don't jump while photos load (WebP/PNG/JPEG headers).
const dimCache = new Map();
function imageDims(src) {
  if (dimCache.has(src)) return dimCache.get(src);
  let d = null;
  try {
    const b = fs.readFileSync("src" + decodeURI(src));
    if (b.toString("ascii", 0, 4) === "RIFF" && b.toString("ascii", 8, 12) === "WEBP") {
      const c = b.toString("ascii", 12, 16);
      if (c === "VP8 ") d = [b.readUInt16LE(26) & 0x3fff, b.readUInt16LE(28) & 0x3fff];
      else if (c === "VP8L") { const n = b.readUInt32LE(21); d = [(n & 0x3fff) + 1, ((n >> 14) & 0x3fff) + 1]; }
      else if (c === "VP8X") d = [b.readUIntLE(24, 3) + 1, b.readUIntLE(27, 3) + 1];
    } else if (b.readUInt32BE(0) === 0x89504e47) d = [b.readUInt32BE(16), b.readUInt32BE(20)];
    else if (b[0] === 0xff && b[1] === 0xd8) {
      for (let i = 2; i < b.length; ) {
        const m = b[i + 1], len = b.readUInt16BE(i + 2);
        if (m >= 0xc0 && m <= 0xcf && ![0xc4, 0xc8, 0xcc].includes(m)) { d = [b.readUInt16BE(i + 7), b.readUInt16BE(i + 5)]; break; }
        i += 2 + len;
      }
    }
  } catch { d = null; }
  dimCache.set(src, d);
  return d;
}

export default function (eleventyConfig) {
  eleventyConfig.addPassthroughCopy("src/img");
  eleventyConfig.addPassthroughCopy("src/css");
  // Travel pages are plain HTML extracted from iWeb; item descriptions are Markdown, one line per line.
  eleventyConfig.setTemplateFormats(["html", "njk", "md"]);
  eleventyConfig.setLibrary("md", markdownIt({ html: true, breaks: true, linkify: true }));

  const STATUS_ORDER = { Available: 0, "On Hold": 1, Sold: 2 };
  eleventyConfig.addFilter("inCategory", (items, key) => (items || []).filter((i) => i.data.category === key));
  eleventyConfig.addFilter("notSold", (items) => items.filter((i) => i.data.status !== "Sold"));
  eleventyConfig.addFilter("onlySold", (items) => items.filter((i) => i.data.status === "Sold"));
  eleventyConfig.addFilter("sortItems", (items) =>
    [...items].sort((a, b) => (STATUS_ORDER[a.data.status] ?? 0) - (STATUS_ORDER[b.data.status] ?? 0) || a.data.title.localeCompare(b.data.title)));
  // Category cover: first photo of an unsold item, else of any item.
  eleventyConfig.addFilter("coverPhoto", (items) => {
    const withPhoto = items.filter((i) => i.data.photos && i.data.photos.length);
    const pick = withPhoto.find((i) => i.data.status !== "Sold") || withPhoto[0];
    return pick ? pick.data.photos[0] : null;
  });
  eleventyConfig.addFilter("findCat", (cats, key) => cats.find((c) => c.key === key) || { key: "", title: "For Sale" });
  eleventyConfig.addFilter("dims", (src) => { const d = imageDims(src); return d ? `width="${d[0]}" height="${d[1]}"` : ""; });
  eleventyConfig.addFilter("slugStatus", (s) => String(s || "Available").toLowerCase().replace(/\s+/g, "-"));

  // _redirects: paths may not contain spaces; encode anything outside the safe set.
  const enc = (s) => s.replace(/[^A-Za-z0-9\-._~\/!$'()*+,;=:@&%]/g, (c) => encodeURIComponent(c));
  eleventyConfig.addFilter("redirectPath", (p) => enc(p));
  return {
    dir: { input: "src", includes: "_includes", data: "_data", output: "_site" },
    htmlTemplateEngine: false,
    markdownTemplateEngine: false,
  };
}
