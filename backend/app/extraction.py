from __future__ import annotations

import asyncio
import io
import multiprocessing as mp
import queue
from typing import AsyncGenerator, List, Tuple

from fastapi import UploadFile

from .schemas import DocumentText

MAX_CHARS_PER_FILE = 70_000
MAX_PDF_PAGES = 6
EXTRACTION_TIMEOUT_SECONDS = 25
MAX_RAW_BYTES_FOR_FULL_TEXT = 25 * 1024 * 1024


def _trim(text: str) -> str:
    text = text or ""
    if len(text) > MAX_CHARS_PER_FILE:
        return text[:MAX_CHARS_PER_FILE] + "\n\n[TRUNCADO PARA PROCESSAMENTO]"
    return text


async def extract_uploads(files: List[UploadFile]) -> List[DocumentText]:
    docs: List[DocumentText] = []
    async for _event, doc in extract_uploads_progress(files):
        if doc is not None:
            docs.append(doc)
    return docs


async def extract_raw_uploads_progress(items: List[tuple[str, bytes]]) -> AsyncGenerator[Tuple[dict, DocumentText | None], None]:
    items = items or []
    total = len(items)
    yield {"type": "status", "message": f"Recebi {total} arquivo(s). Iniciando extração segura..."}, None
    for idx, (name, raw) in enumerate(items, start=1):
        name = name or f"arquivo_{idx}"
        size_mb = len(raw or b"") / 1024 / 1024
        yield {"type": "status", "message": f"Extraindo {idx}/{total}: {name} ({size_mb:.2f} MB)"}, None
        doc = await _safe_extract_document(name, raw, idx, total)
        if doc.status == "ok":
            yield {"type": "status", "message": f"OK {idx}/{total}: {name} ({doc.chars} caracteres)"}, doc
        elif doc.error == "timeout":
            yield {"type": "status", "message": f"Tempo limite em {name}; seguindo com os demais."}, doc
        else:
            yield {"type": "status", "message": f"Extração parcial em {name}; seguindo com os demais."}, doc
    yield {"type": "status", "message": "Extração concluída. Iniciando agentes..."}, None


async def extract_uploads_progress(files: List[UploadFile]) -> AsyncGenerator[Tuple[dict, DocumentText | None], None]:
    files = files or []
    total = len(files)
    yield {"type": "status", "message": f"Recebi {total} arquivo(s). Iniciando extração segura..."}, None
    for idx, file in enumerate(files, start=1):
        name = file.filename or f"arquivo_{idx}"
        raw = await file.read()
        size_mb = len(raw or b"") / 1024 / 1024
        yield {"type": "status", "message": f"Extraindo {idx}/{total}: {name} ({size_mb:.2f} MB)"}, None
        doc = await _safe_extract_document(name, raw, idx, total)
        if doc.status == "ok":
            yield {"type": "status", "message": f"OK {idx}/{total}: {name} ({doc.chars} caracteres)"}, doc
        elif doc.error == "timeout":
            yield {"type": "status", "message": f"Tempo limite em {name}; seguindo com os demais."}, doc
        else:
            yield {"type": "status", "message": f"Extração parcial em {name}; seguindo com os demais."}, doc
    yield {"type": "status", "message": "Extração concluída. Iniciando agentes..."}, None


async def _safe_extract_document(name: str, raw: bytes, idx: int, total: int) -> DocumentText:
    try:
        text, status = await asyncio.to_thread(_extract_raw_with_hard_timeout, name, raw, EXTRACTION_TIMEOUT_SECONDS)
        text = _trim(text)
        return DocumentText(filename=name, status=status, text=text, chars=len(text))
    except TimeoutError:
        text = _fallback_reference_text(name, raw, f"Extração interrompida após {EXTRACTION_TIMEOUT_SECONDS}s")
        return DocumentText(filename=name, status="parcial", text=text, chars=len(text), error="timeout")
    except Exception as exc:
        text = _fallback_reference_text(name, raw, f"Falha ao extrair texto: {exc}")
        return DocumentText(filename=name, status="parcial", text=text, chars=len(text), error=str(exc))


