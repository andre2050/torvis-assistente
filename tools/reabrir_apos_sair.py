"""Espera o TORVIS fechar e reabre — a parte que roda fora da janela.

POR QUE ESTE ARQUIVO EXISTE
    O clique em "ATUALIZAR SISTEMA" termina com o app se fechando. Alguém precisa
    reabri-lo: o próprio processo não consegue fazer isso depois de sair. Antes
    essa tarefa era do APLICAR-ATUALIZACAO.bat, que abria um console e pedia uma
    tecla — fricção que quebrava a ideia de "um clique".

    Aqui não se troca arquivo nenhum. Quem aplica o pacote é a abertura do app
    (core.autoupdate.aplicar_na_abertura), que já faz isso com rollback e antes
    de a interface existir. Este script só espera o processo anterior sair e
    chama o INICIAR.bat. Um caminho só para aplicar, testado em um lugar só.

Uso (chamado pelo core.autoupdate, não pelo usuário):
    python tools/reabrir_apos_sair.py --pid 1234
    python tools/reabrir_apos_sair.py --pid 1234 --esperar-max 120 --log arquivo
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


def _vivo(pid: int) -> bool:
    """True enquanto o processo existir E estiver rodando.

    No Linux, um processo que já terminou mas ainda não foi colhido (zumbi)
    continua respondendo ao teste de existência por pid. Tratá-lo como vivo
    fazia a reabertura esperar o tempo limite inteiro por um app que já tinha
    fechado — foi o que este arquivo descobriu no primeiro teste de ponta a
    ponta. Lemos o estado em /proc e consideramos "Z" como morto.
    """
    if pid <= 0:
        return False
    try:
        if os.name == "nt":
            import ctypes
            QUERY = 0x1000                     # PROCESS_QUERY_LIMITED_INFORMATION
            STILL_ACTIVE = 259
            k32 = ctypes.windll.kernel32
            mao = k32.OpenProcess(QUERY, False, pid)
            if not mao:
                return False
            try:
                codigo = ctypes.c_ulong()
                if not k32.GetExitCodeProcess(mao, ctypes.byref(codigo)):
                    return True
                return codigo.value == STILL_ACTIVE
            finally:
                k32.CloseHandle(mao)

        if Path("/proc/self").exists():
            try:
                stat = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8", errors="replace")
            except FileNotFoundError:
                return False
            except OSError:
                pass                                # sem permissão: decide pelo kill
            else:
                try:
                    return stat[stat.rindex(")") + 2] != "Z"
                except (ValueError, IndexError):
                    pass

        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except OSError:
        return False
    except Exception:                          # noqa: BLE001 — nunca matar a reabertura
        return True


def esperar_sair(pid: int, maximo: float = 120.0, passo: float = 0.4) -> bool:
    """Aguarda o processo sair. True se ele saiu, False se estourou o tempo."""
    if pid <= 0:
        return True
    limite = time.monotonic() + maximo
    while time.monotonic() < limite:
        if not _vivo(pid):
            return True
        time.sleep(passo)
    return not _vivo(pid)


def _registrar(caminho: Path | None, texto: str) -> None:
    if not caminho:
        return
    try:
        caminho.parent.mkdir(parents=True, exist_ok=True)
        carimbo = time.strftime("%d/%m/%Y %H:%M:%S")
        with caminho.open("a", encoding="utf-8") as f:
            f.write(f"[{carimbo}] {texto}\n")
    except OSError:
        pass


def reabrir(raiz: Path | None = None) -> tuple[bool, str]:
    """Reabre o app e devolve (deu_certo, motivo).

    Duas tentativas, nesta ordem: o INICIAR.bat (é ele que prepara o ambiente e o
    venv) e, se a chamada falhar, o main.py direto pelo interpretador atual. A
    mensagem de erro precisa dizer o que falhou: "não encontrei" quando o arquivo
    existe esconde a causa real e já custou uma depuração.
    """
    base = Path(raiz) if raiz else RAIZ
    iniciar = base / "INICIAR.bat"
    main = base / "main.py"
    motivos: list[str] = []

    if iniciar.is_file():
        try:
            subprocess.Popen(["cmd", "/c", "start", "", str(iniciar)],
                             cwd=str(base), shell=False)
            return True, f"INICIAR.bat executado ({iniciar})"
        except Exception as exc:                       # noqa: BLE001
            motivos.append(f"INICIAR.bat falhou: {type(exc).__name__}: {exc}")
    else:
        motivos.append("INICIAR.bat não existe")

    if main.is_file():
        try:
            exe = sys.executable
            if os.name == "nt":
                candidato = Path(exe).with_name("pythonw.exe")
                if candidato.is_file():
                    exe = str(candidato)
            subprocess.Popen([exe, str(main)], cwd=str(base), shell=False)
            return True, f"main.py executado com {Path(exe).name}"
        except Exception as exc:                       # noqa: BLE001
            motivos.append(f"main.py falhou: {type(exc).__name__}: {exc}")
    else:
        motivos.append("main.py não existe")

    return False, "; ".join(motivos)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Reabre o TORVIS após uma atualização.")
    parser.add_argument("--pid", type=int, default=0,
                        help="processo do TORVIS que deve fechar antes da reabertura")
    parser.add_argument("--esperar-max", type=float, default=120.0,
                        help="segundos máximos de espera pelo fechamento")
    parser.add_argument("--sem-reabrir", action="store_true",
                        help="só esperar, sem abrir o app")
    parser.add_argument("--log", default="", help="arquivo de log opcional")
    args = parser.parse_args(argv)

    log = Path(args.log) if args.log else None
    _registrar(log, f"aguardando o processo {args.pid} sair (máx {args.esperar_max:.0f}s)")
    saiu = esperar_sair(args.pid, args.esperar_max)
    if not saiu:
        _registrar(log, "o app não fechou no tempo previsto; tentando reabrir mesmo assim")

    if args.sem_reabrir:
        _registrar(log, "reabertura desativada por argumento")
        return 0

    ok, motivo = reabrir()
    _registrar(log, f"reabertura: {motivo}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
