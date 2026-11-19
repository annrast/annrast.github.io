#!/usr/bin/env python3
"""Redesign prototype, step 3 (after extract_iweb.py and build_items.py):
- keep the personal/travel pages (as extracted) under /my-travels/, unlisted + noindex
- drop the other extracted page bodies (their content now lives in src/items + about page)
- write src/_data/legacy.json: every old iWeb URL → its new home in the redesign
"""
import json, os, re, glob

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
M = json.load(open(os.path.join(ROOT, 'scripts', 'item-map.json')))
L = json.load(open(os.path.join(ROOT, 'scripts', 'legacy-faithful.json')))   # faithful map: old → faithful url (copy made by hand from the eleventy-rebuild branch)
PAGES, TRAV = os.path.join(ROOT, 'src', 'pages'), os.path.join(ROOT, 'src', 'my-travels')
SITE_PAGES = {'AnnRast.com.html': '/', 'DOLLS_FOR_SALE.html': '/', 'About_Me.html': '/about/', 'Contact.html': '/about/#contact',
              'How_to_Buy.html': '/about/#how-to-buy', 'DOLL_FURNITURE_&_ACCESSORIES.html': '/for-sale/doll-clothes-accessories/',
              'Do_Not_Copy_Text_Box.html': '/'}
personal = set(M['personal'])

def new_url(f, faithful):
    if f in SITE_PAGES:
        return SITE_PAGES[f]
    if f in personal:
        return '/my-travels/' if f == 'TRAVEL.html' else '/my-travels' + faithful
    items = M['pageItems'].get(f, [])
    if len(items) == 1:
        return f'/item/{items[0]}/'
    cat = M['pageCategory'].get(f)
    return f'/for-sale/{cat}/' if cat else '/'

faithful_to_new = {}
out = []
for d in L:
    n = new_url(d['file'], d['new'])
    faithful_to_new[d['new']] = n
    out.append({**d, 'new': n})

os.makedirs(TRAV, exist_ok=True)
for d in L:
    src = os.path.join(PAGES, (d['new'].strip('/') or 'index') + '.html')
    if not os.path.exists(src):
        continue
    if d['file'] in personal:
        txt = open(src, encoding='utf-8').read()
        fm_end = txt.index('\n---\n', 4)
        fm = json.loads(txt[4:fm_end])
        body = txt[fm_end + 5:]
        body = re.sub(r'href="(/[^"#]*)', lambda m: 'href="' + faithful_to_new.get(m.group(1), m.group(1)), body)
        fm = {'title': fm['title'], 'description': fm['description'], 'permalink': faithful_to_new[d['new']],
              'layout': 'travel.njk', 'theme': fm.get('theme'), 'canvasWidth': fm.get('canvasWidth')}
        name = 'index' if d['file'] == 'TRAVEL.html' else d['new'].strip('/')
        with open(os.path.join(TRAV, name + '.html'), 'w', encoding='utf-8') as fh:
            fh.write('---\n' + json.dumps({k: v for k, v in fm.items() if v is not None}, ensure_ascii=False, indent=1) + '\n---\n' + body)
    os.remove(src)
json.dump(out, open(os.path.join(ROOT, 'src', '_data', 'legacy.json'), 'w'), indent=1, ensure_ascii=False)
print('travel pages', len(glob.glob(TRAV + '/*.html')), 'legacy entries', len(out))
