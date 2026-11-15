@echo off
setlocal EnableExtensions
chcp 65001 >nul
title Assistente Inteligente - Criar Executavel
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo O ambiente ainda nao foi preparado.
    echo Execute PREPARAR-WINDOWS.bat primeiro.
    pause
    exit /b 1
)

call ".venv\Scripts\activate.bat"
python -m pip install --upgrade pyinstaller
if errorlevel 1 goto :erro

echo.
echo Criando TORVIS.exe...
if exist "build\TORVIS" rmdir /s /q "build\TORVIS"
if exist "dist\TORVIS" rmdir /s /q "dist\TORVIS"

rem Prefer project spec if available; otherwise use a conservative onedir build.
set "SPEC=packaging\assistente_inteligente.spec"
if exist "%SPEC%" (
    echo Usando configuracao de build: %SPEC%
    python -m PyInstaller --noconfirm --clean "%SPEC%"
) else (
    python -m PyInstaller --noconfirm --clean --windowed --onedir --name "TORVIS" --icon "config\torvis_ultra.ico" --add-data "config\torvis_ultra.ico;config" --add-data "config\torvis_ultra.png;config" main.py
)
if errorlevel 1 goto :erro

echo.
echo ============================================================
echo BUILD CONCLUIDO
echo Procure o programa dentro da pasta dist.
echo ============================================================
start "" "dist"
pause
exit /b 0

:erro
echo.
echo O executavel nao foi criado.
echo Leia o erro acima; a janela permanecera aberta.
pause
exit /b 1
