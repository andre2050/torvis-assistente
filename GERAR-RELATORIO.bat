@echo off
chcp 65001 >nul
cd /d "%~dp0"
py -3 -m core.report "%~dp0relatorio-torvis.txt"
echo.
echo Abrindo o relatorio...
if exist "%~dp0relatorio-torvis.txt" start notepad "%~dp0relatorio-torvis.txt"
pause
