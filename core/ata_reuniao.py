"""Ata de reunião: gravação entra, decisões e tarefas saem.

O caminho é curto de propósito: transcrever, e depois pedir ao modelo a leitura
que interessa a quem faltou — o que foi decidido, quem ficou de fazer o quê e
quando. Sem modelo disponível, ainda entrega uma ata útil: transcrição com
marcas de tempo, participantes identificados pelas falas e os trechos que
parecem tarefa, encontrados por palavra-chave.

Gravar do microfone é opcional: se não houver dispositivo, aceita o arquivo de
áudio que a pessoa já tem (gravou no celular, na chamada, no Teams).
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Callable

from core.userdata import USERDATA_DIR

PASTA_ATAS = Path.home() / "Documents" / "TORVIS" / "atas"
ARQUIVO_INDICE = USERDATA_DIR / "atas.json"

_PALAVRAS_TAREFA = ("vou ", "vamos ", "fico de", "ficou de", "fazer", "enviar",
                    "mandar", "revisar", "preparar", "até sexta", "até segunda",
                    "amanhã", "prazo", "responsável", "encaminhar", "checar")
_PALAVRAS_DECISAO = ("decidimos", "ficou decidido", "aprovado", "vamos com",
                     "fechado", "definido", "optamos", "escolhemos")


def _limpar(texto: str) -> str:
    return re.sub(r"\s+", " ", str(texto or "")).strip()


def falantes(transcricao: str) -> list[str]:
    """Nomes que aparecem como "Fulano:" no começo das falas."""
    nomes: list[str] = []
    for linha in str(transcricao or "").splitlines():
        achado = re.match(r"\s*([A-ZÁÉÍÓÚÂÊÔÃÕÇ][\wÁÉÍÓÚÂÊÔÃÕÇáéíóúâêôãõç]{1,20})\s*:", linha)
        if achado and achado.group(1) not in nomes:
            nomes.append(achado.group(1))
    return nomes


def trechos(transcricao: str, palavras: tuple[str, ...]) -> list[str]:
    """Frases que contêm alguma das palavras — a matéria-prima sem modelo."""
    frases = re.split(r"(?<=[.!?])\s+|\n", str(transcricao or ""))
    achados = []
    for frase in frases:
        limpa = _limpar(frase)
        if len(limpa) < 12:
            continue
        baixa = limpa.lower()
        if any(p in baixa for p in palavras) and limpa not in achados:
            achados.append(limpa)
    return achados[:12]


def ata_sem_modelo(transcricao: str, titulo: str = "Reunião") -> dict[str, Any]:
    """Ata montada por regra: participantes, decisões e tarefas prováveis."""
    decisoes = trechos(transcricao, _PALAVRAS_DECISAO)
    # uma decisão também casa com as palavras de tarefa ("vamos com o plano A"),
    # e aparecer nos dois lugares deixa a ata confusa
    tarefas = [t for t in trechos(transcricao, _PALAVRAS_TAREFA) if t not in decisoes]
    return {
        "titulo": titulo,
        "participantes": falantes(transcricao),
        "decisoes": decisoes,
        "tarefas": tarefas,
        "transcricao": _limpar(transcricao),
        "gerado_por": "regras",
    }


def ata_com_modelo(transcricao: str, titulo: str, gerador: Callable[[str], str]) -> dict[str, Any]:
    """Pede ao modelo um resumo estruturado; se ele falhar, cai nas regras."""
    pedido = (
        "Leia a transcrição de uma reunião e responda SÓ com JSON, sem comentário:\n"
        '{"resumo": "até 5 linhas", "decisoes": ["..."], "tarefas": '
        '[{"quem": "nome ou \'\'", "o_que": "...", "quando": "prazo ou \'\'"}]}\n\n'
        f"Transcrição:\n{transcricao[:12000]}"
    )
    try:
        bruto = gerador(pedido) or ""
        inicio, fim = bruto.find("{"), bruto.rfind("}")
        dados = json.loads(bruto[inicio:fim + 1])
        if not isinstance(dados, dict):
            raise ValueError("resposta não é objeto")
    except Exception:
        return ata_sem_modelo(transcricao, titulo)
    return {
        "titulo": titulo,
        "participantes": falantes(transcricao),
        "resumo": _limpar(dados.get("resumo")),
        "decisoes": [str(d) for d in dados.get("decisoes") or []][:20],
        "tarefas": [t if isinstance(t, dict) else {"quem": "", "o_que": str(t), "quando": ""}
                    for t in dados.get("tarefas") or []][:30],
        "transcricao": _limpar(transcricao),
        "gerado_por": "modelo",
    }


def em_markdown(ata: dict[str, Any]) -> str:
    linhas = [f"# {ata.get('titulo') or 'Reunião'}", ""]
    if ata.get("participantes"):
        linhas += ["**Participantes:** " + ", ".join(ata["participantes"]), ""]
    if ata.get("resumo"):
        linhas += ["## Resumo", ata["resumo"], ""]
    if ata.get("decisoes"):
        linhas += ["## Decisões"] + [f"- {d}" for d in ata["decisoes"]] + [""]
    if ata.get("tarefas"):
        linhas += ["## Tarefas"]
        for t in ata["tarefas"]:
            if isinstance(t, dict):
                quem = f"{t.get('quem')}: " if t.get("quem") else ""
                quando = f" (até {t['quando']})" if t.get("quando") else ""
                linhas.append(f"- [ ] {quem}{t.get('o_que', '')}{quando}")
            else:
                linhas.append(f"- [ ] {t}")
        linhas.append("")
    if ata.get("transcricao"):
        linhas += ["## Transcrição", ata["transcricao"], ""]
    linhas.append(f"_Gerado pelo TORVIS em {time.strftime('%d/%m/%Y %H:%M')}._")
    return "\n".join(linhas)


def salvar(ata: dict[str, Any], pasta: Path | None = None) -> Path:
    destino = Path(pasta or PASTA_ATAS)
    destino.mkdir(parents=True, exist_ok=True)
    nome = re.sub(r"[^\w\- ]+", "", str(ata.get("titulo") or "reuniao")).strip() or "reuniao"
    arquivo = destino / f"{time.strftime('%Y-%m-%d')}-{nome.replace(' ', '-').lower()}.md"
    arquivo.write_text(em_markdown(ata), encoding="utf-8")
    _registrar(arquivo, ata)
    return arquivo


def _registrar(arquivo: Path, ata: dict[str, Any]) -> None:
    try:
        historico = json.loads(ARQUIVO_INDICE.read_text(encoding="utf-8"))
        if not isinstance(historico, list):
            historico = []
    except (OSError, ValueError):
        historico = []
    historico.append({"arquivo": str(arquivo), "titulo": ata.get("titulo"),
                      "quando": time.time(), "tarefas": len(ata.get("tarefas") or [])})
    try:
        ARQUIVO_INDICE.parent.mkdir(parents=True, exist_ok=True)
        ARQUIVO_INDICE.write_text(json.dumps(historico[-100:], ensure_ascii=False, indent=2),
                                  encoding="utf-8")
    except OSError:
        pass


def ultimas(limite: int = 10) -> list[dict[str, Any]]:
    try:
        dados = json.loads(ARQUIVO_INDICE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return list(reversed(dados))[:limite] if isinstance(dados, list) else []


def transcrever_audio(caminho: Path | str) -> str:
    """Transcreve um arquivo de áudio com o que estiver instalado.

    Reaproveita o faster-whisper que a secretária do WhatsApp já usa, para não
    baixar um segundo modelo.
    """
    from core import whatsapp as wa

    arquivo = Path(caminho).expanduser()
    if not arquivo.is_file():
        raise FileNotFoundError(arquivo)
    modelo = wa._modelo_de_transcricao()          # noqa: SLF001 - mesma instância
    segmentos, _info = modelo.transcribe(str(arquivo), language="pt")
    return " ".join(seg.text.strip() for seg in segmentos).strip()


def gerar(transcricao: str, titulo: str = "Reunião",
          gerador: Callable[[str], str] | None = None,
          pasta: Path | None = None) -> dict[str, Any]:
    """Fecha o ciclo: transcrição → ata → arquivo markdown."""
    if not _limpar(transcricao):
        raise ValueError("transcrição vazia: não há o que resumir")
    ata = (ata_com_modelo(transcricao, titulo, gerador) if gerador
           else ata_sem_modelo(transcricao, titulo))
    arquivo = salvar(ata, pasta)
    return {"ata": ata, "arquivo": str(arquivo), "tarefas": len(ata.get("tarefas") or [])}
