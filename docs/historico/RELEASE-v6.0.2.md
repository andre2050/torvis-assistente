# T.O.R.V.I.S. 2026 v6.0.2 — escada medida e erros com rastro

Base: v6.0.1. Nada removido; duas melhorias novas.

## 1. A escada de modelos aprende a ordem sozinha
Antes: a ordem era fixa e medida uma vez, num dia, com uma chave. Quando um degrau
ficava lento (504 depois de 14 s) ou saía para a chave atual (404), a conversa
pagava esse tempo em TODA chamada.

Agora (`core/model_ladder.py`), sem gastar cota:
- cada resposta que já acontece registra a latência daquele modelo;
- a ordem passa a ser: medidos rápidos → medidos lentos → nunca medidos →
  que falharam (cota/indisponibilidade vão para o fim);
- nenhuma requisição extra é feita para medir;
- medidas com mais de 7 dias são descartadas (a API muda);
- a medição é por chave (hash), sem guardar a chave.

Exemplo real com os tempos que o próprio gemini.py documenta:
  antes : 3.5-flash-lite, flash-lite-latest, 3.1-flash-lite(7,5s), 3.5-flash,
          3.6-flash(falha), 3.8-flash(6,5s), 3.7-flash(falha)
  depois: 3.5-flash-lite, flash-lite-latest, 3.5-flash, 3.8-flash,
          3.1-flash-lite, 3.6-flash, 3.7-flash

O cooldown existente continua mandando: quem está descansando nem entra na conta.

## 2. Erros com rastro (`core/errlog.py`)
Antes: um erro dentro da interface aparecia por três segundos e desaparecia.
Agora todo erro não tratado — interface ou thread de trabalho — vai para
`erros.log` na pasta de estado, com data, thread e traceback. Ao passar de 1 MB,
o arquivo anterior vira `erros.old.log` (rotação, não crescimento infinito).
O log nunca pode derrubar o app: falha de escrita é silenciosa.

O diagnóstico passou a mostrar os últimos erros e a ordem aprendida dos modelos.

## Testes
114 no total (90 herdados + 6 de rede + 11 da escada + 7 do log).
Cobrem: ordenação por latência, falha vai para o fim, medição vencida não
influencia, isolamento por chave, arquivo corrompido não quebra, rotação do log,
erro em thread chega ao arquivo, e a integração com `usable_rungs`.
