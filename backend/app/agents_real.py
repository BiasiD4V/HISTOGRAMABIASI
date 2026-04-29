from __future__ import annotations
import json, os, re
from typing import Any, Dict

def extract_json(text: str) -> Dict[str, Any]:
    text = (text or "").strip()
    text = re.sub(r"^```(?:json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    try:
        return json.loads(text)
    except Exception:
        pass
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        return json.loads(match.group(0))
    raise ValueError(f"Resposta não trouxe JSON válido: {text[:500]}")

async def run_agent_json(agent_name: str, instructions: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Executa um agente real via OpenAI Agents SDK e retorna JSON estruturado."""
    if os.getenv("USE_MOCK_AGENTS", "false").lower() == "true":
        return _mock(agent_name, payload)
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("Chave OpenAI não configurada. Abra a tela de Configuração, cole sua chave e salve antes de rodar agentes reais.")

    from agents import Agent, Runner
    agent_model = os.getenv("OPENAI_MODEL", "gpt-5.2")
    reasoning = os.getenv("OPENAI_REASONING_EFFORT", "high")
    # O OpenAI Agents SDK pode variar conforme a versao instalada. Para manter o app robusto,
    # usamos o modelo escolhido diretamente e registramos o esforco de raciocinio nas instrucoes.
    instructions = instructions + f"\n\nParametro operacional solicitado: reasoning_effort={reasoning}. Trabalhe com criterio tecnico, explique criterios na saida e retorne JSON valido."
    agent = Agent(name=agent_name, instructions=instructions, model=agent_model)
    prompt = (
        "Entrada em JSON:\n"
        + json.dumps(payload, ensure_ascii=False, indent=2)[:250000]
        + "\n\nResponda somente com JSON válido. Não use markdown."
    )
    result = await Runner.run(agent, prompt)
    return extract_json(result.final_output)

def _mock(agent_name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    text = json.dumps(payload, ensure_ascii=False).lower()
    if "ScopeReader" in agent_name:
        disciplinas = []
        if any(k in text for k in ["elétrica", "eletrica", "spda", "cabo", "painel"]): disciplinas.append("INSTALAÇÕES ELÉTRICAS")
        if any(k in text for k in ["tubulação", "tubulacao", "hidrául", "hidraul", "utilidades", "encanador"]): disciplinas.append("INSTALAÇÕES HIDRÁULICAS / TUBULAÇÃO")
        if any(k in text for k in ["civil", "concreto", "base", "fundação"]): disciplinas.append("CIVIL")
        if any(k in text for k in ["instrument", "automação", "automacao", "plc"]): disciplinas.append("AUTOMAÇÃO / INSTRUMENTAÇÃO")
        if not disciplinas: disciplinas = ["INSTALAÇÕES INDUSTRIAIS"]
        return {"summary":"Escopo identificado em modo mock", "disciplinas":disciplinas, "sistemas":disciplinas, "atividades":["mobilização", "infraestrutura", "montagem", "testes"], "quantitativos":[{"item":"cabos", "valor":1800, "unidade":"m", "trecho_evidencia":"mock"}], "frentes_sugeridas":max(1, len(disciplinas)), "evidencias":["modo mock"], "lacunas":["validar quantitativos"]}
    if "EAPBuilder" in agent_name:
        return {"summary":"EAP preliminar gerada", "eap":[
            {"etapa":"INSTALAÇÕES ELÉTRICAS", "subetapa":"INFRAESTRUTURA", "hh_estimado":220, "criterio":"mock: infraestrutura proporcional ao prazo", "confianca":"baixa", "evidencia":"mock"},
            {"etapa":"INSTALAÇÕES ELÉTRICAS", "subetapa":"CABEAMENTO", "hh_estimado":420, "criterio":"mock: cabos identificados", "confianca":"baixa", "evidencia":"mock"},
            {"etapa":"INSTALAÇÕES ELÉTRICAS", "subetapa":"TESTES / AS BUILT", "hh_estimado":120, "criterio":"mock: percentual final", "confianca":"baixa", "evidencia":"mock"},
        ], "premissas":["Validar quantitativos antes de enviar ao cliente"]}
    if "ChronoPlanner" in agent_name:
        semanas = payload.get("project", {}).get("semanas") or payload.get("project", {}).get("prazo") or 8
        return {"summary":"Cronograma preliminar mock", "cronograma":[
            {"etapa":"INSTALAÇÕES ELÉTRICAS", "subetapa":"INFRAESTRUTURA", "semana_inicio":1, "semana_fim":max(2, semanas//3), "predecessoras":[], "tipo_relacao":"FS", "critica":True},
            {"etapa":"INSTALAÇÕES ELÉTRICAS", "subetapa":"CABEAMENTO", "semana_inicio":max(2, semanas//3), "semana_fim":max(3, int(semanas*0.75)), "predecessoras":["INFRAESTRUTURA"], "tipo_relacao":"SS", "critica":True},
            {"etapa":"INSTALAÇÕES ELÉTRICAS", "subetapa":"TESTES / AS BUILT", "semana_inicio":max(3, int(semanas*0.75)), "semana_fim":semanas, "predecessoras":["CABEAMENTO"], "tipo_relacao":"FS", "critica":True},
        ], "caminho_critico":["INFRAESTRUTURA", "CABEAMENTO", "TESTES / AS BUILT"], "alertas":[]}
    if "ProdutivIA" in agent_name:
        return {"summary":"Equipe base mock", "equipe_base":[
            {"funcao":"Eletricista", "tipo":"direta", "quantidade":4, "disciplina":"Elétrica", "criterio":"mock por HH"},
            {"funcao":"Ajudante de Eletricista", "tipo":"direta", "quantidade":3, "disciplina":"Elétrica", "criterio":"mock por HH"},
            {"funcao":"Encarregado Elétrico", "tipo":"direta", "quantidade":1, "disciplina":"Elétrica", "criterio":"mock por frente"},
            {"funcao":"Supervisor", "tipo":"indireta", "quantidade":1, "disciplina":"Gestão", "criterio":"mock"},
            {"funcao":"Téc. Segurança", "tipo":"indireta", "quantidade":1, "disciplina":"SMS", "criterio":"mock"}
        ], "alertas":["mock"]}
    if "EngCheck" in agent_name:
        return {"summary":"Validação mock concluída", "status":"aprovado_com_ressalvas", "alertas":[{"severidade":"atencao", "tema":"base", "descricao":"Modo mock; validar com agentes reais", "recomendacao":"Desativar USE_MOCK_AGENTS"}], "checklist_revisao":["validar escopo", "validar quantitativos", "validar custo"]}
    if "PropostaNarrator" in agent_name:
        return {"summary":"Resumo mock", "paragrafo_mobilizacao":"Histograma preliminar gerado em modo mock para validação de fluxo.", "bullets_premissas":["Validar quantitativos"], "texto_memoria_calculo":"Cálculo determinístico aplicado no backend."}
    return {"summary": f"{agent_name} executado em mock"}

SCOPE_READER_INSTRUCTIONS = """
Você é o ScopeReader Biasi. Leia documentos técnicos de obras industriais e extraia escopo, disciplinas, sistemas, atividades, quantitativos, frentes de trabalho, evidências e lacunas.
Não estime mão de obra nem custo. Diferencie dado encontrado de premissa.
Retorne JSON com exatamente estas chaves: summary, disciplinas[], sistemas[], atividades[], quantitativos[{item, valor, unidade, trecho_evidencia}], frentes_sugeridas, evidencias[], lacunas[].
"""

EAP_BUILDER_INSTRUCTIONS = """
Você é o EAPBuilder Biasi. Transforme o escopo em EAP para histograma de mão de obra.
Crie etapas e subetapas no formato de engenharia industrial. Para cada subetapa, estime HH preliminar de forma conservadora, explique o critério e indique confiança.
Se não houver quantitativos suficientes, use faixas/percentuais preliminares e marque confiança baixa.
Retorne JSON com: summary, eap[{etapa, subetapa, hh_estimado, criterio, confianca, evidencia}], premissas[].
Exemplo: etapa INSTALAÇÕES ELÉTRICAS, subetapas INFRAESTRUTURA, CABEAMENTO, PAINÉIS/INTERLIGAÇÕES, SPDA/ATERRAMENTO, TESTES/AS BUILT.
"""

CHRONO_PLANNER_INSTRUCTIONS = """
Você é o ChronoPlanner Biasi. Distribua a EAP em semanas conforme prazo, precedências e caminho crítico preliminar.
Retorne JSON com: summary, cronograma[{etapa, subetapa, semana_inicio, semana_fim, predecessoras[], tipo_relacao, critica}], caminho_critico[], alertas[].
Use semanas inteiras; respeite o prazo informado; destaque atividades críticas.
"""

PRODUTIVIA_INSTRUCTIONS = """
Você é o ProdutivIA Biasi. Converta EAP e HH em mão de obra direta e indireta por função Biasi.
Use funções preferenciais: Eletricista, Eletricista Força e Controle, Ajudante de Eletricista, Encanador, Ajudante de Hidráulica, Ajudante Geral, Soldador/Serralheiro, Pedreiro, Instrumentista, Téc. Automação, Encarregado Elétrico, Encarregado Hidráulico, Supervisor, Engenheiro, Téc. Segurança, Almoxarife.
Retorne JSON com: summary, equipe_base[{funcao, tipo: direta|indireta, quantidade, disciplina, criterio}], alertas[].
Explique o critério de cada quantidade com base em HH, prazo, jornada, frentes e disciplina.
"""

ENGCHECK_INSTRUCTIONS = """
Você é o EngCheck Biasi. Valide o histograma, EAP, prazo, pico, custo e premissas. Seja rigoroso.
Retorne JSON com: summary, status, alertas[{severidade: critico|atencao|informativo, tema, descricao, recomendacao}], checklist_revisao[].
Não esconda risco técnico. Classifique severidade de forma conservadora.
"""

NARRATOR_INSTRUCTIONS = """
Você é o PropostaNarrator Biasi. Redija texto comercial técnico para proposta, explicando mobilização, pico, premissas, EAP e custo total de MO.
Não esconda ressalvas. Retorne JSON com: summary, paragrafo_mobilizacao, bullets_premissas[], texto_memoria_calculo.
"""
