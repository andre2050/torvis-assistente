"""vigia — pasta observada, arquivo tratado sozinho."""
from __future__ import annotations

import json

from core import modo_vigia as vigia


def _ok(**d) -> str:
    return json.dumps({"ok": True, **d}, ensure_ascii=False)


def _falha(e: str) -> str:
    return json.dumps({"ok": False, "erro": e}, ensure_ascii=False)


def vigia(parameters=None, response=None, player=None, **_kw) -> str:
    p = parameters or {}
    acao = str(p.get("action") or "status").strip().lower()
    try:
        if acao in {"vigiar", "adicionar"}:
            caminho = str(p.get("pasta") or "").strip()
            if not caminho:
                return _falha("informe a pasta")
            return _ok(**vigia.vigiar(caminho))
        if acao == "parar":
            return _ok(**vigia.parar(p.get("pasta") or None))
        if acao == "varrer":
            return _ok(**vigia.varrer())
        if acao == "acoes":
            return _ok(acoes=vigia.ultimas_acoes(int(p.get("limite") or 20)))
        return _ok(pastas=vigia.pastas())
    except Exception as exc:  # noqa: BLE001
        return _falha(str(exc))


TOOL = {
    "name": "vigia",
    "description": (
        "Observa pastas e trata o que chega: foto vai para uma pasta por ano-mês, "
        "nota fiscal é renomeada com data e valor, PDF ganha um resumo ao lado. "
        "Use action='vigiar' com a pasta para começar, 'parar' para desligar, "
        "'varrer' para uma passada imediata e 'acoes' para ver o que ele fez."
    ),
    "handler": vigia,
    "behavior": "ACTION",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING",
                       "description": "vigiar | parar | varrer | acoes | status"},
            "pasta": {"type": "STRING", "description": "caminho da pasta"},
            "limite": {"type": "INTEGER", "description": "quantas ações listar"},
        },
        "required": ["action"],
    },
}
