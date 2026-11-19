"""Modo vigia: ele trabalha na pasta enquanto ninguém está olhando.

A ideia é simples e por isso não depende de nada exótico: de tempos em tempos
ele olha uma pasta, vê o que é novo desde a última passada e aplica a regra que
combina com o arquivo. Foto vai para uma pasta por ano-mês, nota fiscal é
renomeada com a data que está dentro dela, PDF é resumido num arquivo de texto
ao lado.

Sem `watchdog`: um laço de varredura a cada poucos segundos custa quase nada e
não adiciona dependência que pode faltar na máquina do usuário. O que já foi
tratado fica registrado num estado em disco, então reiniciar o app não reprocessa
a pasta inteira.
"""
from __future__ import annotations

import json
import re
import shutil
import time
from pathlib import Path
from typing import Any, Callable

from core.userdata import USERDATA_DIR

ESTADO = USERDATA_DIR / "vigia.json"
FOTOS = {".jpg", ".jpeg", ".png", ".heic", ".webp", ".gif"}
FISCAL = (".pdf",)
_MESES = ("janeiro", "fevereiro", "marco", "abril", "maio", "junho", "julho",
          "agosto", "setembro", "outubro", "novembro", "dezembro")


def _carregar() -> dict[str, Any]:
    try:
        dados = json.loads(ESTADO.read_text(encoding="utf-8"))
        if isinstance(dados, dict):
            return dados
    except (OSError, ValueError):
        pass
    return {"pastas": [], "tratados": [], "acoes": []}


def _salvar(dados: dict[str, Any]) -> None:
    dados["tratados"] = dados.get("tratados", [])[-4000:]
    dados["acoes"] = dados.get("acoes", [])[-500:]
    try:
        ESTADO.parent.mkdir(parents=True, exist_ok=True)
        ESTADO.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass


def vigiar(pasta: Path | str) -> dict[str, Any]:
    """Adiciona uma pasta à lista (a mesma pasta não entra duas vezes)."""
    alvo = Path(pasta).expanduser()
    if not alvo.is_dir():
        raise NotADirectoryError(alvo)
    dados = _carregar()
    chave = str(alvo.resolve())
    if chave not in dados["pastas"]:
        dados["pastas"].append(chave)
        _salvar(dados)
    return {"pasta": chave, "pastas": dados["pastas"]}


def parar(pasta: Path | str | None = None) -> dict[str, Any]:
    dados = _carregar()
    if pasta is None:
        dados["pastas"] = []
    else:
        chave = str(Path(pasta).expanduser().resolve())
        dados["pastas"] = [p for p in dados["pastas"] if p != chave]
    _salvar(dados)
    return {"pastas": dados["pastas"]}


def pastas() -> list[str]:
    return list(_carregar().get("pastas") or [])


def _data_da_foto(arquivo: Path) -> tuple[int, int]:
    """Ano e mês da foto: EXIF quando existe, senão a data do arquivo."""
    try:
        from PIL import Image
        with Image.open(arquivo) as im:
            exif = im.getexif() or {}
            bruto = exif.get(36867) or exif.get(306)     # DateTimeOriginal / DateTime
        if bruto:
            partes = re.findall(r"\d+", str(bruto))
            if len(partes) >= 2:
                return int(partes[0]), int(partes[1])
    except Exception:
        pass
    carimbo = time.localtime(arquivo.stat().st_mtime)
    return carimbo.tm_year, carimbo.tm_mon


def _mes_do_texto(texto: str) -> tuple[int, int] | None:
    """Procura 'março/2026', '03/2026' ou '2026-03' no conteúdo."""
    baixo = texto.lower()
    for i, nome in enumerate(_MESES, 1):
        if nome in baixo:
            ano = re.search(r"(20\d{2})", baixo)
            if ano:
                return int(ano.group(1)), i
    achado = re.search(r"\b(0[1-9]|1[0-2])[/-](20\d{2})\b", baixo)
    if achado:
        return int(achado.group(2)), int(achado.group(1))
    achado = re.search(r"\b(20\d{2})-(0[1-9]|1[0-2])\b", baixo)
    if achado:
        return int(achado.group(1)), int(achado.group(2))
    return None


