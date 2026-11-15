from memory.cognitive_memory import MemoriaCognitiva
from core.version import VERSAO
from actions.cognitive_memory import TOOL


def test_memoria_530_permanece_em_versoes_posteriores():
    assert tuple(map(int, VERSAO.split("."))) >= (5, 3, 0)


def test_memoria_cognitiva_ranqueia_e_esquece(tmp_path):
    m = MemoriaCognitiva(tmp_path / "memoria.json")
    baixa = m.lembrar("comprar leite", categoria="tarefas", importancia=0.2)
    alta = m.lembrar("projeto torvis usa núcleo I.S.A.", categoria="projetos", tags=["torvis"], importancia=0.95)
    res = m.buscar("torvis ISA")
    assert res and res[0]["id"] == alta.id
    assert m.esquecer(baixa.id) is True
    assert all(x["id"] != baixa.id for x in m.buscar("", tocar=False))


def test_memoria_nao_grava_automaticamente(tmp_path):
    m = MemoriaCognitiva(tmp_path / "memoria.json")
    assert m.status()["gravacao_automatica"] is False
    assert m.status()["registros"] == 0


def test_tool_cognitive_memory_disponivel():
    assert TOOL["name"] == "cognitive_memory"
    assert callable(TOOL["handler"])
