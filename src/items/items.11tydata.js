export default {
  layout: "item.njk",
  tags: ["item"],
  eleventyComputed: {
    permalink: (data) => `/item/${data.page.fileSlug}/`,
    description: (data) => [data.title, data.price, data.status].filter(Boolean).join(" · "),
  },
};
