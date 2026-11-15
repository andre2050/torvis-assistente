"""Relatório, métricas e orçamento diário: três coisas que precisam ser confiáveis."""
import json
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from core import budget, metrics, report


class BudgetTests(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self._patch = mock.patch.object(budget, "ARQUIVO", Path(self._tmp.name) / "uso.json")
        self._patch.start()
        self._env = mock.patch.dict(os.environ, {}, clear=False)
        self._env.start()
        os.environ.pop("TORVIS_LIMITE_DIARIO_IA", None)

    def tearDown(self):
        self._env.stop()
        self._patch.stop()
        self._tmp.cleanup()

    def test_conta_por_modelo_e_total(self):
        budget.contar("m1")
        budget.contar("m1")
        budget.contar("m2")
        self.assertEqual(budget.total_hoje(), 3)
        self.assertIn("m1: 2", budget.resumo())

    def test_sem_teto_nunca_bloqueia(self):
        for _ in range(50):
            budget.contar("m1")
        self.assertTrue(budget.permitido())
        self.assertIsNone(budget.restante())
        self.assertEqual(budget.aviso(), "")

    def test_teto_bloqueia_ao_atingir(self):
        os.environ["TORVIS_LIMITE_DIARIO_IA"] = "2"
        budget.contar("m1")
        self.assertTrue(budget.permitido())
        budget.contar("m1")
        self.assertFalse(budget.permitido())
        self.assertEqual(budget.restante(), 0)
        self.assertIn("atingido", budget.aviso())

    def test_aviso_em_oitenta_por_cento(self):
        os.environ["TORVIS_LIMITE_DIARIO_IA"] = "10"
        for _ in range(9):
            budget.contar("m1")
        self.assertIn("9 de 10", budget.aviso())

    def test_zerar_reinicia_o_dia(self):
        budget.contar("m1")
        budget.zerar()
        self.assertEqual(budget.total_hoje(), 0)

    def test_arquivo_corrompido_nao_quebra(self):
        budget.ARQUIVO.write_text("nao e json", encoding="utf-8")
        self.assertEqual(budget.total_hoje(), 0)
        budget.contar("m1")
        self.assertEqual(budget.total_hoje(), 1)


class MetricsTests(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self._patch = mock.patch.object(metrics, "ARQUIVO", Path(self._tmp.name) / "metricas.jsonl")
        self._patch.start()
        metrics._MARCAS.clear()

    def tearDown(self):
        self._patch.stop()
        self._tmp.cleanup()
        metrics._MARCAS.clear()

    def test_marcar_e_intervalo(self):
        metrics.marcar("a")
        metrics.marcar("b")
        self.assertIsNotNone(metrics.desde("a"))
        self.assertGreaterEqual(metrics.intervalo("a", "b"), 0)
        self.assertIsNone(metrics.intervalo("a", "inexistente"))

    def test_salvar_grava_uma_linha_por_execucao(self):
        metrics.marcar("imports")
        metrics.salvar()
        metrics.salvar()
        linhas = metrics.ARQUIVO.read_text(encoding="utf-8").strip().splitlines()
        self.assertEqual(len(linhas), 2)
        registro = json.loads(linhas[-1])
        self.assertIn("imports", registro)
        self.assertIn("versao", registro)

    def test_poda_mantem_arquivo_pequeno(self):
        metrics.marcar("imports")
        for _ in range(metrics._LIMITE_LINHAS + 20):
            metrics.salvar()
        linhas = metrics.ARQUIVO.read_text(encoding="utf-8").strip().splitlines()
        self.assertLessEqual(len(linhas), metrics._LIMITE_LINHAS)

    def test_resumo_sem_marcas(self):
        self.assertIn("nenhuma métrica", metrics.resumo())


class ReportTests(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.destino = Path(self._tmp.name) / "relatorio.txt"

    def tearDown(self):
        self._tmp.cleanup()

    def test_gera_secoes_essenciais(self):
        caminho = report.gerar(self.destino)
        texto = caminho.read_text(encoding="utf-8")
        for secao in ("SISTEMA", "DEPENDÊNCIAS", "REDE", "MODELOS", "ÚLTIMOS ERROS", "MÉTRICAS"):
            self.assertIn(secao, texto)

    def test_nunca_vaza_a_chave(self):
        with mock.patch.dict(os.environ, {"GEMINI_API_KEY": "AQ.segredo-que-nao-pode-sair"}):
            texto = report.gerar(self.destino).read_text(encoding="utf-8")
        self.assertNotIn("segredo-que-nao-pode-sair", texto)

    def test_cria_pasta_do_destino(self):
        alvo = Path(self._tmp.name) / "sub" / "dir" / "rel.txt"
        report.gerar(alvo)
        self.assertTrue(alvo.exists())


if __name__ == "__main__":
    unittest.main()
