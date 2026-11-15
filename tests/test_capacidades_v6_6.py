"""Capacidades novas da v6.6.0.

Além do caminho feliz, estes testes protegem o que pode machucar:
  - a calculadora não executa código (`__import__` vira erro, não execução);
  - nota não some quando duas gravações chegam juntas (trava do JsonStore);
  - arquivo de dados ilegível é preservado, nunca apagado em silêncio;
  - sem configuração, e-mail/casa/música explicam o que falta em vez de quebrar;
  - senha e token nunca aparecem na resposta.
"""
import sys
import threading
import unittest
import urllib.error
from email.message import EmailMessage
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from core import userdata as ud                                  # noqa: E402
from core.userdata import JsonStore                              # noqa: E402
from actions import (daily_tools, clock_info, quick_notes, task_list,   # noqa: E402
                     market_quotes, music_player, email_reader, smart_home)


def _store_temporario(modulo, arquivo):
    """Aponta o armazenamento do módulo para uma pasta temporária."""
    pasta = TemporaryDirectory()
    dir_antigo = ud.USERDATA_DIR
    ud.USERDATA_DIR = Path(pasta.name)
    store_antigo = getattr(modulo, "_STORE")
    modulo._STORE = JsonStore(arquivo)
    return pasta, dir_antigo, store_antigo


class CalculadoraTests(unittest.TestCase):
    def test_contas_basicas(self):
        self.assertIn("87", daily_tools.calcular("12*7+3"))
        self.assertIn("12", daily_tools.calcular("sqrt(144)"))
        self.assertIn("3,142", daily_tools.calcular("round(pi, 3)"))

    def test_virgula_decimal_brasileira(self):
        self.assertIn("4", daily_tools.calcular("0,5*8"))
        self.assertIn("10", daily_tools.calcular("5,5+4,5"))

    def test_porcentagem_falada(self):
        self.assertIn("70", daily_tools.calcular("20% de 350"))

    def test_nao_executa_codigo(self):
        for perigo in ("__import__('os').system('echo oi')",
                       "open('/etc/passwd').read()",
                       "[x for x in range(3)]",
                       "exec('1')"):
            self.assertIn("Não consegui", daily_tools.calcular(perigo), perigo)

    def test_divisao_por_zero_explica(self):
        self.assertIn("dividir por zero", daily_tools.calcular("10/0"))


class ConversorTests(unittest.TestCase):
    def test_comprimento_e_massa(self):
        self.assertIn("6,2137", daily_tools.converter(10, "km", "milhas"))
        self.assertIn("2,2046", daily_tools.converter(1, "kg", "libras"))

    def test_temperatura(self):
        self.assertIn("212", daily_tools.converter(100, "celsius", "fahrenheit"))
        self.assertIn("0", daily_tools.converter(32, "f", "c"))

    def test_familias_diferentes_nao_inventam(self):
        self.assertIn("Ainda não sei", daily_tools.converter(3, "km", "segundos"))

    def test_valor_invalido(self):
        self.assertIn("número", daily_tools.converter("abc", "km", "m"))


class SenhaTests(unittest.TestCase):
    def test_tamanho_e_grupos(self):
        senha = daily_tools.gerar_senha(20)
        self.assertEqual(len(senha), 20)
        self.assertTrue(any(c.isdigit() for c in senha))
        self.assertTrue(any(c.isupper() for c in senha))
        self.assertTrue(any(not c.isalnum() for c in senha))

    def test_limites_de_tamanho(self):
        self.assertEqual(len(daily_tools.gerar_senha(2)), 8)
        self.assertEqual(len(daily_tools.gerar_senha(500)), 128)

    def test_sem_simbolos_quando_pedido(self):
        senha = daily_tools.gerar_senha(16, simbolos=False, numeros=False)
        self.assertTrue(senha.isalpha())


