"""Memória de sequência limitada e inferência RNN opcional (PyTorch)."""
from collections import deque

class MemoriaSequencial:
    def __init__(self, capacidade=40):
        if capacidade < 1: raise ValueError("capacidade deve ser positiva")
        self.eventos = deque(maxlen=capacidade)

    def adicionar(self, evento):
        self.eventos.append(str(evento)[:500])

    def contexto(self):
        return tuple(self.eventos)

class RNNOpcional:
    def __init__(self, entrada, oculto, saida):
        import torch
        self.torch = torch
        self.rede = torch.nn.RNN(entrada, oculto, batch_first=True)
        self.cabeca = torch.nn.Linear(oculto, saida)

    def prever(self, sequencia):
        with self.torch.no_grad():
            saida, _ = self.rede(sequencia)
            return self.cabeca(saida[:, -1, :])
