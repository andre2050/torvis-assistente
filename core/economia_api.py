"""Modo economia de API: escolhe o modelo pelo tamanho do problema.

A conta de quem usa assistente todos os dias não vem dos pedidos difíceis: vem
da centena de pedidos fáceis que foram para o modelo caro. "Que horas são",
"abre o Chrome" e "resume isso" custam o mesmo que um pedido que exige
raciocínio, se ninguém escolher.

Aqui a escolha é explícita e auditável: uma heurística olha o pedido e devolve
`rapido` ou `forte`. O que foi economizado é somado por mês, com a diferença de
preço entre os dois modelos, para a pessoa ver o número em vez de acreditar.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

from core.userdata import USERDATA_DIR

ARQUIVO = USERDATA_DIR / "economia_api.json"

# preço relativo por 1k tokens de entrada, só para comparação interna
CUSTO_RELATIVO = {"rapido": 1.0, "forte": 12.0}

_TAREFA_SIMPLES = ("que horas", "que dia", "abre ", "abrir ", "fecha ", "volume",
                   "brilho", "toca ", "pausa", "lembra", "lembrete", "anota",
                   "desliga", "liga ", "calcula", "quanto é", "qual o nome")
_TAREFA_COMPLEXA = ("analisa", "compare", "explica por que", "estratégia", "plano",
                    "contrato", "código", "refatora", "debug", "investiga",
                    "resume o documento", "avalie", "trade-off", "arquitetura")
_DECIDE_DE_VERDADE = ("decida", "decidir", "escolha entre", "trade-off", "avalie")


def _carregar() -> dict[str, Any]:
    try:
        dados = json.loads(ARQUIVO.read_text(encoding="utf-8"))
        if isinstance(dados, dict):
            return dados
    except (OSError, ValueError):
        pass
    return {"mes": time.strftime("%Y-%m"), "chamadas": [], "economia": 0.0}


def _salvar(dados: dict[str, Any]) -> None:
    try:
        ARQUIVO.parent.mkdir(parents=True, exist_ok=True)
        ARQUIVO.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass


def escolher(pedido: str, *, tamanho: int | None = None) -> dict[str, Any]:
    """Decide o modelo e explica a escolha em uma linha."""
    texto = str(pedido or "").strip().lower()
    tokens = tamanho if tamanho is not None else max(1, len(texto) // 4)
    motivos: list[str] = []

    if any(p in texto for p in _TAREFA_COMPLEXA):
        motivos.append("o pedido exige análise")
    if len(texto) > 1200:
        motivos.append("o pedido é longo")
    if re.search(r"(por que|como funciona|o que muda)", texto):
        motivos.append("pede explicação")
    if any(p in texto for p in _TAREFA_SIMPLES) and not motivos:
        motivos.append("é comando direto")
    if tokens > 4000:
        motivos.append("muito contexto")

    forte = bool(motivos) and motivos != ["é comando direto"]
    return {"modelo": "forte" if forte else "rapido",
            "motivo": "; ".join(motivos) or "pedido curto e direto",
            "tokens": tokens}


def registrar(escolha: dict[str, Any], *, tokens_saida: int = 0) -> dict[str, Any]:
    """Anota a chamada e quanto ela deixou de custar."""
    dados = _carregar()
    mes = time.strftime("%Y-%m")
    if dados.get("mes") != mes:
        dados = {"mes": mes, "chamadas": [], "economia": 0.0}
    tokens = int(escolha.get("tokens") or 0) + int(tokens_saida or 0)
    poupado = 0.0
    if escolha.get("modelo") == "rapido":
        poupado = tokens / 1000 * (CUSTO_RELATIVO["forte"] - CUSTO_RELATIVO["rapido"])
    dados["chamadas"] = (dados.get("chamadas") or [])[-2000:] + [
        {"quando": time.time(), "modelo": escolha.get("modelo"), "tokens": tokens,
         "poupado": round(poupado, 3), "motivo": escolha.get("motivo")}]
    dados["economia"] = round(float(dados.get("economia") or 0) + poupado, 3)
    _salvar(dados)
    return dados


def resumo_mes() -> dict[str, Any]:
    dados = _carregar()
    if dados.get("mes") != time.strftime("%Y-%m"):
        return {"mes": time.strftime("%Y-%m"), "chamadas": 0, "economia": 0.0,
                "percentual_rapido": 0.0}
    chamadas = dados.get("chamadas") or []
    rapidas = sum(1 for c in chamadas if c.get("modelo") == "rapido")
    return {
        "mes": dados.get("mes"),
        "chamadas": len(chamadas),
        "rapidas": rapidas,
        "fortes": len(chamadas) - rapidas,
        "percentual_rapido": round(rapidas / len(chamadas) * 100, 1) if chamadas else 0.0,
        "economia": dados.get("economia", 0.0),
    }
