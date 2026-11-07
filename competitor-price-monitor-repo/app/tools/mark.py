"""把某个款式标成"不查"(停售老款，不占用页数)，或取消。结果里该款显示"不查"；其它"确认没有/已下架"由程序自动记，28 天后自动复查。
用法: python app/tools/mark.py 品牌 型号 内存 skip      标"不查"
      python app/tools/mark.py 品牌 型号 内存 unskip    取消
      python app/tools/mark.py list                      看现在有哪些记录"""
import pathlib, sys, datetime
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import competitors as C
try:
    import paths; P = paths.CACHE.with_name("competitor_status.json")
except ImportError:
    P = pathlib.Path(__file__).resolve().parents[1] / "competitor_status.json"
d = C.load_cache(P)
if sys.argv[1:] == ["list"]:
    for k, v in d.items(): print(k, {s: e["state"] + " " + e["date"] for s, e in v.items()})
    sys.exit()
if len(sys.argv) != 5 or sys.argv[4] not in ("skip", "unskip"): sys.exit(__doc__)
key = "|".join(sys.argv[1:4])
if sys.argv[4] == "skip": d.setdefault(key, {})["*"] = {"state": "skip", "date": str(datetime.date.today())}; print("已标不查:", key)
else: d.get(key, {}).pop("*", None); print("已取消:", key)
C.save_cache(P, d)
