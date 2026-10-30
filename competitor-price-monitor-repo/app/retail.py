"""EURO / OleOle(同一套平台)商品页解析：当前页价格 + 页面内嵌的所有变体(颜色/内存)链接。"""
import json, re
VAR = re.compile(r'\{"variantValue":"([^"]+)","currentProduct":(true|false),"colorCodes":(?:null|\[[^\]]*\]),'
                 r'"identifiers":\[\{"plu":"(\d+)","productLinkName":"([^"]+)","productGroupLinkName":"([^"]+)"')

def variants(html):
    """返回 [(variantValue, is_current, plu, linkname, group)]，去重"""
    seen, out = set(), []
    for v, cur, plu, link, grp in VAR.findall(html):
        if (v, plu) in seen: continue
        seen.add((v, plu)); out.append((v, cur == "true", plu, link, grp))
    return out

def color_variants(html):
    """同一内存下不同颜色的变体(排除 '256 GB' 这类内存变体)"""
    return [x for x in variants(html) if not re.fullmatch(r"\d+\s*(GB|TB)", x[0], re.I)]

def product_info(html):
    """当前页的 名称 / 价格 / 币种 / 有效期 / 库存(JSON-LD Product)"""
    for m in re.finditer(r'<script[^>]*application/ld\+json[^>]*>(.*?)</script>', html, re.S):
        try: d = json.loads(m.group(1))
        except Exception: continue
        for x in (d if isinstance(d, list) else [d]):
            if isinstance(x, dict) and str(x.get("@type", "")).endswith("Product"):
                o = x.get("offers") or {}
                o = o[0] if isinstance(o, list) and o else o
                if o.get("price") is not None:
                    return {"name": x.get("name"), "price": o.get("price"), "currency": o.get("priceCurrency"),
                            "valid_until": o.get("priceValidUntil"), "availability": (o.get("availability") or "").split("/")[-1]}
    # 兜底: 结构化数据里没有价格(常见于缺货商品)时，读页面自带的 prices.mainPrice 和 og:title
    from html import unescape
    mp = re.search(r'"prices":\{"mainPrice":([\d.]+)', html)
    t = re.search(r'<meta property="og:title" content="([^"]+)"', html)
    if mp and t:
        return {"name": unescape(t.group(1)), "price": float(mp.group(1)), "currency": "PLN", "valid_until": None, "availability": ""}
    return None

GROUP = re.compile(r'"variantGroupName":"([^"]+)","variants":\[')

def color_group(html, current_slug):
    """取'当前商品所在的 Kolor(颜色)组'(页面里还混着推荐商品的变体)。返回 [(颜色, linkname, productGroup)]"""
    heads = [(m.start(), m.end(), m.group(1)) for m in GROUP.finditer(html)]
    allv = list(VAR.finditer(html))
    for i, (st, en, name) in enumerate(heads):
        if name.lower() not in ("kolor", "color"): continue
        lim = heads[i + 1][0] if i + 1 < len(heads) else len(html)
        grp, last = [], en
        for m in allv:
            if m.start() < en or m.start() >= lim: continue
            if m.start() - last > 200: break
            grp.append((m.group(1), m.group(2) == "true", m.group(4), m.group(5))); last = m.end()
        if any(cur and link == current_slug for _, cur, link, _ in grp):
            return [(v, link, g) for v, _, link, g in grp]
    return []

COLORS = {"czarny": "Black", "zielony": "Green", "niebieski": "Blue", "biały": "White", "bialy": "White", "szary": "Gray",
          "fioletowy": "Violet", "różowy": "Pink", "rozowy": "Pink", "błękitny": "Ice Blue", "zloty": "Gold", "złoty": "Gold",
          "srebrny": "Silver", "pomarańczowy": "Orange", "granatowy": "Navy", "tytanowy": "Titanium", "jasnoniebieski": "Light Blue",
          "ciemnoniebieski": "Dark Blue", "ciemnozielony": "Dark Green", "purpurowy": "Purple", "biało-pomarańczowy": "White-Orange", "bialo-pomaranczowy": "White-Orange"}
def color_en(c): return COLORS.get(c.lower(), c)

