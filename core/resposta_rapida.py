"""Resposta rápida: seleciona em qualquer programa, aperta o atalho, volta pronto.

O trabalho real é dividido em duas partes: a transformação do texto (pura, fácil
de testar) e o transporte até o cursor do outro programa (copiar a seleção,
transformar, colar de volta). O transporte só existe onde há área de
transferência e teclado simulável, e falha com uma mensagem clara quando não há.
"""
from __future__ import annotations

from typing import Callable

MODOS = {
    "resumir": "Resuma o texto abaixo em no máximo 3 frases, sem opinião:",
    "reescrever": ("Reescreva o texto abaixo com clareza e concisão, mantendo "
                   "o sentido e o tom, sem acrescentar informação:"),
    "traduzir": ("Traduza o texto abaixo para português do Brasil, mantendo "
                 "nomes próprios e termos técnicos:"),
    "corrigir": ("Corrija ortografia, gramática e pontuação do texto abaixo, "
                 "sem reescrever o estilo:"),
    "explicar": "Explique em linguagem simples o que o texto abaixo diz:",
}
LIMITE = 8000


def instrucao(modo: str) -> str:
    chave = (modo or "").strip().lower()
    if chave not in MODOS:
        raise ValueError(f"modo desconhecido: {modo!r}. Use {', '.join(MODOS)}")
    return MODOS[chave]


def transformar(texto: str, modo: str, gerador: Callable[[str], str]) -> str:
    """Aplica o modo ao texto usando o gerador de linguagem do TORVIS."""
    limpo = (texto or "").strip()
    if not limpo:
        raise ValueError("nada selecionado")
    pedido = f"{instrucao(modo)}\n\n{limpo[:LIMITE]}"
    resposta = (gerador(pedido) or "").strip()
    if not resposta:
        raise RuntimeError("o modelo não devolveu texto")
    return resposta


def _clipboard():
    try:
        import pyperclip
        return pyperclip
    except Exception as exc:  # pragma: no cover - depende da máquina
        raise RuntimeError("área de transferência indisponível: instale pyperclip") from exc


def capturar_selecao(atalho_copiar: str = "ctrl+c") -> str:
    """Copia a seleção do programa em foco e devolve o texto."""
    try:
        import pyautogui
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("não consigo simular teclado: instale pyautogui") from exc
    clip = _clipboard()
    anterior = ""
    try:
        anterior = clip.paste()
    except Exception:
        pass
    try:
        clip.copy("")
    except Exception:
        pass
    pyautogui.hotkey(*atalho_copiar.split("+"))
    import time
    time.sleep(0.25)
    try:
        texto = clip.paste() or ""
    finally:
        if anterior:
            try:
                clip.copy(anterior)
            except Exception:
                pass
    return texto.strip()


def colar(texto: str) -> None:
    """Devolve o texto no cursor do programa que estava em foco."""
    clip = _clipboard()
    clip.copy(texto)
    try:
        import pyautogui
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("não consigo simular teclado: instale pyautogui") from exc
    pyautogui.hotkey("ctrl", "v")


def executar(modo: str, gerador: Callable[[str], str], *, colar_de_volta: bool = True) -> dict:
    """Fluxo completo: seleção → transformação → cursor."""
    original = capturar_selecao()
    if not original:
        return {"ok": False, "motivo": "nada estava selecionado"}
    novo = transformar(original, modo, gerador)
    if colar_de_volta:
        colar(novo)
    return {"ok": True, "modo": modo, "original": original[:400], "resultado": novo}
