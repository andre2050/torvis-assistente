"""Desfazer global: o ponto de retorno que sobrevive ao fechar o app.

O `core/undo.py` já sabe desfazer, mas guarda funções em memória: ao fechar o
TORVIS, some. Se o Computer Use mexeu em dez arquivos e você só percebeu no dia
seguinte, não havia para onde voltar.

Aqui a garantia é outra: antes de um arquivo ser escrito, apagado ou movido, o
conteúdo anterior é copiado para `userdata/desfazer/<lote>/` e o que aconteceu
vai para um diário em disco. Desfazer relê o diário, devolve cada arquivo ao
lugar e apaga o que havia sido criado — inclusive depois de reiniciar.

O que NÃO entra aqui: ação que não tem cópia possível (volume, brilho, janela).
Essas continuam no `undo.py`, que é rápido e só vale na sessão.
"""
from __future__ import annotations

import json
import shutil
import time
import uuid
from pathlib import Path
from typing import Any

from core.userdata import USERDATA_DIR

PASTA = USERDATA_DIR / "desfazer"
DIARIO = USERDATA_DIR / "desfazer.jsonl"
MAX_LOTES = 20          # quantos lotes ficam guardados antes do mais velho sair
LIMITE_ARQUIVO = 64 * 1024 * 1024   # não copia arquivo gigante; registra o aviso


def _lote_novo() -> str:
    return time.strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6]


def _anotar(registro: dict[str, Any]) -> None:
    DIARIO.parent.mkdir(parents=True, exist_ok=True)
    with DIARIO.open("a", encoding="utf-8") as f:
        f.write(json.dumps(registro, ensure_ascii=False) + "\n")


def _ler_diario() -> list[dict[str, Any]]:
    try:
        linhas = DIARIO.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    registros = []
    for linha in linhas:
        linha = linha.strip()
        if not linha:
            continue
        try:
            registros.append(json.loads(linha))
        except ValueError:
            continue
    return registros


def _purgar_antigos() -> None:
    try:
        lotes = sorted(p for p in PASTA.iterdir() if p.is_dir())
    except OSError:
        return
    for lote in lotes[:-MAX_LOTES]:
        shutil.rmtree(lote, ignore_errors=True)


def guardar(caminho: Path | str, lote: str | None = None) -> dict[str, Any]:
    """Guarda o conteúdo atual do arquivo antes de ele ser alterado.

    Devolve o registro criado. Arquivo que não existe é registrado como
    `criado`, porque desfazer uma criação é apagar o que apareceu.
    """
    alvo = Path(caminho).expanduser()
    lote = lote or _lote_novo()
    pasta = PASTA / lote
    pasta.mkdir(parents=True, exist_ok=True)

    if not alvo.exists():
        registro = {"lote": lote, "tipo": "criado", "caminho": str(alvo),
                    "quando": time.time()}
        _anotar(registro)
        return registro

    tamanho = alvo.stat().st_size
    if tamanho > LIMITE_ARQUIVO:
        registro = {"lote": lote, "tipo": "grande", "caminho": str(alvo),
                    "quando": time.time(), "bytes": tamanho}
        _anotar(registro)
        return registro

    copia = pasta / f"{uuid.uuid4().hex[:8]}-{alvo.name}"
    shutil.copy2(alvo, copia)
    registro = {"lote": lote, "tipo": "copia", "caminho": str(alvo),
                "copia": str(copia), "quando": time.time(), "bytes": tamanho}
    _anotar(registro)
    _purgar_antigos()
    return registro


def lotes() -> list[str]:
    """Lotes conhecidos, do mais novo para o mais antigo."""
    vistos: list[str] = []
    for registro in _ler_diario():
        lote = registro.get("lote")
        if lote and lote not in vistos:
            vistos.append(lote)
    return list(reversed(vistos))


def resumo(lote: str | None = None) -> list[dict[str, Any]]:
    registros = _ler_diario()
    if lote:
        registros = [r for r in registros if r.get("lote") == lote]
    return registros


def desfazer(lote: str | None = None) -> dict[str, Any]:
    """Volta um lote inteiro ao estado anterior.

    Sem argumento, desfaz o lote mais recente. As ações são revertidas na ordem
    inversa em que aconteceram: se o mesmo arquivo foi escrito duas vezes, o
    primeiro desfazer devolve a versão intermediária e o segundo a original.
    """
    todos = _ler_diario()
    if not todos:
        return {"ok": False, "motivo": "nada para desfazer"}
    lote = lote or todos[-1].get("lote")
    registros = [r for r in todos if r.get("lote") == lote]
    if not registros:
        return {"ok": False, "motivo": f"lote {lote} não encontrado"}

    restaurados, removidos, falhas = [], [], []
    for registro in reversed(registros):
        alvo = Path(registro["caminho"])
        tipo = registro.get("tipo")
        try:
            if tipo == "copia":
                copia = Path(registro["copia"])
                if not copia.exists():
                    falhas.append(f"{alvo.name}: a cópia sumiu do cofre")
                    continue
                alvo.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(copia, alvo)
                restaurados.append(str(alvo))
            elif tipo == "criado":
                if alvo.is_file():
                    alvo.unlink()
                    removidos.append(str(alvo))
            elif tipo == "grande":
                falhas.append(f"{alvo.name}: era grande demais para copiar, não tenho a versão anterior")
        except OSError as exc:
            falhas.append(f"{alvo.name}: {exc}")

    # o lote sai do diário: desfazer duas vezes o mesmo lote seria mentira
    restantes = [r for r in todos if r.get("lote") != lote]
    try:
        DIARIO.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in restantes),
                          encoding="utf-8")
        shutil.rmtree(PASTA / lote, ignore_errors=True)
    except OSError:
        pass
    return {"ok": True, "lote": lote, "restaurados": restaurados,
            "removidos": removidos, "falhas": falhas}
