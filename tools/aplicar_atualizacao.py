"""Aplica o pacote de atualização já preparado pelo TORVIS.

O app valida, baixa e prepara, mas não troca os próprios arquivos enquanto está
aberto. Este script faz a troca: espera alguns segundos (para a janela fechar),
aplica com rollback automático e, se pedido, reabre o assistente.

Uso:
    python tools/aplicar_atualizacao.py                # aplica e reabre
    python tools/aplicar_atualizacao.py --sem-reabrir   # só aplica
    python tools/aplicar_atualizacao.py --esperar 5     # espera antes de aplicar
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))


def main() -> int:
    espera = 3.0
    if "--esperar" in sys.argv:
        try:
            espera = float(sys.argv[sys.argv.index("--esperar") + 1])
        except (IndexError, ValueError):
            pass
    reabrir = "--sem-reabrir" not in sys.argv

    try:
        from core import update_manager as um
    except Exception as exc:
        print(f"Não consegui carregar o atualizador: {type(exc).__name__}: {exc}")
        return 1

    pendente = um.read_pending_update()
    if not pendente:
        print("Não há atualização preparada.")
        print("Abra o TORVIS e use 'ATUALIZAR SISTEMA' primeiro.")
        return 1

    versao_atual = um.installed_version()
    print(f"Versão instalada: {versao_atual}")
    print(f"Versão preparada: {pendente.get('version')}")
    if pendente.get("backup_path"):
        print(f"Backup dos seus dados: {pendente['backup_path']}")
    print()

    if espera > 0:
        print(f"Aplicando em {espera:.0f} segundos (o TORVIS deve fechar para isso)...")
        time.sleep(espera)

    try:
        resultado = um.apply_pending_update(
            progress=lambda etapa, detalhe: print(f"  [{etapa}] {detalhe}"))
    except Exception as exc:
        print()
        print(f"FALHOU: {type(exc).__name__}: {exc}")
        print("Nada foi alterado: os arquivos voltaram ao estado anterior.")
        print("A atualização continua preparada; você pode tentar de novo.")
        return 2

    print()
    print(f"✓ Atualizado para {resultado['version']}")
    print(f"  {resultado['applied_files']} arquivos trocados")
    if resultado.get("skipped_files"):
        print(f"  preservados (seus dados): {', '.join(resultado['skipped_files'])}")
    print(f"  pasta: {resultado['app_dir']}")

    if reabrir:
        iniciar = Path(resultado["app_dir"]) / "INICIAR.bat"
        if iniciar.is_file():
            import subprocess
            print("\nReabrindo o TORVIS...")
            subprocess.Popen(["cmd", "/c", "start", "", str(iniciar)],
                             cwd=str(iniciar.parent), shell=False)
        else:
            print("\nAbra o TORVIS pelo INICIAR.bat quando quiser.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
