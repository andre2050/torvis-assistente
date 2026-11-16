#!/usr/bin/env python3
"""Servidor do webhook da secretária de WhatsApp do TORVIS.

A Meta precisa de um endereço público para entregar as mensagens. Este servidor
recebe, entende e responde. Rodar no PC:

    python tools/servidor_whatsapp.py --porta 8099

E expor para fora (escolha um):

    cloudflared tunnel --url http://127.0.0.1:8099
    ngrok http 8099

No painel da Meta, o endereço do webhook fica `https://SEU-ENDERECO/webhook` e o
token de verificação é o que estiver em `userdata/whatsapp.json` (chave
`verificar`). Sem `--ensaio`, é preciso ter token e id do número configurados.

O que este servidor faz com cada evento:

  * mensagem de texto  → pergunta ao TORVIS e responde;
  * nota de voz        → baixa, transcreve e responde (e devolve em áudio);
  * chamada perdida    → manda o recado, porque a API de mensagens não atende ligação.
"""
from __future__ import annotations

import argparse
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import whatsapp as wa  # noqa: E402


def gerador_padrao(texto: str) -> str:
    """Responde usando o mesmo modelo do TORVIS. Falha de cota não derruba o servidor."""
    try:
        from core import gemini
        cliente = gemini.client(timeout_ms=60_000)
        resposta = cliente.models.generate_content(model=gemini.SMART, contents=texto)
        return str(getattr(resposta, "text", "") or "").strip()
    except Exception as exc:  # noqa: BLE001
        print(f"[whatsapp] modelo indisponível: {exc}", flush=True)
        return ""


def falar_mp3(texto: str) -> bytes:
    """Gera a nota de voz (mp3) com o motor de fala do próprio TORVIS."""
    from core.tts import EdgeTTSEngine
    import asyncio
    motor = EdgeTTSEngine("pt-BR-AntonioNeural")
    laco = asyncio.new_event_loop()
    try:
        return laco.run_until_complete(motor._synth(texto))  # noqa: SLF001
    finally:
        laco.close()


def processar(corpo: dict, secretaria: wa.SecretariaWhatsApp, *, com_audio: bool = True) -> list[dict]:
    """Executa o que cada evento pede e devolve o que aconteceu (útil no log e nos testes)."""
    saida: list[dict] = []
    for evento in wa.ler_webhook(corpo):
        if evento["tipo"] == "mensagem":
            msg = wa.Mensagem(de=evento["de"], texto=evento["texto"], nome=evento["nome"],
                              tipo=evento["tipo_midia"], media_id=evento["media_id"])
            resultado = secretaria.responder_mensagem(
                msg, gerador_padrao, falar=falar_mp3 if com_audio else None)
            print(f"[whatsapp] {evento['de']}: {resultado}", flush=True)
            saida.append(resultado)
        elif evento["tipo"] == "chamada" and evento.get("estado") in ("missed", "timeout", "rejected", "terminated"):
            resultado = secretaria.avisar_chamada_perdida(evento["de"])
            print(f"[whatsapp] chamada de {evento['de']}: {resultado}", flush=True)
            saida.append(resultado)
    return saida


class Handler(BaseHTTPRequestHandler):
    secretaria: wa.SecretariaWhatsApp | None = None
    verificar = ""
    com_audio = True

    def log_message(self, formato, *args):  # noqa: A003
        print(f"[whatsapp] {self.address_string()} {formato % args}", flush=True)

    def _responder(self, codigo: int, corpo: bytes = b"", tipo: str = "text/plain; charset=utf-8"):
        self.send_response(codigo)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(corpo)))
        self.end_headers()
        if corpo:
            self.wfile.write(corpo)

    def do_GET(self):  # noqa: N802
        if not self.path.startswith("/webhook"):
            return self._responder(404, b"so /webhook")
        from urllib.parse import parse_qs, urlparse
        consulta = parse_qs(urlparse(self.path).query)
        modo = (consulta.get("hub.mode") or [""])[0]
        token = (consulta.get("hub.verify_token") or [""])[0]
        desafio = (consulta.get("hub.challenge") or [""])[0]
        if modo == "subscribe" and token and token == self.verificar:
            return self._responder(200, desafio.encode())
        return self._responder(403, b"token de verificacao nao confere")

    def do_POST(self):  # noqa: N802
        if not self.path.startswith("/webhook"):
            return self._responder(404, b"so /webhook")
        tamanho = int(self.headers.get("Content-Length") or 0)
        bruto = self.rfile.read(tamanho) if tamanho else b"{}"
        try:
            corpo = json.loads(bruto or b"{}")
        except ValueError:
            return self._responder(400, b"json invalido")
        try:
            resultados = processar(corpo, self.secretaria, com_audio=self.com_audio)
        except Exception as exc:  # noqa: BLE001 - a Meta não pode ver stack trace
            print(f"[whatsapp] falha ao processar: {exc}", flush=True)
            resultados = [{"ok": False, "motivo": str(exc)}]
        # 200 sempre que o corpo foi entendido: senão a Meta reenvia em laço.
        return self._responder(200, json.dumps({"ok": True, "eventos": resultados}, ensure_ascii=False).encode(),
                               "application/json; charset=utf-8")


def main() -> int:
    p = argparse.ArgumentParser(description="Webhook da secretária de WhatsApp do TORVIS")
    p.add_argument("--porta", type=int, default=8099)
    p.add_argument("--endereco", default="0.0.0.0")
    p.add_argument("--ensaio", action="store_true", help="não chama a Meta; mostra o que faria")
    p.add_argument("--sem-audio", action="store_true", help="responde só em texto")
    args = p.parse_args()

    cfg = wa.carregar_config()
    if not cfg.get("verificar"):
        cfg = wa.salvar_config({"verificar": "torvis-" + str(abs(hash(str(cfg))) % 100000)})
    secretaria = wa.SecretariaWhatsApp(cfg, ensaio=args.ensaio)
    disponivel, motivo = secretaria.disponivel()

    Handler.secretaria = secretaria
    Handler.verificar = cfg["verificar"]
    Handler.com_audio = not args.sem_audio
    servidor = ThreadingHTTPServer((args.endereco, args.porta), Handler)
    print(f"[whatsapp] escutando em http://{args.endereco}:{args.porta}/webhook")
    print(f"[whatsapp] token de verificação: {cfg['verificar']}")
    print(f"[whatsapp] credencial: {'ok' if disponivel else motivo}")
    print(f"[whatsapp] atendimento: {'ligado' if cfg['ligada'] else 'desligado'}")
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\n[whatsapp] encerrado")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
