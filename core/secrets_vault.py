"""Cofre de segredos do TORVIS (DPAPI no Windows, permissão restrita no Unix).

Não exige dependências externas: usa ctypes + crypt32.dll no Windows.
"""
from __future__ import annotations

import base64
import ctypes
import ctypes.wintypes as wintypes
import platform
from typing import Optional

_PREFIXO_DPAPI = "dpapi:v1:"
_IS_WINDOWS = platform.system() == "Windows"


class _DATA_BLOB(ctypes.Structure):
    _fields_ = [
        ("cbData", wintypes.DWORD),
        ("pbData", ctypes.POINTER(ctypes.c_char)),
    ]


def _dpapi_protect(raw: bytes) -> str:
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    in_blob = _DATA_BLOB(len(raw), ctypes.create_string_buffer(raw, len(raw)))
    out_blob = _DATA_BLOB()
    if not crypt32.CryptProtectData(
        ctypes.byref(in_blob), "TORVIS-API-KEY", None, None, None, 0x1, ctypes.byref(out_blob)
    ):
        raise OSError("Falha ao criptografar chave com DPAPI")
    try:
        encrypted = ctypes.string_at(out_blob.pbData, out_blob.cbData)
        return _PREFIXO_DPAPI + base64.b64encode(encrypted).decode("ascii")
    finally:
        kernel32.LocalFree(out_blob.pbData)


def _dpapi_unprotect(encoded: str) -> str:
    payload = base64.b64decode(encoded[len(_PREFIXO_DPAPI):])
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    in_blob = _DATA_BLOB(len(payload), ctypes.create_string_buffer(payload, len(payload)))
    out_blob = _DATA_BLOB()
    if not crypt32.CryptUnprotectData(
        ctypes.byref(in_blob), None, None, None, None, 0x1, ctypes.byref(out_blob)
    ):
        raise OSError("Falha ao descriptografar chave DPAPI")
    try:
        return ctypes.string_at(out_blob.pbData, out_blob.cbData).decode("utf-8")
    finally:
        kernel32.LocalFree(out_blob.pbData)


def proteger_segredo(valor: str) -> str:
    texto = (valor or "").strip()
    if not texto or texto.startswith(_PREFIXO_DPAPI):
        return texto
    if _IS_WINDOWS:
        try:
            return _dpapi_protect(texto.encode("utf-8"))
        except Exception:
            return texto
    return texto


def revelar_segredo(valor: Optional[str]) -> str:
    texto = (valor or "").strip()
    if not texto:
        return ""
    if texto.startswith(_PREFIXO_DPAPI) and _IS_WINDOWS:
        try:
            return _dpapi_unprotect(texto)
        except Exception:
            return ""
    return texto


def esta_protegido(valor: Optional[str]) -> bool:
    return bool(valor and str(valor).startswith(_PREFIXO_DPAPI))
