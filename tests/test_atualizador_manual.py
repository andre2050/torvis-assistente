"""Atualizador manual do TORVIS (tools/atualizar_manual.py).

Este é o caminho que funciona quando o botão "ATUALIZAR SISTEMA" do app falha.
Então o que se testa aqui é justamente o que pode estragar a instalação de
alguém: sobrescrever configuração, instalar pacote corrompido, instalar pacote
de outra coisa, e apagar arquivo do usuário.
"""
import hashlib
import json
import sys
import unittest
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "tools"))

import atualizar_manual as am                            # noqa: E402


def _app(base: Path, versao: str, extra: dict | None = None) -> Path:
    """Cria um TORVIS falso (só o necessário) numa pasta."""
    (base / "core").mkdir(parents=True, exist_ok=True)
    (base / "core" / "version.py").write_text(f'VERSAO = "{versao}"\n', encoding="utf-8")
    for nome, texto in (extra or {}).items():
        alvo = base / nome
        alvo.parent.mkdir(parents=True, exist_ok=True)
        alvo.write_text(texto, encoding="utf-8")
    return base


def _pacote(base: Path, versao: str, extra: dict | None = None) -> Path:
    """Zip no mesmo formato do release: uma pasta raiz com core/version.py."""
    raiz = base / f"TORVIS-falso-{versao}"
    _app(raiz, versao, extra)
    destino = base / f"pacote-{versao}.zip"
    with zipfile.ZipFile(destino, "w") as z:
        for arquivo in raiz.rglob("*"):
            if arquivo.is_file():
                z.write(arquivo, arquivo.relative_to(raiz.parent))
    return destino


def _sha(arquivo: Path) -> str:
    return hashlib.sha256(arquivo.read_bytes()).hexdigest()


class PreservacaoTests(unittest.TestCase):
    def test_dados_do_usuario_ficam_intocados(self):
        for caminho in ("config.json", "memory/cognitive_memory.json", "updates/x.log",
                        "notas/notas.json", "tarefas/tarefas.json", "erros.log",
                        ".env", "backup/v6.zip", "core/version.py.bak"):
            self.assertTrue(am._preservar(caminho), caminho)

    def test_codigo_do_projeto_e_substituivel(self):
        for caminho in ("core/version.py", "core/qa.py", "actions/qa_dev.py",
                        "requirements.txt", "INICIAR.bat"):
            self.assertFalse(am._preservar(caminho), caminho)


class PacoteTests(unittest.TestCase):
    def test_acha_a_raiz_dentro_do_zip(self):
        with TemporaryDirectory() as tmp:
            raiz = _pacote(Path(tmp), "9.9.9")
            alvo = Path(tmp) / "extraido"
            with zipfile.ZipFile(raiz) as z:
                z.extractall(alvo)
            encontrada = am._pasta_raiz_extraida(alvo)
            self.assertTrue((encontrada / "core" / "version.py").is_file())
            self.assertEqual(am._versao_instalada(encontrada), "9.9.9")

    def test_pacote_estranho_e_recusado(self):
        with TemporaryDirectory() as tmp:
            with self.assertRaises(RuntimeError):
                am._pasta_raiz_extraida(Path(tmp))


class AtualizacaoTests(unittest.TestCase):
    def _manifesto(self, base: Path, versao: str, pacote: Path, sha: str | None = None) -> Path:
        manifesto = base / "update.json"
        manifesto.write_text(json.dumps({
            "version": versao,
            "package_url": pacote.resolve().as_uri(),
            "sha256": sha if sha is not None else _sha(pacote),
        }), encoding="utf-8")
        return manifesto

    def test_instala_versao_nova_e_preserva_config(self):
        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            app = _app(base / "app", "6.6.0", {"config.json": '{"minha":"chave"}',
                                               "notas/notas.json": '{"itens":[]}'})
            pacote = _pacote(base, "6.6.2", {"actions/qa_dev.py": "# ferramenta\n"})
            manifesto = self._manifesto(base, "6.6.2", pacote)

            codigo = am.atualizar(app, None, manifesto.resolve().as_uri())

            self.assertEqual(codigo, 0)
            self.assertEqual(am._versao_instalada(app), "6.6.2")
            self.assertTrue((app / "actions" / "qa_dev.py").is_file())
            self.assertEqual((app / "config.json").read_text(encoding="utf-8"),
                             '{"minha":"chave"}')
            self.assertTrue((app / "notas" / "notas.json").is_file())

    def test_sha_errado_nao_instala_nada(self):
        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            app = _app(base / "app", "6.6.0")
            pacote = _pacote(base, "6.6.2")
            manifesto = self._manifesto(base, "6.6.2", pacote, sha="0" * 64)

            codigo = am.atualizar(app, None, manifesto.resolve().as_uri())

            self.assertEqual(codigo, 3)
            self.assertEqual(am._versao_instalada(app), "6.6.0")
            self.assertFalse((app / "actions").exists())

    def test_pacote_corrompido_para_antes_de_copiar(self):
        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            app = _app(base / "app", "6.6.0")
            ruim = base / "ruim.zip"
            ruim.write_bytes(b"isto nao e um zip")
            manifesto = base / "update.json"
            manifesto.write_text(json.dumps({
                "version": "6.6.2", "package_url": ruim.resolve().as_uri(),
                "sha256": _sha(ruim)}), encoding="utf-8")

            codigo = am.atualizar(app, None, manifesto.resolve().as_uri())

            self.assertEqual(codigo, 3)
            self.assertEqual(am._versao_instalada(app), "6.6.0")

    def test_mesma_versao_nao_faz_nada(self):
        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            app = _app(base / "app", "6.6.2")
            pacote = _pacote(base, "6.6.2")
            manifesto = self._manifesto(base, "6.6.2", pacote)
            self.assertEqual(am.atualizar(app, None, manifesto.resolve().as_uri()), 0)

    def test_pacote_local_evita_download(self):
        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            app = _app(base / "app", "6.6.0")
            pacote = _pacote(base, "6.6.2")
            manifesto = self._manifesto(base, "6.6.2", pacote)
            codigo = am.atualizar(app, pacote, manifesto.resolve().as_uri())
            self.assertEqual(codigo, 0)
            self.assertEqual(am._versao_instalada(app), "6.6.2")

    def test_registro_de_atualizacao_e_gravado(self):
        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            app = _app(base / "app", "6.6.0")
            pacote = _pacote(base, "6.6.2")
            manifesto = self._manifesto(base, "6.6.2", pacote)
            am.atualizar(app, pacote, manifesto.resolve().as_uri())
            log = (app / "updates" / "atualizacao-manual.log").read_text(encoding="utf-8")
            self.assertIn("6.6.0", log)
            self.assertIn("6.6.2", log)


class DeteccaoTests(unittest.TestCase):
    def test_acha_a_raiz_pela_pasta_do_script(self):
        with TemporaryDirectory() as tmp:
            app = _app(Path(tmp) / "TORVIS", "6.6.2")
            (app / "tools").mkdir()
            self.assertEqual(am._raiz_do_app(), Path.cwd())  # fora do app: usa o cwd

    def test_versao_desconhecida_nao_estoura(self):
        with TemporaryDirectory() as tmp:
            self.assertEqual(am._versao_instalada(Path(tmp)), "desconhecida")


if __name__ == "__main__":
    unittest.main()
