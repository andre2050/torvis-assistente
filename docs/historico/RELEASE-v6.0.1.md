# T.O.R.V.I.S. 2026 v6.0.1 — correção de rede e do firewall

Base: v6.0.0 RC1 (nada removido; só correções e um módulo novo).

## 1. Bug corrigido: firewall Linux derrubava a configuração de rede
`fix_network_access()` usava uma variável `port` que não existia no escopo.
Resultado: `NameError` em qualquer Linux com ufw/firewalld/iptables ativo, e as
portas do dashboard nunca eram liberadas. Agora percorre cada porta recebida.

## 2. Causa mais comum de "tempo esgotado" tratada: IPv6 quebrado
Quando o IPv6 da máquina existe mas não conecta (comum no Windows com certos
roteadores, VPN e antivírus), o Python tenta IPv6 primeiro e espera até estourar
o tempo, mesmo com a internet funcionando por IPv4.

Novo `core/netguard.py`:
- testa o IPv6 uma vez, em segundo plano, ao abrir o app (não atrasa a janela);
- se o IPv6 falhar, a resolução passa a devolver IPv4 primeiro para TODO o
  processo: SDK do Gemini, urllib, websockets. Nada é descartado, só reordenado;
- se o IPv6 estiver bom, não muda nada.

## 3. O diagnóstico agora enxerga a rede
`diagnostico_windows.py` passa a testar, além das dependências:
proxy do sistema, DNS, porta 443, certificado TLS, resposta HTTP e IPv6 —
e termina com uma frase dizendo o que fazer. Antes ele dizia "dependências OK"
e o usuário continuava sem conexão, sem pista nenhuma.

Novo atalho: `DIAGNOSTICO-REDE.bat` (ou `python -m core.netguard_report`).

## 4. Testes
96 testes (90 herdados + 6 novos): IPv6 quebrado liga a proteção, ordenação
coloca IPv4 na frente sem descartar IPv6, IPv6 saudável não altera nada, teste
em segundo plano não bloqueia, e o caminho do firewall roda sem NameError.

## O que NÃO foi mexido, de propósito
- A escada de modelos (`core/gemini.py`) tem tempos medidos em comentário e
  cooldown por esgotamento de cota: é decisão de produto, não bug. Só mexi se
  houvesse nome inexistente comprovado.
- Arquivos grandes (`gui/window.py` 3.5k linhas, `main.py` 3.2k) não foram
  fatiados nesta entrega: refatoração desse porte precisa de validação em
  Windows real, com microfone e tela, e não cabe num passo seguro.

## Validação
- `pytest tests` → 96 passed
- `pyflakes` em todos os .py → nenhum nome indefinido
- `python diagnostico_windows.py` → reporta rede + dependências
