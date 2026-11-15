# T.O.R.V.I.S 2026 v5.6.2 — Correção e Controles Rápidos

## Correções
- Corrige crash ao abrir **Personalizar Assistente** (DEFAULT_VOICE).
- Corrige crash ao abrir **Dispositivos de Áudio** (DEFAULT_LABEL).
- Move tarefas, relatórios e rotinas para o diretório de estado do usuário.
- Corrige leitura da memória usada pelo Computer Use.
- Corrige build do PyInstaller para incluir actions/providers/plugins e assets essenciais.
- Build Windows passa a executar a suíte pytest completa.
- CRIAR-EXECUTAVEL.bat usa o spec oficial em packaging/.
- WhatsApp deixa de fazer envio cego quando o driver verificado não está disponível.

## Novos controles funcionais
- **Microfone Ativo [F4]** — liga/desliga a captura do microfone.
- **Sempre Ouvindo** — desliga Wake Word e Push-to-talk e mantém o microfone em modo normal.
- **Conectar WhatsApp** — abre o aplicativo e, se necessário, o WhatsApp Web para QR Code.
- **Controle Remoto** — abre o fluxo de chave/QR do dashboard remoto já existente.
- **Cowork sem Pasta** — cria um novo projeto pelo dev_agent sem exigir pasta carregada.
- **Computer Use** — permissão real para automação de mouse/teclado/apps; desligado bloqueia as ferramentas correspondentes.
- **Segundo Plano [F9]** — oculta/restaura a janela mantendo o processo ativo; usa bandeja do sistema quando disponível.

## Interface principal — barra inferior
- Os sete controles principais agora ficam **sempre visíveis no rodapé da janela principal**, abaixo dos HUBs.
- Eles foram removidos do painel **Controles** para evitar duplicidade e reduzir cliques.
- A barra usa botões maiores com estado visual para Microfone, Sempre Ouvindo, Computer Use e Segundo Plano.
- O painel **Controles** permanece apenas para opções secundárias como tela cheia, brief, wake word, push-to-talk e estilo do HUD.

## Painel de conversa
- Renomeia **COMMUNICATIONS** para **CONVERSA** no painel direito.
- Adiciona o botão **LIMPAR CONVERSA** no cabeçalho do painel.
- O botão pede confirmação, limpa o histórico visual e cancela mensagens ainda em animação.
- O I.S.A. descarta o contexto da sessão ativa e reconecta sem o identificador de retomada, iniciando uma conversa realmente nova.
