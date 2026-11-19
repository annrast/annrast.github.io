#!/usr/bin/env python3
"""One-time migration: turn the iWeb 3 export into Eleventy content files.

Reads the original export (SRC), writes:
  src/pages/*.html      one content file per old page (front matter + body)
  src/img/**.webp       resized, re-encoded, de-duplicated images
  src/css/text.css      shared text classes (deduped from 530 per-page CSS files)
  src/_data/legacy.json old URL -> new URL map (used for _redirects / sitemap / feed)
  migration-report.json  what was dropped / restored
"""
import os, re, sys, json, hashlib, html, urllib.parse, collections
from bs4 import BeautifulSoup, NavigableString, Tag
from PIL import Image, ImageStat

SRC = sys.argv[1] if len(sys.argv) > 1 else '/workspace/site-rebuild/annrast-src'
OUT = sys.argv[2] if len(sys.argv) > 2 else '/workspace/site-rebuild/annrast-11ty'
SITE = 'Ann_Rast_Dolls_&_Collectibles'
SD = os.path.join(SRC, SITE)
DESIGN_W = 949
NAV_TARGETS = {'DOLLS_FOR_SALE.html', 'How_to_Buy.html', 'Contact.html', 'About_Me.html', 'AnnRast.com.html'}

report = collections.defaultdict(list)

# ---------------------------------------------------------------- helpers
def parse_style(s):
    d = {}
    for part in (s or '').split(';'):
        if ':' in part:
            k, v = part.split(':', 1)
            d[k.strip().lower()] = v.strip()
    return d

def px(v, default=0.0):
    m = re.match(r'(-?[\d.]+)', v or '')
    return float(m.group(1)) if m else default

def slugify(s):
    s = s.replace('&', ' and ')
    s = re.sub(r"['’]", '', s)
    s = re.sub(r'[^A-Za-z0-9]+', '-', s).strip('-').lower()
    return re.sub(r'-+', '-', s)

def norm_text(s):
    return re.sub(r'\s+', ' ', s or '').strip()

# ---------------------------------------------------------------- CSS → shared classes
CSS_RULE = re.compile(r'([^{}]+)\{([^{}]*)\}')
KEEP_P = ['color', 'font-family', 'font-size', 'font-style', 'font-weight', 'text-align',
          'text-decoration', 'letter-spacing', 'text-transform', 'padding-top', 'padding-bottom',
          'margin-top', 'margin-bottom', 'text-indent']
KEEP_SPAN = ['color', 'font-family', 'font-size', 'font-style', 'font-weight', 'text-decoration',
             'letter-spacing', 'text-transform', 'vertical-align', 'background-color']
DEFAULTS = {'letter-spacing': '0', 'text-transform': 'none', 'text-indent': '0px', 'padding-top': '0px',
            'padding-bottom': '0px', 'margin-top': '0px', 'margin-bottom': '0px', 'font-weight': '400',
            'font-style': 'normal', 'text-decoration': 'none', 'vertical-align': 'baseline'}
global_classes = {}   # canonical decl string -> class name

def load_page_css(page_files_dir, base):
    rules = {}
    p = os.path.join(page_files_dir, base + '.css')
    if not os.path.exists(p):
        return rules
    txt = open(p, encoding='utf-8', errors='replace').read()
    txt = re.sub(r'/\*.*?\*/', '', txt, flags=re.S)
    for sel, body in CSS_RULE.findall(txt):
        for one in sel.split(','):
            one = one.strip()
            rules.setdefault(one, {}).update(parse_style(body))
    return rules

def font_size_css(v):
    n = px(v, 16)
    if n <= 20:
        return f'{n:g}px'
    lo = max(18, round(n * 0.62))
    vw = round(n / DESIGN_W * 100 * 1.6, 2)
    return f'clamp({lo}px, {vw}vw, {n:g}px)'

def make_class(decls, keep):
    d = {}
    for k in keep:
        if k in decls:
            v = decls[k]
            if DEFAULTS.get(k) == v or (k == 'letter-spacing' and v in ('0', '0px')):
                continue
            if k in ('padding-top', 'padding-bottom', 'margin-top', 'margin-bottom', 'text-indent') and px(v) == 0:
                continue
            if k == 'font-size':
                v = font_size_css(v)
            if k == 'font-family':
                v = re.sub(r"'Cochin-(Italic|Bold|BoldItalic)',\s*", '', v)  # face names → family + style
            d[k] = v
    if not d:
        return None
    key = ';'.join(f'{k}:{d[k]}' for k in sorted(d))
    if key not in global_classes:
        global_classes[key] = f't{len(global_classes) + 1}'
    return global_classes[key]

