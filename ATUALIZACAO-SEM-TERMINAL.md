# Atualizar o TORVIS por janela (dois cliques, sem terminal)

O botão **ATUALIZAR SISTEMA** troca arquivos com o próprio app aberto. No Windows isso trava por
três motivos: arquivo em uso, pasta sem permissão de escrita e antivírus segurando o `.zip`.

O `ATUALIZAR-TORVIS.pyw` roda **fora** do app. Sem app aberto não há arquivo em uso, e ele mostra
o motivo de cada falha em vez de esconder no log.

## Como usar

1. Feche o TORVIS.
2. Dê dois cliques em `ATUALIZAR-TORVIS.pyw`.
3. Clique em **Atualizar agora**. No fim, ele pergunta se quer abrir o TORVIS.

Se ele não achar a pasta, clique em **Escolher pasta** e aponte a pasta que tem `core/version.py`.

## O que ele faz antes de tocar em qualquer arquivo

- consulta o manifesto oficial e compara as versões;
- baixa o pacote com até três tentativas;
- confere o **SHA-256** publicado: divergência para tudo, sem tocar na instalação;
- abre o zip em memória e recusa se estiver corrompido;
- recusa pacote que não tenha `core/version.py` (não é do TORVIS);
- verifica se algum arquivo do app está em uso e, se estiver, pede para fechar primeiro.

## O que ele nunca toca

`config.json`, `memory/`, `notas`, `tarefas`, `updates/`, `dist/`, `.env`, `*.log`, `*.jsonl`,
`*.bak`, `*.zip`. Ele só acrescenta e substitui código.

## Registro

Cada execução grava `updates/atualizacao-janela.log` com versão de origem, destino, quantidade de
arquivos copiados e a lista de falhas com o motivo.

## Se o duplo clique abrir o Bloco de Notas

O Windows não associou `.pyw` ao Python. Duas saídas: renomeie para `ATUALIZAR-TORVIS.py` e rode
`py -3 ATUALIZAR-TORVIS.py`; ou (melhor) reinstale o Python marcando "Python Launcher" na primeira
tela do instalador.
