# T.O.R.V.I.S 2026 v5.6.1 — Atualizador GitHub

## Fonte oficial

Por padrão, o I.S.A. consulta:

`https://raw.githubusercontent.com/andre2050/torvis-assistente/main/update.json`

A URL pode ser substituída por `TORVIS_UPDATE_MANIFEST_URL` ou pela chave
`update_manifest_url` da configuração, útil para homologação.

## Fluxo de segurança

1. Consulta `update.json` somente por HTTPS.
2. Compara a versão remota com a versão instalada.
3. Baixa o ZIP para a pasta de estado do usuário.
4. Valida o SHA-256 do ZIP antes de extrair.
5. Extrai em diretório temporário com proteção contra path traversal e symlinks.
6. Valida `update-manifest.json` e os hashes dos arquivos internos.
7. Cria backup completo de `config/` e `memory/`.
8. Prepara o pacote em `updates/staged-<versão>` e grava `pending.json`.

O aplicativo não tenta sobrescrever à força o próprio executável em uso. O pacote
fica preparado para um instalador/helper aplicar de forma segura no próximo ciclo.

## Manifesto remoto

Exemplo:

```json
{
  "version": "5.6.2",
  "channel": "stable",
  "package_url": "https://raw.githubusercontent.com/andre2050/torvis-assistente/main/releases/v5.6.2/TORVIS-Assistente-v5.6.2.zip",
  "sha256": "<64 caracteres hex>",
  "release_notes": "Melhorias e correções."
}
```
