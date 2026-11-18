"""Planejador seguro do Agente Autônomo 5.4.0."""
from __future__ import annotations
import json
from core.autonomous_agent import AgenteAutonomo


def autonomous_planner(parameters=None, **_context) -> str:
    p = parameters or {}
    objetivo = str(p.get("objective") or "").strip()
    passos = p.get("steps") or []
    if isinstance(passos, str):
        try:
            passos = json.loads(passos)
        except Exception:
            return json.dumps({"ok": False, "erro": "steps deve ser uma lista JSON"}, ensure_ascii=False)
    if not passos and objetivo:
        # Sem passos explícitos: o próprio I.S.A. planeja com as ferramentas descritas (nunca executa).
        try:
            from core.isa import obter_isa
            isa = obter_isa()
            if not isa.catalogo.nomes():
                from actions.smart_agent import _preparar
                _preparar(isa)
            plano = isa.planejar_com_llm(objetivo)
            return json.dumps({"ok": True, "plano": plano.como_dict()}, ensure_ascii=False)
        except Exception as exc:
            return json.dumps({"ok": False, "erro": str(exc)}, ensure_ascii=False)
    try:
        plano = AgenteAutonomo(max_passos=int(p.get("max_steps") or 12)).criar_plano(objetivo, passos)
        return json.dumps({"ok": True, "plano": plano.como_dict()}, ensure_ascii=False)
    except Exception as exc:
        return json.dumps({"ok": False, "erro": str(exc)}, ensure_ascii=False)


TOOL = {
    "name": "autonomous_planner",
    "description": (
        "Cria um plano de múltiplas etapas para o T.O.R.V.I.S. O planejador apenas estrutura e classifica risco; "
        "a execução real continua passando pelas ferramentas registradas e pelas confirmações do I.S.A."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "objective": {"type": "STRING", "description": "Objetivo da tarefa"},
            "steps": {"type": "ARRAY", "description": "Lista de passos com ferramenta e argumentos (opcional: sem passos, o I.S.A. planeja sozinho)", "items": {"type": "OBJECT"}},
            "max_steps": {"type": "INTEGER", "description": "Limite de passos do plano"},
        },
    },
    "handler": autonomous_planner,
    "tier": "core",
    "brief": "Cria planos seguros em etapas e marca ações que exigem confirmação.",
}
