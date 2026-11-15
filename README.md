# T.O.R.V.I.S. 2026 — ULTRA AI

Assistente pessoal para Windows com voz, memória, HUBs animados, automação de desktop e
integração com o Gemini (Live e texto). Versão atual: **6.1.1**.

Este repositório é o código-fonte. Ele **não** contém executável compilado: o `.exe` é
gerado na sua máquina com `CRIAR-EXECUTAVEL.bat`.

---

## Começando no Windows

```
1. Instale o Python 3.11 ou 3.12 (64 bits) → python.org
2. Duplo clique em PREPARAR-WINDOWS.bat     (instala as dependências)
3. Duplo clique em INICIAR.bat              (abre o assistente)
```

Se algo não funcionar, na ordem:

| Atalho | Para que serve |
|---|---|
| `DIAGNOSTICO-REDE.bat` | Testa DNS, porta 443, TLS, HTTP e IPv6 |
| `GERAR-RELATORIO.bat` | Gera um `.txt` com sistema, rede, modelos e últimos erros |
| `PREPARAR-WINDOWS.bat` | Reinstala as dependências |

O relatório **não** contém a sua chave de API.

## Chave do Gemini

Crie a chave em [aistudio.google.com/apikey](https://aistudio.google.com/apikey) e cole
dentro do app, em *Configurações → IA e chaves*. Ela fica só no seu computador, na pasta de
dados do usuário — nunca neste repositório.

## Bibliotecas

Obrigatórias: `PyQt6`, `google-genai`.
Recomendada: `psutil` (monitor de CPU/RAM/rede).

```bash
pip install PyQt6 google-genai psutil
```

`openai` e Ollama são opcionais: só entram em uso se você configurar esse provedor.

## Estrutura

```
core/        núcleo: IA (gemini), memória, RAG, voz, automação, rede, telemetria
gui/         interface: janela, HUBs, HUD, painéis, temas
actions/     ferramentas que o assistente executa (arquivos, sistema, dev, jogos)
dashboard/   servidor local para acessar pelo celular
tests/       127 testes automatizados
tools/       utilitários de desenvolvimento (renderização dos HUBs)
```

## Testes

```bash
python -m pytest tests -q      # 127 passed
```

Cobrem escada de modelos, orçamento diário, log de erros, rede/IPv4, relatório e firewall.

## O que há de novo nas últimas versões

- **6.1.1** — HUBs com material de metal escovado, oclusão de ambiente, duas fontes de luz,
  Fresnel, bloom, reflexo de piso e grão. Material em cache para não pesar no quadro.
- **6.1.0** — Relatório de um clique, métricas por execução, orçamento diário de IA.
- **6.0.2** — Escada de modelos aprende a ordem do uso real; `erros.log` com traceback.
- **6.0.1** — Correção do firewall Linux (`NameError`), proteção contra IPv6 quebrado,
  diagnóstico de rede.

## Estado atual

Funciona e passa nos testes, mas **alguns caminhos só se validam em Windows real**:
microfone, áudio/SAPI, visão de tela, Gemini Live e o executável empacotado. Rode
`GERAR-RELATORIO.bat` no Windows e anexe o arquivo ao abrir uma issue.

## Licença

Base herdada de **MARK 56 — JARVIS** (c) 2026 FatihMakes, com modificações deste projeto.
Veja `LICENSE`.
