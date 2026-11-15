"""Renderiza um HUB em tamanho grande, para inspeção visual."""
import sys
from pathlib import Path
RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QImage, QPainter, QRadialGradient, QBrush
from PyQt6.QtWidgets import QApplication
from gui.hubs_realistic import HubVisualState, RealisticHubRenderer

estilo = sys.argv[1] if len(sys.argv) > 1 else "hexagono"
saida = Path(sys.argv[2] if len(sys.argv) > 2 else f"hub_{estilo}.png")
LADO = 760
app = QApplication.instance() or QApplication([])
img = QImage(LADO, LADO, QImage.Format.Format_ARGB32)
img.fill(QColor("#00060a"))
p = QPainter(img)
p.setRenderHint(QPainter.RenderHint.Antialiasing)
fundo = QRadialGradient(LADO/2, LADO/2, LADO*0.75)
fundo.setColorAt(0.0, QColor("#00202e")); fundo.setColorAt(1.0, QColor("#00060a"))
p.fillRect(0, 0, LADO, LADO, QBrush(fundo))
visual = HubVisualState(phase=1.4, amp=0.55, state="OUVINDO", speaking=True, muted=False)
RealisticHubRenderer().paint(p, LADO/2, LADO/2, LADO*0.30, estilo,
                             QColor("#0a3a55"), QColor("#ff6b00"), QColor("#ffffff"), visual)
p.end(); img.save(str(saida)); print(saida.resolve())
