# T.O.R.V.I.S. 2026 v6.1.0 — relatório, métricas, orçamento e HUBs com volume

Base: v6.0.2. Nada removido.

## 1. Relatório de um clique (item 1)
`GERAR-RELATORIO.bat` (ou `python -m core.report`) escreve um .txt com: sistema,
dependências, rede, ordem aprendida dos modelos, últimos erros e métricas.
Nenhum dado sensível: a chave nunca entra (há teste garantindo isso).

## 2. Métricas de abertura (item 3)
`core/metrics.py` marca o instante de cada etapa (imports, janela criada) e grava
uma linha por execução em `metricas.jsonl`, com poda em 200 linhas. Sem número,
"está lento" não vira melhoria.

## 3. Orçamento diário de IA (item 4)
`core/budget.py` conta as respostas por modelo e por dia. Teto desligado por
padrão (0 = sem limite), porque a cota depende do plano. Para ligar:
`set TORVIS_LIMITE_DIARIO_IA=300`. Avisa ao chegar em 80% e informa quando
atinge o teto — o app segue funcionando sem a IA.

## 4. HUBs com volume e luz direcional
Passagem nova no `RealisticHubRenderer` (`_realismo`), aplicada aos nove HUBs:
- aresta iluminada em cima à esquerda e aresta escura embaixo à direita;
- sombra interna, que dá espessura de vidro;
- brilho especular que acompanha a amplitude da voz;
- scanlines discretas; franja quente junto ao aro.
Custo: alguns gradientes por quadro, sem OpenGL nem biblioteca nova.

Ferramentas de desenvolvimento incluídas: `tools/render_hubs.py` (grade dos nove)
e `tools/render_hub_grande.py` (um HUB ampliado), para comparar antes/depois.

## Testes
127 no total (114 anteriores + 13 novos): relatório gera todas as seções, não
vaza a chave, cria pasta; métricas marcam, salvam e podam; orçamento conta por
modelo, bloqueia no teto, avisa em 80% e sobrevive a arquivo corrompido.