def _texto_do_pdf(arquivo: Path, limite: int = 4000) -> str:
    try:
        from pypdf import PdfReader
        leitor = PdfReader(str(arquivo))
        return "\n".join((pagina.extract_text() or "") for pagina in leitor.pages[:3])[:limite]
    except Exception:
        return ""


def organizar_foto(arquivo: Path, destino_raiz: Path | None = None) -> Path:
    ano, mes = _data_da_foto(arquivo)
    destino = (destino_raiz or arquivo.parent) / f"{ano}-{mes:02d}"
    destino.mkdir(parents=True, exist_ok=True)
    final = destino / arquivo.name
    if final.exists():
        final = destino / f"{arquivo.stem}-{int(arquivo.stat().st_mtime)}{arquivo.suffix}"
    shutil.move(str(arquivo), str(final))
    return final


def renomear_nota(arquivo: Path) -> Path | None:
    """Nota fiscal ganha data e valor no nome, quando dá para ler."""
    texto = _texto_do_pdf(arquivo)
    if not texto:
        return None
    mes = _mes_do_texto(texto)
    valor = re.search(r"R\$\s*([\d.]+,\d{2})", texto)
    pedacos = []
    if mes:
        pedacos.append(f"{mes[0]}-{mes[1]:02d}")
    if valor:
        pedacos.append(valor.group(1).replace(".", "").replace(",", "-"))
    if not pedacos:
        return None
    novo = arquivo.with_name("-".join(["nota"] + pedacos) + arquivo.suffix)
    if novo == arquivo or novo.exists():
        return None
    arquivo.rename(novo)
    return novo


def resumir_pdf(arquivo: Path, gerador: Callable[[str], str] | None = None) -> Path | None:
    texto = _texto_do_pdf(arquivo)
    if not texto.strip():
        return None
    resumo = ""
    if gerador is not None:
        try:
            resumo = (gerador(f"Resuma em até 5 linhas:\n{texto[:6000]}") or "").strip()
        except Exception:
            resumo = ""
    if not resumo:
        frases = re.split(r"(?<=[.!?])\s+", re.sub(r"\s+", " ", texto))
        resumo = " ".join(frases[:4]).strip()
    saida = arquivo.with_suffix(".resumo.txt")
    saida.write_text(resumo, encoding="utf-8")
    return saida


def varrer(gerador: Callable[[str], str] | None = None) -> dict[str, Any]:
    """Uma passada por todas as pastas vigiadas. Devolve o que fez."""
    dados = _carregar()
    tratados = set(dados.get("tratados") or [])
    feitas: list[dict[str, Any]] = []
    for chave in list(dados.get("pastas") or []):
        pasta = Path(chave)
        if not pasta.is_dir():
            continue
        for arquivo in sorted(p for p in pasta.iterdir() if p.is_file()):
            if str(arquivo) in tratados:
                continue
            sufixo = arquivo.suffix.lower()
            try:
                if sufixo in FOTOS:
                    final = organizar_foto(arquivo)
                    feitas.append({"acao": "foto organizada", "de": arquivo.name,
                                   "para": str(final)})
                elif sufixo in FISCAL:
                    novo = renomear_nota(arquivo)
                    alvo = novo or arquivo
                    resumo = resumir_pdf(alvo, gerador)
                    if novo or resumo:
                        feitas.append({"acao": "nota tratada", "arquivo": str(alvo),
                                       "renomeado": bool(novo),
                                       "resumo": str(resumo) if resumo else ""})
                        tratados.add(str(alvo))
                    else:
                        continue
                else:
                    continue
                tratados.add(str(arquivo))
            except Exception as exc:  # noqa: BLE001 - vigia não pode morrer
                feitas.append({"acao": "falhou", "arquivo": arquivo.name, "motivo": str(exc)})
                tratados.add(str(arquivo))
    dados["tratados"] = sorted(tratados)
    dados["acoes"] = (dados.get("acoes") or []) + feitas
    _salvar(dados)
    return {"tratados": len(feitas), "acoes": feitas}


def ultimas_acoes(limite: int = 20) -> list[dict[str, Any]]:
    return list(reversed(_carregar().get("acoes") or []))[:limite]
