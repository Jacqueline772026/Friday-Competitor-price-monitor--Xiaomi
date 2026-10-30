# Agent 说明 / Instructions for coding agents (Codex, Claude Code, etc.)

这是一个独立的竞品价格周监控工具。请先阅读 `skills/competitor-price-operator/SKILL.md`，按其中流程操作。
This is a standalone weekly competitor price monitor; follow `skills/competitor-price-operator/SKILL.md`.

- 每周五完整检查: `python app/run.py`；查错补漏(只补没读到的): `python app/run.py --mode resume`。两个入口不要混用。
- 表格体检: `python app/tools/check_table.py`；补/改链接: `python app/tools/add_link.py`(不会改用户的竞品表)。
- 不要绕过验证码/反爬；低频访问；不要提交竞品表、结果表、`config/competitor_links.json`、`data/`。
- 改完代码跑 `python tests/run_tests.py`。
