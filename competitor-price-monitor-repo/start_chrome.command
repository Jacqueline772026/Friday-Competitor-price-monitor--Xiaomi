#!/bin/bash
cd "$(dirname "$0")"
.venv/bin/python -c "import sys; sys.path.insert(0,\"app\"); import browser; browser.start_chrome()"
echo; read -n 1 -s -r -p "按任意键关闭 / Press any key to close..."
