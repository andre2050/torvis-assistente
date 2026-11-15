# T.O.R.V.I.S 2026 v5.6.0 — HUB Realista

A versão 5.6.0 moderniza os 10 HUBs sem remover a interface existente nem exigir GPU.

## Melhorias visuais

- Renderizador independente `gui/hubs_realistic.py` para os HUBs geométricos.
- Profundidade e perspectiva simuladas em software com `QPainter`.
- Glow em duas camadas, vidro holográfico, reflexos e sombra de projeção.
- Partículas orbitais e telemetria animada reagindo a áudio e estado do I.S.A.
- Hexágono em camadas; prisma com faces translúcidas; cubo com perspectiva giratória.
- Íris com lâminas animadas; engrenagem mecânica; átomo com elétrons em órbita.
- Mandala procedural; espectro circular reativo; vórtice com túnel em profundidade.
- Reator continua usando o modelo 3-D dedicado de `gui/reactor.py`.
- O pintor geométrico anterior foi mantido como fallback de segurança.

## Desempenho

A implementação usa apenas o pipeline gráfico já existente do PyQt6. Não adiciona OpenGL,
shaders, modelos 3-D externos ou novas dependências obrigatórias.

## Compatibilidade

Preserva Visão Inteligente, Memória Cognitiva, Agente Autônomo, Inteligência Adaptativa,
os 10 HUBs e a pasta principal `T.O.R.V.I.S 2026`.
