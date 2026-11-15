#!/usr/bin/env python3
"""Atualizador manual do TORVIS — para quando o botão "ATUALIZAR SISTEMA" falha.

POR QUE ISTO EXISTE
    O atualizador de dentro do app precisa baixar, conferir e substituir arquivos
    com o próprio programa rodando. No Windows isso dá errado por três motivos
    comuns: arquivo em uso, pasta sem permissão de escrita e antivírus segurando
    o .zip. Este script faz o mesmo trabalho com o app FECHADO e diz, arquivo por
    arquivo, o que não conseguiu copiar.

O QUE ELE GARANTE
    - só copia; nunca apaga nada seu;
    - não toca em config, memórias, notas, tarefas, logs nem na pasta updates/;
    - confere o SHA-256 do pacote antes de instalar: download corrompido para aqui;
    - deixa registro em updates/atualizacao-manual.log.

USO (na pasta do TORVIS, com o app fechado)
    py -3 tools\\atualizar_manual.py
    py -3 tools\\atualizar_manual.py --pacote C:\\Users\\voce\\Downloads\\TORVIS-Assistente-v6.6.2.zip
    py -3 tools\\atualizar_manual.py --diagnostico
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import sys
import tempfile
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

MANIFESTO_PADRAO = "https://raw.githubusercontent.com/andre2050/torvis-assistente/main/update.json"
TIMEOUT = 45.0
TENTATIVAS = 3

# Nomes que representam dado do usuário: nunca sobrescrever, nunca apagar.
PRESERVAR_PREFIXOS = (
    "config", "memory", "memorias", "memórias", "notas", "tarefas", "updates",
    "dist", ".git", "__pycache__", ".agents", "chroma", "indice", "índice",
    "erros.log", "metricas", "logs", "backup", "backups", ".env",
)
PRESERVAR_SUFIXOS = (".log", ".jsonl", ".sqlite", ".db", ".key", ".pem", ".zip", ".bak", ".orig")


def _raiz_do_app() -> Path:
    """A pasta do TORVIS: onde este script mora, um nível acima (ou um acima disso)."""
    aqui = Path(__file__).resolve().parent
    for candidata in (aqui, aqui.parent, Path.cwd(), Path.cwd().parent):
        if (candidata / "core" / "version.py").is_file():
            return candidata
    return Path.cwd()


def _versao_instalada(destino: Path) -> str:
    arquivo = destino / "core" / "version.py"
    try:
        for linha in arquivo.read_text(encoding="utf-8").splitlines():
            if linha.startswith("VERSAO"):
                return linha.split("=")[1].strip().strip('"').strip("'")
    except OSError:
        pass
    return "desconhecida"


def _baixar(url: str, destino: Path) -> Path:
    destino.parent.mkdir(parents=True, exist_ok=True)
    ultimo_erro = None
    for tentativa in range(1, TENTATIVAS + 1):
        try:
            pedido = urllib.request.Request(url, headers={
                "User-Agent": "TORVIS-Atualizador/1.0",
                "Cache-Control": "no-cache", "Pragma": "no-cache"})
            with urllib.request.urlopen(pedido, timeout=TIMEOUT) as resposta, \
                    destino.open("wb") as saida:
                total = int(resposta.headers.get("Content-Length") or 0)
                lido = 0
                while True:
                    bloco = resposta.read(262144)
                    if not bloco:
                        break
                    saida.write(bloco)
                    lido += len(bloco)
                    if total:
                        print(f"\r  baixando: {lido * 100 // total}%", end="", flush=True)
            print()
            return destino
        except (urllib.error.URLError, OSError) as exc:
            ultimo_erro = exc
            print(f"  tentativa {tentativa} de {TENTATIVAS} falhou: {exc}")
            time.sleep(2)
    raise RuntimeError(f"não consegui baixar o pacote: {ultimo_erro}")


def _sha256(arquivo: Path) -> str:
    resumo = hashlib.sha256()
    with arquivo.open("rb") as leitor:
        for bloco in iter(lambda: leitor.read(1048576), b""):
            resumo.update(bloco)
    return resumo.hexdigest()


def _ler_manifesto(url: str) -> dict:
    alvo = f"{url}?t={int(time.time())}" if url.lower().startswith("http") else url
    pedido = urllib.request.Request(alvo, headers={
        "User-Agent": "TORVIS-Atualizador/1.0",
        "Cache-Control": "no-cache, no-store", "Pragma": "no-cache"})
    with urllib.request.urlopen(pedido, timeout=TIMEOUT) as resposta:
        return json.loads(resposta.read().decode("utf-8"))


def _preservar(caminho_relativo: str) -> bool:
    partes = [p.lower() for p in Path(caminho_relativo).parts]
    if any(parte.startswith(PRESERVAR_PREFIXOS) for parte in partes):
        return True
    return qualquer_sufixo(caminho_relativo, PRESERVAR_SUFIXOS)


def qualquer_sufixo(nome: str, sufixos: tuple[str, ...]) -> bool:
    minusculo = nome.lower()
    return any(minusculo.endswith(s) for s in sufixos)


def _pasta_raiz_extraida(base: Path) -> Path:
    """O pacote traz uma pasta por cima; a raiz de verdade tem core/version.py."""
    if (base / "core" / "version.py").is_file():
        return base
    for filho in sorted(base.iterdir()):
        if filho.is_dir() and (filho / "core" / "version.py").is_file():
            return filho
    raise RuntimeError("o pacote não parece ser do TORVIS: falta core/version.py")


def _copiar(origem: Path, destino: Path) -> tuple[list[str], list[tuple[str, str]], list[str]]:
    copiados, falhas, preservados = [], [], []
    for raiz, pastas, arquivos in os.walk(origem):
        pastas[:] = [p for p in pastas if p.lower() not in ("__pycache__", ".git")]
        for nome in arquivos:
            fonte = Path(raiz) / nome
            relativo = str(fonte.relative_to(origem))
            if _preservar(relativo):
                preservados.append(relativo)
                continue
            alvo = destino / relativo
            try:
                alvo.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(fonte, alvo)
                copiados.append(relativo)
            except (OSError, PermissionError) as exc:
                falhas.append((relativo, str(exc)))
    return copiados, falhas, preservados


def atualizar(destino: Path, pacote: Path | None = None, manifesto_url: str = MANIFESTO_PADRAO,
              forcar: bool = False) -> int:
    print(f"Pasta do TORVIS: {destino}")
    instalada = _versao_instalada(destino)
    print(f"Versão instalada: {instalada}")

    aviso = ""
    sha_esperado = None
    remota = None
    package_url = None
    try:
        dados = _ler_manifesto(manifesto_url)
        remota = str(dados.get("version") or "").strip()
        sha_esperado = str(dados.get("sha256") or "").strip().lower() or None
        package_url = str(dados.get("package_url") or "").strip() or None
        print(f"Versão publicada: {remota}")
    except Exception as exc:                              # noqa: BLE001
        aviso = f"não consegui consultar o manifesto ({exc})"
        print("Aviso: " + aviso)

    if remota and remota == instalada and not forcar:
        print("Já está na versão publicada. Nada a fazer.")
        return 0

    temporaria = Path(tempfile.mkdtemp(prefix="torvis-update-"))
    try:
        if pacote is None:
            if not package_url:
                print("Sem pacote local e sem URL no manifesto: nada para instalar.")
                return 2
            print("Baixando o pacote...")
            pacote = _baixar(package_url, temporaria / "pacote.zip")

        if not pacote.is_file():
            print(f"Pacote não encontrado: {pacote}")
            return 2

        if sha_esperado:
            calculado = _sha256(pacote)
            if calculado != sha_esperado:
                print("O pacote baixado não confere com o SHA-256 publicado.")
                print(f"  esperado: {sha_esperado}")
                print(f"  obtido:   {calculado}")
                print("Apague o arquivo e baixe de novo; nada foi alterado no seu TORVIS.")
                return 3
            print("SHA-256 conferido.")

        print("Extraindo...")
        extracao = temporaria / "extraido"
        try:
            with zipfile.ZipFile(pacote) as z:
                ruim = z.testzip()
                if ruim:
                    print(f"O pacote está corrompido no arquivo {ruim}.")
                    print("Nada foi alterado no seu TORVIS. Baixe o pacote de novo.")
                    return 3
                z.extractall(extracao)
        except (zipfile.BadZipFile, OSError) as exc:
            # Download interrompido ou arquivo trocado no meio: melhor parar aqui,
            # com mensagem, do que estourar traceback na cara do usuário.
            print(f"O arquivo não é um zip válido ({exc}).")
            print("Nada foi alterado no seu TORVIS. Baixe o pacote de novo.")
            return 3
        try:
            raiz = _pasta_raiz_extraida(extracao)
        except RuntimeError as exc:
            print(f"{exc}\nEsse zip não é um pacote do TORVIS. Nada foi alterado.")
            return 3
        nova_versao = _versao_instalada(raiz)

        print("Copiando arquivos...")
        copiados, falhas, preservados = _copiar(raiz, destino)

        registro = destino / "updates"
        registro.mkdir(parents=True, exist_ok=True)
        with (registro / "atualizacao-manual.log").open("a", encoding="utf-8") as log:
            log.write(f"\n=== {time.strftime('%d/%m/%Y %H:%M:%S')} ===\n")
            log.write(f"de {instalada} para {nova_versao}\n")
            log.write(f"copiados: {len(copiados)} | falhas: {len(falhas)} | preservados: {len(preservados)}\n")
            for nome, motivo in falhas:
                log.write(f"FALHA {nome}: {motivo}\n")

        print()
        print(f"Copiados: {len(copiados)} arquivo(s).")
        print(f"Preservados (seus dados): {len(preservados)} arquivo(s).")
        if falhas:
            print(f"Não consegui copiar {len(falhas)} arquivo(s):")
            for nome, motivo in falhas[:12]:
                print(f"  - {nome}: {motivo}")
            print("Feche o TORVIS (e o console do Python) e rode de novo. "
                  "Se continuar, a pasta está sem permissão de escrita.")
            return 4

        agora = _versao_instalada(destino)
        print()
        print(f"Pronto: {instalada} -> {agora}")
        print("Abra o TORVIS pelo INICIAR.bat.")
        return 0
    finally:
        shutil.rmtree(temporaria, ignore_errors=True)


def diagnostico(destino: Path) -> int:
    print("=== Diagnóstico do atualizador ===")
    print(f"Sistema: {platform.platform()}")
    print(f"Python: {sys.version.split()[0]} ({'64 bits' if sys.maxsize > 2**32 else '32 bits'})")
    print(f"Pasta do TORVIS: {destino}")
    print(f"Versão instalada: {_versao_instalada(destino)}")

    teste = destino / ".teste_escrita.tmp"
    try:
        teste.write_text("ok", encoding="utf-8")
        teste.unlink()
        print("Pode escrever na pasta do TORVIS: sim")
    except OSError as exc:
        print(f"Pode escrever na pasta do TORVIS: NÃO ({exc})")
        print("  -> mova o TORVIS para uma pasta sua, como C:\\TORVIS, ou rode como administrador.")

    try:
        dados = _ler_manifesto(MANIFESTO_PADRAO)
        print(f"Manifesto publicado: {dados.get('version')} (alcançável)")
        url = dados.get("package_url")
        pedido = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "TORVIS/1.0"})
        with urllib.request.urlopen(pedido, timeout=TIMEOUT) as resposta:
            print(f"Pacote responde: HTTP {resposta.getcode()} "
                  f"({int(resposta.headers.get('Content-Length') or 0) // 1024} KB)")
    except Exception as exc:                              # noqa: BLE001
        print(f"Rede/GitHub: FALHOU ({exc})")
        print("  -> antivírus, proxy ou firewall podem estar bloqueando github.com.")

    travados = []
    for pasta, arquivos in (("core", "version.py"), ("actions", "qa_dev.py")):
        alvo = destino / pasta / arquivos
        if not alvo.is_file():
            continue
        try:
            with alvo.open("r+b"):
                pass
        except OSError:
            travados.append(str(alvo))
    print("Arquivos em uso (bloqueados): " + (", ".join(travados) if travados else "nenhum"))
    print()
    print("Rode este diagnóstico com o TORVIS FECHADO. Se aparecer 'arquivos em uso',")
    print("algum processo ainda está segurando os arquivos — é isso que quebra a troca.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Atualizador manual do TORVIS")
    parser.add_argument("--destino", help="pasta do TORVIS (padrão: detectada)")
    parser.add_argument("--pacote", help="caminho de um zip já baixado")
    parser.add_argument("--manifesto", default=MANIFESTO_PADRAO)
    parser.add_argument("--diagnostico", action="store_true", help="só verifica o ambiente")
    parser.add_argument("--forcar", action="store_true", help="instala mesmo na mesma versão")
    args = parser.parse_args(argv)

    destino = Path(args.destino).expanduser().resolve() if args.destino else _raiz_do_app()
    if not (destino / "core" / "version.py").is_file():
        print(f"Não achei um TORVIS em {destino}.")
        print("Rode de dentro da pasta do TORVIS, ou use --destino CAMINHO_DA_PASTA.")
        return 2

    if args.diagnostico:
        return diagnostico(destino)
    return atualizar(destino, Path(args.pacote).expanduser() if args.pacote else None,
                     args.manifesto, args.forcar)


if __name__ == "__main__":
    sys.exit(main())
