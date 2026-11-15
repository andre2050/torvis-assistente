from core.adaptive_intelligence import InteligenciaAdaptativa, MotorCandidato, RecursosSistema
from core.version import VERSAO
from actions.adaptive_intelligence import TOOL


def test_versao_550():
    assert tuple(map(int, VERSAO.split("."))) >= (5, 5, 0)


def _roteador(modo="equilibrado"):
    r = InteligenciaAdaptativa(modo)
    r.registrar(MotorCandidato("leve", "texto", True, 0.55, 0.05, 80))
    r.registrar(MotorCandidato("pesado", "texto", True, 0.96, 0.35, 1800))
    r.registrar(MotorCandidato("nuvem", "texto", False, 0.99, 0.20, 50))
    return r


def test_privacidade_rejeita_remoto():
    r = _roteador("privacidade")
    e = r.selecionar("texto", RecursosSistema(20, 20, False, False))
    assert e["ok"] is True
    assert e["escolhido"]["local"] is True


def test_pressao_memoria_remove_motor_pesado():
    r = _roteador("desempenho")
    e = r.selecionar("texto", RecursosSistema(40, 95, False, False))
    assert e["escolhido"]["nome"] != "pesado"


def test_modo_eco_prefere_solucao_leve_local():
    r = _roteador("eco")
    e = r.selecionar("texto", RecursosSistema(70, 75, False, True))
    assert e["escolhido"]["nome"] == "leve"


def test_tool_adaptativo_disponivel():
    assert TOOL["name"] == "adaptive_intelligence"
