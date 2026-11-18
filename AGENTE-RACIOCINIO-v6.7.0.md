# Agentes autônomos mais inteligentes (ciclo de raciocínio)

Arquivo principal: `core/raciocinio.py`. Ferramenta para a voz: `smart_agent` (`actions/smart_agent.py`).

| # | Recurso | Onde |
|---|---------|------|
| 1 | Intenção em JSON (ação, ferramenta, parâmetros, faltando, ambiguidades, suposições) com fallback sem LLM | `entender_intencao` |
| 2 | Planejar → agir → observar → ajustar (replaneja até 2x quando um passo falha) | `AgenteAutonomo.executar_verificando` + `replanejar_com_llm` |
| 3 | Ferramentas com descrição, parâmetros e custo do erro | `CatalogoFerramentas`, `NucleoISA.registrar_ferramenta(..., descricao, parametros, custo_erro)`, `ligar_registro_de_acoes` |
| 4 | Perguntar só quando precisa: dado faltando, risco médio/alto ou confiança < 0,4. Ambíguo + barato = assume e avisa | `decidir` |
| 5 | Memória: lê a Memória Cognitiva (só explícita) e guarda hábitos por período do dia | `CadernoDeCorrecoes` |
| 6 | Aprende com "não, não era isso": guarda pedido/erro/correção e usa como exemplo | `eh_correcao`, `CadernoDeCorrecoes` |
| 7 | Verifica o resultado: `status=failed` não é sucesso; `unverified` é avisado; verificador opcional | `verificar` |
| 8 | Contexto do momento: hora, período, dia, app em foco (Windows), último pedido, histórico | `contexto_do_momento` |

Agentes em segundo plano (`core/tasks/engine.py`): regras de intenção/verificação, bloco `[CONTEXT]`
(período do dia e tarefas recentes, só para agentes sem web) e uma checagem única do resultado
contra o pedido antes de entregar.

Segurança mantida: só ferramentas registradas, confirmação para risco médio/alto, sem shell arbitrário.
Correções e hábitos ficam em `agente_correcoes.json` (pasta de memória); apagar o arquivo zera o aprendizado.
Também corrigido: `NucleoISA.executar` quebrava com ferramentas que têm parâmetro chamado `nome`.
