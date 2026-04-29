from __future__ import annotations
import json, math, tempfile
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional
from .schemas import AgentStep, DocumentText, ProjectInput
from .agents_real import (
    run_agent_json, SCOPE_READER_INSTRUCTIONS, EAP_BUILDER_INSTRUCTIONS,
    CHRONO_PLANNER_INSTRUCTIONS, PRODUTIVIA_INSTRUCTIONS, ENGCHECK_INSTRUCTIONS,
    NARRATOR_INSTRUCTIONS,
)
from .cost_base import calculate_costs, load_default_costs, import_costs_from_xlsx

AGENT_META = {
    "scope": ("ScopeReader Biasi", "Levanta escopo, disciplinas, quantitativos e evidências."),
    "eap": ("EAPBuilder Biasi", "Cria etapas, subetapas, HH e percentuais."),
    "chrono": ("ChronoPlanner Biasi", "Distribui EAP no prazo e caminho crítico."),
    "prod": ("ProdutivIA Biasi", "Transforma HH em equipe direta/indireta."),
    "mobiliza": ("Mobiliza Biasi", "Gera curva semanal por função."),
    "cost": ("CostCheck Biasi", "Calcula custo total e memória de cálculo."),
    "check": ("EngCheck Biasi", "Valida coerência técnica e riscos."),
    "narrator": ("PropostaNarrator Biasi", "Redige texto executivo e premissas."),
}

def docs_to_context(docs: List[DocumentText]) -> str:
    chunks = []
    for d in docs:
        chunks.append(f"### ARQUIVO: {d.filename}\nSTATUS: {d.status}\nCHARS: {d.chars}\n{d.text[:50000]}")
    return "\n\n".join(chunks)

