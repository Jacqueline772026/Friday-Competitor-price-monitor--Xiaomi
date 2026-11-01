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
SITES = R.SITES

class Budget(Exception): pass

def is_search(u): return "search" in (u or "").lower()

def search_url(site, it):
    kw = quote(it["brand"] + " " + it["product"])
    return f"{SITES[site]}search?query[menu_item]=&query[querystring]={kw}" if site == "MEX" else f"{SITES[site]}search2.bhtml?keyword={kw}"

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
    if url and not is_search(url):
        try:
            html = fetch(site, url); info = retail.product_info(html)
        except R.Blocked as b:
            if derived and "重定向回首页" in str(b): info = None          # 推导的链接不存在(被送回首页)，不算拦截，改用搜索
            else: raise
        if info:
            ok, why = C.verify(info["name"], it["brand"], it["product"], it["spec"], derived)
            if ok: return finish(site, it, cache, url, html, info, derived)
            mismatch = f"链接商品与表不符: {why}"                         # 链接对不上 -> 下面重新搜索
    # 站内搜索(严格核对型号+内存)
    surl = url if (url and is_search(url)) else search_url(site, it)
    html = fetch(site, surl); items = C.mex_items(html) if site == "MEX" else retail.listing_items(html)
    cands = [u for n, u, _ in items if C.verify(n, it["brand"], it["product"], it["spec"], True)[0] and C.norm_mem(n)]
    if not cands:
        if not items and len(html) < 30000 and site != "MEX": raise R.Blocked("搜索页只有很小的页面(疑似拦截页): " + surl)
        return ("text", f"{mismatch}；已重新搜索，该渠道没有这个内存/型号" if mismatch else f"搜索结果里没有找到该型号/内存 [共{len(items)}个结果]")
    new = cands[0] if cands[0].startswith("http") else origin.rstrip("/") + cands[0]
    html = fetch(site, new); info = retail.product_info(html)
    if not info: return ("text", mismatch or "页面无价格数据")
    ok, why = C.verify(info["name"], it["brand"], it["product"], it["spec"], True)
    return finish(site, it, cache, new, html, info, True) if ok else ("text", mismatch or f"链接商品与表不符: {why}")

def finish(site, it, cache, url, html, info, remember):
    slug = url.split("?")[0].rsplit("/", 1)[-1].replace(".bhtml", "")
    st = retail.delivery_status(html, info.get("availability", ""), slug)
    if remember:
        cache.setdefault(it["key"], {})[site] = url; C.save_cache(CACHE_P, cache)
    price = round(float(info["price"]), 2) if info.get("price") is not None else None
    mp = re.search(r'"prices":\{"mainPrice":([\d.]+)', html)
    if not price and "nie jest już dostępny" in html:     # 只有价格为 0/空 且页面有这句话才算下架(这句话在每个页面的模板里都有，不能单独作为依据)
        return ("price", float(mp.group(1)) if mp else None, "discontinued", url)      # 页面写着"产品已不再销售"，JSON-LD 价格常为 0
    if not price and mp and float(mp.group(1)) > 0: price = round(float(mp.group(1)), 2)   # JSON-LD 没价格时用页面自带价格
    if not price: return ("price", None, "no_price", url)
    return ("price", price, st, url)

def main():
    if hasattr(sys.stdout, "reconfigure"): sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(); ap.add_argument("table", nargs="?", default=str(TABLE_DEFAULT)); ap.add_argument("--sheet"); ap.add_argument("--euro-col", default="E")
    ap.add_argument("--oleole-col"); ap.add_argument("--mex-col", default="F"); ap.add_argument("--rows"); ap.add_argument("--resume", action="store_true"); ap.add_argument("--sites", default="EURO,OleOle,MEX")
    ap.add_argument("--max-pages", default="EURO=50,OleOle=40,MEX=40"); ap.add_argument("--date"); ap.add_argument("--out", default=str(OUT_DEFAULT)); a = ap.parse_args()
    table, out = pathlib.Path(a.table), pathlib.Path(a.out)
    if not table.exists(): sys.exit(f"找不到竞品表 {table}。请把竞品价格表放到项目文件夹(或用参数指定路径)。")
    if (out.parent / f"~${out.name}").exists(): sys.exit(f"{out.name} 正在被 Excel 打开。请先关闭 Excel(提示保存时选\"不保存\")，再重新运行。")
    day = dt.date.fromisoformat(a.date) if a.date else dt.date.today(); label = day.strftime("%Y.%m.%d")
    if day.weekday() != 4: print(f"提示: {label} 不是周五(周五才是正式的每周检查)，照常运行。")
    sites = [s for s in a.sites.split(",") if s in SITES]
    budget = {k: int(v) for k, v in (x.split("=") for x in a.max_pages.split(","))}
    items, sname = C.read_table(table, a.sheet, a.euro_col, a.oleole_col, a.mex_col)
    if a.rows:
        lo, hi = (int(x) for x in a.rows.split("-")) if "-" in a.rows else (int(a.rows),) * 2
        items = [i for i in items if lo <= i["row"] <= hi]
    cache = C.load_cache(CACHE_P); book = C.Book(out); book.sync(items, cache); cols = book.date_cols(label, tuple(sites))
    print(f"竞品表: {table.name} [{sname}] 共 {len(items)} 款 | 检查日期 {label} | 结果: {out.name}")
    used = {s: 0 for s in SITES}; streak = {s: 0 for s in SITES}; stopped = {}; stat = {}
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
                    if not (it["euro"] or it["oleole"] or it.get("mex") or cache.get(it["key"])): txt = "无链接"; num = None       # 表里一个链接都没有的款式不去搜索
                    elif site in stopped: txt = "待续"; num = None
                    else:
                        num = None
                        try:
                            res = lookup(page, site, it, cache, fetch); streak[site] = 0
                            if res[0] == "price":
                                _, price, st, url = res
                                if st in ("unavailable", "unavailable online", "discontinued"): txt = st; note = f"页面价格 {price}" if price else None
                                elif st == "no_price": txt, note = "页面无价格数据", None
                                else: txt, num, note = price, price, None
                                if txt is None: txt = "页面无价格数据"
                            else: txt, note = res[1], None
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
                    if txt != "无链接" and txt != "待续": print(f"行{it['row']} {site:6} {txt}")
                prices = {s: book.get(r, cols[s]) for s in sites}
                book.put(r, cols["cmp"], C.compare_text(it["rrp"], prices))
                sc = book.ws.cell(r, cols["sum"], C.summary_text(prices)); sc.alignment = Alignment(horizontal="left")
                book.save()
        finally: page.close()
    book.sync(items, cache); book.save()          # 把这次自动找到的链接也写回结果表的链接列
    print(f"\n完成，已写入 {out.name} 的 [{label}] 各列。统计:")
    for s in sites:
        v = stat.get(s, []); n = lambda f: sum(1 for x in v if f(x))
        print(f"  {s}: 有价格 {n(lambda x: isinstance(x, (int, float)))} | 缺货 {n(lambda x: str(x).startswith('unavailable'))} | 待续 {n(lambda x: x == '待续')} | 拦截 {n(lambda x: x == '被网站拦截')} | 无链接 {n(lambda x: x == '无链接')} | 其他异常 {n(lambda x: isinstance(x, str) and x.startswith(('链接商品', '搜索结果', '页面无价格', '读取失败')))}")
    if stopped or any(x == "待续" for v in stat.values() for x in v): print("还有\"待续\"的格子: 过几个小时再运行 resume(只读没读到的)。")

if __name__ == "__main__": main()
