"""Inteligência Adaptativa do T.O.R.V.I.S 2026 v5.5.0.

Roteia capacidades disponíveis segundo recursos do computador e preferência do
usuário. O roteador recomenda/seleciona; não envia dados nem instala modelos por
conta própria.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from threading import RLock
from typing import Any


@dataclass(frozen=True)
class RecursosSistema:
    cpu_percent: float = 0.0
    memoria_percent: float = 0.0
    gpu_disponivel: bool = False
    bateria: bool = False

    def como_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MotorCandidato:
    nome: str
    modalidade: str
    local: bool
    qualidade: float
    latencia: float
    ram_mb: int
    requer_gpu: bool = False
    disponivel: bool = True

    def como_dict(self) -> dict[str, Any]:
        return asdict(self)


class InteligenciaAdaptativa:
    MODOS = {"eco", "equilibrado", "desempenho", "privacidade"}

    def __init__(self, modo: str = "equilibrado"):
        self._lock = RLock()
        self._motores: dict[str, MotorCandidato] = {}
        self.modo = "equilibrado"
        self.selecoes = 0
        self.ultimo: dict[str, Any] | None = None
        self.definir_modo(modo)

    def definir_modo(self, modo: str) -> str:
        valor = (modo or "equilibrado").strip().casefold()
        if valor not in self.MODOS:
            raise ValueError(f"modo inválido: {modo}")
        self.modo = valor
        return self.modo

    def registrar(self, motor: MotorCandidato) -> None:
        if not motor.nome or not motor.modalidade:
            raise ValueError("motor inválido")
        with self._lock:
            self._motores[motor.nome] = motor

    def listar(self, modalidade: str | None = None) -> list[dict[str, Any]]:
        with self._lock:
            itens = list(self._motores.values())
        if modalidade:
            itens = [x for x in itens if x.modalidade == modalidade]
        return [x.como_dict() for x in itens]

    @staticmethod
    def recursos_atuais() -> RecursosSistema:
        try:
            import psutil
            cpu = float(psutil.cpu_percent(interval=None))
            mem = float(psutil.virtual_memory().percent)
            bateria = bool(getattr(psutil.sensors_battery(), "power_plugged", True) is False) if hasattr(psutil, "sensors_battery") else False
        except Exception:
            cpu, mem, bateria = 0.0, 0.0, False
        gpu = False
        try:
            import cv2
            gpu = bool(hasattr(cv2, "cuda") and cv2.cuda.getCudaEnabledDeviceCount() > 0)
        except Exception:
            pass
        return RecursosSistema(cpu, mem, gpu, bateria)

    def _viavel(self, motor: MotorCandidato, r: RecursosSistema) -> bool:
        if not motor.disponivel:
            return False
        if motor.requer_gpu and not r.gpu_disponivel:
            return False
        # Em pressão extrema de memória, evita motores declarados pesados.
        if r.memoria_percent >= 92 and motor.ram_mb >= 900:
            return False
        if self.modo == "privacidade" and not motor.local:
            return False
        return True

    def _score(self, m: MotorCandidato, r: RecursosSistema) -> float:
        qualidade = max(0.0, min(1.0, float(m.qualidade)))
        latencia = max(0.0, min(1.0, float(m.latencia)))  # 0 = rápido, 1 = lento
        rapidez = 1.0 - latencia
        leveza = 1.0 - min(1.0, m.ram_mb / 2500.0)
        local = 1.0 if m.local else 0.0

        if self.modo == "eco":
            score = 0.20 * qualidade + 0.32 * rapidez + 0.38 * leveza + 0.10 * local
        elif self.modo == "desempenho":
            score = 0.62 * qualidade + 0.22 * rapidez + 0.08 * leveza + 0.08 * local
        elif self.modo == "privacidade":
            score = 0.44 * qualidade + 0.20 * rapidez + 0.16 * leveza + 0.20 * local
        else:
            score = 0.42 * qualidade + 0.27 * rapidez + 0.21 * leveza + 0.10 * local

        # Pressão de recursos torna soluções pesadas menos atraentes.
        pressao = max(r.cpu_percent, r.memoria_percent) / 100.0
        score -= pressao * min(0.28, m.ram_mb / 9000.0)
        if r.bateria and m.ram_mb > 700:
            score -= 0.08
        return score

    def selecionar(self, modalidade: str, recursos: RecursosSistema | None = None) -> dict[str, Any]:
        r = recursos or self.recursos_atuais()
        with self._lock:
            candidatos = [m for m in self._motores.values() if m.modalidade == modalidade and self._viavel(m, r)]
        if not candidatos:
            resultado = {"ok": False, "modalidade": modalidade, "motivo": "nenhum motor viável", "recursos": r.como_dict()}
            self.ultimo = resultado
            return resultado
        ordenados = sorted(candidatos, key=lambda m: (self._score(m, r), m.qualidade, -m.latencia), reverse=True)
        escolhido = ordenados[0]
        self.selecoes += 1
        resultado = {
            "ok": True,
            "modalidade": modalidade,
            "modo": self.modo,
            "escolhido": escolhido.como_dict(),
            "pontuacao": round(self._score(escolhido, r), 4),
            "recursos": r.como_dict(),
            "alternativas": [m.nome for m in ordenados[1:4]],
        }
        self.ultimo = resultado
        return resultado

    def status(self) -> dict[str, Any]:
        return {
            "ativo": True,
            "modo": self.modo,
            "motores": len(self._motores),
            "selecoes": self.selecoes,
            "envio_automatico_dados": False,
            "instalacao_automatica_modelos": False,
            "ultimo": self.ultimo,
        }


def criar_padrao(modo: str = "equilibrado") -> InteligenciaAdaptativa:
    a = InteligenciaAdaptativa(modo)
    # Capacidades já existentes ou previstas no projeto. O roteador não afirma
    # que um modelo externo está instalado; candidatos opcionais ficam indisponíveis.
    a.registrar(MotorCandidato("isa_regras", "texto", True, 0.45, 0.05, 35, disponivel=True))
    a.registrar(MotorCandidato("visao_base", "visao", True, 0.48, 0.08, 120, disponivel=True))
    a.registrar(MotorCandidato("visao_onnx_cpu", "visao", True, 0.82, 0.38, 520, disponivel=True))
    a.registrar(MotorCandidato("rnn_opcional", "sequencia", True, 0.72, 0.42, 750, disponivel=_tem_modulo("torch")))
    a.registrar(MotorCandidato("classificador_denso", "classificacao", True, 0.74, 0.40, 720, disponivel=_tem_modulo("torch")))
    return a


def _tem_modulo(nome: str) -> bool:
    try:
        from importlib.util import find_spec
        return find_spec(nome) is not None
    except Exception:
        return False


_adaptativo_global: InteligenciaAdaptativa | None = None


def obter_adaptativo() -> InteligenciaAdaptativa:
    global _adaptativo_global
    if _adaptativo_global is None:
        _adaptativo_global = criar_padrao()
    return _adaptativo_global
