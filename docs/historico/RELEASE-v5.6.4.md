# T.O.R.V.I.S 2026 v5.6.4 — Estabilidade Gemini Live

Hotfix da conexão de voz em tempo real.

- reconhece o erro WebSocket/API 1011 mesmo dentro de ExceptionGroup;
- reconecta automaticamente sem despejar traceback assustador no usuário;
- primeira queda tenta retomar a conversa com session resumption;
- quedas 1011 repetidas em até 60s descartam o handle e criam sessão limpa;
- failover temporário para gemini-3.8-live quando o modelo atual fica instável;
- mantém o modelo 3.1 como padrão para não mudar a voz sem necessidade;
- exige google-genai 2.34.x (linha 2.x) ou superior compatível, sem migrar para 3.x neste hotfix.
