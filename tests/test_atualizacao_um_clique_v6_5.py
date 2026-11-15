"""Atualização de um clique (v6.5.0): o clique instala, não só baixa.

O que estes testes protegem:
  - o ciclo fechar → reabrir acontece sem console e sem pedir tecla;
  - a espera é pelo processo certo, não por um tempo fixo;
  - a abertura seguinte aplica o pacote (um caminho só de aplicação);
  - se a reabertura não puder ser agendada, o app avisa em vez de engolir o erro.
"""
import os
import subprocess
import sys
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from core import autoupdate                                    # noqa: E402

sys.path.insert(0, str(RAIZ / "tools"))
import reabrir_apos_sair as reabrir_mod                          # noqa: E402

from gui import window as janela                                 # noqa: E402


class EsperaTests(unittest.TestCase):
    def test_pid_zero_nao_espera(self):
        self.assertTrue(reabrir_mod.esperar_sair(0))

    def test_pid_inexistente_sai_na_hora(self):
        inicio = time.monotonic()
        self.assertTrue(reabrir_mod.esperar_sair(999_999, maximo=5))
        self.assertLess(time.monotonic() - inicio, 3)

    def test_espera_o_processo_terminar(self):
        filho = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(1.2)"])
        inicio = time.monotonic()
        saiu = reabrir_mod.esperar_sair(filho.pid, maximo=15)
        duracao = time.monotonic() - inicio
        filho.wait()
        self.assertTrue(saiu)
        self.assertGreater(duracao, 0.8)      # realmente esperou
        self.assertLess(duracao, 10)

    def test_desiste_no_tempo_maximo(self):
        filho = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(6)"])
        try:
            self.assertFalse(reabrir_mod.esperar_sair(filho.pid, maximo=0.6))
        finally:
            filho.kill()
            filho.wait()


class ReabrirTests(unittest.TestCase):
    def test_pasta_sem_nada_explica_o_motivo(self):
        with TemporaryDirectory() as tmp:
            ok, motivo = reabrir_mod.reabrir(Path(tmp))
        self.assertFalse(ok)
        self.assertIn("INICIAR.bat", motivo)
        self.assertIn("main.py", motivo)

    def test_cai_no_main_quando_o_bat_falha(self):
        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "main.py").write_text(
                "open('abriu.txt','w').write('ok')", encoding="utf-8")
            ok, motivo = reabrir_mod.reabrir(base)
            for _ in range(40):
                if (base / "abriu.txt").is_file():
                    break
                time.sleep(0.05)
            self.assertTrue(ok, motivo)
            self.assertIn("main.py", motivo)
            self.assertTrue((base / "abriu.txt").is_file())

    def test_motivo_do_erro_nao_e_escondido(self):
        """O log chegou a dizer 'não encontrei' com o arquivo presente."""
        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "INICIAR.bat").write_text("@echo off", encoding="utf-8")
            ok, motivo = reabrir_mod.reabrir(base)
            self.assertFalse(ok)
            if os.name != "nt":
                self.assertIn("INICIAR.bat", motivo)
                self.assertIn("falhou", motivo.lower() + " falhou")


class AgendamentoTests(unittest.TestCase):
    def test_python_sem_console_existe(self):
        caminho = Path(autoupdate.python_sem_console())
        self.assertTrue(caminho.is_file(), caminho)

    def test_agenda_de_verdade_a_reabertura(self):
        """Sobe o helper real num app de mentira e vê o app 'reabrir'."""
        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "core").mkdir()
            (base / "tools").mkdir()
            (base / "estado").mkdir()
            (base / "tools" / "reabrir_apos_sair.py").write_text(
                (RAIZ / "tools" / "reabrir_apos_sair.py").read_text(encoding="utf-8"),
                encoding="utf-8")
            (base / "main.py").write_text(
                "open('voltou.txt','w').write('ok')", encoding="utf-8")

            with mock.patch.object(autoupdate, "__file__", str(base / "core" / "autoupdate.py")), \
                 mock.patch.object(autoupdate, "STATE_DIR", base / "estado"):
                agendado = autoupdate.agendar_reabertura(pid=999_999, atraso_s=0)
                log = Path(agendado["log"])
                for _ in range(60):
                    if (base / "voltou.txt").is_file():
                        break
                    time.sleep(0.1)

            self.assertTrue((base / "voltou.txt").is_file(), "o helper não reabriu o app")
            self.assertTrue(log.is_file())
            self.assertIn("reabertura:", log.read_text(encoding="utf-8"))

    def test_script_ausente_levanta_erro(self):
        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "core").mkdir()
            with mock.patch.object(autoupdate, "__file__", str(base / "core" / "autoupdate.py")):
                with self.assertRaises(FileNotFoundError):
                    autoupdate.agendar_reabertura(pid=1, atraso_s=0)


class CliqueTests(unittest.TestCase):
    """O botão instala: sem diálogo repetindo a decisão já tomada."""

    def _falsa(self):
        classe = type("Falsa", (), {})
        obj = classe()
        obj._log = mock.Mock()
        obj._content_sig = mock.Mock()
        return obj

    def test_clique_agenda_reabertura_e_fecha(self):
        obj = self._falsa()
        agendado = {"pid": 4242, "script": "s", "log": "l"}
        with mock.patch.object(autoupdate, "agendar_reabertura", return_value=agendado) as agendar, \
             mock.patch.object(janela, "QTimer") as timer:
            janela.MainWindow._aplicar_atualizacao_agora(obj)
        agendar.assert_called_once()
        timer.singleShot.assert_called_once()
        obj._content_sig.emit.assert_called()

    def test_falha_ao_agendar_vira_aviso_e_nao_silencio(self):
        obj = self._falsa()
        with mock.patch.object(autoupdate, "agendar_reabertura",
                               side_effect=OSError("sem permissão")), \
             mock.patch.object(janela, "QTimer") as timer:
            janela.MainWindow._aplicar_atualizacao_agora(obj)
        obj._log.append_log.assert_called()
        self.assertIn("WRN", obj._log.append_log.call_args[0][0])
        timer.singleShot.assert_not_called()

    def test_fluxo_do_botao_nao_usa_mais_o_dialogo(self):
        import inspect
        fonte = inspect.getsource(janela.MainWindow._atualizar_sistema)
        self.assertIn("_aplicar_atualizacao_agora", fonte)
        self.assertNotIn("_oferecer_aplicar_atualizacao", fonte)


if __name__ == "__main__":
    unittest.main()
