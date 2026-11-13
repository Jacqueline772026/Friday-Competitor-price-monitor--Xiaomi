"""竞品价格监控: EURO + OleOle 现价 vs 你竞品表里的 RRP。结果追加到结果工作簿(每周一组带日期的列)，不改动你的原表。
前提: 专用 Chrome 已打开(run.py 会自动打开)。
用法: python app/check_competitors.py 竞品表.xlsm [--sheet 竞品价格] [--euro-col E] [--oleole-col G]
        [--mex-col F] [--rows 2-30] [--resume] [--sites EURO,OleOle,MEX] [--max-pages EURO=50,OleOle=40,MEX=40] [--date 2026-10-30]
链接来源(优先级): 你表里的链接 > config/competitor_links.json(上次自动找到并核对过的) > OleOle 用 EURO 同名链接推导 > 站内搜索。
每个网站每次运行有页数上限(默认 EURO 50 / OleOle 40)，到上限的格子写"待续"，几小时后用 --resume 继续，避免被拦截。"""
from openpyxl.styles import Alignment
import argparse, datetime as dt, pathlib, re, sys, time
from urllib.parse import quote
import competitors as C
import retail
from playwright.sync_api import sync_playwright

import paths
import browser as R

OUT_DEFAULT, CACHE_P, TABLE_DEFAULT = paths.LOG_XLSX, paths.CACHE, paths.find_table()
STATUS_P = CACHE_P.with_name("competitor_status.json")   # 记住"确认没有该型号/已下架/不查"，下次不再浪费页数
SITES = R.SITES

class Budget(Exception): pass

def is_search(u): return "search" in (u or "").lower()

def search_url(site, it):
    kw = quote(it["brand"] + " " + it["product"])
    return f"{SITES[site]}search?query[menu_item]=&query[querystring]={kw}" if site == "MEX" else f"{SITES[site]}search2.bhtml?keyword={kw}"

SEARCH_MISSING = False   # 默认不为"没有链接"的格子去站内搜索(省页数)；加 --search-missing 才搜
LINK_ALERTS = []      # 本次运行里"表里/缓存里的链接和型号对不上"的记录，运行结束时列出

def lookup(page, site, it, cache, fetch):
    """-> ('price', 价格, 状态, 网址) 或 ('text', 文字)。
    自查流程: 缓存里核对过的链接 > 你表里的链接 > (OleOle)用 EURO 同名链接推导 > 站内搜索。
    表里的链接和型号/内存对不上时，不是直接报错，而是重新搜索，搜到并核对一致就更新(并记住)，搜不到才如实报告。"""
    origin, key = SITES[site], it["key"]
    own = {"EURO": it["euro"], "OleOle": it["oleole"], "MEX": it.get("mex")}[site]
    cached = cache.get(key, {}).get(site)
    url, derived, mismatch = cached or own, False, None
    if url is None and site == "OleOle" and it["euro"] and not is_search(it["euro"]):
        url, derived = it["euro"].replace("euro.com.pl", "oleole.pl"), True       # EURO 与 OleOle 同一集团，商品链接常常只差域名
    if not SEARCH_MISSING and not (url and not is_search(url)) and not (url and is_search(url)):
        return ("text", "无链接")        # 这个渠道表里没有链接、也推不出来 -> 先不查，运行结束后在清单里汇报，由用户决定查不查
    if url and not is_search(url):
        try:
            html = fetch(site, url); info = retail.product_info(html)
        except R.Blocked as b:
            if derived and "重定向回首页" in str(b): info = None if SEARCH_MISSING else False     # 推导的链接不存在(被送回首页)，不算拦截；默认不搜索，直接记无链接
            else: raise
        if info is False: return ("text", "无链接")
        if info:
            ok, why = C.verify(info["name"], it["brand"], it["product"], it["spec"], derived)
            if ok and retail.is_outlet(info["name"], url): ok, why = False, "Outlet/翻新/展示机商品，不计"
            if ok: return finish(site, it, cache, url, html, info, derived)
            mismatch = f"链接商品与表不符: {why}"                         # 链接对不上 -> 下面重新搜索
            LINK_ALERTS.append((it, site, url, why))
    # 站内搜索(严格核对型号+内存)
    surl = url if (url and is_search(url)) else search_url(site, it)
    html = fetch(site, surl); items = C.mex_items(html) if site == "MEX" else retail.listing_items(html)
    cands = [u for n, u, _ in items if C.verify(n, it["brand"], it["product"], it["spec"], True)[0] and C.norm_mem(n) and not retail.is_outlet(n, u)]
    if not cands:
        if not items and len(html) < 30000 and site != "MEX": raise R.Blocked("搜索页只有很小的页面(疑似拦截页): " + surl)
        confirmed = len(items) > 0            # 搜索页确实返回了别的商品、但没有这一款 -> 才记住；0 个结果(断网/页面没加载好)不记，下次重新搜
        return ("text", f"{mismatch}；已重新搜索，该渠道没有这个内存/型号" if mismatch else f"搜索结果里没有找到该型号/内存 [共{len(items)}个结果]", confirmed)
    new = cands[0] if cands[0].startswith("http") else origin.rstrip("/") + cands[0]
    html = fetch(site, new); info = retail.product_info(html)
    if not info: return ("text", mismatch or "页面无价格数据")
    ok, why = C.verify(info["name"], it["brand"], it["product"], it["spec"], True)
    return finish(site, it, cache, new, html, info, True) if ok else ("text", mismatch or f"链接商品与表不符: {why}")

