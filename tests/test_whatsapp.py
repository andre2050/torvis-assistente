"""Testes da secretária de WhatsApp.

Nada aqui fala com a Meta: o modo ensaio monta a requisição e devolve o que
seria enviado. O que se prova é o comportamento — quem é atendido, quando fica
calado, o que acontece com nota de voz e com ligação perdida.
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path

from core import whatsapp as wa


def cfg(**mudancas):
    base = wa.config_inicial()
    base.update({"token": "token-de-teste", "numero_id": "123456789", "ligada": True,
                 "permitidos": [], "silencioso_inicio": 23, "silencioso_fim": 7})
    base.update(mudancas)
    return base


class EnvioTests(unittest.TestCase):
    def test_texto_vai_para_o_numero_certo(self):
        s = wa.SecretariaWhatsApp(cfg(), ensaio=True)
        s.enviar_texto("+55 (85) 99999-1234", "oi")
        enviado = s.enviados[-1]
        self.assertEqual(enviado["tipo"], "texto")
        self.assertEqual(enviado["para"], "+55 (85) 99999-1234")

    def test_numero_e_limpo_de_pontuacao(self):
        self.assertEqual(wa.so_digitos("+55 (85) 99999-1234"), "5585999991234")

    def test_sem_token_nao_engana(self):
        s = wa.SecretariaWhatsApp(cfg(token=""), ensaio=False)
        with self.assertRaises(wa.SecretariaIndisponivel):
            s.enviar_texto("5585999991234", "oi")

    def test_audio_precisa_de_formato_aceito(self):
        s = wa.SecretariaWhatsApp(cfg(), ensaio=True)
        ruim = Path("/tmp/torvis-teste.xyz")
        ruim.write_bytes(b"nada")
        with self.assertRaises(ValueError):
            s.enviar_audio("5585999991234", ruim)

    def test_audio_mp3_sobe_e_envia(self):
        s = wa.SecretariaWhatsApp(cfg(), ensaio=True)
        arq = Path("/tmp/torvis-teste.mp3")
        arq.write_bytes(b"ID3" + b"\x00" * 200)
        s.enviar_audio("5585999991234", arq)
        self.assertEqual(s.enviados[-1]["tipo"], "audio")

    def test_audio_grande_e_recusado(self):
        s = wa.SecretariaWhatsApp(cfg(), ensaio=True)
        arq = Path("/tmp/torvis-grande.mp3")
        arq.write_bytes(b"x" * (17 * 1024 * 1024))
        with self.assertRaises(ValueError):
            s.enviar_audio("5585999991234", arq)


class QuemEhAtendidoTests(unittest.TestCase):
    def test_lista_de_permitidos_bloqueia_desconhecido(self):
        s = wa.SecretariaWhatsApp(cfg(permitidos=["5585999991234"]), ensaio=True)
        self.assertTrue(s.permitido("5585999991234"))
        self.assertFalse(s.permitido("5511999998888"))
        self.assertEqual(s.deve_responder("5511999998888", hora=12)[1], "número fora da lista de permitidos")

    def test_horario_silencioso_atravessa_a_meia_noite(self):
        self.assertTrue(wa.dentro_do_silencio(cfg(), hora=23))
        self.assertTrue(wa.dentro_do_silencio(cfg(), hora=2))
        self.assertTrue(wa.dentro_do_silencio(cfg(), hora=6))
        self.assertFalse(wa.dentro_do_silencio(cfg(), hora=12))

    def test_janela_diurna_tambem_funciona(self):
        c = cfg(silencioso_inicio=9, silencioso_fim=18)
        self.assertTrue(wa.dentro_do_silencio(c, hora=10))
        self.assertFalse(wa.dentro_do_silencio(c, hora=20))

    def test_desligada_nao_responde(self):
        s = wa.SecretariaWhatsApp(cfg(ligada=False), ensaio=True)
        self.assertEqual(s.deve_responder("5585999991234", hora=12)[1], "secretária desligada")


class ConversaTests(unittest.TestCase):
    def test_texto_recebe_resposta_em_texto(self):
        s = wa.SecretariaWhatsApp(cfg(responder_audio=False), ensaio=True)
        r = s.responder_mensagem(wa.Mensagem(de="5585999991234", texto="que horas são?"),
                                 lambda p: f"sobre: {p}")
        self.assertTrue(r["ok"])
        self.assertEqual(r["resposta"], "sobre: que horas são?")

    def test_nota_de_voz_e_transcrita_antes_de_responder(self):
        visto = {}

        def transcritor(audio, sufixo):
            visto["audio"] = audio
            return "marca reunião amanhã"

        s = wa.SecretariaWhatsApp(cfg(responder_audio=False), ensaio=True, transcritor=transcritor)
        s.baixar_midia = lambda mid: b"OGG-DADOS"       # não chama a Meta
        r = s.responder_mensagem(wa.Mensagem(de="5585999991234", tipo="audio", media_id="m1"),
                                 lambda p: f"entendi: {p}")
        self.assertTrue(r["ok"])
        self.assertEqual(r["pergunta"], "marca reunião amanhã")
        self.assertEqual(visto["audio"], b"OGG-DADOS")

    def test_audio_ruim_nao_derruba_a_secretaria(self):
        def transcritor(audio, sufixo):
            raise RuntimeError("formato estranho")

        s = wa.SecretariaWhatsApp(cfg(), ensaio=True, transcritor=transcritor)
        s.baixar_midia = lambda mid: b"x"
        r = s.responder_mensagem(wa.Mensagem(de="5585999991234", tipo="audio", media_id="m1"),
                                 lambda p: "nunca chamado")
        self.assertFalse(r["ok"])
        self.assertIn("não entendi o áudio", r["motivo"])

    def test_resposta_tambem_vai_em_audio(self):
        s = wa.SecretariaWhatsApp(cfg(responder_audio=True), ensaio=True)
        r = s.responder_mensagem(wa.Mensagem(de="5585999991234", texto="bom dia"),
                                 lambda p: "bom dia, senhor",
                                 falar=lambda texto: b"ID3" + b"\x00" * 100)
        self.assertTrue(r["ok"])
        tipos = [e["tipo"] for e in s.enviados]
        self.assertEqual(tipos, ["texto", "audio"])

    def test_silencio_nao_responde_mas_nao_quebra(self):
        s = wa.SecretariaWhatsApp(cfg(), ensaio=True)
        r = s.responder_mensagem(wa.Mensagem(de="5585999991234", texto="oi"), lambda p: "oi", hora=2)
        self.assertFalse(r["ok"])
        self.assertEqual(s.enviados, [])


class ChamadaTests(unittest.TestCase):
    def test_chamada_perdida_recebe_recado(self):
        s = wa.SecretariaWhatsApp(cfg(silencioso_inicio=0, silencioso_fim=0), ensaio=True)
        r = s.avisar_chamada_perdida("5585999991234", nome="André")
        self.assertTrue(r["ok"])
        self.assertTrue(r["resposta"].startswith("André, não consigo falar agora"))
        self.assertEqual(s.enviados[-1]["tipo"], "texto")

    def test_chamada_de_quem_esta_fora_da_lista_nao_recebe_nada(self):
        s = wa.SecretariaWhatsApp(cfg(permitidos=["5511999998888"], silencioso_inicio=0, silencioso_fim=0),
                                  ensaio=True)
        r = s.avisar_chamada_perdida("5585999991234")
        self.assertFalse(r["ok"])
        self.assertEqual(s.enviados, [])


class WebhookTests(unittest.TestCase):
    def test_leitura_de_mensagem_e_de_chamada(self):
        corpo = {"entry": [{"changes": [{"value": {
            "contacts": [{"wa_id": "5585999991234", "profile": {"name": "André"}}],
            "messages": [{"from": "5585999991234", "type": "text", "text": {"body": "oi"}},
                         {"from": "5585999991234", "type": "audio", "audio": {"id": "mid123"}}],
            "calls": [{"from": "5585999991234", "event": "missed"}],
        }}]}]}
        eventos = wa.ler_webhook(corpo)
        self.assertEqual([e["tipo"] for e in eventos], ["mensagem", "mensagem", "chamada"])
        self.assertEqual(eventos[0]["texto"], "oi")
        self.assertEqual(eventos[0]["nome"], "André")
        self.assertEqual(eventos[1]["media_id"], "mid123")
        self.assertEqual(eventos[1]["tipo_midia"], "audio")
        self.assertEqual(eventos[2]["estado"], "missed")

    def test_webhook_vazio_não_quebra(self):
        self.assertEqual(wa.ler_webhook({}), [])
        self.assertEqual(wa.ler_webhook(None), [])


class ConfigTests(unittest.TestCase):
    def test_config_padrao_e_util(self):
        c = wa.config_inicial()
        self.assertFalse(c["ligada"])
        self.assertTrue(c["responder_audio"])
        self.assertEqual(c["permitidos"], [])
        self.assertTrue(c["recado"])


if __name__ == "__main__":
    unittest.main()

class RegistroTests(unittest.TestCase):
    """A ferramenta precisa entrar como core, senão é descartada na hora de
    montar a lista que vai para o modelo e o usuário 'não vê' a secretária."""

    def test_metadados_reconhecidos_pelo_carregador(self):
        from core import action_loader as al
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "whatsapp_secretary", "actions/whatsapp_secretary.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        r = al._validate(mod, "whatsapp_secretary.py")
        self.assertTrue(r.valid, r.error)
        self.assertEqual(r.tier, "core")
        self.assertEqual(r.behavior, "NON_BLOCKING")
        self.assertTrue(r.brief)
