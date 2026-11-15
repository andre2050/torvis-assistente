"""Gerenciador neural lazy do T.O.R.V.I.S 2026."""
from __future__ import annotations

from .vision import VisaoNeural
from .sequence import MemoriaSequencial, RNNOpcional
from .reinforcement import AgenteSimulado
from .feedforward import ClassificadorDenso


class GerenciadorNeural:
    def __init__(self):
        self.memoria = MemoriaSequencial()
        self.simulador = AgenteSimulado()
        self._visao: VisaoNeural | None = None
        self._visao_base = VisaoNeural()

    def configurar_visao(self, caminho_modelo, rotulos=None, *, carregar=False):
        self._visao = VisaoNeural(caminho_modelo, rotulos)
        if carregar:
            self._visao.carregar()
        return self._visao

    @property
    def visao(self) -> VisaoNeural:
        """Visão configurada quando houver modelo; caso contrário, camada base."""
        return self._visao or self._visao_base

    def analisar_imagem(self, imagem) -> dict:
        analise = self.visao.analisar_imagem(imagem).como_dict()
        regioes = [r.como_dict() for r in self.visao.encontrar_elementos_interface(imagem)]
        return {"analise": analise, "elementos_interface": regioes}

    def detectar_objetos(self, imagem, **kwargs) -> list[dict]:
        if self._visao is None:
            raise RuntimeError("Configure um modelo ONNX antes de detectar objetos")
        if self._visao._net is None:
            self._visao.carregar()
        return [d.como_dict() for d in self._visao.detectar_objetos(imagem, **kwargs)]

    def status(self):
        return {
            "visao_configurada": self._visao is not None,
            "visao_base": True,
            "deteccao_onnx": _disponivel("cv2"),
            "rnn_disponivel": _disponivel("torch"),
            "cnn_opencv_disponivel": _disponivel("cv2"),
            "classificador_disponivel": _disponivel("torch"),
            "reforco": "simulacao",
            "eventos_memoria": len(self.memoria.eventos),
        }


def _disponivel(nome):
    from importlib.util import find_spec
    return find_spec(nome) is not None
