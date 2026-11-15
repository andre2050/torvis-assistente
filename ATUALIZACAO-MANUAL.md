# Atualização manual do TORVIS (quando o botão falha)

O botão **ATUALIZAR SISTEMA** faz o trabalho com o programa aberto. No Windows isso pode falhar
por três motivos, e nenhum deles é falta de versão publicada:

1. **arquivo em uso** — o TORVIS (ou o console do Python) ainda segura algum arquivo e o Windows
   não deixa substituir;
2. **pasta sem permissão** — instalação em `Arquivos de Programas` sem permissão de escrita;
3. **antivírus** — segura o `.zip` no meio do download e o SHA-256 não confere.

O script `tools/atualizar_manual.py` resolve os três: roda com o app fechado, confere o SHA-256
antes de instalar, diz arquivo por arquivo o que não conseguiu copiar e nunca apaga nada seu.

## Como usar

Com o TORVIS **fechado**, abra o terminal na pasta do TORVIS e rode:

```
py -3 tools\atualizar_manual.py
```

Se o script estiver salvo em outro lugar (Downloads, por exemplo), aponte a pasta:

```
py -3 "%USERPROFILE%\Downloads\atualizar_manual.py" --destino "C:\caminho\do\TORVIS"
```

Para só verificar o ambiente, sem instalar nada:

```
py -3 tools\atualizar_manual.py --diagnostico
```

E com um pacote já baixado, sem internet:

```
py -3 tools\atualizar_manual.py --pacote "%USERPROFILE%\Downloads\TORVIS-Assistente-v6.6.2.zip"
```

## O que o diagnóstico responde

- versão instalada e versão publicada;
- se a pasta do TORVIS aceita escrita;
- se o manifesto e o pacote respondem (rede, proxy, antivírus);
- se há arquivo travado por outro processo — que é a causa mais comum de "não mudou".

## O que ele nunca faz

- não apaga arquivo;
- não sobrescreve `config.json`, `memory/`, `notas`, `tarefas`, `updates/`, `dist/`, `.env`,
  `*.log`, `*.jsonl`, `*.bak`;
- não instala pacote cujo SHA-256 não confira com o publicado;
- não instala um zip que não seja do TORVIS (falta `core/version.py`).

Cada execução deixa registro em `updates/atualizacao-manual.log`, com versão de origem, versão de
destino e a lista de arquivos que falharam.
