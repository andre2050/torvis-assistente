"""Hora, data e fuso horário — resposta direta, sem consultar a internet.

O modelo não sabe que horas são: o relógio dele é o do treino. Sem uma
ferramenta, "que horas são?" vira um chute. Aqui a resposta vem do relógio da
máquina, que é o único que importa para quem está sentado na frente dela.
"""
from __future__ import annotations

from datetime import datetime, timezone

_DIAS = ("segunda-feira", "terça-feira", "quarta-feira", "quinta-feira",
         "sexta-feira", "sábado", "domingo")
_MESES = ("janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
          "agosto", "setembro", "outubro", "novembro", "dezembro")

# Cidades que aparecem em conversa; o resto fica no fuso local.
_FUSOS = {
    "sao paulo": "America/Sao_Paulo", "são paulo": "America/Sao_Paulo",
    "rio": "America/Sao_Paulo", "brasilia": "America/Sao_Paulo",
    "brasília": "America/Sao_Paulo", "manaus": "America/Manaus",
    "recife": "America/Recife", "fortaleza": "America/Fortaleza",
    "lisboa": "Europe/Lisbon", "portugal": "Europe/Lisbon",
    "londres": "Europe/London", "london": "Europe/London",
    "paris": "Europe/Paris", "berlim": "Europe/Berlin", "madri": "Europe/Madrid",
    "nova york": "America/New_York", "new york": "America/New_York",
    "los angeles": "America/Los_Angeles", "miami": "America/New_York",
    "toquio": "Asia/Tokyo", "tóquio": "Asia/Tokyo", "tokyo": "Asia/Tokyo",
    "pequim": "Asia/Shanghai", "xangai": "Asia/Shanghai",
    "dubai": "Asia/Dubai", "sydney": "Australia/Sydney",
    "buenos aires": "America/Argentina/Buenos_Aires",
    "mexico": "America/Mexico_City", "cidade do mexico": "America/Mexico_City",
    "utc": "UTC", "gmt": "UTC",
}


def _agora() -> datetime:
    return datetime.now().astimezone()


def _hora_texto(momento: datetime) -> str:
    return momento.strftime("%H:%M")


def _data_texto(momento: datetime) -> str:
    return (f"{_DIAS[momento.weekday()]}, {momento.day} de "
            f"{_MESES[momento.month - 1]} de {momento.year}")


def _deslocamento_texto(momento: datetime) -> str:
    deslocamento = momento.utcoffset() or timezone.utc.utcoffset(None)
    total = int(deslocamento.total_seconds() // 60)
    sinal = "+" if total >= 0 else "-"
    horas, minutos = divmod(abs(total), 60)
    return f"UTC{sinal}{horas:02d}:{minutos:02d}"


def _fuso(cidade: str) -> str | None:
    chave = (cidade or "").strip().lower()
    if not chave:
        return None
    if chave in _FUSOS:
        return _FUSOS[chave]
    for nome, zona in _FUSOS.items():                      # "hora em lisboa agora"
        if nome in chave:
            return zona
    return None


def clock_action(parameters: dict, player=None, session_memory=None) -> str:
    acao = str(parameters.get("action") or "agora").strip().lower()
    cidade = parameters.get("city") or parameters.get("cidade") or ""
    try:
        momento = _agora()
        if cidade:
            zona = _fuso(cidade)
            if not zona:
                return (f"Não conheço o fuso de {cidade}. Sei responder para "
                        "Lisboa, Londres, Nova York, Tóquio, Brasília, Manaus e outras.")
            from zoneinfo import ZoneInfo
            momento = datetime.now(ZoneInfo(zona))

        if acao in ("hora", "time", "que horas"):
            resposta = f"Agora são {_hora_texto(momento)}."
        elif acao in ("data", "date", "que dia"):
            resposta = f"Hoje é {_data_texto(momento)}."
        elif acao in ("semana", "weekday", "dia da semana"):
            resposta = f"Hoje é {_DIAS[momento.weekday()]}."
        elif acao in ("fuso", "timezone", "utc"):
            resposta = (f"Estamos em {_deslocamento_texto(momento)}, "
                        f"e agora são {_hora_texto(momento)}.")
        else:
            resposta = (f"São {_hora_texto(momento)} de {_DIAS[momento.weekday()]}, "
                        f"{momento.day} de {_MESES[momento.month - 1]} de {momento.year} "
                        f"({_deslocamento_texto(momento)}).")
    except Exception as exc:                              # noqa: BLE001
        resposta = f"Não consegui ler o relógio do computador: {exc}"

    print(f"[Relógio] {resposta}")
    if player:
        try:
            player.write_log(f"Assistente Inteligente: {resposta}")
        except Exception:                                 # noqa: BLE001
            pass
    return resposta


TOOL = {
    "name": "clock_info",
    "description": (
        "Diz a hora e a data reais do computador. Use SEMPRE que perguntarem que horas "
        "são, que dia é hoje, o dia da semana, o fuso horário, ou a hora em outra cidade "
        "('que horas são em Lisboa'). Nunca responda de memória."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "agora (hora + data) | hora | data | semana | fuso",
                "enum": ["agora", "hora", "data", "semana", "fuso"],
            },
            "city": {
                "type": "STRING",
                "description": "Cidade, quando a pergunta é sobre outro fuso (ex: 'Lisboa').",
            },
        },
        "required": ["action"],
    },
    "tier": "core",
    "brief": "Hora, data, dia da semana e fuso horário, do relógio do computador.",
    "handler": clock_action,
}
