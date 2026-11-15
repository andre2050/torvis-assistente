@echo off
chcp 65001 >nul
cd /d "%~dp0"
py -3 -m core.netguard_report
echo.
pause
