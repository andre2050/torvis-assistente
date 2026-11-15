@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Aplicando a atualizacao preparada pelo TORVIS...
echo.
py -3 tools\aplicar_atualizacao.py --esperar 3
echo.
pause
