# T.O.R.V.I.S. 2026 v5.7.0 — LLM + RAG + agentes

## O que está integrado

- **LLM:** reutiliza o roteamento existente de Gemini e de **Engine & Providers** (Ollama, LM Studio e outros provedores compatíveis). `core/intelligence.py` permite perguntas com fontes e planos criados por LLM sem executar passos automaticamente.
- **RAG:** `core/knowledge_rag.py` mantém uma base SQLite privada por usuário, com pesquisa FTS5 e ranking lexical. Embeddings Ollama local são opcionais (híbrido lexical+vetorial com RRF), sem obrigar downloads de modelos pesados.
- **Chat e voz:** `actions/knowledge_rag.py` é descoberta automaticamente como ferramenta `knowledge_rag` no motor de ferramentas do TORVIS. A busca cita `arquivo#trecho-N`.
- **Cowork:** novo perfil *Especialista em conhecimento local*, com ferramenta `knowledge_search` sem acesso à web ou aos recursos privados fora da base indexada. Tarefas longas continuam usando o motor existente de checkpoint, retomada e orçamento.
- **Agentes autônomos:** a I.S.A. pode gerar plano a partir de um objetivo (`NucleoISA.planejar_com_llm`), validando cada ferramenta contra as registradas, com confirmação obrigatória para passos sensíveis durante a execução (`executar_plano`). **Gerar plano não executa ações**.

## Como preparar o RAG no Windows

1. Inicie o TORVIS e peça **“Qual é o status da minha base de documentos?”**. A ferramenta `knowledge_rag` mostrará a pasta autorizada, normalmente `%LOCALAPPDATA%\Assistente Inteligente\knowledge\inbox`.
2. Coloque nela somente arquivos que **deseja indexar** (TXT, MD, PDF, DOCX, CSV, JSON, LOG, PY ou HTML). Não coloque senhas nem dados que não deseja armazenar no índice local.
3. Peça **“Indexe os documentos da pasta de conhecimento”**. Ele usará `mode=index_inbox`, ou peça para indexar um único nome de arquivo.
4. Pergunte **“O que os meus documentos dizem sobre [assunto]?”**. A resposta deve trazer fontes e trecho. Para investigar por várias etapas, selecione o agente **Especialista em conhecimento local** no Cowork.

**Opcional:** para busca semântica com embeddings, instale Ollama, execute `ollama pull nomic-embed-text` e defina a variável de ambiente `TORVIS_RAG_EMBED_MODEL=nomic-embed-text` antes de iniciar o TORVIS. Essa variável é opcional: sem ela funciona a busca lexical, sem enviar o conteúdo a uma API de embeddings. Configure antes de indexar para gravar embeddings. O módulo de embeddings só aceita HTTP para localhost/loopback e não segue redirecionamentos.

## Privacidade e segurança

- Nenhum diretório pessoal é varrido automaticamente. A ferramenta de indexação aceita somente arquivos que estejam dentro da pasta `knowledge/inbox` do usuário; symlinks que apontem para fora são recusados.
- A base e os arquivos ficam fora da pasta de instalação, dentro da área de dados por usuário. Não há transferência automática para a nuvem no RAG. **Ao fazer uma pergunta com `answer_with_knowledge`, porém, os trechos recuperados são enviados ao provedor LLM selecionado**, que pode ser remoto. Para documentos sensíveis, configure um LLM local.
- O conteúdo dos documentos é tratado como dados não confiáveis (instruções de documentos não são autorizadas a controlar o computador).
- Agentes Cowork com acesso à web **não** recebem simultaneamente ferramentas de documentos privados; agentes locais recebem RAG sem web.
- Planejamento não implica execução: ações sensíveis continuam exigindo aprovação por passo. Aplicações, instalação de programas e uso de credenciais não são liberados por essa versão.

## Limites e testes

- Busca vetorial exige Ollama local com modelo de embeddings baixado; a busca lexical funciona sem ele.
- Os PDFs devem conter texto selecionável. Não há OCR para documentos escaneados nesta etapa.
- Esta versão é um **pacote de código-fonte**; testes automatizados verificam RAG, isolamento, planejamento e permissões. Não é uma compilação `.exe` testada em Windows.
- A v5.7.0 não altera o manifesto de atualização automática remoto: publicar um pacote como release e atualizar seu hash/versionamento é uma etapa de distribuição separada.

## Testes

```powershell
py -m pytest -q tests/test_rag_570.py
```
