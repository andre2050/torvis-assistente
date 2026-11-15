"""Rede densa opcional para classificação, sem treinamento implícito."""
class ClassificadorDenso:
    def __init__(self, entradas, classes, ocultas=32):
        import torch
        self.torch = torch
        self.modelo = torch.nn.Sequential(torch.nn.Linear(entradas, ocultas), torch.nn.ReLU(), torch.nn.Linear(ocultas, classes))

    def prever(self, dados):
        with self.torch.no_grad():
            return self.modelo(dados).argmax(dim=-1)
