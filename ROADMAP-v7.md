# ROADMAP v7 — o que falta para ficar avançado

Levantamento feito no código da v6.6.9: 1 236 arquivos Python, 450 mil linhas,
3 576 linhas de teste, nenhuma integração contínua.

Números que orientam as prioridades abaixo:

- `core/cloud.py`: 2 933 linhas, **0 testes**.
- `gui/window.py`: 3 628 linhas, 4 arquivos de teste citam o módulo.
- `core/knowledge_rag.py`: motor real (263 linhas), mas depende de **Ollama
  rodando** em `127.0.0.1:11434` para gerar embeddings. Sem Ollama, a busca cai
  para texto exato.
- Chave da API em **texto puro** no config do usuário.
- No celular, as ações são escolhidas por **expressão regular**, não pelo modelo.

---

## Nível 1 — fundação (barato, evita retrabalho)

### 1.1 Integração contínua e trava de regressão
**Por quê:** o defeito de escrita de código que você viu passaria em CI; hoje
só aparece quando um modelo falha em produção.
**Como:** GitHub Actions rodando `python -m unittest discover -s tests` em
Windows e Linux, a cada push. Badge no README.
**Custo:** baixo. **Ganho:** alto.

### 1.2 Testes nos módulos de risco
**Por quê:** `cloud.py` (2 933 linhas) não tem um único teste, e é por onde
passa toda conversa em nuvem.
**Como:** começar pelos pontos de falha reais: cota estourada, timeout,
resposta vazia, troca de modelo, streaming interrompido.
**Custo:** médio. **Ganho:** alto.

### 1.3 Chave da API protegida
**Por quê:** hoje é texto puro num JSON; qualquer backup ou print expõe.
**Como:** DPAPI no Windows, Keychain no macOS, arquivo 0600 no Linux;
EncryptedSharedPreferences no Android. Migração automática da chave antiga.
**Custo:** baixo. **Ganho:** médio.

---

## Nível 2 — o que faz parecer avançado

### 2.1 RAG sem depender de Ollama
**Por quê:** busca em documentos só funciona com outro programa instalado.
**Como:** embeddings ONNX embutidos (~25 MB, MiniLM multilíngue), com Ollama
virando opcional; índice incremental, citação por arquivo e trecho.
**Custo:** médio-alto. **Ganho:** alto.

### 2.2 Ferramentas escolhidas pelo modelo (substituir regex)
**Por quê:** hoje "no pc status" e "brilho 35" são regras fixas. O modelo não
combina ações nem lida com frase diferente.
**Como:** enviar `functionDeclarations` ao Gemini e executar a chamada que ele
escolher, com confirmação para ações de risco (já existe `avaliar_risco`).
Exemplo que passa a funcionar: *"marca reunião amanhã 15h e me lembra 20 min
antes"* → agenda + lembrete numa tacada.
**Custo:** médio. **Ganho:** muito alto (é o maior salto de capacidade).

### 2.3 Memória v2
**Por quê:** a memória atual guarda fatos soltos e manda todos no prompt.
**Como:** resumo rolante da conversa, recuperação por relevância (RAG da 2.1),
idades e esquecimento, limite de tokens.
**Custo:** médio. **Ganho:** alto.

### 2.4 Proatividade de verdade
**Por quê:** o assistente espera ser chamado.
**Como:** briefing matinal (agenda, e-mail, clima, tarefas), monitor de site e
de preço, lembretes que **sobrevivem ao reinício** (hoje morrem: o Android
descarta alarmes no reboot), e um "resumo do que ficou pendente".
**Custo:** baixo-médio. **Ganho:** médio-alto.

### 2.5 Ponte celular ↔ PC v2
**Por quê:** hoje é um token fixo em HTTP puro na rede local.
**Como:** token rotativo por sessão, limite de tentativas, fila de comandos
quando o PC está fora, estado compartilhado (notas, tarefas, memória).
**Custo:** médio. **Ganho:** médio.

---

## Nível 3 — diferencial

### 3.1 Voz contínua com palavra de ativação
`core/wake_word.py` já existe no PC. Falta: detecção local no celular, VAD para
não cortar a fala, e interrupção ("pare") durante a resposta.
**Custo:** alto. **Ganho:** alto em uso real.

### 3.2 Modo offline real
Modelo pequeno (Gemma 2B via llama.cpp) como último degrau da escada, quando não
há rede. Responde devagar, mas responde.
**Custo:** alto. **Ganho:** médio (só importa sem internet).

### 3.3 Painel de custo e latência
Cota gasta por modelo, tempo por resposta, quedas e motivo. Hoje o
comportamento da escada é invisível até falhar.
**Custo:** baixo. **Ganho:** médio (diagnóstico).

---

## Ordem recomendada

1. CI + testes de `cloud.py` — barato e protege todo o resto.
2. Ferramentas escolhidas pelo modelo — maior salto de capacidade por esforço.
3. RAG com embeddings embutidos — tira a dependência do Ollama.
4. Chave protegida + lembretes que sobrevivem ao reboot — dois incômodos reais.
5. Memória v2, proatividade, ponte v2.

Itens 1, 2 e 4 podem sair numa única versão (v7.0) sem risco para o que já
funciona.