def _fallback_reference_text(name: str, raw: bytes, reason: str) -> str:
    size_mb = len(raw or b"") / 1024 / 1024
    return (
        f"[Arquivo usado como referência nominal: {name}]\n"
        f"Motivo: {reason}.\n"
        f"Tamanho: {size_mb:.2f} MB.\n"
        "O texto interno não foi extraído com segurança dentro do limite, mas o nome do arquivo deve ser considerado como evidência de escopo/disciplina."
    )


def _worker_extract(name: str, raw: bytes, output_queue) -> None:
    try:
        output_queue.put(("ok", _extract_raw(name, raw)))
    except Exception as exc:
        output_queue.put(("error", str(exc)))


def _extract_raw_with_hard_timeout(name: str, raw: bytes, timeout_seconds: int) -> tuple[str, str]:
    lower = (name or "").lower()

    if len(raw or b"") > MAX_RAW_BYTES_FOR_FULL_TEXT and lower.endswith(".pdf"):
        return _fallback_reference_text(name, raw, "PDF grande demais para extração completa automática"), "parcial"

    try:
        ctx = mp.get_context("fork")
    except ValueError:
        ctx = mp.get_context("spawn")

    output_queue = ctx.Queue(maxsize=1)
    process = ctx.Process(target=_worker_extract, args=(name, raw, output_queue), daemon=True)
    process.start()
    process.join(timeout_seconds)

    if process.is_alive():
        process.terminate()
        process.join(3)
        if process.is_alive():
            process.kill()
            process.join(3)
        raise TimeoutError(f"Timeout extraindo {name}")

    try:
        status, payload = output_queue.get_nowait()
    except queue.Empty:
        if process.exitcode == 0:
            return "", "parcial"
        raise RuntimeError(f"Processo de extração terminou sem retorno para {name}")

    if status == "error":
        raise RuntimeError(payload)
    return payload


def _extract_raw(name: str, raw: bytes) -> tuple[str, str]:
    lower = name.lower()
    if lower.endswith((".txt", ".csv", ".md", ".json")):
        return raw.decode("utf-8", errors="ignore"), "ok"
    if lower.endswith(".pdf"):
        return _extract_pdf(raw), "ok"
    if lower.endswith(".docx"):
        return _extract_docx(raw), "ok"
    if lower.endswith((".xlsx", ".xlsm", ".xls")):
        return _extract_xlsx(raw), "ok"
    return f"[Arquivo anexado, mas tipo não extraído automaticamente: {name}]", "parcial"


def _extract_pdf(raw: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(raw), strict=False)
    pages = []
    for page_index, page in enumerate(reader.pages[:MAX_PDF_PAGES], start=1):
        try:
            page_text = page.extract_text() or ""
            if page_text.strip():
                pages.append(f"--- PÁGINA {page_index} ---\n{page_text}")
        except Exception:
            pages.append(f"--- PÁGINA {page_index} ---\n[Texto não extraído desta página]")
    return "\n".join(pages)


def _extract_docx(raw: bytes) -> str:
    from docx import Document

    doc = Document(io.BytesIO(raw))
    blocks = [p.text for p in doc.paragraphs if p.text.strip()]
    for table in doc.tables:
        for row in table.rows:
            vals = [c.text.strip() for c in row.cells]
            if any(vals):
                blocks.append(" | ".join(vals))
    return "\n".join(blocks)


def _extract_xlsx(raw: bytes) -> str:
    from openpyxl import load_workbook

    wb = load_workbook(io.BytesIO(raw), data_only=True, read_only=True)
    chunks = []
    for ws in wb.worksheets[:8]:
        chunks.append(f"### PLANILHA: {ws.title}")
        max_rows = min(ws.max_row, 160)
        max_cols = min(ws.max_column, 45)
        for row in ws.iter_rows(min_row=1, max_row=max_rows, max_col=max_cols, values_only=True):
            vals = [str(v).strip() if v is not None else "" for v in row]
            if any(vals):
                chunks.append(";".join(vals))
    return "\n".join(chunks)
