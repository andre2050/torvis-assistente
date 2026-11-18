"""Memória Cognitiva local do T.O.R.V.I.S 2026.

Armazena somente lembranças explicitamente registradas. A recuperação combina
relevância lexical, importância, recência e frequência de uso sem exigir rede,
embeddings ou dependências pesadas.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
import threading
from threading import RLock
from typing import Any, Iterable, Optional
import json
import math
import re
import time
import uuid

from core.paths import MEMORY_DIR

DEFAULT_PATH = MEMORY_DIR / "cognitive_memory.json"
_TOKEN_RE = re.compile(r"[\wÀ-ÿ]+", re.UNICODE)


def _agora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _tokens(texto: str) -> set[str]:
    return {x.casefold() for x in _TOKEN_RE.findall(texto or "") if len(x) > 1}


@dataclass
class Lembranca:
    id: str
    conteudo: str
    categoria: str = "geral"
    tags: list[str] = field(default_factory=list)
    importancia: float = 0.5
    criada_em: str = field(default_factory=_agora)
    atualizada_em: str = field(default_factory=_agora)
    ultimo_acesso: str = ""
    acessos: int = 0
    metadados: dict[str, Any] = field(default_factory=dict)

    def como_dict(self) -> dict[str, Any]:
        return asdict(self)


_PENDENTES: dict = {}
_TRAVA_GRAVACAO = RLock()
_ESCRITOR = None
_INTERVALO_GRAVACAO = 0.8


def _agendar_gravacao(caminho, dados) -> None:
    """Marca o arquivo como sujo; um escritor único despeja em lote."""
    global _ESCRITOR
    with _TRAVA_GRAVACAO:
        _PENDENTES[caminho] = dados
        if _ESCRITOR is None or not _ESCRITOR.is_alive():
            _ESCRITOR = threading.Thread(target=_laco_gravacao, name="memoria-disco",
                                         daemon=True)
            _ESCRITOR.start()


def _laco_gravacao(intervalo: float = _INTERVALO_GRAVACAO) -> None:
    while True:
        time.sleep(intervalo)
        with _TRAVA_GRAVACAO:
            lote = dict(_PENDENTES)
            _PENDENTES.clear()
        if not lote:
            continue
        for caminho, dados in lote.items():
            try:
                caminho.parent.mkdir(parents=True, exist_ok=True)
                tmp = caminho.with_suffix(caminho.suffix + ".tmp")
                tmp.write_text(json.dumps(dados, ensure_ascii=False, indent=2),
                               encoding="utf-8")
                tmp.replace(caminho)
            except OSError:
                with _TRAVA_GRAVACAO:
                    _PENDENTES[caminho] = dados


def descarregar_memoria(segundos: float = 3.0) -> bool:
    """Força a gravação pendente e espera. Usado ao fechar o aplicativo."""
    limite = time.time() + segundos
    while time.time() < limite:
        with _TRAVA_GRAVACAO:
            if not _PENDENTES:
                return True
        time.sleep(0.05)
    return False


class MemoriaCognitiva:
    """Store JSON pequeno, determinístico e seguro para memória explícita."""

    def __init__(self, caminho: str | Path | None = None, max_registros: int = 2000):
        self.caminho = Path(caminho) if caminho else DEFAULT_PATH
        self.max_registros = max(10, int(max_registros))
        self._lock = RLock()

    def _carregar(self) -> list[Lembranca]:
        if not self.caminho.exists():
            return []
        try:
            raw = json.loads(self.caminho.read_text(encoding="utf-8"))
            if not isinstance(raw, list):
                return []
            out: list[Lembranca] = []
            for item in raw:
                if not isinstance(item, dict) or not item.get("id") or not item.get("conteudo"):
                    continue
                out.append(Lembranca(
                    id=str(item["id"]),
                    conteudo=str(item["conteudo"]),
                    categoria=str(item.get("categoria") or "geral"),
                    tags=[str(x) for x in item.get("tags", []) if str(x).strip()],
                    importancia=float(item.get("importancia", 0.5)),
                    criada_em=str(item.get("criada_em") or _agora()),
                    atualizada_em=str(item.get("atualizada_em") or _agora()),
                    ultimo_acesso=str(item.get("ultimo_acesso") or ""),
                    acessos=int(item.get("acessos", 0)),
                    metadados=dict(item.get("metadados") or {}),
                ))
            return out
        except Exception:
            return []

    def _salvar(self, itens: Iterable[Lembranca]) -> None:
        """RAM na frente; disco depois, agrupado.

        O usuário não espera o disco para o assistente lembrar. A lista viva fica
        em memória e um escritor único junta as gravações próximas numa só, o que
        evita dezenas de reescritas quando ele dita várias lembranças seguidas.
        """
        dados = [x.como_dict() for x in itens]
        self._em_ram = dados
        _agendar_gravacao(self.caminho, dados)

    @staticmethod
    def _normalizar_importancia(valor: float) -> float:
        return min(1.0, max(0.0, float(valor)))

    def lembrar(self, conteudo: str, *, categoria: str = "geral", tags: Iterable[str] = (),
                importancia: float = 0.5, metadados: dict[str, Any] | None = None) -> Lembranca:
        texto = (conteudo or "").strip()
        if not texto:
            raise ValueError("conteúdo vazio")
        if len(texto) > 4000:
            texto = texto[:4000].rstrip() + "…"
        now = _agora()
        item = Lembranca(
            id=uuid.uuid4().hex[:12],
            conteudo=texto,
            categoria=(categoria or "geral").strip()[:60] or "geral",
            tags=sorted({str(t).strip().casefold() for t in tags if str(t).strip()})[:20],
            importancia=self._normalizar_importancia(importancia),
            criada_em=now,
            atualizada_em=now,
            metadados=dict(metadados or {}),
        )
        with self._lock:
            itens = self._carregar()
            itens.append(item)
            if len(itens) > self.max_registros:
                # Limpeza controlada: remove primeiro registros pouco importantes e pouco usados.
                itens.sort(key=lambda x: (x.importancia, x.acessos, x.atualizada_em))
                itens = itens[-self.max_registros:]
            self._salvar(itens)
        return item

    @staticmethod
    def _idade_dias(item: Lembranca) -> float:
        try:
            dt = datetime.fromisoformat(item.atualizada_em.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return max(0.0, (datetime.now(timezone.utc) - dt).total_seconds() / 86400.0)
        except Exception:
            return 365.0

    def _pontuar(self, item: Lembranca, consulta: str) -> float:
        q = _tokens(consulta)
        texto = _tokens(item.conteudo)
        meta = _tokens(item.categoria + " " + " ".join(item.tags))
        if q:
            inter_texto = len(q & texto) / max(1, len(q))
            inter_meta = len(q & meta) / max(1, len(q))
            frase = 1.0 if consulta.casefold() in item.conteudo.casefold() else 0.0
            relevancia = 0.62 * inter_texto + 0.23 * inter_meta + 0.15 * frase
            if relevancia <= 0:
                return 0.0
        else:
            relevancia = 0.35
        recencia = math.exp(-self._idade_dias(item) / 120.0)
        uso = min(1.0, math.log1p(max(0, item.acessos)) / math.log(8))
        return relevancia * 0.58 + item.importancia * 0.24 + recencia * 0.12 + uso * 0.06

    def buscar(self, consulta: str = "", *, limite: int = 8, tocar: bool = True) -> list[dict[str, Any]]:
        limite = min(50, max(1, int(limite)))
        with self._lock:
            itens = self._carregar()
            ranqueados = [(self._pontuar(x, consulta), x) for x in itens]
            ranqueados = [(s, x) for s, x in ranqueados if s > 0]
            ranqueados.sort(key=lambda p: (p[0], p[1].importancia, p[1].atualizada_em), reverse=True)
            escolhidos = ranqueados[:limite]
            if tocar and escolhidos:
                now = _agora()
                ids = {x.id for _, x in escolhidos}
                for item in itens:
                    if item.id in ids:
                        item.acessos += 1
                        item.ultimo_acesso = now
                self._salvar(itens)
            return [{**x.como_dict(), "pontuacao": round(s, 4)} for s, x in escolhidos]

    def esquecer(self, id_memoria: str) -> bool:
        alvo = (id_memoria or "").strip()
        if not alvo:
            return False
        with self._lock:
            itens = self._carregar()
            novos = [x for x in itens if x.id != alvo]
            if len(novos) == len(itens):
                return False
            self._salvar(novos)
            return True

    def contexto(self, consulta: str, *, limite: int = 5, max_chars: int = 1400) -> str:
        linhas = []
        usados = 0
        for item in self.buscar(consulta, limite=limite):
            linha = f"[{item['categoria']}] {item['conteudo']}"
            if usados + len(linha) + 1 > max_chars:
                break
            linhas.append(linha)
            usados += len(linha) + 1
        return "\n".join(linhas)

    def status(self) -> dict[str, Any]:
        with self._lock:
            itens = self._carregar()
        return {
            "ativo": True,
            "registros": len(itens),
            "limite": self.max_registros,
            "armazenamento": str(self.caminho),
            "gravacao_automatica": False,
        }
