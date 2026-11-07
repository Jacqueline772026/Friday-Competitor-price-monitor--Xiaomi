---
name: competitor-price-operator
description: 运行竞品价格周监控(EURO/OleOle/Media Expert 现价 vs RRP)：每周五完整检查、查错补漏、体检竞品表、补链接、解读结果。Use for the weekly competitor price check, gap-filling, table checks and link fixes.
---

# Competitor Price Operator

项目根目录 = 含 `app/run.py` 的文件夹。命令从根目录运行，Python 用 `.venv`(Mac: `.venv/bin/python`，Windows: `.venv\Scripts\python`)。

## 0. 环境
- 安装：`setup.command`(Mac) / `setup.bat`(Windows)，需要 Python 3.9+ 和本机 Chrome/Edge。
- 有沙箱的 agent(Codex 等)：启动 Chrome、访问 `localhost:9222` 和零售网站需要用户放行；放行不了就让用户双击 `run_full` / `resume`，不要绕过。
- 列出结果时按每个日期 5 列：EURO / OleOle / MEX / 对比RRP / 汇总(复制用)；汇总格里相同价格只写一次。

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

## 3b. 缺 RRP / 缺链接：自己触发查找，不要停下来问
- 缺 RRP 的型号：先到 https://m.gsmarena.com/ 搜该型号(页面里有发布价/各地区价格)。注意 GSMArena 给的多为 EUR/USD 价格，不是波兰 PLN 官方 RRP：只作参考，在汇报里写明来源、币种和日期，RRP 单元格不要自行猜填，标"?"待用户确认。WebFetch 常被拦，改用浏览器或搜索摘要。
- 缺 EURO / Media Expert 链接的型号(表里空，且缓存里没有)：agent 自己去 EURO(`euro.com.pl/search.bhtml?keyword=`)、Media Expert(`mediaexpert.pl/search?query[querystring]=`)站内搜，核对型号+内存完全一致后用 `add_link.py` 写入；OleOle 由 EURO 同名链接推导。不要等用户提醒，也不要硬配相近型号；确实没有就汇报"该渠道没有"。
- 程序跑完发现的 `无链接` 也按此处理，做完再补漏。

## 3c. 省页数：确认没有 / 已下架 / 不查
- 程序自动记住：站内搜索确认"没有该型号/内存"的格子写 `无此型号(已确认)`（原因在批注里）、页面写明下架的写 `discontinued`；28 天内不再重复搜，表里链接改过会立即重新查。记录在 `config/competitor_status.json`。
- 停售老款：`python app/tools/mark.py 品牌 型号 内存 skip` 标成 `不查`（结果里显示"不查"，不占页数）；`unskip` 取消；`list` 查看。判断是否停售要先在 EURO/Media Expert 看过，不要凭印象标。
- 这些文字属于"已完成"，resume 不会再重读。

## 4. 增减款式
在竞品表里加/删行(用户操作)。运行 `check_table.py`；没有链接的款式不会被检查：用浏览器在 EURO/Media Expert 搜到同型号同内存的商品页，`add_link.py` 补上。OleOle 一般不用补(会用 EURO 同名链接推导)。找不到不要猜，列入"待用户确认"。

## 5. 汇报模板
日期 · 各网站有价格/缺货/待续/异常数量 · 比 RRP 便宜/贵的款式 · 表里疑似写错的型号/内存 · 缺链接/缺 RRP 清单 · 需要用户做的事。
