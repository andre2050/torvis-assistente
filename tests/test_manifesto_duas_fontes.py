"""O botão ATUALIZAR só pode dizer "já está atualizado" quando NÃO existe
versão maior. O caso real: o update.json do branch ficou em 7.0.0 enquanto o
release tinha 7.4.0, e o app respondia que estava em dia."""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import update_manager  # noqa: E402


def _man(versao):
    return {"version": versao, "package_url": "https://exemplo/p.zip",
            "sha256": "a" * 64, "channel": "stable"}


class EscolhaDaFonteTest(unittest.TestCase):
    def _buscar(self, mapa):
        def leitor(url, timeout):
            if url in mapa:
                d = dict(mapa[url])
                d.setdefault("sha256", "a" * 64)
                d.setdefault("package_url", "https://exemplo/p.zip")
                return d
            raise RuntimeError("404")
        with mock.patch.object(update_manager, "_manifesto_de", side_effect=leitor):
            return update_manager.fetch_remote_manifest("https://branch/update.json")

    def test_release_novo_vence_branch_velho(self):
        r = self._buscar({
            "https://branch/update.json": _man("7.0.0"),
            update_manager.MIRROR_MANIFEST_URLS[0]: _man("7.4.0"),
        })
        self.assertEqual(r["version"], "7.4.0")

    def test_branch_mais_novo_tambem_vale(self):
        r = self._buscar({
            "https://branch/update.json": _man("7.9.0"),
            update_manager.MIRROR_MANIFEST_URLS[0]: _man("7.4.0"),
        })
        self.assertEqual(r["version"], "7.9.0")

    def test_uma_fonte_fora_do_ar_nao_derruba(self):
        r = self._buscar({"https://branch/update.json": _man("7.4.0")})
        self.assertEqual(r["version"], "7.4.0")

    def test_nenhuma_fonte_avisa(self):
        with mock.patch.object(update_manager, "_manifesto_de",
                               side_effect=RuntimeError("sem rede")):
            with self.assertRaises(RuntimeError):
                update_manager.fetch_remote_manifest("https://branch/update.json")

    def test_versao_maior_nao_diz_que_esta_atualizado(self):
        manifesto = {**_man("7.4.0"), "manifest_url": "https://branch/update.json"}
        with mock.patch.object(update_manager, "fetch_remote_manifest",
                               return_value=manifesto):
            r = update_manager.check_for_update(current_version="7.3.0")
        self.assertTrue(r.get("available") or r.get("update_available") or
                        r.get("has_update"), r)


if __name__ == "__main__":
    unittest.main()
