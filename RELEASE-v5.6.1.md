# Release 5.6.1 — Atualizador GitHub

- Fonte oficial pré-configurada para `andre2050/torvis-assistente`.
- Comparação de versões sem dependência externa.
- Download HTTPS em streaming com limite de tamanho.
- Validação SHA-256 do ZIP.
- Extração segura contra path traversal e symlinks.
- Manifesto interno com hashes dos arquivos do pacote.
- Backup de configurações e memórias antes do staging.
- `pending.json` com origem, hash, backup e caminho preparado.
- Botão **Atualizar Sistema** executado em thread para não travar a interface.
- Mensagens claras para sistema atualizado, atualização preparada, 404 e falha de rede.
