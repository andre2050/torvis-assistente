"""O catálogo tem que achar programa por apelido, fechar sem derrubar tudo e
criar projeto de verdade. Estes testes não abrem nem fecham nada na máquina:
as chamadas de sistema são substituídas."""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import catalogo_pc  # noqa: E402


class BuscaTest(unittest.TestCase):
    def setUp(self):
        catalogo_pc._cache = [
            {"nome": "Adobe Photoshop 2026", "alvo": "C:/ps/ps.exe", "tipo": "atalho"},
            {"nome": "Visual Studio Code", "alvo": "C:/vscode/Code.exe", "tipo": "atalho"},
            {"nome": "Sublime Text", "alvo": "C:/subl/sublime_text.exe", "tipo": "atalho"},
            {"nome": "Microsoft Word", "alvo": "C:/w/WINWORD.EXE", "tipo": "registro"},
        ]

    def tearDown(self):
        catalogo_pc._cache = None

    def test_apelido_curto_acha_o_programa(self):
        self.assertEqual(catalogo_pc.procurar("photoshop")["nome"], "Adobe Photoshop 2026")
        self.assertEqual(catalogo_pc.procurar("word")["nome"], "Microsoft Word")

    def test_nome_parcial_acha(self):
        self.assertEqual(catalogo_pc.procurar("sublime")["nome"], "Sublime Text")
        self.assertEqual(catalogo_pc.procurar("visual studio")["nome"], "Visual Studio Code")

    def test_erro_de_digitacao_ainda_acha(self):
        self.assertIsNotNone(catalogo_pc.procurar("photosop"))

    def test_vazio_nao_acha_nada(self):
        self.assertIsNone(catalogo_pc.procurar("   "))


class FecharTest(unittest.TestCase):
    def tearDown(self):
        catalogo_pc._cache = None

    def test_fecha_pela_janela_primeiro(self):
        with mock.patch.object(catalogo_pc, "_janelas",
                               return_value=["Sem título - Bloco de notas"]), \
             mock.patch.object(catalogo_pc, "_fechar_janela", return_value=True) as fechou:
            r = catalogo_pc.fechar("bloco de notas")
        self.assertEqual(r["status"], "closed")
        self.assertEqual(r["modo"], "janela")
        fechou.assert_called_once()

    def test_sem_janela_cai_no_processo(self):
        with mock.patch.object(catalogo_pc, "_janelas", return_value=[]), \
             mock.patch.object(catalogo_pc, "_processos",
                               return_value=[(1, "chrome.exe"), (2, "Code.exe")]), \
             mock.patch("subprocess.run", return_value=mock.Mock(returncode=0)):
            r = catalogo_pc.fechar("chrome")
        self.assertEqual(r["status"], "closed")
        self.assertEqual(r["modo"], "processo")

    def test_nome_vazio_falha_sem_explodir(self):
        self.assertEqual(catalogo_pc.fechar("")["status"], "failed")

    def test_programa_que_nao_existe_falha(self):
        with mock.patch.object(catalogo_pc, "_janelas", return_value=[]), \
             mock.patch.object(catalogo_pc, "_processos", return_value=[]):
            self.assertEqual(catalogo_pc.fechar("programa-inexistente")["status"], "failed")


class CriarProjetoTest(unittest.TestCase):
    def test_site_cria_tres_arquivos(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            r = catalogo_pc.criar_projeto("site", "meu-site", d)
            self.assertEqual(r["status"], "created")
            self.assertEqual(r["arquivos"], ["LEIA-ME.md", "index.html", "script.js", "style.css"])

    def test_jogo_e_app_tem_main(self):
        import tempfile
        for tipo in ("jogo", "app"):
            with tempfile.TemporaryDirectory() as d:
                r = catalogo_pc.criar_projeto(tipo, f"p-{tipo}", d)
                self.assertIn("main.py", r["arquivos"])

    def test_nome_perigoso_nao_escapa_da_pasta(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            r = catalogo_pc.criar_projeto("site", "../../fora", d)
            self.assertTrue(Path(r["pasta"]).parent == Path(d))


class FerramentaTest(unittest.TestCase):
    def test_acao_desconhecida_avisa(self):
        from actions import pc_master
        r = pc_master.pc_master({"action": "explodir"})
        self.assertEqual(r["status"], "failed")
        self.assertIn("abrir", r["acoes"])

    def test_abrir_usa_o_catalogo(self):
        from actions import pc_master
        with mock.patch.object(catalogo_pc, "abrir",
                               return_value={"status": "started", "programa": "Word", "alvo": "x"}):
            r = pc_master.pc_master({"action": "abrir", "name": "word"})
        self.assertEqual(r["status"], "started")
        self.assertIn("Word", r["spoken"])


if __name__ == "__main__":
    unittest.main()
