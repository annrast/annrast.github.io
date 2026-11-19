# annrast.com — Eleventy rebuild

Ann Rast Dolls & Collectibles, rebuilt from the 2009-era iWeb export (still on `master`) as a small Eleventy site.
Same text, prices, photos, colours and fonts; one shared layout and stylesheet; responsive.

```
npm install
npm run build          # → _site/ (SITE_URL=https://… sets absolute URLs in sitemap/feed/robots)
npm run serve          # local preview
```

- `src/pages/*.html` – one content file per old iWeb page (front matter: title, description, permalink, legacyUrl).
- `src/_includes/base.njk` – shared header / nav / footer (+ StatCounter 8256649 over HTTPS where the old page had it).
- `src/css/site.css` – layout; `src/css/text.css` – text styles merged from the 530 iWeb stylesheets.
- `src/img/` – resized WebP images (de-duplicated; one copy of shared backgrounds in `img/shared/`).
- `src/redirects.njk` → `_redirects` – 301 from every old iWeb URL (literal `&` and `%26` forms) to its new path.
- `src/_data/legacy.json` – old URL → new URL map. `migration-report.json` – what was dropped/restored.
- `scripts/extract_iweb.py` – the one-time migration script (run against a checkout of `master`).
