"""Agente inteligente: pedido em linguagem natural → intenção → decisão → plano → ação → verificação.

Ponte do ciclo de raciocínio (core/raciocinio.py) para o assistente de voz. A ferramenta
entende o que o usuário quer (JSON estruturado), usa contexto, memória e correções
anteriores, pergunta só quando o erro seria caro ou falta um dado, executa passo a passo,
confere se deu certo e tenta outro caminho se falhar.
"""
from __future__ import annotations

import json
import threading

_lock = threading.Lock()
_ligado = False


def _preparar(isa) -> None:
    """Descreve ao agente as ferramentas reais do app (uma vez)."""
    global _ligado
    with _lock:
        if _ligado:
            return
        try:
            from core.action_loader import discover_actions
            from core.paths import APP_DIR
            registro = discover_actions(APP_DIR / "actions", logger=lambda *_a, **_k: None)
            isa.ligar_registro_de_acoes(registro)
        except Exception:
            pass
        _ligado = True


def smart_agent(parameters=None, player=None, **_ctx) -> str:
    from core.isa import obter_isa
    p = parameters or {}
    pedido = str(p.get("request") or "").strip()
    if not pedido:
        return json.dumps({"estado": "vazio", "mensagem": "faltou o pedido"}, ensure_ascii=False)
    isa = obter_isa()
    _preparar(isa)
    try:
        saida = isa.processar_pedido(pedido)
    except Exception as exc:
        return json.dumps({"estado": "falhou", "mensagem": f"{type(exc).__name__}: {exc}"[:300]}, ensure_ascii=False)
    return json.dumps(saida, ensure_ascii=False, default=str)[:6000]


TOOL = {
    "name": "smart_agent",
    "description": (
        "Agente autônomo inteligente para pedidos que precisam de interpretação, vários passos ou "
        "referências ('faz de novo', 'manda pro mesmo cara', 'aquela música de ontem'). Entende a "
        "intenção, planeja, executa, VERIFICA o resultado e tenta outro caminho se falhar. Se o "
        "retorno trouxer estado=pergunta, faça a pergunta ao usuário e, com a resposta, chame de novo "
        "com a resposta dele em request. Se trouxer 'aviso', diga ao usuário o que foi assumido. "
        "Se trouxer 'nao_verificado', diga que pediu mas não conseguiu confirmar. "
        "Quando o usuário corrigir ('não, não era isso'), chame com a correção em request."),
    "brief": "Agente que entende a intenção, planeja, executa, verifica e aprende com correções.",
    "tier": "core",
    "parameters": {
        "type": "OBJECT",
        "properties": {"request": {"type": "STRING",
                                   "description": "O pedido do usuário, nas palavras dele (ou a resposta/correção a uma pergunta anterior)"}},
        "required": ["request"],
    },
    "handler": smart_agent,
}