def mex_state(html):
    """Media Expert 页面里: 写着"Produkt chwilowo niedostępny"(暂时无货)或卖家不是 Media Expert 自营(第三方 Marketplace) -> 该渠道视为 unavailable。
    无货商品的结构化数据里常残留旧价格(例如 Razr 60 Ultra 5699.99)，第三方卖家价格(例如 MellaShop 7441)也不是 Media Expert 的价格。"""
    t = re.sub(r"<script[\s\S]*?</script>|<style[\s\S]*?</style>", " ", html)
    t = re.sub(r"\s+", " ", re.sub(r"<[^>]+>|&nbsp;", " ", t))
    if re.search(r"chwilowo niedostępny", t, re.I): return "unavailable"
    m = re.search(r"Sprzedawca:\s*(.+?)\s+(?:Opis i dane|Akcesoria|POMIŃ|DO KOSZYKA)", t)
    if m and "media expert" not in m.group(1).lower(): return "unavailable"
    return None

def finish(site, it, cache, url, html, info, remember):
    slug = url.split("?")[0].rsplit("/", 1)[-1].replace(".bhtml", "")
    st = retail.delivery_status(html, info.get("availability", ""), slug)
    if remember:
        cache.setdefault(it["key"], {})[site] = url; C.save_cache(CACHE_P, cache)
    if site == "MEX" and mex_state(html): st = "unavailable"          # 无货/第三方卖家: 不计页面上残留的价格
    price = round(float(info["price"]), 2) if info.get("price") is not None else None
    mp = re.search(r'"prices":\{"mainPrice":([\d.]+)', html)
    if not price and "nie jest już dostępny" in html:     # 只有价格为 0/空 且页面有这句话才算下架(这句话在每个页面的模板里都有，不能单独作为依据)
        return ("price", float(mp.group(1)) if mp else None, "discontinued", url)      # 页面写着"产品已不再销售"，JSON-LD 价格常为 0
    if not price and mp and float(mp.group(1)) > 0: price = round(float(mp.group(1)), 2)   # JSON-LD 没价格时用页面自带价格
    if not price: return ("price", None, "no_price", url)
    return ("price", price, st, url)

MANUAL_BAD = ("无链接", C.NOLIST_TEXT)
HOME = {"EURO": "https://www.euro.com.pl/", "OleOle": "https://www.oleole.pl/", "MEX": "https://www.mediaexpert.pl/"}

def manual_keywords(it):
    """手动查询用的关键词: 品牌+型号(短)、品牌+型号+内存(波兰站常见写法 8/256GB)。"""
    base = f"{it['brand']} {it['product']}".strip()
    m = re.match(r"\s*(\d+)\s*\+\s*(\d+)", str(it.get("spec") or ""))
    mem = f"{m.group(1)}/{m.group(2)}GB" if m else str(it.get("spec") or "")
    return base, f"{base} {mem}".strip()

