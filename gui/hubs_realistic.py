"""Renderizador dos HUBs realistas do T.O.R.V.I.S 2026 v5.6.0.

Mantém a interface leve: somente QPainter, sem OpenGL, shaders ou novas
bibliotecas. Cada HUB compartilha uma linguagem visual (vidro holográfico,
profundidade, glow, sombra e partículas), mas conserva sua geometria própria.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from PyQt6.QtCore import QLineF, QPointF, QRectF, Qt
from PyQt6.QtGui import (QBrush, QColor, QConicalGradient, QPainter, QPainterPath, QPen, QPixmap,
                         QPolygonF, QRadialGradient)


REALISTIC_HUBS = (
    "hexagono", "prisma", "cubo", "iris", "engrenagem",
    "atomo", "mandala", "espectro", "vortice",
)


def _alpha(col: QColor, value: float) -> QColor:
    c = QColor(col)
    c.setAlphaF(max(0.0, min(1.0, value)))
    return c


def _mix(a: QColor, b: QColor, t: float) -> QColor:
    t = max(0.0, min(1.0, t))
    return QColor(
        int(a.red() + (b.red() - a.red()) * t),
        int(a.green() + (b.green() - a.green()) * t),
        int(a.blue() + (b.blue() - a.blue()) * t),
        int(a.alpha() + (b.alpha() - a.alpha()) * t),
    )


def _poly(cx: float, cy: float, n: int, radius: float, phase: float = 0.0,
          squash: float = 1.0, yoff: float = 0.0) -> QPolygonF:
    return QPolygonF([
        QPointF(cx + math.cos(phase + i * math.tau / n) * radius,
                cy + yoff + math.sin(phase + i * math.tau / n) * radius * squash)
        for i in range(n)
    ])


@dataclass(frozen=True)
class HubVisualState:
    phase: float
    amp: float
    state: str
    speaking: bool
    muted: bool

    @property
    def live(self) -> bool:
        return (self.speaking or self.amp > 0.04) and not self.muted

    @property
    def speed(self) -> float:
        if self.muted:
            return 0.18
        if self.state in ("THINKING", "PROCESSING"):
            return 1.8
        if self.speaking:
            return 1.35
        if self.state == "OUVINDO":
            return 0.9
        return 0.42


class RealisticHubRenderer:
    """Desenha os nove HUBs geométricos com aparência holográfica/3-D."""

    supported = frozenset(REALISTIC_HUBS)

    def __init__(self) -> None:
        # O material (metal, oclusão, Fresnel) não muda de quadro para quadro.
        # Rasterizá-lo uma vez e reutilizar custa uma fração de o redesenhar a
        # cada 33 ms — e é o que permite oferecer o acabamento também em HUB
        # grande sem estourar o tempo de quadro.
        self._cache_material: dict[tuple, QPixmap] = {}

    def paint(self, p: QPainter, cx: float, cy: float, r: float, style: str,
              main: QColor, acc: QColor, white: QColor, visual: HubVisualState) -> bool:
        if style not in self.supported:
            return False
        amp = max(0.0, min(1.0, visual.amp))
        pulse = 1.0 + amp * 0.09 + (0.018 * math.sin(visual.phase * 2.1))
        rr = r * pulse

        p.save()
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        self._reflexo_piso(p, cx, cy, rr, main, acc, amp)
        self._floor_shadow(p, cx, cy, rr, main, acc, amp)
        self._glass_field(p, cx, cy, rr, main, acc, visual)

        painter = getattr(self, f"_paint_{style}")
        painter(p, cx, cy, rr, main, acc, white, visual)

        self._outer_instrumentation(p, cx, cy, rr, main, acc, visual)
        self._core_light(p, cx, cy, rr, main, acc, white, visual)
        self._material(p, cx, cy, rr, main, acc, white, visual)
        self._realismo(p, cx, cy, rr, main, acc, white, visual)
        p.restore()
        return True

    # ── ambiente comum ──────────────────────────────────────────────────
    def _floor_shadow(self, p, cx, cy, r, main, acc, amp):
        p.save()
        p.translate(cx, cy + r * 0.74)
        p.scale(1.0, 0.23)
        g = QRadialGradient(0, 0, r * 1.08)
        g.setColorAt(0.0, _alpha(acc, 0.22 + amp * 0.16))
        g.setColorAt(0.5, _alpha(main, 0.08))
        g.setColorAt(1.0, _alpha(main, 0.0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(g))
        p.drawEllipse(QPointF(0, 0), r * 1.08, r * 1.08)
        p.restore()

    def _glass_field(self, p, cx, cy, r, main, acc, visual):
        amp = visual.amp
        # corpo de luz interno
        g = QRadialGradient(cx - r * 0.10, cy - r * 0.14, r * 0.92)
        g.setColorAt(0.0, _alpha(acc, 0.19 + amp * 0.16))
        g.setColorAt(0.35, _alpha(main, 0.10))
        g.setColorAt(0.72, _alpha(main, 0.035))
        g.setColorAt(1.0, _alpha(main, 0.0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(g))
        p.drawEllipse(QPointF(cx, cy), r * 0.98, r * 0.98)

        # vidro externo + reflexo superior
        p.setBrush(_alpha(main, 0.018))
        p.setPen(QPen(_alpha(main, 0.20), 1.0))
        p.drawEllipse(QPointF(cx, cy), r * 0.96, r * 0.96)
        p.setPen(QPen(_alpha(QColor(255, 255, 255), 0.11), 1.2))
        p.drawArc(QRectF(cx-r*.88, cy-r*.88, r*1.76, r*1.76), 28*16, 124*16)

    def _outer_instrumentation(self, p, cx, cy, r, main, acc, visual):
        phase = visual.phase * visual.speed
        # marcas técnicas no aro
        major, minor = [], []
        for i in range(72):
            a = math.radians(i * 5) + phase * 0.035
            ca, sa = math.cos(a), math.sin(a)
            rin = r * (0.88 if i % 6 == 0 else 0.92)
            rout = r * 0.965
            line = QLineF(cx + ca*rin, cy + sa*rin, cx + ca*rout, cy + sa*rout)
            (major if i % 6 == 0 else minor).append(line)
        p.setPen(QPen(_alpha(acc, 0.45), 1.45))
        p.drawLines(major)
        p.setPen(QPen(_alpha(main, 0.18), 0.9))
        p.drawLines(minor)

        # arco de varredura e três pontos de telemetria
        box = QRectF(cx-r*.81, cy-r*.81, r*1.62, r*1.62)
        p.setPen(QPen(_alpha(acc, 0.68), 2.0))
        p.drawArc(box, int((phase*25 % 360)*16), 48*16)
        for k in range(3):
            a = phase * (0.75 + k*0.12) + k * math.tau / 3
            rad = r * (0.70 + 0.055*k)
            x, y = cx + math.cos(a)*rad, cy + math.sin(a)*rad
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(_alpha(acc, 0.75 - k*0.12))
            p.drawEllipse(QPointF(x, y), 2.6 + visual.amp*2, 2.6 + visual.amp*2)

    def _core_light(self, p, cx, cy, r, main, acc, white, visual):
        amp = visual.amp
        core = r * (0.07 + amp * 0.025)
        g = QRadialGradient(cx-r*.018, cy-r*.024, core*3.2)
        g.setColorAt(0.0, _alpha(white, 0.96))
        g.setColorAt(0.18, _alpha(acc, 0.92))
        g.setColorAt(0.48, _alpha(main, 0.45))
        g.setColorAt(1.0, _alpha(main, 0.0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(g))
        p.drawEllipse(QPointF(cx, cy), core*3.2, core*3.2)
        p.setBrush(_alpha(white, 0.88))
        p.drawEllipse(QPointF(cx, cy), core, core)

    # ── material: o que faz parecer peça usinada, não desenho ────────────
    def _material(self, p, cx, cy, r, main, acc, white, visual):
        """Metal escovado + oclusão de ambiente + Fresnel, com cache.

        Metal escovado: dezenas de arcos finíssimos de alfa alternado, imitando as
        marcas de usinagem de uma peça torneada. O padrão é calculado (seno do
        índice), não sorteado: não "ferve" enquanto o HUB gira.
        """
        chave = (int(r), main.rgb(), acc.rgb(), white.rgb())
        pixmap = self._cache_material.get(chave)
        if pixmap is None:
            lado = int(r * 2.08) + 2
            pixmap = QPixmap(lado, lado)
            pixmap.fill(Qt.GlobalColor.transparent)
            pc = QPainter(pixmap)
            pc.setRenderHint(QPainter.RenderHint.Antialiasing)
            self._pintar_material_base(pc, lado / 2, lado / 2, r, main, acc, white)
            pc.end()
            if len(self._cache_material) > 12:      # cache pequeno e previsível
                self._cache_material.clear()
            self._cache_material[chave] = pixmap

        p.drawPixmap(int(cx - pixmap.width() / 2), int(cy - pixmap.height() / 2), pixmap)

        # segunda luz, fria, vinda de baixo à direita: separa o objeto do fundo
        caixa = QRectF(cx - r, cy - r, r * 2, r * 2)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(_alpha(QColor(120, 210, 255), 0.30), 2.2, Qt.PenStyle.SolidLine,
                      Qt.PenCapStyle.RoundCap))
        p.drawArc(caixa.adjusted(-0.4, -0.4, 0.4, 0.4), int(300 * 16), int(60 * 16))

    def _pintar_material_base(self, p, cx, cy, r, main, acc, white):
        """A parte estática do material, desenhada uma vez e depois reaproveitada."""
        caminho = QPainterPath()
        caminho.addEllipse(QPointF(cx, cy), r * 1.02, r * 1.02)
        p.save()
        p.setClipPath(caminho)

        # oclusão de ambiente: escurece onde as peças se encontram
        oc = QRadialGradient(cx, cy, r)
        oc.setColorAt(0.0, _alpha(QColor(0, 0, 0), 0.0))
        oc.setColorAt(0.55, _alpha(QColor(0, 0, 0), 0.16))
        oc.setColorAt(0.86, _alpha(QColor(0, 0, 0), 0.30))
        oc.setColorAt(1.0, _alpha(QColor(0, 0, 0), 0.10))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(oc))
        p.drawEllipse(QPointF(cx, cy), r * 1.02, r * 1.02)

        # marcas de usinagem
        p.setBrush(Qt.BrushStyle.NoBrush)
        aneis = max(14, min(46, int(r * 0.42)))
        for i in range(aneis):
            t = i / aneis
            raio = r * (0.30 + 0.68 * t)
            brilho = 0.030 + 0.022 * (0.5 + 0.5 * math.sin(i * 12.9898))
            tom = white if i % 3 == 0 else main
            p.setPen(QPen(_alpha(tom, brilho), 0.7))
            p.drawArc(QRectF(cx - raio, cy - raio, raio * 2, raio * 2),
                      int((i * 37) % 360 * 16), int(120 * 16))

        # Fresnel: a borda ganha luz quando vista de raspão
        fr = QRadialGradient(cx, cy, r * 1.02)
        fr.setColorAt(0.0, _alpha(white, 0.0))
        fr.setColorAt(0.78, _alpha(white, 0.0))
        fr.setColorAt(0.93, _alpha(white, 0.10))
        fr.setColorAt(1.0, _alpha(acc, 0.16))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(fr))
        p.drawEllipse(QPointF(cx, cy), r * 1.02, r * 1.02)
        p.restore()

    def _grao(self, p, cx, cy, r, white, visual):
        """Grão fino: quebra o degradê liso que denuncia imagem gerada.

        Deterministico (sem random) para o quadro não tremer. A fase desloca o
        padrão devagar, como grão de filme.
        """
        caminho = QPainterPath()
        caminho.addEllipse(QPointF(cx, cy), r * 1.0, r * 1.0)
        p.save()
        p.setClipPath(caminho)
        p.setPen(Qt.PenStyle.NoPen)
        total = max(24, min(60, int(r * 0.55)))
        desloc = int(visual.phase * 6) % 97
        for i in range(total):
            ang = (i * 2.399963) + desloc * 0.017        # espiral de ângulo áureo
            dist = r * (0.06 + 0.94 * ((i * 37 + desloc) % 97) / 97)
            x = cx + math.cos(ang) * dist
            y = cy + math.sin(ang) * dist
            alfa = 0.035 + 0.030 * (0.5 + 0.5 * math.sin(i * 7.13 + visual.phase))
            p.setBrush(_alpha(white, alfa))
            tamanho = 0.7 + 0.5 * ((i * 13) % 3)
            p.drawEllipse(QPointF(x, y), tamanho, tamanho)
        p.restore()

    def _reflexo_piso(self, p, cx, cy, r, main, acc, amp):
        """Reflexo alongado abaixo do HUB: o objeto pertence a uma superfície."""
        p.save()
        p.translate(cx, cy + r * 0.68)
        p.scale(1.0, 0.16)
        for fator, alfa in ((0.55, 0.16 + amp * 0.10), (0.95, 0.07 + amp * 0.05)):
            g = QRadialGradient(0, 0, r * fator * 1.5)
            g.setColorAt(0.0, _alpha(acc, alfa))
            g.setColorAt(0.6, _alpha(main, alfa * 0.35))
            g.setColorAt(1.0, _alpha(main, 0.0))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(g))
            p.drawEllipse(QPointF(0, 0), r * fator * 1.5, r * fator * 1.5)
        p.restore()

    def _bloom(self, p, cx, cy, r, main, acc, white, visual):
        """Halo aditivo em três raios: dá a sensação de luz de verdade."""
        intensidade = 0.10 + min(0.18, max(0.0, visual.amp) * 0.30)
        p.save()
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Plus)
        for fator, alfa in ((0.30, intensidade * 0.55), (0.55, intensidade * 0.28),
                            (0.90, intensidade * 0.12)):
            g = QRadialGradient(cx, cy, r * fator)
            g.setColorAt(0.0, _alpha(acc, alfa))
            g.setColorAt(0.55, _alpha(main, alfa * 0.45))
            g.setColorAt(1.0, _alpha(main, 0.0))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(g))
            p.drawEllipse(QPointF(cx, cy), r * fator, r * fator)
        p.restore()

    # ── acabamento: o que separa "desenho" de "objeto com volume" ────────
    def _realismo(self, p, cx, cy, r, main, acc, white, visual):
        """Luz e profundidade aplicadas depois da geometria.

        A geometria de cada HUB diz o que ele é; esta passagem diz de onde vem a
        luz. É o que faz o objeto parecer ter espessura em vez de ser um contorno
        plano: aresta iluminada em cima à esquerda, aresta escura embaixo à
        direita, brilho especular, sombra interna e um fio de scanline.
        """
        p.save()
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        self._bloom(p, cx, cy, r, main, acc, white, visual)
        self._luz_lateral(p, cx, cy, r, main, acc, white)
        self._sombra_interna(p, cx, cy, r, main)
        self._brilho_especular(p, cx, cy, r, white, visual)
        self._scanlines(p, cx, cy, r, acc, visual)
        self._grao(p, cx, cy, r, white, visual)
        p.restore()

    def _luz_lateral(self, p, cx, cy, r, main, acc, white):
        """Aresta clara a ~135° e aresta escura a ~315°: luz vinda do alto/esquerda."""
        caixa = QRectF(cx - r, cy - r, r * 2, r * 2)
        p.setBrush(Qt.BrushStyle.NoBrush)
        # lado iluminado (dois arcos finos e sobrepostos fazem o degradê de brilho)
        for desloc, alfa, largura in ((0.0, 0.55, 2.6), (-0.6, 0.28, 1.4)):
            p.setPen(QPen(_alpha(white, alfa), largura, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.drawArc(caixa.adjusted(desloc, desloc, -desloc, -desloc),
                      int(105 * 16), int(70 * 16))
        # lado em sombra
        p.setPen(QPen(_alpha(QColor(0, 0, 0), 0.45), 3.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawArc(caixa.adjusted(0.6, 0.6, -0.6, -0.6), int(285 * 16), int(80 * 16))
        # franja quente junto ao aro interno do lado claro
        p.setPen(QPen(_alpha(acc, 0.20), 1.1))
        p.drawArc(caixa.adjusted(r * 0.06, r * 0.06, -r * 0.06, -r * 0.06),
                  int(110 * 16), int(50 * 16))

    def _sombra_interna(self, p, cx, cy, r, main):
        """Escurece a borda por dentro: dá espessura de vidro/acrílico."""
        g = QRadialGradient(cx, cy, r)
        g.setColorAt(0.0, _alpha(main, 0.0))
        g.setColorAt(0.72, _alpha(main, 0.0))
        g.setColorAt(0.94, _alpha(QColor(0, 0, 0), 0.30))
        g.setColorAt(1.0, _alpha(QColor(0, 0, 0), 0.55))
        caminho = QPainterPath()
        caminho.addEllipse(QPointF(cx, cy), r, r)
        p.save()
        p.setClipPath(caminho)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(g))
        p.drawEllipse(QPointF(cx, cy), r, r)
        p.restore()

    def _brilho_especular(self, p, cx, cy, r, white, visual):
        """Reflexo em gota no alto à esquerda; acompanha a pulsação da voz."""
        intensidade = 0.13 + min(0.10, max(0.0, visual.amp) * 0.22)
        p.save()
        p.translate(cx - r * 0.34, cy - r * 0.40)
        p.rotate(-32)
        p.scale(1.0, 0.42)
        g = QRadialGradient(0, 0, r * 0.52)
        g.setColorAt(0.0, _alpha(white, intensidade))
        g.setColorAt(0.55, _alpha(white, intensidade * 0.35))
        g.setColorAt(1.0, _alpha(white, 0.0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(g))
        p.drawEllipse(QPointF(0, 0), r * 0.52, r * 0.52)
        p.restore()

    def _scanlines(self, p, cx, cy, r, acc, visual):
        """Fio de varredura bem discreto: sugere tela, não estraga a arte."""
        caminho = QPainterPath()
        caminho.addEllipse(QPointF(cx, cy), r * 0.97, r * 0.97)
        p.save()
        p.setClipPath(caminho)
        passo = max(3, int(r * 0.075))
        alfa = 0.035 + min(0.03, max(0.0, visual.amp) * 0.05)
        p.setPen(QPen(_alpha(acc, alfa), 1))
        inicio = int(cy - r)
        fim = int(cy + r)
        for y in range(inicio, fim, passo):
            p.drawLine(int(cx - r), y, int(cx + r), y)
        p.restore()

    def _glow_line(self, p, a: QPointF, b: QPointF, col: QColor, width=1.4, alpha=0.75):
        p.setPen(QPen(_alpha(col, alpha*0.16), width*4.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawLine(a, b)
        p.setPen(QPen(_alpha(col, alpha), width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawLine(a, b)

    def _glow_poly(self, p, poly: QPolygonF, col: QColor, width=1.6, alpha=0.72):
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(_alpha(col, alpha*0.16), width*4.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        p.drawPolygon(poly)
        p.setPen(QPen(_alpha(col, alpha), width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        p.drawPolygon(poly)

    # ── HUBs ────────────────────────────────────────────────────────────
    def _paint_hexagono(self, p, cx, cy, r, main, acc, white, v):
        phase = v.phase * v.speed * 0.38
        layers = ((1.0, -r*.055, main, .74), (.74, 0, acc, .80), (.46, r*.035, main, .54))
        polys = []
        for scale, yoff, col, a in layers:
            q = _poly(cx, cy, 6, r*scale, phase * (1 if scale != .74 else -1.25), squash=.78, yoff=yoff)
            polys.append(q)
            self._glow_poly(p, q, col, 1.5 + (1-scale)*1.4, a)
        for i in range(6):
            self._glow_line(p, polys[2][i], polys[0][i], acc, 1.0, .42)
        # placas de vidro triangulares no anel intermediário
        for i in range(6):
            a, b = polys[1][i], polys[1][(i+1)%6]
            face = QPolygonF([QPointF(cx, cy), a, b])
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(_alpha(acc if i%2 == 0 else main, .025 + v.amp*.022))
            p.drawPolygon(face)

    def _paint_prisma(self, p, cx, cy, r, main, acc, white, v):
        ph = v.phase * v.speed * .24
        front = _poly(cx-r*.08, cy+r*.05, 3, r*.70, ph, squash=.92)
        back = _poly(cx+r*.18, cy-r*.15, 3, r*.70, ph, squash=.92)
        # faces translúcidas: fundo primeiro, arestas depois
        faces = [QPolygonF([front[i], front[(i+1)%3], back[(i+1)%3], back[i]]) for i in range(3)]
        for i, face in enumerate(faces):
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(_alpha(acc if i==1 else main, .035 + v.amp*.025))
            p.drawPolygon(face)
        self._glow_poly(p, back, main, 1.25, .38)
        self._glow_poly(p, front, acc, 1.8, .84)
        for i in range(3):
            self._glow_line(p, front[i], back[i], main, 1.25, .58)
        # feixe interno vertical
        self._glow_line(p, QPointF(cx,cy-r*.48), QPointF(cx,cy+r*.48), acc, 1.2, .36+.3*v.amp)

    def _paint_cubo(self, p, cx, cy, r, main, acc, white, v):
        ph = v.phase * v.speed * .34
        c, s = math.cos(ph), math.sin(ph)
        verts=[]
        # perspectiva isométrica simples, girando no eixo Y
        for x,y,z in [(-1,-1,-1),(1,-1,-1),(1,1,-1),(-1,1,-1),(-1,-1,1),(1,-1,1),(1,1,1),(-1,1,1)]:
            xr=x*c+z*s; zr=-x*s+z*c
            px=cx + (xr*.52 + zr*.24)*r*.58
            py=cy + (y*.52 - zr*.18)*r*.58
            verts.append(QPointF(px,py))
        faces=((0,1,2,3),(4,5,6,7),(0,1,5,4),(3,2,6,7))
        for j, ids in enumerate(faces):
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(_alpha(acc if j==1 else main, .026 + j*.006 + v.amp*.018))
            p.drawPolygon(QPolygonF([verts[i] for i in ids]))
        edges=((0,1),(1,2),(2,3),(3,0),(4,5),(5,6),(6,7),(7,4),(0,4),(1,5),(2,6),(3,7))
        for j,(a,b) in enumerate(edges):
            self._glow_line(p, verts[a], verts[b], acc if j in (4,5,9) else main, 1.45, .74 if j in (4,5,9) else .47)
        for i,pt in enumerate(verts):
            p.setPen(Qt.PenStyle.NoPen); p.setBrush(_alpha(acc, .55 if i%2 else .30))
            p.drawEllipse(pt, 2.0, 2.0)

    def _paint_iris(self, p, cx, cy, r, main, acc, white, v):
        phase = v.phase * v.speed * .42
        blades=12
        inner=r*(.22 + .035*math.sin(phase*1.8))
        outer=r*.72
        for i in range(blades):
            a=phase + i*math.tau/blades
            a2=a + math.tau/blades*.78
            pth=QPainterPath()
            pth.moveTo(cx+math.cos(a)*inner, cy+math.sin(a)*inner)
            pth.quadTo(cx+math.cos(a+.19)*outer*.86, cy+math.sin(a+.19)*outer*.86,
                       cx+math.cos(a2)*outer, cy+math.sin(a2)*outer)
            pth.quadTo(cx+math.cos(a2-.18)*inner*1.18, cy+math.sin(a2-.18)*inner*1.18,
                       cx+math.cos(a)*inner, cy+math.sin(a)*inner)
            p.setPen(QPen(_alpha(acc if i%3==0 else main, .56), 1.0))
            p.setBrush(_alpha(acc if i%3==0 else main, .035 + v.amp*.025))
            p.drawPath(pth)
        p.setBrush(_alpha(QColor(0,0,0), .28))
        p.setPen(QPen(_alpha(acc,.72),1.7))
        p.drawEllipse(QPointF(cx,cy), inner*.95, inner*.95)
        p.setPen(QPen(_alpha(white,.18),1))
        p.drawArc(QRectF(cx-outer,cy-outer,outer*2,outer*2), 35*16, 105*16)

    def _paint_engrenagem(self, p, cx, cy, r, main, acc, white, v):
        phase=v.phase*v.speed*.22
        teeth=24
        pts=[]
        for i in range(teeth*2):
            a=phase+i*math.pi/teeth
            rad=r*(.74 if i%2 else .88)
            pts.append(QPointF(cx+math.cos(a)*rad,cy+math.sin(a)*rad*.84))
        gear=QPolygonF(pts)
        p.setBrush(_alpha(main,.025)); self._glow_poly(p,gear,main,1.35,.62)
        inner=r*.42
        p.setPen(QPen(_alpha(acc,.62),1.6)); p.setBrush(_alpha(acc,.022))
        p.drawEllipse(QPointF(cx,cy),inner,inner*.84)
        for i in range(8):
            a=-phase*1.5+i*math.pi/4
            self._glow_line(p,QPointF(cx+math.cos(a)*inner*.48,cy+math.sin(a)*inner*.40),
                            QPointF(cx+math.cos(a)*r*.70,cy+math.sin(a)*r*.59),acc,1.1,.48)
        # segunda engrenagem interna para sensação mecânica
        p.setPen(QPen(_alpha(main,.30),1.0))
        p.drawEllipse(QPointF(cx,cy),r*.25,r*.21)

    def _paint_atomo(self, p, cx, cy, r, main, acc, white, v):
        phase=v.phase*v.speed*.56
        for k,deg in enumerate((0,60,-60)):
            p.save(); p.translate(cx,cy); p.rotate(deg + math.degrees(phase*.08)*(1 if k%2==0 else -1))
            rect=QRectF(-r*.78,-r*.22,r*1.56,r*.44)
            p.setPen(QPen(_alpha(main if k else acc,.58),1.35)); p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(rect)
            # elétron real na órbita
            a=phase*(1.15+k*.17)+k*2.1
            ex=math.cos(a)*r*.78; ey=math.sin(a)*r*.22
            g=QRadialGradient(ex,ey,8.0); g.setColorAt(0,_alpha(white,.95)); g.setColorAt(.25,_alpha(acc,.9)); g.setColorAt(1,_alpha(acc,0))
            p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(g)); p.drawEllipse(QPointF(ex,ey),8,8)
            p.restore()
        p.setPen(QPen(_alpha(acc,.40),1)); p.drawEllipse(QPointF(cx,cy),r*.24,r*.24)

    def _paint_mandala(self, p, cx, cy, r, main, acc, white, v):
        phase=v.phase*v.speed*.18
        for ring in range(1,5):
            rad=r*(.18+ring*.14)
            n=6+ring*2
            p.setPen(QPen(_alpha(main,.20+.055*ring),1.0))
            p.drawEllipse(QPointF(cx,cy),rad,rad)
            for i in range(n):
                a=phase*(1 if ring%2 else -1)+i*math.tau/n
                x=cx+math.cos(a)*rad; y=cy+math.sin(a)*rad
                pet=QPainterPath(); pet.moveTo(cx,cy)
                tangent=a+math.pi/2
                ctrl=r*.12
                pet.cubicTo(cx+math.cos(tangent)*ctrl,cy+math.sin(tangent)*ctrl,
                            x+math.cos(tangent)*ctrl, y+math.sin(tangent)*ctrl, x,y)
                p.setPen(QPen(_alpha(acc if ring==4 else main,.28+.08*ring),.85))
                p.drawPath(pet)
        p.setPen(QPen(_alpha(acc,.55),1.3)); p.drawEllipse(QPointF(cx,cy),r*.13,r*.13)

    def _paint_espectro(self, p, cx, cy, r, main, acc, white, v):
        phase=v.phase*v.speed
        bars=64
        for i in range(bars):
            a=-math.pi*.92+i*(math.pi*1.84/(bars-1))
            wave=.5+.5*math.sin(phase*4.4+i*.52)*math.cos(phase*1.7-i*.17)
            level=.08 + .22*wave + v.amp*(.24+.32*wave)
            r1=r*.47; r2=r*(.55+min(.33,level))
            ca,sa=math.cos(a),math.sin(a)
            col=acc if level>.26 else main
            self._glow_line(p,QPointF(cx+ca*r1,cy+sa*r1),QPointF(cx+ca*r2,cy+sa*r2),col,1.1,.44+.38*level)
        # lente interna com ponteiro de fase
        p.setPen(QPen(_alpha(main,.30),1.2)); p.setBrush(_alpha(main,.018)); p.drawEllipse(QPointF(cx,cy),r*.38,r*.38)
        a=phase*.7; self._glow_line(p,QPointF(cx,cy),QPointF(cx+math.cos(a)*r*.34,cy+math.sin(a)*r*.34),acc,1.3,.62)

    def _paint_vortice(self, p, cx, cy, r, main, acc, white, v):
        phase=v.phase*v.speed*1.25
        prev=None
        total=190
        for i in range(total):
            q=i/(total-1)
            a=phase+i*.205
            rad=r*(.07 + .73*q)
            # compressão vertical no exterior cria túnel em perspectiva
            pt=QPointF(cx+math.cos(a)*rad, cy+math.sin(a)*rad*(.68+.25*q))
            if prev is not None:
                col=_mix(main,acc,q)
                self._glow_line(p,prev,pt,col,.8+q*.65,.16+.54*q)
            prev=pt
        for k in range(8):
            q=(k+1)/9
            a=phase*1.35+k*.83
            rad=r*(.16+.62*q)
            pt=QPointF(cx+math.cos(a)*rad,cy+math.sin(a)*rad*(.72+.20*q))
            p.setPen(Qt.PenStyle.NoPen); p.setBrush(_alpha(acc,.26+.5*q))
            p.drawEllipse(pt,1.6+3*q,1.6+3*q)
