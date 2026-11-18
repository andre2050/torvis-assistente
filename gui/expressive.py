"""T.O.R.V.I.S dock v5.8 — expressively painted, keyboard-accessible controls.

No extra dependencies or background timers. Animates only while pointer enters/leaves;
all actions continue to use normal QPushButton.clicked and existing slots.
"""
from __future__ import annotations

from PyQt6.QtCore import QEasingCurve, QRectF, Qt, QVariantAnimation
from PyQt6.QtGui import QColor, QBrush, QFont, QLinearGradient, QPainter, QPen
from PyQt6.QtWidgets import QPushButton, QSizePolicy, QStyleOptionButton

from gui.theme import C, qcol
from gui.style import px_font, sombra_suave, brilho_topo, superficie_realista


class ExpressiveDockButton(QPushButton):
    """Three-line status tile which reflects live state and supports focus/hover.

    Text contract remains `KEY\nLabel\nStatus` so existing toolbar updates work.
    The visual mode is explicit; *disabled* is not confused with an error state.
    """
    MODES = frozenset({"on", "dim", "primary", "purple", "danger", "warning"})

    def __init__(self, text: str, kind: str = "primary", parent=None):
        super().__init__(text, parent)
        self._mode = kind if kind in self.MODES else "primary"
        self._glow = 0.0
        self.setMinimumHeight(82)
        self.setMaximumHeight(98)
        self.setMinimumWidth(92)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAutoDefault(False) if hasattr(self, "setAutoDefault") else None
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(150)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.valueChanged.connect(self._on_glow)
        self._update_accessibility()

    def _update_accessibility(self):
        self.setAccessibleName(" — ".join(part.strip() for part in self.text().splitlines() if part.strip()))
        self.setAccessibleDescription(self.toolTip() or "Controle do TORVIS")

    def setText(self, value):  # noqa: N802 - QPushButton method signature
        super().setText(str(value or ""))
        self._update_accessibility()
        self.update()

    def set_visual_mode(self, kind: str):
        self._mode = kind if kind in self.MODES else "primary"
        self.update()

    def setToolTip(self, value):  # noqa: N802
        super().setToolTip(value)
        self._update_accessibility()

    def _on_glow(self, value):
        self._glow = float(value)
        self.update()

    def _animate_to(self, target: float):
        self._anim.stop()
        self._anim.setStartValue(self._glow)
        self._anim.setEndValue(float(target))
        if self.isVisible() and self.isEnabled():
            self._anim.start()
        else:
            self._glow = float(target)
            self.update()

    def enterEvent(self, event):
        self._animate_to(1.0)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._animate_to(0.0)
        super().leaveEvent(event)

    def focusInEvent(self, event):
        super().focusInEvent(event)
        self.update()

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        self.update()

    def changeEvent(self, event):
        super().changeEvent(event)
        self.update()

    def _accent(self) -> QColor:
        return {
            "on": qcol(C.GREEN),
            "danger": qcol(C.RED),
            "warning": qcol(C.ACC),
            "purple": QColor("#c38aff"),
            "dim": qcol(C.TEXT_MED),
        }.get(self._mode, qcol(C.PRI))

    def paintEvent(self, event):
        w, h = self.width(), self.height()
        if w < 6 or h < 6:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        enabled = self.isEnabled()
        highlight = self._glow if enabled else 0.0
        if self.isDown():
            highlight = 1.0
        acento = self._accent() if enabled else qcol(C.TEXT_DIM)
        # Minimal Pro: a neutral tile, a hairline edge and one accent detail.
        # The old version outlined each tile in its own colour, so the dock read
        # as seven competing buttons; the colour now lives in a dot and a rail.
        base = QRectF(2.0, 2.0 + (1.5 if self.isDown() else 0.0), w - 4.0, h - 6.0)

        def translucent(col, alpha):
            cc = QColor(col)
            cc.setAlphaF(max(0.0, min(1.0, alpha)))
            return cc

        _raio = float(getattr(C, "RAIO_CAMPO", 11)) - 1
        superficie_realista(painter, base, raio=_raio, elevacao=1.0,
                            topo=qcol(C.PANEL2).lighter(104 + int(highlight * 10)))
        if highlight > 0.5:
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(qcol(C.BORDER_B), 1.0))
            painter.drawRoundedRect(base, _raio, _raio)

        # O detalhe de acento: ponto de estado e trilho curto embaixo.
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(translucent(acento, 0.90 if enabled else 0.35))
        painter.drawEllipse(QRectF(w - 15, 13, 5, 5))
        painter.setBrush(translucent(acento, 0.40 + 0.45 * highlight))
        painter.drawRoundedRect(QRectF(12, h - 8, max(0.0, (w - 24) * (0.28 + 0.55 * highlight)), 2.0), 1.0, 1.0)

        parts = (self.text().splitlines() + ["", "", ""])[:3]
        key, title, status = [part.strip() for part in parts]
        if not title:
            title = key
        symbols = {"MIC": "◉", "OUVIR": "◌", "WA": "✦", "REMOTE": "⌘",
                   "COWORK": "◆", "PC": "▣", "BG": "◐"}
        painter.setFont(px_font(13, QFont.Weight.Normal))
        painter.setPen(QPen(translucent(acento, 0.85 if enabled else 0.40)))
        painter.drawText(QRectF(12, 11, 22, 20), Qt.AlignmentFlag.AlignCenter,
                         symbols.get(key.upper(), "◇"))

        painter.setFont(px_font(10, QFont.Weight.DemiBold, spacing=1.4))
        painter.setPen(QPen(translucent(qcol(C.TEXT_DIM), .96 if enabled else .42)))
        fm = painter.fontMetrics()
        painter.drawText(QRectF(38, 11, max(5, w - 50), 20), Qt.AlignmentFlag.AlignVCenter,
                         fm.elidedText(key, Qt.TextElideMode.ElideRight, max(5, w - 50)))

        title_size = 12 if w >= 127 else 11
        painter.setFont(px_font(title_size, QFont.Weight.DemiBold))
        painter.setPen(QPen(translucent(qcol(C.WHITE), .97 if enabled else .40)))
        fm = painter.fontMetrics()
        painter.drawText(QRectF(10, 33, w - 20, 22),
                         Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignHCenter,
                         fm.elidedText(title, Qt.TextElideMode.ElideRight, max(10, w - 21)))

        painter.setFont(px_font(9.5, QFont.Weight.Normal, spacing=0.4))
        status_col = acento if self._mode in {"on", "danger", "purple", "warning"} else qcol(C.TEXT_DIM)
        painter.setPen(QPen(translucent(status_col, 0.95 if enabled else 0.45)))
        fm = painter.fontMetrics()
        status_text = fm.elidedText(status, Qt.TextElideMode.ElideRight, max(10, w - 20))
        painter.drawText(QRectF(9, h - 28, w - 18, 17), Qt.AlignmentFlag.AlignCenter, status_text)

        if self.hasFocus():
            painter.setPen(QPen(translucent(qcol(C.PRI), 0.85), 1.2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(base.adjusted(3, 3, -3, -3), 9, 9)
        painter.end()
