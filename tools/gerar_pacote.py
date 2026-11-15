"""Gera o pacote de atualização e o manifesto de integridade.

O atualizador do TORVIS só aceita um pacote se TODO arquivo estiver listado no
`update-manifest.json` com o sha256 correto — se faltar um, ou sobrar um que não
está listado, a atualização é recusada. Este script monta essa lista a partir do
conteúdo real do projeto, então pacote e manifesto nunca saem de sincronia.

Uso:
    python tools/gerar_pacote.py                 # gera dist/TORVIS-Assistente-v<versao>.zip
    python tools/gerar_pacote.py --destino saida/
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import zipfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
IGNORAR_DIR = {"__pycache__", ".pytest_cache", ".git", "dist", "build", ".venv", "venv", "node_modules"}
IGNORAR_EXT = {".pyc", ".log", ".jsonl"}
IGNORAR_NOME = {"relatorio-torvis.txt", "relatorio_chave.txt", "erros.old.log",
                "model_ladder.json", "uso_ia.json"}


def _sha256(caminho: Path) -> str:
    h = hashlib.sha256()
    with caminho.open("rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def _arquivos(base: Path) -> list[Path]:
    saida: list[Path] = []
    for raiz, dirs, nomes in os.walk(base):
        dirs[:] = [d for d in dirs if d not in IGNORAR_DIR]
        for nome in nomes:
            p = Path(raiz) / nome
            if p.suffix in IGNORAR_EXT or nome in IGNORAR_NOME:
                continue
            if nome == "update-manifest.json":
                continue          # regerado sempre a partir do conteúdo real
            saida.append(p)
    return sorted(saida)


def colisoes_de_caixa(arquivos: list[Path], raiz: Path) -> dict[str, list[str]]:
    """Arquivos que só diferem em maiúscula/minúscula.

    Existem no Linux, mas no Windows viram UM arquivo só: o pacote sai com dois
    nomes no manifesto e um arquivo no disco, e a atualização é recusada com
    "missing update file". Melhor falhar aqui, com o motivo à vista.
    """
    mapa: dict[str, list[str]] = {}
    for arquivo in arquivos:
        rel = arquivo.relative_to(raiz).as_posix()
        mapa.setdefault(rel.lower(), []).append(rel)
    return {chave: nomes for chave, nomes in mapa.items() if len(nomes) > 1}


def versao() -> str:
    sys.path.insert(0, str(RAIZ))
    from core.version import VERSAO

    return VERSAO


def gerar(destino: Path | None = None) -> tuple[Path, str]:
    v = versao()
    destino = Path(destino or RAIZ / "dist")
    destino.mkdir(parents=True, exist_ok=True)
    nome_base = f"TORVIS-Assistente-v{v}"
    pasta = destino / nome_base

    if pasta.exists():
        import shutil

        shutil.rmtree(pasta)
    pasta.mkdir(parents=True)

    arquivos = _arquivos(RAIZ)
    repetidos = colisoes_de_caixa(arquivos, RAIZ)
    if repetidos:
        detalhe = "; ".join(" / ".join(nomes) for nomes in repetidos.values())
        raise SystemExit(
            f"Pacote abortado: arquivos que diferem apenas em maiúscula/minúscula ({detalhe}).\n"
            "No Windows eles colapsam em um só e a atualização seria recusada. Renomeie um deles.")
    hashes: dict[str, str] = {}
    for origem in arquivos:
        rel = origem.relative_to(RAIZ)
        alvo = pasta / rel
        alvo.parent.mkdir(parents=True, exist_ok=True)
        alvo.write_bytes(origem.read_bytes())
        hashes[rel.as_posix()] = _sha256(alvo)

    manifesto = {
        "product": "T.O.R.V.I.S 2026",
        "version": v,
        "channel": "stable",
        "format": 1,
        "files": hashes,
    }
    (pasta / "update-manifest.json").write_text(
        json.dumps(manifesto, indent=2, ensure_ascii=False), encoding="utf-8")

    zip_path = destino / f"{nome_base}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for arquivo in sorted(pasta.rglob("*")):
            if arquivo.is_file():
                zf.write(arquivo, f"{nome_base}/{arquivo.relative_to(pasta).as_posix()}")

    return zip_path, _sha256(zip_path)


if __name__ == "__main__":
    destino = None
    if "--destino" in sys.argv:
        destino = Path(sys.argv[sys.argv.index("--destino") + 1])
    caminho, hash_zip = gerar(destino)
    print(f"pacote: {caminho}")
    print(f"arquivos: {len(json.loads((caminho.parent / caminho.stem / 'update-manifest.json').read_text(encoding='utf-8'))['files'])}")
    print(f"sha256: {hash_zip}")
