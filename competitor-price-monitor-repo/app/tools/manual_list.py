"""不重新联网，直接根据结果表里最新一列生成《需手动查询清单.md》。用法: python app/tools/manual_list.py [结果表] [表格]"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import competitors as C, check_competitors as K
root = pathlib.Path(__file__).resolve().parents[2]
res = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else root / "竞品价格记录.xlsx"
tab = pathlib.Path(sys.argv[2]) if len(sys.argv) > 2 else root / "竞品价格表.xlsx"
items, _ = C.read_table(str(tab)); cache = C.load_cache(root / "app" / "competitor_links.json")
b = C.Book(str(res)); b.sync(items, cache)
import re
labels = sorted({m.group(1) for c in range(8, b.ws.max_column + 1) for m in [re.fullmatch(r"EURO (\d{4}\.\d{2}\.\d{2})", str(b.ws.cell(1, c).value or ""))] if m})
cols = b.date_cols(labels[-1], ("EURO", "OleOle", "MEX"))
n = K.manual_lookup(items, b, cols, ("EURO", "OleOle", "MEX"), res.with_name("需手动查询清单.md"))
print(f"最新一列 {labels[-1]}: {n} 个格子需要手动查询 -> {res.with_name('需手动查询清单.md')}")
