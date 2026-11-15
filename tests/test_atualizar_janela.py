"""Atualizador por janela (ATUALIZAR-TORVIS.pyw).

O arquivo é um .pyw (dois cliques, sem console), então aqui ele é carregado
como módulo. O que se protege: config e notas não podem ser sobrescritas por
um arquivo do pacote, SHA-256 errado para antes de copiar, e TORVIS aberto
bloqueia a troca em vez de copiar pela metade.
"""
import hashlib
import importlib.util
import json
import os
import sys
import unittest
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory

RAIZ = Path(__file__).resolve().parents[1]
ARQUIVO = RAIZ / "ATUALIZAR-TORVIS.pyw"


def _carregar():
    spec = importlib.util.spec_from_loader("atualizador_janela", loader=None)
    modulo = importlib.util.module_from_spec(spec)
    modulo.__dict__["__file__"] = str(ARQUIVO)
    exec(compile(ARQUIVO.read_text(encoding="utf-8"), str(ARQUIVO), "exec"), modulo.__dict__)
    return modulo


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = _carregar()

    def _app(self, base: Path, versao: str) -> Path:
        app = base / "TORVIS"
        (app / "core").mkdir(parents=True, exist_ok=True)
        (app / "core" / "version.py").write_text(f'VERSAO = "{versao}"\n', encoding="utf-8")
        (app / "config.json").write_text('{"minha":"chave"}', encoding="utf-8")
        (app / "notas").mkdir(exist_ok=True)
        (app / "notas" / "notas.json").write_text('{"itens":[]}', encoding="utf-8")
        return app

    def _pacote(self, base: Path, versao: str) -> Path:
        raiz = base / f"TORVIS-Assistente-v{versao}"
        (raiz / "core").mkdir(parents=True, exist_ok=True)
        (raiz / "core" / "version.py").write_text(f'VERSAO = "{versao}"\n', encoding="utf-8")
        (raiz / "actions").mkdir(exist_ok=True)
        (raiz / "actions" / "qa_dev.py").write_text("# ferramenta nova\n", encoding="utf-8")
        # o pacote traz um config.json: ele NÃO pode substituir o do usuário
        (raiz / "config.json").write_text('{"nao_deve":"entrar"}', encoding="utf-8")
        destino = base / f"pacote-{versao}.zip"
        with zipfile.ZipFile(destino, "w") as z:
            for arquivo in raiz.rglob("*"):
                if arquivo.is_file():
                    z.write(arquivo, arquivo.relative_to(raiz.parent))
        return destino

    def _manifesto(self, base: Path, versao: str, pacote: Path, sha: str | None = None) -> Path:
        texto = base / "update.json"
        texto.write_text(json.dumps({
            "version": versao, "package_url": pacote.resolve().as_uri(),
            "sha256": sha or hashlib.sha256(pacote.read_bytes()).hexdigest()}), encoding="utf-8")
        return texto


class PreservacaoTests(Base):
    def test_dados_do_usuario_ficam_fora(self):
        for caminho in ("config.json", "memory/x.json", "notas/notas.json", "updates/a.log",
                        "erros.log", ".env", "core/version.py.bak"):
            self.assertTrue(self.mod.preservar(caminho), caminho)

    def test_codigo_e_substituivel(self):
        for caminho in ("core/version.py", "actions/qa_dev.py", "requirements.txt"):
            self.assertFalse(self.mod.preservar(caminho), caminho)


class AtualizacaoTests(Base):
    def test_instala_e_preserva(self):
        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            app = self._app(base, "6.6.0")
            pacote = self._pacote(base, "6.6.3")
            manifesto = self._manifesto(base, "6.6.3", pacote)

            relato = self.mod.atualizar(app, manifesto_url=manifesto.as_uri())

            self.assertTrue(relato["ok"], relato["mensagem"])
            self.assertEqual(self.mod.versao_instalada(app), "6.6.3")
            self.assertTrue((app / "actions" / "qa_dev.py").is_file())
            self.assertEqual((app / "config.json").read_text(encoding="utf-8"),
                             '{"minha":"chave"}')
            self.assertTrue((app / "notas" / "notas.json").is_file())

    def test_sha_errado_para_antes_de_copiar(self):
        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            app = self._app(base, "6.6.0")
            pacote = self._pacote(base, "6.6.3")
            manifesto = self._manifesto(base, "6.6.3", pacote, sha="0" * 64)

            relato = self.mod.atualizar(app, manifesto_url=manifesto.as_uri())

            self.assertFalse(relato["ok"])
            self.assertIn("SHA-256", relato["mensagem"])
            self.assertEqual(self.mod.versao_instalada(app), "6.6.0")
            self.assertFalse((app / "actions").exists())

    def test_zip_invalido_nao_estoura(self):
        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            app = self._app(base, "6.6.0")
            ruim = base / "ruim.zip"
            ruim.write_bytes(b"isto nao e zip")
            manifesto = base / "update.json"
            manifesto.write_text(json.dumps({
                "version": "6.6.3", "package_url": ruim.resolve().as_uri(),
                "sha256": hashlib.sha256(ruim.read_bytes()).hexdigest()}), encoding="utf-8")

            relato = self.mod.atualizar(app, manifesto_url=manifesto.as_uri())

            self.assertFalse(relato["ok"])
            self.assertIn("zip", relato["mensagem"].lower())
            self.assertEqual(self.mod.versao_instalada(app), "6.6.0")

    def test_mesma_versao_nao_faz_nada(self):
        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            app = self._app(base, "6.6.3")
            pacote = self._pacote(base, "6.6.3")
            manifesto = self._manifesto(base, "6.6.3", pacote)
            relato = self.mod.atualizar(app, manifesto_url=manifesto.as_uri())
            self.assertTrue(relato["ok"])
            self.assertIn("já está", relato["mensagem"].lower())

    def test_registro_em_updates(self):
        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            app = self._app(base, "6.6.0")
            pacote = self._pacote(base, "6.6.3")
            manifesto = self._manifesto(base, "6.6.3", pacote)
            self.mod.atualizar(app, manifesto_url=manifesto.as_uri())
            log = (app / "updates" / "atualizacao-janela.log").read_text(encoding="utf-8")
            self.assertIn("6.6.0 -> 6.6.3", log)


class DescobertaTests(Base):
    def test_acha_a_pasta_do_app(self):
        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            app = self._app(base, "6.6.2")
            self.assertEqual(self.mod.achar_app(app / "core"), app)

    def test_pasta_que_nao_e_do_torvis_devolve_none(self):
        # O módulo é carregado de uma cópia fora do repositório: se ele ficasse
        # aqui dentro, achar_app acharia o próprio repo e o teste não provaria nada.
        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            copia = base / "ATUALIZAR-TORVIS.pyw"
            copia.write_text(ARQUIVO.read_text(encoding="utf-8"), encoding="utf-8")
            spec = importlib.util.spec_from_loader("atualizador_isolado", loader=None)
            isolado = importlib.util.module_from_spec(spec)
            isolado.__dict__["__file__"] = str(copia)
            exec(compile(copia.read_text(encoding="utf-8"), str(copia), "exec"), isolado.__dict__)

            vazia = base / "vazia"
            vazia.mkdir()
            antes = Path.cwd()
            os.chdir(vazia)
            try:
                self.assertIsNone(isolado.achar_app(vazia))
            finally:
                os.chdir(antes)


if __name__ == "__main__":
    unittest.main()