_BAD = ("UNAVAILABLE", "UNDEFINED")          # 配送代码里表示'没有'的词(含 TEMPORARILY_UNAVAILABLE)

def _obj(h, start):
    i = h.index("{", start); d = 0
    for j in range(i, len(h)):
        d += (h[j] == "{") - (h[j] == "}")
        if d == 0: return json.loads(h[i:j + 1])

def color_variants(html):
    """页面里的 variantDetails -> 颜色组: [(颜色, 商品链接名, 分类名, 相对当前页面的差价, 是否可买, 是否当前页)]；没有就返回 []。
    差价 = 该颜色价格 - 当前页面价格；available=false 即页面上显示"不可用"。一个页面就能得到全部颜色，不必逐个打开。"""
    i = html.find('"variantDetails"')
    if i < 0: return []
    try: d = _obj(html, html.index("{", i + len('"variantDetails"')))
    except Exception: return []
    out = []
    for g in d.get("variantGroups") or []:
        if g.get("variantGroupName") != "Kolor": continue
        for v in g.get("variants") or []:
            sub = (v.get("variants") or [{}])[0]; ident = sub.get("identifiers") or {}
            if not ident.get("productLinkName"): return []
            out.append((v.get("variantValue", ""), ident["productLinkName"], ident.get("productGroupLinkName"),
                        float(sub.get("productWariantPriceDifference") or 0), bool(sub.get("available")), bool(v.get("currentProduct"))))
    return out

def delivery_status(html, ld_avail="", slug=None):
    """-> 'available' / 'unavailable online'(只能店里买或无法配送) / 'unavailable'(店里也没有且无法配送) / 'unknown'
    依据页面里第一个 deliveryAvailability(=当前商品；后面的是推荐商品) + 结构化数据里的 availability"""
    ld = (ld_avail or "").split("/")[-1]
    m = re.search(r'"deliveryAvailability":', html)
    d = None
    if m:
        try: d = _obj(html, m.end())
        except Exception: d = None
    # 页面「变体」数据里每个商品都有 "available":true/false(页面上显示"不可用"就是读它)；当前商品为 false 视为网上不可买
    var_unavail = False
    if slug:
        flags = re.findall(r'"available":(true|false),"identifiers":\{"plu":"\d+","productLinkName":"' + re.escape(slug) + '"', html)
        var_unavail = "false" in flags
    ok = lambda x: bool(x) and not any(b in str(x.get("code", "")).upper() for b in _BAD)
    if d:
        online = ok(d.get("homeDeliveryAvailability")) or ok(d.get("pickUpPointDeliveryAvailability")) or ok(d.get("commonDeliveryAvailability"))
        store = ok(d.get("shopDeliveryAvailability")) or bool(d.get("shopsOnlyAvailable")) or bool(d.get("reserveAndCollectAvailable"))
        if ld == "InStoreOnly": online, store = False, True
        if ld in ("OutOfStock", "SoldOut", "Discontinued") or var_unavail: online = False
    elif ld in ("InStock", "OnlineOnly", "LimitedAvailability", "PreOrder", "BackOrder"): return "available"
    elif ld == "InStoreOnly": return "unavailable online"
    elif ld in ("OutOfStock", "SoldOut", "Discontinued"): return "unavailable"
    else: return "unknown"
    return "available" if online else ("unavailable online" if store else "unavailable")

def listing_items(html):
    """搜索结果页里的商品列表(JSON-LD ItemList) -> [(名称, 链接, 价格)]"""
    out = []
    for m in re.finditer(r'<script[^>]*application/ld\+json[^>]*>(.*?)</script>', html, re.S):
        try: d = json.loads(m.group(1))
        except Exception: continue
        for x in (d if isinstance(d, list) else [d]):
            if isinstance(x, dict) and x.get("@type") == "ItemList":
                for e in x.get("itemListElement", []):
                    it = e.get("item", e) if isinstance(e, dict) else {}
                    o = it.get("offers") or {}
                    o = o[0] if isinstance(o, list) and o else o
                    if it.get("name") and it.get("url"): out.append((it["name"], it["url"], o.get("price")))
    return out
