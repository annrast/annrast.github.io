# Ann Rast Dolls & Collectibles — redesign prototype (branch `redesign-prototype`)

Eleventy 3 site. Everything for sale is one Markdown file per item in `src/items/`, edited through
[Pages CMS](https://pagescms.org) (config: `.pages.yml`). Preview: https://redesign.annrast.pages.dev

## Structure
- `/` — welcome text + category tiles (`src/index.njk`)
- `/for-sale/<category>/` — item cards; sold items collapsed at the bottom (`src/category.njk`, `src/_data/categories.json`)
- `/item/<slug>/` — photos, price, status, description, "Ask about this item" mailto (`src/_includes/item.njk`)
- `/about/` — About, Contact, How to buy (`src/about.md`)
- `/my-travels/…` — Ann's travel pages (kept as extracted from iWeb; noindex, out of sitemap, footer link only)
- `/edit/` — plain-language editing help (noindex)
- `src/_data/settings.json` — site name, welcome text, inquiry email, phone, show-sold toggle
- `_redirects` + `functions/[[path]].js` — every old iWeb URL → its new page (`src/_data/legacy.json`)

## Item fields
`title`, `category` (key from categories.json), `price` (free text), `status` (Available / On Hold / Sold),
`photos` (list, first = thumbnail), body = description (one line per line), `todo` (review note, not shown), `oldPage`.

## Regenerating from the old iWeb site (one-off; overwrites hand edits)
    python3 scripts/extract_iweb.py ../annrast-src     # → src/pages, src/img, scripts/iweb-items.json
    python3 scripts/build_items.py                     # → src/items/*.md, scripts/item-map.json
    python3 scripts/redesign_pages.py                  # → src/my-travels/, src/_data/legacy.json; removes src/pages
(`scripts/legacy-faithful.json` is the faithful-rebuild URL map that redesign_pages.py reads.)

## Build / deploy
    npm ci && SITE_URL=https://redesign.annrast.pages.dev npx @11ty/eleventy
    npx wrangler pages deploy _site --project-name=annrast --branch=redesign
