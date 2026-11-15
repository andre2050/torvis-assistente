"""Rede e firewall: IPv4 preferido quando o IPv6 esta quebrado, sem NameError."""
import io
import socket
import unittest
from contextlib import redirect_stdout
from unittest import mock

from core import netguard


class _FakeSocket:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class NetguardTests(unittest.TestCase):
    def tearDown(self):
        netguard.restaurar()

    def test_sem_ipv6_no_host(self):
        with mock.patch.object(socket, "getaddrinfo", side_effect=OSError("sem AAAA")):
            self.assertIsNone(netguard.ipv6_conecta("exemplo.test", 0.1))

    def test_ipv6_quebrado_forca_ipv4_primeiro(self):
        def resolver(host, porta, family=0, *a, **k):
            if family == socket.AF_INET6:
                return [(socket.AF_INET6, socket.SOCK_STREAM, 6, "", ("2001:db8::1", 443, 0, 0))]
            return [(socket.AF_INET6, socket.SOCK_STREAM, 6, "", ("2001:db8::1", 443, 0, 0)),
                    (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("142.250.1.1", 443))]

        with mock.patch.object(socket, "getaddrinfo", side_effect=resolver), \
                mock.patch.object(socket, "create_connection", side_effect=OSError("recusado")):
            self.assertTrue(netguard.preferir_ipv4("exemplo.test", 0.1),
                            "com IPv6 quebrado, a protecao deve ser ligada")
            self.assertTrue(netguard.estado()["ipv4_forcado"])

    def test_ordenacao_coloca_ipv4_na_frente(self):
        def falso(*a, **k):
            return [(socket.AF_INET6, socket.SOCK_STREAM, 6, "", ("2001:db8::1", 443, 0, 0)),
                    (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("142.250.1.1", 443))]

        original = netguard._ORIGINAL
        netguard._ORIGINAL = falso
        try:
            achados = netguard._resolver_com_ipv4_primeiro("exemplo.test", 443)
        finally:
            netguard._ORIGINAL = original
        self.assertEqual(achados[0][0], socket.AF_INET, "IPv4 deveria vir primeiro")
        self.assertEqual(len(achados), 2, "nada pode ser descartado")

    def test_ipv6_bom_nao_mexe_em_nada(self):
        antes = socket.getaddrinfo
        with mock.patch.object(socket, "create_connection", return_value=_FakeSocket()), \
                mock.patch.object(socket, "getaddrinfo",
                                  return_value=[(socket.AF_INET6, socket.SOCK_STREAM, 6, "", ("2001:db8::1", 443, 0, 0))]):
            self.assertFalse(netguard.preferir_ipv4("exemplo.test", 0.1))
        self.assertIs(socket.getaddrinfo, getattr(netguard, "_ORIGINAL", antes))

    def test_em_segundo_plano_nao_bloqueia(self):
        with mock.patch.object(netguard, "preferir_ipv4", side_effect=RuntimeError("falhou")):
            t = netguard.preferir_ipv4_em_segundo_plano("exemplo.test")
            t.join(timeout=3)
        self.assertFalse(t.is_alive())


class FirewallTests(unittest.TestCase):
    """O caminho Linux usava a variavel 'port', que nao existia."""

    def test_fix_network_access_nao_estoura_nameerror(self):
        from dashboard import server

        rodado: list[list[str]] = []

        class Resultado:
            def __init__(self, texto=""):
                self.stdout = texto
                self.returncode = 0
                self.stderr = ""

        def falso_run(cmd, *a, **k):
            rodado.append(list(cmd) if isinstance(cmd, list) else [str(cmd)])
            if "ufw" in cmd:
                return Resultado("Status: active")
            return Resultado("")

        with mock.patch("subprocess.run", side_effect=falso_run):
            saida = io.StringIO()
            with redirect_stdout(saida):
                server.fix_network_access(8000)

        texto = saida.getvalue()
        self.assertIn("8000", texto)
        self.assertTrue(any("ufw" in " ".join(c) for c in rodado))


if __name__ == "__main__":
    unittest.main()
