"""Ação de Visão Inteligente do T.O.R.V.I.S 2026.

Captura a tela ou câmera somente quando a ferramenta é chamada e transforma o
frame em dados estruturados para o I.S.A.: métricas visuais, candidatos de UI e,
quando um modelo ONNX local foi indicado, detecções de objetos.
"""
from __future__ import annotations

import io
import json
from pathlib import Path

import numpy as np
from PIL import Image

from actions.screen_processor import _capture_camera, _capture_screen
from neural.vision import VisaoNeural


def _imagem_de_bytes(data: bytes) -> np.ndarray:
    img = Image.open(io.BytesIO(data)).convert("RGB")
    return np.asarray(img)


def _imagem_de_arquivo(path: str) -> np.ndarray:
    p = Path(path).expanduser()
    if not p.is_file():
        raise FileNotFoundError(f"Imagem não encontrada: {p}")
    with Image.open(p) as img:
        return np.asarray(img.convert("RGB"))


def _rotulos(parameters: dict) -> list[str]:
    raw = parameters.get("labels") or []
    if isinstance(raw, str):
        p = Path(raw).expanduser()
        if p.is_file():
            return [x.strip() for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]
        return [x.strip() for x in raw.split(",") if x.strip()]
    if isinstance(raw, list):
        return [str(x).strip() for x in raw if str(x).strip()]
    return []


def vision_intelligence(parameters=None, **_context) -> str:
    params = parameters or {}
    origem = str(params.get("source") or "screen").strip().lower()
    modo = str(params.get("mode") or "analyze").strip().lower()

    if origem == "screen":
        data, _mime = _capture_screen()
        frame = _imagem_de_bytes(data)
    elif origem == "camera":
        data, _mime = _capture_camera()
        frame = _imagem_de_bytes(data)
    elif origem == "file":
        frame = _imagem_de_arquivo(str(params.get("image_path") or ""))
    else:
        return json.dumps({"ok": False, "erro": "source deve ser screen, camera ou file"}, ensure_ascii=False)

    visao = VisaoNeural()
    resposta: dict = {"ok": True, "source": origem, "mode": modo}

    if modo in ("analyze", "ui"):
        resposta["analise"] = visao.analisar_imagem(frame).como_dict()
        resposta["elementos_interface"] = [
            r.como_dict() for r in visao.encontrar_elementos_interface(frame)
        ]
        return json.dumps(resposta, ensure_ascii=False)

    if modo == "objects":
        modelo = str(params.get("model_path") or "").strip()
        if not modelo:
            return json.dumps({
                "ok": False,
                "erro": "Para detectar objetos, informe model_path de um ONNX local compatível.",
            }, ensure_ascii=False)
        detector = VisaoNeural(modelo, _rotulos(params)).carregar()
        resposta["objetos"] = [
            d.como_dict() for d in detector.detectar_objetos(
                frame,
                confianca_minima=float(params.get("confidence") or 0.35),
            )
        ]
        return json.dumps(resposta, ensure_ascii=False)

    if modo == "template":
        caminho = str(params.get("template_path") or "").strip()
        if not caminho:
            return json.dumps({"ok": False, "erro": "Informe template_path."}, ensure_ascii=False)
        template = _imagem_de_arquivo(caminho)
        resposta["correspondencias"] = visao.localizar_template(
            frame,
            template,
            limiar=float(params.get("confidence") or 0.86),
        )
        return json.dumps(resposta, ensure_ascii=False)

    return json.dumps({"ok": False, "erro": "mode deve ser analyze, ui, objects ou template"}, ensure_ascii=False)


TOOL = {
    "name": "vision_intelligence",
    "description": (
        "Analisa visualmente a tela, câmera ou um arquivo de imagem. Pode medir a cena, "
        "encontrar candidatos de botões/ícones, localizar uma imagem-modelo e detectar objetos "
        "quando um modelo ONNX local compatível é fornecido. Use somente quando a solicitação "
        "do usuário realmente exigir informação visual."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "source": {"type": "STRING", "description": "screen, camera ou file"},
            "mode": {"type": "STRING", "description": "analyze, ui, objects ou template"},
            "image_path": {"type": "STRING", "description": "Caminho da imagem quando source=file"},
            "template_path": {"type": "STRING", "description": "Imagem pequena a localizar quando mode=template"},
            "model_path": {"type": "STRING", "description": "Modelo ONNX local quando mode=objects"},
            "labels": {"type": "STRING", "description": "Arquivo de rótulos ou nomes separados por vírgula"},
            "confidence": {"type": "NUMBER", "description": "Limiar de confiança, de 0 a 1"},
        },
    },
    "handler": vision_intelligence,
    "tier": "extra",
    "brief": "Analisa tela/câmera/imagem e encontra elementos visuais ou objetos locais.",
}
