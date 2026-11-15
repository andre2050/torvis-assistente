from core.isa import NucleoISA
from neural.sequence import MemoriaSequencial
from neural.reinforcement import AgenteSimulado
from neural.vision import VisaoNeural
from neural.manager import GerenciadorNeural
import pytest

def test_integracao_isa():
    isa=NucleoISA()
    assert isa.estado()["neural"]["reforco"] == "simulacao"
    assert isa.interpretar("Que horas são?").intencao == "pergunta"

def test_memoria_limite():
    m=MemoriaSequencial(2)
    for i in range(3):m.adicionar(i)
    assert m.contexto()==("1","2")

def test_reforco_nao_executa():
    a=AgenteSimulado(taxa=0.5)
    assert a.aprender("s","a",2,"fim") == 1.0
    assert a.escolher("s",["a","b"]) == "a"

def test_visao_exige_modelo():
    with pytest.raises(FileNotFoundError): VisaoNeural().carregar()

def test_status_sem_dependencias():
    assert GerenciadorNeural().status()["visao_configurada"] is False
