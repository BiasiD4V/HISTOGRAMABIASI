from __future__ import annotations
import json, os, tempfile
from pathlib import Path
from typing import List, Optional
from fastapi import FastAPI, File, Form, UploadFile
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse, HTMLResponse
from dotenv import load_dotenv
from .schemas import ProjectInput
from .extraction import extract_uploads, extract_raw_uploads_progress
from .orchestrator import run_pipeline_stream

ROOT_PATH = Path(__file__).resolve().parents[2]
ENV_PATH = ROOT_PATH / ".env"
load_dotenv(ENV_PATH, override=True)

def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()

for _name in (
    "OPENAI_API_KEY",
    "OPENAI_MODEL",
    "OPENAI_REASONING_EFFORT",
    "USE_MOCK_AGENTS",
    "HOSTED_MODE",
    "CORS_ORIGINS",
):
    if _name in os.environ:
        os.environ[_name] = _env(_name)

class SettingsPayload(BaseModel):
    openai_api_key: str = ""
    openai_model: str = "gpt-5.2"
    reasoning_effort: str = "high"
    use_mock_agents: bool = False

def _is_hosted_mode() -> bool:
    return _env("HOSTED_MODE", "false").lower() == "true"

def _write_env(settings: SettingsPayload):
    if _is_hosted_mode():
        # Em hospedagem, a chave deve vir das variáveis de ambiente do provedor
        # e não ser gravada via navegador. Ainda permitimos alternar modo/modelo
        # apenas se o provedor expuser essas variáveis.
        return
    # Se o campo vier vazio e ja existir uma chave salva, preservar a chave anterior.
    api_key = settings.openai_api_key.strip() or _env("OPENAI_API_KEY", "")
    model = settings.openai_model.strip() or "gpt-5.2"
    reasoning = (settings.reasoning_effort or "high").strip()
    use_mock = "true" if settings.use_mock_agents else "false"
    ENV_PATH.write_text(
        f"OPENAI_API_KEY={api_key}\nOPENAI_MODEL={model}\nOPENAI_REASONING_EFFORT={reasoning}\nUSE_MOCK_AGENTS={use_mock}\nCORS_ORIGINS=*\n",
        encoding="utf-8",
    )
    os.environ["OPENAI_API_KEY"] = api_key
    os.environ["OPENAI_MODEL"] = model
    os.environ["OPENAI_REASONING_EFFORT"] = reasoning
    os.environ["USE_MOCK_AGENTS"] = use_mock

app = FastAPI(title="Orquestra Biasi - Agentes Reais", version="1.0.0")
origins = [item.strip() for item in _env("CORS_ORIGINS", "*").split(",") if item.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins if origins != ["*"] else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

FRONTEND_PATH = Path(__file__).resolve().parents[2] / "frontend" / "index.html"

@app.get("/", response_class=HTMLResponse)
def index():
    return FRONTEND_PATH.read_text(encoding="utf-8")

@app.get("/health")
def health():
    return {
        "ok": True,
        "mock_mode": _env("USE_MOCK_AGENTS", "false"),
        "model": _env("OPENAI_MODEL", "gpt-5.2"),
        "has_api_key": bool(_env("OPENAI_API_KEY")),
    }

@app.get("/api/settings")
def get_settings():
    return {
        "has_api_key": bool(_env("OPENAI_API_KEY")),
        "hosted_mode": _is_hosted_mode(),
        "openai_model": _env("OPENAI_MODEL", "gpt-5.2"),
        "reasoning_effort": _env("OPENAI_REASONING_EFFORT", "high"),
        "use_mock_agents": _env("USE_MOCK_AGENTS", "false").lower() == "true",
        "env_path": str(ENV_PATH),
    }

@app.post("/api/settings")
def save_settings(settings: SettingsPayload):
    _write_env(settings)
    return {
        "ok": True,
        "hosted_mode": _is_hosted_mode(),
        "has_api_key": bool(_env("OPENAI_API_KEY")),
        "openai_model": _env("OPENAI_MODEL", "gpt-5.2"),
        "reasoning_effort": _env("OPENAI_REASONING_EFFORT", "high"),
        "use_mock_agents": _env("USE_MOCK_AGENTS", "false").lower() == "true",
    }

@app.post("/api/runs/stream")
async def run_stream(
    cliente: str = Form("Cliente não informado"),
    obra: str = Form("Obra não informada"),
    prazo: int = Form(8),
    unidade: str = Form("semanas"),
    jornada_h_dia: float = Form(8),
    dias_semana: int = Form(5),
    eficiencia: float = Form(0.75),
    premissas_internas: str = Form(""),
    files: List[UploadFile] = File(default=[]),
    cost_file: Optional[UploadFile] = File(default=None),
):
    project = ProjectInput(
        cliente=cliente, obra=obra, prazo=prazo, unidade=unidade,
        jornada_h_dia=jornada_h_dia, dias_semana=dias_semana,
        eficiencia=eficiencia, premissas_internas=premissas_internas,
    )
    # Ler bytes antes do StreamingResponse evita que o Windows/FastAPI feche os arquivos
    # enquanto os agentes ainda estão rodando. A extração pesada continua dentro do streaming.
    uploaded_items = []
    for f in files or []:
        uploaded_items.append((f.filename or "arquivo", await f.read()))
    cost_item = None
    if cost_file and cost_file.filename:
        cost_item = (cost_file.filename, await cost_file.read())

    async def gen():
        docs = []
        cost_path = None
        try:
            yield json.dumps({"type":"status", "message":"Servidor recebeu a solicitação. Preparando arquivos..."}, ensure_ascii=False) + "\n"
            async for event, doc in extract_raw_uploads_progress(uploaded_items):
                yield json.dumps(event, ensure_ascii=False) + "\n"
                if doc is not None:
                    docs.append(doc)
            yield json.dumps({"type":"status", "message":f"Documentos preparados: {len(docs)}", "documents":[d.model_dump() for d in docs]}, ensure_ascii=False) + "\n"

            if cost_item:
                yield json.dumps({"type":"status", "message":"Lendo planilha de custos Biasi..."}, ensure_ascii=False) + "\n"
                filename, raw = cost_item
                suffix = Path(filename).suffix or ".xlsx"
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
                tmp.write(raw)
                tmp.close()
                cost_path = tmp.name

            async for event in run_pipeline_stream(project, docs, cost_path):
                yield json.dumps(event, ensure_ascii=False) + "\n"
        except Exception as exc:
            yield json.dumps({"type":"error", "message": str(exc)}, ensure_ascii=False) + "\n"
        finally:
            if cost_path:
                try: os.unlink(cost_path)
                except Exception: pass

    return StreamingResponse(gen(), media_type="application/x-ndjson")

@app.post("/api/runs")
async def run_once(
    cliente: str = Form("Cliente não informado"),
    obra: str = Form("Obra não informada"),
    prazo: int = Form(8),
    unidade: str = Form("semanas"),
    jornada_h_dia: float = Form(8),
    dias_semana: int = Form(5),
    eficiencia: float = Form(0.75),
    premissas_internas: str = Form(""),
    files: List[UploadFile] = File(default=[]),
):
    project = ProjectInput(cliente=cliente, obra=obra, prazo=prazo, unidade=unidade, jornada_h_dia=jornada_h_dia, dias_semana=dias_semana, eficiencia=eficiencia, premissas_internas=premissas_internas)
    docs = await extract_uploads(files)
    events = []
    async for event in run_pipeline_stream(project, docs):
        events.append(event)
    final = next((e["result"] for e in reversed(events) if e.get("type") == "final"), None)
    return JSONResponse({"events": events, "result": final})
