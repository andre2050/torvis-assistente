"""O app precisa saber sozinho que há versão nova, sem ninguém clicar.

Os testes chamam o método numa janela falsa: o que interessa é a decisão
(anunciar ou ficar quieto), não a janela em si.
"""
import sys
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

with mock.patch.object(sys, "argv", ["torvis-test", "-", "{}"]):
    try:
        from gui.window import MainWindow
    except Exception as _exc:      # pragma: no cover - ambiente sem Qt
        MainWindow = None
        _MOTIVO = str(_exc)


def _falsa():
    return SimpleNamespace(_update_btn=mock.Mock(), _log=mock.Mock())


@unittest.skipIf(MainWindow is None, "Qt indisponível neste ambiente")
class ChecagemAoAbrirTest(unittest.TestCase):
    def _rodar(self, retorno=None, erro=None):
        janela = _falsa()
        alvo = mock.Mock(return_value=retorno, side_effect=erro)
        with mock.patch("core.update_manager.check_for_update", alvo):
            MainWindow._checar_atualizacao_ao_abrir(janela)
            for _ in range(60):
                if janela._update_btn.setText.called or alvo.called:
                    time.sleep(0.05)
                    break
                time.sleep(0.05)
        return janela

    def test_anuncia_versao_nova_no_botao(self):
        janela = self._rodar(retorno={"update_available": True, "remote_version": "9.9.9"})
        for _ in range(40):
            if janela._update_btn.setText.called:
                break
            time.sleep(0.05)
        self.assertTrue(janela._update_btn.setText.called)
        self.assertIn("9.9.9", janela._update_btn.setText.call_args[0][0])

    def test_sem_novidade_nao_mexe_no_botao(self):
        janela = self._rodar(retorno={"update_available": False})
        time.sleep(0.2)
        self.assertFalse(janela._update_btn.setText.called)

    def test_falha_de_rede_fica_silenciosa(self):
        janela = self._rodar(erro=RuntimeError("sem rede"))
        time.sleep(0.2)
        self.assertFalse(janela._update_btn.setText.called)
        self.assertFalse(janela._log.append_log.called)

    def test_agendamento_marca_os_dois_momentos(self):
        janela = _falsa()
        janela._checar_atualizacao_ao_abrir = lambda: None
        with mock.patch("PyQt6.QtCore.QTimer") as timer:
            MainWindow._agendar_checagem_de_atualizacao(janela)
        self.assertTrue(timer.singleShot.called)
        atraso = timer.singleShot.call_args[0][0]
        self.assertGreaterEqual(atraso, 1000)      # não compete com a abertura


if __name__ == "__main__":
    unittest.main()
