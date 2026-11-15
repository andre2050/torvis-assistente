"""Trilha de testes do TORVIS (v6.6.1).

Os testes rodam offline: o servidor HTTP dos testes de API é local, e Azure,
Jira e Test.ai entram com resposta falsa. O que se protege aqui:

  - `executar()` só roda programa da lista e recusa encadeamento de shell;
  - a coleção de API reprova status errado, campo JSON errado e lentidão;
  - o JUnit gerado é XML válido (sem isso o Azure e o Xray recusariam);
  - sem plataforma configurada, a resposta diz o que falta em vez de estourar;
  - nenhum token aparece na mensagem devolvida.
"""
import json
import sys
import threading
import unittest
import xml.etree.ElementTree as ET
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from core import qa                                     # noqa: E402
from actions import qa_dev                              # noqa: E402


class _Servidor(BaseHTTPRequestHandler):
    def do_GET(self):                                      # noqa: N802
        if self.path == "/ok":
            corpo = json.dumps({"ok": True, "itens": [{"id": 7}]}).encode()
            self.send_response(200)
        elif self.path == "/lento":
            import time
            time.sleep(0.2)
            corpo = b'{"ok": true}'
            self.send_response(200)
        else:
            corpo = b'{"erro": "nao existe"}'
            self.send_response(404)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(corpo)

    def log_message(self, *_a):
        pass