class RelogioTests(unittest.TestCase):
    def test_hora_data_e_dia(self):
        self.assertIn("Agora são", clock_info.clock_action({"action": "hora"}))
        self.assertIn("Hoje é", clock_info.clock_action({"action": "data"}))
        self.assertIn("São", clock_info.clock_action({"action": "agora"}))
        self.assertIn("fuso" if False else "UTC", clock_info.clock_action({"action": "fuso"}))

    def test_cidade_conhecida_e_desconhecida(self):
        self.assertIn("Agora são", clock_info.clock_action({"action": "hora", "city": "Lisboa"}))
        self.assertIn("Não conheço o fuso",
                      clock_info.clock_action({"action": "hora", "city": "Marte"}))


class NotasETarefasTests(unittest.TestCase):
    def setUp(self):
        self.pasta_notas, self.dir_n, self.store_n = _store_temporario(quick_notes, "notas.json")
        self.pasta_tarefas, self.dir_t, self.store_t = _store_temporario(task_list, "tarefas.json")

    def tearDown(self):
        quick_notes._STORE = self.store_n
        task_list._STORE = self.store_t
        ud.USERDATA_DIR = self.dir_n
        self.pasta_notas.cleanup()
        self.pasta_tarefas.cleanup()

    def test_nota_vai_e_volta(self):
        self.assertIn("Nota 1", quick_notes.adicionar("pedreiro vem terça"))
        self.assertIn("pedreiro", quick_notes.listar())
        self.assertIn("terça", quick_notes.ler("1"))
        self.assertIn("apagada", quick_notes.apagar("1"))
        self.assertIn("não tem notas", quick_notes.listar())

    def test_busca_ignora_acento(self):
        quick_notes.adicionar("reunião com o José")
        self.assertIn("1 nota", quick_notes.buscar("reuniao"))

    def test_referencia_ambigua_pede_numero(self):
        quick_notes.adicionar("café da manhã")
        quick_notes.adicionar("café da tarde")
        self.assertIn("me diga o número", quick_notes.apagar("café"))

    def test_gravacoes_simultaneas_nao_somem(self):
        def escrever(indice):
            quick_notes.adicionar(f"nota {indice}")

        fios = [threading.Thread(target=escrever, args=(i,)) for i in range(20)]
        for fio in fios:
            fio.start()
        for fio in fios:
            fio.join()
        self.assertEqual(len(quick_notes._STORE.ler()["itens"]), 20)

    def test_tarefa_concluida_e_projetos(self):
        task_list.adicionar("finalizar relatório", "Capstone", "alta")
        task_list.adicionar("comprar café")
        self.assertIn("finalizar relatório", task_list.listar())
        self.assertIn("Capstone", task_list.projetos())
        self.assertIn("concluída", task_list.concluir("2"))
        self.assertIn("1 tarefa", task_list.listar())
        self.assertIn("removidas", task_list.limpar_concluidas())

    def test_prioridade_invalida_vira_normal(self):
        task_list.adicionar("tarefa qualquer", "", "urgentíssima")
        self.assertEqual(task_list._STORE.ler()["itens"][0]["prioridade"], "normal")


class ArmazenamentoTests(unittest.TestCase):
    def test_grava_e_preserva_corrompido(self):
        with TemporaryDirectory() as tmp:
            antigo = ud.USERDATA_DIR
            ud.USERDATA_DIR = Path(tmp)
            try:
                store = JsonStore("x.json")
                store.escrever({"itens": [{"id": 1, "texto": "oi"}], "proximo_id": 2})
                self.assertEqual(len(store.ler()["itens"]), 1)
                store.caminho.write_text("{ isto não é json", encoding="utf-8")
                self.assertEqual(store.ler()["itens"], [])
                self.assertTrue(list(Path(tmp).glob("x.corrompido-*.json")),
                                "o arquivo ilegível deveria ser preservado")
            finally:
                ud.USERDATA_DIR = antigo


