"""Agente Autônomo controlado do T.O.R.V.I.S 2026 v5.4.0.

O agente não possui executor de shell próprio. Ele só pode usar ferramentas que
o I.S.A. já registrou e respeita confirmação por passo para ações sensíveis.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Iterable
import re
import uuid


_SENSITIVE = (
    "delete", "remove", "erase", "format", "apagar", "excluir", "remover", "formatar",
    "send", "enviar", "publish", "publicar", "purchase", "buy", "comprar", "pay", "pagamento",
    "password", "senha", "credential", "credencial", "shutdown", "desligar", "restart", "reiniciar",
)
_HIGH_RISK = ("format", "formatar", "purchase", "buy", "comprar", "pay", "pagamento", "credential", "credencial")


def avaliar_risco(ferramenta: str, argumentos: dict[str, Any] | None = None) -> str:
    texto = f"{ferramenta} {argumentos or {}}".casefold()
    if any(x in texto for x in _HIGH_RISK):
        return "alto"
    if any(x in texto for x in _SENSITIVE):
        return "medio"
    return "baixo"


@dataclass
class PassoPlano:
    ferramenta: str
    argumentos: dict[str, Any] = field(default_factory=dict)
    descricao: str = ""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    risco: str = "baixo"
    requer_confirmacao: bool = False

    def como_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PlanoExecucao:
    objetivo: str
    passos: list[PassoPlano]
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:10])
    status: str = "planejado"
    indice_atual: int = 0

    def como_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "objetivo": self.objetivo,
            "status": self.status,
            "indice_atual": self.indice_atual,
            "passos": [p.como_dict() for p in self.passos],
        }


class AgenteAutonomo:
    def __init__(self, max_passos: int = 12):
        self.max_passos = min(50, max(1, int(max_passos)))
        self.planos_criados = 0
        self.passos_executados = 0
        self.bloqueios = 0

    def criar_plano(self, objetivo: str, passos: Iterable[dict[str, Any] | PassoPlano]) -> PlanoExecucao:
        alvo = (objetivo or "").strip()
        if not alvo:
            raise ValueError("objetivo vazio")
        preparados = self.preparar_passos(passos)
        if not preparados:
            raise ValueError("plano sem passos")
        self.planos_criados += 1
        return PlanoExecucao(alvo, preparados)

    def preparar_passos(self, passos: Iterable[dict[str, Any] | PassoPlano]) -> list[PassoPlano]:
        """Valida, classifica o risco e marca confirmação de cada passo."""
        preparados: list[PassoPlano] = []
        for raw in list(passos)[: self.max_passos]:
            if isinstance(raw, PassoPlano):
                passo = raw
            elif isinstance(raw, dict):
                ferramenta = str(raw.get("ferramenta") or raw.get("tool") or "").strip()
                if not ferramenta or not re.match(r"^[A-Za-z_][A-Za-z0-9_]{0,63}$", ferramenta):
                    raise ValueError("ferramenta inválida no plano")
                args = dict(raw.get("argumentos") or raw.get("arguments") or {})
                passo = PassoPlano(
                    ferramenta=ferramenta,
                    argumentos=args,
                    descricao=str(raw.get("descricao") or raw.get("description") or "")[:300],
                )
            else:
                raise TypeError("passo deve ser dict ou PassoPlano")
            passo.risco = avaliar_risco(passo.ferramenta, passo.argumentos)
            passo.requer_confirmacao = passo.requer_confirmacao or passo.risco in {"medio", "alto"}
            preparados.append(passo)
        return preparados

    def executar_verificando(self, plano: PlanoExecucao, executor: Callable[[str, dict[str, Any]], Any], *,
                             verificar_fn: Callable[[str, dict[str, Any], Any], str],
                             replanejar_fn: Callable[[dict[str, Any], str, list[dict[str, Any]]], list] | None = None,
                             aprovacoes: Iterable[str] = (), max_replanos: int = 2) -> dict[str, Any]:
        """Planejar → agir → observar → ajustar.

        Depois de cada passo o resultado é verificado (`verificar_fn` devolve
        done | unverified | failed | ask | started). `failed` não é sucesso: se houver
        `replanejar_fn`, os passos que faltam são trocados por um caminho alternativo
        (até `max_replanos` vezes); senão o plano para dizendo por quê. `unverified`
        segue adiante, mas o passo sai marcado verificado=False para o agente dizer
        que não conseguiu confirmar em vez de afirmar "pronto"."""
        aprovadas = set(aprovacoes)
        resultados: list[dict[str, Any]] = []
        replanos = 0
        plano.status = "executando"
        i = plano.indice_atual
        while i < len(plano.passos):
            passo = plano.passos[i]
            plano.indice_atual = i
            if passo.requer_confirmacao and passo.id not in aprovadas:
                plano.status = "aguardando_confirmacao"
                self.bloqueios += 1
                return {"ok": False, "status": plano.status, "plano_id": plano.id,
                        "passo": passo.como_dict(), "resultados": resultados, "replanos": replanos}
            erro = ""
            valor: Any = None
            try:
                valor = executor(passo.ferramenta, dict(passo.argumentos))
                veredito = verificar_fn(passo.ferramenta, dict(passo.argumentos), valor)
                if veredito == "failed":
                    erro = str(valor)[:400]
            except Exception as exc:
                veredito, erro = "failed", str(exc)[:400]
            if veredito == "failed":
                novos: list = []
                if replanejar_fn is not None and replanos < max(0, int(max_replanos)):
                    replanos += 1
                    try:
                        novos = list(replanejar_fn(passo.como_dict(), erro, list(resultados)) or [])
                    except Exception:
                        novos = []
                    preparados = self.preparar_passos(novos) if novos else []
                    if preparados:
                        resultados.append({"passo_id": passo.id, "ok": False, "verificado": True,
                                           "resultado": erro, "replanejado": True})
                        plano.passos[i:] = preparados
                        continue
                plano.status = "falhou"
                resultados.append({"passo_id": passo.id, "ok": False, "verificado": True, "resultado": erro})
                return {"ok": False, "status": plano.status, "plano_id": plano.id, "erro": erro,
                        "passo": passo.como_dict(), "resultados": resultados, "replanos": replanos}
            if veredito == "ask":
                plano.status = "aguardando_resposta"
                resultados.append({"passo_id": passo.id, "ok": False, "verificado": True, "resultado": str(valor)[:1200]})
                return {"ok": False, "status": plano.status, "plano_id": plano.id,
                        "resultados": resultados, "replanos": replanos}
            self.passos_executados += 1
            resultados.append({"passo_id": passo.id, "ok": True, "verificado": veredito == "done",
                               "em_andamento": veredito == "started", "resultado": str(valor)[:1200]})
            i += 1
            plano.indice_atual = i
        plano.status = "concluido"
        return {"ok": True, "status": plano.status, "plano_id": plano.id,
                "resultados": resultados, "replanos": replanos}

    def executar(self, plano: PlanoExecucao, executor: Callable[[str, dict[str, Any]], Any],
                 *, aprovacoes: Iterable[str] = ()) -> dict[str, Any]:
        aprovadas = set(aprovacoes)
        resultados: list[dict[str, Any]] = []
        plano.status = "executando"

        for i in range(plano.indice_atual, len(plano.passos)):
            passo = plano.passos[i]
            plano.indice_atual = i
            if passo.requer_confirmacao and passo.id not in aprovadas:
                plano.status = "aguardando_confirmacao"
                self.bloqueios += 1
                return {
                    "ok": False,
                    "status": plano.status,
                    "plano_id": plano.id,
                    "passo": passo.como_dict(),
                    "resultados": resultados,
                }
            try:
                valor = executor(passo.ferramenta, dict(passo.argumentos))
            except Exception as exc:
                plano.status = "falhou"
                return {
                    "ok": False,
                    "status": plano.status,
                    "plano_id": plano.id,
                    "erro": str(exc),
                    "passo": passo.como_dict(),
                    "resultados": resultados,
                }

            # O executor pode retornar o resultado do I.S.A. com campo bloqueado.
            bloqueado = bool(getattr(valor, "bloqueado", False))
            if bloqueado:
                plano.status = "bloqueado"
                self.bloqueios += 1
                resultados.append({"passo_id": passo.id, "ok": False, "resultado": str(valor)})
                return {"ok": False, "status": plano.status, "plano_id": plano.id, "resultados": resultados}

            self.passos_executados += 1
            resultados.append({"passo_id": passo.id, "ok": True, "resultado": str(valor)[:1200]})
            plano.indice_atual = i + 1

        plano.status = "concluido"
        return {"ok": True, "status": plano.status, "plano_id": plano.id, "resultados": resultados}

    def status(self) -> dict[str, Any]:
        return {
            "ativo": True,
            "max_passos": self.max_passos,
            "planos_criados": self.planos_criados,
            "passos_executados": self.passos_executados,
            "bloqueios": self.bloqueios,
            "shell_arbitrario": False,
            "confirmacao_sensivel": True,
        }
