@echo off
chcp 65001 >nul
echo.
echo [BUILD] NurseScheduler
echo.

uv sync
echo.

uv run pyinstaller --onedir --windowed --icon="logo.ico" --name NurseScheduler --collect-all ortools --collect-all holidays main.py
echo.

echo [DONE] dist\NurseScheduler\r
pause
