"""Disjuntor por provedor de IA: falha repetida não vira espera repetida.

A escada de modelos já descansava um modelo que estourou cota. Faltava o passo
seguinte: quando o provedor inteiro está fora (chave recusada, serviço caído,
timeout em série), a próxima chamada não deve pagar o mesmo erro antes de cair
no alternativo. O disjuntor abre, manda o tráfego para o próximo da lista e só
volta a testar depois do tempo de espera, com uma única tentativa de sondagem.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Iterable, Optional

FALHAS_PARA_ABRIR = 3
ESPERA_PADRAO = 120.0
ESPERA_MAXIMA = 900.0


@dataclass
class Estado:
    falhas: int = 0
    aberto_ate: float = 0.0
    ultimo_motivo: str = ""
    sucessos: int = 0
    aberturas: int = 0
    historico: list[str] = field(default_factory=list)


class Disjuntor:
    """Um disjuntor por nome de provedor ou modelo."""

    def __init__(self, nome: str, *, limiar: int = FALHAS_PARA_ABRIR,
                 espera: float = ESPERA_PADRAO) -> None:
        self.nome = nome
        self.limiar = max(1, int(limiar))
        self.espera = float(espera)
        self._estado = Estado()
        self._trava = threading.RLock()

    def permitir(self, agora: Optional[float] = None) -> bool:
        """Pode tentar? Fechado ou em sondagem: sim. Aberto: não."""
        agora = time.time() if agora is None else agora
        with self._trava:
            return agora >= self._estado.aberto_ate

    def falhou(self, motivo: str = "", agora: Optional[float] = None) -> bool:
        """Registra falha e diz se o disjuntor acabou de abrir."""
        agora = time.time() if agora is None else agora
        with self._trava:
            e = self._estado
            e.falhas += 1
            e.ultimo_motivo = (motivo or "")[:200]
            e.historico.append(e.ultimo_motivo)
            del e.historico[:-10]
            if e.falhas >= self.limiar and e.aberto_ate <= agora:
                espera = min(ESPERA_MAXIMA, self.espera * (2 ** (e.aberturas)))
                e.aberto_ate = agora + espera
                e.aberturas += 1
                return True
            return False

    def funcionou(self) -> None:
        with self._trava:
            self._estado.falhas = 0
            self._estado.aberto_ate = 0.0
            self._estado.sucessos += 1

    def estado(self) -> dict:
        with self._trava:
            e = self._estado
            aberto = e.aberto_ate > time.time()
            return {"nome": self.nome, "aberto": aberto, "falhas": e.falhas,
                    "aberto_ate": e.aberto_ate, "motivo": e.ultimo_motivo,
                    "sucessos": e.sucessos, "aberturas": e.aberturas}


_REGISTRO: dict[str, Disjuntor] = {}
_TRAVA_REGISTRO = threading.RLock()


def disjuntor(nome: str) -> Disjuntor:
    with _TRAVA_REGISTRO:
        if nome not in _REGISTRO:
            _REGISTRO[nome] = Disjuntor(nome)
        return _REGISTRO[nome]


def permitidos(nomes: Iterable[str]) -> list[str]:
    """Só os nomes cujo disjuntor está fechado; se todos abriram, devolve todos.

    Devolver todos no pior caso é de propósito: melhor tentar com o provedor
    duvidoso do que responder ao usuário que não há nenhum.
    """
    lista = list(nomes)
    livres = [n for n in lista if disjuntor(n).permitir()]
    return livres or lista


def registrar_falha(nome: str, motivo: str = "") -> bool:
    return disjuntor(nome).falhou(motivo)


def registrar_sucesso(nome: str) -> None:
    disjuntor(nome).funcionou()


def abertos() -> dict[str, dict]:
    with _TRAVA_REGISTRO:
        nomes = list(_REGISTRO)
    return {n: disjuntor(n).estado() for n in nomes if disjuntor(n).estado()["aberto"]}


def tentar_em_ordem(candidatos: Iterable[tuple[str, Callable[[], object]]], *,
                    ao_escolher: Optional[Callable[[str], None]] = None) -> tuple[str, object]:
    """Executa o primeiro candidato com disjuntor fechado; abre os que falharem.

    Cada item é (nome, chamada_sem_argumentos). O primeiro que responder vence.
    Levanta o último erro quando todos falham, com o nome do último na mensagem.
    """
    erros: list[str] = []
    for nome, chamada in candidatos:
        if not disjuntor(nome).permitir():
            erros.append(f"{nome}: disjuntor aberto")
            continue
        if ao_escolher:
            ao_escolher(nome)
        try:
            resultado = chamada()
        except Exception as exc:  # noqa: BLE001 - cada provedor falha do seu jeito
            registrar_falha(nome, str(exc))
            erros.append(f"{nome}: {exc}")
            continue
        registrar_sucesso(nome)
        return nome, resultado
    raise RuntimeError("todos os provedores falharam — " + " | ".join(erros))
