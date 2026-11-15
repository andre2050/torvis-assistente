# T.O.R.V.I.S 2026

**Responsável pelas modificações:** Andre Luiz Lima Menezes  
**Idioma padrão:** Português do Brasil (pt-BR)  
**Plataforma principal:** Windows

O T.O.R.V.I.S é um assistente de IA para computador com voz, memória, automação, visão, rotinas, painel, plugins e integração com diferentes provedores de modelos de linguagem.

## Instalação para desenvolvimento

1. Instale Python 3.11 a 3.13.
2. Execute `python setup.py`.
3. Configure as chaves necessárias na tela de configurações.
4. Execute `python main.py`.

## Compilar para Windows

Execute `build_windows.ps1`. O script instala as dependências de compilação, executa os testes e gera o executável **TORVIS.exe**. Se o Inno Setup estiver instalado, também será criado o instalador.

## Dados do usuário

No Windows, configurações, memória, cache, logs, sessões e backups ficam em `%LOCALAPPDATA%\\Assistente Inteligente`. Isso permite atualizar o programa sem misturar os arquivos graváveis com os arquivos do aplicativo.

## Idioma

A interface, mensagens destinadas ao usuário, respostas e voz padrão foram configuradas para português do Brasil. O assistente só deve responder em outro idioma quando o usuário pedir explicitamente.

## Segurança

Ações sensíveis devem continuar exigindo confirmação. Atualizações são preparadas e verificadas antes da aplicação, e os mecanismos de backup e recuperação devem ser mantidos ativos.

## Atribuição

Este projeto deriva da base Mark 56 / Mark LVII. A licença e as atribuições obrigatórias do projeto de origem e de componentes de terceiros permanecem preservadas no arquivo `LICENSE`.


## v5.6.0 — HUB Realista

Os 10 HUBs receberam profundidade, iluminação holográfica, partículas e animações reativas, mantendo o renderizador anterior como fallback.


## v5.6.1 — Atualizador GitHub

O botão **Atualizar Sistema** agora consulta a fonte oficial no GitHub, compara versões, baixa o ZIP, valida SHA-256, valida o manifesto interno, cria backup das configurações/memórias e prepara a atualização de forma transacional. A substituição do executável em uso continua separada para evitar corrupção no Windows.


## v5.6.2 — Correção e Controles Rápidos

Corrige os painéis Personalizar/Áudio e adiciona Microfone, Sempre Ouvindo, WhatsApp, Controle Remoto, Cowork sem Pasta, Computer Use e Segundo Plano [F9]. Os sete controles principais ficam agora em uma **barra inferior fixa da interface principal**, sempre visíveis e fora do painel Controles.


## v5.6.3 — Refinamento da Interface e Cowork Rápido

A interface principal ganhou um núcleo/HUB central maior e mais reativo, conversa em blocos visuais, Code Agent recolhível, estados consistentes nos sete botões inferiores, indicador ON/OFF em Sempre Ouvindo, sensores indisponíveis sem `N/A`, tarefas ociosas compactas, comando mais legível e adaptação para telas menores.

O **Cowork Rápido** agora inicia com uma única pergunta, reconhece localmente projetos comuns (aplicativo desktop, site, API, automação/script), pula uma rodada de planejamento quando isso é seguro e pode gerar pequenos projetos em lote em uma única chamada de modelo, mantendo fallback automático para o fluxo completo.


## v5.6.4 — Estabilidade Gemini Live
- Reconexão automática para erro 1011 do Gemini Live, inclusive quando encapsulado em ExceptionGroup.
- Recuperação escalonada com session resumption, sessão limpa e failover temporário de modelo.

## v5.6.5 — Cowork Resiliente
- Heartbeat visual mantém o Code Agent atualizando mesmo durante chamadas longas do modelo.
- Modo rápido usa limite de tempo por geração e abandona etapas travadas em vez de ficar parado indefinidamente.
- Bundle rápido cai automaticamente para geração por arquivo quando o provedor demora, falha ou devolve resposta incompleta.
- Escrita por arquivo recebe uma segunda tentativa para falhas transitórias.
- Instalação de dependências no modo rápido tem timeout reduzido e continua como etapa não fatal.
- O painel mostra ATIVO/AGUARDANDO e informa quando está esperando o modelo ou preparando fallback.



## v5.7.0 — LLM + RAG + Agentes

- Nova base de conhecimento RAG local em SQLite/FTS5, com fontes citáveis e indexação sob pedido.
- Busca vetorial opcional com embeddings Ollama local e combinação híbrida.
- Ferramenta `knowledge_rag` no chat e agente Cowork privado `local_knowledge`.
- I.S.A. planeja com LLM apenas ferramentas registradas, com aprovação para operações sensíveis.
- Consulte `RAG-LLM-AGENTES-v5.7.0.md` para o passo a passo de configuração.


## v5.7.1 — Cowork mais rápido e seguro

- Projetos Python simples entram no modo rápido automaticamente.
- Arquivos independentes são gerados em paralelo após falha da geração em lote, respeitando dependências.
- O sistema avisa quando o projeto não ficou completo e bloqueia caminhos inseguros.
- Veja `RELEASE-v5.7.1.md` para os detalhes.

## v6.0.0 RC1 — ULTRA AI (pré-lançamento)

Correções para pasta real da Área de Trabalho/OneDrive, verificação do resultado de criação de pastas, pesquisa Google Maps, iconografia neural #11 no topo, no atalho e na compilação, nome TORVIS.exe unificado no instalador. Recursos anteriores (LLM, RAG, Cowork, memória, visão, voz e 10 HUBs) mantidos. Leia `RELEASE-v6.0.0-RC1.md`. RC1 requer verificação em Windows antes de uso como versão estável.
