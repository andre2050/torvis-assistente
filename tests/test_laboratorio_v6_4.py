"""Conjunto de ajuste fino e relatório do capstone: o que sai, e o que não sai."""
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from core import capstone, finetuning


def _memoria_longa() -> dict:
    return {
        "identity": {"nome": {"value": "André Luiz Lima Menezes"}},
        "preferences": {
            "tom": {"value": "respostas curtas, sem despedida"},
            "contato": {"value": "andre@exemplo.com e (11) 98765-4321"},
        },
        "projects": {"torvis": {"value": "assistente em PyQt6"}},
        "sessions": [{"date": "2026-11-14", "summary": "Ajustamos a atualização automática."}],
    }


class SaneamentoTests(unittest.TestCase):
    def test_mascara_email_telefone_e_chave(self):
        texto = ("mail andre@exemplo.com fone (11) 98765-4321 "
                 "chave AIzaSyD1234567890abcdefghijklmnopqrstuv")
        limpo = finetuning.sanear(texto)
        self.assertNotIn("andre@exemplo.com", limpo.texto)
        self.assertNotIn("98765-4321", limpo.texto)
        self.assertNotIn("AIzaSyD", limpo.texto)
        self.assertIn("[email]", limpo.texto)
        self.assertEqual(limpo.mascarados["chave_api"], 1)
        self.assertEqual(limpo.total, 3)

    def test_texto_limpo_nao_muda(self):
        limpo = finetuning.sanear("prefere respostas curtas")
        self.assertEqual(limpo.texto, "prefere respostas curtas")
        self.assertEqual(limpo.total, 0)

    def test_cpf_e_cnpj(self):
        limpo = finetuning.sanear("CPF 123.456.789-01 e CNPJ 12.345.678/0001-90")
        self.assertIn("[cpf]", limpo.texto)
        self.assertIn("[cnpj]", limpo.texto)


