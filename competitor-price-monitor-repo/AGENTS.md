# AGENTS.md — Codex / Claude Code / 其它 coding agent 通用说明

这是一个**独立**的竞品价格周监控工具（EURO / OleOle / Media Expert 现价 vs 你自己竞品表里的 RRP）。
This is a standalone weekly competitor price monitor. Full procedure: [`skills/competitor-price-operator/SKILL.md`](skills/competitor-price-operator/SKILL.md)
(同一份也放在 `.agents/skills/competitor-price-operator/SKILL.md`，供自动发现 skill 的 agent 使用；两份必须一致，`tests/run_tests.py` 会检查。)

## 环境 / Setup
- Python 3.9+，在项目根目录运行。第一次：Mac `bash setup.command`，Windows `setup.bat`；或手动 `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`(Windows: `.venv\Scripts\`)。
- 需要本机装有 Google Chrome 或 Edge。程序会自己启动**专用 Chrome**(独立资料夹，调试端口 9222)，Playwright 通过 CDP 连接。
- **沙箱提示**：启动 Chrome、访问 `localhost:9222`、访问零售网站都需要联网/本机权限。在 Codex 等有沙箱的环境里，请向用户申请放行(或让用户自己在终端双击 `run_full` / `resume`)，不要换成别的绕过办法。

## 常用命令 / Commands
| 目的 | 命令 |
|---|---|
| 每周五完整检查(整张表重读) | `python app/run.py` |
| 查错补漏(只补没读到的，已读到的不动) | `python app/run.py --mode resume` |
| 小范围试跑 | `python app/run.py --rows 4-10` |
| 竞品表体检(无链接/无 RRP/RRP 存疑) | `python app/tools/check_table.py` |
| 补/改某款链接 | `python app/tools/add_link.py 品牌 型号 内存 EURO|OleOle|MEX 网址` |
| 离线自检(不联网) | `python tests/run_tests.py` |

两个入口(完整 / 补漏)**不要混用**；完整检查之后出现"待续/读取失败/被网站拦截"，隔 2–3 小时再 resume。

## 规矩 / Rules
- 不绕过验证码/反爬；低频访问(页间隔 ≥8 秒)；不要提高每站页数上限(EURO 50 / OleOle 40 / MEX 40)。
- 竞品表(`competitor_table.xlsm/.xlsx`)只读，不要改它(xlsm 含宏)；链接修正写进 `config/competitor_links.json`(用 `add_link.py`)。
- 运行前确认 `competitor_log.xlsx` 没在 Excel 里打开(没有 `~$competitor_log.xlsx`)。
- 不要提交：竞品表、`competitor_log.xlsx`、`config/competitor_links.json`、`data/`、`.venv/`。
- 结果列：每个日期 5 列 —— `EURO <日期>`、`OleOle <日期>`、`MEX <日期>`、`对比RRP <日期>`、`汇总(复制用) <日期>`（有价格的渠道用 `/` 连接，相同价格只写一次；没价格写 `无链接` / `unavailable` / `待续`）。
- "链接商品与表不符 / 搜索结果里没有找到"：按 SKILL 第 3 节自查，确认网站上确实没有就如实汇报"表里型号/内存可能写错"，不要硬配链接。
- 改动代码后必须跑 `python tests/run_tests.py`；改了 SKILL 要同步 `.agents/skills/` 那份。
