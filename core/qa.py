"""Trilha de testes automatizados para devs (v6.6.1).

POR QUE ASSIM
    As quatro frentes pedidas (UI com Selenium/Puppeteer, testes de API,
    plataformas como Azure Test Plans e Test.ai, e DevOps/Atlassian) parecem
    quatro integrações diferentes. São uma só: todas comem JUnit XML ou um
    resultado de execução com nome, status e motivo. Então o motor daqui faz
    três coisas bem feitas e o resto é encaixe:

        1. descobre o que está instalado na máquina;
        2. cria e executa testes (UI em Selenium/Puppeteer, API em HTTP puro);
        3. escreve o resultado em JUnit XML e publica onde o usuário mandar.

    Teste de API não depende de `requests`: `urllib` já está no Python e não
    pede instalação. Dependência que falha na hora de rodar o teste é pior que
    teste que nunca existiu.

SEGURANÇA
    `executar()` só aceita programas de uma lista fechada, nunca usa `shell=True`
    e mata o processo no tempo limite. Um assistente que ouve a voz do usuário
    não pode virar um executor de string arbitrária.
"""
from __future__ import annotations

import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

from core.paths import STATE_DIR

QA_DIR = STATE_DIR / "qa"


def _resultados_file() -> Path:
    """Derivado na hora, não no import: assim trocar QA_DIR (teste, outro perfil)
    realmente muda onde o resultado é lido e gravado."""
    return QA_DIR / "ultimo_resultado.json"

_SISTEMA = platform.system()
_TIMEOUT_PADRAO = 180.0
_TIMEOUT_COMANDO = 20.0
# Nomes exatos: no Linux o interpretador é `python3.11`, e uma lista de nomes
# fixos recusaria o próprio Python que está rodando o assistente.
_PROGRAMA_OK = re.compile(r"^(python|python3(\.\d+)?|py|pytest|node|npx|npm|chrome|chromium)$")

_deteccao: tuple[float, dict] | None = None
_CACHE_SEGUNDOS = 60.0


# ── descoberta do ambiente ───────────────────────────────────────────────────
def _tem_modulo(nome: str) -> bool:
    import importlib.util

    try:
        return importlib.util.find_spec(nome) is not None
    except (ImportError, ValueError):
        return False


def _versao_comando(programa: str, argumento: str = "--version") -> str | None:
    caminho = shutil.which(programa)
    if not caminho:
        return None
    try:
        saida = subprocess.run([caminho, argumento], capture_output=True, text=True,
                               timeout=_TIMEOUT_COMANDO, creationflags=_sem_janela())
        texto = (saida.stdout or saida.stderr or "").strip().splitlines()
        return texto[0][:60] if texto else "instalado"
    except (subprocess.SubprocessError, OSError):
        return "instalado"


def _sem_janela() -> int:
    """No Windows, não abrir console preto a cada verificação."""
    if _SISTEMA == "Windows":
        return getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return 0


