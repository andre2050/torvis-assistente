# T.O.R.V.I.S. 2026 — v5.7.1 (Cowork mais rápido)

Atualização incremental da versão 5.7.0. Mantém LLM, RAG, provedores e agentes.

- Novos projetos Python simples começam automaticamente no perfil rápido; projetos complexos mantêm o planejamento completo. Use `profile: full` para forçar o processo completo.
- Se uma geração em lote falhar, o Cowork agora gera até **dois arquivos independentes em paralelo**, preservando a ordem das dependências locais. Isso pode reduzir o tempo de criação quando o provedor responde com boa latência, mas não garante um tempo fixo.
- Arquivos ausentes impedem a falsa mensagem de conclusão: o projeto é identificado como **parcial**.
- Planos vindos do modelo não podem gravar arquivos fora da pasta do projeto ou usar caminhos duplicados.

## Testes e limites

Testes automatizados locais cobrem concorrência, segurança de caminhos, dependências e resultados incompletos. Testes com microfone, interface Windows e APIs reais ainda exigem ambiente Windows e credenciais do usuário; nenhuma compilação `.exe` foi realizada aqui. O arquivo `update-manifest.json` é interno ao ZIP: **não indica que há uma atualização publicada no GitHub**.