def manual_lookup(items, book, cols, sites, out_path):
    """列出程序没找到链接的格子，给出官网首页、站内搜索网址和关键词，方便手动查；写成 markdown 文件并打印条数。"""
    rows = []
    for it in items:
        for s in sites:
            v = book.get(it["_r"], cols[s])
            if isinstance(v, str) and (v in MANUAL_BAD or v.startswith(("链接商品", "搜索结果", "页面无价格"))):
                k1, k2 = manual_keywords(it)
                rows.append((it, s, v, k1, k2))
    lines = ["# 需手动查询清单", "", "程序没能自动找到下面这些款式在对应网站的链接。请按\"搜索网址\"打开站内搜索，核对型号和内存(RAM+存储)后，把商品页链接填回竞品价格表的 EURO / MEDIA EXPERT 列；确实没有这款就保持现状或标记不查。", "",
             "| 行 | 品牌 型号 内存 | 网站 | 程序结果 | 关键词(短) | 关键词(带内存) | 官网首页 | 站内搜索网址 |", "|---|---|---|---|---|---|---|---|"]
    for it, s, v, k1, k2 in rows:
        lines.append(f"| {it['row']} | {it['brand']} {it['product']} {it['spec']} | {s} | {v} | {k1} | {k2} | {HOME[s]} | {search_url(s, {'brand': it['brand'], 'product': it['product'] + (' ' + k2.split(' ')[-1] if False else '')})} |")
    if not rows: lines.append("| - | 本次没有需要手动查询的款式 | | | | | | |")
    pathlib.Path(out_path).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return len(rows)

