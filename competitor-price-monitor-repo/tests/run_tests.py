"""离线自检(不联网、不需要真实数据): python tests/run_tests.py"""
import json, pathlib, sys, tempfile
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "app"))

def eq(got, want):
    assert got == want, f"期望 {want!r}，实际 {got!r}"; print("ok", want)

# ---------- 竞品周价格监控(离线) ----------
import competitors as C
import check_competitors as K
import browser as R

eq(C.norm_mem("8/256GB"), (8, 256)); eq(C.norm_mem("12+1T"), (12, 1024)); eq(C.norm_mem("4+128G"), (4, 128)); eq(C.norm_mem("abc"), None)
eq(C.parse_rrp("875?"), (875.0, True)); eq(C.parse_rrp("12991180"), (None, False)); eq(C.parse_rrp("0"), (None, False)); eq(C.parse_rrp("1499"), (1499.0, False))
eq(C.compare_text(1000, {"EURO": 1000.0, "OleOle": 1000.5}), "= RRP")
eq(C.compare_text(1000, {"EURO": 900.0, "OleOle": 1100.0}), "EURO -100 | OleOle +100")
eq(C.compare_text(None, {"EURO": 900.0}), "无RRP"); eq(C.compare_text(1000, {"EURO": "unavailable"}), "")
eq(C.verify("Smartfon SAMSUNG Galaxy A16 4/128GB Czarny", "Samsung", "A16 5G", "4+128", True)[0], True)
eq(C.verify("Samsung Galaxy S25 Ultra 12/256GB", "Samsung", "S25", "12+256", True)[0], False)      # 型号词不同: Ultra
eq(C.verify("Samsung Galaxy S25+ 12/256GB", "Samsung", "S25 Plus", "12+256", True)[0], True)
eq(C.verify("Samsung Galaxy A26 5G 6/128GB", "Samsung", "A26 5G", "8+128", False)[0], False)     # 内存不符

def page(name, price, avail="InStock"):
    ld = {"@type": "Product", "name": name, "offers": {"price": price, "priceCurrency": "PLN", "availability": "https://schema.org/" + avail}}
    return f'<html><head><script type="application/ld+json">{json.dumps(ld)}</script></head><body>{"x" * 40000}</body></html>'
def listing(items):
    ld = {"@type": "ItemList", "itemListElement": [{"item": {"name": n, "url": u, "offers": {"price": 1}}} for n, u in items]}
    return f'<html><script type="application/ld+json">{json.dumps(ld)}</script><body>{"x" * 40000}</body></html>'

it = {"key": "Samsung|A16 5G|4+128", "brand": "Samsung", "product": "A16 5G", "spec": "4+128", "rrp": 549.0,
      "euro": "https://www.euro.com.pl/telefony-komorkowe/samsung-a16.bhtml", "oleole": None}
K.CACHE_P = pathlib.Path(tempfile.mkdtemp()) / "cache.json"; cache = {}
pages = {"https://www.euro.com.pl/telefony-komorkowe/samsung-a16.bhtml": page("Samsung Galaxy A16 5G 4/128GB", 539.0)}
fetch = lambda site, url: pages[url] if url in pages else (_ for _ in ()).throw(R.Blocked("被重定向回首页: " + url))
r = K.lookup(None, "EURO", it, cache, fetch); eq(r[:3], ("price", 539.0, "available"))
# OleOle: 推导的同名链接不存在(被送回首页) -> 站内搜索 -> 找到并记住
prod = "https://www.oleole.pl/telefony-komorkowe/samsung-a16-oleole.bhtml"
pages["https://www.oleole.pl/search2.bhtml?keyword=Samsung%20A16%205G"] = listing([("Samsung Galaxy A16 5G 4/128GB", prod), ("Samsung Galaxy A16 5G 4/128GB LTE x", prod + "2")])
pages[prod] = page("Samsung Galaxy A16 5G 4/128GB", 549.0)
r = K.lookup(None, "OleOle", it, cache, fetch); eq(r[:3], ("price", 549.0, "available")); eq(cache[it["key"]]["OleOle"], prod)
# 你自己配的链接内存对不上 -> 如实报告
it2 = dict(it, key="Samsung|A26 5G|8+128", product="A26 5G", spec="8+128"); pages["https://www.euro.com.pl/telefony-komorkowe/samsung-a16.bhtml"] = page("Samsung Galaxy A26 5G 6/128GB", 999.0)
# 链接内存对不上 -> 自动重新搜索；搜到正确的就更新并记住，搜不到才如实报告
good = "https://www.euro.com.pl/telefony-komorkowe/samsung-a26-8-128.bhtml"
pages["https://www.euro.com.pl/search2.bhtml?keyword=Samsung%20A26%205G"] = listing([("Samsung Galaxy A26 5G 6/128GB", "https://x/6"), ("Samsung Galaxy A26 5G 8/128GB", good)])
pages[good] = page("Samsung Galaxy A26 5G 8/128GB", 999.0)
c2 = {}; r2 = K.lookup(None, "EURO", dict(it2, euro="https://www.euro.com.pl/telefony-komorkowe/samsung-a16.bhtml"), c2, fetch)
eq(r2[:3], ("price", 999.0, "available")); eq(c2[it2["key"]]["EURO"], good)
pages["https://www.euro.com.pl/search2.bhtml?keyword=Samsung%20A26%205G"] = listing([("Samsung Galaxy A26 5G 6/128GB", "https://x/6")])
eq(K.lookup(None, "EURO", dict(it2, euro="https://www.euro.com.pl/telefony-komorkowe/samsung-a16.bhtml"), {}, fetch)[0], "text")   # 搜不到 -> 报告不符
pages["https://www.euro.com.pl/telefony-komorkowe/samsung-a16.bhtml"] = page("Samsung Galaxy A16 5G 4/128GB", 539.0, "OutOfStock")
eq(K.lookup(None, "EURO", it, {}, fetch)[:3][2], "unavailable")

