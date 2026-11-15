"""Casa inteligente pelo Home Assistant: ligar, desligar, ajustar.

Escolhi o Home Assistant porque ele fala com quase tudo (lâmpada Wi-Fi, tomada,
ar-condicionado, cortina) atrás de uma API local só. Se o usuário não usa HA,
nada aqui quebra: a ação explica o que falta e o resto do assistente segue
funcionando.

Configuração no `config.json`:
    "home_assistant_url":   "http://homeassistant.local:8123"
    "home_assistant_token": "token de longa duração criado no perfil do HA"
"""
from __future__ import annotations

import json
import re
import unicodedata
import urllib.error
import urllib.parse
import urllib.request

_TIMEOUT = 8.0
_DOMINIOS_ENTIDADE = ("light", "switch", "climate", "fan", "cover", "media_player")

_ultimo_estado: dict[str, dict] = {}


def _sem_acento(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", str(texto))
                   if unicodedata.category(c) != "Mn").lower()


def _credenciais() -> tuple[str, str] | tuple[None, str]:
    try:
        from memory.config_manager import load_api_keys

        config = load_api_keys() or {}
    except Exception:                                     # noqa: BLE001
        config = {}

    url = str(config.get("home_assistant_url") or "").strip().rstrip("/")
    token = str(config.get("home_assistant_token") or "").strip()
    if not url or not token:
        return None, (
            "A casa inteligente ainda não está configurada. Coloque no config.json a URL do "
            "seu Home Assistant em 'home_assistant_url' (ex: http://homeassistant.local:8123) "
            "e um token de longa duração em 'home_assistant_token'. Sem isso não tenho como "
            "alcançar suas lâmpadas.")
    return f"{url}|{token}", ""


def _pedir(servico_url: str, dados_reais: tuple[str, str], metodo: str = "GET",
           corpo: dict | None = None) -> object:
    url, token = dados_reais
    pedido = urllib.request.Request(url, method=metodo, headers={
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    })
    if corpo is not None:
        pedido.data = json.dumps(corpo).encode("utf-8")
    with urllib.request.urlopen(pedido, timeout=_TIMEOUT) as resposta:
        bruto = resposta.read().decode("utf-8", errors="replace")
    return json.loads(bruto) if bruto.strip() else {}


def _base() -> tuple[str, str]:
    combinado, erro = _credenciais()
    if not combinado:
        raise RuntimeError(erro)
    url, token = combinado.split("|", 1)
    return url, token


def _entidades() -> list[dict]:
    url, token = _base()
    estados = _pedir(f"{url}/api/states", (url, token))
    if not isinstance(estados, list):
        return []
    saida = []
    for item in estados:
        identidade = str(item.get("entity_id") or "")
        dominio = identidade.split(".")[0]
        if dominio not in _DOMINIOS_ENTIDADE:
            continue
        saida.append({
            "entity_id": identidade,
            "dominio": dominio,
            "nome": str((item.get("attributes") or {}).get("friendly_name") or identidade),
            "estado": str(item.get("state") or ""),
            "atributos": item.get("attributes") or {},
        })
    _ultimo_estado.clear()
    for item in saida:
        _ultimo_estado[item["entity_id"]] = item
    return saida


def _achar(referencia: str) -> tuple[dict | None, str]:
    if not referencia:
        return None, "Qual dispositivo? Diga o nome, como 'luz da sala'."
    if _ultimo_estado:
        lista = list(_ultimo_estado.values())
    else:
        try:
            lista = _entidades()
        except RuntimeError as exc:
            return None, str(exc)
        except Exception as exc:                          # noqa: BLE001
            return None, f"Não consegui falar com o Home Assistant: {exc}"

    alvo = _sem_acento(referencia)
    exatos = [i for i in lista if _sem_acento(i["nome"]) == alvo
              or i["entity_id"].split(".")[-1] == alvo.replace(" ", "_")]
    if exatos:
        return exatos[0], ""
    parciais = [i for i in lista if alvo in _sem_acento(i["nome"])]
    if len(parciais) == 1:
        return parciais[0], ""
    if not parciais:
        nomes = ", ".join(i["nome"] for i in lista[:6]) or "nenhum"
        return None, (f"Não achei '{referencia}'. Conheço: {nomes}. "
                      "Se o nome estiver diferente no Home Assistant, me diga como está lá.")
    return None, ("Mais de um dispositivo com esse nome: "
                  + ", ".join(i["nome"] for i in parciais[:5]))


def _chamar(dominio: str, servico: str, entidade: str, dados: dict | None = None) -> None:
    url, token = _base()
    corpo = {"entity_id": entidade}
    corpo.update(dados or {})
    _pedir(f"{url}/api/services/{dominio}/{servico}", (url, token), "POST", corpo)


def listar(filtro: str = "") -> str:
    try:
        lista = _entidades()
    except RuntimeError as exc:
        return str(exc)
    except Exception as exc:                              # noqa: BLE001
        return f"Não consegui falar com o Home Assistant: {exc}"

    if filtro:
        lista = [i for i in lista if _sem_acento(filtro) in _sem_acento(i["nome"])]
    if not lista:
        return "Nenhum dispositivo encontrado" + (f" com '{filtro}'" if filtro else "") + "."
    linhas = []
    for item in lista[:25]:
        estado = item["estado"]
        if item["dominio"] == "light" and estado == "on":
            brilho = item["atributos"].get("brightness")
            if brilho:
                estado += f" ({round(float(brilho) / 2.55)}%)"
        if item["dominio"] == "climate" and estado == "on":
            temperatura = item["atributos"].get("temperature")
            if temperatura is not None:
                estado += f" ({temperatura}°)"
        linhas.append(f"- {item['nome']}: {estado}")
    return f"{len(lista)} dispositivo(s):\n" + "\n".join(linhas)


