# v6.6.9 — o agente não estraga mais o arquivo

## O que estava errado

O agente de desenvolvimento pedia o arquivo inteiro a **um** modelo e gravava o
que voltasse. Três consequências:

1. Resposta cortada (o caso clássico em CSS e JS de site) era gravada mesmo
   assim, e o projeto parava de abrir.
2. Cota estourada naquele modelo encerrava a escrita do arquivo. Os outros
   modelos nem eram tentados.
3. O relato final era "todos falharam", sem dizer qual arquivo, por quê, nem se
   o arquivo tinha sido alterado.

## O que passa a acontecer

- **Escada com descanso**: o arquivo é pedido ao modelo principal e, se der 429
  ou instabilidade, aos seguintes. O que falhou sai da fila por 10 minutos (cota)
  ou 2 minutos (instável) em vez de ser tentado a cada arquivo.
- **Validação antes de gravar**: chaves, colchetes, parênteses, strings e
  comentários são conferidos respeitando texto dentro de aspas. Python passa pelo
  compilador; JS pelo `node --check` quando existe. Resposta cortada é recusada.
- **Gravação atômica com volta atrás**: escreve em `.novo`, valida, só então
  troca; guarda `.bak`; se o disco falhar, restaura o anterior.
- **Arquivo grande é editado por trecho**: acima de 4 000 caracteres o modelo
  devolve só o bloco que muda (`<<<ANTES>>>` / `<<<DEPOIS>>>`). Se o trecho não
  casar, cai para a reescrita completa, também validada.
- **Relato útil**: "Não consegui alterar `style.css`: a resposta terminou com
  '```', veio cortada. O arquivo ficou exatamente como estava."

## Onde ficou

- `core/edicao_segura.py` — validação, gravação segura, patch e geração com
  insistência.
- `actions/dev_agent.py` — `_write_file`, `_fix_files` e `_corrigir_um_arquivo`
  passam por essa camada.
- `tests/test_edicao_segura.py` (24) e `tests/test_dev_agent_escrita.py` (8).
