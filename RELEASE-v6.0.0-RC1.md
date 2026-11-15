# T.O.R.V.I.S. 2026 v6.0.0 — ULTRA AI (RC1)

Versão candidata de testes baseada na v5.7.1, com funcionalidades anteriores preservadas.

## Correções implementadas neste pacote
- Versão centralizada em 6.0.0 e identificação RC1 no documento de lançamento.
- Arquivos oficiais logo #11 em config/torvis_ultra.png e .ico; topo da janela, ícone do Windows, bandeja e atalho.
- Build consistente: `dist/TORVIS/TORVIS.exe`, instalador Inno Setup apontando para esse mesmo caminho.
- Resolução de Desktop/Documentos/Downloads redirecionados pelo shell do Windows, com fallback de OneDrive.
- Criação de pastas com conferência de existência e caminho completo na resposta, sem anunciar sucesso falso.
- Ferramenta Google Maps por link de pesquisa ou direções, sem geocodificação inventada.
- LLM, RAG local, memória cognitiva, visão de tela, voz, Cowork acelerado/reconexão preservados da v5.7.1.
- Dez HUBs e controles originais preservados.

## Limitações e verificação
- Este arquivo ZIP contém o código-fonte e scripts de compilação, NÃO um TORVIS.exe compilado.
- Os testes automatizados nesta plataforma não simulam a integração real de microfone, Gemini Live ou tela no Windows.
- Para compilar: `PREPARAR-WINDOWS.bat` e `CRIAR-EXECUTAVEL.bat`; para instalador: Inno Setup / `build_windows.ps1`.
- Faça backup da versão instalada antes de testar esta RC1. Não use sem verificar permissões de ferramentas autônomas.