def ligar(referencia: str) -> str:
    item, erro = _achar(referencia)
    if not item:
        return erro
    servico = "turn_on"
    try:
        _chamar(item["dominio"], servico, item["entity_id"])
    except urllib.error.HTTPError as exc:
        return f"O Home Assistant recusou o comando ({exc.code})."
    except Exception as exc:                              # noqa: BLE001
        return f"Não consegui ligar {item['nome']}: {exc}"
    return f"{item['nome']} ligado."


def desligar(referencia: str) -> str:
    item, erro = _achar(referencia)
    if not item:
        return erro
    try:
        _chamar(item["dominio"], "turn_off", item["entity_id"])
    except Exception as exc:                              # noqa: BLE001
        return f"Não consegui desligar {item['nome']}: {exc}"
    return f"{item['nome']} desligado."


def definir(referencia: str, brilho=None, temperatura=None, cor_temperatura=None) -> str:
    item, erro = _achar(referencia)
    if not item:
        return erro

    dados: dict = {}
    if brilho is not None:
        try:
            percentual = max(1, min(100, int(float(brilho))))
            dados["brightness_pct"] = percentual
        except (TypeError, ValueError):
            return "O brilho precisa ser um número de 1 a 100."
    if temperatura is not None and item["dominio"] == "climate":
        try:
            dados["temperature"] = float(temperatura)
        except (TypeError, ValueError):
            return "A temperatura precisa ser um número."
    if cor_temperatura is not None:
        try:
            dados["color_temp_kelvin"] = int(float(cor_temperatura))
        except (TypeError, ValueError):
            return "A temperatura de cor precisa ser um número em kelvin."
    if not dados:
        return "Diga o que ajustar: brilho em %, temperatura do ar ou temperatura de cor."

    servico = "turn_on" if item["dominio"] in ("light", "switch", "fan", "climate") else "set_cover_position"
    try:
        _chamar(item["dominio"], servico, item["entity_id"], dados)
    except Exception as exc:                              # noqa: BLE001
        return f"Não consegui ajustar {item['nome']}: {exc}"

    partes = [f"{chave.replace('_pct', '')} {valor}" for chave, valor in dados.items()]
    return f"{item['nome']} ajustado ({', '.join(partes)})."


def status(referencia: str) -> str:
    item, erro = _achar(referencia)
    if not item:
        return erro
    detalhe = ""
    if item["dominio"] == "light" and item["estado"] == "on":
        brilho = item["atributos"].get("brightness")
        if brilho:
            detalhe = f", brilho em {round(float(brilho) / 2.55)}%"
    if item["dominio"] == "climate":
        temperatura = item["atributos"].get("current_temperature")
        alvo = item["atributos"].get("temperature")
        if temperatura is not None:
            detalhe += f", ambiente {temperatura}°"
        if alvo is not None:
            detalhe += f", alvo {alvo}°"
    return f"{item['nome']} está {item['estado']}{detalhe}."


def smart_home_action(parameters: dict, player=None, session_memory=None) -> str:
    acao = str(parameters.get("action") or "listar").strip().lower()
    alvo = parameters.get("device") or parameters.get("dispositivo") or parameters.get("name") or ""
    try:
        if acao in ("listar", "list"):
            resposta = listar(parameters.get("filter") or parameters.get("filtro") or "")
        elif acao in ("ligar", "on", "acender"):
            resposta = ligar(alvo)
        elif acao in ("desligar", "off", "apagar"):
            resposta = desligar(alvo)
        elif acao in ("definir", "ajustar", "set"):
            resposta = definir(alvo,
                               parameters.get("brightness", parameters.get("brilho")),
                               parameters.get("temperature", parameters.get("temperatura")),
                               parameters.get("color_temp", parameters.get("cor_temperatura")))
        elif acao in ("status", "estado"):
            resposta = status(alvo)
        else:
            resposta = "Posso listar os dispositivos, ligar, desligar, ajustar ou informar o estado."
    except Exception as exc:                              # noqa: BLE001
        resposta = f"Não consegui mexer na casa agora: {exc}"

    print(f"[Casa] {resposta}")
    if player:
        try:
            player.write_log(f"Assistente Inteligente: {resposta}")
        except Exception:                                 # noqa: BLE001
            pass
    return resposta


TOOL = {
    "name": "smart_home",
    "description": (
        "Casa inteligente via Home Assistant: 'listar' mostra lâmpadas, tomadas, ar-condicionado "
        "e cortinas; 'ligar'/'desligar' acionam pelo nome; 'definir' ajusta brilho (%), "
        "temperatura do ar ou temperatura de cor; 'status' diz o estado. Só funciona se o "
        "usuário tiver configurado o Home Assistant — se não tiver, a resposta explica o que falta."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "listar | ligar | desligar | definir | status",
                "enum": ["listar", "ligar", "desligar", "definir", "status"],
            },
            "device": {"type": "STRING", "description": "Nome do dispositivo, ex: 'luz da sala', 'ar do quarto'."},
            "brightness": {"type": "NUMBER", "description": "Brilho em porcentagem (1 a 100)."},
            "temperature": {"type": "NUMBER", "description": "Temperatura alvo do ar-condicionado."},
            "color_temp": {"type": "NUMBER", "description": "Temperatura de cor em kelvin."},
            "filter": {"type": "STRING", "description": "Filtro de nome ao listar."},
        },
        "required": ["action"],
    },
    "tier": "extra",
    "brief": "Casa inteligente (Home Assistant): ligar, desligar, ajustar, listar.",
    "handler": smart_home_action,
}
