"""竞品周价格监控的纯逻辑部分(不联网、不依赖浏览器，方便测试)。
- read_table: 读你的竞品表(Brand / product / spec / RRP / EURO 链接 [/ OleOle 链接])
- norm_mem / model_tokens / verify: 核对页面商品和表里的型号、内存是否一致
- compare_text: 现价和 RRP 的对比文字
- Book: 结果工作簿，每周五追加一组带日期的列(EURO / OleOle / 对比RRP)，不改动你的原表"""
import json, pathlib, re
import openpyxl
from openpyxl.comments import Comment
from openpyxl.styles import Alignment, Font, PatternFill

SHEET = "竞品价格"
SKIP_BRANDS = {"xiaomi", "redmi", "redmi note", "poco", "pad"}      # 自己的品牌不在这里查(日常表已覆盖)
STOP = {"smartfon", "smartphone", "tablet", "galaxy", "moto", "motorola", "samsung", "realme", "honor", "lenovo",
        "xiaomi", "lte", "5g", "4g", "wifi", "wi", "fi", "wi-fi", "tab"}
GREEN, RED = PatternFill("solid", fgColor="E2F0D9"), PatternFill("solid", fgColor="F8D7DA")
DONE_TEXT = ("unavailable", "unavailable online", "discontinued", "无链接")           # 这些结果 resume 时不再重查

def norm_mem(s):
    """'8+256' / '8/256GB' / '12+1T' / '4+128G' -> (8, 256)；识别不出返回 None"""
    m = re.search(r"(?<![\w.,])(\d+)\s*[+/]\s*(\d+)\s*(GB|TB|G|T)?", str(s or ""), re.I)       # 前面不能紧挨字母/数字(避免把 "S25+ 12/256" 里的 5+ 12 当内存)
    if not m: return None
    ram, rom, u = int(m[1]), int(m[2]), (m[3] or "GB").upper()
    return ram, rom * 1024 if u.startswith("T") else rom

def model_tokens(s, brand=""):
    """商品名/型号名 -> 型号词集合(去掉品牌、通用词、屏幕尺寸、内存及其后面的颜色等)。S25+ 与 S25 Plus 视为相同。"""
    s = str(s or "").lower()
    m = re.search(r"(?<![\w.,])\d+\s*[+/]\s*\d+", s)
    if m: s = s[:m.start()]
    s = re.sub(r"\d+(?:[.,]\d+)?\s*[\"″”]", " ", s).replace(",", ".")
    out = set()
    for t in re.findall(r"[a-z0-9.+\-]+", s):
        if t in STOP or t in set(str(brand).lower().split()): continue
        if t.endswith("+") and len(t) > 1: out.update({t[:-1], "plus"})
        else: out.add(t)
    return out

def model_key(s, brand=""):
    """型号词按顺序拼成一个串(Magic7 与 Magic 7 视为相同，S25+ 与 S25 Plus 视为相同)"""
    s = str(s or "").lower().replace("+", " plus ")
    m = re.search(r"(?<![\w.,])\d+\s*[+/]\s*\d+", s)
    if m: s = s[:m.start()]
    s = re.sub(r"\d+(?:[.,]\d+)?\s*[\"″”]", " ", s).replace(",", ".")
    skip = set(str(brand).lower().split())
    return "".join(t for t in re.findall(r"[a-z0-9.\-]+", s) if t not in STOP and t not in skip).replace("-", "").replace(".", "")

def verify(page_name, brand, product, spec, strict):
    """-> (是否一致, 说明)。宽松(你自己配的链接): 只核对内存；严格(自动找到/推导的链接): 内存 + 型号词必须完全一致"""
    want, got = norm_mem(spec), norm_mem(page_name)
    if want and got and want != got: return False, f"页面是《{str(page_name)[:55]}》"
    if strict and model_key(page_name, brand) != model_key(product, brand): return False, f"页面是《{str(page_name)[:55]}》"
    return True, ("" if got else "未能核对内存")

