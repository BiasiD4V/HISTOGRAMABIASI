@echo off
chcp 65001 >nul
title Orquestra Biasi - Histograma
cd /d "%~dp0"

echo.
echo ==============================================
echo   ORQUESTRA BIASI - INICIANDO APLICATIVO
echo ==============================================
echo.

call :find_python
if not defined PY_CMD (
  echo Python nao encontrado de forma valida neste computador.
  echo.
  echo Tentarei instalar Python automaticamente usando winget.
  echo Se o Windows pedir permissao, aceite a instalacao.
  echo.
  where winget >nul 2>nul
  if errorlevel 1 (
    echo Nao encontrei winget. Vou abrir a pagina de download do Python.
    echo Instale o Python e marque a opcao "Add python.exe to PATH".
    start "" "https://www.python.org/downloads/windows/"
    pause
    exit /b 1
  )
  winget install --id Python.Python.3.12 -e --source winget --accept-package-agreements --accept-source-agreements
  echo.
  echo Rechecando Python...
  call :find_python
)

if not defined PY_CMD (
  echo.
  echo Ainda nao consegui encontrar o Python.
  echo Feche esta janela, abra de novo o INICIAR_APP_WINDOWS.bat.
  echo Se continuar, reinicie o computador depois de instalar o Python.
  pause
  exit /b 1
)

echo Python encontrado: %PY_CMD%

if not exist ".env" copy ".env.example" ".env" >nul

if not exist ".venv\Scripts\python.exe" (
  echo.
  echo Criando ambiente local do aplicativo...
  %PY_CMD% -m venv .venv
  if errorlevel 1 (
    echo Falha ao criar ambiente local.
    pause
    exit /b 1
  )
)

call ".venv\Scripts\activate.bat"

echo.
echo Instalando/checando dependencias. Isso pode demorar na primeira vez...
python -m pip install --upgrade pip
if errorlevel 1 (
  echo Falha ao atualizar pip.
  pause
  exit /b 1
)
python -m pip install -r backend\requirements.txt
if errorlevel 1 (
  echo Falha ao instalar dependencias.
  pause
  exit /b 1
)

echo.
echo Iniciando servidor local...
echo O navegador vai abrir automaticamente em alguns segundos.
echo Para parar o app, feche esta janela.
echo.
start "" cmd /c "timeout /t 5 >nul && start http://127.0.0.1:8000"
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000

echo.
echo O aplicativo foi encerrado.
pause
exit /b 0

:find_python
set "PY_CMD="
py -3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)" >nul 2>nul
if not errorlevel 1 (
  set "PY_CMD=py -3"
  exit /b 0
)
python -c "import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)" >nul 2>nul
if not errorlevel 1 (
  set "PY_CMD=python"
  exit /b 0
)
python3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)" >nul 2>nul
if not errorlevel 1 (
  set "PY_CMD=python3"
  exit /b 0
)
exit /b 0
