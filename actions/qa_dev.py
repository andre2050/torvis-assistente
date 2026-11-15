"""Ação `qa_dev`: a trilha de testes do TORVIS numa ferramenta só.

Cobre as quatro frentes pedidas, sem inventar integração que não existe:

    UI          criar_ui / rodar_ui      Selenium (Python) e Puppeteer (Node)
    API         criar_api / rodar_api    HTTP puro, sem dependência extra
    Plataformas plataformas / publicar   Azure Test Plans, Test.ai
    DevOps      pipeline / publicar      Jira/Atlassian, Azure Pipelines, GitHub Actions

O que amarra tudo é o JUnit XML: é o que Azure, Xray e os pipelines leem.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from core import qa
from core.paths import STATE_DIR

_PASTA = STATE_DIR / "qa" / "testes"


def _log(mensagem: str, player=None) -> None:
    print(f"[Testes] {mensagem[:300]}")
    if player:
        try:
            player.write_log(f"Assistente Inteligente: {mensagem[:300]}")
        except Exception:                                 # noqa: BLE001
            pass


def _pasta(nome_arquivo: str) -> Path:
    _PASTA.mkdir(parents=True, exist_ok=True)
    return _PASTA / nome_arquivo


def _resumo_execucao(resultado: dict) -> str:
    """Uma frase honesta sobre o que passou e o que não passou."""
    testes = resultado.get("resultados") or []
    if not testes:
        return "Nenhum teste rodou."
    falhas = [t for t in testes if not t.get("passou")]
    aprovados = len(testes) - len(falhas)
    cabeca = f"{aprovados} de {len(testes)} passaram."
    if not falhas:
        return cabeca
    detalhes = "; ".join(f"{t.get('nome')}: {t.get('detalhe')}" for t in falhas[:3])
    return f"{cabeca} Falhas: {detalhes}"


def qa_dev_action(parameters: dict, player=None, session_memory=None) -> str:
    acao = str(parameters.get("action") or "diagnostico").strip().lower()
    try:
        resposta = _rotas(acao, parameters)
    except Exception as exc:                              # noqa: BLE001
        resposta = f"A trilha de testes parou num erro inesperado: {exc}"
    _log(resposta, player)
    return resposta


def _rotas(acao: str, parameters: dict) -> str:
    if acao in ("diagnostico", "diagnóstico", "status", "ambiente"):
        ambiente = qa.detectar(forcar=True)
        return "Ambiente de testes:\n" + qa.resumo_ambiente(ambiente)

    if acao in ("criar_ui", "criar teste de ui"):
        framework = str(parameters.get("framework") or "selenium").strip().lower()
        url = str(parameters.get("url") or "").strip()
        seletor = str(parameters.get("selector") or parameters.get("seletor") or "body").strip()
        texto = str(parameters.get("expect_text") or parameters.get("texto") or "").strip()
        if not url.lower().startswith(("http://", "https://")):
            return "Me diga a URL da página que o teste deve abrir."
        if framework.startswith(("puppeteer", "node", "js")):
            destino = qa.criar_teste_puppeteer(_pasta("teste_ui.js"), url, seletor, texto)
            return (f"Teste de UI em Puppeteer criado em {destino}. "
                    "Rode com 'rodar_ui' e o caminho desse arquivo.")
        destino = qa.criar_teste_selenium(_pasta("teste_ui.py"), url, seletor, texto)
        return (f"Teste de UI em Selenium criado em {destino}. "
                "Rode com 'rodar_ui' e o caminho desse arquivo.")

    if acao in ("rodar_ui", "rodar teste de ui"):
        caminho = parameters.get("path") or parameters.get("arquivo")
        if not caminho:
            padrao = _PASTA / "teste_ui.py"
            if not padrao.is_file():
                return ("Não tenho um teste de UI para rodar. Crie primeiro com 'criar_ui', "
                        "ou me diga o caminho do arquivo.")
            caminho = padrao
        resultado = qa.rodar_ui(Path(str(caminho)).expanduser(),
                                float(parameters.get("timeout") or 180))
        if "resultados" not in resultado:                  # falha de ambiente, não de teste
            return f"Não consegui rodar o teste: {resultado.get('saida')}."
        resumo = qa.salvar_resultado(resultado)
        junit = qa.exportar_junit(resultado)
        return (f"{_resumo_execucao(resultado)} ({resultado.get('segundos', '—')}s). "
                f"JUnit salvo em {junit}.")

    if acao in ("criar_api", "criar teste de api"):
        base = str(parameters.get("base_url") or parameters.get("url") or "https://exemplo.com")
        nome = str(parameters.get("name") or parameters.get("nome") or "minha-api")
        destino = qa.criar_colecao(_pasta("testes_api.json"), base, nome)
        return (f"Coleção de testes de API criada em {destino}. Edite os testes nela e rode "
                "com 'rodar_api'. O formato aceita método, cabeçalhos, corpo, status esperado, "
                "campo JSON esperado e tempo limite.")

    if acao in ("rodar_api", "rodar teste de api"):
        caminho = parameters.get("path") or parameters.get("arquivo")
        if caminho:
            try:
                colecao = json.loads(Path(str(caminho)).expanduser().read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                return f"Não consegui ler a coleção {caminho}: {exc}"
        elif isinstance(parameters.get("collection"), dict):
            colecao = parameters["collection"]
        else:
            padrao = _PASTA / "testes_api.json"
            if not padrao.is_file():
                return "Não tenho coleção de API para rodar. Crie com 'criar_api'."
            colecao = json.loads(padrao.read_text(encoding="utf-8"))

        resultado = qa.rodar_colecao(colecao, float(parameters.get("timeout") or 15))
        if resultado.get("erro"):
            return resultado["erro"]
        qa.salvar_resultado(resultado)
        junit = qa.exportar_junit(resultado)
        return f"{_resumo_execucao(resultado)} JUnit salvo em {junit}."

    if acao in ("plataformas", "configuracao", "configuração"):
        return "Plataformas de teste:\n" + qa.resumo_plataformas()

    if acao in ("publicar", "publicar_resultado"):
        resultado = qa.ler_resultado()
        if not resultado.get("resultados"):
            return "Não há resultado de execução para publicar. Rode um teste antes."
        destino = str(parameters.get("target") or parameters.get("destino") or "junit").strip().lower()
        if destino.startswith("azure"):
            return qa.publicar_azure(resultado)
        if destino.startswith(("jira", "atlassian")):
            return qa.publicar_jira(resultado)
        if destino.startswith("test"):
            return qa.preparar_testai(resultado)
        caminho = qa.exportar_junit(resultado)
        return f"JUnit XML gravado em {caminho}. Azure Pipelines, GitHub Actions e Xray importam esse arquivo."

    if acao in ("pipeline", "ci"):
        plataforma = str(parameters.get("platform") or parameters.get("plataforma") or "azure").strip().lower()
        destino = qa.gerar_pipeline(plataforma, _pasta("pipeline"))
        return (f"Pipeline criada em {destino}. Ela instala as dependências, roda o pytest e "
                "publica o JUnit no painel de testes do CI.")

    return ("Posso: diagnosticar o ambiente, criar e rodar teste de UI (Selenium/Puppeteer), "
            "criar e rodar teste de API, mostrar as plataformas, publicar o resultado e gerar pipeline.")


TOOL = {
    "name": "qa_dev",
    "description": (
        "Trilha de testes automatizados para desenvolvimento. 'diagnostico' mostra o que existe "
        "na máquina (Python, Node, Selenium, Puppeteer, Chrome). 'criar_ui' cria teste de "
        "interface em Selenium ou Puppeteer e 'rodar_ui' executa. 'criar_api' cria uma coleção "
        "de testes HTTP e 'rodar_api' executa com asserções de status, JSON e tempo. 'plataformas' "
        "mostra o que está configurado em Azure Test Plans, Test.ai e Jira. 'publicar' envia o "
        "último resultado para JUnit, Azure, Jira ou Test.ai. 'pipeline' gera a pipeline de CI. "
        "Use sempre que pedirem teste automatizado, teste de tela, teste de API ou pipeline de testes."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "diagnostico | criar_ui | rodar_ui | criar_api | rodar_api | plataformas | publicar | pipeline",
                "enum": ["diagnostico", "criar_ui", "rodar_ui", "criar_api", "rodar_api",
                         "plataformas", "publicar", "pipeline"],
            },
            "framework": {
                "type": "STRING",
                "description": "Para criar_ui: selenium (Python) ou puppeteer (Node).",
                "enum": ["selenium", "puppeteer"],
            },
            "url": {"type": "STRING", "description": "URL da página a testar, ou URL base no criar_api."},
            "selector": {"type": "STRING", "description": "Seletor CSS do elemento, ex: '#login', 'h1'."},
            "expect_text": {"type": "STRING", "description": "Texto que precisa aparecer na página."},
            "path": {"type": "STRING", "description": "Caminho do arquivo de teste ou da coleção JSON."},
            "timeout": {"type": "NUMBER", "description": "Segundos até desistir do teste (padrão 180 UI, 15 API)."},
            "target": {
                "type": "STRING",
                "description": "Para publicar: junit | azure | jira | testai",
                "enum": ["junit", "azure", "jira", "testai"],
            },
            "platform": {
                "type": "STRING",
                "description": "Para pipeline: azure ou github.",
                "enum": ["azure", "github"],
            },
        },
        "required": ["action"],
    },
    "tier": "core",
    "brief": "Trilha de testes: UI (Selenium/Puppeteer), API, Azure/Jira/Test.ai e pipeline.",
    "handler": qa_dev_action,
}
