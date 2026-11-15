@echo off
setlocal EnableExtensions
chcp 65001 >nul
title Assistente Inteligente - Preparação do Windows
cd /d "%~dp0"

echo ============================================================
echo        ASSISTENTE INTELIGENTE - PREPARAÇÃO DO WINDOWS
echo ============================================================
echo.

set "PYEXE="

rem Prefer Python 3.12 because this project/build is validated for it.
py -3.12 -c "import sys; assert sys.maxsize > 2**32" >nul 2>&1
if not errorlevel 1 set "PYEXE=py -3.12"

if not defined PYEXE (
    python -c "import sys; assert sys.version_info[:2] == (3,12) and sys.maxsize > 2**32" >nul 2>&1
    if not errorlevel 1 set "PYEXE=python"
)

if not defined PYEXE (
    echo Python 3.12 de 64 bits nao foi encontrado.
    echo.
    where winget >nul 2>&1
    if errorlevel 1 (
        echo O Gerenciador de Pacotes do Windows ^(winget^) tambem nao foi encontrado.
        echo Instale o Python 3.12 de 64 bits pelo site oficial do Python
        echo e execute este arquivo novamente.
        echo.
        pause
        exit /b 1
    )
    echo Vou solicitar ao Windows a instalacao do Python 3.12.
    echo Pode aparecer uma confirmacao do instalador.
    echo.
    winget install --id Python.Python.3.12 -e --source winget --accept-package-agreements --accept-source-agreements
    if errorlevel 1 (
        echo.
        echo Nao foi possivel instalar o Python automaticamente.
        echo Feche esta janela, instale o Python 3.12 de 64 bits e tente novamente.
        pause
        exit /b 1
    )
    echo.
    echo Python instalado. Atualizando a deteccao...
    py -3.12 -c "import sys; assert sys.maxsize > 2**32" >nul 2>&1
    if not errorlevel 1 set "PYEXE=py -3.12"
)

if not defined PYEXE (
    echo A instalacao terminou, mas esta janela ainda nao consegue localizar o Python.
    echo Feche-a, abra novamente PREPARAR-WINDOWS.bat e continue.
    pause
    exit /b 1
)

echo Criando ambiente isolado do Assistente Inteligente...
%PYEXE% -m venv ".venv"
if errorlevel 1 goto :erro

call ".venv\Scripts\activate.bat"
python -m pip install --upgrade pip setuptools wheel
if errorlevel 1 goto :erro

if exist requirements.txt (
    echo.
    echo Instalando dependencias do projeto...
    python -m pip install -r requirements.txt
    if errorlevel 1 goto :erro
) else (
    echo ERRO: requirements.txt nao foi encontrado.
    goto :erro
)

echo.
echo Verificando a instalacao...
python -c "import PyQt6, sounddevice; print('Dependencias principais: OK')" 
if errorlevel 1 goto :erro

echo.
echo ============================================================
echo Preparacao concluida com sucesso.
echo Agora voce pode usar INICIAR.bat.
echo Para gerar o executavel, use CRIAR-EXECUTAVEL.bat.
echo ============================================================
pause
exit /b 0

:erro
echo.
echo Nao foi possivel concluir a preparacao.
echo Leia a mensagem acima. Nenhum arquivo pessoal foi apagado.
pause
exit /b 1