async def run_pipeline_stream(
    project: ProjectInput,
    docs: List[DocumentText],
    cost_xlsx_path: Optional[str] = None,
) -> AsyncGenerator[Dict[str, Any], None]:
    state: Dict[str, Any] = {"project": project.model_dump(), "documents": [d.model_dump() for d in docs], "steps": []}
    context = docs_to_context(docs)
    base_payload = {"project": project.model_dump(), "documentos": context, "premissas_internas": project.premissas_internas}

    costs = load_default_costs()
    if cost_xlsx_path:
        try:
            costs = import_costs_from_xlsx(cost_xlsx_path)
            yield {"type":"status", "message":f"Base de custos importada da planilha enviada ({len(costs)} funções)."}
        except Exception as exc:
            yield {"type":"status", "message":f"Não foi possível importar a planilha de custos enviada; usando base embutida. Motivo: {exc}"}

    async def start(agent_id: str):
        name, desc = AGENT_META[agent_id]
        yield {"type": "agent_start", "agent_id": agent_id, "agent_name": name, "description": desc}

    async def finish(agent_id: str, step: AgentStep):
        state["steps"].append(step.model_dump())
        yield {"type": "agent_end", "step": step.model_dump(), "state_preview": _preview_state(state)}

    # 1 ScopeReader
    async for ev in start("scope"): yield ev
    scope = await run_agent_json("ScopeReader Biasi", SCOPE_READER_INSTRUCTIONS, base_payload)
    state["scope"] = scope
    step = AgentStep(agent_id="scope", agent_name="ScopeReader Biasi", summary=scope.get("summary", "Escopo extraído"), details=_details_from(scope, ["disciplinas","sistemas","frentes_sugeridas","lacunas"]), evidence=scope.get("evidencias", [])[:10], output=scope)
    async for ev in finish("scope", step): yield ev

    # 2 EAPBuilder
    async for ev in start("eap"): yield ev
    eap = await run_agent_json("EAPBuilder Biasi", EAP_BUILDER_INSTRUCTIONS, {"project": project.model_dump(), "scope": scope})
    eap = normalize_eap(eap)
    state["eap"] = eap
    step = AgentStep(agent_id="eap", agent_name="EAPBuilder Biasi", summary=eap.get("summary", "EAP gerada"), details=[f"{x['etapa']} / {x['subetapa']}: {x['percent_etapa']}% da etapa, {x['percent_total']}% do total, {x['hh_estimado']} HH" for x in eap.get("eap", [])[:14]], evidence=[x.get("criterio", "") for x in eap.get("eap", [])[:10]], output=eap)
    async for ev in finish("eap", step): yield ev

    # 3 ChronoPlanner
    async for ev in start("chrono"): yield ev
    chrono = await run_agent_json("ChronoPlanner Biasi", CHRONO_PLANNER_INSTRUCTIONS, {"project": project.model_dump(), "scope": scope, "eap": eap})
    chrono = normalize_chrono(chrono, project, eap)
    state["chrono"] = chrono
    step = AgentStep(agent_id="chrono", agent_name="ChronoPlanner Biasi", summary=chrono.get("summary", "Cronograma criado"), details=[f"{x.get('subetapa')}: S{x.get('semana_inicio')}-S{x.get('semana_fim')} | crítica={x.get('critica')}" for x in chrono.get("cronograma", [])[:16]], evidence=chrono.get("caminho_critico", [])[:10], output=chrono)
    async for ev in finish("chrono", step): yield ev

    # 4 ProdutivIA
    async for ev in start("prod"): yield ev
    prod = await run_agent_json("ProdutivIA Biasi", PRODUTIVIA_INSTRUCTIONS, {"project": project.model_dump(), "scope": scope, "eap": eap, "cronograma": chrono})
    prod = normalize_prod(prod, eap, project)
    state["produtividade"] = prod
    step = AgentStep(agent_id="prod", agent_name="ProdutivIA Biasi", summary=prod.get("summary", "Equipe base calculada"), details=[f"{x['funcao']} ({x['tipo']}): {x['quantidade']} - {x.get('criterio','')}" for x in prod.get("equipe_base", [])], evidence=["Quantidade = função do HH, prazo, jornada, dias/semana, eficiência e disciplina."], output=prod)
    async for ev in finish("prod", step): yield ev

    # 5 Mobiliza deterministic
    async for ev in start("mobiliza"): yield ev
    mobiliza = build_histogram(project, prod, chrono)
    state["mobilizacao"] = mobiliza
    step = AgentStep(agent_id="mobiliza", agent_name="Mobiliza Biasi", summary=f"Histograma semanal gerado com pico de {mobiliza['pico_total']} pessoas em S{mobiliza['semana_pico']}", details=[f"Equipe média: {mobiliza['equipe_media']}", f"Semanas: {mobiliza['semanas']}", f"Funções: {', '.join(mobiliza['funcoes'])}"], evidence=["Curva usa rampa de subida até montagem principal e rampa de saída após testes."], output=mobiliza)
    async for ev in finish("mobiliza", step): yield ev

    # 6 CostCheck deterministic
    async for ev in start("cost"): yield ev
    cost = calculate_costs(mobiliza["weekly_histogram"], project.dias_semana, project.jornada_h_dia, costs)
    state["custos"] = cost
    formatted_total = _brl(cost["total_mo"])
    step = AgentStep(agent_id="cost", agent_name="CostCheck Biasi", summary=f"Custo total de MO: {formatted_total}", details=[f"{k}: {_brl(v)}" for k,v in cost.get("by_role", {}).items()], evidence=[cost.get("cost_formula", "")], output=cost)
    async for ev in finish("cost", step): yield ev

    # 7 EngCheck
    async for ev in start("check"): yield ev
    check = await run_agent_json("EngCheck Biasi", ENGCHECK_INSTRUCTIONS, {"project": project.model_dump(), "scope": scope, "eap": eap, "cronograma": chrono, "produtividade": prod, "mobilizacao": mobiliza, "custos": cost})
    state["validacao"] = check
    step = AgentStep(agent_id="check", agent_name="EngCheck Biasi", summary=check.get("summary", "Validação concluída"), details=[f"{a.get('severidade')}: {a.get('descricao')}" for a in check.get("alertas", [])], evidence=check.get("checklist_revisao", [])[:12], output=check)
    async for ev in finish("check", step): yield ev

    # 8 Narrator
    async for ev in start("narrator"): yield ev
    narrator = await run_agent_json("PropostaNarrator Biasi", NARRATOR_INSTRUCTIONS, {"project": project.model_dump(), "scope": scope, "eap": eap, "cronograma": chrono, "produtividade": prod, "mobilizacao": mobiliza, "custos": cost, "validacao": check})
    state["resumo"] = narrator
    step = AgentStep(agent_id="narrator", agent_name="PropostaNarrator Biasi", summary=narrator.get("summary", "Resumo gerado"), details=[narrator.get("paragrafo_mobilizacao", "")], evidence=narrator.get("bullets_premissas", [])[:12], output=narrator)
    async for ev in finish("narrator", step): yield ev

    yield {"type": "final", "result": state}

