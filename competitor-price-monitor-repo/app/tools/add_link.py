"""手动指定/更新某个款式在某个网站的链接(写进 config/competitor_links.json，优先于竞品表里的链接；不会修改你的竞品表)。
用法: python app/tools/add_link.py 品牌 型号 内存 渠道 网址        渠道: EURO / OleOle / MEX
例:   python app/tools/add_link.py Samsung "A16 5G" 4+128 EURO https://www.euro.com.pl/telefony-komorkowe/xxx.bhtml"""
import pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import competitors as C, paths
DOM = {"EURO": "euro.com.pl", "OleOle": "oleole.pl", "MEX": "mediaexpert.pl"}
if len(sys.argv) != 6: sys.exit(__doc__)
brand, product, spec, ch, url = sys.argv[1:]
ch = next((k for k in DOM if k.lower() == ch.lower()), None) or sys.exit(f"渠道必须是 {', '.join(DOM)}")
if not url.startswith("https://") or DOM[ch] not in url.split("/")[2]: sys.exit(f"网址必须是 https://...{DOM[ch]}/...")
d = C.load_cache(paths.CACHE); key = f"{brand}|{product}|{spec}"; old = d.setdefault(key, {}).get(ch); d[key][ch] = url; C.save_cache(paths.CACHE, d)
print(("更新" if old else "新增"), key, ch, "->", url)
