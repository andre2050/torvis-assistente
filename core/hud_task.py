"""Trabalho pesado fora da thread gráfica, com retorno seguro para a janela.

A interface do TORVIS é PyQt6: qualquer leitura de arquivo grande, consulta à
rede ou geração de relatório feita na thread da janela congela o desenho. Este
módulo dá um caminho único para mandar isso para trás e voltar com o resultado
na thread certa, sem que cada tela invente o seu jeito.

Uso:
    tarefa = rodar(pesado, ao_terminar=mostrar_resultado, ao_falhar=mostrar_erro)
    tarefa.cancelar()

`rodar` devolve na hora. O resultado chega em `ao_terminar` já na thread da
interface quando o Qt está presente; sem Qt, chega na thread de trabalho e o
teste continua simples.
"""
from __future__ import annotations

import threading
import traceback
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any, Callable, Optional

_MAX_TRABALHADORES = 4
_pool = ThreadPoolExecutor(max_workers=_MAX_TRABALHADORES,
                           thread_name_prefix="torvis-hud")
_registro: dict[str, Future] = {}
_trava = threading.RLock()


def _na_thread_da_janela(funcao: Callable[[], None]) -> None:
    """Executa na thread gráfica se houver Qt; senão, aqui mesmo."""
    try:
        from PyQt6.QtCore import QTimer
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance()
        if app is not None:
            QTimer.singleShot(0, funcao)
            return
    except Exception:
        pass
    funcao()


class TarefaHud:
    """Alça de uma tarefa em segundo plano: cancelar, acompanhar, saber o erro."""

    def __init__(self, nome: str, futuro: Future) -> None:
        self.nome = nome
        self._futuro = futuro

    def cancelar(self) -> bool:
        return self._futuro.cancel()

    def pronta(self) -> bool:
        return self._futuro.done()

    def resultado(self) -> Any:
        return self._futuro.result(timeout=0)


def rodar(funcao: Callable[..., Any], *args,
          nome: str = "tarefa",
          ao_terminar: Optional[Callable[[Any], None]] = None,
          ao_falhar: Optional[Callable[[Exception], None]] = None,
          **kwargs) -> TarefaHud:
    """Agenda `funcao(*args, **kwargs)` fora da thread gráfica."""

    def trabalho() -> Any:
        try:
            saida = funcao(*args, **kwargs)
        except Exception as exc:
            if ao_falhar:
                _na_thread_da_janela(lambda: ao_falhar(exc))
            else:
                traceback.print_exc()
            raise
        if ao_terminar:
            _na_thread_da_janela(lambda: ao_terminar(saida))
        return saida

    futuro = _pool.submit(trabalho)
    with _trava:
        _registro[nome] = futuro
    return TarefaHud(nome, futuro)


def aguardar(nome: str, segundos: float = 5.0) -> Optional[Any]:
    """Espera uma tarefa pelo nome; devolve None se ainda não terminou."""
    with _trava:
        futuro = _registro.get(nome)
    if futuro is None:
        return None
    try:
        return futuro.result(timeout=segundos)
    except Exception:
        return None


def encerrar() -> None:
    """Fecha o pool no encerramento do app, sem segurar a saída."""
    _pool.shutdown(wait=False, cancel_futures=True)
