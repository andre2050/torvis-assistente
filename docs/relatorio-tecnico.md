# Assistente Inteligente T.O.R.V.I.S 2026

*Relatório técnico · versão 6.7.0 · 17/11/2026 12:35*


## 1. Objetivo

Este documento descreve um assistente pessoal de voz executado no computador do próprio usuário: ele escuta, responde em voz alta, executa tarefas no sistema e mantém memória entre sessões. O diferencial não é conversar — é agir: abrir programas, controlar arquivos, pesquisar na web, acompanhar telas e automatizar rotinas com confirmação humana nas ações irreversíveis.


## 2. Arquitetura

A separação é por responsabilidade: o núcleo não desenha, a interface não decide, e as ferramentas não sabem quem as chamou. A conversa ao vivo é o caminho padrão; um motor alternativo pode substituir escuta, raciocínio e fala sem tocar no resto do sistema.

| Pacote | Linhas | O que faz |
|---|---|---|
| core | 22.467 | núcleo: estado, modelos, rede, atualização, políticas e relatórios |
| actions | 16.780 | ferramentas que o assistente executa por comando de voz ou texto |
| gui | 11.013 | interface: HUD, painéis, temas e os 9 HUBs do avatar |
| providers | 5.905 | motor plugável de escuta, raciocínio e fala |
| raiz | 4.158 | módulo de apoio |
| tests | 3.898 | suíte automatizada de testes |
| memory | 1.371 | memória de longo prazo, memória cognitiva e configuração |
| dashboard | 1.320 | painel web local para acompanhar o assistente |
| tools | 961 | scripts de empacotamento, render e aplicação de atualização |
| neural | 578 | módulos neurais opcionais (classificador, visão, sequência) |
| plugins | 66 | extensões carregadas em tempo de execução |
| config | 28 | módulo de apoio |


## 3. Números do projeto

| Indicador | Valor |
|---|---|
| Módulos Python | 197 |
| Linhas de código Python | 68.545 |
| Arquivos de teste | 37 |
| Documentos técnicos | 58 |
| Total de arquivos | 293 |
| Python | 3.12.8 |


## 4. Metodologia

O desenvolvimento foi incremental e verificado: cada versão só é publicada depois de a suíte automatizada passar, e as atualizações chegam ao usuário por pacote assinado com SHA-256, aplicado de forma atômica e com rollback automático em caso de falha. Arquivos de chave, memória e configuração nunca são sobrescritos.

- Testes automatizados por módulo, executados fora da interface.
- Diagnóstico embutido: rede, modelos, dependências e erros num arquivo só.
- Métricas de desempenho gravadas em cada abertura.
- Atualização verificada por hash, com o sistema antigo preservado até a troca.


## 5. Cronologia

| Versão | Entrega |
|---|---|
| v5.x | HUBs visuais, memória cognitiva, visão computacional e agentes |
| v6.0 | núcleo I.S.A., política de execução, orçamento e diagnóstico |
| v6.1 | HUBs realistas, relatório de um clique e métricas de desempenho |
| v6.2 | atualização atômica com rollback e proteção de chaves |
| v6.3 | atualização automática em segundo plano |
| v6.4 | conjunto de ajuste fino e relatório de capstone |


## 6. Limitações declaradas

- O ajuste fino não altera a conversa ao vivo: ele troca o modelo de texto usado nas tarefas escritas.
- Nenhum método prevê sorteios ou eventos aleatórios; as decisões do assistente são apoio, não garantia.
- A suíte cobre a lógica; microfone, tela e voz dependem de teste manual no Windows.
- A latência percebida depende da rede e do provedor, não só do código.


## 7. Trabalhos futuros

- Testes com mocks para microfone, SAPI e captura de tela, hoje só validados à mão.
- Divisão de window.py e main.py por HUB, para reduzir o custo de cada correção.
- Watchdog da sessão ao vivo, com reconexão automática e estado visível.
- Trilha de auditoria das ações autônomas, com desfazer para o que é reversível.
