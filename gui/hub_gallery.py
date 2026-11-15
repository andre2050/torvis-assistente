"""Lightweight native-Qt gallery for choosing a HUD appearance.

Previews are drawn locally with the same geometry renderer as the live HUB,
not remote screenshots; the gallery stays usable offline and requires no GPU.
"""
from __future__ import annotations

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QBrush, QColor, QPainter, QPen
from PyQt6.QtWidgets import QDialog, QGridLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget

from gui.hubs_realistic import HubVisualState, RealisticHubRenderer
from gui.style import px_font
from gui.theme import C, qcol

HUB_OPTIONS = (
    ("face", "Rosto Animado"), ("core", "Reator 3D"), ("reator", "Reator"),
    ("hexagono", "Hexágono"), ("prisma", "Prisma"), ("cubo", "Cubo"),
    ("iris", "Íris"), ("engrenagem", "Engrenagem"), ("atomo", "Átomo"),
    ("mandala", "Mandala"), ("espectro", "Espectro"), ("vortice", "Vórtice"),
)


class HubPreviewButton(QPushButton):
    def __init__(self, style: str, label: str, active: bool = False, parent=None):
        super().__init__(parent)
        self.hub_style, self.label, self.active = style, label, active
        self.setMinimumSize(150, 144)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName(f"HUB {label}" + (", selecionado" if active else ""))
        self.setToolTip(f"Selecionar HUB {label}")
        self._renderer = RealisticHubRenderer()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        q = qcol(C.PRI)
        hot = self.underMouse() or self.hasFocus()
        base = QRectF(2, 2, w - 4, h - 4)
        p.setBrush(QBrush(qcol(C.PANEL2 if hot or self.active else C.PANEL)))
        c = qcol(C.GREEN) if self.active else q
        c.setAlphaF(0.95 if hot or self.active else 0.48)
        p.setPen(QPen(c, 1.7 if hot or self.active else 1))
        p.drawRoundedRect(base, 12, 12)
        r = min(40, w * .28)
        cx, cy = w / 2, 60
        if not self._renderer.paint(p, cx, cy, r, self.hub_style, q, qcol(C.ACC), qcol(C.WHITE),
                                    HubVisualState(phase=0.7, amp=0.08, state="IDLE", speaking=False, muted=False)):
            # Minimal static fallback for the classic Reactor/Face styles.
            p.setPen(QPen(qcol(C.PRI), 2))
            p.setBrush(QBrush(qcol(C.PRI_GHO)))
            p.drawEllipse(QPointF(cx, cy), 37, 37)
            p.drawEllipse(QPointF(cx, cy), 24, 24)
            p.drawEllipse(QPointF(cx, cy), 10, 10)
            if self.hub_style == "face":
                p.setBrush(QBrush(qcol(C.WHITE)))
                p.drawEllipse(QPointF(cx - 10, cy - 5), 3, 3)
                p.drawEllipse(QPointF(cx + 10, cy - 5), 3, 3)
        p.setFont(px_font(12))
        p.setPen(QPen(qcol(C.WHITE)))
        p.drawText(QRectF(6, h-38, w-12, 18), Qt.AlignmentFlag.AlignCenter, self.label)
        p.setFont(px_font(9))
        p.setPen(QPen(qcol(C.GREEN if self.active else C.TEXT_DIM)))
        p.drawText(QRectF(6, h-21, w-12, 14), Qt.AlignmentFlag.AlignCenter,
                   "✓ SELECIONADO" if self.active else "CLIQUE PARA USAR")
        p.end()


class HubGalleryDialog(QDialog):
    """Pick a HUB without silently changing preferences on cancel/close."""
    def __init__(self, current: str, parent=None):
        super().__init__(parent)
        self.selected_style: str | None = None
        self.setWindowTitle("T.O.R.V.I.S. • Galeria de HUBs")
        self.setMinimumSize(560, 520)
        self.resize(680, 640)
        self.setStyleSheet(f"QDialog {{background:{C.BG};}} QLabel {{color:{C.TEXT};}}")
        column = QVBoxLayout(self)
        heading = QLabel("ESCOLHA SEU HUB")
        heading.setFont(px_font(20))
        heading.setStyleSheet(f"color:{C.PRI};")
        heading.setAccessibleName("Escolha seu HUB")
        column.addWidget(heading)
        hint = QLabel("Pré-visualização dos 12 estilos. Clique em um cartão para aplicar.")
        hint.setFont(px_font(12))
        column.addWidget(hint)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        holder = QWidget()
        layout = QGridLayout(holder)
        layout.setHorizontalSpacing(10)
        layout.setVerticalSpacing(10)
        for index, (style, label) in enumerate(HUB_OPTIONS):
            tile = HubPreviewButton(style, label, style == current)
            tile.clicked.connect(lambda checked=False, selection=style: self._choose(selection))
            layout.addWidget(tile, index // 3, index % 3)
        scroll.setWidget(holder)
        column.addWidget(scroll)

    def _choose(self, choice: str):
        self.selected_style = choice
        self.accept()
