@echo off
chcp 65001 >nul
title Instalar Python - Orquestra Biasi
cd /d "%~dp0"
echo.
echo ==============================================
echo   INSTALAR PYTHON E INICIAR ORQUESTRA BIASI
echo ==============================================
echo.
where winget >nul 2>nul
if errorlevel 1 (
  echo Nao encontrei o instalador automatico do Windows ^(winget^).
  echo Vou abrir a pagina oficial do Python.
  start "" "https://www.python.org/downloads/windows/"
  echo.
  echo Instale o Python marcando "Add python.exe to PATH".
  echo Depois rode INICIAR_APP_WINDOWS.bat novamente.
  pause
  exit /b 1
)
winget install --id Python.Python.3.12 -e --source winget --accept-package-agreements --accept-source-agreements
echo.
echo Instalacao solicitada. Agora vou tentar iniciar o aplicativo.
call "%~dp0INICIAR_APP_WINDOWS.bat"
