#!/usr/bin/env python3
"""Redesign prototype: turn the extracted iWeb page items (scripts/iweb-items.json, written by
extract_iweb.py) into one content file per item for sale.

Rules: never invent an item, name or price. Text is copied from the old pages. Anything the
heuristics are unsure about gets a `todo:` note for a human to check.
"""
import json, re, os, urllib.parse, collections, yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = json.load(open(os.path.join(ROOT, 'scripts', 'iweb-items.json')))
OUT = os.path.join(ROOT, 'src', 'items')

# ---- categories (from the old "Dolls For Sale" hub and its sub-pages) -------------------------
CATS = [
    ('madame-alexander', 'Madame Alexander Dolls', ['8-Inch_MA', '10-Inch_MADAME', '12-21-Inch_MADAME', 'MADAME_ALEXANDER_DOLLS', 'Cissy_1955',
        'Cissy_Godey_1961', 'Southern_Belle_1965', 'Wendy_Another_Party_Dress', 'Wendy_in_Little_Genius', 'Nina_Ballerina', '...html', 'Cissette_Teddy']),
    ('robert-tonner', 'Robert Tonner Dolls', ['TONNER_DOLLS', 'Tyler_&_Family', 'ELLOWYNE_WILDE', 'Ellowyne_Accessories', 'Grace_-_Tyler', '_...html',
        '__._._._._._._.._._._._._._..html', 'Ima_Shopaholic', 'MODELS', 'Odile_Outfit']),
    ('other-dolls', 'Other Dolls', ['Other_Dolls', 'Dolls_for_your_Dolls', 'Shoe_Fairy', 'Penny_Brite', 'file.html', '..html']),
    ('doll-clothes-accessories', 'Doll Clothes, Shoes & Accessories', ['Cissys_Closet', 'Cissettes_Closet', 'Lissys_Closet', 'Wendys_Closet',
        'Cissy_Clothing', 'Cissy_Dress_Forms', 'Cissy_Jewelry', 'Cissy_Luggage', 'Doll_Shoes', 'HATS_-_8-10', 'Socks', 'Petticoats', 'Tights',
        'Parasols', 'Millinery', 'Jewelry', 'Doll_Accessories', 'Misc_Doll_Items', 'Doll_Dresses', 'Dress_Form', 'Doll_Stands', 'Doll_Stand_Sleeves',
        'Wrist_Tags.html']),
    ('doll-furniture', 'Doll Furniture & Tea Sets', ['Doll_Furniture', 'Benches', 'China_Cabinet', 'Dresser', 'Tables_&_Chairs', 'Sroller', 'Windows',
        'Tea_Sets', 'Furniture_Cissy', 'Red_Vevet_Chair']),
    ('teddy-bears', 'Teddy Bears', ['Teddy_Bears', 'Joan_Woessners', 'Allison_&_Fawn', 'Christmas_Elfinbearry', 'Jester_Bear', 'Peach_Velved',
        'Purple_Bear', 'Gund_Bears', 'Steiff', 'Priscilla', 'Prissy_Panda', 'Pocket_Pals', 'VIB_Cinbearella', 'Victorian_Bears', 'La_Purr']),
    ('figurines', 'Figurines', ['FIGURINES', 'WDCC_Lucifer', 'Figurines_&_Paper_Dolls', 'Snow_Whites', '__._._._._._..html', '__._._._._._._..html',
        '__._._._._._._._..html', '__._._._._._._._._..html']),
    ('fabric-lace-trims', 'Fabric, Lace & Trims', ['FABRIC', 'Everything_Else', 'BLACK', 'BLUE', 'GREEN', 'PINK', 'RED.html', 'WHITE', 'IVORY', 'GOLD_&_SILVER', 'FLOWERS',
        'Lace,', 'Copy_Lace', 'Ribbon_Page', 'Ruffles']),
    ('patterns-books', 'Patterns, Books & Catalogs', ['Patterns.html', 'Catalogs_&_Books', 'Tonner_Catalogs', 'Wrist_Tags,_Patterns,_Books',
        'Convention_Souvenirs']),
    ('art-prints', 'Art & Prints', ['ARTWORK', 'Mary_Hulgan', 'Pictures,_Paintings']),
    ('collectibles', 'Coca-Cola, Star Wars & Other Collectibles', ['COCA_COLA', 'Star_Wars', 'STAR_TREK', 'STAR_WARS', 'Boba_Fett', 'Fenton']),
    ('furniture', 'Furniture (full size)', ['Furniture_For_Sale']),
]
PERSONAL = ['TRAVEL', 'Day_', 'Days_', 'Grand_European', 'Ship_&_Cabin', 'Menus', 'Waiters', 'Cruise_Friends', 'Fun_w_Friends', 'Breckenridge',
            'Snow_1-10-2011', 'Anns_Gallery']
