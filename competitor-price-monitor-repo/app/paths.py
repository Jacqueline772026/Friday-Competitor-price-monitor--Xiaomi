"""项目路径(都相对于项目根目录)。"""
import pathlib
APP = pathlib.Path(__file__).resolve().parent
ROOT = APP.parent
DATA, LOGS, CONFIG = ROOT / "data", ROOT / "data" / "logs", ROOT / "config"
LOG_XLSX = ROOT / "competitor_log.xlsx"                 # 结果工作簿(每周追加一组带日期的列)
CACHE = CONFIG / "competitor_links.json"                # 自动找到/手动指定并核对过的链接
def find_table():
    """竞品表: 根目录下的 competitor_table.xlsm / .xlsx"""
    return next((ROOT / n for n in ("competitor_table.xlsm", "competitor_table.xlsx") if (ROOT / n).exists()), ROOT / "competitor_table.xlsx")