class _Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.servidor = ThreadingHTTPServer(("127.0.0.1", 0), _Servidor)
        cls.base = f"http://127.0.0.1:{cls.servidor.server_port}"
        threading.Thread(target=cls.servidor.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.servidor.shutdown()


class ExecutorSeguroTests(unittest.TestCase):
    def test_roda_python_e_devolve_saida(self):
        resultado = qa.executar([sys.executable, "-c", "print('ok')"])
        self.assertTrue(resultado["ok"])
        self.assertIn("ok", resultado["saida"])

    def test_recusa_programa_fora_da_lista(self):
        resultado = qa.executar(["bash", "-c", "echo x"])
        self.assertFalse(resultado["ok"])
        self.assertIn("permitidos", resultado["saida"])

    def test_nao_usa_shell_entao_ponto_e_virgula_e_so_codigo(self):
        # "print(1); print(2)" é sintaxe do Python, não encadeamento de shell:
        # sem shell=True, o programa recebe o texto inteiro como argumento.
        resultado = qa.executar([sys.executable, "-c", "print(1); print(2)"])
        self.assertTrue(resultado["ok"])
        self.assertIn("1", resultado["saida"])
        self.assertIn("2", resultado["saida"])

    def test_respeita_tempo_limite(self):
        resultado = qa.executar([sys.executable, "-c", "import time; time.sleep(5)"], timeout=0.5)
        self.assertFalse(resultado["ok"])
        self.assertIn("encerrado", resultado["saida"])


class DeteccaoTests(unittest.TestCase):
    def test_diagnostico_lista_o_essencial(self):
        dados = qa.detectar(forcar=True)
        for chave in ("python", "node", "selenium", "puppeteer", "chrome"):
            self.assertIn(chave, dados)
        self.assertIn("Python", qa.resumo_ambiente(dados))

    def test_faltando_aponta_o_que_instalar(self):
        resumo = qa.resumo_ambiente({"python": "3.12", "node": None, "selenium": False,
                                     "playwright": False, "puppeteer": False,
                                     "pytest": False, "chrome": None, "sistema": "teste"})
        self.assertIn("pip install selenium", resumo)


class CriacaoTests(unittest.TestCase):
    def test_teste_selenium_e_python_valido(self):
        with TemporaryDirectory() as tmp:
            destino = qa.criar_teste_selenium(Path(tmp) / "t.py", "https://example.com", "h1", "Example")
            codigo = destino.read_text(encoding="utf-8")
        compile(codigo, "t.py", "exec")          # se não compilar, o teste quebra aqui
        self.assertIn("https://example.com", codigo)
        self.assertIn("headless", codigo)

    def test_teste_puppeteer_tem_assert(self):
        with TemporaryDirectory() as tmp:
            destino = qa.criar_teste_puppeteer(Path(tmp) / "t.js", "https://example.com", "h1")
            codigo = destino.read_text(encoding="utf-8")
        self.assertIn("puppeteer", codigo)
        self.assertIn("assert", codigo)

    def test_rodar_ui_recusa_arquivo_inexistente(self):
        resultado = qa.rodar_ui(Path("/nao/existe.py"))
        self.assertFalse(resultado["ok"])

    def test_rodar_ui_recusa_extensao_desconhecida(self):
        with TemporaryDirectory() as tmp:
            alvo = Path(tmp) / "teste.txt"
            alvo.write_text("nada", encoding="utf-8")
            resultado = qa.rodar_ui(alvo)
        self.assertIn("Só sei rodar", resultado["saida"])


class ApiTests(_Base):
    def test_colecao_completa_reprova_erros(self):
        colecao = {
            "nome": "local",
            "variaveis": {"base": self.base},
            "testes": [
                {"nome": "ok responde 200", "metodo": "GET", "url": "{{base}}/ok",
                 "espera_status": 200, "espera_json": [{"caminho": "ok", "igual": True}]},
                {"nome": "status errado", "metodo": "GET", "url": "{{base}}/ok",
                 "espera_status": 201},
                {"nome": "campo errado", "metodo": "GET", "url": "{{base}}/ok",
                 "espera_json": [{"caminho": "itens.0.id", "igual": 99}]},
                {"nome": "404 esperado", "metodo": "GET", "url": "{{base}}/nada",
                 "espera_status": 404},
            ],
        }
        resultado = qa.rodar_colecao(colecao)
        por_nome = {t["nome"]: t for t in resultado["resultados"]}
        self.assertTrue(por_nome["ok responde 200"]["passou"])
        self.assertTrue(por_nome["404 esperado"]["passou"])
        self.assertFalse(por_nome["status errado"]["passou"])
        self.assertIn("201", por_nome["status errado"]["detalhe"])
        self.assertFalse(por_nome["campo errado"]["passou"])

    def test_tempo_limite_reprova(self):
        colecao = {"nome": "lento", "testes": [
            {"nome": "lento demais", "url": f"{self.base}/lento", "espera_status": 200,
             "limite_ms": 50}]}
        resultado = qa.rodar_colecao(colecao)
        self.assertFalse(resultado["resultados"][0]["passou"])
        self.assertIn("lento", resultado["resultados"][0]["detalhe"])

    def test_url_invalida_nao_quebra(self):
        resultado = qa.rodar_colecao({"testes": [{"nome": "sem url", "url": "ftp://x"}]})
        self.assertFalse(resultado["resultados"][0]["passou"])

    def test_colecao_malformada_explica(self):
        self.assertIn("erro", qa.rodar_colecao({"nome": "x"}))


class JunitTests(_Base):
    def test_xml_valido_com_contagem_certa(self):
        resultado = qa.rodar_colecao({"nome": "suite", "testes": [
            {"nome": "a", "url": f"{self.base}/ok", "espera_status": 200},
            {"nome": "b", "url": f"{self.base}/ok", "espera_status": 500},
        ]})
        texto = qa.junit_xml(resultado)
        raiz = ET.fromstring(texto)                       # XML válido ou exceção
        self.assertEqual(raiz.get("tests"), "2")
        self.assertEqual(raiz.get("failures"), "1")

    def test_exporta_e_rele(self):
        with TemporaryDirectory() as tmp:
            resultado = {"nome": "s", "resultados": [
                {"nome": "x", "passou": True, "ms": 10}]}
            destino = qa.exportar_junit(resultado, Path(tmp) / "r.xml")
            self.assertTrue(destino.is_file())
            self.assertIn("<testsuite", destino.read_text(encoding="utf-8"))


class PlataformasTests(unittest.TestCase):
    @staticmethod
    def _manual(config):
        plataformas = {p: {"configurada": all(str(config.get(c) or "").strip() for c in cs),
                           "faltando": [c for c in cs if not str(config.get(c) or "").strip()]}
                       for p, cs in qa._CHAVES.items()}
        return {"plataformas": plataformas, "config": config}

    def _status(self, configurar: bool):
        """Configuração cheia ou vazia, sem tocar no config.json real."""
        config = ({"azure_devops_org": "org", "azure_devops_project": "proj",
                   "azure_devops_pat": "PAT-SECRETO", "atlassian_site": "site.atlassian.net",
                   "atlassian_email": "a@b.com", "atlassian_token": "TOKEN-SECRETO",
                   "atlassian_project": "QA", "testai_api_url": "https://t/x",
                   "testai_api_key": "CHAVE-SECRETA"} if configurar else {})
        return mock.patch.object(qa, "configurar_status", return_value=self._manual(config))

    def test_sem_configuracao_diz_o_que_falta(self):
        with self._status(False):
            saida = qa.publicar_azure({"resultados": []})
        self.assertIn("azure_devops_org", saida)

    def test_publica_no_azure_com_resultados(self):
        enviados = []

        def falso(url, corpo, cabecalhos, timeout=20.0):
            enviados.append((url, corpo))
            return {"id": 42} if "runs" in url and "results" not in url else {}

        with self._status(True), mock.patch.object(qa, "_post_json", side_effect=falso):
            saida = qa.publicar_azure({"resultados": [
                {"nome": "a", "passou": True, "ms": 12},
                {"nome": "b", "passou": False, "ms": 30, "detalhe": "status 500"}]})
        self.assertIn("42", saida)
        resultados = [c for u, c in enviados if "results" in u][0]
        self.assertEqual([r["outcome"] for r in resultados], ["Passed", "Failed"])
        self.assertNotIn("PAT-SECRETO", saida)

    def test_publica_no_jira_um_issue_por_falha(self):
        criados = []

        def falso(url, corpo, cabecalhos, timeout=20.0):
            criados.append(corpo)
            return {"key": "QA-1"}

        with self._status(True), mock.patch.object(qa, "_post_json", side_effect=falso):
            saida = qa.publicar_jira({"resultados": [
                {"nome": "ok", "passou": True},
                {"nome": "quebrou", "passou": False, "detalhe": "status 500",
                 "url": "https://x", "metodo": "GET"}]})
        self.assertEqual(len(criados), 1)
        self.assertIn("[teste] quebrou", criados[0]["fields"]["summary"])
        self.assertIn("1 issue", saida)
        self.assertNotIn("TOKEN-SECRETO", saida)

    def test_jira_sem_falha_nao_abre_issue(self):
        with self._status(True):
            self.assertIn("Nenhum teste falhou",
                          qa.publicar_jira({"resultados": [{"nome": "a", "passou": True}]}))

    def test_pacote_do_testai_e_gravado(self):
        with TemporaryDirectory() as tmp, \
             mock.patch.object(qa, "QA_DIR", Path(tmp)), \
             self._status(False):
            saida = qa.preparar_testai({"nome": "s", "resultados": [
                {"nome": "a", "passou": True, "ms": 5}]})
            pacote = json.loads((Path(tmp) / "testai_payload.json").read_text(encoding="utf-8"))
        self.assertEqual(pacote["results"][0]["status"], "passed")
        self.assertIn("testai_api_url", saida)


class PipelineTests(unittest.TestCase):
    def test_github_publica_junit(self):
        with TemporaryDirectory() as tmp:
            destino = qa.gerar_pipeline("github", Path(tmp) / "p")
            texto = destino.read_text(encoding="utf-8")
        self.assertIn("upload-artifact", texto)
        self.assertIn("--junitxml", texto)

    def test_azure_usa_publishtestresults(self):
        with TemporaryDirectory() as tmp:
            destino = qa.gerar_pipeline("azure", Path(tmp) / "p")
            texto = destino.read_text(encoding="utf-8")
        self.assertIn("PublishTestResults@2", texto)


class AcaoTests(_Base):
    def setUp(self):
        self.dir = TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.patches = [
            mock.patch.object(qa_dev, "_PASTA", Path(self.dir.name)),
            mock.patch.object(qa, "QA_DIR", Path(self.dir.name)),
        ]
        for p in self.patches:
            p.start()
            self.addCleanup(p.stop)

    def test_criar_ui_sem_url_pede_url(self):
        self.assertIn("URL", qa_dev.qa_dev_action({"action": "criar_ui"}))

    def test_criar_e_rodar_api_ponta_a_ponta(self):
        criar = qa_dev.qa_dev_action({"action": "criar_api", "base_url": self.base, "name": "local"})
        self.assertIn("testes_api.json", criar)

        colecao = json.loads((Path(self.dir.name) / "testes_api.json").read_text(encoding="utf-8"))
        colecao["testes"] = [{"nome": "raiz responde 200", "metodo": "GET",
                              "url": "{{base}}/ok", "espera_status": 200}]
        (Path(self.dir.name) / "testes_api.json").write_text(
            json.dumps(colecao), encoding="utf-8")

        roda = qa_dev.qa_dev_action({"action": "rodar_api"})
        self.assertIn("1 de 1 passaram", roda)
        self.assertTrue((Path(self.dir.name) / "resultado-junit.xml").is_file())

    def test_publicar_sem_resultado_avisa(self):
        self.assertIn("Rode um teste antes",
                      qa_dev.qa_dev_action({"action": "publicar", "target": "junit"}))

    def test_diagnostico_pela_acao(self):
        self.assertIn("Ambiente de testes", qa_dev.qa_dev_action({"action": "diagnostico"}))


if __name__ == "__main__":
    unittest.main()
