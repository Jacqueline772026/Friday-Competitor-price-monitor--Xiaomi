# Competitor Price Monitor · 竞品价格周监控

> 每周五核对竞品手机/平板在波兰 **EURO、OleOle、Media Expert** 的现价，直接和你表里的 **RRP** 对比，结果按日期追加到 Excel。
> Weekly check of competitor phone/tablet prices at Polish retailers (EURO, OleOle, Media Expert), compared with the RRP in your own table, appended to Excel by date.

这是一个**独立项目**，不依赖任何其他价格监控项目。
This is a standalone project.

## 1. 它做什么
- 读你的**竞品表**（`competitor_table.xlsm` 或 `.xlsx`）：品牌 / 型号 / 内存 / RRP / 各网站商品链接。**只读，不会修改你的表**（xlsm 里的宏不受影响）。
- 每个款式查 EURO、OleOle、Media Expert 的当前价格和库存。
- 结果写入 **`competitor_log.xlsx`**：左边是品牌/型号/内存/RRP/链接，右边**每周追加一组带日期的四列**：`EURO 2026.10.30`、`OleOle 2026.10.30`、`MEX 2026.10.30`、`对比RRP 2026.10.30`。

| 单元格 | 含义 |
|---|---|
| `1399.99` | 现价（数字；比 RRP 便宜的浅绿、更贵的浅红） |
| `unavailable` | 网上缺货（页面价格放在单元格批注里） |
| `unavailable online` | 只有门店有货，网上不能买 |
| `discontinued` | 页面写明"产品已不再销售" |
| `待续` | 到了页数上限或被拦截，稍后补漏 |
| `被网站拦截` / `读取失败(...)` | 稍后补漏 |
| `链接商品与表不符: ...；已重新搜索，该渠道没有这个内存/型号` | 你表里的链接指向别的内存/型号，程序已重新搜索仍找不到：多半是表里的型号/内存写错了 |
| `搜索结果里没有找到该型号/内存` | 站内搜索也没有这款 |
| `无链接` | 这个款式没有任何链接，不检查 |

「对比RRP」列：`EURO -100 | OleOle +0 | MEX +50`（现价 − RRP）；全部等于 RRP 写 `= RRP`；表里没有 RRP 写 `无RRP`。

## 2. 安装
需要 **Python 3.9+** 和 **Google Chrome**（或 Edge）。不需要额外下载浏览器。
- Mac：双击 `setup.command`　·　Windows：双击 `setup.bat`（先安装 Python 并勾选 *Add to PATH*）
- 把竞品表放在项目根目录，命名 `competitor_table.xlsm` 或 `competitor_table.xlsx`。格式见 `templates/competitor_table_template.xlsx`：
  - 用名为 `竞品价格` 的 sheet（或名字里含 `competitor` 的；否则用第一个 sheet）。
  - A=Brand、B=product、C=spec（如 `8+256` 或 `8/256`）、D=RRP、E=EURO 链接、F=Media Expert 链接。可选 OleOle 链接放别的列，用 `--oleole-col` 指定；不放也行，程序会自动找。
  - 品牌为 `Xiaomi / Redmi / Redmi Note / POCO / Pad` 的行会被跳过。

## 3. 使用
| 想做什么 | Mac | Windows | 命令行 |
|---|---|---|---|
| **每周五完整检查**（整张表重新读一遍） | `run_full.command` | `run_full.bat` | `python app/run.py` |
| **查错补漏**（只补没读到的，已读到的不动） | `resume.command` | `resume.bat` | `python app/run.py --mode resume` |

1. 先关闭 Excel 里的 `competitor_log.xlsx`（提示保存时选"不保存"）。
2. 双击 `run_full`。脚本会自动打开一个**专用 Chrome**（独立资料夹，不影响你平时的浏览器），首次启动后多等约 30 秒；运行期间不要关它。系统若弹出密码/授权框，请先处理。
3. 如果结果里有 `待续`、`读取失败`、`被网站拦截`，**过 2–3 个小时**再双击 `resume`。两个入口分开用，不要混着点。
4. 看完关闭 Excel，选"不保存"。

小范围试跑：`python app/run.py --rows 4-10`（行号为竞品表里的行号）。

## 4. 链接是怎么找的（含自查）
优先级：`config/competitor_links.json`（核对过的链接）→ 你表里的链接 → OleOle 用 EURO 同名链接推导 → 站内搜索。
- 表里的链接和型号/内存对不上时，**自动重新搜索**，找到并核对一致就采用并记住，下周直接用。
- 自动找到的链接要求「型号 + 内存」完全一致（`Magic7` 与 `Magic 7`、`S25+` 与 `S25 Plus` 视为相同），对不上宁可报告也不乱填。
- 手动指定链接：`python app/tools/add_link.py Samsung "A16 5G" 4+128 EURO <网址>`。

## 5. 礼貌限制
- 每页间隔 8–14 秒；超时/网络抖动自动重试一次。
- 每个网站每次最多读 EURO 50 / OleOle 40 / Media Expert 40 页（`--max-pages EURO=50,OleOle=40,MEX=40`）。第一次运行要找链接，页数多，需要分 2–3 次（间隔几小时）完成。
- 识别拦截页（Lockdown / Lock / Blokada / 跳回首页），连续 2 次就停止该网站；**不绕过**任何反爬或验证码。
- 请遵守各网站服务条款，仅用于合理的内部价格核对。

## 6. 增减款式
在竞品表里加/删行即可（下次运行自动并入）。`python app/tools/check_table.py` 会列出没有链接、没有 RRP、RRP 存疑的款式。没有链接的款式不会被检查；缺链接的可用 `add_link.py` 补，或让 AI agent 按 `AGENTS.md` / `skills/competitor-price-operator/SKILL.md` 代你搜索补齐。

## 7. 交给 AI agent
Claude、Codex 等读 `AGENTS.md` 和 `skills/competitor-price-operator/SKILL.md` 就能代你：每周五运行、补漏、检查表格、补链接、解读结果。

## 8. 项目结构
```
app/          run.py(入口) · check_competitors.py · competitors.py(纯逻辑) · browser.py(专用 Chrome/限速/拦截识别) · retail.py(EURO/OleOle 页面解析) · tools/
config/       competitor_links.json 自动生成(已被 git 忽略)
templates/    竞品表模板
skills/       给 AI agent 的操作说明
docs/         ARCHITECTURE.md · TROUBLESHOOTING.md
tests/        python tests/run_tests.py (离线自检)
```

## 9. 兼容性
macOS 已在真机使用验证；Windows 提供了 `.bat` 和 Chrome/Edge 路径查找，**尚未在真实 Windows 电脑上完整测试**。Python 3.9+。

## 10. 许可证
暂未指定。公开发布前请仓库所有者自行选择（例如 MIT）并添加 `LICENSE`。
