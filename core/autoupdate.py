"""Atualização automática: baixa sozinho, aplica na abertura, sem clique.

Como funciona, em duas partes:

1. **Enquanto o app está aberto** — uma thread consulta a fonte oficial a cada
   algumas horas. Se houver versão nova, baixa, confere o SHA-256 e deixa o
   pacote preparado. Nada é trocado com o app rodando: a janela continua
   funcionando com a versão que está em memória.

2. **Na abertura seguinte** — antes de carregar a interface, o bootstrap aplica
   o pacote preparado. Como os módulos do app ainda não foram importados, o
   código novo é o que entra em uso. É por isso que a troca funciona sem
   reiniciar nada à força.

Se qualquer etapa falhar, o app abre normalmente com a versão atual: atualização
automática nunca pode ser motivo para não abrir.
"""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path

from core.paths import STATE_DIR

MARCADOR = STATE_DIR / "atualizado_em.json"
_INTERVALO_PADRAO_HORAS = 6.0


def config() -> dict:
    """Preferências do usuário, com padrões seguros (ligado)."""
    valores = {"auto_update": True, "auto_update_hours": _INTERVALO_PADRAO_HORAS,
               "auto_update_apply_on_start": True}
    try:
        from memory.config_manager import load_api_keys

        cfg = load_api_keys() or {}
        if "auto_update" in cfg:
            valores["auto_update"] = bool(cfg["auto_update"])
        if "auto_update_apply_on_start" in cfg:
            valores["auto_update_apply_on_start"] = bool(cfg["auto_update_apply_on_start"])
        horas = cfg.get("auto_update_hours")
        if isinstance(horas, (int, float)) and 0.25 <= float(horas) <= 168:
            valores["auto_update_hours"] = float(horas)
    except Exception:
        pass
    return valores


def _log(texto: str) -> None:
    try:
        from core import errlog

        errlog.registrar(texto, "auto-update")
    except Exception:
        print(f"[Auto-Update] {texto}")


def aplicar_na_abertura() -> dict | None:
    """Aplica o pacote preparado antes da interface existir.

    Devolve o resultado quando algo foi aplicado, None quando não havia nada.
    Nunca levanta: um pacote ruim não pode impedir o app de abrir.
    """
    if not config().get("auto_update_apply_on_start", True):
        return None
    try:
        from core import update_manager as um

        pendente = um.read_pending_update()
        if not pendente:
            return None
        versao_pendente = str(pendente.get("version") or "")
        instalada = um.installed_version()
        if not um.is_newer_version(versao_pendente, instalada):
            # Pacote velho ou igual: descarta para não tentar de novo toda abertura.
            um.cancel_pending_update()
            _log(f"pacote {versao_pendente} ignorado (instalada {instalada}); descartado")
            return None

        resultado = um.apply_pending_update()
        _log(f"aplicada {resultado.get('version')} na abertura "
             f"({resultado.get('applied_files')} arquivos)")
        try:
            MARCADOR.write_text(json.dumps({
                "version": resultado.get("version"),
                "when": time.time(),
                "files": resultado.get("applied_files"),
                "previous": instalada,
            }, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass
        return resultado
    except Exception as exc:
        _log(f"falha ao aplicar na abertura: {type(exc).__name__}: {exc}")
        return None


def atualizacao_recem_aplicada() -> dict | None:
    """Informação da última aplicação na abertura, para avisar o usuário uma vez."""
    try:
        dados = json.loads(MARCADOR.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if time.time() - float(dados.get("when", 0)) > 600:   # só avisa se foi agora
        return None
    try:
        MARCADOR.unlink(missing_ok=True)
    except OSError:
        pass
    return dados


def verificar_uma_vez() -> dict | None:
    """Consulta, baixa e prepara se houver versão nova. Devolve o resultado do preparo."""
    try:
        from core import update_manager as um

        info = um.check_for_update()
        if not info.get("update_available"):
            return None
        preparado = um.prepare_remote_update()
        _log(f"versão {preparado.get('remote_version') or preparado.get('version')} preparada "
             "para a próxima abertura")
        return preparado
    except Exception as exc:
        _log(f"verificação falhou: {type(exc).__name__}: {exc}")
        return None


def iniciar_vigia(ao_preparar=None, intervalo_horas: float | None = None) -> threading.Thread | None:
    """Thread que verifica de tempos em tempos, sem travar a interface."""
    preferencias = config()
    if not preferencias.get("auto_update", True):
        return None
    horas = float(intervalo_horas or preferencias.get("auto_update_hours") or _INTERVALO_PADRAO_HORAS)

    def vigiar() -> None:
        time.sleep(45)                    # deixa o app abrir e respirar primeiro
        while True:
            preparado = verificar_uma_vez()
            if preparado and callable(ao_preparar):
                try:
                    ao_preparar(preparado)
                except Exception:
                    pass
            time.sleep(max(900.0, horas * 3600.0))

    t = threading.Thread(target=vigiar, name="torvis-auto-update", daemon=True)
    t.start()
    return t
