"""Continuação de core/netguard.py: o relatório de rede mostrado ao usuário."""

from __future__ import annotations

import socket
import time

from urllib.request import Request, getproxies, urlopen

from core.netguard import HOST, estado, ipv6_conecta, preferir_ipv4


def _ms(inicio: float) -> int:
    return int((time.time() - inicio) * 1000)


def _dns() -> tuple[str, str]:
    inicio = time.time()
    try:
        infos = socket.getaddrinfo(HOST, 443, proto=socket.IPPROTO_TCP)
        ips = sorted({i[4][0] for i in infos})
        return "ok", f"{', '.join(ips[:3])} ({_ms(inicio)} ms)"
    except OSError as exc:
        return "erro", f"{type(exc).__name__}: {exc}"


def _tcp() -> tuple[str, str]:
    inicio = time.time()
    try:
        with socket.create_connection((HOST, 443), timeout=12):
            return "ok", f"conectou em {_ms(inicio)} ms"
    except socket.timeout:
        return "erro", "porta 443 sem resposta (firewall/antivirus/VPN)"
    except OSError as exc:
        return "erro", f"{type(exc).__name__}: {exc}"


def _tls() -> tuple[str, str]:
    import ssl

    inicio = time.time()
    try:
        contexto = ssl.create_default_context()
        with socket.create_connection((HOST, 443), timeout=12) as bruto:
            with contexto.wrap_socket(bruto, server_hostname=HOST) as tls:
                versao = tls.version()
        return "ok", f"TLS {versao} em {_ms(inicio)} ms"
    except ssl.SSLError as exc:
        return "erro", f"TLS recusado ({exc.reason or exc}) - antivirus/proxy no meio"
    except OSError as exc:
        return "erro", f"{type(exc).__name__}: {exc}"


def _http() -> tuple[str, str]:
    """Sem chave, um 400/403 ja prova que o servidor respondeu."""
    inicio = time.time()
    try:
        with urlopen(Request(f"https://{HOST}/v1beta/models", headers={"User-Agent": "TORVIS-diagnostico"}),
                     timeout=30) as resposta:
            return "ok", f"HTTP {resposta.status} em {_ms(inicio)} ms"
    except Exception as exc:  # HTTPError também serve de prova
        codigo = getattr(exc, "code", None)
        if codigo:
            return "ok", f"HTTP {codigo} em {_ms(inicio)} ms (servidor respondeu)"
        if isinstance(exc, (socket.timeout, TimeoutError)):
            return "erro", "sem resposta em 30 s"
        return "erro", f"{type(exc).__name__}: {exc}"


def diagnosticar() -> list[tuple[str, str]]:
    preferir_ipv4()          # liga a proteção se o IPv6 desta máquina estiver quebrado
    proxy = getproxies()
    achados: list[tuple[str, str]] = [
        ("info", "Proxy do sistema: " + (", ".join(f"{k}={v}" for k, v in proxy.items()) or "nenhum")),
        ("info", "Preferencia por IPv4: " + ("ativa" if estado().get("ipv4_forcado") else "nao necessaria")),
    ]
    for nome, funcao in (("DNS", _dns), ("Porta 443", _tcp), ("Certificado", _tls), ("Resposta HTTP", _http)):
        situacao, detalhe = funcao()
        achados.append((situacao, f"{nome}: {detalhe}"))
    ipv6 = ipv6_conecta()
    if ipv6 is None:
        achados.append(("info", "IPv6: este host nao oferece IPv6 (usa IPv4)"))
    elif ipv6:
        achados.append(("ok", "IPv6: conecta normalmente"))
    else:
        achados.append(("erro", "IPv6: existe mas nao conecta (causa classica de tempo esgotado)"))
    return achados


def veredito(achados: list[tuple[str, str]]) -> str:
    erros = [d for e, d in achados if e == "erro"]
    if not erros:
        return "Rede OK: o servidor do Google responde normalmente daqui."
    texto = " ".join(erros)
    if "DNS" in texto:
        return ("O nome do servidor nao resolve. Troque o DNS para 8.8.8.8 / 1.1.1.1 "
                "ou desative o filtro de DNS do antivirus.")
    if "443" in texto:
        return ("A porta 443 esta bloqueada. Libere generativelanguage.googleapis.com no "
                "firewall/antivirus ou desligue a VPN e tente de novo.")
    if "TLS" in texto or "Certificado" in texto:
        return ("O certificado esta sendo interceptado: desative a inspecao HTTPS do antivirus "
                "ou instale o certificado dele no Windows.")
    if "IPv6" in texto:
        return ("O IPv6 desta maquina nao conecta. O TORVIS ja passa a usar IPv4 primeiro; "
                "se ainda falhar, desative o IPv6 no adaptador de rede.")
    return "O servidor nao respondeu a tempo. Teste em outra rede (4G do celular) para confirmar."


def texto() -> str:
    achados = diagnosticar()
    marcas = {"ok": "✔", "erro": "✖", "info": "·"}
    linhas = [f"{marcas.get(e, '·')} {d}" for e, d in achados]
    return "\n".join(linhas) + "\n\n" + veredito(achados)


if __name__ == "__main__":
    print(texto())
