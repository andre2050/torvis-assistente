"""Ordem da escada de modelos, aprendida do uso real.

O problema que isto resolve: a escada fixa em core/gemini.py foi medida uma vez,
em um dia e com uma chave. Quando um degrau fica lento (504 depois de 14 s) ou
sai para a chave atual (404), a conversa paga esse tempo de novo a cada chamada,
porque a ordem nunca muda.

Aqui a ordem passa a vir da medição de verdade — e sem gastar cota: cada
conversa que já acontece registra quanto tempo aquele modelo levou. Nenhuma
requisição extra é feita para medir.

Regras:
  * o que respondeu rápido fica na frente;
  * o que nunca foi medido mantém a posição original (não mexemos no que não sabemos);
  * o que falhou por cota/indisponibilidade vai para o fim e é reavaliado depois;
  * medidas com mais de 7 dias são descartadas, porque a API muda.
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

from core.paths import STATE_DIR

_ARQUIVO = STATE_DIR / "model_ladder.json"
_AMOSTRAS = 5                 # ultimas medicoes consideradas por modelo
_VALIDADE = 7 * 24 * 3600     # 7 dias


def _impressao(key: str) -> str:
    """Identifica a chave sem guardá-la."""
    return hashlib.sha256(("" if not key else key).encode("utf-8")).hexdigest()[:10]


def _ler() -> dict:
    try:
        dados = json.loads(Path(_ARQUIVO).read_text(encoding="utf-8"))
        return dados if isinstance(dados, dict) else {}
    except (OSError, ValueError):
        return {}


def _gravar(dados: dict) -> None:
    try:
        _ARQUIVO.parent.mkdir(parents=True, exist_ok=True)
        temporario = _ARQUIVO.with_suffix(".tmp")
        temporario.write_text(json.dumps(dados, indent=2), encoding="utf-8")
        temporario.replace(_ARQUIVO)          # troca atômica: nunca deixa arquivo pela metade
    except OSError:
        pass                                   # cache é conveniência, não pode quebrar a conversa


def _modelos(key: str) -> dict:
    return _ler().get(_impressao(key), {})


def _valido(medida: dict) -> bool:
    return bool(medida) and (time.time() - float(medida.get("at", 0))) < _VALIDADE


def registrar_sucesso(key: str, modelo: str, ms: int) -> None:
    """Chamado a cada resposta recebida; média das últimas amostras."""
    if not modelo or modelo.startswith("prov:") or modelo == "live":
        return                       # provedores externos e Live têm regras próprias
    dados = _ler()
    chave = dados.setdefault(_impressao(key), {})
    item = chave.setdefault(modelo, {"ms": [], "falhas": 0})
    amostras = [int(ms)] + list(item.get("ms") or [])
    item["ms"] = amostras[:_AMOSTRAS]
    item["falhas"] = 0
    item["at"] = time.time()
    _gravar(dados)


def registrar_falha(key: str, modelo: str) -> None:
    """Cota, indisponibilidade ou modelo retirado: esse degrau vai para o fim."""
    if not modelo or modelo.startswith("prov:") or modelo == "live":
        return
    dados = _ler()
    chave = dados.setdefault(_impressao(key), {})
    item = chave.setdefault(modelo, {"ms": [], "falhas": 0})
    item["falhas"] = int(item.get("falhas", 0)) + 1
    item["at"] = time.time()
    _gravar(dados)


def media_ms(key: str, modelo: str) -> int | None:
    """Média medida; None quando nunca foi medido ou quando a medida venceu."""
    item = _modelos(key).get(modelo) or {}
    if not _valido(item):
        return None
    amostras = [m for m in (item.get("ms") or []) if isinstance(m, int)]
    return int(sum(amostras) / len(amostras)) if amostras else None


def ordenar(ladder, key: str = "") -> list:
    """Devolve a escada na ordem que o uso real recomenda."""
    rungs = list(ladder)
    try:
        medidos = _modelos(key)
    except Exception:
        return rungs

    def posicao(par):
        indice, modelo = par
        item = medidos.get(modelo) or {}
        if not _valido(item):
            return (1, 0, indice)            # desconhecido: mantém a posição relativa
        if int(item.get("falhas", 0)) > 0:
            return (2, 0, indice)            # falhou: para o fim
        amostras = [m for m in (item.get("ms") or []) if isinstance(m, int)]
        if not amostras:
            return (1, 0, indice)
        return (0, int(sum(amostras) / len(amostras)), indice)

    return [modelo for _, modelo in sorted(enumerate(rungs), key=posicao)]


def resumo(key: str = "") -> list[tuple[str, str]]:
    """Linhas para o diagnóstico: o que já foi medido nesta chave."""
    medidos = _modelos(key)
    if not medidos:
        return [("info", "Ainda sem medições: a ordem será aprendida nas próximas conversas.")]
    linhas: list[tuple[str, str]] = []
    for modelo, item in sorted(medidos.items(),
                               key=lambda par: media_ms(key, par[0]) or 999999):
        if not _valido(item):
            continue
        media = media_ms(key, modelo)
        falhas = int(item.get("falhas", 0))
        if falhas:
            linhas.append(("aviso", f"{modelo}: {falhas} falha(s) recente(s) — foi para o fim"))
        elif media is not None:
            linhas.append(("ok", f"{modelo}: {media} ms (média de {len(item.get('ms') or [])})"))
    return linhas or [("info", "Sem medições válidas no momento.")]


def esquecer(key: str = "") -> None:
    """Descarta o aprendizado desta chave (útil ao trocar de conta)."""
    dados = _ler()
    dados.pop(_impressao(key), None)
    _gravar(dados)
