"""Música no computador do usuário: tocar um arquivo, uma pasta ou procurar.

O YouTube já está coberto por `youtube_video`. O que faltava era a música que
está no disco: "toca aquela do Djavan", "põe a pasta de MPB", "para a música".
A busca é por trecho do nome, sem ligar para acento ou maiúscula, dentro da
pasta de músicas configurada.

Play/pause, próxima, anterior e parar reaproveitam `media_*` de
`actions.computer_settings`, que já manda as teclas de mídia do sistema — dois
implementações da mesma tecla divergiriam com o tempo.
"""
from __future__ import annotations

import os
import platform
import subprocess
import unicodedata
from pathlib import Path

_EXTENSOES = (".mp3", ".wav", ".flac", ".m4a", ".ogg", ".opus", ".wma", ".aac", ".aiff", ".mp4", ".mkv")
_MAX_VARREDURA = 4000          # arquivos examinados por busca: não varrer o disco inteiro


def _sem_acento(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", str(texto))
                   if unicodedata.category(c) != "Mn").lower()


def _pastas_candidatas() -> list[Path]:
    from core.paths import STATE_DIR

    pastas: list[Path] = []
    try:
        from memory.config_manager import load_api_keys

        configurada = str((load_api_keys() or {}).get("music_folder") or "").strip()
        if configurada:
            pastas.append(Path(configurada).expanduser())
    except Exception:                                     # noqa: BLE001
        pass
    casa = Path.home()
    for nome in ("Music", "Músicas", "Musicas", "Música"):
        pastas.append(casa / nome)
    pastas.append(STATE_DIR / "music")
    return [p for p in pastas if p.is_dir()]


def _abrir(caminho: Path) -> None:
    sistema = platform.system()
    if sistema == "Windows":
        os.startfile(str(caminho))                        # noqa: S606 — abre no player padrão
    elif sistema == "Darwin":
        subprocess.Popen(["open", str(caminho)])
    else:
        subprocess.Popen(["xdg-open", str(caminho)])


def _procurar(termo: str) -> tuple[Path | None, str]:
    alvo = _sem_acento(termo)
    examinados = 0
    pastas = _pastas_candidatas()
    if not pastas:
        return None, ("Não achei sua pasta de músicas. Me diga o caminho completo do "
                      "arquivo ou da pasta, ou configure 'music_folder' no config.json.")

    # 1) se o termo já é um caminho, respeita
    tentativa = Path(termo).expanduser()
    if tentativa.is_file():
        return tentativa, ""

    achados: list[Path] = []
    for pasta in pastas:
        for raiz, _, arquivos in os.walk(pasta):
            for nome in arquivos:
                if not nome.lower().endswith(_EXTENSOES):
                    continue
                examinados += 1
                if alvo and alvo in _sem_acento(nome):
                    achados.append(Path(raiz) / nome)
                if examinados > _MAX_VARREDURA:
                    break
            if examinados > _MAX_VARREDURA or len(achados) >= 40:
                break
        if achados or examinados > _MAX_VARREDURA:
            break

    if not achados:
        onde = ", ".join(str(p) for p in pastas[:2])
        return None, (f"Não achei nada com '{termo}' em {onde}. "
                      "Posso tocar pelo caminho completo se você me disser.")
    achados.sort(key=lambda p: (len(p.name), p.name.lower()))
    return achados[0], f"({len(achados)} opções; tocando {achados[0].name})" if len(achados) > 1 else ""


def _media(qual: str) -> str:
    """Reaproveita as teclas de mídia já implementadas em computer_settings."""
    from actions import computer_settings as cs

    funcoes = {
        "playpause": (cs.media_play_pause, "Música pausada ou retomada."),
        "next": (cs.media_next, "Pulando para a próxima."),
        "previous": (cs.media_previous, "Voltando para a anterior."),
        "stop": (cs.media_stop, "Música parada."),
    }
    funcao, frase = funcoes[qual]
    try:
        funcao()
        return frase
    except Exception as exc:                              # noqa: BLE001
        return f"Não consegui mandar o comando de mídia ({exc})."


def music_action(parameters: dict, player=None, session_memory=None) -> str:
    acao = str(parameters.get("action") or "tocar").strip().lower()
    try:
        if acao in ("tocar", "play", "musica", "música"):
            termo = str(parameters.get("query") or parameters.get("path") or "").strip()
            pasta = str(parameters.get("folder") or parameters.get("pasta") or "").strip()
            if pasta:
                destino = Path(pasta).expanduser()
                if not destino.exists():
                    resposta = f"A pasta {destino} não existe."
                elif destino.is_dir():
                    arquivos = sorted(p for p in destino.iterdir()
                                      if p.is_file() and p.suffix.lower() in _EXTENSOES)
                    if not arquivos:
                        resposta = f"A pasta {destino.name} não tem arquivos de áudio."
                    else:
                        _abrir(arquivos[0])
                        resposta = f"Tocando {arquivos[0].name} ({len(arquivos)} na pasta)."
                else:
                    _abrir(destino)
                    resposta = f"Tocando {destino.name}."
            elif not termo:
                resposta = "Qual música? Diga o nome, o arquivo ou a pasta."
            else:
                caminho, aviso = _procurar(termo)
                if not caminho:
                    resposta = aviso
                else:
                    _abrir(caminho)
                    resposta = f"Tocando {caminho.name}. {aviso}".strip()
        elif acao in ("pausar", "pause", "retomar", "play_pause", "continuar"):
            resposta = _media("playpause")
        elif acao in ("parar", "stop"):
            resposta = _media("stop")
        elif acao in ("proxima", "próxima", "next"):
            resposta = _media("next")
        elif acao in ("anterior", "previous", "voltar"):
            resposta = _media("previous")
        else:
            resposta = "Posso tocar, pausar, parar, ir para a próxima ou voltar a anterior."
    except Exception as exc:                              # noqa: BLE001
        resposta = f"Não consegui mexer na música: {exc}"

    print(f"[Música] {resposta}")
    if player:
        try:
            player.write_log(f"Assistente Inteligente: {resposta}")
        except Exception:                                 # noqa: BLE001
            pass
    return resposta


TOOL = {
    "name": "music",
    "description": (
        "Toca MÚSICA ou ÁUDIO que está no computador do usuário — arquivo, pasta ou busca "
        "pelo nome ('toca Djavan', 'põe a pasta MPB'). Também pausa, para, avança e volta a "
        "faixa. Para vídeo ou música do YouTube use youtube_video; para vídeo local use video_player."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "tocar | pausar | parar | proxima | anterior",
                "enum": ["tocar", "pausar", "parar", "proxima", "anterior"],
            },
            "query": {"type": "STRING", "description": "Trecho do nome da música ou do arquivo."},
            "path": {"type": "STRING", "description": "Caminho completo do arquivo, quando o usuário deu."},
            "folder": {"type": "STRING", "description": "Pasta de músicas a tocar do começo."},
        },
        "required": ["action"],
    },
    "tier": "extra",
    "brief": "Toca música e áudio que estão no computador.",
    "handler": music_action,
}