# 结果工作簿: 追加日期列、新增机型追加新行、同一天重复运行复用同一组列
import openpyxl
tmp = pathlib.Path(tempfile.mkdtemp()); tbl = tmp / "t.xlsx"
wb = openpyxl.Workbook(); ws = wb.active; ws.title = "竞品价格"
ws.append(["Brand", "product", "spec", "RRP", "x"]); ws.append(["Samsung", "A16 5G", "4+128", "549", "https://www.euro.com.pl/a.bhtml"]); ws.append(["Xiaomi", "N1", "16+512", "6799"]); ws.append(["Motorola", "G15", "8/128", "0"]); wb.save(tbl)
items, nm = C.read_table(tbl); eq((nm, len(items)), ("竞品价格", 2))
b = C.Book(tmp / "out.xlsx"); b.sync(items, {}); cols = b.date_cols("2026.10.30"); b.put(items[0]["_r"], cols["EURO"], 539.0, 549.0); b.save()
b2 = C.Book(tmp / "out.xlsx"); b2.sync(items, {}); eq(b2.date_cols("2026.10.30"), cols); eq(b2.date_cols("2026.11.06")["EURO"], cols["sum"] + 1)
eq(b2.date_cols("2026.10.30")["MEX"], cols["MEX"])
eq(b2.get(items[0]["_r"], cols["EURO"]), 539.0)
# 已下架页面(JSON-LD 价格 0 + 页面写"Produkt nie jest już dostępny") / Media Expert 搜索结果解析
ld0 = '<html><script type="application/ld+json">' + json.dumps({"@type": "Product", "name": "Samsung Galaxy A26 5G 8/256GB", "offers": {"price": 0, "priceCurrency": "PLN", "availability": "https://schema.org/InStock"}}) + '</script><body>Produkt nie jest już dostępny w naszym sklepie "prices":{"mainPrice":1317.33}' + "x" * 40000 + '</body></html>'
pages["https://www.euro.com.pl/telefony-komorkowe/disc.bhtml"] = ld0
itd = dict(it, key="Samsung|A26 5G|8+256", product="A26 5G", spec="8+256", euro="https://www.euro.com.pl/telefony-komorkowe/disc.bhtml")
eq(K.lookup(None, "EURO", itd, {}, fetch)[2], "discontinued")
mh = '<a href="/smartfony-i-zegarki/akcesoria-do-telefonow/szkla/szklo-do-motorola-g55">x</a><a href="https://www.mediaexpert.pl/smartfony-i-zegarki/smartfony/smartfon-motorola-moto-g55-5g-8-256gb-6-5-120hz-szary">y</a>'
eq(C.mex_items(mh)[0][0], "smartfon motorola moto g55 5g 8/256GB 6 5 120hz szary"); eq(len(C.mex_items(mh)), 1)
eq(C.verify(C.mex_items(mh)[0][0], "Motorola", "G55", "8+256", True)[0], True)
# 正常商品页里也有"Produkt nie jest już dostępny"模板文字: 价格>0 时不能判为下架
okp = page("Samsung Galaxy A36 5G 6/128GB", 1399.99).replace("<body>", '<body>"x":"Produkt nie jest już dostępny w naszym sklepie"')
pages["https://www.euro.com.pl/telefony-komorkowe/okp.bhtml"] = okp
ito = dict(it, key="Samsung|A36 5G|6+128", product="A36 5G", spec="6+128", euro="https://www.euro.com.pl/telefony-komorkowe/okp.bhtml")
eq(K.lookup(None, "EURO", ito, {}, fetch)[1:3], (1399.99, "available"))
eq(C.verify("Smartfon Honor Magic7 Lite 5G 8/256GB 6,78\" 108Mpix Czarny", "Honor", "Magic 7 lite", "8+256", True)[0], True)
eq(C.verify("Smartfon Honor Magic7 Pro 5G 12/512GB", "Honor", "Magic 7 lite", "12+512", True)[0], False)
eq(C.verify("Samsung Galaxy S25 Ultra 12/256GB", "Samsung", "S25", "12+256", True)[0], False)
eq(C.summary_text({"EURO": 300, "OleOle": 400, "MEX": 566}), "300/400/566")
eq(C.summary_text({"EURO": 200, "OleOle": "unavailable", "MEX": 300}), "200/300")
eq(C.summary_text({"EURO": "无链接", "OleOle": "无链接", "MEX": "无链接"}), "无链接")
eq(C.summary_text({"EURO": 1399.99, "OleOle": "unavailable online", "MEX": None}), "1399.99")
eq(C.summary_text({"EURO": 799, "OleOle": 799, "MEX": 799}), "799")
eq(C.summary_text({"EURO": 799, "OleOle": 799.0, "MEX": 849}), "799/849")
eq(C.summary_text({"EURO": "链接商品与表不符: x", "OleOle": "discontinued", "MEX": "unavailable online"}), "unavailable")
eq(C.summary_text({"EURO": "unavailable", "OleOle": "待续", "MEX": "无链接"}), "待续")
import pathlib as _pl
_root = _pl.Path(__file__).resolve().parent.parent
eq((_root / "skills/competitor-price-operator/SKILL.md").read_text(encoding="utf-8"), (_root / ".agents/skills/competitor-price-operator/SKILL.md").read_text(encoding="utf-8"))
eq((_root / "AGENTS.md").exists(), True)
print("竞品监控测试通过")
