# T.O.R.V.I.S / Assistente Inteligente 5.1.0 — Inteligência Neural

Os módulos em `neural/` são independentes, com carregamento sob demanda e sem câmera automática.

- `vision.py`: inferência ONNX via OpenCV DNN, **saída bruta**. É necessário fornecer um modelo compatível e implementar o pós-processamento específico para obter caixas/rótulos. Não inclui modelos treinados.
- `sequence.py`: memória de sequência e rede RNN opcional **não treinada**.
- `feedforward.py`: classificador denso opcional **não treinado**.
- `reinforcement.py`: Q-learning tabular em **simulação**, sem permissão de executar comandos no Windows.
- `manager.py`: integração leve com `core/isa.py` e relatório de disponibilidade.

Os 10 HUBs e demais arquivos originais foram mantidos. Não há mudança na captura de tela, webcam ou política de permissões. Para instalar bibliotecas neurais opcionais, use `pip install -r requirements-neural.txt`. Para executar testes: `python -m pytest tests/test_neural.py tests/test_isa_core.py`. Não foi realizada validação em Windows nem compilação de executável.

## Próximas melhorias sugeridas
Pós-processamento YOLO/ONNX e modelos baixados com consentimento; configuração visual de módulos; pipelines de imagens locais; métricas e benchmarks; treino supervisionado com datasets autorizados; feedback humano auditável; testes Windows e empacotamento das dependências opcionais.
