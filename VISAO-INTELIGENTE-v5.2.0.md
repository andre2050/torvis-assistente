# T.O.R.V.I.S 2026 v5.2.0 — Visão Inteligente

## Objetivo

Transformar a visão da 5.1.0, que expunha principalmente saída bruta de ONNX, em uma camada visual utilizável pelo núcleo I.S.A. sem alterar os 10 HUBs.

## Recursos

- análise local da imagem: resolução, luminosidade, contraste, nitidez e densidade de bordas;
- detecção heurística de regiões que podem representar botões, ícones e outros controles visuais;
- localização de uma imagem-modelo dentro de tela/câmera/arquivo (template matching);
- detector ONNX opcional com decodificação de saídas comuns de YOLO v5/v8;
- NMS por classe para reduzir caixas duplicadas;
- nova ação `vision_intelligence`, descoberta automaticamente pelo `action_loader`;
- captura sob demanda de tela ou câmera reaproveitando `actions/screen_processor.py`;
- modelo não é baixado automaticamente: o usuário controla quais pesos locais serão utilizados.

## Limites desta versão

Os candidatos de botão/ícone são heurísticos e não devem ser tratados como certeza sem confirmação adicional. A detecção semântica de objetos exige um modelo ONNX compatível fornecido localmente. A versão não executa cliques automaticamente a partir de uma detecção visual.

## Segurança e estabilidade

A visão é isolada em `neural/vision.py` e `actions/vision_intelligence.py`. Os 10 HUBs existentes permanecem no módulo de HUD e não dependem do detector. Falhas de modelo ou ausência de OpenCV não devem impedir o núcleo I.S.A. de inicializar.
