"""Catálogo do computador: o que existe instalado, e como abrir e fechar.

O `open_app` atual resolve um nome e tenta iniciar. Isso cobre o que está no
PATH, e falha justamente no que o usuário tem: Photoshop, Visual Studio,
Sublime, jogo da Steam, app da Microsoft Store. A resposta era "não encontrei"
para programas que estão no menu Iniciar desde sempre.

Aqui o programa é DESCOBERTO, não adivinhado: atalhos do menu Iniciar (todos os
usuários e o atual), a chave App Paths do registro, apps UWP da Store e, no
Linux e no macOS, os diretórios equivalentes. A busca é por aproximação, então
"photoshop", "vs code", "sublime" e "word" encontram o atalho certo sem o nome
completo. Fechar procura primeiro por janela e depois por processo.
"""
from __future__ import annotations

import difflib
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

_SO = platform.system().lower()
_cache: list[dict] | None = None


# ── descoberta ───────────────────────────────────────────────────────────────
def _pastas_menu_iniciar() -> list[Path]:
    if _SO == "windows":
        saida = []
        for var in ("ProgramData", "APPDATA"):
            raiz = os.environ.get(var)
            if raiz:
                p = Path(raiz) / "Microsoft" / "Windows" / "Start Menu" / "Programs"
                if p.is_dir():
                    saida.append(p)
        return saida
    if _SO == "darwin":
        return [Path(p) for p in ("/Applications", "/System/Applications") if Path(p).is_dir()]
    saida = []
    for p in ("/usr/share/applications", str(Path.home() / ".local/share/applications")):
        if Path(p).is_dir():
            saida.append(Path(p))
    return saida


def _do_registro() -> list[dict]:
    """App Paths: quase todo instalador do Windows registra o executável aqui."""
    if _SO != "windows":
        return []
    try:
        import winreg
    except Exception:
        return []
    itens: list[dict] = []
    raiz = r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths"
    for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        try:
            with winreg.OpenKey(hive, raiz) as chave:
                total = winreg.QueryInfoKey(chave)[0]
                for i in range(total):
                    try:
                        sub = winreg.EnumKey(chave, i)
                        with winreg.OpenKey(chave, sub) as k:
                            alvo = winreg.QueryValue(k, None)
                    except OSError:
                        continue
                    if alvo:
                        nome = Path(sub).stem
                        itens.append({"nome": nome, "alvo": alvo, "tipo": "registro"})
        except OSError:
            continue
    return itens


def _uwp() -> list[dict]:
    """Apps da Store: não têm .exe acessível, só AppUserModelID do shell."""
    if _SO != "windows":
        return []
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-StartApps | Select-Object -Property Name,AppID | ConvertTo-Json -Compress"],
            capture_output=True, text=True, timeout=25,
        )
        import json
        dados = json.loads(r.stdout or "[]")
        if isinstance(dados, dict):
            dados = [dados]
    except Exception:
        return []
    return [{"nome": d["Name"], "alvo": f"shell:AppsFolder\\{d['AppID']}", "tipo": "store"}
            for d in dados if d.get("Name") and d.get("AppID")]


def catalogo(forcar: bool = False) -> list[dict]:
    """Tudo o que dá para abrir nesta máquina, sem repetir nome."""
    global _cache
    if _cache is not None and not forcar:
        return _cache
    itens: list[dict] = []
    for pasta in _pastas_menu_iniciar():
        try:
            arquivos = list(pasta.rglob("*.lnk")) if _SO == "windows" else list(pasta.rglob("*.desktop"))
        except OSError:
            arquivos = []
        for f in arquivos:
            itens.append({"nome": f.stem, "alvo": str(f), "tipo": "atalho"})
    itens += _do_registro()
    itens += _uwp()
    vistos: dict[str, dict] = {}
    for item in itens:
        chave = item["nome"].strip().lower()
        if chave and chave not in vistos:
            vistos[chave] = item
    _cache = sorted(vistos.values(), key=lambda d: d["nome"].lower())
    return _cache


def procurar(termo: str) -> dict | None:
    """Encontra o programa mais próximo do que a pessoa disse."""
    termo = (termo or "").strip().lower()
    if not termo:
        return None
    itens = catalogo()
    nomes = [i["nome"].lower() for i in itens]
    if termo in nomes:
        return itens[nomes.index(termo)]
    # "vs code" -> visual studio code, "photoshop" -> adobe photoshop 2024
    for i, nome in zip(itens, nomes):
        if termo.split(".")[0] in nome or nome.startswith(termo):
            return i
    achado = difflib.get_close_matches(termo, nomes, n=1, cutoff=0.55)
    if achado:
        return itens[nomes.index(achado[0])]
    caminho = shutil.which(termo)
    if caminho:
        return {"nome": termo, "alvo": caminho, "tipo": "path"}
    return None


