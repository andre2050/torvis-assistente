"""Ferramenta de inspeção/seleção da Inteligência Adaptativa 5.5.0."""
from __future__ import annotations
import json
from core.adaptive_intelligence import RecursosSistema, obter_adaptativo


def adaptive_intelligence(parameters=None, **_context) -> str:
    p = parameters or {}
    modo_acao = str(p.get("action") or "status").strip().lower()
    motor = obter_adaptativo()

    if modo_acao == "set_mode":
        try:
            return json.dumps({"ok": True, "mode": motor.definir_modo(str(p.get("mode") or "equilibrado"))}, ensure_ascii=False)
        except Exception as exc:
            return json.dumps({"ok": False, "erro": str(exc)}, ensure_ascii=False)

    if modo_acao == "select":
        modalidade = str(p.get("modality") or "texto").strip().lower()
        recursos = None
        if any(k in p for k in ("cpu", "memory", "gpu", "battery")):
            recursos = RecursosSistema(
                cpu_percent=float(p.get("cpu") or 0),
                memoria_percent=float(p.get("memory") or 0),
                gpu_disponivel=bool(p.get("gpu", False)),
                bateria=bool(p.get("battery", False)),
            )
        return json.dumps(motor.selecionar(modalidade, recursos), ensure_ascii=False)

    if modo_acao == "status":
        return json.dumps({"ok": True, "status": motor.status(), "motores": motor.listar()}, ensure_ascii=False)

    return json.dumps({"ok": False, "erro": "action deve ser status, set_mode ou select"}, ensure_ascii=False)


TOOL = {
    "name": "adaptive_intelligence",
    "description": (
        "Seleciona a estratégia mais adequada entre capacidades disponíveis do T.O.R.V.I.S conforme recursos, "
        "velocidade, qualidade e privacidade. Não envia dados nem instala modelos automaticamente."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "status, set_mode ou select"},
            "mode": {"type": "STRING", "description": "eco, equilibrado, desempenho ou privacidade"},
            "modality": {"type": "STRING", "description": "texto, visao, sequencia ou classificacao"},
            "cpu": {"type": "NUMBER", "description": "CPU em porcentagem para simular/fornecer recursos"},
            "memory": {"type": "NUMBER", "description": "RAM em porcentagem"},
            "gpu": {"type": "BOOLEAN", "description": "GPU disponível"},
            "battery": {"type": "BOOLEAN", "description": "Executando em bateria"},
        },
    },
    "handler": adaptive_intelligence,
    "tier": "core",
    "brief": "Escolhe automaticamente a capacidade mais adequada ao estado do computador.",
}
