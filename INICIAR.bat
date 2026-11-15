@echo off
setlocal EnableExtensions
chcp 65001 >nul
title Assistente Inteligente
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo O Assistente Inteligente ainda nao foi preparado neste computador.
    echo.
    echo Execute primeiro PREPARAR-WINDOWS.bat.
    echo.
    pause
    exit /b 1
)

".venv\Scripts\python.exe" main.py
set "CODIGO=%ERRORLEVEL%"
if not "%CODIGO%"=="0" (
    echo.
    echo ============================================================
    echo O Assistente Inteligente foi encerrado com erro ^(codigo %CODIGO%^).
    echo A mensagem acima ajuda a identificar o problema.
    echo ============================================================
    pause
)
exit /b %CODIGO%
