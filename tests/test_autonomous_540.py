from core.autonomous_agent import AgenteAutonomo, avaliar_risco
from core.isa import NucleoISA
from core.version import VERSAO
from actions.autonomous_planner import TOOL


def test_agente_540_permanece_em_versoes_posteriores():
    assert tuple(map(int, VERSAO.split("."))) >= (5, 4, 0)


def test_risco_sensivel_exige_confirmacao():
    a = AgenteAutonomo()
    plano = a.criar_plano("limpar", [{"tool": "delete_file", "arguments": {"path": "x"}}])
    assert plano.passos[0].requer_confirmacao is True
    assert avaliar_risco("delete_file", {}) == "medio"
    r = a.executar(plano, lambda *_: "não deveria rodar")
    assert r["status"] == "aguardando_confirmacao"


def test_plano_seguro_executa_ferramenta_registrada():
    isa = NucleoISA()
    isa.registrar_ferramenta("eco", lambda texto="": texto.upper())
    plano = isa.criar_plano("ecoar", [{"tool": "eco", "arguments": {"texto": "ok"}}])
    r = isa.executar_plano(plano)
    assert r["ok"] is True
    assert r["status"] == "concluido"
    assert "OK" in r["resultados"][0]["resultado"]


def test_plano_sensivel_roda_so_com_id_aprovado():
    a = AgenteAutonomo()
    plano = a.criar_plano("enviar", [{"tool": "send_message", "arguments": {"text": "oi"}}])
    chamado = []
    r = a.executar(plano, lambda nome, args: chamado.append((nome, args)) or "ok", aprovacoes=[plano.passos[0].id])
    assert r["ok"] is True
    assert chamado


def test_tool_planner_disponivel():
    assert TOOL["name"] == "autonomous_planner"