def normalize_eap(eap: Dict[str, Any]) -> Dict[str, Any]:
    rows = eap.get("eap") or eap.get("items") or []
    if not rows:
        rows = [{"etapa":"INSTALAÇÕES INDUSTRIAIS","subetapa":"EXECUÇÃO","hh_estimado":500,"criterio":"fallback por ausência de EAP","confianca":"baixa"}]
    for r in rows:
        try: r["hh_estimado"] = float(r.get("hh_estimado") or 0)
        except Exception: r["hh_estimado"] = 0
        if r["hh_estimado"] <= 0: r["hh_estimado"] = 100
        r["etapa"] = str(r.get("etapa") or "ETAPA").upper()
        r["subetapa"] = str(r.get("subetapa") or "SUBETAPA").upper()
    total = sum(float(r["hh_estimado"]) for r in rows) or 1
    by_stage: Dict[str, float] = {}
    for r in rows:
        by_stage[r["etapa"]] = by_stage.get(r["etapa"], 0.0) + float(r["hh_estimado"])
    for r in rows:
        r["percent_total"] = round(float(r["hh_estimado"]) / total * 100, 2)
        r["percent_etapa"] = round(float(r["hh_estimado"]) / (by_stage.get(r["etapa"]) or 1) * 100, 2)
    eap["eap"] = rows
    eap["total_hh"] = round(total, 2)
    eap["etapas"] = [{"etapa": k, "hh_total": round(v,2), "percent_total": round(v/total*100,2)} for k,v in by_stage.items()]
    return eap

def normalize_chrono(chrono: Dict[str, Any], project: ProjectInput, eap: Dict[str, Any]) -> Dict[str, Any]:
    weeks = project.semanas
    rows = chrono.get("cronograma") or []
    if not rows:
        # fallback sequential by EAP weights
        cursor = 1
        for item in eap.get("eap", []):
            dur = max(1, round(weeks * float(item.get("percent_total", 10)) / 100))
            rows.append({"etapa": item["etapa"], "subetapa": item["subetapa"], "semana_inicio": cursor, "semana_fim": min(weeks, cursor+dur-1), "predecessoras": [], "tipo_relacao":"FS", "critica": True})
            cursor = min(weeks, cursor+dur)
    for i, r in enumerate(rows):
        try: si = int(r.get("semana_inicio") or 1)
        except Exception: si = 1
        try: sf = int(r.get("semana_fim") or si)
        except Exception: sf = si
        r["semana_inicio"] = max(1, min(weeks, si))
        r["semana_fim"] = max(r["semana_inicio"], min(weeks, sf))
    chrono["semanas"] = weeks
    chrono["cronograma"] = rows
    return chrono