# ── abrir ────────────────────────────────────────────────────────────────────
def abrir(nome: str) -> dict:
    """Abre o programa e diz o que de fato aconteceu."""
    item = procurar(nome)
    if not item:
        return {"status": "failed", "motivo": f"não achei nada parecido com {nome!r} instalado"}
    alvo = item["alvo"]
    try:
        if alvo.startswith("shell:"):
            subprocess.Popen(["explorer.exe", alvo])
        elif _SO == "windows":
            os.startfile(alvo)                       # noqa: S606 — abre pelo próprio Windows
        elif _SO == "darwin":
            subprocess.Popen(["open", alvo])
        else:
            subprocess.Popen(["xdg-open", alvo])
    except Exception as exc:
        return {"status": "failed", "motivo": str(exc), "alvo": alvo}
    return {"status": "started", "programa": item["nome"], "alvo": alvo, "tipo": item["tipo"]}


# ── fechar ───────────────────────────────────────────────────────────────────
def _janelas() -> list[str]:
    try:
        import pygetwindow as gw
        return [t for t in gw.getAllTitles() if t and t.strip()]
    except Exception:
        return []


def _processos() -> list[tuple[int, str]]:
    try:
        import psutil
        return [(p.pid, p.info["name"] or "") for p in
                psutil.process_iter(["name"]) if p.info.get("name")]
    except Exception:
        return []


def _fechar_janela(titulo: str) -> bool:
    """Fecha como um clique no X: o app ainda pode perguntar se quer salvar."""
    try:
        import pygetwindow as gw
        gw.getWindowsWithTitle(titulo)[0].close()
        return True
    except Exception:
        return False


def fechar(nome: str) -> dict:
    """Fecha por janela (educado) e, se preciso, por processo (definitivo)."""
    nome = (nome or "").strip()
    if not nome:
        return {"status": "failed", "motivo": "sem nome de programa ou janela"}
    alvo = nome.lower()

    # 1. janela primeiro: fecha como um clique no X, deixando o app salvar
    for titulo in _janelas():
        if alvo in titulo.lower() and _fechar_janela(titulo):
            return {"status": "closed", "modo": "janela", "janela": titulo}

    # 2. processo: o nome pode ser do programa, não do executável
    candidatos = [n for _pid, n in _processos()
                  if alvo in n.lower() or Path(n).stem.lower() == alvo.split(".")[0]]
    if not candidatos and _SO == "windows":
        item = procurar(nome)
        if item and item["alvo"].lower().endswith(".exe"):
            candidatos = [Path(item["alvo"]).name]
    if not candidatos:
        return {"status": "failed", "motivo": f"nada em execução chamado {nome!r}"}

    fechados: list[str] = []
    for imagem in set(candidatos):
        try:
            if _SO == "windows":
                r = subprocess.run(["taskkill", "/IM", imagem, "/F"],
                                   capture_output=True, text=True, timeout=15)
                if r.returncode == 0:
                    fechados.append(imagem)
            else:
                r = subprocess.run(["pkill", "-f", Path(imagem).stem],
                                   capture_output=True, text=True, timeout=15)
                if r.returncode == 0:
                    fechados.append(imagem)
        except Exception:
            continue
    if fechados:
        return {"status": "closed", "modo": "processo", "processos": fechados}
    return {"status": "failed", "motivo": "encontrei o processo, mas ele não encerrou"}


# ── criar projeto do zero ────────────────────────────────────────────────────
_SITE_HTML = """<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{titulo}</title>
  <link rel="stylesheet" href="style.css">
</head>
<body>
  <main>
    <h1>{titulo}</h1>
    <p>Primeira versão. Edite o texto, o estilo e o script.</p>
    <button id="acao">Começar</button>
  </main>
  <script src="script.js"></script>
</body>
</html>
"""

_SITE_CSS = """*{box-sizing:border-box;margin:0}
body{font-family:system-ui,-apple-system,Segoe UI,sans-serif;background:#0b0e12;
color:#e6edf3;min-height:100vh;display:grid;place-items:center}
main{max-width:640px;padding:48px 32px;text-align:center}
h1{font-size:32px;font-weight:600;letter-spacing:-.02em}
p{color:#8b98a5;margin:12px 0 28px}
button{background:#4cc2ff;color:#06121a;border:0;border-radius:10px;
padding:12px 22px;font-weight:600;cursor:pointer}
button:hover{filter:brightness(1.08)}
"""

_SITE_JS = """document.getElementById('acao')?.addEventListener('click', () => {
  alert('Funcionou.');
});
"""