SITE = ['AnnRast.com.html', 'DOLLS_FOR_SALE.html', 'DOLL_FURNITURE_&_ACCESSORIES.html', 'About_Me.html', 'Contact.html', 'How_to_Buy.html',
        'Do_Not_Copy_Text_Box.html']

def cat_of(f):
    for key, label, pats in CATS:
        for p in pats:
            if (p.endswith('.html') and f == p) or (not p.endswith('.html') and f.startswith(p)):
                return key
    return None

def is_personal(f):
    return any(f.startswith(p) for p in PERSONAL)

PRICE = re.compile(r'\$\s?\.?\d')
STATUS_SOLD = re.compile(r'\bsold\b(?!\s+separately)', re.I)
STATUS_HOLD = re.compile(r'\bon\s+hold\b|\bhold\b', re.I)
NOISE = re.compile(r'click|see .* on another page|please check back|^\(?more\b', re.I)

def target(h):
    if not h:
        return None
    n = urllib.parse.unquote(h.split('#')[0]).split('/')[-1]
    return n if n in D else None

def slugify(s):
    s = s.replace('&', ' and ')
    s = re.sub(r"['’“”\"]", '', s)
    return re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')[:70].strip('-')

def texts(p):
    out = []
    for it in p['items']:
        if it['kind'] == 'text':
            out.append(dict(it, lines=[l for l in it.get('paras') or [] if l.strip()]))
        elif it['kind'] == 'shapetext':
            out.append(dict(it, lines=[l.strip() for l in it['text'].split('\n') if l.strip()]))
    return out

def is_listing_text(t):
    body = ' '.join(t['lines'])
    return bool(PRICE.search(body) or STATUS_SOLD.search(body) or re.search(r'\bon hold\b', body, re.I))

def centre(i):
    return (i['x'] + i['w'] / 2, i['y'] + i['h'] / 2)

def dist(photo, t):
    # captions sit under (or beside) their photo
    ov = min(photo['x'] + photo['w'], t['x'] + t['w']) - max(photo['x'], t['x'])
    below = t['y'] - (photo['y'] + photo['h'])
    if ov > 0.3 * min(photo['w'], t['w']) and -40 <= below <= 120:
        return below / 10
    (ax, ay), (bx, by) = centre(photo), centre(t)
    return ((ax - bx) ** 2 + (ay - by) ** 2) ** 0.5

items, page_items, todos, unplaced = [], collections.defaultdict(list), [], collections.Counter()
detail_pages = {f for f, p in D.items() if any(is_listing_text(t) for t in texts(p))}

def make_item(f, lines, photos, extra_todo=None):
    cat = cat_of(f)
    lines = [l for l in lines if not NOISE.search(l)]
    price_lines = [l for l in lines if PRICE.search(l)]
    name = next((l for l in lines if not PRICE.search(l) and not STATUS_SOLD.fullmatch(l.strip())), None)
    todo = []
    if not name:
        name = D[f]['title'] if re.search(r'[A-Za-z]', D[f]['title']) else 'Untitled item'
        todo.append('Name taken from the old page title; check it.')
    desc = [l for l in lines if l != name and l.strip().lower() not in name.lower() and l not in price_lines and not re.fullmatch(r'(?i)sold|on hold|hold', l.strip())]
    body = ' '.join(lines)
    status = 'Sold' if STATUS_SOLD.search(body) or re.search(r'(?i)out of stock', body) else 'On Hold' if re.search(r'\bon hold\b|\bhold\b', body, re.I) else 'Available'
    price = ' · '.join(price_lines) if price_lines else None
    if not price and status != 'Sold':
        todo.append('No price on the old page.')
    if len(PRICE.findall(body)) > 1 and not re.search(r'(?i)sale|orig|was', body):
        todo.append('Several prices in one listing on the old page; check which applies (may be several items).')
    if not photos:
        todo.append('No photo found for this item on the old page.')
    if extra_todo:
        todo.append(extra_todo)
    return {'title': name, 'category': cat, 'price': price, 'status': status,
            'photos': photos, 'description': '\n'.join(desc), 'todo': ' '.join(todo) or None, 'oldPage': f}

