"""Prova que o agente não grava arquivo cortado nem desiste no primeiro 429."""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from actions import dev_agent as d
from core import edicao_segura as es


INFO = {"path": "style.css", "description": "folha de estilo", "imports": []}


class EscritaDoAgenteTests(unittest.TestCase):
    def setUp(self):
        d._DESCANSO.clear()
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()
        d._DESCANSO.clear()

    def test_429_num_modelo_nao_derruba_o_arquivo(self):
        chamadas = []

        def fake_texto(prompt, *, model_name="smart", fast=False, purpose=""):
            chamadas.append(model_name)
            if model_name == "smart":
                raise RuntimeError("429 RESOURCE_EXHAUSTED quota")
            return ".a{color:red}\n"

        with mock.patch.object(d, "_model_text", fake_texto):
            codigo = d._write_file(INFO, "projeto", [INFO], "css", self.dir, {})

        self.assertIn("color:red", codigo)
        self.assertTrue((self.dir / "style.css").exists())
        self.assertIn("smart", chamadas)
        self.assertIn("fast", chamadas)
        self.assertGreater(d._DESCANSO.get("smart", 0), 0)   # posto de castigo

    def test_resposta_cortada_nao_chega_no_arquivo(self):
        respostas = [".a{color:red", ".a{color:red}\n"]

        def fake_texto(prompt, *, model_name="smart", fast=False, purpose=""):
            return respostas.pop(0) if respostas else ".a{color:red}\n"

        with mock.patch.object(d, "_model_text", fake_texto):
            codigo = d._write_file(INFO, "projeto", [INFO], "css", self.dir, {})

        self.assertEqual((self.dir / "style.css").read_text(encoding="utf-8").strip(), ".a{color:red}")
        self.assertEqual(codigo.strip(), ".a{color:red}")

    def test_tudo_falhando_nao_cria_arquivo_e_explica(self):
        def fake_texto(prompt, *, model_name="smart", fast=False, purpose=""):
            raise RuntimeError("429 RESOURCE_EXHAUSTED quota")

        with mock.patch.object(d, "_model_text", fake_texto):
            with self.assertRaises(es.EscritaFalhou) as ctx:
                d._write_file(INFO, "projeto", [INFO], "css", self.dir, {})

        self.assertFalse((self.dir / "style.css").exists())
        texto = str(ctx.exception)
        self.assertIn("cota", texto.lower())
        # as três tentativas de geração aconteceram, com a escada toda
        self.assertIn("fast", texto)

    def test_arquivo_existente_fica_intacto_quando_nada_e_valido(self):
        alvo = self.dir / "style.css"
        alvo.write_text(".a{color:blue}\n", encoding="utf-8")

        def fake_texto(prompt, *, model_name="smart", fast=False, purpose=""):
            return ".a{color:red"          # sempre cortado

        with mock.patch.object(d, "_model_text", fake_texto):
            with self.assertRaises(es.EscritaFalhou):
                d._write_file(INFO, "projeto", [INFO], "css", self.dir, {})

        self.assertEqual(alvo.read_text(encoding="utf-8"), ".a{color:blue}\n")


class CorrecaoPorTrechoTests(unittest.TestCase):
    def setUp(self):
        d._DESCANSO.clear()
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        # arquivo grande o suficiente para o caminho de trecho
        regras = "".join(f".r{i}{{margin:{i}px}}\n" for i in range(400))
        self.alvo = self.dir / "site.css"
        self.alvo.write_text(regras + ".hero{color:blue}\n", encoding="utf-8")

    def tearDown(self):
        self._tmp.cleanup()
        d._DESCANSO.clear()

    def test_troca_so_o_trecho_pedido(self):
        resposta = ("<<<ANTES>>>\n.hero{color:blue}\n<<<DEPOIS>>>\n.hero{color:gold}\n<<<FIM>>>")
        with mock.patch.object(d, "_texto_de_escrita", lambda *a, **k: resposta):
            novo = d._corrigir_um_arquivo("site.css", self.alvo.read_text(encoding="utf-8"), "corrija", project_dir=self.dir)

        self.assertIn(".hero{color:gold}", novo)
        self.assertIn(".r399{margin:399px}", novo)          # o resto ficou
        self.assertIn(".hero{color:gold}", self.alvo.read_text(encoding="utf-8"))

    def test_trecho_errado_cai_para_reescrita_completa(self):
        certo = self.alvo.read_text(encoding="utf-8").replace("color:blue", "color:green")
        with mock.patch.object(d, "_texto_de_escrita", lambda *a, **k: "<<<ANTES>>>\nnao existe\n<<<DEPOIS>>>\nx\n<<<FIM>>>"), \
             mock.patch.object(d, "_corrigir_um_arquivo", wraps=d._corrigir_um_arquivo):
            # primeira estratégia falha duas vezes; depois o modelo devolve o arquivo inteiro
            respostas = iter([
                "<<<ANTES>>>\nnao existe\n<<<DEPOIS>>>\nx\n<<<FIM>>>",
                "<<<ANTES>>>\nnao existe\n<<<DEPOIS>>>\nx\n<<<FIM>>>",
                certo,
            ])
            with mock.patch.object(d, "_texto_de_escrita", lambda *a, **k: next(respostas)):
                novo = d._corrigir_um_arquivo("site.css", self.alvo.read_text(encoding="utf-8"), "corrija", project_dir=self.dir)

        self.assertIn("color:green", novo)
        self.assertIn(".r0{margin:0px}", novo)


class EscadaTests(unittest.TestCase):
    def setUp(self):
        d._DESCANSO.clear()

    def tearDown(self):
        d._DESCANSO.clear()

    def test_modelo_em_descanso_e_pulado(self):
        d._DESCANSO["smart"] = d.time.time() + 500
        tentados = []

        def fake_texto(prompt, *, model_name="smart", fast=False, purpose=""):
            tentados.append(model_name)
            return "ok"

        with mock.patch.object(d, "_model_text", fake_texto):
            d._texto_de_escrita("x", purpose="t")

        self.assertEqual(tentados, ["fast"])

    def test_quando_todos_estao_em_descanso_o_erro_diz_isso(self):
        for m in d._modelos_de_escrita():
            d._DESCANSO[m] = d.time.time() + 500
        with self.assertRaises(es.EscritaFalhou) as ctx:
            d._texto_de_escrita("x", purpose="t")
        self.assertIn("descanso", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
