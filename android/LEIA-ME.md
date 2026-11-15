# TORVIS 2026 no Android

Arquivo único: `TORVIS-2026-Android.html`. Nenhum servidor, nenhuma instalação.

## No celular

1. Abra o arquivo no Chrome (Downloads → toque no arquivo).
2. Menu ⋮ → **Adicionar à tela inicial**. Vira ícone, abre em tela cheia.
3. Engrenagem → cole a chave da API Gemini → **Diagnosticar** → **Salvar**.
4. Fale pelo microfone ou escreva.

## O que é igual ao app de mesa

- Escada de modelos com castigo por degrau: o modelo que dá 429/404/503 sai da
  frente por alguns minutos e o próximo responde. É o que evita "estourou a cota
  diária" com um modelo só.
- Diagnóstico em etapas: formato da chave, listagem de modelos, teste real de
  resposta, e quais degraus a chave não enxerga.
- Resposta falada em pt-BR quando a opção está ligada.

## O que não tem

- Visão de tela, controle do PC, plugins e ferramentas locais (calculadora, música,
  e-mail, Home Assistant): isso depende do Windows.
- Wake word: o Chrome só escuta depois do toque no microfone.

## Chave da API

Fica no `localStorage` do próprio aparelho. Não passa por nenhum servidor meu.
