"""Armazenamento local simples para notas e tarefas (v6.6.0).

POR QUE EXISTE
    Notas e tarefas são dados do usuário, não do aplicativo: precisam sobreviver
    a uma atualização e não podem corromper se o TORVIS for fechado no meio da
    escrita. Um JSON gravado direto no lugar certo falha nas duas coisas — um
    desligamento no meio do `write` deixa o arquivo pela metade e o app perde
    tudo na próxima leitura.

    Aqui a gravação é atômica (escreve `.tmp`, faz `replace`), há uma trava por
    arquivo porque ações rodam em threads diferentes, e um arquivo ilegível é
    guardado como `.corrompido` em vez de ser sobrescrito em silêncio.
"""
from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Any, Callable

from core.paths import STATE_DIR

USERDATA_DIR = STATE_DIR / "userdata"

_TRAVAS: dict[str, threading.RLock] = {}
_TRAVAS_GUARDA = threading.Lock()


def _trava(caminho: Path) -> threading.RLock:
    chave = str(caminho)
    with _TRAVAS_GUARDA:
        if chave not in _TRAVAS:
            # RLock, não Lock: `alterar()` já segura a trava e chama
            # `escrever()`, que trava de novo. Com Lock comum isso é um abraço
            # mortal — os testes travaram por cinco minutos antes de eu ver.
            _TRAVAS[chave] = threading.RLock()
        return _TRAVAS[chave]


class JsonStore:
    """Um arquivo JSON com lista de itens, lido e escrito com segurança."""

    def __init__(self, nome: str, inicio: dict | None = None):
        self.caminho = USERDATA_DIR / nome
        self._inicio = dict(inicio or {"itens": [], "proximo_id": 1})
        self._cache: dict | None = None
        self._assinatura: tuple[float, int] | None = None

    # -- leitura ---------------------------------------------------------
    def ler(self) -> dict:
        """Conteúdo atual. Devolve uma cópia: quem chamar não altera o cache."""
        try:
            st = self.caminho.stat()
            assinatura = (st.st_mtime, st.st_size)
        except OSError:
            return json.loads(json.dumps(self._inicio))

        if self._cache is not None and assinatura == self._assinatura:
            return json.loads(json.dumps(self._cache))

        try:
            dados = json.loads(self.caminho.read_text(encoding="utf-8"))
            if not isinstance(dados, dict) or not isinstance(dados.get("itens"), list):
                raise ValueError("formato inesperado")
        except (OSError, ValueError):
            self._guardar_corrompido()
            dados = json.loads(json.dumps(self._inicio))

        dados.setdefault("proximo_id", 1 + max((int(i.get("id", 0)) for i in dados["itens"]), default=0))
        self._cache, self._assinatura = dados, assinatura
        return json.loads(json.dumps(dados))

    def _guardar_corrompido(self) -> None:
        """Não apaga o que não conseguiu ler: renomeia para inspeção."""
        try:
            alvo = self.caminho.with_suffix(f".corrompido-{int(time.time())}.json")
            self.caminho.replace(alvo)
        except OSError:
            pass

    # -- escrita ---------------------------------------------------------
    def escrever(self, dados: dict) -> None:
        USERDATA_DIR.mkdir(parents=True, exist_ok=True)
        temporario = self.caminho.with_suffix(self.caminho.suffix + ".tmp")
        texto = json.dumps(dados, indent=2, ensure_ascii=False)
        with _trava(self.caminho):
            temporario.write_text(texto, encoding="utf-8")
            os.replace(temporario, self.caminho)
        try:
            st = self.caminho.stat()
            self._assinatura = (st.st_mtime, st.st_size)
        except OSError:
            self._assinatura = None
        self._cache = dados

    def alterar(self, funcao: Callable[[dict], Any]) -> Any:
        """Lê, deixa a função mexer nos dados e grava — tudo sob a mesma trava.

        É o que evita a nota que some quando duas falas chegam juntas: sem isso
        as duas leem a mesma lista e a segunda gravação apaga a primeira.
        """
        with _trava(self.caminho):
            dados = self.ler()
            resultado = funcao(dados)
            self.escrever(dados)
            return resultado

    def proximo_id(self, dados: dict) -> int:
        novo = int(dados.get("proximo_id", 1))
        dados["proximo_id"] = novo + 1
        return novo
