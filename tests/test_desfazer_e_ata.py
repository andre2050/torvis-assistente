"""Desfazer global (sobrevive ao reinício) e ata de reunião (sem microfone)."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import ata_reuniao as ata  # noqa: E402
from core import desfazer_global as dz  # noqa: E402


class DesfazerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        raiz = Path(self.tmp.name)
        self._patches = [
            mock.patch.object(dz, "PASTA", raiz / "cofre"),
            mock.patch.object(dz, "DIARIO", raiz / "diario.jsonl"),
        ]
        for p in self._patches:
            p.start()
        self.arquivo = raiz / "nota.txt"

    def tearDown(self):
        for p in self._patches:
            p.stop()
        self.tmp.cleanup()

    def test_volta_o_conteudo_anterior(self):
        self.arquivo.write_text("original", encoding="utf-8")
        dz.guardar(self.arquivo)
        self.arquivo.write_text("mexido", encoding="utf-8")
        r = dz.desfazer()
        self.assertTrue(r["ok"])
        self.assertEqual(self.arquivo.read_text(encoding="utf-8"), "original")

    def test_apaga_o_que_foi_criado(self):
        dz.guardar(self.arquivo)                  # ainda não existe
        self.arquivo.write_text("novo", encoding="utf-8")
        r = dz.desfazer()
        self.assertTrue(r["ok"])
        self.assertFalse(self.arquivo.exists())

    def test_sobrevive_a_reinicio(self):
        self.arquivo.write_text("antes", encoding="utf-8")
        dz.guardar(self.arquivo)
        self.arquivo.write_text("depois", encoding="utf-8")
        # simula reinício: nada em memória, só o diário em disco
        self.assertTrue(dz.DIARIO.exists())
        r = dz.desfazer()
        self.assertEqual(self.arquivo.read_text(encoding="utf-8"), "antes")
        self.assertEqual(len(r["restaurados"]), 1)

    def test_duas_escritas_voltam_em_ordem_inversa(self):
        self.arquivo.write_text("v1", encoding="utf-8")
        dz.guardar(self.arquivo)
        self.arquivo.write_text("v2", encoding="utf-8")
        dz.guardar(self.arquivo)
        self.arquivo.write_text("v3", encoding="utf-8")
        dz.desfazer()
        self.assertEqual(self.arquivo.read_text(encoding="utf-8"), "v2")
        dz.desfazer()
        self.assertEqual(self.arquivo.read_text(encoding="utf-8"), "v1")

    def test_desfazer_sem_nada_avisa(self):
        self.assertFalse(dz.desfazer()["ok"])

    def test_lote_ja_desfeito_nao_repete(self):
        self.arquivo.write_text("a", encoding="utf-8")
        lote = dz.guardar(self.arquivo)["lote"]
        self.assertTrue(dz.desfazer(lote)["ok"])
        self.assertFalse(dz.desfazer(lote)["ok"])

    def test_arquivo_grande_avisa_em_vez_de_copiar(self):
        with mock.patch.object(dz, "LIMITE_ARQUIVO", 10):
            self.arquivo.write_text("x" * 100, encoding="utf-8")
            registro = dz.guardar(self.arquivo)
        self.assertEqual(registro["tipo"], "grande")
        r = dz.desfazer()
        self.assertTrue(any("grande demais" in f for f in r["falhas"]))


class AtaTest(unittest.TestCase):
    TEXTO = (
        "Ana: Bom dia, vamos revisar o lançamento.\n"
        "Bruno: O banner está pronto, mas falta o texto final.\n"
        "Ana: Ficou decidido que lançamos dia 25.\n"
        "Bruno: Eu envio o texto até sexta.\n"
        "Carla: Vou preparar a apresentação para a diretoria.\n"
    )

    def test_identifica_participantes(self):
        self.assertEqual(ata.falantes(self.TEXTO), ["Ana", "Bruno", "Carla"])

    def test_encontra_decisao_e_tarefa_sem_modelo(self):
        a = ata.ata_sem_modelo(self.TEXTO, "Lançamento")
        self.assertTrue(any("dia 25" in d for d in a["decisoes"]))
        self.assertTrue(any("sexta" in t for t in a["tarefas"]))
        self.assertEqual(a["gerado_por"], "regras")

    def test_markdown_tem_as_secoes(self):
        md = ata.em_markdown(ata.ata_sem_modelo(self.TEXTO, "Lançamento"))
        for secao in ("# Lançamento", "## Decisões", "## Tarefas", "## Transcrição"):
            self.assertIn(secao, md)

    def test_modelo_bom_estrutura_a_ata(self):
        resposta = json.dumps({"resumo": "Lançamento dia 25.", "decisoes": ["dia 25"],
                               "tarefas": [{"quem": "Bruno", "o_que": "texto",
                                            "quando": "sexta"}]})
        a = ata.ata_com_modelo(self.TEXTO, "Lançamento", lambda _p: resposta)
        self.assertEqual(a["gerado_por"], "modelo")
        self.assertEqual(a["tarefas"][0]["quem"], "Bruno")

    def test_modelo_que_quebra_cai_nas_regras(self):
        a = ata.ata_com_modelo(self.TEXTO, "Lançamento", lambda _p: "desculpe, não sei")
        self.assertEqual(a["gerado_por"], "regras")

    def test_gerar_salva_o_arquivo(self):
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.object(ata, "ARQUIVO_INDICE", Path(d) / "indice.json"):
                r = ata.gerar(self.TEXTO, "Lançamento", pasta=Path(d))
                self.assertTrue(Path(r["arquivo"]).exists())
                self.assertGreaterEqual(r["tarefas"], 1)
                self.assertEqual(ata.ultimas()[0]["titulo"], "Lançamento")

    def test_transcricao_vazia_avisa(self):
        with self.assertRaises(ValueError):
            ata.gerar("   ")


class FerramentaAtaTest(unittest.TestCase):
    def test_sem_audio_nem_transcricao_avisa(self):
        from actions import ata_reuniao as acao
        r = json.loads(acao.ata_reuniao({"action": "gerar"}))
        self.assertFalse(r["ok"])

    def test_gera_por_transcricao(self):
        from actions import ata_reuniao as acao
        with tempfile.TemporaryDirectory() as d, \
             mock.patch.object(ata, "ARQUIVO_INDICE", Path(d) / "indice.json"):
            r = json.loads(acao.ata_reuniao({"transcricao": AtaTest.TEXTO,
                                             "titulo": "Teste", "pasta": d,
                                             "usar_modelo": False}))
        self.assertTrue(r["ok"])
        self.assertIn("participantes", r)


if __name__ == "__main__":
    unittest.main()
