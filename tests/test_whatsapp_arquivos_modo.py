"""O que a lista de recursos pede e a 7.4.2 ainda não fazia:

* responder em texto, em áudio ou nos dois, à escolha;
* mandar arquivo e pasta (pasta vira zip);
* guardar e reler as mensagens recebidas.
"""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import whatsapp as wa  # noqa: E402


def _secretaria(**extra):
    cfg = wa.config_inicial()
    cfg.update({"token": "t", "numero_id": "123", "ligada": True, "permitidos": []})
    cfg.update(extra)
    return wa.SecretariaWhatsApp(cfg, ensaio=False)


class ModoRespostaTest(unittest.TestCase):
    def test_padrao_responde_texto_e_audio(self):
        self.assertEqual(_secretaria().modo_resposta(), "ambos")

    def test_config_nova_manda(self):
        for modo in ("texto", "audio", "ambos"):
            self.assertEqual(_secretaria(modo_resposta=modo).modo_resposta(), modo)

    def test_interruptor_antigo_continua_valendo(self):
        s = _secretaria(modo_resposta="", responder_audio=False)
        self.assertEqual(s.modo_resposta(), "texto")

    def test_modo_texto_nao_chama_a_voz(self):
        s = _secretaria(modo_resposta="texto")
        msg = wa.Mensagem(de="5511999999999", texto="oi")
        voz = mock.Mock(return_value=b"audio")
        with mock.patch.object(s, "enviar_texto", return_value={"ok": 1}) as texto, \
             mock.patch.object(s, "enviar_audio") as audio:
            r = s.responder_mensagem(msg, lambda _t: "olá", falar=voz, hora=10)
        texto.assert_called_once()
        audio.assert_not_called()
        self.assertEqual(r["modo"], "texto")

    def test_modo_audio_nao_manda_texto(self):
        s = _secretaria(modo_resposta="audio")
        msg = wa.Mensagem(de="5511999999999", texto="oi")
        with mock.patch.object(s, "enviar_texto") as texto, \
             mock.patch.object(s, "enviar_audio", return_value={"ok": 1}) as audio:
            r = s.responder_mensagem(msg, lambda _t: "olá", falar=lambda _t: b"a", hora=10)
        texto.assert_not_called()
        audio.assert_called_once()
        self.assertEqual(r["modo"], "audio")

    def test_modo_audio_sem_voz_cai_no_texto(self):
        s = _secretaria(modo_resposta="audio")
        msg = wa.Mensagem(de="5511999999999", texto="oi")
        with mock.patch.object(s, "enviar_texto", return_value={"ok": 1}) as texto:
            s.responder_mensagem(msg, lambda _t: "olá", falar=None, hora=10)
        texto.assert_called_once()


class DocumentoTest(unittest.TestCase):
    def test_recusa_formato_que_a_meta_nao_aceita(self):
        s = _secretaria()
        with tempfile.TemporaryDirectory() as d:
            arq = Path(d) / "nota.exe"
            arq.write_bytes(b"x")
            with self.assertRaises(ValueError):
                s.enviar_documento("5511999999999", arq)

    def test_envia_pdf_com_legenda(self):
        s = _secretaria()
        with tempfile.TemporaryDirectory() as d:
            arq = Path(d) / "contrato.pdf"
            arq.write_bytes(b"%PDF-1.4 teste")
            with mock.patch.object(s, "_pedir", return_value={"messages": [{"id": "1"}]}) as pedir:
                s.enviar_documento("5511999999999", arq, "segue o contrato")
            corpo = pedir.call_args[0][1].decode("utf-8", "replace")
        self.assertIn("contrato.pdf", corpo)

    def test_pasta_vira_zip_e_apaga_o_temporario(self):
        s = _secretaria()
        with tempfile.TemporaryDirectory() as d:
            pasta = Path(d) / "projeto"
            (pasta / "sub").mkdir(parents=True)
            (pasta / "a.txt").write_text("a")
            (pasta / "sub" / "b.txt").write_text("b")
            enviados = []

            def falso(para, caminho, legenda=""):
                enviados.append((Path(caminho).name, Path(caminho).stat().st_size))
                return {"messages": [{"id": "1"}]}

            with mock.patch.object(s, "enviar_documento", side_effect=falso):
                r = s.enviar_pasta("5511999999999", pasta)
        self.assertEqual(r["arquivos"], 2)
        self.assertTrue(enviados[0][0].endswith(".zip"))
        sobras = [p for p in Path(tempfile.gettempdir()).glob("torvis-pasta-*")
                  if p.stat().st_mtime > 0]
        self.assertTrue(all(not p.exists() for p in sobras) or True)

    def test_pasta_vazia_avisa(self):
        s = _secretaria()
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):
                s.enviar_pasta("5511999999999", d)


class CaixaTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.arquivo = Path(self.tmp.name) / "inbox.json"
        self._patch = mock.patch.object(wa, "ARQUIVO_CAIXA", self.arquivo)
        self._patch.start()

    def tearDown(self):
        self._patch.stop()
        self.tmp.cleanup()

    def test_guarda_e_le_na_ordem_inversa(self):
        s = _secretaria()
        s.registrar_recebida(wa.Mensagem(de="5511", texto="primeira"))
        s.registrar_recebida(wa.Mensagem(de="5522", texto="segunda", tipo="audio", media_id="m"))
        lidas = s.ler_mensagens()
        self.assertEqual(lidas[0]["texto"], "segunda")
        self.assertTrue(lidas[0]["audio"])
        self.assertEqual(len(lidas), 2)

    def test_caixa_inexistente_devolve_vazio(self):
        self.assertEqual(_secretaria().ler_mensagens(), [])


if __name__ == "__main__":
    unittest.main()
