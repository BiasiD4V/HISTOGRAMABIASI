from __future__ import annotations

import json
import os
import tempfile
import time
import uuid
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from .extraction import extract_uploads, extract_raw_uploads_progress
from .orchestrator import run_pipeline_stream
from .schemas import ProjectInput

ROOT_PATH = Path(__file__).resolve().parents[2]
ENV_PATH = ROOT_PATH / ".env"
UPLOAD_DIR = Path(tempfile.gettempdir()) / "orquestra_biasi_uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

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


class UploadedFileRef(BaseModel):
    file_id: str
    filename: str
    size: int
    kind: str = "project"


class UploadedRunPayload(BaseModel):
    cliente: str = "Cliente não informado"
    obra: str = "Obra não informada"
    prazo: int = 8
    unidade: str = "semanas"
    jornada_h_dia: float = 8
    dias_semana: int = 5
    eficiencia: float = 0.75
    premissas_internas: str = ""
    files: List[str] = Field(default_factory=list)
    cost_file_id: Optional[str] = None


def _is_hosted_mode() -> bool:
    return _env("HOSTED_MODE", "false").lower() == "true"


def _write_env(settings: SettingsPayload):
    if _is_hosted_mode():
        return
    api_key = settings.openai_api_key.strip() or _env("OPENAI_API_KEY", "")
    model = settings.openai_model.strip() or "gpt-5.2"
    reasoning = (settings.reasoning_effort or "high").strip()
    use_mock = "true" if settings.use_mock_agents else "false"
    ENV_PATH.write_text(
        f"OPENAI_API_KEY={api_key}\n"
        f"OPENAI_MODEL={model}\n"
        f"OPENAI_REASONING_EFFORT={reasoning}\n"
        f"USE_MOCK_AGENTS={use_mock}\n"
        "CORS_ORIGINS=*\n",
        encoding="utf-8",
    )
    os.environ["OPENAI_API_KEY"] = api_key
    os.environ["OPENAI_MODEL"] = model
    os.environ["OPENAI_REASONING_EFFORT"] = reasoning
    os.environ["USE_MOCK_AGENTS"] = use_mock


def _safe_name(name: str) -> str:
    base = Path(name or "arquivo").name
    return "".join(ch if ch.isalnum() or ch in ".-_ ()[]" else "_" for ch in base)[:180] or "arquivo"


def _meta_path(file_id: str) -> Path:
    return UPLOAD_DIR / f"{file_id}.json"


def _blob_path(file_id: str) -> Path:
    return UPLOAD_DIR / f"{file_id}.bin"


def _load_upload(file_id: str) -> tuple[str, bytes]:
    if not file_id or not file_id.replace("-", "").isalnum():
        raise ValueError("ID de arquivo inválido")
    meta_file = _meta_path(file_id)
    blob_file = _blob_path(file_id)
    if not meta_file.exists() or not blob_file.exists():
        raise FileNotFoundError(f"Upload não encontrado ou expirado: {file_id}")
    meta = json.loads(meta_file.read_text(encoding="utf-8"))
    return meta.get("filename") or "arquivo", blob_file.read_bytes()


def _cleanup_old_uploads(max_age_hours: int = 12) -> None:
    cutoff = time.time() - max_age_hours * 3600
    for path in UPLOAD_DIR.glob("*"):
        try:
            if path.stat().st_mtime < cutoff:
                path.unlink(missing_ok=True)
        except Exception:
            pass


app = FastAPI(title="Orquestra Biasi - Agentes Reais", version="1.1.0")
origins = [item.strip() for item in _env("CORS_ORIGINS", "*").split(",") if item.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins if origins != ["*"] else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

FRONTEND_PATH = ROOT_PATH / "frontend" / "index.html"


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
        "upload_mode": "staged-per-file",
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


@app.post("/api/uploads")
async def upload_one(file: UploadFile = File(...), kind: str = Form("project")):
    _cleanup_old_uploads()
    raw = await file.read()
    file_id = uuid.uuid4().hex
    filename = _safe_name(file.filename or "arquivo")
    _blob_path(file_id).write_bytes(raw)
    _meta_path(file_id).write_text(
        json.dumps({"file_id": file_id, "filename": filename, "size": len(raw), "kind": kind, "created_at": time.time()}, ensure_ascii=False),
        encoding="utf-8",
    )
    return UploadedFileRef(file_id=file_id, filename=filename, size=len(raw), kind=kind)


async def _stream_pipeline(project: ProjectInput, uploaded_items: list[tuple[str, bytes]], cost_item: tuple[str, bytes] | None = None):
    docs = []
    cost_path = None
    try:
        yield json.dumps({"type": "status", "message": "Servidor recebeu a solicitação. Preparando arquivos..."}, ensure_ascii=False) + "\n"
        async for event, doc in extract_raw_uploads_progress(uploaded_items):
            yield json.dumps(event, ensure_ascii=False) + "\n"
            if doc is not None:
                docs.append(doc)
        yield json.dumps({"type": "status", "message": f"Documentos preparados: {len(docs)}", "documents": [d.model_dump() for d in docs]}, ensure_ascii=False) + "\n"

        if cost_item:
            yield json.dumps({"type": "status", "message": "Lendo planilha de custos Biasi..."}, ensure_ascii=False) + "\n"
            filename, raw = cost_item
            suffix = Path(filename).suffix or ".xlsx"
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
            tmp.write(raw)
            tmp.close()
            cost_path = tmp.name

        async for event in run_pipeline_stream(project, docs, cost_path):
            yield json.dumps(event, ensure_ascii=False) + "\n"
    except Exception as exc:
        yield json.dumps({"type": "error", "message": str(exc)}, ensure_ascii=False) + "\n"
    finally:
        if cost_path:
            try:
                os.unlink(cost_path)
            except Exception:
                pass


@app.post("/api/runs/stream-from-uploads")
async def run_stream_from_uploads(payload: UploadedRunPayload):
    project = ProjectInput(
        cliente=payload.cliente,
        obra=payload.obra,
        prazo=payload.prazo,
        unidade=payload.unidade,
        jornada_h_dia=payload.jornada_h_dia,
        dias_semana=payload.dias_semana,
        eficiencia=payload.eficiencia,
        premissas_internas=payload.premissas_internas,
    )
    uploaded_items = [_load_upload(file_id) for file_id in payload.files]
    cost_item = _load_upload(payload.cost_file_id) if payload.cost_file_id else None
    return StreamingResponse(_stream_pipeline(project, uploaded_items, cost_item), media_type="application/x-ndjson")


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
        cliente=cliente,
        obra=obra,
        prazo=prazo,
        unidade=unidade,
        jornada_h_dia=jornada_h_dia,
        dias_semana=dias_semana,
        eficiencia=eficiencia,
        premissas_internas=premissas_internas,
    )
    uploaded_items = [(f.filename or "arquivo", await f.read()) for f in files or []]
    cost_item = None
    if cost_file and cost_file.filename:
        cost_item = (cost_file.filename, await cost_file.read())
    return StreamingResponse(_stream_pipeline(project, uploaded_items, cost_item), media_type="application/x-ndjson")


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
