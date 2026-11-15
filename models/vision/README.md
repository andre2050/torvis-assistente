# Modelos de visão — T.O.R.V.I.S 2026

A versão 5.2.0 não baixa pesos automaticamente. Coloque aqui um modelo ONNX compatível e, se necessário, um arquivo de rótulos do modelo.

O módulo `neural.vision.VisaoNeural` aceita saídas comuns de YOLO v5/v8 (`[1,N,C]` ou `[1,C,N]`) e aplica decodificação, limiar de confiança e NMS localmente.

Exemplo em Python:

```python
from neural.vision import VisaoNeural

visao = VisaoNeural("models/vision/model.onnx", ["pessoa", "carro", "... "]).carregar()
deteccoes = visao.detectar_objetos(frame)
```

Use apenas modelos cuja licença permita o seu uso e distribuição.
