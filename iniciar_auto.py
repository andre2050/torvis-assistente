"""Abertura do TORVIS com atualização automática.

Este arquivo fica entre o INICIAR.bat e o main.py de propósito: ele aplica o
pacote preparado ANTES de qualquer módulo da interface ser importado. Assim o
código novo é o que entra em uso, sem precisar fechar nada à força nem reiniciar
duas vezes.

Se não houver atualização preparada, ele simplesmente abre o app — e se a
aplicação falhar, também abre, avisando no log. Atualização nunca impede o uso.
"""
from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))


def main() -> int:
    try:
        from core import autoupdate

        resultado = autoupdate.aplicar_na_abertura()
        if resultado:
            print(f"[Atualização] versão {resultado.get('version')} aplicada "
                  f"({resultado.get('applied_files')} arquivos).")
    except Exception as exc:                     # nunca impede a abertura
        print(f"[Atualização] ignorada: {type(exc).__name__}: {exc}")

    import main as app

    app.main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
