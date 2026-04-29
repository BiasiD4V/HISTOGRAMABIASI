from __future__ import annotations
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

class ProjectInput(BaseModel):
    cliente: str = "Cliente não informado"
    obra: str = "Obra não informada"
    prazo: int = 8
    unidade: str = "semanas"
    jornada_h_dia: float = 8
    dias_semana: int = 5
    eficiencia: float = 0.75
    premissas_internas: str = ""

    @property
    def semanas(self) -> int:
        return int(self.prazo * 4 if self.unidade.lower().startswith("m") else self.prazo)

class DocumentText(BaseModel):
    filename: str
    status: str
    text: str
    chars: int = 0
    error: Optional[str] = None

class AgentStep(BaseModel):
    agent_id: str
    agent_name: str
    status: str = "concluido"
    summary: str = ""
    details: List[str] = Field(default_factory=list)
    evidence: List[str] = Field(default_factory=list)
    output: Dict[str, Any] = Field(default_factory=dict)
