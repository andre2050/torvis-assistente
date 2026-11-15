"""Cotações: dólar, euro, bitcoin e ações da B3.

Duas fontes públicas, sem chave: `economia.awesomeapi.com.br` para moedas e
`brapi.dev` para ações. A resposta fica em cache por dois minutos — perguntar
duas vezes seguidas não deve virar duas requisições, e o preço não muda mais
rápido que isso.

Se a rede falhar, a resposta diz que falhou. Cotação inventada é pior que
cotação ausente: alguém decide comprar com base nela.
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request

_TIMEOUT = 8.0
_CACHE_SEGUNDOS = 120.0
_URL_MOEDAS = "https://economia.awesomeapi.com.br/last/"
_URL_ACOES = "https://brapi.dev/api/quote/"

_MOEDAS = {
    "usd": "USD-BRL", "dolar": "USD-BRL", "dólar": "USD-BRL", "dollar": "USD-BRL",
    "eur": "EUR-BRL", "euro": "EUR-BRL",
    "gbp": "GBP-BRL", "libra": "GBP-BRL",
    "ars": "ARS-BRL", "peso": "ARS-BRL",
    "btc": "BTC-BRL", "bitcoin": "BTC-BRL",
    "eth": "ETH-BRL", "ethereum": "ETH-BRL",
    "ltc": "LTC-BRL", "xrp": "XRP-BRL", "sol": "SOL-BRL",
}

_cache: dict[str, tuple[float, dict]] = {}


def _buscar(url: str) -> dict:
    agora = time.time()
    guardado = _cache.get(url)
    if guardado and agora - guardado[0] < _CACHE_SEGUNDOS:
        return guardado[1]
    pedido = urllib.request.Request(url, headers={
        "User-Agent": "TORVIS-2026/6.6", "Accept": "application/json"})
    with urllib.request.urlopen(pedido, timeout=_TIMEOUT) as resposta:
        dados = json.loads(resposta.read().decode("utf-8", errors="replace"))
    _cache[url] = (agora, dados)
    return dados


def _numero(texto) -> float | None:
    try:
        return float(str(texto).replace(",", "."))
    except (TypeError, ValueError):
        return None


def _reais(valor: float | None) -> str:
    if valor is None:
        return "—"
    if valor >= 1000:
        return f"R$ {valor:,.2f}".replace(",", "\u00a7").replace(".", ",").replace("\u00a7", ".")
    if 0 < abs(valor) < 0.01:            # centavos de peso argentino, por exemplo
        return f"R$ {valor:.4f}".replace(".", ",")
    return f"R$ {valor:.2f}".replace(".", ",")


def _moedas(quais: list[str]) -> str:
    pares, nomes = [], []
    for item in quais:
        chave = str(item or "").strip().lower()
        par = _MOEDAS.get(chave)
        if par and par not in pares:
            pares.append(par)
            nomes.append(chave)
    if not pares:
        pares = ["USD-BRL", "EUR-BRL", "BTC-BRL"]

    url = _URL_MOEDAS + ",".join(pares)
    dados = _buscar(url)
    linhas = []
    for par in pares:
        chave = par.replace("-", "")          # USDBRL
        info = dados.get(chave) or {}
        preco = _numero(info.get("bid"))
        variacao = _numero(info.get("pctChange"))
        if preco is None:
            continue
        nome = str(info.get("name") or par).split("/")[0].strip()
        sinal = "▲" if (variacao or 0) >= 0 else "▼"
        var_texto = (f" ({sinal} {abs(variacao):.2f}%)".replace(".", ",")
                     if variacao is not None else "")
        linhas.append(f"- {nome}: {_reais(preco)}{var_texto}")
    if not linhas:
        return "As cotações voltaram vazias agora. Tente de novo em instantes."
    quando = str((dados.get(pares[0].replace('-', '')) or {}).get("create_date") or "")
    rodape = f" (atualizado em {quando})" if quando else ""
    return "Cotações de agora" + rodape + ":\n" + "\n".join(linhas)


def _acao(ticker: str) -> str:
    simbolo = (ticker or "").strip().upper().replace(" ", "")
    if not simbolo:
        return "Qual ação? Me diga o código, por exemplo PETR4."
    if not simbolo.replace(".", "").isalnum() or len(simbolo) > 12:
        return f"'{ticker}' não parece um código de ação."
    url = _URL_ACOES + urllib.parse.quote(simbolo)
    dados = _buscar(url)
    resultados = (dados.get("results") or [{}])[0] if isinstance(dados, dict) else {}
    preco = _numero(resultados.get("regularMarketPrice"))
    if preco is None:
        return f"Não encontrei cotação para {simbolo}."
    nome = resultados.get("longName") or resultados.get("shortName") or simbolo
    variacao = _numero(resultados.get("regularMarketChangePercent"))
    sinal = "▲" if (variacao or 0) >= 0 else "▼"
    var_texto = (f" ({sinal} {abs(variacao):.2f}%)".replace(".", ",")
                 if variacao is not None else "")
    return f"{nome} ({simbolo}): {_reais(preco)}{var_texto}"


def market_quotes_action(parameters: dict, player=None, session_memory=None) -> str:
    acao = str(parameters.get("action") or "cotacao").strip().lower()
    try:
        if acao in ("acao", "ações", "acoes", "stock"):
            resposta = _acao(parameters.get("ticker") or parameters.get("symbol") or "")
        elif acao in ("moedas", "listar", "disponiveis"):
            resposta = ("Conheço: dólar (USD), euro (EUR), libra (GBP), peso argentino (ARS), "
                        "bitcoin (BTC), ethereum (ETH), litecoin (LTC), XRP e SOL, sempre em reais. "
                        "Para ações, me diga o código, como PETR4 ou VALE3.")
        else:
            pedidas = parameters.get("currencies") or parameters.get("moedas") or ["USD", "EUR", "BTC"]
            if isinstance(pedidas, str):
                pedidas = [p for p in pedidas.replace(" e ", ",").split(",") if p.strip()]
            resposta = _moedas(list(pedidas))
    except urllib.error.HTTPError as exc:
        # 401/404 na brapi não é "sem internet": é código errado ou fonte que
        # passou a exigir chave. Dizer "Unauthorized" ao usuário não ajuda.
        if exc.code in (401, 403):
            resposta = ("A fonte de ações passou a exigir autenticação e não tenho chave "
                        "configurada. As cotações de moedas continuam funcionando.")
        elif exc.code == 404:
            resposta = "Esse código de ação não existe na fonte."
        else:
            resposta = f"A fonte de cotações respondeu com erro {exc.code}."
    except urllib.error.URLError as exc:
        resposta = f"Não consegui falar com a fonte de cotações agora ({exc.reason})."
    except Exception as exc:                              # noqa: BLE001
        resposta = f"Não consegui buscar a cotação: {exc}"

    print(f"[Cotações] {resposta}")
    if player:
        try:
            player.write_log(f"Assistente Inteligente: {resposta}")
        except Exception:                                 # noqa: BLE001
            pass
    return resposta


TOOL = {
    "name": "market_quotes",
    "description": (
        "Cotações em reais, de fonte pública: 'cotacao' devolve dólar, euro, bitcoin e as "
        "moedas pedidas; 'acao' devolve o preço de uma ação da B3 pelo código (PETR4, VALE3). "
        "Use sempre que perguntarem quanto está o dólar, o euro, o bitcoin ou uma ação."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "cotacao (moedas) | acao (bolsa) | listar",
                "enum": ["cotacao", "acao", "listar"],
            },
            "currencies": {
                "type": "ARRAY",
                "description": "Moedas pedidas, ex: ['USD', 'EUR', 'BTC'].",
                "items": {"type": "STRING"},
            },
            "ticker": {"type": "STRING", "description": "Código da ação, ex: 'PETR4'."},
        },
        "required": ["action"],
    },
    "tier": "core",
    "brief": "Cotação de dólar, euro, bitcoin e ações da B3.",
    "handler": market_quotes_action,
}
