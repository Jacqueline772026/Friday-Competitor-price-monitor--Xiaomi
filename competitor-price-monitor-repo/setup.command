#!/bin/bash
cd "$(dirname "$0")"
if [ ! -d .venv ]; then python3 -m venv .venv; fi
.venv/bin/pip install -r requirements.txt && echo "安装完成 / Setup done. 请把竞品表放在本文件夹，命名为 competitor_table.xlsm 或 competitor_table.xlsx。"
echo; read -n 1 -s -r -p "按任意键关闭 / Press any key to close..."
