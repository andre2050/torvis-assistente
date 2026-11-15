from __future__ import annotations
import importlib.util
import platform
import sys

OBRIGATORIAS = {
    "PyQt6": "Interface gráfica",
    "sounddevice": "Microfone e áudio",
    "google.genai": "Integração Google GenAI",
}

def main() -> int:
    print("Assistente Inteligente - Diagnóstico")
    print(f"Python: {sys.version.split()[0]} ({platform.architecture()[0]})")
    faltando = []
    for modulo, descricao in OBRIGATORIAS.items():
        ok = importlib.util.find_spec(modulo) is not None
        print(f"[{'OK' if ok else 'FALTA'}] {descricao}: {modulo}")
        if not ok:
            faltando.append(modulo)

    # Rede: era o ponto cego do diagnóstico — "tempo esgotado" não aparecia aqui.
    print("\nRede (Google Gemini):")
    try:
        from core.netguard_report import texto as rede_texto
        print(rede_texto())
    except Exception as exc:
        print(f"[AVISO] Não foi possível testar a rede: {type(exc).__name__}: {exc}")


    # Escada de modelos: mostra o que já foi medido nesta chave.
    print("\nModelos (ordem aprendida):")
    try:
        from core import gemini, model_ladder
        for tipo, linha in model_ladder.resumo(gemini.api_key()):
            marca = {"ok": "✔", "aviso": "!", "erro": "✖"}.get(tipo, "·")
            print(f"{marca} {linha}")
    except Exception as exc:
        print(f"[AVISO] Não foi possível ler a escada: {type(exc).__name__}: {exc}")

    # Últimos erros registrados: o que antes desaparecia com o aviso na tela.
    print("\nÚltimos erros registrados:")
    try:
        from core import errlog
        blocos = errlog.ultimos(3)
        print("\n\n".join(blocos) if blocos else "nenhum erro registrado até agora")
    except Exception as exc:
        print(f"[AVISO] {type(exc).__name__}: {exc}")

    if faltando:
        print("\nDependências ausentes:", ", ".join(faltando))
        print("Execute PREPARAR-WINDOWS.bat.")
        return 1
    print("\nDependências principais disponíveis.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
