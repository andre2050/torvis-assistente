"""Aplicação da atualização: troca atômica, proteção dos dados e rollback."""
import json
import shutil
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from core import update_manager as um


def _montar(base: Path, versao_nova: str = "9.9.9") -> tuple[Path, Path]:
    staged = base / f"staged-{versao_nova}"
    app = base / "app"
    (staged / "core").mkdir(parents=True)
    (app / "core").mkdir(parents=True)
    (staged / "core" / "version.py").write_text(f'VERSAO = "{versao_nova}"\n', encoding="utf-8")
    (staged / "novo.txt").write_text("novo\n", encoding="utf-8")
    (staged / "config").mkdir()
    (staged / "config" / "api_keys.json").write_text('{"api_key":"DO_PACOTE"}', encoding="utf-8")
    (app / "core" / "version.py").write_text('VERSAO = "6.0.0"\n', encoding="utf-8")
    (app / "config").mkdir()
    (app / "config" / "api_keys.json").write_text('{"api_key":"minha"}', encoding="utf-8")

    files = {r: um._sha256(staged / r)
             for r in ("core/version.py", "novo.txt", "config/api_keys.json")}
    (staged / "update-manifest.json").write_text(json.dumps({
        "product": "T", "version": versao_nova, "channel": "stable",
        "format": 1, "files": files,
    }), encoding="utf-8")
    (base / "pending.json").write_text(
        json.dumps({"version": versao_nova, "path": str(staged)}), encoding="utf-8")
    return staged, app


class AplicarTests(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.base = Path(self._tmp.name)
        self.staged, self.app = _montar(self.base)
        self._p1 = mock.patch.object(um, "UPDATE_DIR", self.base)
        self._p2 = mock.patch.object(um, "APP_DIR", self.app)
        self._p1.start()
        self._p2.start()

    def tearDown(self):
        self._p2.stop()
        self._p1.stop()
        self._tmp.cleanup()

    def test_aplica_arquivos_e_reconhece_a_versao(self):
        resultado = um.apply_pending_update()
        self.assertEqual(resultado["version"], "9.9.9")
        self.assertEqual(um.installed_version(self.app), "9.9.9")
        self.assertTrue((self.app / "novo.txt").exists())

    def test_nao_sobrescreve_chave_do_usuario(self):
        resultado = um.apply_pending_update()
        self.assertIn("config/api_keys.json", resultado["skipped_files"])
        self.assertEqual((self.app / "config" / "api_keys.json").read_text(),
                         '{"api_key":"minha"}')

    def test_limpa_o_pendente_e_o_pacote(self):
        um.apply_pending_update()
        self.assertIsNone(um.read_pending_update())
        self.assertFalse(self.staged.exists())
        self.assertTrue((self.base / "applied.json").exists())

    def test_falha_no_meio_volta_tudo_como_estava(self):
        original = (self.app / "core" / "version.py").read_text()
        chamadas = {"n": 0}
        copiar_real = shutil.copy2

        def copiar_com_falha(origem, destino, *a, **k):
            # deixa o primeiro arquivo passar e quebra no segundo
            if str(origem).endswith("novo.txt"):
                chamadas["n"] += 1
                raise OSError("disco cheio (simulado)")
            return copiar_real(origem, destino, *a, **k)

        with mock.patch.object(um.shutil, "copy2", side_effect=copiar_com_falha):
            with self.assertRaises(OSError):
                um.apply_pending_update()

        self.assertEqual((self.app / "core" / "version.py").read_text(), original,
                         "o arquivo já trocado precisa voltar ao original")
        self.assertIsNotNone(um.read_pending_update(), "o pendente continua para nova tentativa")

    def test_sem_pendente_avisa(self):
        (self.base / "pending.json").unlink()
        with self.assertRaises(ValueError):
            um.apply_pending_update()

    def test_pacote_ausente_avisa(self):
        shutil.rmtree(self.staged)
        with self.assertRaises(ValueError):
            um.apply_pending_update()

    def test_manifesto_adulterado_e_recusado(self):
        alvo = self.staged / "novo.txt"
        alvo.write_text("conteudo trocado depois da validação\n", encoding="utf-8")
        with self.assertRaises(ValueError):
            um.apply_pending_update()
        self.assertEqual((self.app / "core" / "version.py").read_text(),
                         'VERSAO = "6.0.0"\n')

    def test_protegidos_reconhecidos(self):
        for rel in (".env", "memory/long_term.json", "config/api_keys.json"):
            self.assertTrue(um._protegido(rel), rel)
        for rel in ("core/version.py", "README.md"):
            self.assertFalse(um._protegido(rel), rel)


if __name__ == "__main__":
    unittest.main()