def normalize_prod(prod: Dict[str, Any], eap: Dict[str, Any], project: ProjectInput) -> Dict[str, Any]:
    rows = prod.get("equipe_base") or []
    if not rows:
        # simple fallback by HH density
        total_hh = float(eap.get("total_hh") or 500)
        capacity = max(1, project.semanas * project.dias_semana * project.jornada_h_dia * project.eficiencia)
        crew = max(2, math.ceil(total_hh / capacity))
        rows = [
            {"funcao":"Eletricista", "tipo":"direta", "quantidade":max(2, crew//2), "disciplina":"Elétrica", "criterio":"fallback por HH total"},
            {"funcao":"Ajudante de Eletricista", "tipo":"direta", "quantidade":max(1, crew//3), "disciplina":"Elétrica", "criterio":"fallback por HH total"},
            {"funcao":"Encarregado Elétrico", "tipo":"direta", "quantidade":1, "disciplina":"Elétrica", "criterio":"fallback por frente"},
            {"funcao":"Téc. Segurança", "tipo":"indireta", "quantidade":1, "disciplina":"SMS", "criterio":"fallback"},
            {"funcao":"Supervisor", "tipo":"indireta", "quantidade":1, "disciplina":"Gestão", "criterio":"fallback"},
        ]
    for r in rows:
        try: r["quantidade"] = max(0, int(round(float(r.get("quantidade") or 0))))
        except Exception: r["quantidade"] = 0
        r["tipo"] = "indireta" if str(r.get("tipo", "")).lower().startswith("ind") else "direta"
    prod["equipe_base"] = rows
    return prod

def build_histogram(project: ProjectInput, prod: Dict[str, Any], chrono: Dict[str, Any]) -> Dict[str, Any]:
    weeks = int(chrono.get("semanas") or project.semanas)
    rows = []
    funcs = []
    for r in prod.get("equipe_base", []):
        if r.get("funcao") not in funcs:
            funcs.append(r.get("funcao"))
    for w in range(1, weeks+1):
        phase_weight = _phase_weight(w, weeks)
        funcoes = {}
        direta = indireta = 0
        for item in prod.get("equipe_base", []):
            base = int(item.get("quantidade") or 0)
            if item.get("tipo") == "indireta":
                qty = max(1 if base else 0, int(round(base * indirect_weight(w, weeks))))
            else:
                qty = max(0, int(round(base * phase_weight)))
            funcoes[item["funcao"]] = max(funcoes.get(item["funcao"], 0), qty)
            if item.get("tipo") == "indireta": indireta += qty
            else: direta += qty
        rows.append({"semana": w, "funcoes": funcoes, "direta_total": direta, "indireta_total": indireta, "total": direta+indireta})
    pico = max(r["total"] for r in rows) if rows else 0
    semana_pico = next((r["semana"] for r in rows if r["total"] == pico), 1)
    media = round(sum(r["total"] for r in rows) / len(rows), 2) if rows else 0
    return {"semanas": weeks, "funcoes": funcs, "weekly_histogram": rows, "pico_total": pico, "semana_pico": semana_pico, "equipe_media": media}

def _phase_weight(w: int, weeks: int) -> float:
    x = w / max(weeks, 1)
    if x < 0.15: return 0.45 + x * 2.5
    if x < 0.72: return 1.0
    if x < 0.88: return 0.75
    return 0.40

def indirect_weight(w: int, weeks: int) -> float:
    x = w / max(weeks, 1)
    if x < 0.15: return 0.75
    if x > 0.9: return 0.75
    return 1.0

def _details_from(obj: Dict[str, Any], keys: List[str]) -> List[str]:
    return [f"{k}: {obj[k]}" for k in keys if k in obj]

def _preview_state(state: Dict[str, Any]) -> Dict[str, Any]:
    keys = ["scope", "eap", "chrono", "produtividade", "mobilizacao", "custos", "validacao", "resumo"]
    return {k: state[k] for k in keys if k in state}

def _brl(v: float) -> str:
    return (f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
