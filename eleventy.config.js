export default function (eleventyConfig) {
  eleventyConfig.addPassthroughCopy("src/img");
  eleventyConfig.addPassthroughCopy("src/css");
  // Content files are plain HTML extracted from iWeb: don't run a template language over them.
  eleventyConfig.setTemplateFormats(["html", "njk"]);
  // _redirects: paths may not contain spaces; encode anything outside the safe set.
  const enc = (s, keep) => s.replace(/[^A-Za-z0-9\-._~\/!$'()*+,;=:@&%]/g, (c) => encodeURIComponent(c)).replace(/&/g, keep ? "&" : "%26");
  eleventyConfig.addFilter("redirectPath", (p) => enc(p, true));
  eleventyConfig.addFilter("redirectPathEncoded", (p) => enc(p, false));
  return {
    dir: { input: "src", includes: "_includes", data: "_data", output: "_site" },
    htmlTemplateEngine: false,
    markdownTemplateEngine: false,
  };
}