class ColetaTests(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.raiz = Path(self._tmp.name)
        (self.raiz / "long_term.json").write_text(
            json.dumps(_memoria_longa(), ensure_ascii=False), encoding="utf-8")
        (self.raiz / "cognitive_memory.json").write_text(json.dumps(
            [{"id": "l1", "conteudo": "Chama o assistente de TORVIS.", "categoria": "identity"}],
            ensure_ascii=False), encoding="utf-8")

    def tearDown(self):
        self._tmp.cleanup()

    def _coletar(self):
        return finetuning.coletar(
            memoria_longa=self.raiz / "long_term.json",
            memoria_cognitiva=self.raiz / "cognitive_memory.json",
            correcoes=self.raiz / "correcoes.jsonl")

    def test_formato_de_cada_exemplo(self):
        exemplos, _ = self._coletar()
        self.assertTrue(exemplos)
        for exemplo in exemplos:
            mensagens = exemplo["messages"]
            self.assertEqual([m["role"] for m in mensagens], ["user", "model"])
            self.assertTrue(mensagens[0]["content"].strip())
            self.assertTrue(mensagens[1]["content"].strip())

    def test_junta_as_tres_fontes(self):
        exemplos, meta = self._coletar()
        origens = meta["relatorio"]["por_origem"]
        self.assertEqual(origens.get("memoria"), 4)      # 3 memórias + 1 sessão? não: ver abaixo
        self.assertEqual(origens.get("cognitiva"), 1)
        self.assertEqual(len(exemplos), meta["relatorio"]["exemplos"])

    def test_ja_sai_mascarado(self):
        _, meta = self._coletar()
        self.assertGreaterEqual(meta["relatorio"]["exemplos_com_mascara"], 1)
        self.assertIn("email", meta["relatorio"]["mascaras"])

    def test_correcao_registrada_entra(self):
        finetuning.registrar_correcao("Como falo com você?",
                                      "Curto e direto, sem 'estou à disposição'.",
                                      caminho=self.raiz / "correcoes.jsonl")
        exemplos, meta = self._coletar()
        self.assertEqual(meta["relatorio"]["por_origem"].get("correcao"), 1)
        self.assertTrue(any("sem 'estou à disposição'" in e["messages"][1]["content"]
                            for e in exemplos))


class ValidacaoTests(unittest.TestCase):
    def _exemplo(self, pergunta: str, resposta: str) -> dict:
        return {"messages": [{"role": "user", "content": pergunta},
                             {"role": "model", "content": resposta}]}

    def test_remove_repetidos(self):
        exemplos = [self._exemplo("oi", "olá") for _ in range(3)]
        resultado = finetuning.validar(exemplos)
        self.assertEqual(resultado["validos"], 1)
        self.assertEqual(resultado["duplicados"], 2)

    def test_recusa_papeis_fora_de_ordem(self):
        mau = {"messages": [{"role": "model", "content": "a"},
                            {"role": "user", "content": "b"}]}
        resultado = finetuning.validar([mau])
        self.assertEqual(resultado["validos"], 0)
        self.assertTrue(resultado["problemas"])

    def test_recusa_vazio_e_longo_demais(self):
        vazio = self._exemplo("", "algo")
        longo = self._exemplo("pergunta", "x" * (finetuning.MAXIMO_CARACTERES + 10))
        resultado = finetuning.validar([vazio, longo])
        self.assertEqual(resultado["vazios"], 1)
        self.assertEqual(resultado["longos"], 1)
        self.assertEqual(resultado["validos"], 0)

    def test_avisa_abaixo_do_minimo(self):
        resultado = finetuning.validar([self._exemplo("a?", "b")], minimo=10)
        self.assertTrue(any("abaixo do mínimo" in a for a in resultado["avisos"]))

    def test_tokens_estimados_crescem_com_o_texto(self):
        pequeno = finetuning.validar([self._exemplo("oi", "olá")])["tokens_estimados"]
        grande = finetuning.validar(
            [self._exemplo("oi", "olá" * 200)])["tokens_estimados"]
        self.assertGreater(grande, pequeno)

    def test_divisao_preserva_todos(self):
        exemplos = [self._exemplo(f"p{i}", f"r{i}") for i in range(10)]
        treino, teste = finetuning.dividir(exemplos, 0.2)
        self.assertEqual(len(treino) + len(teste), 10)
        self.assertEqual(len(teste), 2)


class ExportacaoTests(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.destino = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _exemplos(self, quantidade: int = 5):
        return [{"messages": [{"role": "user", "content": f"pergunta {i}"},
                              {"role": "model", "content": f"resposta {i}"}]}
                for i in range(quantidade)]

    def test_grava_jsonl_valido(self):
        resultado = finetuning.exportar(self._exemplos(), self.destino)
        treino = Path(resultado["arquivos"]["treino"])
        self.assertTrue(treino.is_file())
        for linha in treino.read_text(encoding="utf-8").splitlines():
            dados = json.loads(linha)
            self.assertEqual(list(dados), ["messages"])

    def test_caminho_de_validacao_nao_e_sobrescrito_pelo_resumo(self):
        """A colisão de chave antiga trocava o caminho por um dicionário."""
        resultado = finetuning.exportar(self._exemplos(10), self.destino)
        self.assertIsInstance(resultado["arquivos"]["validacao"], str)
        self.assertTrue(Path(resultado["arquivos"]["validacao"]).is_file())
        self.assertIsInstance(resultado["resumo"]["validacao"], dict)

    def test_resumo_tem_o_que_enviar(self):
        resultado = finetuning.exportar(self._exemplos(), self.destino)
        resumo = json.loads(Path(resultado["arquivos"]["resumo"]).read_text(encoding="utf-8"))
        self.assertIn("como_enviar", resumo)
        self.assertTrue(resumo["como_enviar"])
        self.assertIn("nao adivinha" if False else "adivinha", " ".join(resumo["como_enviar"]))

    def test_conjunto_vazio_nao_grava_lixo(self):
        resultado = finetuning.exportar([], self.destino)
        self.assertEqual(resultado["resumo"]["exemplos_treino"], 0)
        self.assertEqual(resultado["resumo"]["exemplos_validacao"], 0)


class CapstoneTests(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.raiz = Path(self._tmp.name)
        (self.raiz / "core").mkdir()
        (self.raiz / "core" / "a.py").write_text("x = 1\n" * 10, encoding="utf-8")
        (self.raiz / "tests").mkdir()
        (self.raiz / "tests" / "test_a.py").write_text("y = 2\n", encoding="utf-8")
        (self.raiz / "README.md").write_text("# doc\n", encoding="utf-8")
        (self.raiz / "__pycache__").mkdir()
        (self.raiz / "__pycache__" / "lixo.py").write_text("z" * 100, encoding="utf-8")

    def tearDown(self):
        self._tmp.cleanup()

    def test_inventario_conta_o_projeto(self):
        dados = capstone.inventario(self.raiz)
        self.assertEqual(dados["modulos_python"], 2)
        self.assertEqual(dados["arquivos_de_teste"], 1)
        self.assertEqual(dados["documentos"], 1)

    def test_inventario_ignora_pycache(self):
        dados = capstone.inventario(self.raiz)
        self.assertNotIn("__pycache__", dados["pacotes"])

    def test_relatorio_markdown_e_html(self):
        destino = self.raiz / "docs"
        resultado = capstone.gerar(destino, raiz=self.raiz)
        markdown = Path(resultado["markdown"]).read_text(encoding="utf-8")
        html = Path(resultado["html"]).read_text(encoding="utf-8")
        self.assertIn("# ", markdown)
        self.assertIn("| Pacote | Linhas |", markdown)
        self.assertIn("<!doctype html>", html.lower())
        self.assertIn("Limitações", markdown)

    def test_relatorio_nao_inventa_numero(self):
        destino = self.raiz / "docs"
        resultado = capstone.gerar(destino, raiz=self.raiz)
        markdown = Path(resultado["markdown"]).read_text(encoding="utf-8")
        self.assertIn("Módulos Python | 2", markdown)
        self.assertIn("Arquivos de teste | 1", markdown)

    def test_roteiro_tem_dez_topicos(self):
        destino = self.raiz / "docs"
        resultado = capstone.gerar_roteiro(destino, raiz=self.raiz)
        self.assertEqual(resultado["slides"], 10)
        texto = Path(resultado["roteiro"]).read_text(encoding="utf-8")
        self.assertEqual(texto.count("## "), 10)


if __name__ == "__main__":
    unittest.main()
