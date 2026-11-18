# Roteiro de defesa

*Gerado em 17/11/2026 12:35 · versão 6.7.0*

Dez minutos: cerca de um minuto por tópico, com uma demonstração por bloco.

## 1. O problema

Assistentes de voz conversam bem e agem mal. A proposta foi construir um assistente que executa tarefas no próprio computador, mantém memória e continua útil depois de meses de uso.

**Mostrar na tela:** A janela principal com o HUD do assistente.

## 2. O que ele faz

Escuta por voz ou texto, responde em voz alta, executa comandos no sistema, pesquisa na web, lê arquivos, controla o navegador e automatiza rotinas agendadas.

**Mostrar na tela:** Uma tarefa real concluída ao vivo, com a confirmação aparecendo.

## 3. Arquitetura

Separação por responsabilidade: núcleo, interface, ferramentas, provedores e memória. A conversa ao vivo é o caminho padrão e o motor pode ser trocado sem mexer no resto.

**Mostrar na tela:** A tabela de pacotes do relatório técnico.

## 4. Segurança

Ação irreversível pede confirmação humana, fora do alcance do modelo. A política de execução decide o que roda direto e o que espera permissão.

**Mostrar na tela:** O banner de confirmação e a política configurada.

## 5. Atualização

O pacote chega assinado com SHA-256, é aplicado de forma atômica e volta sozinho se algo falhar. Chaves e memória nunca são sobrescritas.

**Mostrar na tela:** O log de uma atualização aplicada com sucesso.

## 6. Qualidade

A suíte tem 37 arquivos de teste sobre 197 módulos, mais diagnóstico embutido e métricas de abertura.

**Mostrar na tela:** A suíte passando no terminal.

## 7. Memória

Três camadas: longo prazo, cognitiva e sessão. A recuperação combina relevância lexical, importância e recência, sem depender de rede.

**Mostrar na tela:** O painel de memória com entradas reais.

## 8. Dados para ajuste fino

O uso deixa um conjunto que pode ser revisado e exportado no formato do provedor. Nada sai da máquina sem revisão.

**Mostrar na tela:** O painel do laboratório com a contagem de exemplos.

## 9. Limitações

O que não está pronto, dito com clareza: testes de hardware, latência dependente de rede e ausência de previsão em eventos aleatórios.

**Mostrar na tela:** A seção de limitações do relatório.

## 10. Próximos passos

Watchdog da sessão ao vivo, trilha de auditoria das ações e divisão dos arquivos grandes por HUB.

**Mostrar na tela:** A lista de trabalhos futuros.
