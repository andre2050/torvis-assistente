"""Ferramenta da secretária de WhatsApp para o TORVIS.

O TORVIS usa esta ferramenta para: mostrar o estado, ligar/desligar o
atendimento, liberar um número, mandar texto (ou áudio) e definir o recado que
vai para quem ligou e não foi atendido.
"""
from __future__ import annotations

import json
from pathlib import Path

from core import whatsapp as wa

_ACOES = ("status", "ligar", "desligar", "permitir", "remover", "enviar", "audio", "recado")


def _ok(**dados) -> str:
    return json.dumps({"ok": True, **dados}, ensure_ascii=False)


def _falha(erro: str) -> str:
    return json.dumps({"ok": False, "erro": erro}, ensure_ascii=False)


def whatsapp_secretary(parameters=None, **_context) -> str:
    p = parameters or {}
    acao = str(p.get("action") or "status").lower().strip()
    if acao not in _ACOES:
        return _falha("ação deve ser: " + ", ".join(_ACOES))

    if acao == "status":
        cfg = wa.carregar_config()
        secretaria = wa.SecretariaWhatsApp(cfg)
        disponivel, motivo = secretaria.disponivel()
        return _ok(ligada=bool(cfg["ligada"]), credencial=disponivel, detalhe=motivo,
                   responder_audio=bool(cfg["responder_audio"]),
                   permitidos=cfg["permitidos"],
                   silencio=f"{cfg['silencioso_inicio']}h às {cfg['silencioso_fim']}h",
                   recado=cfg["recado"])

    if acao in ("ligar", "desligar"):
        cfg = wa.salvar_config({"ligada": acao == "ligar"})
        if acao == "ligar":
            disponivel, motivo = wa.SecretariaWhatsApp(cfg).disponivel()
            if not disponivel:
                return _ok(ligada=True, aviso=f"ligada, mas {motivo}")
        return _ok(ligada=cfg["ligada"])

    if acao in ("permitir", "remover"):
        numero = wa.so_digitos(p.get("numero") or p.get("para") or "")
        if not numero:
            return _falha("informe o número com DDI, por exemplo 5585999991234")
        cfg = wa.carregar_config()
        lista = [wa.so_digitos(n) for n in cfg["permitidos"]]
        if acao == "permitir" and numero not in lista:
            lista.append(numero)
        if acao == "remover" and numero in lista:
            lista.remove(numero)
        wa.salvar_config({"permitidos": lista})
        return _ok(permitidos=lista)

    if acao == "recado":
        texto = str(p.get("texto") or "").strip()
        if not texto:
            return _falha("informe o texto do recado")
        wa.salvar_config({"recado": texto[:600]})
        return _ok(recado=texto[:600])

    if acao in ("enviar", "audio"):
        destino = wa.so_digitos(p.get("para") or p.get("numero") or "")
        if not destino:
            return _falha("informe para quem enviar")
        secretaria = wa.SecretariaWhatsApp(wa.carregar_config())
        disponivel, motivo = secretaria.disponivel()
        if not disponivel:
            return _falha(motivo)
        if acao == "enviar":
            texto = str(p.get("texto") or "").strip()
            if not texto:
                return _falha("informe o texto")
            secretaria.enviar_texto(destino, texto)
            return _ok(enviado="texto", para=destino)
        texto = str(p.get("texto") or "").strip()
        if not texto:
            return _falha("informe o texto que vira áudio")
        try:
            from core.tts import EdgeTTSEngine
            import asyncio
            motor = EdgeTTSEngine("pt-BR-AntonioNeural")
            laco = asyncio.new_event_loop()
            try:
                som = laco.run_until_complete(motor._synth(texto))  # noqa: SLF001
            finally:
                laco.close()
        except Exception as exc:  # noqa: BLE001
            return _falha(f"não consegui gerar a voz: {exc}")
        if not som:
            return _falha("a voz voltou vazia")
        arquivo = Path(secretaria._tmp(".mp3"))  # noqa: SLF001
        arquivo.write_bytes(som)
        secretaria.enviar_audio(destino, arquivo)
        return _ok(enviado="audio", para=destino)

    return _falha("ação não tratada")


TOOL = {
    "name": "whatsapp_secretary",
    "description": (
        "Secretária de WhatsApp do usuário, pela API oficial. 'status' mostra como está, "
        "'ligar'/'desligar' abre e fecha o atendimento automático, 'permitir'/'remover' "
        "controla quem é atendido (número com DDI), 'enviar' manda texto para alguém, "
        "'audio' manda a mesma mensagem como nota de voz e 'recado' define a resposta "
        "de quem ligou e não foi atendido. Use quando o usuário pedir para responder "
        "ou avisar alguém pelo WhatsApp."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING",
                       "description": "status, ligar, desligar, permitir, remover, enviar, audio ou recado"},
            "numero": {"type": "STRING", "description": "número com DDI, só dígitos ou com pontuação"},
            "para": {"type": "STRING", "description": "destinatário do envio"},
            "texto": {"type": "STRING", "description": "conteúdo da mensagem ou do recado"},
        },
        "required": ["action"],
    },
    "handler": whatsapp_secretary,
    "behavior": "NON_BLOCKING",
    "tier": "core",
    "brief": "Atende WhatsApp: responde texto e áudio, avisa quem ligou e não foi atendido.",
}
