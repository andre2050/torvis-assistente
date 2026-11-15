#!/usr/bin/env python3
"""Ponte do TORVIS — o celular manda, o PC executa.

Rode este arquivo no PC (dois cliques ou `python ponte_pc.py`). Ele mostra um
código de 6 dígitos; digite esse código no TORVIS do celular, em Ferramentas >
Computador. A partir daí o celular controla volume, música, abrir site, travar a
tela e ver o status da máquina — tudo na sua rede local, sem nuvem.

Segurança: só responde a quem apresenta o código, e o código muda a cada vez que
você abre o programa. Ações destrutivas (desligar) exigem confirmação explícita.
"""

import json
import os
import platform
import secrets
import shutil
import socket
import subprocess
import sys
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

PORTA = int(os.environ.get("TORVIS_PORTA", "8787"))
CODIGO = os.environ.get("TORVIS_CODIGO") or str(secrets.randbelow(900000) + 100000)
INICIO = time.time()
WINDOWS = platform.system() == "Windows"


# ── utilidades ────────────────────────────────────────────────────────────────

def rodar(comando, espera=8):
    """Executa um comando do sistema e devolve a saída, sem estourar exceção."""
    try:
        saida = subprocess.run(
            comando, shell=True, capture_output=True, text=True, timeout=espera
        )
        texto = (saida.stdout or saida.stderr or "").strip()
        return texto[:600] if texto else ("ok" if saida.returncode == 0 else "falhou")
    except Exception as erro:  # noqa: BLE001 - o celular precisa do motivo
        return "não consegui: {}".format(erro)


def teclas_windows(codigo_tecla):
    """Aperta uma tecla de mídia/volume no Windows via WScript."""
    return rodar(
        'powershell -NoProfile -Command '
        '"$w=New-Object -ComObject WScript.Shell; '
        '$w.SendKeys([char]{});"'.format(codigo_tecla)
    )


def status_maquina():
    dados = {
        "pc": socket.gethostname(),
        "sistema": platform.system(),
        "ligado": "{} min".format(int((time.time() - INICIO) / 60)),
    }
    try:
        uso = shutil.disk_usage(os.path.expanduser("~"))
        dados["disco"] = "{:.0f} GB livres de {:.0f} GB".format(
            uso.free / 1073741824, uso.total / 1073741824
        )
    except Exception:  # noqa: BLE001
        pass
    try:
        import psutil  # opcional: se existir, dá números de verdade

        dados["cpu"] = "{:.0f}%".format(psutil.cpu_percent(interval=0.3))
        dados["memoria"] = "{:.0f}% de {:.0f} GB".format(
            psutil.virtual_memory().percent,
            psutil.virtual_memory().total / 1073741824,
        )
    except Exception:  # noqa: BLE001
        try:
            carga = os.getloadavg()[0]
            dados["cpu"] = "{:.2f} de carga".format(carga)
        except Exception:  # noqa: BLE001
            dados["cpu"] = "não medido"
    return dados


def resumo_status():
    s = status_maquina()
    partes = ["{} ({})".format(s.get("pc", "PC"), s.get("sistema", "?"))]
    if s.get("cpu"):
        partes.append("CPU " + s["cpu"])
    if s.get("memoria"):
        partes.append("memória " + s["memoria"])
    if s.get("disco"):
        partes.append(s["disco"])
    return ", ".join(partes)


# ── ações que o celular pode pedir ────────────────────────────────────────────

def acao_volume_mais(_):
    if WINDOWS:
        return teclas_windows(175) or "volume aumentado"
    return rodar("pactl set-sink-volume @DEFAULT_SINK@ +10% 2>/dev/null || "
                 "amixer -D pulse sset Master 10%+ 2>/dev/null || echo sem-mixer")


def acao_volume_menos(_):
    if WINDOWS:
        return teclas_windows(174) or "volume diminuído"
    return rodar("pactl set-sink-volume @DEFAULT_SINK@ -10% 2>/dev/null || "
                 "amixer -D pulse sset Master 10%- 2>/dev/null || echo sem-mixer")


def acao_mudo(_):
    if WINDOWS:
        return teclas_windows(173) or "som alternado"
    return rodar("pactl set-sink-mute @DEFAULT_SINK@ toggle 2>/dev/null || echo sem-mixer")


def acao_midia(qual):
    mapa = {"play": 179, "pause": 179, "next": 176, "prev": 177, "stop": 178}
    tecla = mapa.get(str(qual or "play").lower(), 179)
    if WINDOWS:
        return teclas_windows(tecla) or "feito"
    alvo = {"play": "play-pause", "pause": "play-pause", "next": "next",
            "prev": "previous", "stop": "stop"}.get(str(qual or "play"), "play-pause")
    return rodar("playerctl {} 2>/dev/null || echo sem-player".format(alvo))


