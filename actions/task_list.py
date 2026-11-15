"""Lista de tarefas com projetos: o que fazer, o que ficou pronto.

Separado de `reminder` (que é um alarme na hora marcada) e de `routines` (que
são rotinas automáticas). Aqui é a lista que o usuário consulta: "o que tenho
para hoje", "marca como feito", "quais são meus projetos".

Armazenamento: `STATE_DIR/userdata/tarefas.json`, via `core.userdata.JsonStore`.
"""
from __future__ import annotations

import time
import unicodedata
from datetime import datetime

from core.userdata import JsonStore

_STORE = JsonStore("tarefas.json")
_PRIORIDADES = ("baixa", "normal", "alta")


def _sem_acento(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", str(texto))
                   if unicodedata.category(c) != "Mn").lower()


def _data_curta(carimbo) -> str:
    if not carimbo:
        return ""
    try:
        return datetime.fromtimestamp(float(carimbo)).strftime("%d/%m")
    except Exception:                                     # noqa: BLE001
        return ""


def _achar(dados: dict, referencia) -> tuple[dict | None, str]:
    itens = dados.get("itens", [])
    texto = str(referencia if referencia is not None else "").strip()
    if not texto:
        return None, "Qual tarefa? Diga o número."
    if texto.isdigit():
        for item in itens:
            if int(item.get("id", -1)) == int(texto):
                return item, ""
        return None, f"Não achei a tarefa {texto}."
    alvo = _sem_acento(texto)
    achadas = [i for i in itens if alvo in _sem_acento(i.get("texto", ""))]
    if len(achadas) == 1:
        return achadas[0], ""
    if not achadas:
        return None, f"Nenhuma tarefa fala de '{texto}'."
    return None, (f"{len(achadas)} tarefas falam disso — me diga o número: "
                  + ", ".join(str(i["id"]) for i in achadas[:6]))


def adicionar(texto: str, projeto: str = "", prioridade: str = "normal") -> str:
    texto = (texto or "").strip()
    if not texto:
        return "Qual é a tarefa?"
    prioridade = (prioridade or "normal").strip().lower()
    if prioridade not in _PRIORIDADES:
        prioridade = "normal"

    def _mutar(dados: dict) -> int:
        novo = _STORE.proximo_id(dados)
        dados["itens"].append({
            "id": novo,
            "texto": texto,
            "projeto": (projeto or "").strip(),
            "prioridade": prioridade,
            "feita": False,
            "criada": time.time(),
        })
        return novo

    novo_id = _STORE.alterar(_mutar)
    onde = f" no projeto {projeto.strip()}" if (projeto or "").strip() else ""
    return f"Tarefa {novo_id} anotada{onde}: {texto[:80]}"


def listar(projeto: str = "", incluir_feitas: bool = False) -> str:
    dados = _STORE.ler()
    itens = dados.get("itens", [])
    if projeto:
        filtro = _sem_acento(projeto)
        itens = [i for i in itens if filtro in _sem_acento(i.get("projeto", ""))]
    if not incluir_feitas:
        itens = [i for i in itens if not i.get("feita")]

    if not itens:
        return ("Nada pendente" + (f" em {projeto}" if projeto else "") + ".")
    ordem = {"alta": 0, "normal": 1, "baixa": 2}
    itens = sorted(itens, key=lambda i: (ordem.get(i.get("prioridade", "normal"), 1),
                                         i.get("criada", 0)))
    linhas = []
    for i in itens[:40]:
        marca = "x" if i.get("feita") else " "
        extra = []
        if i.get("projeto"):
            extra.append(str(i["projeto"]))
        if i.get("prioridade") == "alta":
            extra.append("urgente")
        if i.get("criada"):
            extra.append(_data_curta(i["criada"]))
        sufixo = f"  ({', '.join(extra)})" if extra else ""
        linhas.append(f"[{marca}] {i['id']}. {str(i.get('texto', ''))[:100]}{sufixo}")
    return f"{len(itens)} tarefa(s):\n" + "\n".join(linhas)


def concluir(referencia) -> str:
    dados = _STORE.ler()
    item, erro = _achar(dados, referencia)
    if not item:
        return erro
    alvo = item["id"]

    def _mutar(dados_novos: dict) -> bool:
        for i in dados_novos.get("itens", []):
            if i.get("id") == alvo:
                i["feita"] = True
                i["concluida"] = time.time()
                return True
        return False

    if _STORE.alterar(_mutar):
        return f"Tarefa {alvo} concluída: {str(item.get('texto', ''))[:80]}"
    return "Não achei mais essa tarefa."