def parse_rrp(v):
    """-> (数值或 None, 是否存疑)。空 / 0 / 明显不是价格(如 12991180) -> None；'875?' -> (875, True)"""
    if v in (None, "", 0, "0"): return None, False
    if isinstance(v, (int, float)): return (float(v), False) if 100 <= v <= 20000 else (None, False)
    m = re.fullmatch(r"\s*(\d{2,5})(?:[.,]\d+)?\s*(\?)?\s*", str(v))
    if not m: return None, False
    x = float(m[1]); return (x, bool(m[2])) if 100 <= x <= 20000 else (None, False)

def compare_text(rrp, prices):
    """现价 vs RRP。prices = {渠道: 价格或 None}"""
    nums = {k: v for k, v in prices.items() if isinstance(v, (int, float))}
    if not nums: return ""
    if rrp is None: return "无RRP"
    d = {k: round(v - rrp) for k, v in nums.items()}
    if all(abs(v) < 1 for v in d.values()): return "= RRP"
    return " | ".join(f"{k} {v:+d}" if v else f"{k} 0" for k, v in d.items())

def _fmt_price(v):
    return str(int(v)) if float(v).is_integer() else f"{v:.2f}".rstrip("0").rstrip(".")

def summary_text(prices):
    """复制用的汇总格: 有价格的渠道按 EURO/OleOle/MEX 顺序用 / 连起来，相同价格只写一次(799/799/799 -> 799)。
    没有价格时: 全部无链接 -> 无链接；有链接但缺货/没找到型号/没价格 -> unavailable；还没读到(待续/失败/被拦截) -> 待续。"""
    vals = [v for v in prices.values() if v not in (None, "")]
    nums = []
    for v in vals:
        if isinstance(v, (int, float)) and v > 0 and v not in nums: nums.append(v)
    if nums: return "/".join(_fmt_price(v) for v in nums)
    texts = [str(v) for v in vals]
    if not texts: return ""
    if all(t == "无链接" for t in texts): return "无链接"
    if any(t in ("待续", "被网站拦截") or t.startswith("读取失败") for t in texts): return "待续"
    return "unavailable"

def read_table(path, sheet=None, euro_col="E", oleole_col=None, mex_col="F", skip=SKIP_BRANDS):
    """读竞品表 -> 条目列表。只读，不修改原表(xlsx / xlsm 都行)。"""
    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    names = wb.sheetnames
    name = sheet or next((n for n in names if "竞品" in n or "competitor" in n.lower()), names[0])
    ws = wb[name]; idx = lambda c: openpyxl.utils.column_index_from_string(c) - 1
    ec, oc, mc = idx(euro_col), (idx(oleole_col) if oleole_col else None), (idx(mex_col) if mex_col else None)
    url = lambda v: str(v).strip() if isinstance(v, str) and v.strip().startswith("http") else None
    items = []
    for r, row in enumerate(ws.iter_rows(values_only=True), start=1):
        row = list(row) + [None] * 12
        brand, product, spec = (str(row[i]).strip() if row[i] not in (None, "") else "" for i in (0, 1, 2))
        if not (brand and product and spec) or brand.lower() in ("brand", *skip): continue
        rrp, doubt = parse_rrp(row[3])
        items.append({"row": r, "brand": brand, "product": product, "spec": spec, "rrp": rrp, "rrp_doubt": doubt,
                      "euro": url(row[ec]), "oleole": url(row[oc]) if oc is not None else None, "mex": url(row[mc]) if mc is not None else None,
                      "key": f"{brand}|{product}|{spec}"})
    wb.close(); return items, name

def mex_items(html):
    """Media Expert 搜索结果页没有结构化列表，从商品链接里还原 (名称, 链接, None)。链接名里的 8-256gb 还原成 8/256GB 以便核对内存。"""
    out, seen = [], set()
    for m in re.finditer(r'href="((?:https://www\.mediaexpert\.pl)?/(?:smartfony-i-zegarki/smartfony|komputery-i-tablety/tablety-i-e-booki/tablety[^/"]*)/(?:smartfon|tablet)-[^"#?]+)', html):
        u = m.group(1); slug = u.rstrip("/").rsplit("/", 1)[-1]
        if u in seen: continue
        seen.add(u); name = re.sub(r"(?<![\d])(\d+)-(\d+)gb", r"\1/\2GB", slug).replace("-", " ")
        out.append((name, u, None))
    return out

