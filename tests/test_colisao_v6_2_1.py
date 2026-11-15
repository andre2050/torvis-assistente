"""Colisão de maiúsculas: o pacote tem que ser o mesmo arquivo no Linux e no Windows."""
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from core import update_manager as um
from tools.gerar_pacote import colisoes_de_caixa


class ColisaoTests(unittest.TestCase):
    def test_detecta_dois_readmes(self):
        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "README.md").write_text("a", encoding="utf-8")
            (base / "readme.md").write_text("b", encoding="utf-8")
            (base / "main.py").write_text("c", encoding="utf-8")
            achados = colisoes_de_caixa(sorted(base.iterdir()), base)
        self.assertIn("readme.md", achados)
        self.assertEqual(len(achados["readme.md"]), 2)

    def test_sem_colisao_quando_nomes_diferem(self):
        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "README.md").write_text("a", encoding="utf-8")
            (base / "README_PROJETO.md").write_text("b", encoding="utf-8")
            self.assertEqual(colisoes_de_caixa(sorted(base.iterdir()), base), {})

    def test_projeto_atual_nao_tem_colisao(self):
        raiz = Path(__file__).resolve().parent.parent
        arquivos = [p for p in raiz.rglob("*")
                    if p.is_file() and "__pycache__" not in p.parts
                    and not p.name.endswith((".pyc", ".log"))]
        self.assertEqual(colisoes_de_caixa(arquivos, raiz), {},
                         "o projeto precisa ter nomes únicos sem distinguir maiúsculas")

    def test_verificador_aponta_colisao_e_nao_falta(self):
        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "README.md").write_text("conteudo", encoding="utf-8")
            manifesto = {
                "version": "9.9.9", "channel": "stable", "format": 1,
                "files": {
                    "README.md": um._sha256(base / "README.md"),
                    "readme.md": um._sha256(base / "README.md"),
                },
            }
            (base / "update-manifest.json").write_text(json.dumps(manifesto), encoding="utf-8")
            with self.assertRaises(ValueError) as ctx:
                um.verify_package(base)
        self.assertIn("case-collision", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
