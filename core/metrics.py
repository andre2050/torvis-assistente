"""Métricas de inicialização e resposta: sem número, "está lento" não vira melhoria.

Cada marca é um instante desde o início do processo. Ao final, as diferenças
mostram onde o tempo foi gasto: importação, construção da janela, primeira
resposta da IA. Fica em `metricas.jsonl` na pasta de estado, uma linha por
abertura, para comparar versões depois.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from core.paths import STATE_DIR

ARQUIVO = STATE_DIR / "metricas.jsonl"
_INICIO = time.monotonic()
_MARCAS: dict[str, float] = {}
_LIMITE_LINHAS = 200          # mantém o arquivo pequeno


def marcar(nome: str) -> float:
    """Registra o instante de um marco; devolve os ms desde o início do processo."""
    agora = time.monotonic()
    _MARCAS[nome] = agora
    return int((agora - _INICIO) * 1000)


def desde(nome: str) -> int | None:
    """Milissegundos entre o início do processo e o marco."""
    valor = _MARCAS.get(nome)
    return int((valor - _INICIO) * 1000) if valor else None


def intervalo(primeiro: str, segundo: str) -> int | None:
    a, b = _MARCAS.get(primeiro), _MARCAS.get(segundo)
    return int((b - a) * 1000) if a is not None and b is not None else None


def salvar(extra: dict | None = None) -> None:
    """Grava a linha desta execução. Falha de escrita nunca derruba o app."""
    registro = {nome: desde(nome) for nome in _MARCAS}
    registro["versao"] = _versao()
    registro["quando"] = time.strftime("%Y-%m-%d %H:%M:%S")
    if extra:
        registro.update(extra)
    try:
        ARQUIVO.parent.mkdir(parents=True, exist_ok=True)
        with ARQUIVO.open("a", encoding="utf-8") as f:
            f.write(json.dumps(registro, ensure_ascii=False) + "\n")
        _podar()
    except OSError:
        pass


def _podar() -> None:
    try:
        linhas = ARQUIVO.read_text(encoding="utf-8").splitlines()
        if len(linhas) > _LIMITE_LINHAS:
            ARQUIVO.write_text("\n".join(linhas[-_LIMITE_LINHAS:]) + "\n", encoding="utf-8")
    except OSError:
        pass


def _versao() -> str:
    try:
        from core.version import VERSAO

        return VERSAO
    except Exception:
        return "?"


def ultima() -> dict:
    try:
        linhas = ARQUIVO.read_text(encoding="utf-8").splitlines()
        return json.loads(linhas[-1]) if linhas else {}
    except (OSError, ValueError):
        return {}


def resumo() -> str:
    """Texto curto com os marcos desta execução, para o relatório."""
    marcos = {nome: desde(nome) for nome in _MARCAS}
    if not marcos:
        return "nenhuma métrica registrada nesta execução"
    linhas = [f"{nome}: {ms} ms" for nome, ms in marcos.items() if ms is not None]
    anterior = ultima()
    if anterior:
        linhas.append(f"(execução anterior: {anterior})")
    return "\n".join(linhas)
