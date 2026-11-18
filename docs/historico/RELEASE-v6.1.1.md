# T.O.R.V.I.S. 2026 v6.1.1 — HUBs com material e iluminação de estúdio

Base: v6.1.0. Só o renderizador dos HUBs mudou.

## O que mudou no visual
1. **Metal escovado.** Dezenas de arcos finíssimos de alfa alternado, imitando as
   marcas de usinagem de uma peça torneada. O padrão é calculado, não sorteado:
   não treme enquanto o HUB gira.
2. **Oclusão de ambiente.** Escurecimento onde as peças se encontram: sem isso a
   geometria parece colada no fundo.
3. **Duas fontes de luz.** Quente em cima à esquerda (aresta clara) e fria embaixo
   à direita (azulada), que é o que separa o objeto da parede.
4. **Fresnel.** A borda ganha luz quando vista de raspão, como vidro real.
5. **Bloom aditivo** em três raios ao redor do núcleo.
6. **Reflexo de piso** alongado e **grão fino** que quebra o degradê liso.
7. Scanlines e brilho especular continuam acompanhando a amplitude da voz.

## Desempenho (medido, 30 fps = 33 ms por quadro)
- Material estático agora vai para um QPixmap em cache: 10,2 ms → 7,8 ms por
  quadro no HUB de 400 px.
- Densidade das marcas escala com o tamanho: miniatura da galeria não paga o
  custo do HUB grande.
- O HUD real tem no mínimo 300×300, então o custo fica abaixo do medido.

## Ferramentas
`tools/render_hubs.py` (grade dos nove) e `tools/render_hub_grande.py` (um HUB
ampliado) geram PNG sem abrir a interface, para comparar versões.
