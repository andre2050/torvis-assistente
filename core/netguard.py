"""Rede do TORVIS: evita o "tempo esgotado" e explica a falha em palavras claras.

Por que este modulo existe: quando o IPv6 da maquina esta quebrado (comum no
Windows com certos roteadores e em redes com VPN), o Python tenta o endereco
IPv6 primeiro e fica esperando ate estourar o tempo - mesmo com a internet
funcionando por IPv4. O sintoma e "tempo esgotado ao falar com o servidor" com
tudo mais normal.

Aqui a maquina e testada uma vez, em segundo plano; se o IPv6 nao conectar, a
resolucao passa a devolver IPv4 primeiro para TODO o processo (SDK do Gemini,
urllib, websockets), sem mexer em cada chamada.
"""
from __future__ import annotations

import socket
import threading
import time

HOST = "generativelanguage.googleapis.com"

_ESTADO: dict = {"testado": False, "ipv6": None, "ipv4_forcado": False}
_TRAVA = threading.Lock()
_ORIGINAL = socket.getaddrinfo


def ipv6_conecta(host: str = HOST, segundos: float = 3.0) -> bool | None:
    """True/False se o IPv6 conecta; None quando o host nem tem IPv6."""
    try:
        infos = socket.getaddrinfo(host, 443, socket.AF_INET6, socket.SOCK_STREAM)
    except OSError:
        return None
    if not infos:
        return None
    try:
        with socket.create_connection((infos[0][4][0], 443), timeout=segundos):
            return True
    except OSError:
        return False


def _resolver_com_ipv4_primeiro(*args, **kwargs):
    """IPv4 na frente, mantendo o IPv6 como alternativa (nada e descartado)."""
    achados = _ORIGINAL(*args, **kwargs)
    try:
        return sorted(achados, key=lambda item: 0 if item[0] == socket.AF_INET else 1)
    except Exception:
        return achados


def preferir_ipv4(host: str = HOST, segundos: float = 3.0) -> bool:
    """Instala a preferencia por IPv4 apenas se o IPv6 estiver quebrado."""
    with _TRAVA:
        if _ESTADO["ipv4_forcado"]:
            return True
        estado = ipv6_conecta(host, segundos)
        _ESTADO.update(testado=True, ipv6=estado)
        if estado is False:
            socket.getaddrinfo = _resolver_com_ipv4_primeiro
            _ESTADO["ipv4_forcado"] = True
        return bool(_ESTADO["ipv4_forcado"])


def preferir_ipv4_em_segundo_plano(host: str = HOST) -> threading.Thread:
    """O mesmo teste, sem atrasar a abertura do app."""
    def rodar() -> None:
        try:
            preferir_ipv4(host)
        except Exception:
            pass

    t = threading.Thread(target=rodar, name="netguard-ipv4", daemon=True)
    t.start()
    return t


def estado() -> dict:
    return dict(_ESTADO)


def restaurar() -> None:
    """Desfaz a preferencia (usado nos testes)."""
    with _TRAVA:
        if _ESTADO["ipv4_forcado"]:
            socket.getaddrinfo = _ORIGINAL
        _ESTADO.update(testado=False, ipv6=None, ipv4_forcado=False)
