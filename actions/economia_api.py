"""economia_api — escolhe o modelo pelo problema e mostra quanto poupou."""
from __future__ import annotations

import json

from core import economia_api as eco


def economia_api(parameters=None, response=None, player=None, **_kw) -> str:
    p = parameters or {}
    acao = str(p.get("action") or "resumo").strip().lower()
    if acao in {"escolher", "decidir"}:
        escolha = eco.escolher(str(p.get("pedido") or ""),
                               tamanho=p.get("tokens") or None)
        eco.registrar(escolha, tokens_saida=int(p.get("tokens_saida") or 0))
        return json.dumps({"ok": True, **escolha}, ensure_ascii=False)
    return json.dumps({"ok": True, **eco.resumo_mes()}, ensure_ascii=False)


TOOL = {
    "name": "economia_api",
    "description": (
        "Decide se o pedido vai para o modelo rápido ou para o forte, e soma a "
        "economia do mês. Use action='escolher' antes de uma tarefa pesada quando "
        "quiser economizar cota, e action='resumo' para responder 'quanto economizei'."
    ),
    "handler": economia_api,
    "behavior": "ACTION",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "escolher | resumo"},
            "pedido": {"type": "STRING", "description": "o pedido do usuário"},
            "tokens": {"type": "INTEGER", "description": "tamanho estimado em tokens"},
            "tokens_saida": {"type": "INTEGER", "description": "tokens da resposta"},
        },
        "required": ["action"],
    },
}