def acao_travar(_):
    if WINDOWS:
        return rodar("rundll32.exe user32.dll,LockWorkStation") or "PC travado"
    return rodar("loginctl lock-session 2>/dev/null || xdg-screensaver lock 2>/dev/null "
                 "|| echo sem-bloqueio")


def acao_abrir(url):
    if not url:
        return "faltou o endereço"
    alvo = str(url).strip()
    if not alvo.startswith(("http://", "https://")):
        alvo = "https://" + alvo
    try:
        webbrowser.open(alvo)
        return "abri " + alvo
    except Exception as erro:  # noqa: BLE001
        return "não abri: {}".format(erro)


def acao_status(_):
    return resumo_status()


def acao_desligar(args):
    """Só desliga com confirmar=true, e ainda dá um minuto para desistir."""
    if not (isinstance(args, dict) and args.get("confirmar") is True):
        return "para desligar, mande confirmar=true (o TORVIS pergunta antes)"
    if WINDOWS:
        return rodar("shutdown /s /t 60") or "desligando em 60 segundos"
    return rodar("systemctl poweroff 2>/dev/null || shutdown -h +1 2>/dev/null || echo sem-permissao")


ACOES = {
    "status": acao_status,
    "volume_mais": acao_volume_mais,
    "volume_menos": acao_volume_menos,
    "mudo": acao_mudo,
    "midia": acao_midia,
    "travar": acao_travar,
    "abrir": acao_abrir,
    "desligar": acao_desligar,
}


# ── servidor ──────────────────────────────────────────────────────────────────

class Atendente(BaseHTTPRequestHandler):
    server_version = "TORVIS-Ponte/1.0"

    def _responder(self, codigo_http, corpo):
        texto = json.dumps(corpo, ensure_ascii=False).encode("utf-8")
        self.send_response(codigo_http)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(texto)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Codigo")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()
        self.wfile.write(texto)

    def do_OPTIONS(self):  # noqa: N802 - assinatura exigida pelo http.server
        self._responder(204, {})

    def do_GET(self):  # noqa: N802
        caminho = urlparse(self.path).path
        if caminho in ("/ping", "/"):
            self._responder(200, {
                "ok": True, "servico": "torvis-ponte",
                "pc": socket.gethostname(), "porta": PORTA,
            })
            return
        self._responder(404, {"ok": False, "erro": "caminho desconhecido"})

    def do_POST(self):  # noqa: N802
        caminho = urlparse(self.path).path
        if caminho != "/execu":
            self._responder(404, {"ok": False, "erro": "caminho desconhecido"})
            return

        enviado = (self.headers.get("X-Codigo") or "").strip()
        if not secrets.compare_digest(enviado, CODIGO):
            self._responder(401, {"ok": False, "erro": "código errado"})
            return

        tamanho = int(self.headers.get("Content-Length") or 0)
        if tamanho > 4096:
            self._responder(413, {"ok": False, "erro": "pedido grande demais"})
            return
        try:
            corpo = json.loads(self.rfile.read(tamanho) or b"{}")
        except Exception:  # noqa: BLE001
            self._responder(400, {"ok": False, "erro": "JSON inválido"})
            return

        acao = str(corpo.get("acao") or "")
        args = corpo.get("args")
        if acao not in ACOES:
            self._responder(400, {"ok": False, "erro": "ação desconhecida: " + acao})
            return
        try:
            resultado = ACOES[acao](args)
        except Exception as erro:  # noqa: BLE001
            resultado = "falhou: {}".format(erro)
        print("  [{}] {} -> {}".format(time.strftime("%H:%M:%S"), acao, resultado))
        self._responder(200, {"ok": True, "resultado": resultado})

    def log_message(self, formato, *args):  # silencia o log padrão
        return


def ip_local():
    try:
        sonda = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sonda.connect(("8.8.8.8", 80))
        ip = sonda.getsockname()[0]
        sonda.close()
        return ip
    except Exception:  # noqa: BLE001
        return "127.0.0.1"


def principal():
    ip = ip_local()
    linhas = [
        "",
        "  ╔══════════════════════════════════════════════════════╗",
        "  ║            TORVIS 2026 — ponte do computador         ║",
        "  ╚══════════════════════════════════════════════════════╝",
        "",
        "  No celular: Ferramentas > Computador",
        "  Endereço:  {}:{}".format(ip, PORTA),
        "  Código:    {}".format(CODIGO),
        "",
        "  Deixe esta janela aberta. Ctrl+C encerra.",
        "",
    ]
    print("\n".join(linhas))

    servidor = ThreadingHTTPServer(("0.0.0.0", PORTA), Atendente)
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\n  ponte encerrada.")
    finally:
        servidor.server_close()


if __name__ == "__main__":
    principal()
