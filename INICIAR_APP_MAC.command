#!/bin/bash
cd "$(dirname "$0")"
echo "=============================================="
echo "  ORQUESTRA BIASI - INICIANDO APLICATIVO"
echo "=============================================="
if ! command -v python3 >/dev/null 2>&1; then
  echo "Python3 nao encontrado. Instale em https://www.python.org/downloads/"
  open https://www.python.org/downloads/
  exit 1
fi
[ -f .env ] || cp .env.example .env
if [ ! -f .venv/bin/python ]; then
  python3 -m venv .venv
fi
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r backend/requirements.txt
open http://127.0.0.1:8000
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
