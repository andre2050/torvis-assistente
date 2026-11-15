"""Controle de uso diário da IA: o app não morre no meio da tarde.

O cooldown que já existe cuida do minuto (cota por minuto). Este módulo cuida do
dia: conta quantas respostas cada modelo entregou hoje e, quando um teto é
configurado, avisa e evita queimar a cota restante em tarefas de fundo.

Teto desligado por padrão (0 = sem limite), porque a cota depende do plano de
cada chave. Para ligar: variável de ambiente TORVIS_LIMITE_DIARIO_IA=300
ou config["limite_diario_ia"] = 300.
"""
from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path

from core.paths import STATE_DIR

ARQUIVO = STATE_DIR / "uso_ia.json"


def _hoje() -> str:
    return date.today().isoformat()


def _ler() -> dict:
    try:
        dados = json.loads(Path(ARQUIVO).read_text(encoding="utf-8"))
        return dados if isinstance(dados, dict) else {}
    except (OSError, ValueError):
        return {}


def _gravar(dados: dict) -> None:
    try:
        ARQUIVO.parent.mkdir(parents=True, exist_ok=True)
        temporario = ARQUIVO.with_suffix(".tmp")
        temporario.write_text(json.dumps(dados, indent=2), encoding="utf-8")
        temporario.replace(ARQUIVO)
    except OSError:
        pass


def limite() -> int:
    """Teto diário configurado; 0 significa sem teto."""
    bruto = os.environ.get("TORVIS_LIMITE_DIARIO_IA", "").strip()
    if bruto.isdigit():
        return int(bruto)
    return 0


def _do_dia(dados: dict | None = None) -> dict:
    dados = dados if dados is not None else _ler()
    dia = dados.get(_hoje())
    if not isinstance(dia, dict):
        dia = {"modelos": {}, "total": 0}
        dados[_hoje()] = dia
    dia.setdefault("modelos", {})
    dia.setdefault("total", 0)
    return dia


def contar(modelo: str) -> int:
    """Registra uma resposta entregue e devolve o total de hoje."""
    if not modelo:
        return 0
    dados = _ler()
    dia = _do_dia(dados)
    dia["modelos"][modelo] = int(dia["modelos"].get(modelo, 0)) + 1
    dia["total"] = int(dia["total"]) + 1
    _gravar(dados)
    return dia["total"]


def total_hoje() -> int:
    return int(_do_dia().get("total", 0))


def restante() -> int | None:
    teto = limite()
    if not teto:
        return None
    return max(0, teto - total_hoje())


def permitido() -> bool:
    """False somente quando há teto configurado e ele já foi atingido."""
    teto = limite()
    return True if not teto else total_hoje() < teto


def aviso() -> str:
    """Mensagem para a interface, vazia quando não há nada a dizer."""
    teto = limite()
    if not teto:
        return ""
    usado = total_hoje()
    if usado >= teto:
        return f"Teto diário de IA atingido ({usado}/{teto}). O app segue funcionando sem a IA até amanhã."
    if usado >= teto * 0.8:
        return f"Já foram {usado} de {teto} respostas de IA hoje."
    return ""


def resumo() -> str:
    dados = _ler()
    dia = dados.get(_hoje()) or {}
    modelos = dia.get("modelos") or {}
    if not modelos:
        return "nenhuma resposta de IA registrada hoje"
    linhas = [f"total hoje: {dia.get('total', 0)}" + (f" (teto {limite()})" if limite() else " (sem teto)")]
    linhas += [f"  {m}: {n}" for m, n in sorted(modelos.items(), key=lambda p: -p[1])]
    return "\n".join(linhas)


def zerar() -> None:
    dados = _ler()
    dados.pop(_hoje(), None)
    _gravar(dados)
