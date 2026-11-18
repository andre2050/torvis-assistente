"""Cache de manifesto das ações: o boot não paga de novo o que não mudou.

A descoberta de ações importava todos os módulos de `actions/` a cada partida.
Com 34 ferramentas, isso custa tempo de import, leitura de disco e a chance de
um módulo quebrado derrubar a lista inteira antes de a janela aparecer.

Aqui fica só o que o modelo precisa saber sobre cada ferramenta: nome, descrição,
parâmetros e metadados de orçamento. O módulo em si só é importado quando a
ferramenta é chamada de verdade.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Optional

VERSAO_CACHE = 2
_NOME_ARQUIVO = "cache_acoes.json"


def caminho_do_cache(userdata_dir: Path) -> Path:
    return Path(userdata_dir) / _NOME_ARQUIVO


def assinatura(path: Path) -> list[int]:
    """Identidade barata de um arquivo: muda quando o conteúdo muda."""
    st = path.stat()
    return [int(st.st_mtime_ns), int(st.st_size)]


def carregar(userdata_dir: Path) -> dict[str, dict[str, Any]]:
    """Manifesto salvo na partida anterior, ou vazio se não servir."""
    caminho = caminho_do_cache(userdata_dir)
    try:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(dados, dict) or dados.get("versao") != VERSAO_CACHE:
        return {}
    arquivos = dados.get("arquivos")
    return arquivos if isinstance(arquivos, dict) else {}


def confere(path: Path, entrada: Optional[dict[str, Any]]) -> bool:
    """A entrada do cache ainda descreve este arquivo?"""
    if not isinstance(entrada, dict):
        return False
    try:
        if assinatura(path) != entrada.get("sig"):
            return False
    except OSError:
        return False
    obrigatorios = ("nome", "descricao", "parametros")
    return all(entrada.get(k) for k in obrigatorios)


def gravar(userdata_dir: Path, arquivos: dict[str, dict[str, Any]]) -> None:
    """Grava o manifesto de forma atômica; falhar aqui não pode atrapalhar o boot."""
    caminho = caminho_do_cache(userdata_dir)
    dados = {"versao": VERSAO_CACHE, "arquivos": arquivos}
    try:
        caminho.parent.mkdir(parents=True, exist_ok=True)
        tmp = caminho.with_suffix(caminho.suffix + ".tmp")
        tmp.write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, caminho)
    except OSError:
        pass


def entrada_de(path: Path, rec) -> dict[str, Any]:
    """Resumo de um ActionRecord pronto para o próximo boot."""
    return {
        "sig": assinatura(path),
        "nome": rec.name,
        "descricao": rec.description,
        "parametros": rec.parameters,
        "tier": rec.tier,
        "behavior": rec.behavior,
        "brief": rec.brief,
        "scheduling": getattr(rec, "scheduling", None),
    }