_JOGO_PY = '''"""Jogo em Pygame gerado pelo TORVIS. Rode com: python main.py"""
import random
import pygame

pygame.init()
TELA = pygame.display.set_mode((640, 480))
pygame.display.set_caption("{titulo}")
REL = pygame.time.Clock()
x, y = 320, 240
alvo = pygame.Rect(random.randint(40, 560), random.randint(40, 400), 26, 26)
pontos = 0
rodando = True
while rodando:
    for evento in pygame.event.get():
        if evento.type == pygame.QUIT:
            rodando = False
    teclas = pygame.key.get_pressed()
    x += (teclas[pygame.K_RIGHT] - teclas[pygame.K_LEFT]) * 5
    y += (teclas[pygame.K_DOWN] - teclas[pygame.K_UP]) * 5
    corpo = pygame.Rect(x, y, 20, 20)
    if corpo.colliderect(alvo):
        pontos += 1
        alvo = pygame.Rect(random.randint(40, 560), random.randint(40, 400), 26, 26)
    TELA.fill((11, 14, 18))
    pygame.draw.rect(TELA, (255, 138, 61), alvo)
    pygame.draw.rect(TELA, (76, 194, 255), corpo)
    pygame.display.set_caption("{titulo} - pontos: " + str(pontos))
    pygame.display.flip()
    REL.tick(60)
pygame.quit()
'''

_APP_PY = '''"""App de janela gerado pelo TORVIS. Rode com: python main.py"""
import tkinter as tk

JANELA = tk.Tk()
JANELA.title("{titulo}")
JANELA.geometry("520x360")
JANELA.configure(bg="#0b0e12")


def acao():
    texto.configure(text="Feito.")


titulo = tk.Label(JANELA, text="{titulo}", bg="#0b0e12", fg="#e6edf3",
                  font=("Segoe UI", 18, "bold"))
titulo.pack(pady=(28, 6))
texto = tk.Label(JANELA, text="Primeira versão.", bg="#0b0e12", fg="#8b98a5",
                 font=("Segoe UI", 11))
texto.pack(pady=(0, 20))
botao = tk.Button(JANELA, text="Começar", command=acao, bg="#4cc2ff",
                  fg="#06121a", relief="flat", padx=18, pady=8)
botao.pack()
JANELA.mainloop()
'''


def criar_projeto(tipo: str, nome: str, destino: str | None = None) -> dict:
    """Cria a pasta e os arquivos iniciais de site, app ou jogo."""
    tipo = (tipo or "site").strip().lower()
    nome = (nome or "projeto").strip().replace("/", "-").replace("\\", "-")
    raiz = Path(destino).expanduser() if destino else Path.home() / "Documents" / "TORVIS"
    pasta = raiz / nome
    pasta.mkdir(parents=True, exist_ok=True)
    titulo = nome.replace("-", " ").replace("_", " ").title()

    if tipo in {"site", "website", "html"}:
        (pasta / "index.html").write_text(_SITE_HTML.format(titulo=titulo), encoding="utf-8")
        (pasta / "style.css").write_text(_SITE_CSS, encoding="utf-8")
        (pasta / "script.js").write_text(_SITE_JS, encoding="utf-8")
    elif tipo in {"jogo", "game", "pygame"}:
        (pasta / "main.py").write_text(_JOGO_PY.format(titulo=titulo), encoding="utf-8")
    else:
        tipo = "app"
        (pasta / "main.py").write_text(_APP_PY.format(titulo=titulo), encoding="utf-8")

    (pasta / "LEIA-ME.md").write_text(
        f"# {titulo}\n\nCriado pelo TORVIS.\n\n"
        + ("Abra `index.html` no navegador.\n" if tipo == "site"
           else "Instale as dependências e rode `python main.py`.\n"),
        encoding="utf-8")
    return {"status": "created", "tipo": tipo, "pasta": str(pasta),
            "arquivos": sorted(p.name for p in pasta.iterdir())}


# ── abrir editor ─────────────────────────────────────────────────────────────
_EDITORES = (("code", "Visual Studio Code"), ("code-insiders", "VS Code Insiders"),
             ("subl", "Sublime Text"), ("sublime_text", "Sublime Text"),
             ("notepad++", "Notepad++"), ("gedit", "gedit"), ("nano", "nano"))


def editor_disponivel() -> tuple[str, str] | None:
    for cmd, nome in _EDITORES:
        caminho = shutil.which(cmd)
        if caminho:
            return caminho, nome
    return None


def abrir_editor(caminho: str | None = None) -> dict:
    """Abre o editor de código que estiver instalado, na pasta pedida."""
    achado = editor_disponivel()
    alvo = str(Path(caminho).expanduser()) if caminho else str(Path.home())
    if not achado:
        try:
            if _SO == "windows":
                os.startfile(alvo)                   # noqa: S606
            elif _SO == "darwin":
                subprocess.Popen(["open", alvo])
            else:
                subprocess.Popen(["xdg-open", alvo])
            return {"status": "started", "editor": "gerenciador de arquivos", "pasta": alvo}
        except Exception as exc:
            return {"status": "failed", "motivo": str(exc)}
    cmd, nome = achado
    try:
        subprocess.Popen([cmd, alvo])
    except Exception as exc:
        return {"status": "failed", "motivo": str(exc)}
    return {"status": "started", "editor": nome, "pasta": alvo}