# ---------------------------------------------------------------- images
img_cache = {}  # (hash, crop, width) -> url
img_bytes_in = 0
def process_image(src_path, page_slug, disp_w, disp_h, crop=None):
    """Return (url, w, h) of an optimized WebP; crop is (l,t,r,b) in display px."""
    global img_bytes_in
    raw = open(src_path, 'rb').read()
    h = hashlib.sha1(raw).hexdigest()[:10]
    key = (h, crop, round(disp_w))
    if key in img_cache:
        return img_cache[key]
    im = Image.open(src_path)
    im.load()
    nat_w, nat_h = im.size
    if crop and disp_w and disp_h:
        sx, sy = nat_w / disp_w, nat_h / disp_h
        l, t, r, b = crop
        box = (max(0, round(l * sx)), max(0, round(t * sy)), min(nat_w, round(r * sx)), min(nat_h, round(b * sy)))
        if box[2] - box[0] > 4 and box[3] - box[1] > 4:
            im = im.crop(box)
        out_w_disp, out_h_disp = r - l, b - t
    else:
        out_w_disp, out_h_disp = disp_w, disp_h
    w, hgt = im.size
    target = min(w, max(1, round(out_w_disp * 2)))   # 2x for retina, never upscale
    if target < w:
        im = im.resize((target, max(1, round(hgt * target / w))), Image.LANCZOS)
    if im.mode not in ('RGB', 'RGBA'):
        im = im.convert('RGBA' if 'transparency' in im.info or im.mode in ('LA', 'P') else 'RGB')
    if im.mode == 'RGBA' and im.getchannel('A').getextrema()[0] == 255:
        im = im.convert('RGB')
    base = slugify(os.path.splitext(os.path.basename(src_path))[0]) or 'img'
    rel = f'img/{page_slug or "home"}/{base}-{h[:6]}.webp'
    dst = os.path.join(OUT, 'src', rel)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    im.save(dst, 'WEBP', quality=82, method=6)
    img_bytes_in += len(raw)
    res = ('/' + rel, round(out_w_disp), round(out_h_disp))
    img_cache[key] = res
    return res

def is_blank(path):
    try:
        im = Image.open(path)
        if im.mode == 'RGBA':
            return im.getchannel('A').getextrema()[1] == 0
        if im.mode == 'P' and 'transparency' in im.info:
            return im.convert('RGBA').getchannel('A').getextrema()[1] == 0
    except Exception:
        return True
    return False

