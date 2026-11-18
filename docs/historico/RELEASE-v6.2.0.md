# T.O.R.V.I.S. 2026 v6.2.0 — a atualização agora se conclui

Base: v6.1.1. O que muda é o fim do caminho: antes o app preparava o pacote e
parava ali, sem forma de aplicar pela interface.

## O problema
`ATUALIZAR SISTEMA` baixava, validava o SHA-256, criava backup e deixava o pacote
em `...\updates\staged-<versao>`, com a mensagem "o pacote fica preparado". Nada
no projeto trocava os arquivos, então a versão instalada nunca mudava.

## O que entrou
1. **`update_manager.apply_pending_update()`** — aplica o pacote preparado na
   pasta do app:
   - revalida o manifesto antes de tocar em qualquer arquivo;
   - troca arquivo por arquivo de forma atômica (`.novo` e substituição);
   - guarda a versão anterior de cada arquivo e, se qualquer passo falhar,
     devolve tudo como estava (o app nunca fica pela metade);
   - nunca sobrescreve `config/api_keys.json`, `memory/` ou `.env`;
   - ao terminar, grava `applied.json`, apaga o `pending.json` e libera o pacote.
2. **Diálogo no app** — depois de preparar, o TORVIS pergunta "Aplicar agora?",
   fecha, aplica fora da janela e reabre. Não é mais preciso fazer nada à mão.
3. **`APLICAR-ATUALIZACAO.bat`** — aplica pelo terminal, com reabertura opcional.
4. **`tools/aplicar_atualizacao.py`** — a mesma lógica em linha de comando.

## Nota sobre quem está na 6.0.0/6.1.x
Essa versão não pode instalar a si mesma, porque o código que aplica ainda não
está lá. Para essa primeira transição existe o aplicador avulso
(`APLICAR-AGORA.bat`): ele confere o pacote, aplica e preserva a chave. Das
próximas vezes em diante, o próprio app conclui.

## Testes
135 no total (8 novos): aplica e reconhece a versão, não sobrescreve a chave do
usuário, limpa pendente e pacote, falha no meio e volta tudo, recusa manifesto
adulterado, avisa quando não há pendente ou o pacote sumiu.