for f, p in D.items():
    cat = cat_of(f)
    if not cat or f in SITE or is_personal(f):
        continue
    ts = texts(p)
    listing = [t for t in ts if is_listing_text(t)]
    photos = [i for i in p['items'] if i['kind'] == 'photo' and i.get('url')]
    nav_photos = [i for i in photos if target(i.get('href')) and target(i.get('href')) != f]
    own_photos = sorted([i for i in photos if i not in nav_photos], key=lambda i: (round(i['y'] / 40), i['x']))
    # a listing on a summary page whose photo links to a detail page with its own listings → the detail page owns it
    assign = {id(t): [] for t in listing}
    skip = set()
    for t in listing:
        near = [ph for ph in nav_photos if dist(ph, t) < 15]
        if near and all(target(ph['href']) in detail_pages for ph in near):
            skip.add(id(t))
    live = [t for t in listing if id(t) not in skip]
    for ph in own_photos:
        if not live:
            break
        best = min(live, key=lambda t: dist(ph, t))
        if dist(ph, best) < 700:
            assign[id(best)].append(ph['url'])
        else:
            unplaced[f] += 1
    for ph in nav_photos:  # summary-page listing that links to a page without its own listings: keep its photo
        for t in live:
            if dist(ph, t) < 15:
                assign[id(t)].append(ph['url'])
    if len(live) == 1 and not skip:
        # a page about one item: the page title is the item name, every photo and note on it belongs to it
        t = live[0]
        title = p['title'] if re.search(r'[A-Za-z]', p['title']) and p['title'] != 'Ann Rast Dolls & Collectibles' else None
        extra = [l for o in ts if o is not t and not is_listing_text(o) for l in o['lines']
                 if l.strip().lower() != (title or '').lower() and len(o['lines']) and o['y'] > t['y'] - 400]
        lines = ([title] if title else []) + [l for l in t['lines'] if l.strip().lower() != (title or '').lower()] + extra
        page_items[f].append(make_item(f, lines, [ph['url'] for ph in own_photos] + assign[id(t)][len(own_photos):] if own_photos else assign[id(t)]))
        continue
    for t in live:
        lines = list(t['lines'])
        first = next((l for l in lines if not PRICE.search(l)), '')
        if first and (len(first) <= 14 or not re.search(r'[A-Za-z]{4}', first)) and re.search(r'[A-Za-z]', p['title']):
            nxt = [l for l in lines[lines.index(first) + 1:] if not PRICE.search(l) and re.search(r'[A-Za-z]{4}', l)]
            if nxt:   # "FAB-31" + "Red Print …" → "Red Print … (FAB-31)"
                lines.remove(nxt[0]); lines[lines.index(first)] = f"{nxt[0]} ({first})"
            else:
                lines[lines.index(first)] = f"{p['title']} – {first}"   # e.g. "LE 1/25 MIB" → "Candy Kisses … – LE 1/25 MIB"
        page_items[f].append(make_item(f, lines, assign[id(t)]))
    if not listing and own_photos and len(nav_photos) < len(photos) / 2:
        # a product page with no price or status text at all: one item per page, flagged
        lines = [l for t in ts for l in t['lines']]
        page_items[f].append(make_item(f, lines, [ph['url'] for ph in own_photos],
                                       'Built from a whole old page with no price or status; check it is one item and still for sale.'))
    if not listing and not photos and [t for t in ts if t['lines']]:
        lines = [l for t in ts for l in t['lines']]
        if f == 'Furniture_For_Sale.html':
            lines = lines[1:]  # first line is the page heading "Furniture For Sale"
        if len(lines) >= 2:
            page_items[f].append(make_item(f, lines, []))

# ---- write files ---------------------------------------------------------------------------
os.makedirs(OUT, exist_ok=True)
for old in os.listdir(OUT):
    if old.endswith('.md'):
        os.remove(os.path.join(OUT, old))
used = collections.Counter()
legacy_targets = {}
for f in sorted(page_items):
    for it in page_items[f]:
        s = slugify(it['title']) or 'item'
        used[s] += 1
        if used[s] > 1:
            s = f'{s}-{used[s]}'
        it['slug'] = s
        fm = {k: it[k] for k in ('title', 'category', 'price', 'status', 'photos', 'todo', 'oldPage') if it[k] not in (None, [], '')}
        with open(os.path.join(OUT, s + '.md'), 'w') as fh:
            fh.write('---\n' + yaml.safe_dump(fm, allow_unicode=True, sort_keys=False, width=1000) + '---\n' + it['description'] + '\n')
        items.append(it)
    legacy_targets[f] = [i['slug'] for i in page_items[f]]

cats = [{'key': k, 'title': label} for k, label, _ in CATS]
json.dump({'categories': cats, 'personal': [f for f in D if is_personal(f)],
           'pageItems': legacy_targets, 'pageCategory': {f: cat_of(f) for f in D}},
          open(os.path.join(ROOT, 'scripts', 'item-map.json'), 'w'), indent=1)
c = collections.Counter(i['category'] for i in items)
st = collections.Counter(i['status'] for i in items)
print('items', len(items), dict(c), dict(st), 'with todo', sum(1 for i in items if i['todo']), 'unplaced photos', sum(unplaced.values()))
unc = [f for f in D if not cat_of(f) and f not in SITE and not is_personal(f)]
print('uncategorised pages', unc)
