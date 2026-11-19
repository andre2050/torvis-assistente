"""ata_reuniao — gravação entra, ata com decisões e tarefas sai.

Existe porque a parte chata de uma reunião não é ouvi-la: é escrever o que foi
decidido e quem ficou de fazer o quê. Aceita um arquivo de áudio ou uma
transcrição já pronta, e devolve o caminho do markdown gerado.
"""
from __future__ import annotations

import json
from pathlib import Path

from core import ata_reuniao as ata


def _ok(**dados) -> str:
    return json.dumps({"ok": True, **dados}, ensure_ascii=False)


def _falha(erro: str) -> str:
    return json.dumps({"ok": False, "erro": erro}, ensure_ascii=False)


def _gerador_padrao():
    """Usa o modelo do TORVIS quando há chave; sem chave, devolve None e a ata
    sai pelas regras, que não dependem de rede."""
    try:
        from core import intelligence
        if not getattr(intelligence, "disponivel", lambda: True)():
            return None
        return lambda pedido: intelligence.responder(pedido)  # type: ignore[attr-defined]
    except Exception:
        return None


def ata_reuniao(parameters=None, response=None, player=None, **_kw) -> str:
    p = parameters or {}
    acao = str(p.get("action") or "gerar").strip().lower()

    if acao in {"listar", "ultimas"}:
        return _ok(atas=ata.ultimas(int(p.get("limite") or 10)))

    if acao == "transcrever":
        caminho = str(p.get("audio") or "").strip()
        if not caminho:
            return _falha("informe o caminho do áudio")
        try:
            texto = ata.transcrever_audio(caminho)
        except Exception as exc:  # noqa: BLE001
            return _falha(str(exc))
        return _ok(transcricao=texto, caracteres=len(texto))

    transcricao = str(p.get("transcricao") or "").strip()
    if not transcricao:
        caminho = str(p.get("audio") or "").strip()
        if not caminho:
            return _falha("informe 'audio' (arquivo) ou 'transcricao' (texto)")
        try:
            transcricao = ata.transcrever_audio(caminho)
        except Exception as exc:  # noqa: BLE001
            return _falha(f"não consegui transcrever: {exc}")

    titulo = str(p.get("titulo") or "Reunião").strip() or "Reunião"
    usar_modelo = bool(p.get("usar_modelo", True))
    try:
        resultado = ata.gerar(transcricao, titulo,
                              _gerador_padrao() if usar_modelo else None,
                              Path(p["pasta"]) if p.get("pasta") else None)
    except Exception as exc:  # noqa: BLE001
        return _falha(str(exc))
    return _ok(arquivo=resultado["arquivo"], tarefas=resultado["tarefas"],
               participantes=resultado["ata"].get("participantes"),
               gerado_por=resultado["ata"].get("gerado_por"))


TOOL = {
    "name": "ata_reuniao",
    "description": (
        "Transforma uma reunião em ata. Use quando a pessoa pedir 'faz a ata', "
        "'resume a reunião', 'o que ficou decidido'. Passe 'audio' com o caminho "
        "do arquivo gravado, ou 'transcricao' se o texto já existe. Devolve o "
        "caminho de um markdown com resumo, decisões, tarefas com responsável e "
        "prazo, e a transcrição. Com action='listar' mostra as atas anteriores."
    ),
    "handler": ata_reuniao,
    "behavior": "ACTION",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING",
                       "description": "gerar (padrão) | transcrever | listar"},
            "audio": {"type": "STRING", "description": "caminho do arquivo de áudio da reunião"},
            "transcricao": {"type": "STRING", "description": "texto já transcrito da reunião"},
            "titulo": {"type": "STRING", "description": "nome da reunião"},
            "pasta": {"type": "STRING", "description": "onde salvar a ata"},
            "usar_modelo": {"type": "BOOLEAN",
                            "description": "false para montar a ata só por regras"},
            "limite": {"type": "INTEGER", "description": "quantas atas listar"},
        },
        "required": [],
    },
}
