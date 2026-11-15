"""Escada de modelos aprendida: ordem, validade da medição e isolamento por chave."""
import json
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from core import model_ladder


class EscadaTests(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self._arq = Path(self._tmp.name) / "model_ladder.json"
        self._patch = mock.patch.object(model_ladder, "_ARQUIVO", self._arq)
        self._patch.start()
        self.chave = "chave-de-teste-123456"

    def tearDown(self):
        self._patch.stop()
        self._tmp.cleanup()

    def _gravar_bruto(self, dados):
        self._arq.write_text(json.dumps(dados), encoding="utf-8")

    def test_media_de_varias_amostras(self):
        model_ladder.registrar_sucesso(self.chave, "m1", 100)
        model_ladder.registrar_sucesso(self.chave, "m1", 300)
        self.assertEqual(model_ladder.media_ms(self.chave, "m1"), 200)

    def test_rapido_vai_na_frente_e_falho_vai_para_o_fim(self):
        model_ladder.registrar_sucesso(self.chave, "lento", 900)
        model_ladder.registrar_sucesso(self.chave, "rapido", 120)
        model_ladder.registrar_falha(self.chave, "ruim")

        ordem = model_ladder.ordenar(["lento", "desconhecido", "rapido", "ruim"], self.chave)
        self.assertEqual(ordem, ["rapido", "lento", "desconhecido", "ruim"])

    def test_sem_medicao_a_escada_original_e_preservada(self):
        original = ["a", "b", "c", "d"]
        self.assertEqual(model_ladder.ordenar(original, self.chave), original)

    def test_medicao_antiga_expira(self):
        antigo = {"m1": {"ms": [100], "falhas": 0, "at": time.time() - 8 * 24 * 3600}}
        self._gravar_bruto({model_ladder._impressao(self.chave): antigo})

        ordem = model_ladder.ordenar(["m2", "m1"], self.chave)
        self.assertEqual(ordem, ["m2", "m1"], "medição vencida não pode influenciar a ordem")
        self.assertIsNone(model_ladder.media_ms(self.chave, "m1"))

    def test_chaves_diferentes_nao_se_misturam(self):
        model_ladder.registrar_sucesso("chave-A", "m1", 50)
        self.assertIsNone(model_ladder.media_ms("chave-B", "m1"))

    def test_provedor_e_live_ficam_fora_da_medicao(self):
        model_ladder.registrar_sucesso(self.chave, "prov:openai", 100)
        model_ladder.registrar_sucesso(self.chave, "live", 100)
        self.assertEqual(model_ladder._modelos(self.chave), {})

    def test_arquivo_corrompido_nao_quebra(self):
        self._arq.write_text("{ isso nao e json", encoding="utf-8")
        self.assertEqual(model_ladder.ordenar(["a", "b"], self.chave), ["a", "b"])
        model_ladder.registrar_sucesso(self.chave, "a", 10)   # reescreve sem estourar

    def test_esquecer_limpa_a_chave(self):
        model_ladder.registrar_sucesso(self.chave, "m1", 10)
        model_ladder.esquecer(self.chave)
        self.assertIsNone(model_ladder.media_ms(self.chave, "m1"))

    def test_resumo_descreve_o_que_foi_medido(self):
        model_ladder.registrar_sucesso(self.chave, "rapido", 80)
        model_ladder.registrar_falha(self.chave, "ruim")
        tipos = {t for t, _ in model_ladder.resumo(self.chave)}
        self.assertIn("ok", tipos)
        self.assertIn("aviso", tipos)


class IntegracaoComGeminiTests(unittest.TestCase):
    """A escada do gemini.py precisa usar a ordem aprendida."""

    def test_usable_rungs_usa_a_ordem_aprendida(self):
        from core import gemini

        with mock.patch.object(gemini.model_ladder, "ordenar",
                               side_effect=lambda rungs, key: list(reversed(list(rungs)))) as ordenar, \
                mock.patch.object(gemini, "_cooling", return_value=False), \
                mock.patch.object(gemini, "api_key", return_value="chave-x"):
            resultado = gemini.usable_rungs(["a", "b", "c"])

        self.assertEqual(resultado, ["c", "b", "a"])
        ordenar.assert_called_once()

    def test_falha_de_ordenacao_nao_derruba_a_conversa(self):
        from core import gemini

        with mock.patch.object(gemini.model_ladder, "ordenar", side_effect=RuntimeError("boom")), \
                mock.patch.object(gemini, "_cooling", return_value=False), \
                mock.patch.object(gemini, "api_key", return_value="chave-x"):
            self.assertEqual(gemini.usable_rungs(["a", "b"]), ["a", "b"])


if __name__ == "__main__":
    unittest.main()
