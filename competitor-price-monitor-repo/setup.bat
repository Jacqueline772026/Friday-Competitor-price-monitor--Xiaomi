@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist .venv ( py -3 -m venv .venv )
.venv\Scripts\pip install -r requirements.txt && echo Setup done. Put your table here as competitor_table.xlsm or competitor_table.xlsx
echo.
pause