def load_cache(p):
    try: return json.load(open(p, encoding="utf-8"))
    except Exception: return {}

def save_cache(p, d):
    pathlib.Path(p).parent.mkdir(parents=True, exist_ok=True)
    json.dump(dict(sorted(d.items())), open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

class Book:
    """结果工作簿: 左边固定 6 列(品牌/型号/内存/RRP/EURO链接/OleOle链接)，右边每个检查日期 3 列。"""
    FIXED = ["Brand", "Product", "Spec", "RRP", "EURO 链接", "OleOle 链接", "MEX 链接"]

    def __init__(self, path):
        self.path = pathlib.Path(path)
        if self.path.exists(): self.wb = openpyxl.load_workbook(self.path)
        else:
            self.wb = openpyxl.Workbook(); self.wb.active.title = SHEET
        self.ws = self.wb[SHEET] if SHEET in self.wb.sheetnames else self.wb.create_sheet(SHEET, 0)
        if self.ws.cell(1, 1).value != "Brand":
            for i, h in enumerate(self.FIXED, 1): self.ws.cell(1, i, h).font = Font(bold=True)
            self.ws.freeze_panes = "D2"
            for col, w in zip("ABCDEFG", (12, 18, 9, 8, 22, 22, 22)): self.ws.column_dimensions[col].width = w
        self.rows = {f"{self.ws.cell(r, 1).value}|{self.ws.cell(r, 2).value}|{self.ws.cell(r, 3).value}": r
                     for r in range(2, self.ws.max_row + 1) if self.ws.cell(r, 1).value}

    def sync(self, items, cache):
        """把竞品表里的条目同步进来(新增机型追加新行；RRP 以最新为准)，返回 条目->行号"""
        for it in items:
            r = self.rows.get(it["key"])
            if r is None:
                r = self.ws.max_row + 1; self.rows[it["key"]] = r
                for i, v in enumerate((it["brand"], it["product"], it["spec"]), 1): self.ws.cell(r, i, v)
            c = self.ws.cell(r, 4, it["rrp"] if it["rrp"] is not None else "无RRP")
            if it["rrp_doubt"]: c.comment = Comment("表里这个 RRP 带问号，请确认", "price-monitor")
            self.ws.cell(r, 5, it["euro"] or cache.get(it["key"], {}).get("EURO") or "")
            self.ws.cell(r, 6, it["oleole"] or cache.get(it["key"], {}).get("OleOle") or "")
            self.ws.cell(r, 7, it.get("mex") or cache.get(it["key"], {}).get("MEX") or "")
            it["_r"] = r

    def date_cols(self, label, sites=("EURO", "OleOle", "MEX")):
        """找(或新建)这个日期的各列 -> {'EURO': 列号, 'OleOle': 列号, 'MEX': 列号, 'cmp': 列号, 'sum': 列号}"""
        heads = {self.ws.cell(1, c).value: c for c in range(8, self.ws.max_column + 1)}
        out = {}
        for k, h in [(x, f"{x} {label}") for x in sites] + [("cmp", f"对比RRP {label}"), ("sum", f"汇总(复制用) {label}")]:
            if h not in heads:
                c = max(self.ws.max_column, 7) + 1
                self.ws.cell(1, c, h).font = Font(bold=True); self.ws.column_dimensions[openpyxl.utils.get_column_letter(c)].width = 14 if k not in ("cmp", "sum") else 22
                heads[h] = c
            out[k] = heads[h]
        return out

    def get(self, r, c): return self.ws.cell(r, c).value

    def put(self, r, c, value, rrp=None, note=None):
        cell = self.ws.cell(r, c, value); cell.alignment = Alignment(horizontal="right")
        cell.fill = PatternFill(fill_type=None)
        if isinstance(value, (int, float)) and rrp is not None:
            if value < rrp - 1: cell.fill = GREEN
            elif value > rrp + 1: cell.fill = RED
        cell.comment = Comment(note, "price-monitor") if note else None

    def save(self): self.wb.save(self.path)
