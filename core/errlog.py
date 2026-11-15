"""Registro de erros em arquivo: nada mais falha em silêncio.

O problema que isto resolve: quando algo estoura dentro da interface, o aviso
aparece por três segundos e desaparece. Sem rastro, o relato vira "deu erro" e
o diagnóstico começa do zero.

Aqui todo erro não tratado — na thread principal ou em qualquer thread de
trabalho — vai para `erros.log` na pasta de estado, com data, thread e
traceback. O arquivo tem tamanho limitado: ao passar de 1 MB, o anterior vira
`erros.old.log`, então ele nunca cresce sem controle.
"""
from __future__ import annotations

import sys
import threading
import traceback
from datetime import datetime
from pathlib import Path

from core.paths import STATE_DIR

ARQUIVO = STATE_DIR / "erros.log"
LIMITE_BYTES = 1024 * 1024
_instalado = False
_trava = threading.Lock()


def _rotacionar() -> None:
    try:
        if ARQUIVO.exists() and ARQUIVO.stat().st_size > LIMITE_BYTES:
            antigo = ARQUIVO.with_name("erros.old.log")
            if antigo.exists():
                antigo.unlink(missing_ok=True)
            ARQUIVO.replace(antigo)
    except OSError:
        pass


def registrar(texto: str, onde: str = "") -> None:
    """Grava uma entrada. Nunca levanta exceção: log não pode derrubar o app."""
    with _trava:
        try:
            ARQUIVO.parent.mkdir(parents=True, exist_ok=True)
            _rotacionar()
            carimbo = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            thread = threading.current_thread().name
            cabeca = f"[{carimbo}] {onde or 'erro'} (thread {thread})"
            with ARQUIVO.open("a", encoding="utf-8") as f:
                f.write(f"{cabeca}\n{texto.rstrip()}\n\n")
        except OSError:
            pass


def registrar_excecao(exc: BaseException, onde: str = "") -> None:
    registrar("".join(traceback.format_exception(type(exc), exc, exc.__traceback__)), onde)


def _hook_principal(tipo, erro, tb) -> None:
    registrar("".join(traceback.format_exception(tipo, erro, tb)), "erro não tratado")
    sys.__excepthook__(tipo, erro, tb)


def _hook_thread(args) -> None:
    tipo, erro, tb = args.exc_type, args.exc_value, args.exc_traceback
    registrar("".join(traceback.format_exception(tipo, erro, tb)), "erro em thread")


def instalar() -> bool:
    """Liga os ganchos. Idempotente: chamar duas vezes não duplica nada."""
    global _instalado
    if _instalado:
        return True
    sys.excepthook = _hook_principal
    try:
        threading.excepthook = _hook_thread
    except AttributeError:
        pass
    _instalado = True
    return True


def ultimos(quantidade: int = 3) -> list[str]:
    """Blocos mais recentes, para o diagnóstico mostrar sem abrir o arquivo."""
    try:
        conteudo = ARQUIVO.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    blocos = [b for b in conteudo.split("\n\n") if b.strip()]
    return blocos[-quantidade:]


def limpar() -> None:
    try:
        ARQUIVO.unlink(missing_ok=True)
    except OSError:
        pass
