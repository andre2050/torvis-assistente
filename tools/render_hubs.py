"""Renderiza os HUBs em PNG (ferramenta de desenvolvimento, sem interface).

Uso:  python tools/render_hubs.py antes.png
Serve para comparar o visual antes/depois de mexer no renderizador, e para
mostrar o resultado sem precisar de um Windows na frente.
"""
from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtGui import QColor, QFont, QImage, QLinearGradient, QPainter, QBrush
from PyQt6.QtWidgets import QApplication

from gui.hubs_realistic import HubVisualState, RealisticHubRenderer

LADO = 260          # tamanho de cada HUB na grade
COLUNAS = 3


def grade(destino: Path, tempo: float = 1.2, amp: float = 0.35) -> Path:
    app = QApplication.instance() or QApplication([])   # noqa: F841 (necessário para QImage)
    hubs = list(RealisticHubRenderer.supported)
    hubs.sort()
    linhas = (len(hubs) + COLUNAS - 1) // COLUNAS
    largura, altura = LADO * COLUNAS, LADO * linhas

    imagem = QImage(largura, altura, QImage.Format.Format_ARGB32)
    imagem.fill(QColor("#00060a"))
    p = QPainter(imagem)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    fundo = QLinearGradient(0, 0, largura, altura)     # fundo do app, não preto puro
    fundo.setColorAt(0.0, QColor("#000a12"))
    fundo.setColorAt(1.0, QColor("#00131c"))
    p.fillRect(0, 0, largura, altura, QBrush(fundo))

    renderer = RealisticHubRenderer()
    visual = HubVisualState(phase=tempo, amp=amp, state="OUVINDO", speaking=False, muted=False)
    fonte = QFont("Segoe UI", 9)

    for indice, estilo in enumerate(hubs):
        col, lin = indice % COLUNAS, indice // COLUNAS
        cx, cy = col * LADO + LADO / 2, lin * LADO + LADO / 2
        renderer.paint(p, cx, cy, LADO * 0.33, estilo,
                       QColor("#0a3a55"), QColor("#ff6b00"), QColor("#ffffff"), visual)
        p.setPen(QColor("#7fa6b8"))
        p.setFont(fonte)
        p.drawText(int(cx - 60), int(cy + LADO * 0.40), estilo.upper())

    p.end()
    destino.parent.mkdir(parents=True, exist_ok=True)
    imagem.save(str(destino))
    return destino


if __name__ == "__main__":
    saida = Path(sys.argv[1] if len(sys.argv) > 1 else "hubs.png")
    print(grade(saida).resolve())
