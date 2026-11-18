# T.O.R.V.I.S. 2026 v6.3.0 — atualização automática

Base: v6.2.1. Agora o app se atualiza sozinho, sem clicar em nada.

## Como funciona
1. **Com o app aberto:** uma thread consulta a fonte oficial (padrão: a cada 6
   horas, com 45 s de folga na abertura para a janela carregar). Se houver
   versão nova, baixa, confere o SHA-256, valida o conteúdo e deixa preparado.
   Avisa na tela: "Versão X baixada; será aplicada na próxima abertura".
2. **Na abertura seguinte:** `iniciar_auto.py` aplica o pacote **antes** de
   importar qualquer módulo da interface. Como o código novo entra em uso desde
   o início, não é preciso fechar nada à força nem reiniciar duas vezes.
3. **Depois de aplicar:** o app mostra "Versão X aplicada automaticamente" uma
   única vez, com a versão anterior.

## Por que é seguro
- Falha em qualquer etapa (rede, download, hash, cópia) nunca impede a abertura:
  o app abre na versão atual e registra o motivo em `erros.log`.
- A aplicação mantém o rollback da v6.2.0: cópia de cada arquivo antes de trocar,
  e volta tudo se algo falhar no meio.
- `config/api_keys.json`, `memory/` e `.env` nunca são sobrescritos.
- Pacote igual ou mais antigo é descartado em vez de reaplicado.

## Preferências (config)
- `auto_update` — liga/desliga a verificação (padrão: ligada)
- `auto_update_hours` — intervalo entre verificações (padrão: 6; entre 0,25 e 168)
- `auto_update_apply_on_start` — aplica na abertura (padrão: ligado)

## Correção incluída
- `gui/window.py` chamava `self.toast()`, que não existe, ao falhar o aplicador.
  Agora usa o log da interface — o erro aparecia como `AttributeError`.

## Testes
153 no total (14 novos): aplica só quando há versão nova, descarta pacote igual,
falha sem levantar, respeita a preferência, avisa uma vez, prepara em segundo
plano e abre mesmo quando a aplicação falha.
