"""Testes das quatro promessas: cache de boot, disjuntor, memória e tarefa de HUD."""
from __future__ import annotations

import sys
import tempfile
import time
import unittest
from pathlib import Path

from core import boot_cache, circuit, hud_task


class CacheDeBootTests(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        (self.dir / "userdata").mkdir()
        self.acoes = self.dir / "actions"
        self.acoes.mkdir()
        (self.acoes / "uma.py").write_text(
            'TOOL = {"name": "uma", "description": "primeira", '
            '"parameters": {"type": "OBJECT", "properties": {}}, '
            '"handler": lambda p=None, **_c: "feito"}\n', encoding="utf-8")

    def test_manifesto_vazio_no_primeiro_boot(self):
        self.assertEqual(boot_cache.carregar(self.dir / "userdata"), {})

    def test_assinatura_muda_quando_o_arquivo_muda(self):
        alvo = self.acoes / "uma.py"
        antes = boot_cache.assinatura(alvo)
        time.sleep(0.01)
        alvo.write_text(alvo.read_text(encoding="utf-8") + "\n# mudou\n", encoding="utf-8")
        self.assertNotEqual(antes, boot_cache.assinatura(alvo))

    def test_grava_e_rele_o_manifesto(self):
        alvo = self.acoes / "uma.py"
        entrada = {"sig": boot_cache.assinatura(alvo), "nome": "uma",
                   "descricao": "primeira", "parametros": {"type": "OBJECT"}}
        boot_cache.gravar(self.dir / "userdata", {"uma.py": entrada})
        lido = boot_cache.carregar(self.dir / "userdata")
        self.assertIn("uma.py", lido)
        self.assertTrue(boot_cache.confere(alvo, lido["uma.py"]))

    def test_arquivo_apagado_invalida_o_cache(self):
        alvo = self.acoes / "two.py"
        alvo.write_text("TOOL = {}\n", encoding="utf-8")
        entrada = {"sig": boot_cache.assinatura(alvo), "nome": "two",
                   "descricao": "x", "parametros": {"type": "OBJECT"}}
        alvo.unlink()
        self.assertFalse(boot_cache.confere(alvo, entrada))

    def test_manifesto_de_versao_antiga_e_ignorado(self):
        caminho = boot_cache.caminho_do_cache(self.dir / "userdata")
        caminho.parent.mkdir(parents=True, exist_ok=True)
        caminho.write_text('{"versao": 1, "arquivos": {"a.py": {}}}', encoding="utf-8")
        self.assertEqual(boot_cache.carregar(self.dir / "userdata"), {})

    def test_caminho_rapido_nao_importa_a_acao(self):
        from core.action_loader import discover_actions
        _ = discover_actions(self.acoes, logger=lambda m: None)   # primeiro boot
        sys.modules.pop("actions.uma", None)
        reg = discover_actions(self.acoes, logger=lambda m: None)  # segundo boot
        self.assertIn("uma", reg.names())
        self.assertNotIn("actions.uma", sys.modules)               # não importou
        self.assertEqual(reg.run("uma", {}), "feito")               # importa ao chamar
        self.assertIn("actions.uma", sys.modules)


class DisjuntorTests(unittest.TestCase):
    def test_abre_depois_de_tres_falhas(self):
        d = circuit.Disjuntor("teste-a", limiar=3, espera=60)
        for _ in range(2):
            self.assertFalse(d.falhou("erro"))
        self.assertTrue(d.falhou("erro"))
        self.assertFalse(d.permitir())
        self.assertTrue(d.estado()["aberto"])

    def test_volta_a_permitir_depois_da_espera(self):
        d = circuit.Disjuntor("teste-b", limiar=1, espera=30)
        agora = 1_000.0
        d.falhou("cota", agora=agora)
        self.assertFalse(d.permitir(agora=agora + 1))
        self.assertTrue(d.permitir(agora=agora + 31))

    def test_sucesso_fecha(self):
        d = circuit.Disjuntor("teste-c", limiar=1, espera=60)
        d.falhou("erro")
        d.funcionou()
        self.assertTrue(d.permitir())
        self.assertEqual(d.estado()["falhas"], 0)

    def test_espera_cresce_a_cada_abertura(self):
        d = circuit.Disjuntor("teste-d", limiar=1, espera=10)
        d.falhou("1", agora=0)
        primeira = d.estado()["aberto_ate"]
        d.falhou("2", agora=primeira + 1)
        self.assertGreater(d.estado()["aberto_ate"], primeira)

    def test_tentar_em_ordem_cai_para_o_segundo(self):
        def quebrado():
            raise RuntimeError("fora do ar")
        escolhidos = []
        nome, valor = circuit.tentar_em_ordem(
            [("principal", quebrado), ("reserva", lambda: "ok")],
            ao_escolher=escolhidos.append)
        self.assertEqual((nome, valor), ("reserva", "ok"))
        self.assertEqual(escolhidos, ["principal", "reserva"])

    def test_todos_falhando_explica_cada_um(self):
        with self.assertRaises(RuntimeError) as ctx:
            circuit.tentar_em_ordem([("a", lambda: 1/0), ("b", lambda: (_ for _ in ()).throw(ValueError("x")))])
        self.assertIn("todos os provedores falharam", str(ctx.exception))
        self.assertIn("a:", str(ctx.exception))

    def test_nunca_devolve_lista_vazia(self):
        self.assertEqual(circuit.permitidos(["x", "y"]), ["x", "y"])


class MemoriaTestes(unittest.TestCase):
    def test_grava_e_entrega_no_prazo(self):
        from memory.cognitive_memory import MemoriaCognitiva, descarregar_memoria
        dir = Path(tempfile.mkdtemp()) / "memoria.json"
        mem = MemoriaCognitiva(dir)
        mem.lembrar("o usuário prefere respostas curtas", categoria="preferencias")
        self.assertTrue(descarregar_memoria(3.0))
        self.assertTrue(dir.exists())
        self.assertIn("respostas curtas", dir.read_text(encoding="utf-8"))


class TarefaHudTestes(unittest.TestCase):
    def test_roda_fora_e_entrega_o_resultado(self):
        recebido = []
        tarefa = hud_task.rodar(lambda: 2 + 2, nome="conta", ao_terminar=recebido.append)
        self.assertIsInstance(tarefa, hud_task.TarefaHud)
        for _ in range(100):
            if recebido:
                break
            time.sleep(0.02)
        self.assertEqual(recebido, [4])

    def test_erro_vai_para_o_tratador(self):
        erros = []
        hud_task.rodar(lambda: 1/0, nome="divide", ao_falhar=erros.append)
        for _ in range(100):
            if erros:
                break
            time.sleep(0.02)
        self.assertTrue(erros)
        self.assertIsInstance(erros[0], ZeroDivisionError)

    def test_interface_nao_espera(self):
        inicio = time.time()
        hud_task.rodar(lambda: time.sleep(0.3), nome="lenta")
        self.assertLess(time.time() - inicio, 0.2)


if __name__ == "__main__":
    unittest.main()
