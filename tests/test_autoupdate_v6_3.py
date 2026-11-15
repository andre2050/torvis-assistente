"""Atualização automática: aplica na abertura e nunca impede o app de abrir."""
import json
import sys
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from core import autoupdate, update_manager as um


class AplicarNaAberturaTests(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.marcador = Path(self._tmp.name) / "atualizado_em.json"
        self._p = mock.patch.object(autoupdate, "MARCADOR", self.marcador)
        self._p.start()
        self._c = mock.patch.object(autoupdate, "config",
                                    return_value={"auto_update_apply_on_start": True})
        self._c.start()

    def tearDown(self):
        self._c.stop()
        self._p.stop()
        self._tmp.cleanup()

    def test_aplica_quando_ha_versao_nova(self):
        with mock.patch.object(um, "read_pending_update", return_value={"version": "6.3.0", "path": "/x"}), \
                mock.patch.object(um, "installed_version", return_value="6.2.1"), \
                mock.patch.object(um, "apply_pending_update",
                                  return_value={"version": "6.3.0", "applied_files": 10}) as aplicar:
            resultado = autoupdate.aplicar_na_abertura()
        self.assertEqual(resultado["version"], "6.3.0")
        aplicar.assert_called_once()

    def test_sem_pendente_nao_faz_nada(self):
        with mock.patch.object(um, "read_pending_update", return_value=None), \
                mock.patch.object(um, "apply_pending_update") as aplicar:
            self.assertIsNone(autoupdate.aplicar_na_abertura())
        aplicar.assert_not_called()

    def test_pacote_igual_e_descartado(self):
        with mock.patch.object(um, "read_pending_update", return_value={"version": "6.2.1"}), \
                mock.patch.object(um, "installed_version", return_value="6.2.1"), \
                mock.patch.object(um, "apply_pending_update") as aplicar, \
                mock.patch.object(um, "cancel_pending_update") as cancelar:
            self.assertIsNone(autoupdate.aplicar_na_abertura())
        aplicar.assert_not_called()
        cancelar.assert_called_once()

    def test_falha_ao_aplicar_nao_levanta(self):
        with mock.patch.object(um, "read_pending_update", return_value={"version": "6.3.0"}), \
                mock.patch.object(um, "installed_version", return_value="6.2.1"), \
                mock.patch.object(um, "apply_pending_update", side_effect=OSError("disco cheio")):
            self.assertIsNone(autoupdate.aplicar_na_abertura())

    def test_desligado_nao_aplica(self):
        with mock.patch.object(autoupdate, "config", return_value={"auto_update_apply_on_start": False}), \
                mock.patch.object(um, "apply_pending_update") as aplicar:
            self.assertIsNone(autoupdate.aplicar_na_abertura())
        aplicar.assert_not_called()

    def test_marcador_avisa_uma_vez(self):
        with mock.patch.object(um, "read_pending_update", return_value={"version": "6.3.0"}), \
                mock.patch.object(um, "installed_version", return_value="6.2.1"), \
                mock.patch.object(um, "apply_pending_update",
                                  return_value={"version": "6.3.0", "applied_files": 7}):
            autoupdate.aplicar_na_abertura()
        aviso = autoupdate.atualizacao_recem_aplicada()
        self.assertEqual(aviso["version"], "6.3.0")
        self.assertEqual(aviso["previous"], "6.2.1")
        self.assertIsNone(autoupdate.atualizacao_recem_aplicada(), "só avisa uma vez")

    def test_marcador_antigo_nao_avisa(self):
        self.marcador.write_text(json.dumps({"version": "6.3.0", "when": time.time() - 3600}),
                                 encoding="utf-8")
        self.assertIsNone(autoupdate.atualizacao_recem_aplicada())


class VigiaTests(unittest.TestCase):
    def test_desligado_nao_cria_thread(self):
        with mock.patch.object(autoupdate, "config", return_value={"auto_update": False}):
            self.assertIsNone(autoupdate.iniciar_vigia())

    def test_sem_novidade_nao_prepara(self):
        with mock.patch.object(um, "check_for_update", return_value={"update_available": False}), \
                mock.patch.object(um, "prepare_remote_update") as preparar:
            self.assertIsNone(autoupdate.verificar_uma_vez())
        preparar.assert_not_called()

    def test_prepara_quando_ha_versao_nova(self):
        with mock.patch.object(um, "check_for_update", return_value={"update_available": True}), \
                mock.patch.object(um, "prepare_remote_update",
                                  return_value={"version": "6.3.0", "remote_version": "6.3.0"}):
            preparado = autoupdate.verificar_uma_vez()
        self.assertEqual(preparado["version"], "6.3.0")

    def test_falha_de_rede_nao_estoura(self):
        with mock.patch.object(um, "check_for_update", side_effect=OSError("sem rede")):
            self.assertIsNone(autoupdate.verificar_uma_vez())

    def test_config_padrao_ligada(self):
        valores = autoupdate.config()
        self.assertTrue(valores["auto_update"])
        self.assertTrue(valores["auto_update_apply_on_start"])
        self.assertEqual(valores["auto_update_hours"], 6.0)


class BootstrapTests(unittest.TestCase):
    def _rodar(self, erro=None):
        import iniciar_auto

        ordem: list[str] = []
        falso_main = mock.MagicMock()
        falso_main.main.side_effect = lambda: ordem.append("abrir")

        def aplicar():
            if erro:
                raise erro
            ordem.append("aplicar")

        with mock.patch.object(autoupdate, "aplicar_na_abertura", side_effect=aplicar), \
                mock.patch.dict(sys.modules, {"main": falso_main}):
            codigo = iniciar_auto.main()
        return ordem, codigo

    def test_aplica_antes_de_abrir(self):
        ordem, codigo = self._rodar()
        self.assertEqual(ordem, ["aplicar", "abrir"], "aplicar tem que vir antes de abrir")
        self.assertEqual(codigo, 0)

    def test_abre_mesmo_se_aplicar_falhar(self):
        ordem, codigo = self._rodar(erro=RuntimeError("boom"))
        self.assertEqual(ordem, ["abrir"], "falha na atualização não pode impedir a abertura")
        self.assertEqual(codigo, 0)


if __name__ == "__main__":
    unittest.main()
