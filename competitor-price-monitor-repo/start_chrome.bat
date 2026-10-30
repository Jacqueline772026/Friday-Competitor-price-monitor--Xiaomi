@echo off
chcp 65001 >nul
cd /d "%~dp0"
.venv\Scripts\python -c "import sys; sys.path.insert(0,\"app\"); import browser; browser.start_chrome()"
echo.
pause