def remover(referencia) -> str:
    dados = _STORE.ler()
    item, erro = _achar(dados, referencia)
    if not item:
        return erro
    alvo = item["id"]

    def _mutar(dados_novos: dict) -> bool:
        antes = len(dados_novos.get("itens", []))
        dados_novos["itens"] = [i for i in dados_novos.get("itens", []) if i.get("id") != alvo]
        return len(dados_novos["itens"]) < antes

    if _STORE.alterar(_mutar):
        return f"Tarefa {alvo} removida."
    return "Essa tarefa já não estava na lista."


def projetos() -> str:
    dados = _STORE.ler()
    contagem: dict[str, list[int]] = {}
    for item in dados.get("itens", []):
        nome = str(item.get("projeto") or "").strip()
        if not nome:
            continue
        aberta, feita = contagem.setdefault(nome, [0, 0])
        if item.get("feita"):
            contagem[nome][1] = feita + 1
        else:
            contagem[nome][0] = aberta + 1
    if not contagem:
        return "Nenhum projeto com tarefas ainda. Diga por exemplo 'tarefa X no projeto Site'."
    linhas = [f"- {nome}: {abertas} aberta(s), {feitas} concluída(s)"
              for nome, (abertas, feitas) in sorted(contagem.items())]
    return "Seus projetos:\n" + "\n".join(linhas)


def limpar_concluidas() -> str:
    dados = _STORE.ler()
    feitas = [i for i in dados.get("itens", []) if i.get("feita")]
    if not feitas:
        return "Não há tarefas concluídas para limpar."

    def _mutar(dados_novos: dict) -> int:
        antes = len(dados_novos.get("itens", []))
        dados_novos["itens"] = [i for i in dados_novos.get("itens", []) if not i.get("feita")]
        return antes - len(dados_novos["itens"])

    total = _STORE.alterar(_mutar)
    return f"{total} tarefa(s) concluída(s) removidas da lista."


def task_list_action(parameters: dict, player=None, session_memory=None) -> str:
    acao = str(parameters.get("action") or "listar").strip().lower()
    try:
        if acao in ("adicionar", "add", "criar"):
            resposta = adicionar(parameters.get("text") or parameters.get("texto") or "",
                                 parameters.get("project") or parameters.get("projeto") or "",
                                 parameters.get("priority") or parameters.get("prioridade") or "normal")
        elif acao in ("listar", "list"):
            resposta = listar(parameters.get("project") or parameters.get("projeto") or "",
                              bool(parameters.get("include_done") or parameters.get("incluir_feitas")))
        elif acao in ("concluir", "done", "feito"):
            resposta = concluir(parameters.get("id") or parameters.get("referencia"))
        elif acao in ("remover", "remove", "delete", "apagar"):
            resposta = remover(parameters.get("id") or parameters.get("referencia"))
        elif acao in ("projetos", "projects"):
            resposta = projetos()
        elif acao in ("limpar", "clear"):
            resposta = limpar_concluidas()
        else:
            resposta = "Posso adicionar, listar, concluir, remover tarefas ou mostrar seus projetos."
    except Exception as exc:                              # noqa: BLE001
        resposta = f"Não consegui mexer nas tarefas agora: {exc}"

    print(f"[Tarefas] {resposta}")
    if player:
        try:
            player.write_log(f"Assistente Inteligente: {resposta}")
        except Exception:                                 # noqa: BLE001
            pass
    return resposta


TOOL = {
    "name": "task_list",
    "description": (
        "Lista de tarefas e projetos do usuário (diferente de 'reminder', que é um alarme "
        "numa hora). 'adicionar' cria uma tarefa com projeto e prioridade opcionais, 'listar' "
        "mostra as pendentes, 'concluir' marca como feita, 'remover' apaga, 'projetos' mostra "
        "quantas tarefas cada projeto tem e 'limpar' tira as concluídas."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "adicionar | listar | concluir | remover | projetos | limpar",
                "enum": ["adicionar", "listar", "concluir", "remover", "projetos", "limpar"],
            },
            "text": {"type": "STRING", "description": "O que precisa ser feito."},
            "project": {"type": "STRING", "description": "Projeto ao qual a tarefa pertence (opcional)."},
            "priority": {
                "type": "STRING",
                "description": "baixa | normal | alta",
                "enum": ["baixa", "normal", "alta"],
            },
            "id": {"type": "STRING", "description": "Número ou trecho da tarefa, para concluir ou remover."},
            "include_done": {"type": "BOOLEAN", "description": "Ao listar, incluir as já concluídas."},
        },
        "required": ["action"],
    },
    "tier": "core",
    "brief": "Tarefas e projetos do usuário: adicionar, listar, concluir, remover.",
    "handler": task_list_action,
}