def main():
    R.DELAY = (15.0, 25.0)   # 竞品周检放慢，降低被拦概率
    if hasattr(sys.stdout, "reconfigure"): sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(); ap.add_argument("table", nargs="?", default=str(TABLE_DEFAULT)); ap.add_argument("--sheet"); ap.add_argument("--euro-col", default="E")
    ap.add_argument("--oleole-col"); ap.add_argument("--mex-col", default="F"); ap.add_argument("--rows"); ap.add_argument("--resume", action="store_true"); ap.add_argument("--overwrite", action="store_true"); ap.add_argument("--search-missing", action="store_true", help="也为表里没有链接的格子去站内搜索(默认不搜)"); ap.add_argument("--sites", default="EURO,OleOle,MEX")
    ap.add_argument("--max-pages", default="EURO=50,OleOle=40,MEX=40"); ap.add_argument("--date"); ap.add_argument("--out", default=str(OUT_DEFAULT)); a = ap.parse_args()
    global SEARCH_MISSING; SEARCH_MISSING = a.search_missing
    table, out = pathlib.Path(a.table), pathlib.Path(a.out)
    if not table.exists(): sys.exit(f"找不到竞品表 {table}。请把竞品价格表放到项目文件夹(或用参数指定路径)。")
    if (out.parent / f"~${out.name}").exists(): sys.exit(f"{out.name} 正在被 Excel 打开。请先关闭 Excel(提示保存时选\"不保存\")，再重新运行。")
    day = dt.date.fromisoformat(a.date) if a.date else dt.date.today(); label = day.strftime("%Y.%m.%d")
    if a.resume and not a.date and out.exists():            # 补漏默认接着"最近一列"，不会因为换了一天就新开一列、把整张表重读一遍
        try:
            import openpyxl as _ox
            _ws = _ox.load_workbook(out, read_only=True).worksheets[0]; _ws.reset_dimensions()
            _labels = sorted({str(c.value).split()[-1] for c in next(_ws.iter_rows(min_row=1, max_row=1)) if c.value and re.fullmatch(r"EURO \d{4}\.\d{2}\.\d{2}", str(c.value))})
            if _labels and _labels[-1] != label: label = _labels[-1]; day = dt.date.fromisoformat(label.replace(".", "-")); print(f"提示: 补漏接着最近一列 {label}(不新开今天的列)。")
        except Exception: pass
    if not a.date and day.weekday() in (2, 3): day = day + dt.timedelta(days=4 - day.weekday()); label = day.strftime("%Y.%m.%d"); print(f"提示: 今天是周三/周四，提前开跑，结果按本周五的日期 {label} 记录(补漏同样记在这一列)。")
    if day.weekday() != 4 and not (not a.date and dt.date.today().weekday() in (2, 3)): print(f"提示: {label} 不是周五(周五才是正式的每周检查)，照常运行。")
    sites = [s for s in a.sites.split(",") if s in SITES]
    budget = {k: int(v) for k, v in (x.split("=") for x in a.max_pages.split(","))}
    items, sname = C.read_table(table, a.sheet, a.euro_col, a.oleole_col, a.mex_col)
    if a.rows:
        lo, hi = (int(x) for x in a.rows.split("-")) if "-" in a.rows else (int(a.rows),) * 2
        items = [i for i in items if lo <= i["row"] <= hi]
    cache = C.load_cache(CACHE_P); status = C.load_cache(STATUS_P); book = C.Book(out); book.sync(items, cache); cols = book.date_cols(label, tuple(sites))
    print(f"竞品表: {table.name} [{sname}] 共 {len(items)} 款 | 检查日期 {label} | 结果: {out.name}")
    if not a.resume and not a.overwrite and any(book.get(it["_r"], cols[s]) not in (None, "") for it in items for s in sites):
        sys.exit(f"[{label}] 这一列已经有结果了。要接着补没读到的，请用「竞品补漏」(resume)；确实要整列重来才加 --overwrite。(防止把已读到的价格覆盖掉)")
    used = {s: 0 for s in SITES}; streak = {s: 0 for s in SITES}; stopped = {}; stat = {}
    own_link = lambda it, site: {"EURO": it["euro"], "OleOle": it["oleole"], "MEX": it.get("mex")}[site] or ""
    def remember(it, site, state, url=None):
        status.setdefault(it["key"], {})[site] = {"state": state, "date": str(day), "link": own_link(it, site)}; C.save_cache(STATUS_P, status)
    def fetch(site, url):
        if used[site] >= budget.get(site, 999): raise Budget(site)
        used[site] += 1
        try: return R.fetch(page, url)
        except R.Blocked: raise
        except Exception as ex:                                  # 网络抖动(ERR_HTTP2_PROTOCOL_ERROR 等)等 20 秒重试一次
            if "net::ERR" not in str(ex) and "Navigation to" not in str(ex): raise
            time.sleep(20); used[site] += 1; return R.fetch(page, url)
    with sync_playwright() as p:
        try: page = p.chromium.connect_over_cdp("http://localhost:9222").contexts[0].new_page()
        except Exception: sys.exit("连不上专用 Chrome。请先打开专用 Chrome(不要关)，再运行。")
        try:
            for it in items:
                r = it["_r"]
                for site in sites:
                    c = cols[site]; cur = book.get(r, c)
                    if a.resume and cur not in (None, "") and ((isinstance(cur, (int, float)) and cur > 0) or str(cur) in C.DONE_TEXT): continue
                    stt = status.get(it["key"], {})
                    if stt.get("*", {}).get("state") == "skip": txt = C.SKIP_TEXT; num = None                      # 用户/agent 标了"不查"(停售老款)
                    elif C.status_fresh(stt.get(site), own_link(it, site), day): txt = "discontinued" if stt[site]["state"] == "discontinued" else C.NOLIST_TEXT; num = None   # 28 天内确认过，不再读页面
                    elif not (it["euro"] or it["oleole"] or it.get("mex") or cache.get(it["key"])): txt = "无链接"; num = None       # 表里一个链接都没有的款式不去搜索
                    elif site in stopped: txt = "待续"; num = None
                    else:
                        num = None
                        try:
                            res = lookup(page, site, it, cache, fetch); streak[site] = 0
                            if res[0] == "price":
                                _, price, st, url = res
                                if st in ("unavailable", "unavailable online", "discontinued"): txt = st; note = f"页面价格 {price}" if price else None
                                if st == "discontinued": remember(it, site, "discontinued")
                                elif st == "no_price": txt, note = "页面无价格数据", None
                                else: txt, num, note = price, price, None
                                if txt is None: txt = "页面无价格数据"
                            else:
                                txt, note = res[1], None
                                if len(res) > 2 and res[2]: note, txt = txt, C.NOLIST_TEXT; remember(it, site, "no_listing")   # 原因放批注，格子写"无此型号(已确认)"
                        except Budget:
                            stopped[site] = "页数上限"; txt, note = "待续", None
                            print(f"-- {site} 本次已读 {used[site]} 页，到达上限，剩下的标\"待续\"。请过几个小时用 resume 继续。")
                        except R.Blocked:
                            streak[site] += 1; txt, note = "被网站拦截", None
                            if streak[site] >= 2: stopped[site] = "被拦截"; print(f"!! {site} 连续 2 次被拦截，本次不再访问，剩下的标\"待续\"。请几个小时后再 resume。")
                        except Exception as ex:
                            if type(ex).__name__ == "TargetClosedError" or "has been closed" in str(ex): book.save(); sys.exit("专用 Chrome 被关闭或崩溃了，已保存已读到的结果。请重新打开专用 Chrome 后用 resume 继续。")
                            txt, note = f"读取失败({type(ex).__name__}: {str(ex)[:40]})", None
                        else: pass
                        book.put(r, c, txt, it["rrp"] if isinstance(txt, (int, float)) else None, note)
                        stat.setdefault(site, []).append(txt); print(f"行{it['row']} {site:6} {it['brand']} {it['product']} {it['spec']}: {txt}" + (f"  (RRP {it['rrp']:g})" if isinstance(txt, (int, float)) and it["rrp"] else "")); continue
                    book.put(r, c, txt); stat.setdefault(site, []).append(txt)
                    if txt not in ("无链接", "待续", C.SKIP_TEXT): print(f"行{it['row']} {site:6} {txt}")
                prices = {s: book.get(r, cols[s]) for s in sites}
                book.put(r, cols["cmp"], C.compare_text(it["rrp"], prices))
                sc = book.ws.cell(r, cols["sum"], C.summary_text(prices)); sc.alignment = Alignment(horizontal="left")
                book.save()
        finally: page.close()
    book.sync(items, cache); book.save()          # 把这次自动找到的链接也写回结果表的链接列
    # ---- 运行结束后的"待核对清单"(自动提示) ----
    n_manual = manual_lookup(items, book, cols, sites, out.with_name("需手动查询清单.md"))
    if n_manual: print(f"\n【需手动查询】有 {n_manual} 个格子程序没找到链接，已写入 {out.with_name('需手动查询清单.md').name}(含官网搜索网址和关键词)。")
    if LINK_ALERTS:
        print("\n【链接疑似写错】下面这些链接的商品和表里的型号/内存对不上(程序已重新搜索，请确认新链接是否正确):")
        for it, site, url, why in LINK_ALERTS: print(f"  行{it['row']} {site} {it['brand']} {it['product']} {it['spec']}: {why}  | 原链接 {url}")
    odd = []
    for it in items:
        pr = {s: book.get(it["_r"], cols[s]) for s in sites}; nums = {s: float(v) for s, v in pr.items() if isinstance(v, (int, float)) and v > 0}
        why = []
        if len(nums) >= 2 and max(nums.values()) / min(nums.values()) > 2: why.append("站间差超过2倍 " + "/".join(f"{s}{v:g}" for s, v in nums.items()))
        if it["rrp"]:
            for s, v in nums.items():
                if v / it["rrp"] < 0.5 or v / it["rrp"] > 1.5: why.append(f"{s} {v:g} 与 RRP {it['rrp']:g} 相差过大(RRP 可能过时/填错，或页面读错)")
        if why: odd.append((it, why))
    if odd:
        print("\n【价格异常待核对】请在浏览器里打开链接确认(也可能是真实清仓/促销):")
        for it, why in odd: print(f"  行{it['row']} {it['brand']} {it['product']} {it['spec']}: " + "；".join(why))
    print(f"\n完成，已写入 {out.name} 的 [{label}] 各列。统计:")
    for s in sites:
        v = stat.get(s, []); n = lambda f: sum(1 for x in v if f(x))
        print(f"  {s}: 有价格 {n(lambda x: isinstance(x, (int, float)))} | 缺货 {n(lambda x: str(x).startswith('unavailable'))} | 待续 {n(lambda x: x == '待续')} | 拦截 {n(lambda x: x == '被网站拦截')} | 无链接 {n(lambda x: x == '无链接')} | 其他异常 {n(lambda x: isinstance(x, str) and x.startswith(('链接商品', '搜索结果', '页面无价格', '读取失败')))}")
    if stopped or any(x == "待续" for v in stat.values() for x in v): print("还有\"待续\"的格子: 过几个小时再运行 resume(只读没读到的)。")

if __name__ == "__main__": main()
