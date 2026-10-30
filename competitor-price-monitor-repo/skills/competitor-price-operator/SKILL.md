---
name: competitor-price-operator
description: 运行竞品价格周监控(EURO/OleOle/Media Expert 现价 vs RRP)：每周五完整检查、查错补漏、体检竞品表、补链接、解读结果。Use for the weekly competitor price check, gap-filling, table checks and link fixes.
---

# Competitor Price Operator

项目根目录 = 含 `app/run.py` 的文件夹。命令从根目录运行，Python 用 `.venv`(Mac: `.venv/bin/python`，Windows: `.venv\Scripts\python`)。

## 硬规则
- 不绕过验证码/反爬；遇到 captcha、Lockdown、Lock、Blokada → 停止该网站，写进汇报，不要重试轰炸。
- 每页间隔 ≥8 秒；不要调高每站页数上限(EURO 50 / OleOle 40 / MEX 40)。
- 运行前确认 `competitor_log.xlsx` 没在 Excel 里打开(没有 `~$competitor_log.xlsx`)。
- 竞品表(`competitor_table.xlsm/.xlsx`)只读，不要修改(xlsm 有宏)；链接修正写进 `config/competitor_links.json`(用 `add_link.py`)。
- 不提交竞品表、结果表、`config/competitor_links.json`、`data/` 到 git。

## 1. 每周五完整检查
1. `python app/tools/check_table.py` 看表格有没有问题(无链接/无 RRP/RRP 存疑)。
2. `python app/run.py`(整张表重新读一遍)。
3. 结果在 `competitor_log.xlsx` 最右边带今天日期的四列。出现 `待续`/`读取失败`/`被网站拦截`：隔 2–3 小时用补漏(第 2 节)，不要连续重试。

## 2. 查错补漏(单独入口，不和完整检查混用)
`python app/run.py --mode resume`：只补今天还没读到的格子(待续、读取失败、被拦截、链接不符、搜索没找到)，已读到的数字/缺货/下架不动。

## 3. 自查规则(出现"链接商品与表不符"/"搜索结果里没有找到")
1. 程序已自动重新搜索一次。若仍报"该渠道没有这个内存/型号"，在浏览器里打开该网站的站内搜索，确认真实有哪些内存版本。
2. 如果确实没有(例如 EURO 只有 6/128，表里写 8+128)：在汇报里写"已核对，该渠道没有；表里的型号/内存可能写错"，让用户更正表格，不要硬配链接。
3. 如果是程序没搜到但网站上有：用 `python app/tools/add_link.py 品牌 型号 内存 渠道 网址` 补上，再补漏。
4. Media Expert 搜到的全是配件 = 该网站没有这款手机，保持"没有找到"。

## 4. 增减款式
在竞品表里加/删行(用户操作)。运行 `check_table.py`；没有链接的款式不会被检查：用浏览器在 EURO/Media Expert 搜到同型号同内存的商品页，`add_link.py` 补上。OleOle 一般不用补(会用 EURO 同名链接推导)。找不到不要猜，列入"待用户确认"。

## 5. 汇报模板
日期 · 各网站有价格/缺货/待续/异常数量 · 比 RRP 便宜/贵的款式 · 表里疑似写错的型号/内存 · 缺链接/缺 RRP 清单 · 需要用户做的事。
