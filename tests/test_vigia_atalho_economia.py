"""Modo vigia, resposta rápida e economia de API."""
import json
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import economia_api as eco      # noqa: E402
from core import modo_vigia as vigia     # noqa: E402
from core import resposta_rapida as rr   # noqa: E402


class VigiaTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.raiz = Path(self.tmp.name)
        self.pasta = self.raiz / "entrada"
        self.pasta.mkdir()
        self._p = [mock.patch.object(vigia, "ESTADO", self.raiz / "vigia.json")]
        for p in self._p:
            p.start()

    def tearDown(self):
        for p in self._p:
            p.stop()
        self.tmp.cleanup()

    def test_organiza_foto_por_ano_e_mes(self):
        foto = self.pasta / "praia.jpg"
        foto.write_bytes(b"x")
        destino = vigia.organizar_foto(foto)
        self.assertEqual(destino.parent.name, time.strftime("%Y-%m"))

    def test_nota_fiscal_ganha_data_e_valor_no_nome(self):
        texto = "Fatura referencia marco/2026 total R$ 1.234,56 vencimento 10/04/2026"
        nota = self.pasta / "documento.pdf"
        nota.write_bytes(b"%PDF")
        with mock.patch.object(vigia, "_texto_do_pdf", return_value=texto):
            novo = vigia.renomear_nota(nota)
        self.assertIsNotNone(novo)
        self.assertIn("2026-03", novo.name)
        self.assertIn("1234-56", novo.name)

    def test_resumo_sem_modelo_usa_as_primeiras_frases(self):
        nota = self.pasta / "contrato.pdf"
        nota.write_bytes(b"%PDF")
        with mock.patch.object(vigia, "_texto_do_pdf",
                               return_value="Primeira frase. Segunda frase. Terceira. Quarta."):
            saida = vigia.resumir_pdf(nota)
        self.assertTrue(saida.exists())
        self.assertIn("Primeira frase", saida.read_text(encoding="utf-8"))

    def test_varredura_nao_reprocessa_o_mesmo_arquivo(self):
        (self.pasta / "a.jpg").write_bytes(b"x")
        vigia.vigiar(self.pasta)
        primeira = vigia.varrer()
        segunda = vigia.varrer()
        self.assertEqual(primeira["tratados"], 1)
        self.assertEqual(segunda["tratados"], 0)

    def test_pasta_inexistente_avisa(self):
        with self.assertRaises(NotADirectoryError):
            vigia.vigiar(self.raiz / "nao-existe")

    def test_parar_limpa_a_lista(self):
        vigia.vigiar(self.pasta)
        vigia.parar()
        self.assertEqual(vigia.pastas(), [])


class RespostaRapidaTest(unittest.TestCase):
    def test_cada_modo_tem_instrucao(self):
        for modo in rr.MODOS:
            self.assertTrue(rr.instrucao(modo))

    def test_modo_desconhecido_avisa(self):
        with self.assertRaises(ValueError):
            rr.instrucao("fritar")

    def test_transformar_usa_o_gerador(self):
        visto = {}

        def falso(pedido):
            visto["pedido"] = pedido
            return "resumo pronto"

        self.assertEqual(rr.transformar("texto longo", "resumir", falso), "resumo pronto")
        self.assertIn("Resuma", visto["pedido"])
        self.assertIn("texto longo", visto["pedido"])

    def test_texto_vazio_avisa(self):
        with self.assertRaises(ValueError):
            rr.transformar("   ", "resumir", lambda _p: "x")

    def test_gerador_vazio_avisa(self):
        with self.assertRaises(RuntimeError):
            rr.transformar("algo", "resumir", lambda _p: "")


class EconomiaTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self._p = [mock.patch.object(eco, "ARQUIVO", Path(self.tmp.name) / "eco.json")]
        for p in self._p:
            p.start()

    def tearDown(self):
        for p in self._p:
            p.stop()
        self.tmp.cleanup()

    def test_comando_curto_vai_para_o_rapido(self):
        self.assertEqual(eco.escolher("que horas são")["modelo"], "rapido")
        self.assertEqual(eco.escolher("abre o chrome")["modelo"], "rapido")

    def test_pedido_que_exige_analise_vai_para_o_forte(self):
        self.assertEqual(eco.escolher("analisa esse contrato e aponta riscos")["modelo"], "forte")
        self.assertEqual(eco.escolher("explica por que o deploy falhou")["modelo"], "forte")

    def test_texto_longo_forca_o_forte(self):
        self.assertEqual(eco.escolher("resume isso", tamanho=9000)["modelo"], "forte")

    def test_registrar_soma_economia(self):
        escolha = {"modelo": "rapido", "tokens": 1000, "motivo": "comando"}
        dados = eco.registrar(escolha)
        self.assertGreater(dados["economia"], 0)

    def test_resumo_do_mes_conta_as_chamadas(self):
        eco.registrar({"modelo": "rapido", "tokens": 100}, tokens_saida=50)
        eco.registrar({"modelo": "forte", "tokens": 900}, tokens_saida=100)
        r = eco.resumo_mes()
        self.assertEqual(r["chamadas"], 2)
        self.assertEqual(r["rapidas"], 1)
        self.assertEqual(r["percentual_rapido"], 50.0)

    def test_forte_nao_gera_economia(self):
        eco.registrar({"modelo": "forte", "tokens": 1000})
        self.assertEqual(eco.resumo_mes()["economia"], 0.0)


class FerramentasTest(unittest.TestCase):
    def test_vigia_sem_pasta_avisa(self):
        from actions import vigia as acao
        self.assertFalse(json.loads(acao.vigia({"action": "vigiar"}))["ok"])

    def test_resposta_rapida_modo_invalido(self):
        from actions import resposta_rapida as acao
        self.assertFalse(json.loads(acao.resposta_rapida({"modo": "fritar"}))["ok"])

    def test_resposta_rapida_com_texto_nao_mexe_no_teclado(self):
        from actions import resposta_rapida as acao
        with mock.patch.object(rr, "transformar", return_value="ok"), \
             mock.patch.object(rr, "capturar_selecao", side_effect=AssertionError("não deveria")):
            r = json.loads(acao.resposta_rapida({"modo": "resumir", "texto": "abc"}))
        self.assertTrue(r["ok"])


if __name__ == "__main__":
    unittest.main()
