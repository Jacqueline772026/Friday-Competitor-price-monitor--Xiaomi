#!/bin/bash
cd "$(dirname "$0")"
.venv/bin/python app/run.py --mode resume
echo; read -n 1 -s -r -p "按任意键关闭 / Press any key to close..."
