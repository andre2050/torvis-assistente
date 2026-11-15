# Ponte do PC: o celular comanda a máquina

## No PC

```bash
python ponte_pc.py
```

A janela mostra o endereço (ex.: `192.168.0.10:8787`) e um código de 6 dígitos.
O código muda a cada execução. Deixe a janela aberta; Ctrl+C encerra.

## No celular

Ferramentas > Computador: cole o endereço, o código e toque em **Conectar**.
Depois é falar ou escrever:

- `no pc status` — CPU, memória, disco, nome da máquina
- `no pc aumenta o volume` / `no pc diminui o volume` / `no pc mudo`
- `no pc pausar` / `no pc próxima`
- `no pc travar`
- `no pc abrir github.com`
- `no pc desligar` — só executa depois de você responder `no pc desligar confirmo`

## Como funciona

HTTP na rede local, sem nuvem. Cada pedido leva o código no cabeçalho
`X-Codigo`; o servidor compara com `secrets.compare_digest` e recusa o resto
(401). A lista de ações é fechada: qualquer nome fora dela devolve erro.

Porta padrão 8787. Para trocar: `TORVIS_PORTA=9000 python ponte_pc.py`.
