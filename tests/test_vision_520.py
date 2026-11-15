import numpy as np

from core.version import VERSAO
from neural.vision import VisaoNeural
from actions.vision_intelligence import TOOL


def test_visao_520_permanece_em_versoes_posteriores():
    assert tuple(map(int, VERSAO.split("."))) >= (5, 2, 0)


def test_analise_imagem_basica():
    img = np.zeros((40, 60, 3), dtype=np.uint8)
    img[:, 30:] = 220
    r = VisaoNeural().analisar_imagem(img)
    assert r.largura == 60
    assert r.altura == 40
    assert r.canais == 3
    assert 90 <= r.luminosidade <= 130
    assert r.contraste > 80
    assert r.densidade_bordas > 0


def test_template_matching_localiza_padrao():
    cena = np.zeros((32, 40), dtype=np.uint8)
    template = np.array([
        [0, 40, 80, 120],
        [30, 70, 110, 150],
        [60, 100, 140, 180],
    ], dtype=np.uint8)
    cena[11:14, 17:21] = template
    encontrados = VisaoNeural().localizar_template(cena, template, limiar=0.99)
    assert encontrados
    melhor = encontrados[0]
    assert (melhor["x"], melhor["y"]) == (17, 11)
    assert melhor["confianca"] >= 0.99


def test_decodifica_yolov8_e_aplica_nms():
    # x_center, y_center, width, height, score classe0, score classe1
    saida = np.array([[
        [320, 320, 200, 100, 0.90, 0.10],
        [322, 321, 198, 102, 0.82, 0.18],
        [100, 100, 50, 50, 0.05, 0.93],
    ]], dtype=np.float32)
    v = VisaoNeural(rotulos=["pessoa", "carro"])
    det = v.decodificar_saida(
        saida,
        formato_original=(640, 640),
        tamanho_entrada=(640, 640),
        confianca_minima=0.35,
        iou_maximo=0.45,
    )
    assert len(det) == 2
    assert det[0].classe == "carro"  # 0.93 > 0.90
    assert {d.classe for d in det} == {"pessoa", "carro"}


def test_detector_formato_final_n6():
    saida = np.array([[10, 20, 50, 70, 0.88, 2]], dtype=np.float32)
    v = VisaoNeural(rotulos=["a", "b", "janela"])
    det = v.decodificar_saida(
        saida,
        formato_original=(100, 100),
        tamanho_entrada=(100, 100),
        confianca_minima=0.5,
    )
    assert len(det) == 1
    assert det[0].classe == "janela"
    assert det[0].largura == 40
    assert det[0].altura == 50


def test_tool_visual_registravel():
    assert TOOL["name"] == "vision_intelligence"
    assert callable(TOOL["handler"])
    assert TOOL["parameters"]["type"] == "OBJECT"
