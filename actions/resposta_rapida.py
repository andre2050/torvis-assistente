"""resposta_rapida — seleciona, aperta o atalho, volta pronto."""
from __future__ import annotations

import json

from core import resposta_rapida as rr


def _ok(**d) -> str:
    return json.dumps({"ok": True, **d}, ensure_ascii=False)


def _falha(e: str) -> str:
    return json.dumps({"ok": False, "erro": e}, ensure_ascii=False)


def _gerador():
    from core import intelligence
    return lambda pedido: intelligence.responder(pedido)


def resposta_rapida(parameters=None, response=None, player=None, **_kw) -> str:
    p = parameters or {}
    modo = str(p.get("modo") or "resumir").strip().lower()
    try:
        rr.instrucao(modo)
    except ValueError as exc:
        return _falha(str(exc))
    texto = str(p.get("texto") or "").strip()
    try:
        if texto:                       # texto entregue direto, sem mexer no teclado
            novo = rr.transformar(texto, modo, _gerador())
            return _ok(modo=modo, resultado=novo)
        return _ok(**rr.executar(modo, _gerador(),
                                 colar_de_volta=bool(p.get("colar", True))))
    except Exception as exc:  # noqa: BLE001
        return _falha(str(exc))


TOOL = {
    "name": "resposta_rapida",
    "description": (
        "Transforma um texto selecionado em qualquer programa: resume, reescreve, "
        "traduz para português, corrige ou explica, e devolve no lugar do original. "
        "Use quando a pessoa disser 'resume isso', 'traduz isso', 'corrige esse "
        "texto' com algo selecionado. Se o texto vier em 'texto', ele só transforma "
        "e não mexe no teclado."
    ),
    "handler": resposta_rapida,
    "behavior": "ACTION",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "modo": {"type": "STRING",
                     "description": "resumir | reescrever | traduzir | corrigir | explicar"},
            "texto": {"type": "STRING", "description": "texto já capturado (opcional)"},
            "colar": {"type": "BOOLEAN", "description": "colar o resultado no cursor"},
        },
        "required": ["modo"],
    },
}
