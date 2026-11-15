"""Notas rápidas: anotar uma ideia e achá-la depois.

Fica fora da memória cognitiva de propósito. Memória é o que o assistente
lembra sobre o usuário; nota é o que o usuário escreveu e quer de volta nas
próximas semanas, com começo, meio e fim. Misturar as duas faz a nota sumir
dentro das lembranças e a lembrança virar uma pilha de recados.

Armazenamento: `STATE_DIR/userdata/notas.json` (fora da pasta do aplicativo,
então sobrevive a atualização) via `core.userdata.JsonStore`, que grava de forma
atômica e com trava por arquivo.
"""
from __future__ import annotations

import re
import time
import unicodedata
from datetime import datetime

from core.userdata import JsonStore

_STORE = JsonStore("notas.json")
_MAX_TEXTO = 4000


def _sem_acento(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto)
                   if unicodedata.category(c) != "Mn").lower()


def _data_curta(carimbo: float) -> str:
    try:
        return datetime.fromtimestamp(float(carimbo)).strftime("%d/%m %H:%M")
    except Exception:                                     # noqa: BLE001
        return ""


def _achar(dados: dict, referencia) -> tuple[dict | None, str]:
    """Localiza uma nota por id ou pelo começo do texto."""
    itens = dados.get("itens", [])
    texto = str(referencia if referencia is not None else "").strip()
    if not texto:
        return None, "Qual nota? Diga o número dela."
    if texto.isdigit():
        alvo = int(texto)
        for item in itens:
            if int(item.get("id", -1)) == alvo:
                return item, ""
        return None, f"Não achei a nota {alvo}."
    alvo = _sem_acento(texto)
    candidatos = [i for i in itens if alvo in _sem_acento(str(i.get("texto", "")))]
    if len(candidatos) == 1:
        return candidatos[0], ""
    if not candidatos:
        return None, f"Nenhuma nota fala de '{texto}'."
    return None, (f"{len(candidatos)} notas falam disso — me diga o número: "
                  + ", ".join(str(i["id"]) for i in candidatos[:6]))


def adicionar(texto: str, tags: str = "") -> str:
    texto = (texto or "").strip()
    if not texto:
        return "Escreva a nota e eu guardo."
    if len(texto) > _MAX_TEXTO:
        return "Essa nota é longa demais; quebre em duas."

    def _mutar(dados: dict) -> int:
        novo = _STORE.proximo_id(dados)
        dados["itens"].append({
            "id": novo,
            "texto": texto,
            "tags": [t.strip() for t in re.split(r"[,;]", tags or "") if t.strip()],
            "criada": time.time(),
        })
        return novo

    novo_id = _STORE.alterar(_mutar)
    return f"Nota {novo_id} guardada: {texto[:80]}"


def listar(limite: int = 10) -> str:
    dados = _STORE.ler()
    itens = sorted(dados.get("itens", []), key=lambda i: i.get("criada", 0), reverse=True)
    if not itens:
        return "Você não tem notas guardadas."
    try:
        limite = max(1, min(50, int(limite)))
    except (TypeError, ValueError):
        limite = 10
    linhas = [f"{i['id']}. {str(i.get('texto', ''))[:110]}  — {_data_curta(i.get('criada', 0))}"
              for i in itens[:limite]]
    total = len(itens)
    cabeca = f"{total} nota(s)" + ("" if total <= limite else f", as {limite} mais recentes")
    return cabeca + ":\n" + "\n".join(linhas)


def buscar(termo: str) -> str:
    alvo = _sem_acento(termo or "")
    if not alvo:
        return "O que eu procuro nas notas?"
    dados = _STORE.ler()
    achadas = [i for i in dados.get("itens", []) if alvo in _sem_acento(str(i.get("texto", "")))]
    if not achadas:
        return f"Nenhuma nota fala de '{termo}'."
    linhas = [f"{i['id']}. {str(i.get('texto', ''))[:110]}" for i in achadas[:10]]
    return f"{len(achadas)} nota(s) com '{termo}':\n" + "\n".join(linhas)


