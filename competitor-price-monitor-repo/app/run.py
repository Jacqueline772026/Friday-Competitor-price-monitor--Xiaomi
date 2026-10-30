"""一键入口(Windows / Mac / Linux 通用)。
  python app/run.py                 # 每周五完整检查: 整张表重新读一遍
  python app/run.py --mode resume   # 查错补漏: 只补今天还没读到/读失败/待续的格子，已读到的不动
  python app/run.py --table 路径    # 指定竞品表(默认 项目根目录 competitor_table.xlsm / .xlsx)
  其余参数原样传给 check_competitors.py，例如 --rows 4-10 先小范围试跑 / --sites EURO,OleOle
日志写入 data/logs/，超过 30 天的日志自动删除。"""
import argparse, datetime as dt, os, subprocess, sys, time
import browser, paths

def main():
    if hasattr(sys.stdout, "reconfigure"): sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(); ap.add_argument("--mode", choices=["full", "resume"], default="full"); ap.add_argument("--table", default="")
    a, rest = ap.parse_known_args()
    table = a.table or str(paths.find_table())
    if not os.path.exists(table): sys.exit("找不到竞品表。请把竞品价格表放在项目根目录，命名为 competitor_table.xlsm 或 competitor_table.xlsx(模板见 templates/)，或用 --table 指定路径。")
    paths.LOGS.mkdir(parents=True, exist_ok=True)
    logp = paths.LOGS / f"{dt.datetime.now():%Y-%m-%d_%H%M}_{a.mode}.log"
    print(f"模式: {'完整检查' if a.mode == 'full' else '查错补漏(只补没读到的)'} | 竞品表: {os.path.basename(table)} | 日志: {logp.name}")
    if not browser.start_chrome(): sys.exit("无法使用专用 Chrome，已停止")
    cmd = [sys.executable, "-u", str(paths.APP / "check_competitors.py"), table] + (["--resume"] if a.mode == "resume" else []) + rest
    env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    with open(logp, "w", encoding="utf-8") as log:
        p = subprocess.Popen(cmd, cwd=paths.ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace", env=env)
        for line in p.stdout: print(line, end=""); log.write(line); log.flush()
        p.wait()
    for f in paths.LOGS.glob("*.log"):                        # 清理 30 天前的日志
        if time.time() - f.stat().st_mtime > 30 * 86400: f.unlink()
    print(f"\n结果: {paths.LOG_XLSX.name} 最右边带今天日期的各列。有\"待续\"/读取失败就过几个小时运行补漏(resume)，只补没读到的。看完请关闭 Excel(选\"不保存\")。")

if __name__ == "__main__": main()
