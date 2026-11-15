# LABORATÓRIO — v6.4.0

Duas funções num painel só: o conjunto de ajuste fino e o relatório do capstone.
Botão **🎓 LABORATÓRIO** no drawer de configurações.

## O que é ajuste fino, em uma frase

É pegar o modelo de texto que o assistente usa e treinar uma cópia dele com
exemplos do seu jeito de falar, das suas preferências e das correções que você já
fez — para que ele responda mais parecido com o que você espera, sem precisar
repetir tudo no prompt a cada conversa.

O prompt diz o que fazer naquele momento. O ajuste fino muda o comportamento
padrão do modelo. É a diferença entre instruir um funcionário novo todo dia e
contratar alguém que já conhece a empresa.

## Por que isso faz sentido aqui

O TORVIS já guarda esse material: `long_term.json` (identidade, preferências,
projetos, relações), `cognitive_memory.json` (lembranças) e os resumos de sessão.
Sem uma ferramenta, esse acervo fica parado. Com ela, vira arquivo de treino.

## O que o painel faz

- **Número antes do botão:** quantas memórias existem, quantos exemplos sairiam,
  quantos tokens em estimativa e quantos dados sensíveis seriam mascarados.
- **Gerar conjunto:** valida, remove repetidos e vazios, divide treino/validação
  e grava três arquivos em `<estado>/finetuning/`:
  - `treino-AAAAMMDD-HHMM.jsonl`
  - `validacao-AAAAMMDD-HHMM.jsonl`
  - `resumo-AAAAMMDD-HHMM.json`
- **Abrir pasta:** leva direto ao diretório, sem procurar.

Formato de cada linha (esquema de ajuste do Gemini):

```json
{"messages": [{"role": "user", "content": "..."},
              {"role": "model", "content": "..."}]}
```

## O que ele deliberadamente não faz

- **Não treina e não envia nada.** Monta o arquivo; o envio é seu, no console do
  provedor. Nenhuma chamada de rede acontece nesta função.
- **Não inventa exemplo.** Cada par vem de uma memória, sessão ou correção, e o
  manifesto guarda a origem de cada um.
- **Não garante resultado.** Ajuste fino melhora estilo e consistência; não
  transforma o modelo em oráculo nem substitui contexto.

## Mascaramento

Antes de gravar, o texto passa por um saneador: chaves de API, e-mails, CPF,
CNPJ e telefones viram marcadores (`[email]`, `[telefone]`…). O painel informa
quantos foram mascarados — revisar continua sendo trabalho humano.

## Correções: a fonte mais valiosa

`core.finetuning.registrar_correcao(pergunta, resposta)` grava um par vindo do
uso real. É o exemplo que mais ensina, porque veio do dono e não de uma memória
genérica. O arquivo é `correcoes.jsonl`, dentro do diretório de treino.

## O que é o capstone

É o trabalho de conclusão, e ele pede números: quantos módulos, quantas linhas,
quantos testes, o que cada pacote faz, o que ficou de fora. Escrever isso à mão
envelhece no dia seguinte. O painel lê o projeto e escreve:

- `docs/relatorio-tecnico.md` — para editar e colar no trabalho
- `docs/relatorio-tecnico.html` — abre no navegador, Ctrl+P gera o PDF
- `docs/roteiro-defesa.md` — dez tópicos, com o que dizer e o que mostrar em cada um

O relatório não inventa resultado: se a suíte não foi executada, ele não exibe
número de testes aprovados.

## Cuidados honestos

- O ajuste fino **não** altera a conversa ao vivo, que é o coração do TORVIS: ele
  troca o modelo usado nas tarefas escritas.
- Mínimo de exemplos e preço do treino mudam de provedor para provedor e ao longo
  do tempo. O programa não adivinha: ele manda conferir no console.
- Compare o modelo novo com o antigo antes de torná-lo padrão. Ajuste fino com
  conjunto pequeno piora mais do que melhora.

## Como testar sem esperar o uso render

```bash
python -m unittest tests.test_laboratorio_v6_4 -v   # 22 testes
```
