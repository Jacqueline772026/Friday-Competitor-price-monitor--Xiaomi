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
- 缺 RRP 的型号：先到 https://m.gsmarena.com/ 搜该型号(页面里有发布价/各地区价格)。注意 GSMArena 给的多为 EUR/USD 价格，不是波兰 PLN 官方 RRP：只作参考，在汇报里写明来源、币种和日期，RRP 单元格不要自行猜填，标"?"待用户确认。WebFetch 常被拦，改用浏览器或搜索摘要。agent 的浏览器访问 gsmarena 会被转到 tollbit 付费/防爬页，不要绕过：打不开或网站没有该型号的价格时，RRP 一律留空(结果里写"无RRP")，不要猜、不要填欧元价。
- 缺 EURO / Media Expert 链接的型号(表里空，且缓存里没有)：agent 自己去 EURO(`euro.com.pl/search.bhtml?keyword=`)、Media Expert(`mediaexpert.pl/search?query[querystring]=`)站内搜，核对型号+内存完全一致后用 `add_link.py` 写入；OleOle 由 EURO 同名链接推导。不要等用户提醒，也不要硬配相近型号；确实没有就汇报"该渠道没有"。
- 程序跑完发现的 `无链接` 也按此处理，做完再补漏。

## 3c. 省页数：确认没有 / 已下架 / 不查
- 程序自动记住：站内搜索确认"没有该型号/内存"的格子写 `无此型号(已确认)`（原因在批注里）、页面写明下架的写 `discontinued`；28 天内不再重复搜，表里链接改过会立即重新查。记录在 `config/competitor_status.json`。
- 停售老款：`python app/tools/mark.py 品牌 型号 内存 skip` 标成 `不查`（结果里显示"不查"，不占页数）；`unskip` 取消；`list` 查看。判断是否停售要先在 EURO/Media Expert 看过，不要凭印象标。
- 这些文字属于"已完成"，resume 不会再重读。

## 3d. 不计 Outlet
所有渠道不计 Outlet / 翻新 / 展示机 / 拆封退货 / 二手商品：搜索结果里带 outlet、refurbished、regenerowany、poekspozycyjny、po zwrocie、używany 等字样的商品会被程序跳过；链接指向这类商品时按"链接商品与表不符"重新搜索。手动补链接时也不要用 Outlet 页面。

## 3e. 查不到 / 有问题的型号：用 GfK 判断值不值得追踪（固定流程）
对每个"三个网站都查不到(无此型号/无链接)、链接对不上、价格明显异常"的型号：
1. 在用户提供的 GfK 表(HL_SPLIT_I，表头第 19 行)里按品牌+型号+内存找：看最近 6 个月销量、月度趋势(上升/稳定/下滑)、WOB(CONTRACT 运营商 / SIM FREE)、Channel(CES=家电连锁 EURO/OleOle/MEX 一类，MoPhS=运营商/手机店，MassMerch=大卖场)。GfK 没有该内存 = 表里内存写错，建议改型号。
2. 判断：6 个月销量大(几千以上)且稳定/上升 → 建议追踪；量很小(月均百台以下)或明显退市(连续下滑) → 建议不追踪，写清原因。销量主要在 MoPhS/CONTRACT(运营商渠道)的型号，EURO/OleOle/MEX 本来就不卖，不是程序没找到，要追踪需要换渠道。
3. 给用户一段可以直接对领导说的话术：建议追踪时写"销量+趋势+渠道+需要的动作"；不建议时写"销量数据+原因+不会追踪"。用户同意"不追踪"后用 `mark.py ... skip` 标"不查"。
4. 不要凭印象标"不查"：先查 GfK。(2026-11-09 教训：A05s 4+64、G84 12+256、G05、C61 销量并不小，曾被误标，已撤销。)

## 4. 增减款式
在竞品表里加/删行(用户操作)。运行 `check_table.py`；没有链接的款式不会被检查：用浏览器在 EURO/Media Expert 搜到同型号同内存的商品页，`add_link.py` 补上。OleOle 一般不用补(会用 EURO 同名链接推导)。找不到不要猜，列入"待用户确认"。

汇报时固定加一段"缺 RRP 清单"：列出表里 RRP 为空的型号(不含已标"不查"的)，提醒用户来补；用户给了波兰官方价再填进表里。不要自己猜、不要填欧元价。

## 5. 汇报模板
日期 · 各网站有价格/缺货/待续/异常数量 · 比 RRP 便宜/贵的款式 · 表里疑似写错的型号/内存 · 缺链接/缺 RRP 清单 · 需要用户做的事。

### 3f. 价格存疑时，agent 自己用浏览器打开官网核对(不要让用户去看)
运行后出现【价格异常待核对】/【链接疑似写错】里的款式，agent 要自己用浏览器(内置浏览器或专用 Chrome，和程序读页面的方式一致)逐个打开对应商品页核对，再把结论告诉用户，不要把"请你去浏览器看一眼"交给用户。
- EURO/OleOle 是动态页面，打开后要等 6–8 秒再读；读 `"prices":{"mainPrice"..., "promotionalPrice"...}` 和 `deliveryAvailability`，注意促销价(promotionalPrice)与原价(mainPrice)的区别。
- Media Expert：看页面是否写 "Produkt chwilowo niedostępny"(无货)和 "Sprzedawca:" 是不是 Media Expert(第三方卖家的价格不计)。
- 核对商品名称是不是同一型号(5G 与 4G/LTE、内存、颜色版本)；链接对不上就改缓存链接并重读。
- 核对结论分三类告诉用户：真实价格(促销/清仓/RRP过时)、读错(链接错/无货残留价/第三方卖家，已改正)、无法打开(说明原因)。
- **缺失/疑似写错的链接，同样由 agent 用浏览器真实搜索**(打开官网站内搜索页，核对型号+内存+是否 5G/4G 版本，再把商品页链接写进表/缓存)，比凭型号推理可靠。官网搜索网址见《需手动查询清单.md》。注意：Samsung 的 4G 版和 5G 版页面名称常只差型号代码(如 A17: SM-A175=4G，SM-A176=5G)，程序的名称核对分不出来，必须用浏览器看页面标题和型号代码。
