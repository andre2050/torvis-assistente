"""Testes da escrita segura: o arquivo nunca pode ficar pior do que estava."""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from core import edicao_segura as es


class ValidacaoTests(unittest.TestCase):
    def test_css_completo_passa(self):
        css = ".a{color:#fff}\n.b{display:grid;gap:8px}\n"
        self.assertTrue(es.validar_codigo(css, "style.css")[0])

    def test_css_cortado_e_recusado(self):
        css = ".a{color:#fff}\n.b{display:grid;gap:8px"
        ok, motivo = es.validar_codigo(css, "style.css")
        self.assertFalse(ok)
        self.assertIn("nunca fechado", motivo)

    def test_chave_dentro_de_string_nao_conta(self):
        css = '.a{content:"}"}\n'
        self.assertTrue(es.validar_codigo(css, "style.css")[0])

    def test_comentario_sem_fechar_e_recusado(self):
        ok, motivo = es.validar_codigo("/* regra\n.a{color:red}\n", "style.css")
        self.assertFalse(ok)
        self.assertIn("cortada", motivo)

    def test_python_com_erro_de_sintaxe_e_recusado(self):
        ok, motivo = es.validar_codigo("def x(:\n    pass\n", "a.py")
        self.assertFalse(ok)
        self.assertIn("sintaxe", motivo)

    def test_python_bom_passa(self):
        self.assertTrue(es.validar_codigo("def x(a):\n    return a + 1\n", "a.py")[0])

    def test_js_cortado_e_recusado(self):
        ok, motivo = es.validar_codigo("function f(){\n  return 1;\n", "app.js")
        self.assertFalse(ok)
        self.assertTrue("nunca fechado" in motivo or "cortada" in motivo)

    def test_js_com_chave_em_comentario_nao_conta(self):
        self.assertTrue(es.validar_codigo("function f(){ // } nada\n return 1;\n}\n", "app.js")[0])

    def test_resposta_vazia_e_recusada(self):
        self.assertFalse(es.validar_codigo("   ", "a.css")[0])

    def test_resposta_com_cerca_no_fim_e_recusada(self):
        ok, motivo = es.validar_codigo(".a{color:red}\n```", "style.css")
        self.assertFalse(ok)
        self.assertIn("cortada", motivo)


class GravacaoTests(unittest.TestCase):
    def test_grava_e_guarda_copia(self):
        with tempfile.TemporaryDirectory() as tmp:
            alvo = Path(tmp) / "style.css"
            alvo.write_text(".a{color:blue}\n", encoding="utf-8")
            r = es.escrever_com_seguranca(alvo, ".a{color:red}\n")
            self.assertTrue(r.ok)
            self.assertEqual(alvo.read_text(encoding="utf-8"), ".a{color:red}\n")
            self.assertTrue(r.copia and r.copia.exists())
            self.assertEqual(r.copia.read_text(encoding="utf-8"), ".a{color:blue}\n")

    def test_invalido_nao_toca_no_arquivo(self):
        with tempfile.TemporaryDirectory() as tmp:
            alvo = Path(tmp) / "style.css"
            original = ".a{color:blue}\n"
            alvo.write_text(original, encoding="utf-8")
            r = es.escrever_com_seguranca(alvo, ".a{color:red")
            self.assertFalse(r.ok)
            self.assertEqual(alvo.read_text(encoding="utf-8"), original)

    def test_arquivo_novo_em_pasta_que_nao_existe(self):
        with tempfile.TemporaryDirectory() as tmp:
            alvo = Path(tmp) / "sub" / "a.py"
            r = es.escrever_com_seguranca(alvo, "x = 1\n")
            self.assertTrue(r.ok)
            self.assertTrue(alvo.exists())

    def test_falha_de_disco_restaura_o_anterior(self):
        with tempfile.TemporaryDirectory() as tmp:
            alvo = Path(tmp) / "a.py"
            alvo.write_text("x = 1\n", encoding="utf-8")
            def quebrado(_origem, _destino):
                raise OSError("disco cheio")
            with mock.patch("os.replace", quebrado):
                r = es.escrever_com_seguranca(alvo, "x = 2\n")
            self.assertFalse(r.ok)
            self.assertIn("disco cheio", r.motivo)
            self.assertEqual(alvo.read_text(encoding="utf-8"), "x = 1\n")


