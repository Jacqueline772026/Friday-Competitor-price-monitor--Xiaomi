"""竞品表体检(只读，不联网): 列出哪些款式没有链接、没有 RRP、RRP 存疑；以及结果表里最近一次检查还有哪些格子没读到。
用法: python app/tools/check_table.py [竞品表路径] [--json]
增减款式后先跑它，再按提示补链接(见 SKILL.md)。"""
import argparse, json, pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import competitors as C, paths

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("table", nargs="?", default=str(paths.find_table())); ap.add_argument("--json", action="store_true"); a = ap.parse_args()
    if hasattr(sys.stdout, "reconfigure"): sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    items, sheet = C.read_table(a.table); cache = C.load_cache(paths.CACHE)
    nolink = [i["key"] for i in items if not (i["euro"] or i["oleole"] or i.get("mex") or cache.get(i["key"]))]
    norrp = [i["key"] for i in items if i["rrp"] is None]; doubt = [i["key"] for i in items if i["rrp_doubt"]]
    out = {"table": a.table, "sheet": sheet, "rows": len(items), "no_link": nolink, "no_rrp": norrp, "rrp_doubtful": doubt}
    if a.json: print(json.dumps(out, ensure_ascii=False, indent=1)); return
    print(f"{pathlib.Path(a.table).name} [{sheet}]: 共 {len(items)} 款 | 没有任何链接 {len(nolink)} | 没有 RRP {len(norrp)} | RRP 存疑 {len(doubt)}")
    for title, lst in (("没有任何链接(不会被检查)", nolink), ("没有 RRP(照常记录现价，对比写\"无RRP\")", norrp), ("RRP 带问号，请确认", doubt)):
        if lst: print(f"\n{title}:"); [print("  -", k) for k in lst]

if __name__ == "__main__": main()
