"""Testes do servidor de webhook: verificação da Meta e processamento dos eventos."""
from __future__ import annotations

import json
import unittest

from core import whatsapp as wa
from tools import servidor_whatsapp as srv


def cfg(**mudancas):
    base = wa.config_inicial()
    base.update({"token": "t", "numero_id": "1", "ligada": True,
                 "silencioso_inicio": 0, "silencioso_fim": 0, "permitidos": []})
    base.update(mudancas)
    return base


class ProcessamentoTests(unittest.TestCase):
    def test_fluxo_completo_de_mensagem_e_chamada(self):
        secretaria = wa.SecretariaWhatsApp(cfg(responder_audio=False), ensaio=True)
        corpo = {"entry": [{"changes": [{"value": {
            "contacts": [{"wa_id": "5585999991234", "profile": {"name": "André"}}],
            "messages": [{"from": "5585999991234", "type": "text", "text": {"body": "oi"}}],
            "calls": [{"from": "5511999998888", "event": "missed"}],
        }}]}]}
        original = srv.gerador_padrao
        srv.gerador_padrao = lambda texto: f"resposta para {texto}"
        try:
            resultados = srv.processar(corpo, secretaria, com_audio=False)
        finally:
            srv.gerador_padrao = original
        self.assertEqual(len(resultados), 2)
        self.assertTrue(resultados[0]["ok"])
        self.assertTrue(resultados[1]["ok"])
        tipos = [e["tipo"] for e in secretaria.enviados]
        self.assertEqual(tipos, ["texto", "texto"])

    def test_chamada_atendida_nao_gera_mensagem(self):
        secretaria = wa.SecretariaWhatsApp(cfg(), ensaio=True)
        corpo = {"entry": [{"changes": [{"value": {"calls": [{"from": "5585999991234", "event": "accepted"}]}}]}]}
        self.assertEqual(srv.processar(corpo, secretaria, com_audio=False), [])
        self.assertEqual(secretaria.enviados, [])

    def test_corpo_estranho_nao_derruba(self):
        secretaria = wa.SecretariaWhatsApp(cfg(), ensaio=True)
        self.assertEqual(srv.processar({"entry": "nada"}, secretaria, com_audio=False), [])
        self.assertEqual(srv.processar({}, secretaria), [])


class ServidorTests(unittest.TestCase):
    """Sobe o servidor de verdade numa porta livre e conversa por HTTP."""

    def setUp(self):
        import threading
        from http.server import ThreadingHTTPServer
        self.secretaria = wa.SecretariaWhatsApp(cfg(responder_audio=False), ensaio=True)
        srv.Handler.secretaria = self.secretaria
        srv.Handler.verificar = "torvis-teste"
        srv.Handler.com_audio = False
        self.servidor = ThreadingHTTPServer(("127.0.0.1", 0), srv.Handler)
        self.porta = self.servidor.server_address[1]
        threading.Thread(target=self.servidor.serve_forever, daemon=True).start()

    def tearDown(self):
        self.servidor.shutdown()
        self.servidor.server_close()

    def _get(self, caminho):
        import urllib.request
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{self.porta}{caminho}", timeout=5) as r:
                return r.status, r.read().decode()
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read().decode()

    def test_desafio_da_meta_e_devolvido(self):
        codigo, corpo = self._get("/webhook?hub.mode=subscribe&hub.verify_token=torvis-teste&hub.challenge=42")
        self.assertEqual((codigo, corpo), (200, "42"))

    def test_token_errado_e_recusado(self):
        codigo, _ = self._get("/webhook?hub.mode=subscribe&hub.verify_token=outro&hub.challenge=42")
        self.assertEqual(codigo, 403)

    def test_mensagem_por_http_responde_200(self):
        import urllib.request
        original = srv.gerador_padrao
        srv.gerador_padrao = lambda texto: "recebido"
        corpo = json.dumps({"entry": [{"changes": [{"value": {
            "messages": [{"from": "5585999991234", "type": "text", "text": {"body": "oi"}}]}}]}]}).encode()
        pedido = urllib.request.Request(f"http://127.0.0.1:{self.porta}/webhook", data=corpo,
                                        headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(pedido, timeout=5) as r:
                self.assertEqual(r.status, 200)
                self.assertIn("recebido", r.read().decode())
        finally:
            srv.gerador_padrao = original
        self.assertEqual(self.secretaria.enviados[-1]["tipo"], "texto")


if __name__ == "__main__":
    unittest.main()
