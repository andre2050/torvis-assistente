from core.isa import NucleoISA

def test_interpretacao():
    assert NucleoISA().interpretar("Que horas são?").intencao == "pergunta"

def test_execucao():
    isa=NucleoISA()
    isa.registrar_ferramenta("eco",lambda texto="": texto)
    assert isa.executar("eco",texto="ok").resposta == "ok"