class CotacoesTests(unittest.TestCase):
    def setUp(self):
        market_quotes._cache.clear()

    def test_formata_moedas(self):
        dados = {"USDBRL": {"name": "Dólar Americano/Real Brasileiro", "bid": "5.6666",
                            "pctChange": "0.437795", "create_date": "2026-11-15 10:00:00"}}
        with mock.patch.object(market_quotes, "_buscar", return_value=dados):
            saida = market_quotes.market_quotes_action({"action": "cotacao", "currencies": ["USD"]})
        self.assertIn("R$ 5,67", saida)
        self.assertIn("0,44%", saida)

    def test_acao_da_bolsa(self):
        dados = {"results": [{"symbol": "PETR4", "longName": "Petrobras",
                              "regularMarketPrice": 45.3,
                              "regularMarketChangePercent": 1.335}]}
        with mock.patch.object(market_quotes, "_buscar", return_value=dados):
            saida = market_quotes.market_quotes_action({"action": "acao", "ticker": "petr4"})
        self.assertIn("PETR4", saida)
        self.assertIn("45,30", saida)

    def test_cache_evita_requisicao_repetida(self):
        with mock.patch.object(market_quotes.urllib.request, "urlopen") as abrir:
            abrir.return_value.__enter__.return_value.read.return_value = b'{"USDBRL": {}}'
            market_quotes._cache.clear()
            market_quotes._buscar("https://exemplo/1")
            market_quotes._buscar("https://exemplo/1")
        self.assertEqual(abrir.call_count, 1, "a segunda consulta deveria vir do cache")

    def test_fonte_pedindo_chave_nao_vira_erro_generico(self):
        erro = urllib.error.HTTPError("https://exemplo", 401, "Unauthorized", {}, None)
        with mock.patch.object(market_quotes, "_buscar", side_effect=erro):
            saida = market_quotes.market_quotes_action({"action": "acao", "ticker": "PETR4"})
        self.assertIn("autenticação", saida)


class MusicaTests(unittest.TestCase):
    def test_encontra_por_trecho_sem_acento(self):
        with TemporaryDirectory() as tmp:
            pasta = Path(tmp)
            (pasta / "Djavan - Flor de Lis.mp3").write_bytes(b"x")
            (pasta / "Outra Cancao.mp3").write_bytes(b"x")
            (pasta / "leiame.txt").write_text("nao e musica", encoding="utf-8")
            with mock.patch.object(music_player, "_pastas_candidatas", return_value=[pasta]), \
                 mock.patch.object(music_player, "_abrir") as abrir:
                saida = music_player.music_action({"action": "tocar", "query": "flor de lis"})
        abrir.assert_called_once()
        self.assertIn("Flor de Lis", saida)

    def test_pasta_toca_primeira_faixa(self):
        with TemporaryDirectory() as tmp:
            pasta = Path(tmp)
            (pasta / "a.mp3").write_bytes(b"x")
            (pasta / "b.mp3").write_bytes(b"x")
            with mock.patch.object(music_player, "_abrir") as abrir:
                saida = music_player.music_action({"action": "tocar", "folder": str(pasta)})
        abrir.assert_called_once()
        self.assertIn("2 na pasta", saida)

    def test_sem_pasta_explica(self):
        with mock.patch.object(music_player, "_pastas_candidatas", return_value=[]):
            saida = music_player.music_action({"action": "tocar", "query": "djavan"})
        self.assertIn("pasta de músicas", saida)


class FakeIMAP:
    """Servidor IMAP falso, com um cabeçalho de e-mail só."""

    def __init__(self, cabecalho):
        self.cabecalho = cabecalho
        self.encerrado = False

    def select(self, *_a, **_k):
        return "OK", [b"1"]

    def search(self, *_a, **_k):
        return "OK", [b"1"]

    def fetch(self, _numero, _o_que):
        return "OK", [(b"1 (RFC822.HEADER)", self.cabecalho)]

    def logout(self):
        self.encerrado = True
        return "BYE", []


