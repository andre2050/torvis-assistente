"""Ferramenta explícita da Memória Cognitiva 5.3.0."""
from __future__ import annotations
import json
from memory.cognitive_memory import MemoriaCognitiva


def cognitive_memory(parameters=None, **_context) -> str:
    p = parameters or {}
    modo = str(p.get("mode") or "recall").strip().lower()
    memoria = MemoriaCognitiva()

    if modo == "remember":
        item = memoria.lembrar(
            str(p.get("content") or ""),
            categoria=str(p.get("category") or "geral"),
            tags=[x.strip() for x in str(p.get("tags") or "").split(",") if x.strip()],
            importancia=float(p.get("importance") if p.get("importance") is not None else 0.5),
        )
        return json.dumps({"ok": True, "memoria": item.como_dict()}, ensure_ascii=False)

    if modo == "recall":
        itens = memoria.buscar(str(p.get("query") or ""), limite=int(p.get("limit") or 8))
        return json.dumps({"ok": True, "resultados": itens}, ensure_ascii=False)

    if modo == "forget":
        # Requer o ID exato; não apaga por consulta ampla.
        ident = str(p.get("memory_id") or "").strip()
        return json.dumps({"ok": bool(ident and memoria.esquecer(ident)), "memory_id": ident}, ensure_ascii=False)

    if modo == "status":
        return json.dumps({"ok": True, "status": memoria.status()}, ensure_ascii=False)

    return json.dumps({"ok": False, "erro": "mode deve ser remember, recall, forget ou status"}, ensure_ascii=False)


TOOL = {
    "name": "cognitive_memory",
    "description": (
        "Memória cognitiva local e explícita. Use remember somente quando houver intenção clara de guardar "
        "uma informação; recall pesquisa lembranças; forget exige o ID exato da lembrança."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "mode": {"type": "STRING", "description": "remember, recall, forget ou status"},
            "content": {"type": "STRING", "description": "Conteúdo a guardar quando mode=remember"},
            "query": {"type": "STRING", "description": "Consulta de recuperação"},
            "category": {"type": "STRING", "description": "Categoria da lembrança"},
            "tags": {"type": "STRING", "description": "Tags separadas por vírgula"},
            "importance": {"type": "NUMBER", "description": "Importância entre 0 e 1"},
            "limit": {"type": "INTEGER", "description": "Máximo de resultados"},
            "memory_id": {"type": "STRING", "description": "ID exato para esquecer uma lembrança"},
        },
    },
    "handler": cognitive_memory,
    "tier": "core",
    "brief": "Guarda e recupera lembranças locais explicitamente autorizadas.",
}