def _caminhos_chrome() -> list[Path]:
    candidatos: list[Path] = []
    do_ambiente = os.getenv("CHROME_PATH") or os.getenv("CHROME_BIN")
    if do_ambiente:
        candidatos.append(Path(do_ambiente))
    for programa in ("chrome", "google-chrome", "chromium", "chromium-browser", "chrome.exe"):
        achado = shutil.which(programa)
        if achado:
            candidatos.append(Path(achado))
    if _SISTEMA == "Windows":
        for base in (os.getenv("PROGRAMFILES"), os.getenv("PROGRAMFILES(X86)"), os.getenv("LOCALAPPDATA")):
            if not base:
                continue
            for sub in ("Google/Chrome/Application/chrome.exe",
                        "Microsoft/Edge/Application/msedge.exe"):
                candidatos.append(Path(base) / sub)
    elif _SISTEMA == "Darwin":
        candidatos.append(Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"))
    # Chrome for Testing baixado pelo puppeteer fica em ~/.cache/puppeteer
    for raiz in (Path.home() / ".cache" / "puppeteer", Path.home() / "AppData" / "Local" / "puppeteer" / "cache"):
        if raiz.is_dir():
            for achado in raiz.glob("**/chrome*"):
                if achado.is_file() and achado.name.lower().startswith(("chrome", "chromium")):
                    candidatos.append(achado)
    return [c for c in candidatos if c.exists()]


def detectar(forcar: bool = False) -> dict:
    """O que existe nesta máquina: linguagens, frameworks e navegador."""
    global _deteccao
    agora = time.time()
    if not forcar and _deteccao and agora - _deteccao[0] < _CACHE_SEGUNDOS:
        return _deteccao[1]

    chrome = _caminhos_chrome()
    dados = {
        "python": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "node": _versao_comando("node"),
        "npm": _versao_comando("npm"),
        "selenium": _tem_modulo("selenium"),
        "playwright": _tem_modulo("playwright"),
        "pytest": _tem_modulo("pytest"),
        "puppeteer": None,
        "chrome": str(chrome[0]) if chrome else None,
        "sistema": f"{_SISTEMA} {platform.release()}",
    }
    if dados["node"]:
        try:
            achado = subprocess.run(["node", "-e", "process.stdout.write(require.resolve('puppeteer'))"],
                                    capture_output=True, text=True, timeout=_TIMEOUT_COMANDO,
                                    creationflags=_sem_janela())
            dados["puppeteer"] = bool(achado.returncode == 0 and achado.stdout.strip())
        except (subprocess.SubprocessError, OSError):
            dados["puppeteer"] = False
    _deteccao = (agora, dados)
    return dados


def resumo_ambiente(dados: dict | None = None) -> str:
    dados = dados or detectar()
    linhas = [f"- Python {dados['python']}"]
    linhas.append(f"- Node: {dados['node'] or 'não instalado'}")
    linhas.append(f"- Selenium: {'sim' if dados['selenium'] else 'não'}"
                  f" | Playwright: {'sim' if dados['playwright'] else 'não'}"
                  f" | Puppeteer: {'sim' if dados['puppeteer'] else 'não'}")
    linhas.append(f"- pytest: {'sim' if dados['pytest'] else 'não'}")
    linhas.append(f"- Navegador: {dados['chrome'] or 'não encontrado'}")
    faltando = []
    if not dados["selenium"] and not dados["puppeteer"]:
        faltando.append("pip install selenium (ou npm i puppeteer) para testes de UI")
    if not dados["pytest"]:
        faltando.append("pip install pytest para rodar os testes de UI em Python")
    if not dados["chrome"]:
        faltando.append("npx @puppeteer/browsers install chrome@stable (Chrome for Testing)")
    if faltando:
        linhas.append("- Para completar: " + "; ".join(faltando))
    return "\n".join(linhas)


# ── execução segura de comandos ──────────────────────────────────────────────
def executar(comando: list[str], timeout: float = _TIMEOUT_PADRAO, pasta: Path | None = None) -> dict:
    """Roda um comando da lista permitida e devolve código, saída e duração."""
    if not comando:
        return {"ok": False, "codigo": -1, "saida": "Comando vazio.", "segundos": 0.0}
    programa = Path(str(comando[0])).name.lower()
    if programa.endswith(".exe"):
        programa = programa[:-4]
    if not _PROGRAMA_OK.match(programa):
        return {"ok": False, "codigo": -1,
                "saida": f"'{comando[0]}' não está na lista de executores permitidos.",
                "segundos": 0.0}
    # Sem `shell=True` não existe encadeamento de shell para barrar: um `;` dentro
    # de um argumento é texto para o programa, não comando para o sistema. A
    # defesa que importa é a lista fechada de programas acima — e ela é o que
    # impede `bash -c` de passar.

    inicio = time.time()
    try:
        processo = subprocess.run(
            [str(c) for c in comando], capture_output=True, text=True, timeout=timeout,
            cwd=str(pasta) if pasta else None, creationflags=_sem_janela(),
            encoding="utf-8", errors="replace")
        return {
            "ok": processo.returncode == 0,
            "codigo": processo.returncode,
            "saida": ((processo.stdout or "") + (processo.stderr or "")).strip(),
            "segundos": round(time.time() - inicio, 2),
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "codigo": -2,
                "saida": f"O teste passou de {timeout:.0f}s e foi encerrado.",
                "segundos": round(time.time() - inicio, 2)}
    except (OSError, ValueError) as exc:
        return {"ok": False, "codigo": -3, "saida": f"Não consegui executar: {exc}",
                "segundos": round(time.time() - inicio, 2)}


# ── criação de testes de UI ──────────────────────────────────────────────────
def criar_teste_selenium(destino: Path, url: str, seletor: str, texto: str = "") -> Path:
    destino.parent.mkdir(parents=True, exist_ok=True)
    chrome = detectar().get("chrome") or ""
    alvo_texto = (texto or "").replace('"', '\\"')
    verificacao = (f'    assert "{alvo_texto}".lower() in corpo.lower()'
                   if texto else '    assert corpo.strip(), "a pagina veio vazia"')
    destino.write_text(f'''"""Teste de interface gerado pelo TORVIS (Selenium).

Rode com:  python -m pytest {destino.name} -v
"""
import pytest

URL = "{url}"
SELETOR = "{seletor}"
CHROME = "{chrome}"


@pytest.fixture()
def navegador():
    selenium = pytest.importorskip("selenium", reason="instale: pip install selenium")
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options

    opcoes = Options()
    opcoes.add_argument("--headless=new")
    opcoes.add_argument("--no-sandbox")
    opcoes.add_argument("--disable-gpu")
    opcoes.add_argument("--window-size=1366,900")
    if CHROME:
        opcoes.binary_location = CHROME
    driver = webdriver.Chrome(options=opcoes)
    driver.set_page_load_timeout(30)
    yield driver
    driver.quit()


def test_pagina_carrega_e_tem_o_elemento(navegador):
    navegador.get(URL)
    elemento = navegador.find_element("css selector", SELETOR)
    assert elemento.is_displayed(), f"o elemento {{SELETOR}} nao apareceu"


def test_conteudo_esperado(navegador):
    navegador.get(URL)
    corpo = navegador.find_element("tag name", "body").text
{verificacao}
''', encoding="utf-8")
    return destino


def criar_teste_puppeteer(destino: Path, url: str, seletor: str, texto: str = "") -> Path:
    destino.parent.mkdir(parents=True, exist_ok=True)
    chrome = detectar().get("chrome") or ""
    alvo_texto = (texto or "").replace("'", "\\'")
    verificacao = (f"  assert(corpo.includes('{alvo_texto}'), 'texto esperado nao encontrado')"
                   if texto else "  assert(corpo.trim().length > 0, 'pagina vazia')")
    destino.write_text(f'''// Teste de interface gerado pelo TORVIS (Puppeteer + Chrome for Testing).
// Rode com:  node {destino.name}
const assert = require("node:assert");
const puppeteer = require("puppeteer");

const URL = "{url}";
const SELETOR = "{seletor}";
const CHROME = "{chrome}";

(async () => {{
  const opcoes = {{ headless: "new", args: ["--no-sandbox", "--disable-gpu"] }};
  if (CHROME) opcoes.executablePath = CHROME;

  const navegador = await puppeteer.launch(opcoes);
  const pagina = await navegador.newPage();
  try {{
    await pagina.goto(URL, {{ waitUntil: "networkidle2", timeout: 30000 }});
    const elemento = await pagina.$(SELETOR);
    assert(elemento !== null, "elemento " + SELETOR + " nao encontrado");
    const corpo = await pagina.evaluate(() => document.body.innerText);
{verificacao}
    console.log("PASSOU: " + URL);
  }} finally {{
    await navegador.close();
  }}
}})().catch((erro) => {{
  console.error("FALHOU: " + erro.message);
  process.exit(1);
}});
''', encoding="utf-8")
    return destino


def rodar_ui(arquivo: Path, timeout: float = _TIMEOUT_PADRAO) -> dict:
    """Executa um teste de UI pelo runner certo e devolve o resultado."""
    arquivo = Path(arquivo).expanduser()
    if not arquivo.is_file():
        return {"ok": False, "saida": f"Não achei o arquivo {arquivo}."}
    if arquivo.suffix == ".py":
        ambiente = detectar()
        if not ambiente["pytest"]:
            return {"ok": False, "saida": "Falta o pytest: pip install pytest"}
        if not ambiente["selenium"]:
            return {"ok": False, "saida": "Falta o Selenium: pip install selenium"}
        return executar([sys.executable, "-m", "pytest", str(arquivo), "-v", "--tb=short"],
                        timeout=timeout, pasta=arquivo.parent)
    if arquivo.suffix in (".js", ".mjs", ".cjs"):
        ambiente = detectar()
        if not ambiente["node"]:
            return {"ok": False, "saida": "Node.js não está instalado."}
        if not ambiente["puppeteer"]:
            return {"ok": False, "saida": "Falta o Puppeteer: npm i puppeteer"}
        return executar(["node", str(arquivo)], timeout=timeout, pasta=arquivo.parent)
    return {"ok": False, "saida": "Só sei rodar testes .py (pytest) ou .js (node)."}


# ── testes de API ────────────────────────────────────────────────────────────
COLECAO_EXEMPLO = {
    "nome": "minha-api",
    "variaveis": {"base": "https://exemplo.com"},
    "testes": [
        {
            "nome": "lista de exemplo responde 200",
            "metodo": "GET",
            "url": "{{base}}/api/itens",
            "espera_status": 200,
            "espera_json": [{"caminho": "ok", "igual": True}],
            "limite_ms": 3000,
        },
    ],
}


def criar_colecao(destino: Path, base_url: str = "https://exemplo.com", nome: str = "minha-api") -> Path:
    destino.parent.mkdir(parents=True, exist_ok=True)
    modelo = json.loads(json.dumps(COLECAO_EXEMPLO))
    modelo["nome"] = nome
    modelo["variaveis"]["base"] = base_url
    modelo["testes"][0]["url"] = "{{base}}/api/itens"
    destino.write_text(json.dumps(modelo, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return destino


def _substituir(texto: str, variaveis: dict) -> str:
    def troca(encontro):
        chave = encontro.group(1).strip()
        return str(variaveis.get(chave, encontro.group(0)))

    return re.sub(r"\{\{\s*([\w.-]+)\s*\}\}", troca, str(texto or ""))


def _ler_caminho(dados, caminho: str):
    atual = dados
    for parte in str(caminho).split("."):
        if isinstance(atual, dict):
            atual = atual.get(parte)
        elif isinstance(atual, list) and parte.isdigit():
            indice = int(parte)
            atual = atual[indice] if 0 <= indice < len(atual) else None
        else:
            return None
    return atual


def rodar_colecao(colecao: dict, timeout: float = 15.0) -> dict:
    """Executa cada teste HTTP da coleção e devolve os resultados."""
    if not isinstance(colecao, dict) or not isinstance(colecao.get("testes"), list):
        return {"nome": "inválida", "resultados": [],
                "erro": "A coleção precisa de uma lista 'testes'."}

    variaveis = colecao.get("variaveis") or {}
    resultados = []
    for teste in colecao["testes"]:
        if not isinstance(teste, dict):
            continue
        nome = str(teste.get("nome") or teste.get("url") or "teste sem nome")
        metodo = str(teste.get("metodo") or "GET").upper()
        url = _substituir(teste.get("url") or "", variaveis)
        inicio = time.time()
        resultado = {"nome": nome, "metodo": metodo, "url": url,
                     "passou": False, "ms": 0, "detalhe": ""}
        if not url.lower().startswith(("http://", "https://")):
            resultado["detalhe"] = "URL inválida ou vazia."
            resultados.append(resultado)
            continue

        corpo = teste.get("corpo")
        if isinstance(corpo, (dict, list)):
            corpo = json.dumps(_substituir_json(corpo, variaveis)).encode("utf-8")
        elif corpo is not None:
            corpo = _substituir(str(corpo), variaveis).encode("utf-8")

        pedido = urllib.request.Request(url, data=corpo, method=metodo,
                                        headers={str(k): _substituir(str(v), variaveis)
                                                 for k, v in (teste.get("headers") or {}).items()})
        esperado = teste.get("espera_status")
        limite_ms = float(teste.get("limite_ms") or 0)
        try:
            with urllib.request.urlopen(pedido, timeout=timeout) as resposta:
                codigo = resposta.getcode()
                texto = resposta.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            codigo = exc.code
            texto = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
        except (urllib.error.URLError, OSError) as exc:
            resultado["ms"] = round((time.time() - inicio) * 1000)
            resultado["detalhe"] = f"sem resposta: {getattr(exc, 'reason', exc)}"
            resultados.append(resultado)
            continue

        resultado["status"] = codigo
        resultado["ms"] = round((time.time() - inicio) * 1000)
        problemas = []
        if esperado is not None and int(codigo) != int(esperado):
            problemas.append(f"status {codigo}, esperado {esperado}")
        if limite_ms and resultado["ms"] > limite_ms:
            problemas.append(f"lento: {resultado['ms']}ms (limite {limite_ms:.0f}ms)")

        dados = None
        if texto.strip().startswith(("{", "[")):
            try:
                dados = json.loads(texto)
            except ValueError:
                dados = None
        for regra in teste.get("espera_json") or []:
            if not isinstance(regra, dict):
                continue
            valor = _ler_caminho(dados, regra.get("caminho", ""))
            if "igual" in regra and valor != regra["igual"]:
                problemas.append(f"{regra.get('caminho')} = {valor!r}, esperado {regra['igual']!r}")
            if "existe" in regra and bool(valor is not None) != bool(regra["existe"]):
                problemas.append(f"{regra.get('caminho')} {'deveria' if regra['existe'] else 'não deveria'} existir")
        if teste.get("espera_texto") and str(teste["espera_texto"]) not in texto:
            problemas.append(f"texto '{teste['espera_texto']}' não encontrado")

        resultado["passou"] = not problemas
        resultado["detalhe"] = "; ".join(problemas) or "ok"
        resultados.append(resultado)

    return {"nome": str(colecao.get("nome") or "coleção"), "resultados": resultados}


def _substituir_json(valor, variaveis: dict):
    if isinstance(valor, str):
        return _substituir(valor, variaveis)
    if isinstance(valor, list):
        return [_substituir_json(v, variaveis) for v in valor]
    if isinstance(valor, dict):
        return {k: _substituir_json(v, variaveis) for k, v in valor.items()}
    return valor


# ── resultado: JUnit XML (o formato que todo mundo entende) ──────────────────
def junit_xml(resultado: dict) -> str:
    """JUnit XML a partir de um resultado, para Azure, Jira/Xray e pipelines."""
    testes = resultado.get("resultados") or []
    falhas = [t for t in testes if not t.get("passou")]
    suite = ET.Element("testsuite", {
        "name": str(resultado.get("nome") or "torvis"),
        "tests": str(len(testes)),
        "failures": str(len(falhas)),
        "errors": "0",
        "time": f"{sum(float(t.get('ms') or 0) for t in testes) / 1000:.3f}",
    })
    for teste in testes:
        caso = ET.SubElement(suite, "testcase", {
            "name": str(teste.get("nome") or "teste"),
            "classname": str(resultado.get("nome") or "torvis"),
            "time": f"{float(teste.get('ms') or 0) / 1000:.3f}",
        })
        if not teste.get("passou"):
            falha = ET.SubElement(caso, "failure", {"message": str(teste.get("detalhe") or "falhou")})
            falha.text = f"{teste.get('metodo', '')} {teste.get('url', '')}\n{teste.get('detalhe', '')}"
        if teste.get("saida"):
            ET.SubElement(caso, "system-out").text = str(teste["saida"])[:4000]
    return ET.tostring(suite, encoding="unicode")


def salvar_resultado(resultado: dict) -> dict:
    QA_DIR.mkdir(parents=True, exist_ok=True)
    arquivo = _resultados_file()
    arquivo.write_text(json.dumps(resultado, indent=2, ensure_ascii=False), encoding="utf-8")
    testes = resultado.get("resultados") or []
    falhas = sum(1 for t in testes if not t.get("passou"))
    return {"total": len(testes), "falhas": falhas, "arquivo": str(arquivo)}


def exportar_junit(resultado: dict, destino: Path | None = None) -> Path:
    QA_DIR.mkdir(parents=True, exist_ok=True)
    destino = Path(destino) if destino else QA_DIR / "resultado-junit.xml"
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(junit_xml(resultado), encoding="utf-8")
    return destino


def ler_resultado(caminho: Path | None = None) -> dict:
    caminho = Path(caminho) if caminho else _resultados_file()
    try:
        return json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


# ── plataformas ──────────────────────────────────────────────────────────────
_CHAVES = {
    "azure": ("azure_devops_org", "azure_devops_project", "azure_devops_pat"),
    "atlassian": ("atlassian_site", "atlassian_email", "atlassian_token", "atlassian_project"),
    "testai": ("testai_api_url", "testai_api_key"),
    "xray": ("xray_client_id", "xray_client_secret"),
}


def configurar_status() -> dict:
    try:
        from memory.config_manager import load_api_keys

        config = load_api_keys() or {}
    except Exception:                                     # noqa: BLE001
        config = {}
    saida = {}
    for plataforma, chaves in _CHAVES.items():
        faltando = [c for c in chaves if not str(config.get(c) or "").strip()]
        saida[plataforma] = {"configurada": not faltando, "faltando": faltando}
    return {"plataformas": saida, "config": config}


def resumo_plataformas() -> str:
    dados = configurar_status()["plataformas"]
    linhas = []
    nomes = {"azure": "Azure Test Plans", "atlassian": "Jira / Atlassian",
             "testai": "Test.ai", "xray": "Xray (Jira Cloud)"}
    for chave, info in dados.items():
        if info["configurada"]:
            linhas.append(f"- {nomes[chave]}: configurado")
        else:
            linhas.append(f"- {nomes[chave]}: falta {', '.join(info['faltando'])}")
    linhas.append("- Sem plataforma configurada dá para usar o JUnit XML: Azure Pipelines, "
                  "GitHub Actions e Xray aceitam esse arquivo direto.")
    return "\n".join(linhas)


def _post_json(url: str, corpo: dict, cabecalhos: dict, timeout: float = 20.0):
    pedido = urllib.request.Request(url, method="POST",
                                    data=json.dumps(corpo).encode("utf-8"),
                                    headers={"Content-Type": "application/json",
                                             "Accept": "application/json", **cabecalhos})
    with urllib.request.urlopen(pedido, timeout=timeout) as resposta:
        texto = resposta.read().decode("utf-8", errors="replace")
    return json.loads(texto) if texto.strip().startswith(("{", "[")) else {}


def publicar_azure(resultado: dict) -> str:
    """Cria uma execução de teste no Azure Test Plans e joga os resultados nela."""
    dados = configurar_status()
    info = dados["plataformas"]["azure"]
    if not info["configurada"]:
        return ("Para publicar no Azure Test Plans faltam no config.json: "
                + ", ".join(info["faltando"]) + ". O JUnit XML já está pronto e o Azure "
                "Pipelines publica esse arquivo sem token.")
    config = dados["config"]
    org = str(config["azure_devops_org"]).strip().rstrip("/")
    projeto = str(config["azure_devops_project"]).strip()
    import base64

    token = base64.b64encode(f":{config['azure_devops_pat']}".encode()).decode()
    cabecalhos = {"Authorization": f"Basic {token}"}
    base = f"https://dev.azure.com/{org}/{urllib.parse.quote(projeto)}/_apis/test"
    testes = resultado.get("resultados") or []

    try:
        corrida = _post_json(f"{base}/runs?api-version=7.1",
                             {"name": f"TORVIS {time.strftime('%d/%m %H:%M')}",
                              "automated": True, "state": "InProgress"}, cabecalhos)
        corrida_id = corrida.get("id")
        if not corrida_id:
            return "O Azure aceitou a conexão mas não devolveu o id da execução."
        pontos = []
        for teste in testes:
            pontos.append({
                "testCaseTitle": str(teste.get("nome"))[:250],
                "automatedTestName": str(teste.get("url"))[:250],
                "outcome": "Passed" if teste.get("passou") else "Failed",
                "durationInMs": int(teste.get("ms") or 0),
                "errorMessage": "" if teste.get("passou") else str(teste.get("detalhe"))[:1000],
            })
        _post_json(f"{base}/runs/{corrida_id}/results?api-version=7.1", pontos, cabecalhos)
    except urllib.error.HTTPError as exc:
        return f"O Azure recusou a publicação (HTTP {exc.code}). Confira organização, projeto e PAT."
    except Exception as exc:                              # noqa: BLE001
        return f"Não consegui publicar no Azure: {exc}"

    aprovados = sum(1 for t in testes if t.get("passou"))
    return f"Execução {corrida_id} criada no Azure Test Plans: {aprovados} passaram, {len(testes) - aprovados} falharam."


def publicar_jira(resultado: dict) -> str:
    """Abre um issue no Jira para cada teste que falhou (máximo 10)."""
    dados = configurar_status()
    info = dados["plataformas"]["atlassian"]
    if not info["configurada"]:
        return ("Para abrir issue no Jira faltam no config.json: "
                + ", ".join(info["faltando"]) + ". O JUnit XML também pode ser importado "
                "pelo Xray, que evita um issue por falha.")
    config = dados["config"]
    site = str(config["atlassian_site"]).strip().rstrip("/")
    if not site.startswith("http"):
        site = f"https://{site}"
    projeto = str(config["atlassian_project"]).strip()
    import base64

    credencial = base64.b64encode(
        f"{config['atlassian_email']}:{config['atlassian_token']}".encode()).decode()
    falhas = [t for t in (resultado.get("resultados") or []) if not t.get("passou")][:10]
    if not falhas:
        return "Nenhum teste falhou: não há issue para abrir no Jira."

    abertos, erros = 0, []
    for teste in falhas:
        corpo = {
            "fields": {
                "project": {"key": projeto},
                "summary": f"[teste] {str(teste.get('nome'))[:200]}",
                "issuetype": {"name": "Bug"},
                "description": {
                    "type": "doc", "version": 1,
                    "content": [{"type": "paragraph", "content": [{
                        "type": "text",
                        "text": f"{teste.get('metodo', '')} {teste.get('url', '')}\n"
                                f"Status: {teste.get('status', '—')} | {teste.get('ms', 0)}ms\n"
                                f"Motivo: {teste.get('detalhe', '')}"}]}],
                },
            }
        }
        try:
            _post_json(f"{site}/rest/api/3/issue",
                       corpo, {"Authorization": f"Basic {credencial}"})
            abertos += 1
        except urllib.error.HTTPError as exc:
            erros.append(f"HTTP {exc.code}")
        except Exception as exc:                          # noqa: BLE001
            erros.append(str(exc))
    if not abertos:
        return ("O Jira recusou a criação (" + (erros[0] if erros else "sem detalhe") +
                "). Confira site, e-mail, token e a permissão de criar Bug no projeto " + projeto + ".")
    return f"{abertos} issue(s) aberta(s) no Jira para os testes que falharam."


def preparar_testai(resultado: dict) -> str:
    """Test.ai recebe o resultado por API deles; aqui montamos o pacote."""
    QA_DIR.mkdir(parents=True, exist_ok=True)
    dados = configurar_status()
    config = dados["config"]
    pacote = {
        "suite": str(resultado.get("nome") or "torvis"),
        "executed_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "results": [{
            "name": str(t.get("nome")), "status": "passed" if t.get("passou") else "failed",
            "duration_ms": int(t.get("ms") or 0), "message": str(t.get("detalhe") or ""),
        } for t in (resultado.get("resultados") or [])],
    }
    caminho = QA_DIR / "testai_payload.json"
    caminho.write_text(json.dumps(pacote, indent=2, ensure_ascii=False), encoding="utf-8")
    if dados["plataformas"]["testai"]["configurada"]:
        url = str(config["testai_api_url"]).rstrip("/")
        try:
            _post_json(url, pacote, {"Authorization": f"Bearer {config['testai_api_key']}"})
            return "Resultado enviado ao Test.ai."
        except Exception as exc:                          # noqa: BLE001
            return f"Test.ai não aceitou o envio ({exc}). O pacote ficou em {caminho}."
    return (f"Pacote para o Test.ai pronto em {caminho}. Para enviar direto, configure "
            "'testai_api_url' e 'testai_api_key' no config.json.")


def gerar_pipeline(plataforma: str, destino: Path) -> Path:
    """Pipeline pronta que roda pytest e publica o JUnit, no CI do usuário."""
    destino.parent.mkdir(parents=True, exist_ok=True)
    plataforma = (plataforma or "azure").strip().lower()
    if plataforma in ("github", "gh", "actions"):
        destino = destino.with_suffix(".yml")
        destino.write_text('''name: testes
on: [push, pull_request]
jobs:
  testes:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: {python-version: "3.12"}
      - run: pip install pytest selenium
      - run: python -m pytest -v --junitxml=resultado-junit.xml
      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: resultado-junit
          path: resultado-junit.xml
''', encoding="utf-8")
        return destino

    destino = destino.with_suffix(".yml")
    destino.write_text('''trigger:
  - main
pool:
  vmImage: ubuntu-latest
steps:
  - task: UsePythonVersion@0
    inputs: {versionSpec: "3.12"}
  - script: pip install pytest selenium
    displayName: Dependencias
  - script: python -m pytest -v --junitxml=$(Build.SourcesDirectory)/resultado-junit.xml
    displayName: Testes
    continueOnError: true
  - task: PublishTestResults@2
    inputs:
      testResultsFormat: JUnit
      testResultsFiles: resultado-junit.xml
      failTaskOnFailedTests: true
''', encoding="utf-8")
    return destino