class EmailTests(unittest.TestCase):
    def test_sem_configuracao_explica(self):
        with mock.patch.object(email_reader, "_credenciais",
                               return_value=(None, None, "Configure 'email_address'.")):
            self.assertIn("email_address", email_reader.email_action({"action": "checar"}))

    def test_checa_nao_lidas_sem_vazar_senha(self):
        mensagem = EmailMessage()
        mensagem["From"] = "Ana <ana@exemplo.com>"
        mensagem["Subject"] = "Proposta de orçamento"
        mensagem["Date"] = "Sun, 15 Nov 2026 10:00:00 -0300"
        falso = FakeIMAP(mensagem.as_bytes())
        with mock.patch.object(email_reader, "_credenciais",
                               return_value=("eu@exemplo.com", "segredo-do-app", "imap.exemplo.com")), \
             mock.patch.object(email_reader, "_conectar", return_value=falso):
            saida = email_reader.checar()
        self.assertIn("Ana", saida)
        self.assertIn("Proposta", saida)
        self.assertNotIn("segredo-do-app", saida)
        self.assertTrue(falso.encerrado, "a conexão precisa ser fechada")


class CasaTests(unittest.TestCase):
    def setUp(self):
        smart_home._ultimo_estado.clear()

    @staticmethod
    def _estados():
        return [
            {"entity_id": "light.sala", "state": "off",
             "attributes": {"friendly_name": "Luz da sala"}},
            {"entity_id": "light.quarto", "state": "on",
             "attributes": {"friendly_name": "Luz do quarto", "brightness": 127}},
            {"entity_id": "sensor.temp", "state": "23",
             "attributes": {"friendly_name": "Temperatura"}},
        ]

    def test_sem_configuracao_explica(self):
        with mock.patch.object(smart_home, "_credenciais",
                               return_value=(None, "Configure 'home_assistant_url'.")):
            self.assertIn("home_assistant_url",
                          smart_home.smart_home_action({"action": "listar"}))

    def test_lista_ignora_sensores(self):
        with mock.patch.object(smart_home, "_pedir", return_value=self._estados()), \
             mock.patch.object(smart_home, "_base", return_value=("http://ha", "tok")):
            saida = smart_home.listar()
        self.assertIn("Luz da sala", saida)
        self.assertNotIn("Temperatura", saida)
        self.assertIn("50%", saida)

    def test_liga_e_desliga_no_servico_certo(self):
        with mock.patch.object(smart_home, "_pedir", return_value=self._estados()) as pedir, \
             mock.patch.object(smart_home, "_base", return_value=("http://ha", "tok")):
            smart_home.listar()
            self.assertIn("ligado", smart_home.ligar("luz da sala"))
            self.assertIn("desligado", smart_home.desligar("luz da sala"))
        urls = [c[0][0] for c in pedir.call_args_list if c[0] and isinstance(c[0][0], str)]
        self.assertTrue(any("light/turn_on" in u for u in urls))
        self.assertTrue(any("light/turn_off" in u for u in urls))

    def test_nome_ambiguo_pede_detalhe(self):
        with mock.patch.object(smart_home, "_pedir", return_value=self._estados()), \
             mock.patch.object(smart_home, "_base", return_value=("http://ha", "tok")):
            smart_home.listar()
            self.assertIn("Mais de um", smart_home.ligar("luz"))

    def test_ajuste_de_brilho(self):
        with mock.patch.object(smart_home, "_pedir", return_value=self._estados()), \
             mock.patch.object(smart_home, "_base", return_value=("http://ha", "tok")):
            smart_home.listar()
            self.assertIn("ajustado", smart_home.definir("luz do quarto", brilho=30))

    def test_token_nao_aparece_na_resposta(self):
        with mock.patch.object(smart_home, "_pedir", return_value=self._estados()), \
             mock.patch.object(smart_home, "_base", return_value=("http://ha", "TOKEN-SECRETO")):
            saida = smart_home.smart_home_action({"action": "listar"})
        self.assertNotIn("TOKEN-SECRETO", saida)


if __name__ == "__main__":
    unittest.main()
