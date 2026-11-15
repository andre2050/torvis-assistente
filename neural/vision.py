"""Visão Inteligente do T.O.R.V.I.S 2026.

A camada base funciona apenas com NumPy e oferece métricas de cena, busca de
imagem-modelo e heurísticas de elementos de interface. OpenCV é carregado
somente quando disponível e acelera essas operações, além de permitir inferência
ONNX (por exemplo, modelos YOLO exportados para ONNX).

Nenhum modelo é baixado automaticamente. Isso mantém a instalação previsível e
permite ao usuário escolher os pesos locais que deseja usar.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from importlib.util import find_spec
from pathlib import Path
from typing import Iterable, Sequence

import numpy as np


@dataclass(slots=True)
class DeteccaoObjeto:
    classe: str
    confianca: float
    x: int
    y: int
    largura: int
    altura: int
    classe_id: int = -1

    def como_dict(self) -> dict:
        return asdict(self)


@dataclass(slots=True)
class RegiaoInterface:
    tipo: str
    x: int
    y: int
    largura: int
    altura: int
    confianca: float

    def como_dict(self) -> dict:
        return asdict(self)


@dataclass(slots=True)
class AnaliseImagem:
    largura: int
    altura: int
    canais: int
    luminosidade: float
    contraste: float
    nitidez: float
    densidade_bordas: float
    escura: bool
    clara: bool
    desfocada: bool

    def como_dict(self) -> dict:
        return asdict(self)


def _cv2_disponivel() -> bool:
    return find_spec("cv2") is not None


def _normalizar_imagem(imagem) -> np.ndarray:
    arr = np.asarray(imagem)
    if arr.ndim not in (2, 3):
        raise ValueError("A imagem precisa ter formato HxW ou HxWxC")
    if arr.ndim == 3 and arr.shape[2] not in (1, 3, 4):
        raise ValueError("A imagem precisa ter 1, 3 ou 4 canais")
    if arr.shape[0] < 1 or arr.shape[1] < 1:
        raise ValueError("Imagem vazia")
    if arr.dtype != np.uint8:
        arr = np.clip(arr, 0, 255).astype(np.uint8)
    return arr


def _cinza(imagem: np.ndarray) -> np.ndarray:
    if imagem.ndim == 2:
        return imagem.astype(np.float32)
    if imagem.shape[2] == 1:
        return imagem[..., 0].astype(np.float32)
    # Média ponderada aproximada; a ordem RGB/BGR pouco altera métricas globais.
    rgb = imagem[..., :3].astype(np.float32)
    return rgb[..., 0] * 0.299 + rgb[..., 1] * 0.587 + rgb[..., 2] * 0.114


def _iou(a: Sequence[float], b: Sequence[float]) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    if inter <= 0:
        return 0.0
    aa = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    ba = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    den = aa + ba - inter
    return inter / den if den > 0 else 0.0


def _nms(caixas: list[list[float]], scores: list[float], iou_limite: float) -> list[int]:
    ordem = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
    manter: list[int] = []
    while ordem:
        atual = ordem.pop(0)
        manter.append(atual)
        ordem = [i for i in ordem if _iou(caixas[atual], caixas[i]) <= iou_limite]
    return manter


class VisaoNeural:
    """Módulo local de visão com base leve e detector ONNX opcional."""

    def __init__(self, modelo=None, rotulos: Iterable[str] | None = None):
        self.modelo = Path(modelo) if modelo else None
        self.rotulos = [str(x) for x in (rotulos or [])]
        self._net = None

    # ------------------------------------------------------------------
    # Base sem modelo
    # ------------------------------------------------------------------
    def analisar_imagem(self, imagem) -> AnaliseImagem:
        arr = _normalizar_imagem(imagem)
        gray = _cinza(arr)
        h, w = gray.shape
        canais = 1 if arr.ndim == 2 else int(arr.shape[2])

        luminosidade = float(gray.mean())
        contraste = float(gray.std())
        if h >= 3 and w >= 3:
            centro = gray[1:-1, 1:-1]
            lap = (
                4.0 * centro
                - gray[:-2, 1:-1]
                - gray[2:, 1:-1]
                - gray[1:-1, :-2]
                - gray[1:-1, 2:]
            )
            nitidez = float(np.var(lap))
        else:
            nitidez = 0.0

        dx = np.abs(np.diff(gray, axis=1)) if w > 1 else np.zeros((h, 1), dtype=np.float32)
        dy = np.abs(np.diff(gray, axis=0)) if h > 1 else np.zeros((1, w), dtype=np.float32)
        borda_x = float(np.mean(dx > 24.0)) if dx.size else 0.0
        borda_y = float(np.mean(dy > 24.0)) if dy.size else 0.0
        densidade = (borda_x + borda_y) / 2.0

        return AnaliseImagem(
            largura=w,
            altura=h,
            canais=canais,
            luminosidade=round(luminosidade, 2),
            contraste=round(contraste, 2),
            nitidez=round(nitidez, 2),
            densidade_bordas=round(densidade, 4),
            escura=luminosidade < 45.0,
            clara=luminosidade > 215.0,
            desfocada=nitidez < 35.0,
        )

    def localizar_template(self, imagem, template, *, limiar: float = 0.86, max_resultados: int = 10) -> list[dict]:
        """Localiza uma imagem pequena dentro de outra.

        OpenCV é usado quando instalado. Existe fallback NumPy para manter o
        recurso testável e funcional em instalações mínimas (ideal para imagens
        pequenas; OpenCV é preferível para screenshots grandes).
        """
        cena = _normalizar_imagem(imagem)
        alvo = _normalizar_imagem(template)
        cg, tg = _cinza(cena), _cinza(alvo)
        ch, cw = cg.shape
        th, tw = tg.shape
        if th > ch or tw > cw:
            return []
        limiar = float(np.clip(limiar, -1.0, 1.0))
        max_resultados = max(1, int(max_resultados))

        pontos: list[tuple[float, int, int]] = []
        if _cv2_disponivel():
            import cv2
            res = cv2.matchTemplate(cg.astype(np.float32), tg.astype(np.float32), cv2.TM_CCOEFF_NORMED)
            ys, xs = np.where(res >= limiar)
            pontos = [(float(res[y, x]), int(x), int(y)) for y, x in zip(ys, xs)]
        else:
            t = tg - tg.mean()
            tnorm = float(np.sqrt(np.sum(t * t)))
            if tnorm == 0.0:
                # Templates uniformes: erro absoluto normalizado é mais útil que correlação.
                for y in range(ch - th + 1):
                    for x in range(cw - tw + 1):
                        patch = cg[y:y + th, x:x + tw]
                        score = 1.0 - float(np.mean(np.abs(patch - tg))) / 255.0
                        if score >= limiar:
                            pontos.append((score, x, y))
            else:
                for y in range(ch - th + 1):
                    for x in range(cw - tw + 1):
                        patch = cg[y:y + th, x:x + tw]
                        p = patch - patch.mean()
                        pnorm = float(np.sqrt(np.sum(p * p)))
                        score = float(np.sum(p * t) / (pnorm * tnorm)) if pnorm else -1.0
                        if score >= limiar:
                            pontos.append((score, x, y))

        pontos.sort(reverse=True)
        resultados: list[dict] = []
        caixas: list[list[float]] = []
        for score, x, y in pontos:
            caixa = [x, y, x + tw, y + th]
            if any(_iou(caixa, b) > 0.35 for b in caixas):
                continue
            caixas.append(caixa)
            resultados.append({
                "confianca": round(score, 4), "x": x, "y": y,
                "largura": tw, "altura": th,
            })
            if len(resultados) >= max_resultados:
                break
        return resultados

    def encontrar_elementos_interface(
        self,
        imagem,
        *,
        area_minima: float = 0.0004,
        area_maxima: float = 0.22,
        max_resultados: int = 40,
    ) -> list[RegiaoInterface]:
        """Encontra regiões retangulares que parecem controles de interface.

        É uma heurística local — não afirma semanticamente que algo *é* um
        botão. Ela fornece candidatos para o I.S.A. ou para um modelo posterior.
        """
        arr = _normalizar_imagem(imagem)
        gray = _cinza(arr).astype(np.uint8)
        h, w = gray.shape
        area_total = float(h * w)
        out: list[RegiaoInterface] = []

        if _cv2_disponivel():
            import cv2
            blur = cv2.GaussianBlur(gray, (3, 3), 0)
            edges = cv2.Canny(blur, 45, 135)
            kernel = np.ones((3, 3), np.uint8)
            edges = cv2.dilate(edges, kernel, iterations=1)
            contornos, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            candidatos = []
            for c in contornos:
                x, y, ww, hh = cv2.boundingRect(c)
                candidatos.append((x, y, ww, hh))
        else:
            # Fallback leve: componentes conectados sobre bordas fortes.
            dx = np.zeros_like(gray, dtype=np.int16)
            dy = np.zeros_like(gray, dtype=np.int16)
            dx[:, 1:] = np.abs(gray[:, 1:].astype(np.int16) - gray[:, :-1].astype(np.int16))
            dy[1:, :] = np.abs(gray[1:, :].astype(np.int16) - gray[:-1, :].astype(np.int16))
            mask = (dx + dy) > 55
            candidatos = self._componentes(mask)

        for x, y, ww, hh in candidatos:
            area_rel = (ww * hh) / area_total
            if area_rel < area_minima or area_rel > area_maxima:
                continue
            if ww < 8 or hh < 8:
                continue
            proporcao = ww / max(1.0, float(hh))
            if 1.35 <= proporcao <= 9.0 and hh <= h * 0.18:
                tipo = "botao_candidato"
                conf = 0.72
            elif 0.72 <= proporcao <= 1.38 and max(ww, hh) <= min(w, h) * 0.28:
                tipo = "icone_candidato"
                conf = 0.62
            else:
                tipo = "controle_visual"
                conf = 0.48
            out.append(RegiaoInterface(tipo, int(x), int(y), int(ww), int(hh), conf))

        out.sort(key=lambda r: (r.confianca, r.largura * r.altura), reverse=True)
        return out[: max(1, int(max_resultados))]

    @staticmethod
    def _componentes(mask: np.ndarray) -> list[tuple[int, int, int, int]]:
        """Componentes conectados simples para o fallback sem OpenCV."""
        h, w = mask.shape
        vistos = np.zeros((h, w), dtype=bool)
        comps: list[tuple[int, int, int, int]] = []
        for sy, sx in zip(*np.where(mask & ~vistos)):
            if vistos[sy, sx]:
                continue
            pilha = [(int(sy), int(sx))]
            vistos[sy, sx] = True
            minx = maxx = int(sx)
            miny = maxy = int(sy)
            n = 0
            while pilha:
                y, x = pilha.pop()
                n += 1
                minx, maxx = min(minx, x), max(maxx, x)
                miny, maxy = min(miny, y), max(maxy, y)
                for yy, xx in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)):
                    if 0 <= yy < h and 0 <= xx < w and mask[yy, xx] and not vistos[yy, xx]:
                        vistos[yy, xx] = True
                        pilha.append((yy, xx))
            if n >= 4:
                comps.append((minx, miny, maxx - minx + 1, maxy - miny + 1))
        return comps

    # ------------------------------------------------------------------
    # Detector ONNX opcional
    # ------------------------------------------------------------------
    def carregar(self):
        if not self.modelo or not self.modelo.is_file():
            raise FileNotFoundError("Forneça um modelo ONNX local válido")
        if not _cv2_disponivel():
            raise RuntimeError("OpenCV é necessário para carregar modelos ONNX")
        import cv2
        self._net = cv2.dnn.readNetFromONNX(str(self.modelo))
        return self

    def detectar(self, imagem, *, tamanho=(640, 640)):
        """Compatibilidade 5.1: retorna a saída bruta do modelo ONNX."""
        if self._net is None:
            raise RuntimeError("Carregue o modelo antes de detectar")
        import cv2
        arr = _normalizar_imagem(imagem)
        blob = cv2.dnn.blobFromImage(arr, 1 / 255.0, tamanho, swapRB=True, crop=False)
        self._net.setInput(blob)
        return self._net.forward()

    def detectar_objetos(
        self,
        imagem,
        *,
        tamanho=(640, 640),
        confianca_minima: float = 0.35,
        iou_maximo: float = 0.45,
    ) -> list[DeteccaoObjeto]:
        arr = _normalizar_imagem(imagem)
        bruto = self.detectar(arr, tamanho=tamanho)
        return self.decodificar_saida(
            bruto,
            formato_original=arr.shape[:2],
            tamanho_entrada=tamanho,
            confianca_minima=confianca_minima,
            iou_maximo=iou_maximo,
        )

    def decodificar_saida(
        self,
        saida,
        *,
        formato_original: tuple[int, int],
        tamanho_entrada=(640, 640),
        confianca_minima: float = 0.35,
        iou_maximo: float = 0.45,
    ) -> list[DeteccaoObjeto]:
        """Decodifica os formatos ONNX mais comuns de YOLO v5/v8.

        Suporta [1,N,C], [1,C,N] e saídas já reduzidas [N,6]. O redimensionamento
        usado pelo detector é direto (sem letterbox), então X/Y são reescalados
        independentemente para a resolução original.
        """
        pred = np.asarray(saida)
        pred = np.squeeze(pred)
        if pred.ndim == 1:
            pred = pred.reshape(1, -1)
        if pred.ndim != 2:
            raise ValueError(f"Saída ONNX não suportada: shape={np.asarray(saida).shape}")
        if pred.shape[0] <= 128 and pred.shape[1] > 128:
            pred = pred.T

        orig_h, orig_w = map(int, formato_original)
        in_w, in_h = map(int, tamanho_entrada)
        sx = orig_w / max(1.0, float(in_w))
        sy = orig_h / max(1.0, float(in_h))
        conf_min = float(confianca_minima)

        caixas: list[list[float]] = []
        scores: list[float] = []
        classes: list[int] = []

        for row in pred.astype(np.float32, copy=False):
            if row.size < 6:
                continue
            # Se rótulos foram fornecidos, eles desambiguam o caso especial de
            # duas classes (YOLOv8 também tem exatamente 6 colunas: 4 + 2).
            eh_yolo_rotulado = bool(self.rotulos) and row.size in (len(self.rotulos) + 4, len(self.rotulos) + 5)
            if row.size == 6 and not eh_yolo_rotulado:
                # Formato final: x1,y1,x2,y2,score,class_id.
                score = float(row[4])
                cid = int(row[5])
                if score < conf_min:
                    continue
                x1, y1, x2, y2 = map(float, row[:4])
            else:
                cx, cy, bw, bh = map(float, row[:4])
                if self.rotulos and row.size == len(self.rotulos) + 5:
                    obj = float(row[4])
                    probs = row[5:]
                    cid = int(np.argmax(probs))
                    score = obj * float(probs[cid])
                elif self.rotulos and row.size == len(self.rotulos) + 4:
                    probs = row[4:]
                    cid = int(np.argmax(probs))
                    score = float(probs[cid])
                elif row.size == 85:  # YOLOv5 COCO típico
                    obj = float(row[4])
                    probs = row[5:]
                    cid = int(np.argmax(probs))
                    score = obj * float(probs[cid])
                else:  # YOLOv8 e derivados: 4 + classes
                    probs = row[4:]
                    cid = int(np.argmax(probs))
                    score = float(probs[cid])
                if score < conf_min:
                    continue
                x1 = cx - bw / 2.0
                y1 = cy - bh / 2.0
                x2 = cx + bw / 2.0
                y2 = cy + bh / 2.0

            x1, x2 = np.clip([x1 * sx, x2 * sx], 0, orig_w)
            y1, y2 = np.clip([y1 * sy, y2 * sy], 0, orig_h)
            if x2 <= x1 or y2 <= y1:
                continue
            caixas.append([float(x1), float(y1), float(x2), float(y2)])
            scores.append(score)
            classes.append(cid)

        # NMS por classe evita que classes distintas se eliminem mutuamente.
        manter_global: list[int] = []
        for cid in sorted(set(classes)):
            idxs = [i for i, c in enumerate(classes) if c == cid]
            sub_boxes = [caixas[i] for i in idxs]
            sub_scores = [scores[i] for i in idxs]
            manter_global.extend(idxs[j] for j in _nms(sub_boxes, sub_scores, float(iou_maximo)))
        manter_global.sort(key=lambda i: scores[i], reverse=True)

        out: list[DeteccaoObjeto] = []
        for i in manter_global:
            x1, y1, x2, y2 = caixas[i]
            cid = classes[i]
            nome = self.rotulos[cid] if 0 <= cid < len(self.rotulos) else f"classe_{cid}"
            out.append(DeteccaoObjeto(
                classe=nome,
                confianca=round(float(scores[i]), 4),
                x=int(round(x1)),
                y=int(round(y1)),
                largura=max(1, int(round(x2 - x1))),
                altura=max(1, int(round(y2 - y1))),
                classe_id=cid,
            ))
        return out