def ler(referencia) -> str:
    dados = _STORE.ler()
    item, erro = _achar(dados, referencia)
    if not item:
        return erro
    return (f"Nota {item['id']} ({_data_curta(item.get('criada', 0))}):\n"
            f"{item.get('texto', '')}")


def apagar(referencia) -> str:
    dados = _STORE.ler()
    item, erro = _achar(dados, referencia)
    if not item:
        return erro
    alvo_id = item["id"]

    def _mutar(dados_novos: dict) -> bool:
        antes = len(dados_novos.get("itens", []))
        dados_novos["itens"] = [i for i in dados_novos.get("itens", []) if i.get("id") != alvo_id]
        return len(dados_novos["itens"]) < antes

    if _STORE.alterar(_mutar):
        return f"Nota {alvo_id} apagada."
    return f"A nota {alvo_id} já não estava lá."


def limpar() -> str:
    dados = _STORE.ler()
    total = len(dados.get("itens", []))
    if not total:
        return "Não havia notas para apagar."
    _STORE.escrever({"itens": [], "proximo_id": 1})
    return f"{total} nota(s) apagadas."


def quick_notes_action(parameters: dict, player=None, session_memory=None) -> str:
    acao = str(parameters.get("action") or "adicionar").strip().lower()
    try:
        if acao in ("adicionar", "add", "anotar", "guardar"):
            resposta = adicionar(parameters.get("text") or parameters.get("texto") or "",
                                 parameters.get("tags") or "")
        elif acao in ("listar", "list"):
            resposta = listar(parameters.get("limit", 10))
        elif acao in ("buscar", "search", "procurar"):
            resposta = buscar(parameters.get("query") or parameters.get("termo") or "")
        elif acao in ("ler", "read", "abrir"):
            resposta = ler(parameters.get("id") or parameters.get("referencia"))
        elif acao in ("apagar", "delete", "remover"):
            resposta = apagar(parameters.get("id") or parameters.get("referencia"))
        elif acao in ("limpar", "clear"):
            resposta = limpar()
        else:
            resposta = ("Posso anotar, listar, buscar, ler, apagar ou limpar notas.")
    except Exception as exc:                              # noqa: BLE001
        resposta = f"Não consegui mexer nas notas agora: {exc}"

    print(f"[Notas] {resposta}")
    if player:
        try:
            player.write_log(f"Assistente Inteligente: {resposta}")
        except Exception:                                 # noqa: BLE001
            pass
    return resposta


TOOL = {
    "name": "quick_notes",
    "description": (
        "Notas rápidas guardadas no computador do usuário: 'adicionar' guarda um texto "
        "('anota que o pedreiro vem terça'), 'listar' mostra as recentes, 'buscar' procura "
        "por palavra, 'ler' abre uma pelo número, 'apagar' remove e 'limpar' esvazia. "
        "Use para qualquer recado que o usuário queira escrever para depois."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "adicionar | listar | buscar | ler | apagar | limpar",
                "enum": ["adicionar", "listar", "buscar", "ler", "apagar", "limpar"],
            },
            "text": {"type": "STRING", "description": "O texto da nota, exatamente como o usuário ditou."},
            "tags": {"type": "STRING", "description": "Etiquetas separadas por vírgula (opcional)."},
            "query": {"type": "STRING", "description": "Palavra a procurar nas notas."},
            "id": {"type": "STRING", "description": "Número ou trecho da nota, para ler ou apagar."},
            "limit": {"type": "INTEGER", "description": "Quantas notas listar (padrão 10)."},
        },
        "required": ["action"],
    },
    "tier": "core",
    "brief": "Anota, lista, busca e apaga notas rápidas do usuário.",
    "handler": quick_notes_action,
}