class PatchTests(unittest.TestCase):
    def test_troca_exata(self):
        ok, novo, _ = es.aplicar_trecho("a\nb\nc\n", "b", "B")
        self.assertTrue(ok)
        self.assertEqual(novo, "a\nB\nc\n")

    def test_aceita_reindentacao_diferente(self):
        original = ".card {\n    color: blue;\n    padding: 8px;\n}\n"
        antes = ".card {\n  color: blue;\n  padding: 8px;\n}"
        depois = ".card {\n  color: red;\n  padding: 8px;\n}"
        ok, novo, _ = es.aplicar_trecho(original, antes, depois)
        self.assertTrue(ok)
        self.assertIn("color: red", novo)
        self.assertEqual(novo.count("color"), 1)

    def test_trecho_que_nao_existe_e_avisado(self):
        ok, novo, motivo = es.aplicar_trecho("a\nb\n", "zzz", "y")
        self.assertFalse(ok)
        self.assertIn("não achei", motivo)
        self.assertEqual(novo, "a\nb\n")

    def test_le_patch_com_cercas(self):
        resposta = "```css\n<<<ANTES>>>\n.a{color:blue}\n<<<DEPOIS>>>\n.a{color:red}\n<<<FIM>>>\n```"
        antes, depois = es.ler_patch(resposta)
        self.assertIn(".a{color:blue}", antes)
        self.assertIn(".a{color:red}", depois)
        self.assertNotIn("```", depois)

    def test_resposta_sem_marcas_devolve_none(self):
        self.assertIsNone(es.ler_patch(".a{color:red}"))


class GeracaoTests(unittest.TestCase):
    def test_insiste_quando_vem_cortado(self):
        respostas = [".a{color:red", ".a{color:red}\n"]
        pedidos = []
        def gerar(prompt):
            pedidos.append(prompt)
            return respostas[len(pedidos) - 1]
        texto = es.tentar_gerar("escreva", gerar, caminho="style.css")
        self.assertEqual(texto, ".a{color:red}\n")
        self.assertEqual(len(pedidos), 2)
        self.assertIn("cortada", pedidos[1])

    def test_todas_as_tentativas_ruins_levantam_erro(self):
        def gerar(_p):
            return ".a{color:red"
        with self.assertRaises(es.EscritaFalhou) as ctx:
            es.tentar_gerar("escreva", gerar, caminho="style.css", tentativas=2)
        self.assertIn("nunca fechado", str(ctx.exception))

    def test_falha_de_modelo_nao_aborta_a_primeira(self):
        chamadas = []
        def gerar(_p):
            chamadas.append(1)
            if len(chamadas) == 1:
                raise TimeoutError("demorou demais")
            return ".a{color:red}\n"
        self.assertEqual(es.tentar_gerar("x", gerar, caminho="style.css"), ".a{color:red}\n")
        self.assertEqual(len(chamadas), 2)

    def test_relato_explica_e_tranquiliza(self):
        texto = es.relato_para_pessoa("style.css", ["tentativa 1: cota diária estourada nesse modelo"])
        self.assertIn("style.css", texto)
        self.assertIn("ficou exatamente como estava", texto)
        self.assertIn("cota", texto)

    def test_relato_de_resposta_cortada_sugere_reduzir(self):
        texto = es.relato_para_pessoa("app.js", ["tentativa 2: a resposta termina com '```': veio cortada"])
        self.assertIn("pela metade", texto)


if __name__ == "__main__":
    unittest.main()
