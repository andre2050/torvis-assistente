# Secretária de WhatsApp do TORVIS

Responde mensagens em texto, entende nota de voz e responde também em áudio.
Quando a ligação não é atendida, manda um recado no lugar do toque perdido.

## O limite honesto sobre ligação

A API de mensagens da Meta **não atende ligação**. Atender e conversar por voz
só existe pela WhatsApp Business Calling API (disponível desde julho de 2025),
que exige conta business verificada, número elegível, endereço público de
webhook e streaming de áudio em tempo real. É um projeto separado; o que esta
versão entrega é a resposta imediata a quem ligou e não foi atendido.

## O que você precisa da Meta

1. Conta no Meta for Developers com um app do tipo Business.
2. O produto WhatsApp adicionado, com um número de telefone verificado.
3. Dois valores, tirados do painel:

   - **token** de acesso permanente
   - **id do número de telefone** (Phone number ID)

## Configuração no TORVIS

O arquivo fica em `userdata/whatsapp.json` e começa assim:

```json
{
  "token": "",
  "numero_id": "",
  "verificar": "torvis-12345",
  "ligada": false,
  "responder_audio": true,
  "permitidos": [],
  "silencioso_inicio": 23,
  "silencioso_fim": 7,
  "recado": "Não consigo falar agora. Me diz por aqui o que você precisa que eu já vejo."
}
```

Pelo próprio assistente, sem editar arquivo:

- "liga a secretária do WhatsApp" (ferramenta `whatsapp_secretary`, ação `ligar`)
- "só atende o número 5585999991234" (ação `permitir`)
- "manda um áudio pro 5585999991234 dizendo que já vou" (ação `audio`)
- "muda o recado para: estou em reunião" (ação `recado`)

## Receber as mensagens

A Meta precisa de um endereço público apontando para o PC. O servidor do
projeto escuta assim:

```
python tools/servidor_whatsapp.py --porta 8099
```

Ele imprime o token de verificação e o caminho `/webhook`. No painel da Meta,
cadastre esse endereço e assine os eventos `messages` e `calls`. Para expor o PC
à internet, use o método de túnel que você já prefere; o servidor não muda.

Para ensaiar sem credencial nenhuma: `python tools/servidor_whatsapp.py --ensaio`.

## Cuidados

- **Lista de permitidos vazia atende qualquer número.** Preencha antes de ligar.
- Deixe `silencioso_inicio` e `silencioso_fim` iguais para atender 24 horas.
- O servidor responde 200 mesmo quando algo falha ao processar; se devolvesse
  erro, a Meta reenviaria a mesma mensagem em laço.
- Conversa iniciada pela empresa fora da janela de 24 horas exige modelo
  aprovado. Responder a quem escreveu primeiro não tem esse problema.
- Nota de voz aceita mp3, ogg/opus, aac, mp4 e amr, até 16 MB (limite da Meta).

## Testes

`tests/test_whatsapp.py` (20) cobre envio, transcrição, horário, permitidos e
chamada perdida. `tests/test_whatsapp_servidor.py` (6) sobe o servidor de
verdade numa porta livre e conversa por HTTP, incluindo o desafio da Meta e o
token errado.
