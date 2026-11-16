"""Secretária de WhatsApp do T.O.R.V.I.S — API oficial (Cloud API da Meta).

O que esta camada faz:

  * recebe mensagem de texto e **entende nota de voz** (baixa a mídia e transcreve);
  * responde em texto e, se pedido, também em áudio (nota de voz);
  * responde a **chamada perdida** com uma mensagem curta, porque a API de
    mensagens não atende ligação;
  * respeita lista de permitidos, horário silencioso e um interruptor liga/desliga;
  * funciona sem credencial nenhuma em modo ensaio (`ensaio=True`), que monta as
    requisições e devolve o que *seria* enviado — é assim que os testes rodam.

O que ela **não** faz, e nenhuma biblioteca séria faz: atender a ligação e
conversar por voz. Isso só existe pela WhatsApp Business Calling API (GA desde
julho/2025), que exige conta business verificada, número elegível, webhook
público e streaming de áudio em tempo real (WebRTC/RTP). É um projeto à parte:
o `avisar_chamada_perdida` abaixo é o que dá para entregar hoje sem inventar.
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from core.userdata import USERDATA_DIR

VERSAO_API = "v21.0"
BASE = "https://graph.facebook.com"
ARQUIVO_CONFIG = USERDATA_DIR / "whatsapp.json"

# Formatos aceitos pela Cloud API para nota de voz.
AUDIO_OK = {
    ".mp3": "audio/mpeg",
    ".ogg": "audio/ogg",
    ".opus": "audio/ogg",
    ".aac": "audio/aac",
    ".m4a": "audio/mp4",
    ".amr": "audio/amr",
}


_MODELO_STT: Any = None


def _modelo_de_transcricao() -> Any:
    """Carrega o faster-whisper uma única vez (o download do modelo é caro)."""
    global _MODELO_STT
    if _MODELO_STT is not None:
        return _MODELO_STT
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise RuntimeError("transcrição indisponível: instale faster-whisper ou injete um transcritor") from exc
    _MODELO_STT = WhisperModel("base", device="cpu", compute_type="int8")
    return _MODELO_STT


class SecretariaIndisponivel(RuntimeError):
    """Falta credencial (token ou id do número) para falar com a Meta."""


@dataclass
class Mensagem:
    de: str
    texto: str = ""
    tipo: str = "text"
    media_id: str = ""
    quando: float = field(default_factory=time.time)
    nome: str = ""

    @property
    def tem_audio(self) -> bool:
        return self.tipo in ("audio", "voice") and bool(self.media_id)


def config_inicial() -> dict[str, Any]:
    return {
        "token": "",
        "numero_id": "",
        "verificar": "",          # palavra que a Meta repete no cadastro do webhook
        "ligada": False,
        "responder_audio": True,
        "permitidos": [],          # vazio = qualquer um (não recomendado)
        "silencioso_inicio": 23,
        "silencioso_fim": 7,
        "nome": "TORVIS",
        "recado": "Não consigo falar agora. Me diz por aqui o que você precisa que eu já vejo.",
    }


def carregar_config() -> dict[str, Any]:
    base = config_inicial()
    try:
        guardado = json.loads(ARQUIVO_CONFIG.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return base
    if isinstance(guardado, dict):
        base.update({k: v for k, v in guardado.items() if k in base})
    return base


def salvar_config(mudancas: dict[str, Any]) -> dict[str, Any]:
    cfg = carregar_config()
    cfg.update({k: v for k, v in mudancas.items() if k in cfg})
    ARQUIVO_CONFIG.parent.mkdir(parents=True, exist_ok=True)
    temporario = ARQUIVO_CONFIG.with_suffix(".json.tmp")
    temporario.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
    import os as _os
    _os.replace(temporario, ARQUIVO_CONFIG)
    return cfg


def _agora_hora() -> int:
    return time.localtime().tm_hour


def dentro_do_silencio(cfg: dict[str, Any], hora: int | None = None) -> bool:
    inicio = int(cfg.get("silencioso_inicio", 23))
    fim = int(cfg.get("silencioso_fim", 7))
    h = _agora_hora() if hora is None else hora
    if inicio == fim:
        return False
    if inicio < fim:
        return inicio <= h < fim
    return h >= inicio or h < fim       # janela que cruza a meia-noite


def so_digitos(numero: str) -> str:
    return "".join(c for c in str(numero) if c.isdigit())


class SecretariaWhatsApp:
    """Fala com a Cloud API e decide quem, quando e como responder."""

    def __init__(self, config: dict[str, Any] | None = None, *,
                 ensaio: bool = False,
                 transcritor: Callable[[bytes, str], str] | None = None,
                 abrir: Callable[..., Any] | None = None):
        self.cfg = dict(config or carregar_config())
        self.ensaio = ensaio
        self._transcritor = transcritor
        self._abrir = abrir or urllib.request.urlopen
        self.enviados: list[dict[str, Any]] = []   # histórico útil nos testes

    # ── credenciais ────────────────────────────────────────────────────────
    def disponivel(self) -> tuple[bool, str]:
        if self.ensaio:
            return True, "modo ensaio"
        if not self.cfg.get("token"):
            return False, "falta o token da Meta"
        if not self.cfg.get("numero_id"):
            return False, "falta o id do número de telefone"
        return True, "configurada"

    def _url(self, caminho: str) -> str:
        return f"{BASE}/{VERSAO_API}/{caminho.lstrip('/')}"

    def _pedir(self, url: str, dados: bytes | None = None, *, metodo: str = "POST",
               cabecalhos: dict[str, str] | None = None, bruto: bool = False) -> Any:
        cab = {"Authorization": f"Bearer {self.cfg.get('token', '')}"}
        cab.update(cabecalhos or {})
        if self.ensaio:
            return {"ensaio": True, "url": url, "corpo": (dados or b"").decode("utf-8", "replace")}
        pedido = urllib.request.Request(url, data=dados, method=metodo, headers=cab)
        try:
            with self._abrir(pedido, timeout=30) as resp:
                conteudo = resp.read()
        except urllib.error.HTTPError as exc:
            detalhe = exc.read().decode("utf-8", "replace")[:400]
            raise RuntimeError(f"a Meta recusou ({exc.code}): {detalhe}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"sem conexão com a Meta: {exc.reason}") from exc
        return conteudo if bruto else json.loads(conteudo or b"{}")

    # ── envio ──────────────────────────────────────────────────────────────
    def enviar_texto(self, para: str, texto: str) -> dict[str, Any]:
        ok, motivo = self.disponivel()
        if not ok:
            raise SecretariaIndisponivel(motivo)
        corpo = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": so_digitos(para),
            "type": "text",
            "text": {"preview_url": False, "body": texto[:4096]},
        }
        resposta = self._pedir(self._url(f"{self.cfg['numero_id']}/messages"),
                               json.dumps(corpo).encode(), cabecalhos={"Content-Type": "application/json"})
        self.enviados.append({"tipo": "texto", "para": para, "texto": texto})
        return resposta

    def _subir_audio(self, caminho: Path) -> str:
        tipo = AUDIO_OK.get(caminho.suffix.lower())
        if not tipo:
            raise ValueError(f"formato de áudio não aceito pela Meta: {caminho.suffix or 'sem extensão'}")
        limite = 16 * 1024 * 1024
        dados = caminho.read_bytes()
        if len(dados) > limite:
            raise ValueError("áudio passa de 16 MB")
        fronteira = "----torvis" + str(int(time.time() * 1000))
        partes = [
            f"--{fronteira}\r\nContent-Disposition: form-data; name=\"messaging_product\"\r\n\r\nwhatsapp\r\n".encode(),
            f"--{fronteira}\r\nContent-Disposition: form-data; name=\"type\"\r\n\r\n{tipo}\r\n".encode(),
            (f"--{fronteira}\r\nContent-Disposition: form-data; name=\"file\"; "
             f"filename=\"{caminho.name}\"\r\nContent-Type: {tipo}\r\n\r\n").encode() + dados + b"\r\n",
            f"--{fronteira}--\r\n".encode(),
        ]
        if self.ensaio:
            return "midia-de-ensaio"
        resposta = self._pedir(self._url(f"{self.cfg['numero_id']}/media"), b"".join(partes),
                               cabecalhos={"Content-Type": f"multipart/form-data; boundary={fronteira}"})
        return str((resposta or {}).get("id") or "")

    def enviar_audio(self, para: str, caminho_ou_bytes: Path | bytes, sufixo: str = ".mp3") -> dict[str, Any]:
        ok, motivo = self.disponivel()
        if not ok:
            raise SecretariaIndisponivel(motivo)
        if isinstance(caminho_ou_bytes, bytes):
            destino = Path(self._tmp(sufixo))
            destino.write_bytes(caminho_ou_bytes)
        else:
            destino = Path(caminho_ou_bytes)
        if not destino.exists():
            raise FileNotFoundError(destino)
        media_id = self._subir_audio(destino)
        corpo = {
            "messaging_product": "whatsapp",
            "to": so_digitos(para),
            "type": "audio",
            "audio": {"id": media_id},
        }
        resposta = self._pedir(self._url(f"{self.cfg['numero_id']}/messages"),
                               json.dumps(corpo).encode(), cabecalhos={"Content-Type": "application/json"})
        self.enviados.append({"tipo": "audio", "para": para, "arquivo": destino.name})
        return resposta

    @staticmethod
    def _tmp(sufixo: str) -> str:
        import tempfile
        arq = tempfile.NamedTemporaryFile(prefix="torvis-wa-", suffix=sufixo, delete=False)
        arq.close()
        return arq.name

    # ── recebimento ────────────────────────────────────────────────────────
    def baixar_midia(self, media_id: str) -> bytes:
        meta = self._pedir(self._url(media_id), metodo="GET")
        if self.ensaio:
            return b""
        url = str((meta or {}).get("url") or "")
        if not url:
            raise RuntimeError("a Meta não devolveu o endereço da mídia")
        return self._pedir(url, metodo="GET", bruto=True)

    def transcrever(self, audio: bytes, sufixo: str = ".ogg") -> str:
        if self._transcritor is not None:
            return self._transcritor(audio, sufixo)
        destino = Path(self._tmp(sufixo))
        destino.write_bytes(audio)
        modelo = _modelo_de_transcricao()
        trechos, _info = modelo.transcribe(str(destino), vad_filter=True)
        return " ".join(t.text.strip() for t in trechos).strip()

    def permitido(self, numero: str) -> bool:
        lista = [so_digitos(p) for p in (self.cfg.get("permitidos") or [])]
        if not lista:
            return True
        return so_digitos(numero) in lista

    def deve_responder(self, numero: str, hora: int | None = None) -> tuple[bool, str]:
        if not self.cfg.get("ligada"):
            return False, "secretária desligada"
        if not self.permitido(numero):
            return False, "número fora da lista de permitidos"
        if dentro_do_silencio(self.cfg, hora):
            return False, "horário silencioso"
        return True, "ok"

    def responder_mensagem(self, msg: Mensagem, gerador: Callable[[str], str], *,
                           falar: Callable[[str], Path | bytes] | None = None,
                           hora: int | None = None) -> dict[str, Any]:
        """Recebe o texto (ou a nota de voz), pergunta ao TORVIS e devolve a resposta.

        `hora` existe para o teste poder fixar o relógio sem esperar pela madrugada.
        """
        pode, motivo = self.deve_responder(msg.de, hora)
        if not pode:
            return {"ok": False, "motivo": motivo}
        pergunta = msg.texto.strip()
        if msg.tem_audio:
            try:
                pergunta = self.transcrever(self.baixar_midia(msg.media_id)).strip()
            except Exception as exc:  # noqa: BLE001 - a secretária não pode morrer
                return {"ok": False, "motivo": f"não entendi o áudio: {exc}"}
        if not pergunta:
            return {"ok": False, "motivo": "mensagem vazia"}
        resposta = (gerador(pergunta) or "").strip()
        if not resposta:
            return {"ok": False, "motivo": "o assistente não produziu resposta"}
        self.enviar_texto(msg.de, resposta)
        audio = None
        if self.cfg.get("responder_audio") and falar is not None:
            try:
                audio = self.enviar_audio(msg.de, falar(resposta))
            except Exception as exc:  # noqa: BLE001
                audio = {"erro": str(exc)}
        return {"ok": True, "pergunta": pergunta, "resposta": resposta, "audio": audio}

    def avisar_chamada_perdida(self, numero: str, nome: str = "") -> dict[str, Any]:
        """Ligação perdida não pode ser atendida pela API de mensagens; então a
        secretária responde na hora, no lugar do toque que passou."""
        pode, motivo = self.deve_responder(numero)
        if not pode:
            return {"ok": False, "motivo": motivo}
        recado = str(self.cfg.get("recado") or config_inicial()["recado"])
        if nome:
            recado = f"{nome}, " + recado[0].lower() + recado[1:]
        self.enviar_texto(numero, recado)
        return {"ok": True, "resposta": recado}


# ── leitura do que a Meta envia no webhook ─────────────────────────────────
def ler_webhook(corpo: dict[str, Any]) -> list[dict[str, Any]]:
    """Traduz o JSON do webhook em eventos simples.

    Cada evento é `{"tipo": "mensagem"|"chamada", ...}`. Mensagem traz texto ou
    media_id; chamada traz o estado (`ringing`, `missed`, `rejected`…).
    """
    eventos: list[dict[str, Any]] = []
    if not isinstance(corpo, dict):
        return eventos
    for entrada in corpo.get("entry") or []:
        if not isinstance(entrada, dict):
            continue
        for mudanca in entrada.get("changes") or []:
            if not isinstance(mudanca, dict):
                continue
            valor = mudanca.get("value") or {}
            if not isinstance(valor, dict):
                continue
            contatos = {so_digitos(c.get("wa_id", "")): c.get("profile", {}).get("name", "")
                        for c in valor.get("contacts") or []}
            for msg in valor.get("messages") or []:
                de = so_digitos(msg.get("from", ""))
                tipo = str(msg.get("type") or "text")
                evento = {"tipo": "mensagem", "de": de, "nome": contatos.get(de, ""),
                          "tipo_midia": tipo, "media_id": "", "texto": ""}
                if tipo == "text":
                    evento["texto"] = str((msg.get("text") or {}).get("body") or "")
                elif tipo in ("audio", "voice"):
                    evento["media_id"] = str((msg.get("audio") or {}).get("id")
                                             or (msg.get("voice") or {}).get("id") or "")
                    evento["tipo_midia"] = "audio"
                eventos.append(evento)
            for chamada in valor.get("calls") or []:
                eventos.append({"tipo": "chamada",
                                "de": so_digitos(chamada.get("from", "")),
                                "nome": "",
                                "estado": str(chamada.get("event") or chamada.get("status") or "")})
    return eventos
