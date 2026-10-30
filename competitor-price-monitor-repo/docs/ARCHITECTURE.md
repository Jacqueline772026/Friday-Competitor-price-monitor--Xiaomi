# Architecture
- `app/run.py`：入口。检查竞品表 → 启动专用 Chrome → 调用 `check_competitors.py`（full 或 `--resume`）→ 日志写 `data/logs/`，30 天前的日志自动删除。
- `app/competitors.py`（纯逻辑，可离线测试）：读表(`read_table`)、内存/型号核对(`norm_mem`、`model_key`、`verify`)、对比文字(`compare_text`)、Media Expert 搜索结果解析(`mex_items`)、结果工作簿(`Book`)。
- `app/check_competitors.py`：浏览器部分。`lookup()` 的自查流程：缓存链接 → 表里链接 → OleOle 推导 → 站内搜索；对不上则重新搜索并核对，核对一致才记住。`finish()` 判断库存/下架/价格。
- `app/browser.py`：专用 Chrome 启动(CDP 端口 9222、独立 profile)；`fetch()` 限速 8–14 秒、超时重试、拦截页识别。
- `app/retail.py`：EURO / OleOle(同一套平台)页面解析：JSON-LD 价格与库存、`deliveryAvailability`。
- 结果：`competitor_log.xlsx`，固定 7 列(品牌/型号/内存/RRP/三个链接) + 每个检查日期 4 列。
