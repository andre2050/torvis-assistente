"""Google Maps: busca e direções baseadas no endereço pedido pelo usuário."""
from __future__ import annotations

import webbrowser
from urllib.parse import quote


def google_maps(parameters=None, **_context) -> str:
    params = parameters or {}
    query = str(params.get("address") or params.get("query") or "").strip()
    if not query or len(query) > 600:
        return "Informe um endereço ou local (até 600 caracteres) para abrir no Google Maps."
    mode = str(params.get("mode") or "search").lower()
    if mode not in ("search", "directions"):
        return "Modo inválido: use search ou directions."
    encoded = quote(query, safe="")
    url = ("https://www.google.com/maps/dir/?api=1&destination=" if mode == "directions"
           else "https://www.google.com/maps/search/?api=1&query=") + encoded
    try:
        opened = webbrowser.open(url)
    except Exception as exc:
        return f"Não consegui abrir o navegador: {exc}. Link para abrir manualmente: {url}"
    if opened:
        return f"Abri uma pesquisa no Google Maps: {url}. Confirme o endereço no mapa antes de navegar."
    return f"Não foi possível confirmar a abertura do navegador. Abra manualmente: {url}"


TOOL = {
    "name": "google_maps",
    "description": "Abre uma pesquisa ou rota para endereço solicitado explicitamente no Google Maps; não inventa localização nem confirma resultados sem verificar.",
    "parameters": {"type": "OBJECT", "properties": {
        "address": {"type": "STRING", "description": "Endereço ou nome de local a pesquisar"},
        "mode": {"type": "STRING", "description": "search para pesquisar; directions para criar rota"},
    }},
    "handler": google_maps,
    "tier": "core",
}
