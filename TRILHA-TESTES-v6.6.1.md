# TORVIS 2026 v6.6.1 — Trilha de testes automatizados para devs

A ferramenta nova é uma só, `qa_dev`, e cobre as quatro frentes pedidas. Por dentro, o motor
`core/qa.py` faz três coisas bem feitas: descobre o ambiente, cria e executa os testes, e escreve
o resultado em **JUnit XML**. Esse último ponto é o que amarra tudo: Azure Test Plans, Xray,
Azure Pipelines e GitHub Actions todos comem JUnit. Integração de teste que inventa formato
próprio não serve para nada.

## UI: Selenium, Puppeteer e Chrome for Testing

- `criar_ui` gera um teste de verdade, com arquivo no disco: `.py` (pytest + Selenium headless)
  ou `.js` (Puppeteer). O teste já vem com dois casos: o elemento aparece na tela e o texto
  esperado está no corpo da página.
- `rodar_ui` executa pelo runner certo (`python -m pytest file.py -v` ou `node file.js`), com
  tempo limite, e devolve passou/falhou com o motivo.
- **Chrome for Testing**: o diagnóstico procura o navegador em `CHROME_PATH`, no PATH, nos
  caminhos padrão do Windows/macOS e no cache do Puppeteer (`~/.cache/puppeteer`). Se não achar,
  a resposta diz o comando: `npx @puppeteer/browsers install chrome@stable`.

## API

Teste de API não usa `requests`: usa `urllib`, que já vem no Python. Dependência que falha na
hora de rodar é pior que teste que nunca existiu.

- `criar_api` cria uma coleção JSON com variáveis (`{{base}}`), método, cabeçalhos, corpo.
- `rodar_api` executa e reprova por: status diferente do esperado, campo JSON diferente
  (aceita caminho com ponto, como `itens.0.id`), texto ausente na resposta, e lentidão acima de
  `limite_ms`. Sem resposta (DNS, conexão recusada) é falha, não exceção.

## Plataformas: Azure Test Plans, Test.ai e Jira/Atlassian

- `plataformas` mostra o que está configurado e o que falta, chave por chave. Nada quebra por
  falta de configuração: a resposta diz o que colocar no `config.json`.
- `publicar` com destino `azure` cria a execução em Azure Test Plans e envia os resultados com
  `Passed`/`Failed`, duração e mensagem de erro.
- destino `jira` abre um issue de bug por teste que falhou (até 10), com método, URL, status,
  tempo e motivo. Atlassian entra por site + e-mail + token.
- destino `testai` monta o pacote `testai_payload.json` e, se houver `testai_api_url` e
  `testai_api_key`, envia.

## DevOps: pipeline pronta

`pipeline` escreve um YAML que instala dependências, roda o pytest e publica o JUnit:
`PublishTestResults@2` para Azure Pipelines, `upload-artifact` para GitHub Actions. A pipeline
roda com `continueOnError` no passo de testes e falha no passo de publicação, para o painel
mostrar os testes vermelhos em vez de um build cinza.

## Segurança

`executar()` só aceita programa de uma lista fechada (`python`, `py`, `pytest`, `node`, `npx`,
`npm`, `chrome`), nunca usa `shell=True` e mata o processo no tempo limite. Um assistente que
ouve a voz do usuário não pode virar executor de string arbitrária.

## O que precisa de configuração sua

| Recurso | Chaves no `config.json` |
| --- | --- |
| Azure Test Plans | `azure_devops_org`, `azure_devops_project`, `azure_devops_pat` |
| Jira / Atlassian | `atlassian_site`, `atlassian_email`, `atlassian_token`, `atlassian_project` |
| Test.ai | `testai_api_url`, `testai_api_key` |
| Xray (Jira Cloud) | `xray_client_id`, `xray_client_secret` |

Sem essas chaves, tudo que não depende delas funciona: criação, execução e JUnit XML.

## Três defeitos que os testes acharam nesta versão

1. **Teste de Selenium gerado não compilava**: a linha de verificação saía com indentação de 8
   espaços num corpo de função de 4. O `compile()` do teste pegou antes de você.
2. **A lista de executores recusava o próprio Python** no Linux (`python3.11` não estava na
   lista de nomes fixos). Virou expressão regular.
3. **A checagem de "encadeamento de shell" barrava código Python legítimo** (`print(1); print(2)`).
   Sem `shell=True` não existe shell para encadear: a defesa certa é a lista fechada de
   programas, e é ela que impede `bash -c` de passar.

## Estado

- 170 testes passando (27 novos).
- `qa_dev` carrega válida no registro: 33 ferramentas ativas.
- Testes da trilha rodam offline: servidor HTTP local e respostas falsas de Azure, Jira e Test.ai.

## Atualizar

`ATUALIZAR SISTEMA` na interface, ou o pacote `TORVIS-Assistente-v6.6.1.zip` desta release
copiado por cima da pasta do TORVIS (chaves, memórias, notas e tarefas ficam em `%APPDATA%`).
