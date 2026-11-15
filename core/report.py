"""Relatório de um clique: tudo o que é preciso saber sobre uma falha, num arquivo.

Por que existe: quando algo dá errado, a conversa vira "deu erro" e o diagnóstico
recomeça do zero, porque o aviso na tela some e ninguém sabe a versão, a rede, a
ordem dos modelos nem o último traceback. Este módulo junta tudo em um .txt para
ser anexado.
"""
from __future__ import annotations

import platform
import sys
import time
from datetime import datetime
from pathlib import Path

SAIDA_PADRAO = "relatorio-torvis.txt"


def _secao(titulo: str) -> str:
    return f"\n{'=' * 62}\n{titulo}\n{'=' * 62}\n"


def _versao() -> str:
    try:
        from core.version import VERSAO

        return VERSAO
    except Exception:
        return "desconhecida"


def _sistema() -> str:
    linhas = [
        f"Sistema: {platform.platform()}",
        f"Python:  {sys.version.split()[0]} ({platform.architecture()[0]})",
        f"Pasta:   {Path(__file__).resolve().parent.parent}",
        f"Data:    {datetime.now():%d/%m/%Y %H:%M:%S}",
    ]
    try:
        import psutil

        processo = psutil.Process()
        linhas.append(f"RAM em uso: {processo.memory_info().rss / 1024 / 1024:.0f} MB")
        linhas.append(f"Tempo ligado: {time.time() - processo.create_time():.0f} s")
    except Exception:
        linhas.append("RAM em uso: psutil não instalado")
    return "\n".join(linhas)


def _dependencias() -> str:
    import importlib.util

    itens = ("PyQt6", "google.genai", "sounddevice", "psutil", "numpy", "httpx")
    return "\n".join(f"{'OK   ' if importlib.util.find_spec(m) else 'FALTA'} {m}" for m in itens)


def _rede() -> str:
    try:
        from core.netguard_report import texto

        return texto()
    except Exception as exc:
        return f"não foi possível testar a rede: {type(exc).__name__}: {exc}"


def _modelos() -> str:
    try:
        from core import gemini, model_ladder

        linhas = []
        for tipo, linha in model_ladder.resumo(gemini.api_key()):
            marca = {"ok": "✔", "aviso": "!", "erro": "✖"}.get(tipo, "·")
            linhas.append(f"{marca} {linha}")
        return "\n".join(linhas) or "sem medições"
    except Exception as exc:
        return f"não foi possível ler a escada: {type(exc).__name__}: {exc}"


def _erros() -> str:
    try:
        from core import errlog

        blocos = errlog.ultimos(5)
        return "\n\n".join(blocos) if blocos else "nenhum erro registrado"
    except Exception as exc:
        return f"não foi possível ler o log: {type(exc).__name__}: {exc}"


def _metricas() -> str:
    try:
        from core import metrics

        return metrics.resumo()
    except Exception as exc:
        return f"não foi possível ler as métricas: {type(exc).__name__}: {exc}"


def gerar(destino: str | Path | None = None) -> Path:
    """Escreve o relatório e devolve o caminho. Nunca levanta por falha de seção."""
    partes = [f"T.O.R.V.I.S. 2026 — relatório de diagnóstico (versão {_versao()})"]
    partes.append(_secao("SISTEMA") + _sistema())
    partes.append(_secao("DEPENDÊNCIAS") + _dependencias())
    partes.append(_secao("REDE") + _rede())
    partes.append(_secao("MODELOS (ordem aprendida)") + _modelos())
    partes.append(_secao("ÚLTIMOS ERROS") + _erros())
    partes.append(_secao("MÉTRICAS") + _metricas())
    partes.append("\nAnexe este arquivo ao pedir ajuda. Ele não contém a sua chave.\n")

    caminho = Path(destino or SAIDA_PADRAO)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text("\n".join(partes), encoding="utf-8")
    return caminho


if __name__ == "__main__":
    print(f"Relatório salvo em: {gerar(sys.argv[1] if len(sys.argv) > 1 else None).resolve()}")
