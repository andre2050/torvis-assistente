# Atualização de um clique — v6.5.0

Antes: clicar em **ATUALIZAR SISTEMA** baixava e validava o pacote, perguntava
"aplicar agora?" num diálogo e, se você dissesse sim, abria um console com
`APLICAR-ATUALIZACAO.bat`, aplicava e parava em *"pressione qualquer tecla"*.
Três confirmações para uma decisão só, e a última delas no console.

Agora: **um clique busca, instala e reabre.**

## O que acontece ao clicar

1. Consulta o `update.json` do repositório oficial.
2. Se a versão for a mesma, avisa e para. Nada é baixado.
3. Se houver versão nova: baixa o pacote, confere o SHA-256 e o manifesto interno.
4. Cria backup dos seus dados (chave, memória, configurações).
5. Prepara o pacote na pasta de estado.
6. Fecha o TORVIS e lança, fora da janela, o processo que espera e reabre.
7. Na reabertura, o pacote é aplicado **antes** de a interface existir.

O passo 7 é a decisão de projeto desta versão: quem troca os arquivos é a
abertura seguinte, não o processo que está fechando. Assim existe **um único
caminho de aplicação** (`core.autoupdate.aplicar_na_abertura`), já com rollback e
já testado, em vez de dois caminhos que podem divergir. Também é o motivo de não
haver risco de trocar arquivo com o app aberto.

## Nada de console

Quem espera e reabre é `tools/reabrir_apos_sair.py`, chamado pelo
`core.autoupdate.agendar_reabertura()` com `pythonw.exe` (sem janela) e
`CREATE_NO_WINDOW`. A espera é pelo **pid** do TORVIS, não por um tempo fixo:
o app fecha, o helper percebe e chama o `INICIAR.bat`.

## Se algo falhar

- **Aplicação falhou:** os arquivos voltam ao estado anterior (rollback), o app
  abre na versão antiga e o motivo fica em `erros.log` com a etiqueta `auto-update`.
- **Reabertura não pôde ser agendada:** o app avisa na hora e a atualização
  preparada é aplicada na próxima vez que você abrir. O plano B manual continua:
  `APLICAR-ATUALIZACAO.bat`.
- **Reabertura falhou depois:** o motivo é registrado em
  `<estado>/updates/reabertura.log`, com a causa real (o log chegou a dizer
  "não encontrei" com o arquivo presente, o que escondia o erro de verdade).

## Ao reabrir

O app mostra, por dez minutos, um aviso de que acabou de ser atualizado, com a
versão anterior e a nova (`core.autoupdate.atualizacao_recem_aplicada`).

## Seus dados não são tocados

Chave de API, memórias, configurações e histórico ficam fora do pacote
(`_protegido` no atualizador). O backup é feito antes, e o que é preservado
aparece no resultado da aplicação.

## Desligar

Em `config.json`: `"auto_update_apply_on_start": false` mantém a verificação,
mas nunca aplica sozinho. `"auto_update": false` desliga tudo, inclusive a
checagem em segundo plano a cada 6 horas.

## Testes

`python -m unittest tests.test_atualizacao_um_clique_v6_5 -v` — 13 testes,
incluindo um que sobe o helper de verdade num app de mentira e verifica que ele
reabre depois que o processo anterior sai.