def panel_style(path):
    """If an image is a flat framed panel (iWeb shape), return its fill colour."""
    im = Image.open(path).convert('RGBA')
    w, h = im.size
    if w < 120 or h < 120:
        return None
    inner = im.crop((w // 8, h // 8, w - w // 8, h - h // 8))
    st = ImageStat.Stat(inner.convert('RGB'))
    if max(st.stddev) < 4 and inner.getchannel('A').getextrema()[0] > 200:
        r, g, b = [round(x) for x in st.mean]
        edge = im.getpixel((min(12, w // 2), h // 2))
        return {'bg': f'rgb({r},{g},{b})', 'border': f'rgb({edge[0]},{edge[1]},{edge[2]})'}
    return None

# ---------------------------------------------------------------- page list & slugs
files = sorted(f for f in os.listdir(SD) if f.endswith('.html') and f != 'index.html')
soups = {f: BeautifulSoup(open(os.path.join(SD, f), encoding='utf-8'), 'html.parser') for f in files}

def is_punct(name):
    return not re.search(r'[A-Za-z0-9]', name[:-5].replace('_1', ''))

FIXED = {'AnnRast.com.html': '', 'DOLLS_FOR_SALE.html': 'dolls-for-sale'}

def first_real_text(soup):
    for t in soup.find_all(class_='shape-with-text'):
        tx = norm_text(t.get_text(' '))
        if not tx or 'Ann Rast' in tx or tx.startswith('Dolls For Sale') or tx.startswith('For Sale |'):
            continue
        if re.fullmatch(r'[\W_]*', tx) or tx.startswith('Photo Copyright'):
            continue
        for p in t.find_all('p'):
            pt = norm_text(p.get_text(' '))
            if re.search(r'[A-Za-z]', pt):
                return pt
        return tx
    return ''

slugs, used = {}, set()
# live (published) pages claim slugs before the restored hidden ones
for f in sorted(files, key=lambda n: (n.startswith(('_', '.')), n)):
    if f in FIXED:
        s = FIXED[f]
    elif is_punct(f):
        tx = first_real_text(soups[f])
        s = slugify(' '.join(tx.split()[:8])) if tx else ''
        s = s or 'untitled'
    else:
        s = slugify(f[:-5])
    base, n = s, 2
    while s in used:
        s = f'{base}-{n}'; n += 1
    used.add(s)
    slugs[f] = s

def url_for(f):
    return '/' if slugs[f] == '' else f'/{slugs[f]}/'

def page_title(f):
    t = norm_text(soups[f].title.get_text() if soups[f].title else '')
    if not re.search(r'[A-Za-z0-9]', t):
        tx = first_real_text(soups[f])
        t = ' '.join(tx.split()[:8]) if tx else 'Ann Rast Dolls & Collectibles'
    if f == 'AnnRast.com.html':
        t = 'Ann Rast Dolls & Collectibles'
    return t

titles = {f: page_title(f) for f in files}

def resolve_href(href, cur):
    """Map an iWeb href to its new URL. Returns (new_href, ok)."""
    if href is None:
        return None, True
    href = href.strip()
    if not href:
        return None, True
    if href.startswith('mailto:'):
        return href, True                      # keep mailto exactly as-is
    if re.match(r'^[a-z]+:', href):
        if href.startswith('http://apple.com/mac') or href.startswith('http://www.apple.com/mac'):
            return 'https://www.apple.com/mac/', True
        return href, True
    if href.startswith('#'):
        return href, True
    path, _, frag = href.partition('#')
    path = urllib.parse.unquote(path)
    path = path.replace('../', '').replace('./', '')
    name = path.split('/')[-1]
    if name in slugs:
        return url_for(name) + (('#' + frag) if frag else ''), True
    if name in ('', 'index.html'):
        return '/', True
    report['unresolved_links'].append({'page': cur, 'href': href})
    return href, False

# ---------------------------------------------------------------- item extraction
class Item:
    def __init__(self, kind, x, y, w, h, **kw):
        self.kind, self.x, self.y, self.w, self.h = kind, x, y, w, h
        self.__dict__.update(kw)
    @property
    def r(self): return self.x + self.w
    @property
    def b(self): return self.y + self.h

def text_html(node, rules, cur, cls_p=True):
    """Re-emit iWeb text-content with shared classes, links rewritten, no layout styles."""
    out = []
    for p in node.find_all('p'):
        cls = None
        for c in p.get('class', []):
            if '.' + c in rules:
                cls = make_class(rules['.' + c], KEEP_P)
        inner = inline_html(p, rules, cur)
        if not norm_text(BeautifulSoup(inner, 'html.parser').get_text()) and '<img' not in inner:
            inner = ''
            out.append('<p class="sp"></p>')
            continue
        inner = re.sub(r'(<br>\s*)+$', '', inner)
        out.append(f'<p{" class=" + chr(34) + cls + chr(34) if cls else ""}>{inner}</p>')
    # collapse runs of spacer paragraphs and trim them at the ends
    s = '\n'.join(out)
    s = re.sub(r'(<p class="sp"></p>\n?){2,}', '<p class="sp"></p>\n', s)
    s = re.sub(r'^(<p class="sp"></p>\n?)+|(\n?<p class="sp"></p>)+$', '', s)
    return s

def inline_html(el, rules, cur):
    parts = []
    for ch in el.children:
        if isinstance(ch, NavigableString):
            parts.append(html.escape(str(ch), quote=False))
        elif ch.name == 'br':
            parts.append('<br>')
        elif ch.name == 'span':
            cls = None
            for c in ch.get('class', []):
                if '.' + c in rules:
                    cls = make_class(rules['.' + c], KEEP_SPAN)
            inner = inline_html(ch, rules, cur)
            parts.append(f'<span class="{cls}">{inner}</span>' if cls and inner.strip() else inner)
        elif ch.name == 'a':
            href, ok = resolve_href(ch.get('href'), cur)
            cls = None
            for c in ch.get('class', []):
                if 'a.' + c in rules:
                    cls = make_class(rules['a.' + c], KEEP_SPAN)
            inner = inline_html(ch, rules, cur)
            attrs = ''
            if href:
                attrs += f' href="{html.escape(href)}"'
            if cls:
                attrs += f' class="{cls}"'
            if ch.get('target') == '_blank' or (href and href.startswith('http')):
                attrs += ' rel="noopener"'
            parts.append(f'<a{attrs}>{inner}</a>')
        elif ch.name == 'img':
            parts.append('')  # inline images inside text boxes are handled as items
        else:
            parts.append(inline_html(ch, rules, cur))
    return ''.join(parts)

def map_links(soup, img):
    m = soup.find('map', attrs={'name': (img.get('usemap') or '#')[1:]})
    if not m:
        return [], None
    lines, whole = [], None
    for a in m.find_all('area'):
        if a.get('shape') == 'rect':
            co = [int(x) for x in re.findall(r'-?\d+', a.get('coords', ''))]
            lines.append((co[1] if len(co) > 1 else 0, a.get('href')))
        else:
            whole = a.get('href')
    lines.sort()
    return lines, whole

def extract_page(f):
    soup = soups[f]
    base = f[:-5]
    fdir = os.path.join(SD, base + '_files')
    rules = load_page_css(fdir, base)
    slug = slugs[f]
    items = []
    hdr = soup.find(id='header_layer')
    body = soup.find(id='body_layer')
    ftr = soup.find(id='footer_layer')
    hdr_h = px(parse_style(hdr.get('style')).get('height')) if hdr else 0
    body_h = 0
    if body:
        sp = body.find('div', class_='spacer', recursive=False)
        body_h = px(parse_style(sp.get('style')).get('height')) if sp else 0
    nav = soup.find(id='nav_layer')
    offsets = [(nav, 0), (hdr, 0), (body, hdr_h), (ftr, hdr_h + body_h)]
    for layer, off in offsets:
        if not layer:
            continue
        for el in layer.find_all(recursive=False):
            if el.name != 'div':
                if el.name == 'a' and el.find('img') and 'mwmac' in (el.find('img').get('src') or ''):
                    continue  # "Made on a Mac" badge → shared footer
                continue
            cls = el.get('class', [])
            if 'bumper' in cls or 'spacer' in cls:
                continue
            st = parse_style(el.get('style'))
            x, y, w, h = px(st.get('left')), px(st.get('top')) + off, px(st.get('width')), px(st.get('height'))
            framed = any(c.startswith('stroke_') for c in cls)
            shadow = any(c.startswith('shadow_') for c in cls)
            if (el.get('id') or '').startswith('widget'):
                mk = el.find('script')
                murl = re.search(r'htmlMarkupURL = "([^"]+)"', mk.string or '') if mk else None
                mpath = os.path.normpath(os.path.join(SD, murl.group(1))) if murl else ''
                mtxt = open(mpath, encoding='utf-8').read() if mpath and os.path.exists(mpath) else ''
                if 'sc_project' in mtxt:
                    inv = re.search(r'sc_invisible=(\d)', mtxt).group(1)
                    items.append(Item('statcounter', x, y, w, h, invisible=inv))
                elif 'oncontextmenu' in mtxt:
                    report['dropped'].append({'page': f, 'what': 'right-click "protection" alert widget'})
                else:
                    report['dropped'].append({'page': f, 'what': 'empty HTML widget', 'markup': mtxt[:200]})
                continue
            if 'shape-with-text' in cls and el.find(class_='text-content'):
                tc = el.find(class_='text-content')
                txt = norm_text(tc.get_text(' '))
                hrefs = [a.get('href', '') for a in tc.find_all('a')]
                ptxt = ' | '.join(norm_text(p.get_text(' ')) for p in tc.find_all('p'))
                if 'Ann Rast' in txt and 'Dolls & Collectibles' in txt and len(txt) < 40:
                    continue  # per-page site title → shared header
                if (len(hrefs) >= 2 and all(hh == '' or hh.split('/')[-1] in NAV_TARGETS for hh in hrefs) and len(txt) < 60
                        and sum(w in txt for w in ('How To Buy', 'Contac', 'About Me', 'For Sale')) >= 3):
                    continue  # per-page nav → shared nav
                inner_imgs = [i for i in el.find_all('img')]
                if not txt and not inner_imgs:
                    continue  # empty decorative shape
                th = text_html(tc, rules, f)
                if txt:
                    items.append(Item('text', x, y, w, h, html=th, text=txt))
                for i in inner_imgs:
                    srcp = os.path.join(SD, urllib.parse.unquote(i.get('src')))
                    if os.path.exists(srcp) and not is_blank(srcp):
                        ist = parse_style(i.get('style'))
                        a = i.find_parent('a')
                        items.append(Item('photo', x, y + h, px(ist.get('width'), w), px(ist.get('height'), 50), src=srcp,
                                          href=a.get('href') if a else None, framed=False, shadow=False, alt=i.get('alt', '')))
                continue
            img = el.find('img')
            if not img:
                if el.get_text(strip=True):
                    report['dropped'].append({'page': f, 'what': 'unrecognised element', 'text': el.get_text(' ', strip=True)[:120]})
                continue
            if el.get('id') == 'widget' or 'navbar' in str(el.get('class')):
                continue
            src = urllib.parse.unquote(img.get('src', ''))
            srcp = os.path.join(SD, src)
            if 'Darkroom_spotlight' in src:
                continue  # theme decoration → CSS background of the PhotoGray theme
            alt = (img.get('alt') or '').replace('\r', '')
            if img.get('usemap') or 'shapeimage' in src:
                lines, whole = map_links(soup, img)
                if not os.path.exists(srcp):
                    report['missing'].append({'page': f, 'src': src}); continue
                blank = is_blank(srcp)
                _iw, _ih = Image.open(srcp).size
                if h <= 3 or _ih <= 3 or (_ih <= 12 and _iw / max(_ih, 1) > 20):
                    continue  # 1-px rule lines
                if blank:
                    if not alt.strip():
                        continue
                    if alt.strip() == 'Link':
                        items.append(Item('hotspot', x, y, w, h, href=(lines[0][1] if lines else whole)))
                        continue
                    items.append(Item('shapetext', x, y, w, h, text=alt.rstrip('\n'), lines=lines, whole=whole))
                    continue
                ps = None if img.get('usemap') else panel_style(srcp)
                ps = ps or (panel_style(srcp) if not (lines or whole) else None)
                ist = parse_style(img.get('style'))
                items.append(Item('photo', x, y, w, h, src=srcp, href=(lines[0][1] if lines else whole),
                                  framed=False, shadow=False, alt=alt if alt.strip() and 'shapeimage' not in alt else '',
                                  panel=ps, disp=(px(ist.get('width'), w), px(ist.get('height'), h)),
                                  off=(px(ist.get('left')), px(ist.get('top'))), shapeimg=True))
                continue
            if not os.path.exists(srcp):
                report['missing'].append({'page': f, 'src': src}); continue
            ist = parse_style(img.get('style'))
            a = img.find_parent('a')
            iw, ih = px(ist.get('width'), w), px(ist.get('height'), h)
            items.append(Item('photo', x, y, w, h, src=srcp, href=a.get('href') if a else None, framed=framed,
                              shadow=shadow, alt=alt if alt and not alt.startswith('shapeimage') else '',
                              panel=None, disp=(iw, ih), off=(px(ist.get('left')) + px(ist.get('margin-left')),
                                                               px(ist.get('top')) + px(ist.get('margin-top'))), shapeimg=False))
    if 'writeMovie' in open(os.path.join(fdir, base + '.js'), encoding='utf-8', errors='replace').read() if os.path.exists(os.path.join(fdir, base + '.js')) else False:
        report['dropped'].append({'page': f, 'what': 'QuickTime embed of Media/IMG_4775.MOV (file missing from repo, plugin obsolete); removed'})
    return items

# ---------------------------------------------------------------- post-processing per page
def overlap(a0, a1, b0, b1):
    return max(0, min(a1, b1) - max(a0, b0))

def postprocess(items, f):
    # hotspots → give their link to the photo beneath
    for hs in [i for i in items if i.kind == 'hotspot']:
        best = None
        for p in items:
            if p.kind == 'photo' and not p.href and overlap(p.x, p.r, hs.x, hs.r) * overlap(p.y, p.b, hs.y, hs.b) > 0:
                best = p
        if best and hs.href:
            best.href = hs.href
        elif hs.href:
            report['dropped'].append({'page': f, 'what': 'invisible "Link" hotspot with no photo under it', 'href': hs.href})
    items = [i for i in items if i.kind != 'hotspot']
    # panels: flat framed shapes that contain other items
    panels = []
    for p in items:
        if p.kind == 'photo' and getattr(p, 'panel', None):
            kids = [i for i in items if i is not p and p.x - 4 <= i.x + i.w / 2 <= p.r + 4 and p.y - 4 <= i.y + i.h / 2 <= p.b + 4]
            if kids:
                p.kind = 'panel'; panels.append(p)
            else:
                p.kind = 'decor'
    items = [i for i in items if i.kind != 'decor']
    # captions → alt text
    for p in items:
        if p.kind != 'photo' or p.alt:
            continue
        caps = [t for t in items if t.kind in ('text', 'shapetext') and -12 <= t.y - p.b <= 70 and overlap(p.x, p.r, t.x, t.r) > 0.4 * min(p.w, t.w)]
        if caps:
            p.alt = norm_text(sorted(caps, key=lambda t: t.y)[0].text)[:125]
        elif p.href:
            hr, _ = resolve_href(p.href, f)
            nm = urllib.parse.unquote(p.href.split('#')[0]).split('/')[-1]
            p.alt = titles.get(nm, '') if nm in titles else ''
        if not p.alt:
            p.alt = titles[f]
    return items

# ---------------------------------------------------------------- layout (XY-cut)
TOL = 6
def groups_by(items, lo, hi):
    its = sorted(items, key=lo)
    groups, cur, end = [], [], None
    for i in its:
        if cur and lo(i) >= end - TOL:
            groups.append(cur); cur, end = [], None
        cur.append(i)
        end = hi(i) if end is None else max(end, hi(i))
    if cur:
        groups.append(cur)
    return groups

def bbox(items):
    return (min(i.x for i in items), min(i.y for i in items), max(i.r for i in items), max(i.b for i in items))

def place_style(x, w, cx, cw):
    """Horizontal placement of a block of width w at x inside a container."""
    if cw <= 0:
        return ''
    if w >= cw - 8:
        return ''
    centre = (x + w / 2 - cx) / cw
    if abs(centre - 0.5) < 0.08:
        return 'margin-inline:auto'
    pct = max(0, round((x - cx) / cw * 100, 1))
    return f'margin-left:max(0px,min({pct}%,100% - {round(w)}px))'

def page_canvas(soup):
    bc = soup.find(id='body_content')
    w = px(parse_style(bc.get('style')).get('width'), DESIGN_W) if bc else DESIGN_W
    inner = bc.find('div') if bc else None
    theme = 'photogray' if inner is not None and 'PhotoGray' in (inner.get('style') or '') else None
    return w, theme

def render_items(items, cx, cw, f, depth=0):
    if not items:
        return ''
    if depth > 40:
        return '\n'.join(render_item(i, f) for i in sorted(items, key=lambda i: (i.y, i.x)))
    # panels own the items inside them
    if len(items) > 1:
        rows = groups_by(items, lambda i: i.y, lambda i: i.b)
        if len(rows) > 1:
            out, prev_b = [], None
            for g in rows:
                x0, y0, x1, y1 = bbox(g)
                gap = 0 if prev_b is None else max(0, y0 - prev_b)
                inner = render_items(g, cx, cw, f, depth + 1)
                st = [place_style(x0, x1 - x0, cx, cw)] if len(g) == 1 else []
                if gap > 14:
                    st.append(f'margin-top:{min(round(gap), 48)}px')
                st = ';'.join(s for s in st if s)
                if len(g) == 1 and not st:
                    out.append(inner)
                else:
                    out.append(f'<div class="blk"{" style=" + chr(34) + st + chr(34) if st else ""}>\n{inner}\n</div>')
                prev_b = y1 if prev_b is None else max(prev_b, y1)
            return '\n'.join(out)
        cols = groups_by(items, lambda i: i.x, lambda i: i.r)
        if len(cols) > 1:
            out = []
            for g in cols:
                x0, y0, x1, y1 = bbox(g)
                cst = f'flex:0 1 {round(x1 - x0)}px'
                out.append(f'<div class="col" style="{cst}">\n{render_items(g, x0, x1 - x0, f, depth + 1)}\n</div>')
            return '<div class="row">\n' + '\n'.join(out) + '\n</div>'
        # overlapping: a panel containing others?
        pans = [i for i in items if i.kind == 'panel']
        if pans:
            p = max(pans, key=lambda i: i.w * i.h)
            rest = [i for i in items if i is not p]
            inside = [i for i in rest if p.x - 4 <= i.x + i.w / 2 <= p.r + 4 and p.y - 4 <= i.y + i.h / 2 <= p.b + 4]
            outside = [i for i in rest if i not in inside]
            ph = (f'<div class="panel" style="--panel-bg:{p.panel["bg"]};--panel-border:{p.panel["border"]}">\n'
                  f'{render_items(inside, p.x, p.w, f, depth + 1)}\n</div>')
            if not outside:
                return ph
            # re-run layout treating the panel as one opaque block
            blk = Item('raw', p.x, p.y, p.w, p.h, html=ph)
            return render_items(outside + [blk], cx, cw, f, depth + 1)
        # genuinely overlapping content (text over photo etc.): stack in reading order
        ordered = sorted(items, key=lambda i: (round(i.y / 20), i.x))
        return '\n'.join(f'<div class="blk" style="{place_style(i.x, i.w, cx, cw)}">{render_item(i, f)}</div>' for i in ordered)
    i = items[0]
    if i.kind == 'panel':
        return f'<div class="panel" style="--panel-bg:{i.panel["bg"]};--panel-border:{i.panel["border"]};min-height:{round(i.h*0.3)}px"></div>'
    return render_item(i, f)

def render_item(i, f):
    slug = slugs[f]
    if i.kind == 'raw':
        return i.html
    if i.kind == 'text':
        return f'<div class="tb" style="width:{round(i.w)}px">\n{i.html}\n</div>'
    if i.kind == 'shapetext':
        lines = i.text.split('\n')
        nonempty = [l for l in lines if l.strip()]
        linkable = [l for l in i.lines if l[1]]
        out = []
        if linkable and len(linkable) == len(nonempty):
            k = 0
            for l in lines:
                if l.strip():
                    href, _ = resolve_href(linkable[k][1], f); k += 1
                    out.append(f'<a href="{html.escape(href)}">{html.escape(l.strip())}</a>')
                else:
                    out.append('')
            body = '<br>'.join(out)
        else:
            body = '<br>'.join(html.escape(l) for l in lines)
            target = (linkable[0][1] if linkable else None) or i.whole
            if target:
                href, _ = resolve_href(target, f)
                if href:
                    body = f'<a href="{html.escape(href)}">{body}</a>'
        return f'<p class="shape-text" style="width:{round(i.w)}px">{body}</p>'
    if i.kind == 'statcounter':
        return f'<div class="statcounter-slot" data-invisible="{i.invisible}"></div>'
    if i.kind == 'photo':
        dw, dh = getattr(i, 'disp', (i.w, i.h))
        ox, oy = getattr(i, 'off', (0, 0))
        crop = None
        if not getattr(i, 'shapeimg', False) and (dw - i.w > 3 or dh - i.h > 3 or ox < -3 or oy < -3):
            l, t = max(0, -ox), max(0, -oy)
            crop = (round(l), round(t), round(min(dw, l + i.w)), round(min(dh, t + i.h)))
        url, w, h = process_image(i.src, slug, dw, dh, crop)
        cls = 'ph' + (' framed' if i.framed else '') + (' shadow' if i.shadow and not i.framed else '')
        alt = html.escape(norm_text(i.alt), quote=True)
        tag = f'<img src="{url}" width="{w}" height="{h}" alt="{alt}" loading="lazy" decoding="async">'
        if i.href:
            href, _ = resolve_href(i.href, f)
            if href:
                tag = f'<a href="{html.escape(href)}">{tag}</a>'
        return f'<figure class="{cls}" style="width:{w}px">{tag}</figure>'
    return ''

# ---------------------------------------------------------------- run
def describe(items):
    txt = ' '.join(norm_text(i.text) for i in sorted(items, key=lambda i: (i.y, i.x)) if i.kind in ('text', 'shapetext'))
    txt = re.sub(r'\s+', ' ', txt).strip()
    if len(txt) > 155:
        txt = txt[:155].rsplit(' ', 1)[0].rstrip(',;:-') + '…'
    return txt

pages_dir = os.path.join(OUT, 'src', 'pages')
os.makedirs(pages_dir, exist_ok=True)
legacy = []
first_img = {}
for f in files:
    items = postprocess(extract_page(f), f)
    if items:
        x0, y0, x1, y1 = bbox(items)
    canvas_w, theme = page_canvas(soups[f])
    body = render_items(items, 0, canvas_w, f)
    # mark first image eager (LCP)
    body = body.replace(' loading="lazy"', ' fetchpriority="high"', 1)
    if f == 'AnnRast.com.html':
        pass
    desc = describe(items) or titles[f]
    if desc in ('', titles[f]):
        desc = f'{titles[f]} – Ann Rast Dolls & Collectibles'
    sc = [i.invisible for i in items if i.kind == 'statcounter']
    fm = {
        'title': titles[f],
        'description': desc,
        'permalink': url_for(f) if url_for(f) != '/' else '/',
        'legacyUrl': f'/{SITE}/{f}',
        'statcounter': sc[0] if sc else None,
        'restored': f.startswith('_') or f.startswith('.'),
        'blank': not items,
    }
    if theme:
        fm['theme'] = theme
    if canvas_w != DESIGN_W:
        fm['canvasWidth'] = round(canvas_w)
    m = re.search(r'src="([^"]+\.webp)"', body)
    if m:
        fm['ogImage'] = m.group(1)
    fname = (slugs[f] or 'index') + '.html'
    with open(os.path.join(pages_dir, fname), 'w', encoding='utf-8') as fh:
        fh.write('---\n' + json.dumps(fm, ensure_ascii=False, indent=1) + '\n---\n' + body + '\n')
    legacy.append({'old': f'/{SITE}/{f}', 'new': url_for(f), 'title': titles[f], 'restored': fm['restored'], 'file': f})
    if fm['restored']:
        report['restored'].append({'old': f, 'new': url_for(f), 'title': titles[f]})

# shared chrome: one copy of the pinstripe tile (was duplicated 170 times)
os.makedirs(os.path.join(OUT, 'src', 'img', 'shared'), exist_ok=True)
for srcf, name in [('AnnRast.com_files/pinstripe_bk_tile3-51.jpg', 'pinstripe'),
                   ('.._files/PhotoGray_browser_bg-2.jpg', 'photogray-browser-bg'),
                   ('.._files/PhotoGray_bg_c-1.jpg', 'photogray-bg'),
                   ('.._files/Darkroom_spotlight.jpg', 'darkroom-spotlight')]:
    Image.open(os.path.join(SD, srcf)).save(os.path.join(OUT, 'src', 'img', 'shared', name + '.webp'), 'WEBP', quality=85, method=6)

# shared text classes
css = ['/* Generated from the 530 iWeb per-page stylesheets: identical text styles merged into shared classes. */']
for key, name in sorted(global_classes.items(), key=lambda kv: int(kv[1][1:])):
    css.append(f'.{name}{{{key}}}')
os.makedirs(os.path.join(OUT, 'src', 'css'), exist_ok=True)
open(os.path.join(OUT, 'src', 'css', 'text.css'), 'w').write('\n'.join(css) + '\n')
os.makedirs(os.path.join(OUT, 'src', '_data'), exist_ok=True)
json.dump(legacy, open(os.path.join(OUT, 'src', '_data', 'legacy.json'), 'w'), indent=1, ensure_ascii=False)
report['stats'] = {'pages': len(files), 'text_classes': len(global_classes), 'images_out': len(set(img_cache.values())),
                   'source_image_bytes_used': img_bytes_in}
json.dump(report, open(os.path.join(OUT, 'migration-report.json'), 'w'), indent=1, ensure_ascii=False)
print(json.dumps(report['stats']), 'unresolved:', len(report['unresolved_links']), 'missing:', len(report['missing']))
