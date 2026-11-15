# TORVIS 2026 v6.6.0 — Capacidades novas

Você pediu dez áreas: controle do computador, arquivos, internet, comunicação, produtividade,
informação, mídia, ferramentas diárias, casa inteligente e desenvolvimento. Antes de escrever
código, cada área foi conferida no que o TORVIS já tinha. O resultado foi: **sete áreas já
estavam completas** e não foram tocadas; o que faltava de verdade virou oito ferramentas novas.

Nada do que existia foi alterado. As ferramentas novas são arquivos novos em `actions/`, que o
registro já descobre sozinho.

## O que já existia (não mexi)

| Área | Ferramenta que já resolve |
| --- | --- |
| Volume, brilho, atalhos, fechar janela | `computer_settings`, `computer_control` |
| Arquivos: listar, criar, mover, copiar, renomear, apagar | `file_controller` |
| Internet: buscar, abrir site, controlar navegador, notícias | `web_search`, `browser_control` |
| WhatsApp e Telegram | `send_message` |
| Lembretes na hora marcada e rotinas automáticas | `reminder`, `routines` |
| Previsão do tempo | `weather_report` |
| YouTube e vídeo local | `youtube_video`, `video_player` |
| Escrever, editar e rodar código, criar projeto | `code_helper`, `dev_agent` |

## O que faltava e entrou agora

| Ferramenta | O que faz | Detalhe que importa |
| --- | --- | --- |
| `daily_tools` | calculadora, conversor de unidades, gerador de senhas | a calculadora **não usa `eval`**: uma fala do tipo `__import__('os')` vira erro, não execução |
| `clock_info` | hora, data, dia da semana e fuso por cidade | o modelo não sabe que horas são; agora pergunta ao relógio da máquina |
| `quick_notes` | anotar, listar, buscar, ler e apagar notas | grava fora da pasta do app, então sobrevive a atualização |
| `task_list` | tarefas com projeto e prioridade, concluir, remover | separado de `reminder`: lembrete é alarme, isto é lista |
| `market_quotes` | dólar, euro, libra, bitcoin e ações da B3 | cache de 2 minutos; se a rede cair, diz que caiu em vez de inventar preço |
| `music` | toca música e áudio do disco, pausa, avança, volta | busca por trecho do nome sem ligar para acento |
| `email_reader` | checar, listar, ler e buscar e-mail (IMAP) | **somente leitura**: não envia, não apaga, e a senha não aparece na resposta |
| `smart_home` | lâmpadas, tomadas, ar-condicionado e cortinas | pelo Home Assistant; sem configuração, explica o que falta em vez de quebrar |

## O que precisa ser configurado

Só duas coisas pedem dado seu, e as duas funcionam sem configurar (só avisam que falta):

- **E-mail** — em `config.json`: `email_address`, `email_app_password` (senha de app, não a da
  conta) e, se não for Gmail/Outlook, `email_imap_host`. No Gmail a senha de app sai em
  `myaccount.google.com/apppasswords` e o IMAP precisa estar ligado.
- **Casa inteligente** — `home_assistant_url` (ex: `http://homeassistant.local:8123`) e
  `home_assistant_token` (token de longa duração criado no perfil do Home Assistant).
- **Música** — opcional: `music_folder` aponta a pasta certa. Sem isso, o TORVIS procura em
  `Músicas`.

## Dois bugs que os testes acharam (e que teriam aparecido em uso)

1. **Nota sumindo com duas falas juntas.** O armazenamento pegava a trava do arquivo e, dentro
   dela, chamava a gravação, que tentava pegar a mesma trava. Trava comum não é reentrante: o
   programa congelava. Virou `RLock`, e o teste grava 20 notas em 20 fios ao mesmo tempo para
   garantir que nenhuma se perde.
2. **Conversor aceitando família errada.** A condição que escolhia a tabela de unidades estava
   escrita de um jeito que sempre passava. Agora a conversão só acontece quando origem e destino
   estão na mesma família — "km para segundos" responde que não sabe, em vez de inventar número.

## Estado dos testes

- 143 testes passando (36 novos nesta versão).
- As 8 ferramentas novas carregam válidas no registro de ações: 32 ativas no total.
- Nada de rede nos testes: cotações, e-mail e Home Assistant usam respostas falsas.

## Como atualizar

Com a 6.5.x já instalada: **ATUALIZAR SISTEMA** na interface. Ele consulta a versão, baixa,
confere o SHA-256, faz backup, aplica e reabre sozinho. Se a reabertura falhar, o motivo fica em
`updates/reabertura.log`, e o `APLICAR-ATUALIZACAO.bat` continua como plano B.
