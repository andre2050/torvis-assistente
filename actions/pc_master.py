"""pc_master — o computador inteiro, com descoberta em vez de palpite.

Cinco pedidos do dono caem aqui: abrir QUALQUER programa do Windows, fechar
programas e janelas, digitar e agir no computador (via computer_control),
escrever código (via dev_agent) e criar site, app ou jogo do zero abrindo o
editor de código.

A diferença em relação ao open_app: ele resolve um nome no PATH. Este descobre
o que está instalado — menu Iniciar, App Paths do registro e apps da Store —
e casa por aproximação, então "photoshop" acha "Adobe Photoshop 2026".
"""
from __future__ import annotations

from core import catalogo_pc


def _resposta(status: str, fala: str, dados: dict | None = None) -> dict:
    return {"status": status, "spoken": fala, **(dados or {})}


def pc_master(parameters=None, response=None, player=None, **_kw) -> dict:
    p = parameters or {}
    acao = str(p.get("action") or "abrir").strip().lower()
    nome = str(p.get("name") or p.get("app_name") or "").strip()

    if acao in {"listar", "list", "catalogo", "catálogo"}:
        itens = catalogo_pc.catalogo(forcar=bool(p.get("refresh")))
        nomes = [i["nome"] for i in itens][:80]
        return _resposta("ok", f"{len(itens)} programas instalados.", {"programas": nomes})

    if acao in {"abrir", "open", "executar", "run"}:
        r = catalogo_pc.abrir(nome)
        if r["status"] != "started":
            return _resposta("failed", f"Não consegui abrir {nome}. {r.get('motivo', '')}".strip(), r)
        return _resposta("started", f"Abrindo {r['programa']}.", r)

    if acao in {"fechar", "close", "encerrar"}:
        r = catalogo_pc.fechar(nome)
        if r["status"] != "closed":
            return _resposta("failed", f"Não consegui fechar {nome}. {r.get('motivo', '')}".strip(), r)
        return _resposta("closed", f"Fechei {nome}.", r)

    if acao in {"criar_projeto", "criar", "create_project"}:
        r = catalogo_pc.criar_projeto(
            str(p.get("project_type") or "site"), nome or "novo-projeto",
            p.get("path") or None,
        )
        editor = catalogo_pc.abrir_editor(r["pasta"]) if p.get("open_editor", True) else {}
        sufixo = f" Abri no {editor.get('editor')}." if editor.get("editor") else ""
        return _resposta("created", f"Criei o {r['tipo']} em {r['pasta']}.{sufixo}", {**r, "editor": editor})

    if acao in {"abrir_editor", "editor", "code"}:
        r = catalogo_pc.abrir_editor(nome or None)
        if r["status"] != "started":
            return _resposta("failed", "Nenhum editor de código encontrado.", r)
        return _resposta("started", f"Abrindo {r['editor']}.", r)

    return _resposta("failed", f"Ação desconhecida: {acao}", {"acoes": [
        "abrir", "fechar", "listar", "criar_projeto", "abrir_editor"]})


TOOL = {
    "name": "pc_master",
    "description": (
        "Controla o computador inteiro. Use SEMPRE que o pedido for abrir "
        "qualquer programa instalado (Photoshop, Visual Studio, Sublime, Word, "
        "app da Store), fechar um programa ou uma janela, listar o que existe "
        "instalado, criar um site, aplicativo ou jogo do zero, ou abrir o "
        "editor de código. action='abrir' com name do programa em linguagem "
        "natural basta: a busca é por aproximação. action='fechar' fecha "
        "primeiro pela janela (deixando o app salvar) e só encerra o processo "
        "se a janela não responder. action='criar_projeto' gera a pasta com os "
        "arquivos iniciais e abre no editor. Digitar, clicar, atalhos e "
        "capturas continuam em computer_control; escrever código em arquivos "
        "existentes continua em dev_agent."
    ),
    "handler": pc_master,
    "behavior": "ACTION",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "abrir | fechar | listar | criar_projeto | abrir_editor",
            },
            "name": {
                "type": "STRING",
                "description": ("Nome do programa, da janela, do projeto ou da pasta. "
                                "Use o nome que a pessoa disse; não traduza nem complete."),
            },
            "project_type": {"type": "STRING",
                             "description": "site | app | jogo (só para criar_projeto)"},
            "path": {"type": "STRING", "description": "Onde criar a pasta do projeto"},
            "open_editor": {"type": "BOOLEAN",
                            "description": "Abrir o editor ao final de criar_projeto"},
        },
        "required": ["action"],
    },
}
