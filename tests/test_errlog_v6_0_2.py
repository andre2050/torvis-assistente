"""Registro de erros: grava, rotaciona e nunca derruba o app."""
import threading
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from core import errlog


class ErrlogTests(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self._arq = Path(self._tmp.name) / "erros.log"
        self._patch = mock.patch.object(errlog, "ARQUIVO", self._arq)
        self._patch.start()

    def tearDown(self):
        self._patch.stop()
        self._tmp.cleanup()

    def test_registra_com_data_e_thread(self):
        errlog.registrar("algo falhou", "teste")
        texto = self._arq.read_text(encoding="utf-8")
        self.assertIn("algo falhou", texto)
        self.assertIn("teste", texto)
        self.assertIn("thread", texto)

    def test_registra_excecao_com_traceback(self):
        try:
            raise ValueError("quebrou de proposito")
        except ValueError as exc:
            errlog.registrar_excecao(exc, "teste")
        texto = self._arq.read_text(encoding="utf-8")
        self.assertIn("ValueError", texto)
        self.assertIn("quebrou de proposito", texto)

    def test_rotaciona_ao_passar_do_limite(self):
        self._arq.write_text("x" * (errlog.LIMITE_BYTES + 10), encoding="utf-8")
        errlog.registrar("depois da rotacao")
        antigo = self._arq.with_name("erros.old.log")
        self.assertTrue(antigo.exists(), "o arquivo anterior deveria ser preservado")
        self.assertIn("depois da rotacao", self._arq.read_text(encoding="utf-8"))

    def test_erro_em_thread_chega_no_arquivo(self):
        errlog.instalar()

        def explode():
            raise RuntimeError("falha em thread de trabalho")

        t = threading.Thread(target=explode, name="teste-thread")
        t.start()
        t.join()
        # o hook é assíncrono ao fim da thread
        for _ in range(50):
            if self._arq.exists() and "falha em thread de trabalho" in self._arq.read_text(encoding="utf-8"):
                break
            threading.Event().wait(0.02)
        self.assertIn("falha em thread de trabalho", self._arq.read_text(encoding="utf-8"))

    def test_ultimos_devolve_blocos(self):
        errlog.registrar("primeiro", "a")
        errlog.registrar("segundo", "b")
        blocos = errlog.ultimos(2)
        self.assertEqual(len(blocos), 2)
        self.assertIn("segundo", blocos[-1])

    def test_pasta_descoberta_nao_estoura(self):
        errlog.ARQUIVO = Path(self._tmp.name) / "nao" / "existe" / "erros.log"
        errlog.registrar("cria a pasta")
        self.assertTrue(errlog.ARQUIVO.exists())

    def test_ultimos_sem_arquivo(self):
        self.assertEqual(errlog.ultimos(3), [])


if __name__ == "__main__":
    unittest.main()
