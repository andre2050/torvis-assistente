"""Aprendizado por reforço tabular somente em simulação; não executa ações reais."""
class AgenteSimulado:
    def __init__(self, taxa=0.1, desconto=0.9):
        if not (0 < taxa <= 1 and 0 <= desconto <= 1):
            raise ValueError("hiperparâmetros inválidos")
        self.taxa, self.desconto = taxa, desconto
        self.q = {}

    def valor(self, estado, acao):
        return self.q.get((estado, acao), 0.0)

    def aprender(self, estado, acao, recompensa, proximo_estado, proximas_acoes=()):
        futuro = max((self.valor(proximo_estado, a) for a in proximas_acoes), default=0.0)
        anterior = self.valor(estado, acao)
        novo = anterior + self.taxa * (float(recompensa) + self.desconto * futuro - anterior)
        self.q[(estado, acao)] = novo
        return novo

    def escolher(self, estado, acoes):
        if not acoes: raise ValueError("nenhuma ação simulada")
        return max(acoes, key=lambda a: self.valor(estado, a))
