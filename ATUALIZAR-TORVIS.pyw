#!/usr/bin/env python3
"""ATUALIZAR-TORVIS.pyw — atualiza o TORVIS por janela, sem terminal.

COMO USAR
    Dois cliques neste arquivo. Ele acha a pasta do TORVIS, mostra a versão
    instalada e a publicada, e faz a troca quando você clica em "Atualizar".
    Termina com uma mensagem dizendo o que aconteceu, com botão para abrir o TORVIS.

POR QUE ELE EXISTE
    O botão "ATUALIZAR SISTEMA" de dentro do app faz a troca com o próprio app
    rodando. No Windows isso trava: arquivo em uso, pasta sem permissão de escrita
    ou antivírus segurando o zip. Este programa roda FORA do app, então não há
    arquivo em uso, e ele mostra o motivo de cada falha em vez de esconder no log.

O QUE ELE GARANTE
    - confere o SHA-256 do pacote antes de instalar;
    - só copia, nunca apaga;
    - não toca em config, memórias, notas, tarefas, updates/, .env, logs nem .bak;
    - se não achar o TORVIS, pede a pasta em vez de adivinhar.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

# Duas fontes, e fica a de maior versão. O raw.githubusercontent segura cache por
# minutos: logo depois de publicar, ele ainda devolve o manifesto antigo — foi o
# que fez uma atualização "não mudar" sem dar erro. O endereço de release aponta
# sempre para o último release publicado.
FONTES = (
    "https://github.com/andre2050/torvis-assistente/releases/latest/download/update.json",
    "https://raw.githubusercontent.com/andre2050/torvis-assistente/main/update.json",
)
MANIFESTO = FONTES[0]
TIMEOUT = 45.0
TENTATIVAS = 3

PRESERVAR_PREFIXOS = (
    "config", "memory", "memorias", "memórias", "notas", "tarefas", "updates",
    "dist", ".git", "__pycache__", ".agents", "chroma", "indice", "índice",
    "erros.log", "metricas", "logs", "backup", "backups", ".env",
)
PRESERVAR_SUFIXOS = (".log", ".jsonl", ".sqlite", ".db", ".key", ".pem", ".zip", ".bak", ".orig")


# ── núcleo, sem interface ────────────────────────────────────────────────────
def achar_app(inicio: Path | None = None) -> Path | None:
    """Acha a pasta do TORVIS sem adivinhar demais.

    Ordem: a pasta do próprio script, a de cima, o diretório atual e o de cima.
    Só depois olha um nível abaixo (script, atual, Desktop, Downloads), e mesmo
    aí só devolve quando NÃO HÁ DÚVIDA: um candidato só, ou um só que tenha
    INICIAR.bat. Ambiguidade devolve None e a janela pede a pasta — atualizar a
    cópia errada em silêncio é pior que pedir um clique.
    """
    base = Path(inicio or __file__).resolve().parent
    for raiz in (base, base.parent, Path.cwd(), Path.cwd().parent):
        if (raiz / "core" / "version.py").is_file():
            return raiz

    procuradas = [base, Path.cwd(), Path.home() / "Desktop",
                  Path.home() / "Downloads", Path.home() / "OneDrive" / "Desktop"]
    candidatos: dict[Path, None] = {}
    for raiz in procuradas:
        if not raiz.is_dir():
            continue
        try:
            for filho in raiz.iterdir():
                if filho.is_dir() and (filho / "core" / "version.py").is_file():
                    candidatos[filho] = None
        except OSError:
            continue

    lista = list(candidatos)
    if len(lista) == 1:
        return lista[0]
    instaladas = [c for c in lista if (c / "INICIAR.bat").is_file()]
    if len(instaladas) == 1:
        return instaladas[0]
    return None


def versao_instalada(app: Path) -> str:
    try:
        for linha in (app / "core" / "version.py").read_text(encoding="utf-8").splitlines():
            if linha.startswith("VERSAO"):
                return linha.split("=")[1].strip().strip('"').strip("'")
    except OSError:
        pass
    return "desconhecida"


def _tupla(versao: object) -> tuple[int, ...]:
    partes = []
    for pedaco in str(versao or "0").split("."):
        digitos = "".join(c for c in pedaco if c.isdigit())
        partes.append(int(digitos) if digitos else 0)
    return tuple(partes)


def _ler_uma(url: str, cache_bust: bool = True) -> dict:
    alvo = url
    if cache_bust and url.lower().startswith("http"):
        alvo = f"{url}{'&' if '?' in url else '?'}t={int(time.time() * 1000)}"
    pedido = urllib.request.Request(alvo, headers={
        "User-Agent": "TORVIS-Atualizador/2.0",
        "Cache-Control": "no-cache, no-store", "Pragma": "no-cache"})
    with urllib.request.urlopen(pedido, timeout=TIMEOUT) as resposta:
        dados = json.loads(resposta.read().decode("utf-8"))
    if not isinstance(dados, dict) or "version" not in dados:
        raise ValueError("manifesto sem campo 'version'")
    return dados


def ler_manifesto(url: str = MANIFESTO) -> dict:
    """Consulta uma fonte; se for o padrão, consulta todas e devolve a mais nova."""
    if url != MANIFESTO:
        return _ler_uma(url, cache_bust=url.lower().startswith("http"))

    melhores, erros = [], []
    for fonte in FONTES:
        try:
            melhores.append(_ler_uma(fonte))
        except Exception as exc:                          # noqa: BLE001
            erros.append(f"{fonte}: {exc}")
    if not melhores:
        raise RuntimeError("nenhuma fonte respondeu (" + "; ".join(erros) + ")")
    melhores.sort(key=lambda d: _tupla(d.get("version")), reverse=True)
    return melhores[0]


def baixar(url: str, destino: Path, aviso=lambda _t: None) -> Path:
    destino.parent.mkdir(parents=True, exist_ok=True)
    ultimo = None
    for tentativa in range(1, TENTATIVAS + 1):
        try:
            pedido = urllib.request.Request(url, headers={
                "User-Agent": "TORVIS-Atualizador/2.0",
                "Cache-Control": "no-cache", "Pragma": "no-cache"})
            with urllib.request.urlopen(pedido, timeout=TIMEOUT) as resposta, destino.open("wb") as saida:
                total = int(resposta.headers.get("Content-Length") or 0)
                lido = 0
                while True:
                    bloco = resposta.read(262144)
                    if not bloco:
                        break
                    saida.write(bloco)
                    lido += len(bloco)
                    if total:
                        aviso(f"Baixando: {lido * 100 // total}%")
            return destino
        except (urllib.error.URLError, OSError) as exc:
            ultimo = exc
            if tentativa < TENTATIVAS:
                aviso(f"Tentativa {tentativa} falhou, tentando de novo...")
                time.sleep(2)
    raise RuntimeError(f"download falhou: {ultimo}")


def sha256(arquivo: Path) -> str:
    resumo = hashlib.sha256()
    with arquivo.open("rb") as leitor:
        for bloco in iter(lambda: leitor.read(1048576), b""):
            resumo.update(bloco)
    return resumo.hexdigest()


def preservar(relativo: str) -> bool:
    partes = [p.lower() for p in Path(relativo).parts]
    if any(parte.startswith(PRESERVAR_PREFIXOS) for parte in partes):
        return True
    minusculo = relativo.lower()
    return any(minusculo.endswith(s) for s in PRESERVAR_SUFIXOS)


def raiz_extraida(base: Path) -> Path:
    if (base / "core" / "version.py").is_file():
        return base
    for filho in sorted(base.iterdir()):
        if filho.is_dir() and (filho / "core" / "version.py").is_file():
            return filho
    raise RuntimeError("o pacote não parece ser do TORVIS: falta core/version.py")


def copiar(origem: Path, destino: Path) -> tuple[list[str], list[tuple[str, str]], list[str]]:
    copiados, falhas, preservados = [], [], []
    for raiz, pastas, arquivos in os.walk(origem):
        pastas[:] = [p for p in pastas if p.lower() not in ("__pycache__", ".git")]
        for nome in arquivos:
            fonte = Path(raiz) / nome
            relativo = str(fonte.relative_to(origem))
            if preservar(relativo):
                preservados.append(relativo)
                continue
            try:
                alvo = destino / relativo
                alvo.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(fonte, alvo)
                copiados.append(relativo)
            except OSError as exc:
                falhas.append((relativo, str(exc)))
    return copiados, falhas, preservados


def app_aberto(app: Path) -> list[str]:
    """Arquivos que outro processo está segurando (causa número 1 de falha)."""
    travados = []
    for relativo in ("core/version.py", "core/gemini.py", "main.py"):
        alvo = app / relativo
        if not alvo.is_file():
            continue
        try:
            with alvo.open("r+b"):
                pass
        except OSError:
            travados.append(relativo)
    return travados


def atualizar(app: Path, pacote: Path | None = None, aviso=lambda _t: None,
              manifesto_url: str = MANIFESTO) -> dict:
    """Faz a troca e devolve um relato — nunca lança por falha prevista."""
    relato = {"ok": False, "de": versao_instalada(app), "para": None, "mensagem": "",
              "copiados": 0, "falhas": [], "preservados": 0}

    travados = app_aberto(app)
    if travados:
        relato["mensagem"] = ("O TORVIS parece estar aberto (" + ", ".join(travados) + ").\n"
                             "Feche o TORVIS e clique em Atualizar de novo.")
        return relato

    local = pacote is not None
    dados: dict = {}
    if local:
        # Pacote escolhido à mão: a rede deixa de ser obrigatória. Serve para
        # quando antivírus, proxy ou o próprio Windows barram o download.
        try:
            dados = ler_manifesto(manifesto_url)
        except Exception as exc:                          # noqa: BLE001
            aviso(f"Sem consulta ao GitHub ({exc}). Instalando do arquivo escolhido.")
    else:
        aviso("Consultando a versão publicada...")
        try:
            dados = ler_manifesto(manifesto_url)
        except Exception as exc:                          # noqa: BLE001
            relato["mensagem"] = (f"Não consegui consultar o GitHub: {exc}\n\n"
                                  "Antivírus, proxy ou falta de internet podem bloquear.\n"
                                  "Alternativa: baixe o pacote no navegador e use\n"
                                  "\"Instalar pacote baixado (.zip)\".")
            return relato

    remota = str(dados.get("version") or "").strip()
    relato["para"] = remota or None
    if remota and not local and remota == relato["de"]:
        relato.update(ok=True, mensagem=f"Já está na versão {relato['de']}. Nada a fazer.")
        return relato

    temporaria = Path(tempfile.mkdtemp(prefix="torvis-janela-"))
    try:
        if pacote is None:
            url = str(dados.get("package_url") or "").strip()
            if not url:
                relato["mensagem"] = "O manifesto não traz o endereço do pacote."
                return relato
            aviso("Baixando o pacote...")
            pacote = baixar(url, temporaria / "pacote.zip", aviso)

        esperado = "" if local else str(dados.get("sha256") or "").strip().lower()
        if esperado and sha256(pacote) != esperado:
            relato["mensagem"] = ("O pacote baixado não confere com o SHA-256 publicado.\n"
                                  "Nada foi alterado. Tente de novo; se repetir, o antivírus "
                                  "pode estar mexendo no arquivo.")
            return relato

        aviso("Conferindo o conteúdo...")
        try:
            with zipfile.ZipFile(pacote) as z:
                if z.testzip():
                    relato["mensagem"] = "O pacote está corrompido. Nada foi alterado."
                    return relato
                extracao = temporaria / "extraido"
                z.extractall(extracao)
        except (zipfile.BadZipFile, OSError) as exc:
            relato["mensagem"] = f"O arquivo não é um zip válido ({exc}). Nada foi alterado."
            return relato

        try:
            origem = raiz_extraida(extracao)
        except RuntimeError as exc:
            relato["mensagem"] = (f"{exc}\n\n"
                                  "O arquivo escolhido não é um pacote do TORVIS.\n"
                                  "Baixe o pacote oficial na página de releases do GitHub\n"
                                  "e escolha o .zip de novo. Nada foi alterado.")
            return relato
        versao_pacote = versao_instalada(origem)
        relato["para"] = versao_pacote
        if versao_pacote == relato["de"]:
            relato.update(ok=True, mensagem=f"Esse pacote já é a versão {relato['de']}. "
                                            "Nada foi alterado.")
            return relato
        aviso(f"Pacote {versao_pacote}. Copiando arquivos...")
        copiados, falhas, preservados = copiar(origem, app)
        relato.update(copiados=len(copiados), falhas=falhas, preservados=len(preservados))

        try:
            registro = app / "updates"
            registro.mkdir(parents=True, exist_ok=True)
            with (registro / "atualizacao-janela.log").open("a", encoding="utf-8") as log:
                log.write(f"\n=== {time.strftime('%d/%m/%Y %H:%M')} ===\n")
                log.write(f"{relato['de']} -> {versao_pacote} | copiados {len(copiados)} | "
                          f"falhas {len(falhas)}\n")
                for nome, motivo in falhas:
                    log.write(f"FALHA {nome}: {motivo}\n")
        except OSError:
            pass

        if falhas:
            relato["mensagem"] = (f"{len(falhas)} arquivo(s) não puderam ser copiados.\n"
                                  "Feche o TORVIS (e o console do Python) e tente de novo.")
            return relato

        agora = versao_instalada(app)
        relato.update(ok=True, para=agora,
                      mensagem=f"Atualizado: {relato['de']} → {agora}.\n"
                               f"{len(copiados)} arquivos copiados, "
                               f"{len(preservados)} preservados.")
        return relato
    finally:
        shutil.rmtree(temporaria, ignore_errors=True)


def abrir_torvis(app: Path) -> bool:
    """Abre o TORVIS do jeito que a pasta dele oferece."""
    for nome in ("INICIAR.bat", "iniciar.bat"):
        alvo = app / nome
        if alvo.is_file():
            subprocess.Popen(["cmd", "/c", "start", "", str(alvo)], cwd=str(app), shell=False)
            return True
    if (app / "main.py").is_file():
        subprocess.Popen([sys.executable, "main.py"], cwd=str(app))
        return True
    return False


# ── janela ───────────────────────────────────────────────────────────────────
def janela() -> int:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk

    app = achar_app()
    raiz = tk.Tk()
    raiz.title("Atualizar o TORVIS")
    raiz.minsize(560, 320)
    estado = {"app": app, "rodando": False}

    moldura = ttk.Frame(raiz, padding=18)
    moldura.pack(fill="both", expand=True)

    titulo = ttk.Label(moldura, text="Atualizar o TORVIS 2026",
                       font=("Segoe UI", 16, "bold"))
    titulo.pack(anchor="w")

    pasta = ttk.Label(moldura, text="", wraplength=520, foreground="#555")
    pasta.pack(anchor="w", pady=(6, 12))

    versoes = ttk.Label(moldura, text="", font=("Consolas", 11))
    versoes.pack(anchor="w", pady=(0, 10))

    barra = ttk.Progressbar(moldura, mode="determinate", maximum=100)
    barra.pack(fill="x", pady=(0, 10))

    saida = tk.Text(moldura, height=7, wrap="word", relief="flat",
                    background="#f6f8fa", borderwidth=1)
    saida.pack(fill="both", expand=True)
    saida.configure(state="disabled")

    def escrever(texto: str) -> None:
        saida.configure(state="normal")
        saida.insert("end", texto + "\n")
        saida.see("end")
        saida.configure(state="disabled")

    def pintar_estado():
        atual = estado["app"]
        if atual:
            pasta.configure(text=f"Pasta: {atual}")
            versoes.configure(text=f"Instalada: {versao_instalada(atual)}")
        else:
            pasta.configure(text="Não achei o TORVIS. Use \"Escolher pasta\".")
            versoes.configure(text="Instalada: —")

    def escolher():
        escolhida = filedialog.askdirectory(title="Pasta do TORVIS (a que tem core/version.py)")
        if not escolhida:
            return
        candidata = Path(escolhida)
        if not (candidata / "core" / "version.py").is_file():
            messagebox.showerror("Pasta errada",
                                 "Essa pasta não tem core/version.py.\nEscolha a pasta do TORVIS.")
            return
        estado["app"] = candidata
        pintar_estado()

    def aviso(texto: str):
        if texto.startswith("Baixando:"):
            try:
                barra["value"] = int(texto.split(":")[1].strip("% "))
            except ValueError:
                pass
        else:
            escrever(texto)

    def terminar(relato: dict) -> None:
        estado["rodando"] = False
        botao.configure(state="normal", text="Atualizar agora")
        botao_zip.configure(state="normal")
        barra["value"] = 100 if relato.get("ok") else 0
        escrever(relato.get("mensagem", ""))
        pintar_estado()
        if relato.get("ok"):
            if messagebox.askyesno("TORVIS atualizado",
                                   relato["mensagem"] + "\n\nAbrir o TORVIS agora?"):
                abrir_torvis(estado["app"])
            raiz.destroy()
        else:
            messagebox.showwarning("Não deu para atualizar", relato.get("mensagem", ""))

    def copiar_detalhes():
        try:
            raiz.clipboard_clear()
            raiz.clipboard_append(saida.get("1.0", "end").strip())
            escrever("Detalhes copiados. Cole no chat para eu ver o que aconteceu.")
        except Exception as exc:                          # noqa: BLE001
            escrever(f"Não consegui copiar: {exc}")

    def comecar_de_arquivo():
        arquivo = filedialog.askopenfilename(
            title="Pacote do TORVIS já baixado",
            filetypes=[("Pacote do TORVIS", "*.zip"), ("Todos os arquivos", "*.*")])
        if not arquivo:
            return
        if not estado["app"]:
            messagebox.showinfo("Cadê o TORVIS?",
                                "Não achei a pasta do TORVIS.\nUse \"Escolher pasta\".")
            return
        iniciar(Path(arquivo))

    def iniciar(pacote=None):
        if estado["rodando"]:
            return
        estado["rodando"] = True
        botao.configure(state="disabled", text="Atualizando...")
        botao_zip.configure(state="disabled")
        barra["value"] = 0
        escrever("Começando...")

        def corpo():
            try:
                relato = atualizar(estado["app"], pacote=pacote, aviso=aviso)
            except Exception as exc:                      # noqa: BLE001
                relato = {"ok": False, "mensagem": f"Erro inesperado: {exc}"}
            raiz.after(0, lambda: terminar(relato))

        threading.Thread(target=corpo, daemon=True).start()

    def comecar():
        if not estado["app"]:
            messagebox.showinfo("Cadê o TORVIS?",
                                "Não achei a pasta do TORVIS.\nUse \"Escolher pasta\".")
            return
        iniciar(None)

    botoes = ttk.Frame(moldura)
    botoes.pack(fill="x", pady=(12, 0))
    botao = ttk.Button(botoes, text="Atualizar agora", command=comecar)
    botao.pack(side="left")
    botao_zip = ttk.Button(botoes, text="Instalar pacote baixado (.zip)",
                           command=comecar_de_arquivo)
    botao_zip.pack(side="left", padx=8)
    ttk.Button(botoes, text="Copiar detalhes", command=copiar_detalhes).pack(side="left", padx=8)
    ttk.Button(botoes, text="Fechar", command=raiz.destroy).pack(side="right")

    pintar_estado()
    escrever("Feche o TORVIS antes de atualizar: arquivo aberto não pode ser substituído.")
    raiz.mainloop()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(janela())
    except Exception as exc:                              # noqa: BLE001
        # Sem tkinter/ambiente gráfico: avisa por caixa nativa, que existe no Windows.
        print(f"Não consegui abrir a janela: {exc}")
        if os.name == "nt":
            try:
                import ctypes
                ctypes.windll.user32.MessageBoxW(
                    None, f"Não consegui abrir a janela: {exc}", "Atualizar o TORVIS", 0x30)
            except Exception:                             # noqa: BLE001
                pass
        print("Rode: py -3 tools\\atualizar_manual.py --diagnostico")
        sys.exit(1)
