"""Atualizador transacional do T.O.R.V.I.S 2026.

Fluxo remoto (v5.6.1):
1. consulta um manifesto JSON via HTTPS;
2. compara a versão remota com a instalada;
3. baixa o ZIP para a pasta de estado do usuário;
4. valida o SHA-256 do ZIP;
5. extrai sem permitir path traversal/symlinks;
6. valida o ``update-manifest.json`` interno e seus arquivos;
7. cria backup dos dados mutáveis do usuário;
8. prepara a atualização em ``STATE_DIR/updates``.

A substituição do executável em uso continua separada. Isso é intencional: no
Windows, sobrescrever o próprio .exe enquanto ele está rodando é frágil. O
pacote fica pronto para um instalador/helper aplicar no próximo ciclo.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path
from typing import Callable

from core.paths import APP_DIR, STATE_DIR, ensure_state_dirs

UPDATE_DIR = STATE_DIR / "updates"
DOWNLOAD_DIR = UPDATE_DIR / "downloads"
DEFAULT_UPDATE_MANIFEST_URL = (
    "https://raw.githubusercontent.com/andre2050/torvis-assistente/main/update.json"
)
# O update.json do branch é um arquivo como outro qualquer: fica velho quando
# alguém publica uma release e esquece de mexer nele. O asset do release é
# escrito no mesmo passo da publicação, então ele é o retrato da versão atual.
# As duas fontes são consultadas e vence a maior versão.
MIRROR_MANIFEST_URLS = (
    "https://github.com/andre2050/torvis-assistente/releases/latest/download/update.json",
)
USER_AGENT = "TORVIS-Update/5.6.1"
MAX_REMOTE_MANIFEST = 256 * 1024
MAX_UPDATE_ZIP = 1024 * 1024 * 1024  # 1 GiB
MAX_EXTRACTED_BYTES = 2 * 1024 * 1024 * 1024
MAX_EXTRACTED_FILES = 20000

ProgressCallback = Callable[[str, str], None]


def _emit(progress: ProgressCallback | None, stage: str, detail: str) -> None:
    if progress:
        try:
            progress(stage, detail)
        except Exception:
            pass


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _is_hex_sha256(value: object) -> bool:
    text = str(value or "").strip().lower()
    return len(text) == 64 and all(c in "0123456789abcdef" for c in text)


def _version_tuple(value: object) -> tuple[int, ...]:
    """SemVer-like comparison without adding another dependency.

    Pre-release suffixes are ignored for ordering because stable T.O.R.V.I.S
    builds currently use only numeric versions (5.6.1, 5.7.0, ...).
    """
    raw = str(value or "").strip().lower().lstrip("v")
    core = raw.split("-", 1)[0].split("+", 1)[0]
    if not core:
        raise ValueError("versão vazia")
    parts: list[int] = []
    for item in core.split("."):
        if not item.isdigit():
            raise ValueError(f"versão inválida: {value}")
        parts.append(int(item))
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts)


def is_newer_version(remote: object, current: object) -> bool:
    return _version_tuple(remote) > _version_tuple(current)


def get_update_manifest_url() -> str:
    """Resolve a fonte oficial, permitindo override administrativo/local.

    Ordem: variável de ambiente -> configuração persistida -> GitHub oficial.
    """
    env = str(os.getenv("TORVIS_UPDATE_MANIFEST_URL") or "").strip()
    if env:
        return env
    try:
        from memory.config_manager import load_api_keys

        cfg = load_api_keys()
        custom = str(cfg.get("update_manifest_url") or "").strip()
        if custom:
            return custom
    except Exception:
        pass
    return DEFAULT_UPDATE_MANIFEST_URL


def _validate_remote_url(url: str, *, allow_file: bool = True) -> str:
    parsed = urllib.parse.urlparse(str(url or "").strip())
    if parsed.scheme == "https" and parsed.netloc:
        return parsed.geturl()
    if allow_file and parsed.scheme == "file":
        return parsed.geturl()
    raise ValueError("a fonte de atualização precisa usar HTTPS")


def _open_url(url: str, timeout: float, *, cache_bust: bool = False):
    """Abre a URL com cabeçalhos que não aceitam cópia velha.

    O raw.githubusercontent.com serve update.json com cache de alguns minutos.
    Sem isso, clicar em ATUALIZAR SISTEMA logo depois de uma publicação
    respondia "já está atualizado" com o manifesto anterior — a versão existia e
    o app dizia que não.

    O parâmetro extra só vale para o manifesto: numa URL de download assinada
    (o ZIP do release) mexer na query quebra a assinatura.
    """
    alvo = url
    if cache_bust and url.startswith("http"):
        separador = "&" if "?" in url else "?"
        alvo = f"{url}{separador}_={int(time.time() * 1000)}"
    req = urllib.request.Request(alvo, headers={
        "User-Agent": USER_AGENT,
        "Cache-Control": "no-cache, no-store, max-age=0",
        "Pragma": "no-cache",
    })
    return urllib.request.urlopen(req, timeout=timeout)


def _manifesto_de(url: str, timeout: float) -> dict:
    """Lê e valida um manifesto de uma única fonte."""
    url = _validate_remote_url(url)
    try:
        with _open_url(url, timeout, cache_bust=True) as response:
            raw = response.read(MAX_REMOTE_MANIFEST + 1)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            raise RuntimeError(
                "o repositório oficial está configurado, mas update.json ainda não foi publicado"
            ) from exc
        raise RuntimeError(f"servidor de atualização respondeu HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"não foi possível acessar a fonte de atualização: {exc.reason}") from exc
    except OSError as exc:
        raise RuntimeError(f"não foi possível ler a fonte de atualização: {exc}") from exc

    if len(raw) > MAX_REMOTE_MANIFEST:
        raise ValueError("manifesto remoto grande demais")
    try:
        manifest = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("manifesto remoto inválido") from exc
    if not isinstance(manifest, dict):
        raise ValueError("manifesto remoto inválido")

    version = str(manifest.get("version") or "").strip()
    if not version:
        raise ValueError("manifesto remoto sem version")
    _version_tuple(version)

    package_url = str(manifest.get("package_url") or manifest.get("package") or "").strip()
    if not package_url:
        raise ValueError("manifesto remoto sem package_url")
    package_url = urllib.parse.urljoin(url, package_url)
    manifest["package_url"] = _validate_remote_url(package_url)

    sha = str(manifest.get("sha256") or "").strip().lower()
    if not _is_hex_sha256(sha):
        raise ValueError("manifesto remoto sem SHA-256 válido")
    manifest["sha256"] = sha
    manifest["manifest_url"] = url
    manifest.setdefault("channel", "stable")
    return manifest


def fetch_remote_manifest(url: str | None = None, timeout: float = 8.0) -> dict:
    """Consulta todas as fontes e devolve a de MAIOR versão.

    Uma fonte que falha não derruba a checagem: se o release responder e o
    branch estiver velho, vale o release. Sem nenhuma resposta, o erro da
    fonte principal sobe — o usuário precisa saber que a checagem falhou.
    """
    principal = _validate_remote_url(url or get_update_manifest_url())
    fontes = [principal] + [u for u in MIRROR_MANIFEST_URLS if u != principal]
    lidos: list[dict] = []
    erro_principal: Exception | None = None
    for fonte in fontes:
        try:
            lidos.append(_manifesto_de(fonte, timeout))
        except Exception as exc:
            if fonte == principal:
                erro_principal = exc
            continue
    if not lidos:
        if erro_principal:
            raise erro_principal
        raise RuntimeError("nenhuma fonte de atualização respondeu")
    lidos.sort(key=lambda m: _version_tuple(str(m.get("version"))), reverse=True)
    return lidos[0]
    if not package_url:
        raise ValueError("manifesto remoto sem package_url")
    package_url = urllib.parse.urljoin(url, package_url)
    manifest["package_url"] = _validate_remote_url(package_url)

    sha = str(manifest.get("sha256") or "").strip().lower()
    if not _is_hex_sha256(sha):
        raise ValueError("manifesto remoto sem SHA-256 válido")
    manifest["sha256"] = sha
    manifest["manifest_url"] = url
    manifest.setdefault("channel", "stable")
    return manifest


def check_for_update(
    *,
    current_version: str | None = None,
    manifest_url: str | None = None,
    timeout: float = 8.0,
) -> dict:
    if current_version is None:
        from core.version import VERSAO

        current_version = VERSAO
    source = manifest_url or get_update_manifest_url()
    manifest = fetch_remote_manifest(source, timeout=timeout)
    remote_version = str(manifest["version"])
    return {
        "configured": True,
        "current_version": str(current_version),
        "remote_version": remote_version,
        "update_available": is_newer_version(remote_version, current_version),
        "manifest_url": manifest["manifest_url"],
        "package_url": manifest["package_url"],
        "channel": manifest.get("channel", "stable"),
        "release_notes": manifest.get("release_notes") or manifest.get("notes") or "",
        "manifest": manifest,
    }


def download_update(
    manifest: dict,
    *,
    timeout: float = 20.0,
    progress: ProgressCallback | None = None,
) -> Path:
    ensure_state_dirs()
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

    version = str(manifest.get("version") or "").strip()
    url = _validate_remote_url(str(manifest.get("package_url") or ""))
    expected = str(manifest.get("sha256") or "").strip().lower()
    if not version or not _is_hex_sha256(expected):
        raise ValueError("manifesto de download inválido")

    parsed = urllib.parse.urlparse(url)
    name = Path(urllib.parse.unquote(parsed.path)).name or f"TORVIS-{version}.zip"
    if not name.lower().endswith(".zip"):
        name = f"TORVIS-{version}.zip"
    dest = DOWNLOAD_DIR / name
    tmp = dest.with_suffix(dest.suffix + ".part")
    tmp.unlink(missing_ok=True)

    _emit(progress, "download", f"Baixando T.O.R.V.I.S {version}...")
    h = hashlib.sha256()
    total = 0
    last_pct = -1
    try:
        with _open_url(url, timeout) as response, tmp.open("wb") as out:
            try:
                content_length = int(response.headers.get("Content-Length") or 0)
            except Exception:
                content_length = 0
            if content_length > MAX_UPDATE_ZIP:
                raise ValueError("pacote remoto excede o limite de segurança")
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_UPDATE_ZIP:
                    raise ValueError("pacote remoto excede o limite de segurança")
                out.write(chunk)
                h.update(chunk)
                if content_length:
                    pct = min(100, int(total * 100 / content_length))
                    if pct // 10 != last_pct // 10:
                        last_pct = pct
                        _emit(progress, "download", f"Download {pct}%")
    except Exception:
        tmp.unlink(missing_ok=True)
        raise

    actual = h.hexdigest()
    if actual.lower() != expected:
        tmp.unlink(missing_ok=True)
        raise ValueError("SHA-256 do pacote remoto não confere")
    tmp.replace(dest)
    _emit(progress, "verify", "SHA-256 do ZIP validado.")
    return dest


def _safe_extract_zip(archive: Path, destination: Path) -> None:
    destination = Path(destination).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    count = 0
    total = 0
    with zipfile.ZipFile(archive, "r") as zf:
        for info in zf.infolist():
            count += 1
            total += int(info.file_size or 0)
            if count > MAX_EXTRACTED_FILES or total > MAX_EXTRACTED_BYTES:
                raise ValueError("pacote de atualização excede os limites de extração")

            # Unix symlink bit in external attributes.
            mode = (info.external_attr >> 16) & 0xFFFF
            if (mode & 0o170000) == 0o120000:
                raise ValueError(f"link simbólico não permitido no pacote: {info.filename}")

            target = (destination / info.filename).resolve()
            if target != destination and destination not in target.parents:
                raise ValueError(f"caminho inseguro no ZIP: {info.filename}")
        zf.extractall(destination)


def _locate_update_root(extracted: Path) -> Path:
    direct = extracted / "update-manifest.json"
    if direct.is_file():
        return extracted
    candidates = [p.parent for p in extracted.rglob("update-manifest.json") if p.is_file()]
    if len(candidates) != 1:
        raise ValueError("o pacote precisa conter exatamente um update-manifest.json")
    return candidates[0]


def verify_package(source: Path) -> dict:
    source = Path(source)
    manifest_path = source / "update-manifest.json"
    if not manifest_path.is_file():
        raise ValueError("update-manifest.json is missing")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    files = manifest.get("files") or {}
    if not manifest.get("version") or not isinstance(files, dict):
        raise ValueError("invalid update manifest")
    _version_tuple(manifest["version"])
    source_resolved = source.resolve()
    expected_files = {str(rel).replace("\\", "/") for rel in files}
    actual_files = {
        p.relative_to(source).as_posix()
        for p in source.rglob("*")
        if p.is_file() and p.name != "update-manifest.json"
    }
    extra = sorted(actual_files - expected_files)
    missing = sorted(expected_files - actual_files)
    if extra:
        raise ValueError(f"unlisted update file: {extra[0]}")
    if missing:
        # Diagnóstico melhor: se o nome existe com outra caixa, o problema não é
        # arquivo faltando — é o pacote ter dois nomes que o Windows trata como um.
        por_minusculo = {nome.lower(): nome for nome in actual_files}
        for rel in missing:
            gemeo = por_minusculo.get(rel.lower())
            if gemeo and gemeo != rel:
                raise ValueError(
                    f"case-collision in package: '{rel}' and '{gemeo}' are the same file "
                    "on Windows")
        raise ValueError(f"missing update file: {missing[0]}")

    for rel, expected in files.items():
        p = (source / rel).resolve()
        if source_resolved not in p.parents or not p.is_file():
            raise ValueError(f"invalid update file: {rel}")
        if not _is_hex_sha256(expected):
            raise ValueError(f"invalid hash: {rel}")
        if _sha256(p).lower() != str(expected).lower():
            raise ValueError(f"hash mismatch: {rel}")
    return manifest


def stage_update(
    source: Path,
    *,
    backup_path: Path | None = None,
    metadata: dict | None = None,
) -> Path:
    ensure_state_dirs()
    UPDATE_DIR.mkdir(parents=True, exist_ok=True)
    manifest = verify_package(source)
    dest = UPDATE_DIR / f"staged-{manifest['version']}"
    tmp = UPDATE_DIR / (dest.name + ".tmp")
    shutil.rmtree(tmp, ignore_errors=True)
    shutil.copytree(source, tmp)
    shutil.rmtree(dest, ignore_errors=True)
    tmp.replace(dest)

    pending = {
        "version": manifest["version"],
        "path": str(dest),
        "staged_at": time.time(),
        "backup_path": str(backup_path) if backup_path else "",
    }
    if metadata:
        pending["metadata"] = dict(metadata)
    (UPDATE_DIR / "pending.json").write_text(
        json.dumps(pending, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return dest


def read_pending_update() -> dict | None:
    path = UPDATE_DIR / "pending.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def cancel_pending_update(*, restore_backup: bool = False) -> bool:
    pending = read_pending_update()
    if not pending:
        return False
    if restore_backup and pending.get("backup_path"):
        from core.recovery import restore_backup as _restore

        _restore(Path(str(pending["backup_path"])))
    try:
        shutil.rmtree(Path(str(pending.get("path") or "")), ignore_errors=True)
    except Exception:
        pass
    try:
        (UPDATE_DIR / "pending.json").unlink(missing_ok=True)
    except Exception:
        pass
    return True


# Arquivos que pertencem ao usuário, não ao pacote: mesmo que venham no zip, não
# são sobrescritos. A configuração e a memória vivem fora da pasta do app, mas
# instalações antigas guardavam tudo junto — por isso a proteção existe.
PROTEGIDOS = (
    "config/api_keys.json",
    "memory/long_term.json",
    "memory/cognitive_memory.json",
    ".env",
)


def _protegido(rel: str) -> bool:
    rel = rel.replace("\\", "/")
    return rel in PROTEGIDOS or rel.startswith("memory/") or rel.endswith("/.env")


def apply_pending_update(
    *,
    app_dir: Path | None = None,
    progress: ProgressCallback | None = None,
) -> dict:
    """Aplica o pacote preparado na pasta do app, com rollback em caso de falha.

    Por que existe: `stage_update` deixava tudo validado, mas nada trocava os
    arquivos — a atualização ficava eternamente "preparada". Aqui a troca é feita
    arquivo por arquivo, cada um numa operação atômica (escreve `.novo` e
    substitui). Se qualquer passo falhar, os arquivos já trocados voltam do
    snapshot feito antes de começar, então o app nunca fica pela metade.
    """
    pending = read_pending_update()
    if not pending:
        raise ValueError("nenhuma atualização preparada")
    staged = Path(str(pending.get("path") or ""))
    if not staged.is_dir():
        raise ValueError(f"pacote preparado não encontrado em {staged}")

    manifest = verify_package(staged)          # revalida antes de tocar em nada
    versao_nova = str(manifest.get("version") or "")
    destino = Path(app_dir).resolve() if app_dir else APP_DIR.resolve()
    if not destino.is_dir():
        raise ValueError(f"pasta do aplicativo não encontrada: {destino}")

    _emit(progress, "apply", f"Aplicando {versao_nova} em {destino}...")

    arquivos = [rel for rel in manifest.get("files", {}) if not _protegido(rel)]
    pulados = [rel for rel in manifest.get("files", {}) if _protegido(rel)]

    with tempfile.TemporaryDirectory(prefix="torvis-rollback-") as temp:
        rollback = Path(temp)
        trocados: list[str] = []
        try:
            for rel in arquivos:
                origem = staged / rel
                alvo = destino / rel
                anterior = rollback / rel
                if alvo.is_file():                 # guarda a versão atual
                    anterior.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(alvo, anterior)
                alvo.parent.mkdir(parents=True, exist_ok=True)
                temporario = alvo.with_name(alvo.name + ".novo")
                shutil.copy2(origem, temporario)
                temporario.replace(alvo)           # troca atômica por arquivo
                trocados.append(rel)

            manifesto_origem = staged / "update-manifest.json"
            if manifesto_origem.is_file():
                shutil.copy2(manifesto_origem, destino / "update-manifest.json")

        except Exception as exc:                   # noqa: BLE001 — devolver tudo que mexeu
            for rel in reversed(trocados):
                anterior = rollback / rel
                alvo = destino / rel
                try:
                    if anterior.is_file():
                        shutil.copy2(anterior, alvo)
                    else:
                        alvo.unlink(missing_ok=True)
                except OSError:
                    pass
            _emit(progress, "rollback", f"Falha ao aplicar; nada foi alterado: {exc}")
            raise

    _emit(progress, "applied", f"{len(arquivos)} arquivos atualizados.")
    resultado = {
        "version": versao_nova,
        "applied_files": len(arquivos),
        "skipped_files": pulados,
        "app_dir": str(destino),
        "backup_path": str(pending.get("backup_path") or ""),
        "applied_at": time.time(),
    }
    try:
        (UPDATE_DIR / "applied.json").write_text(
            json.dumps(resultado, indent=2, ensure_ascii=False), encoding="utf-8")
        (UPDATE_DIR / "pending.json").unlink(missing_ok=True)
        shutil.rmtree(staged, ignore_errors=True)   # libera espaco do pacote
    except OSError:
        pass
    return resultado


def installed_version(app_dir: Path | None = None) -> str:
    """Lê a versão direto de core/version.py na pasta do app."""
    destino = Path(app_dir).resolve() if app_dir else APP_DIR.resolve()
    arquivo = destino / "core" / "version.py"
    try:
        for linha in arquivo.read_text(encoding="utf-8").splitlines():
            if linha.startswith("VERSAO"):
                return linha.split("=", 1)[1].strip().strip('"\'')
    except OSError:
        pass
    return "desconhecida"


def prepare_remote_update(
    *,
    current_version: str | None = None,
    manifest_url: str | None = None,
    timeout: float = 20.0,
    progress: ProgressCallback | None = None,
) -> dict:
    """Check, download, validate, back up and stage a remote update."""
    _emit(progress, "check", "Consultando a fonte oficial de atualizações...")
    check = check_for_update(
        current_version=current_version,
        manifest_url=manifest_url,
        timeout=min(timeout, 10.0),
    )
    if not check["update_available"]:
        _emit(progress, "done", "O sistema já está atualizado.")
        return {**check, "prepared": False, "reason": "up_to_date"}

    manifest = check["manifest"]
    archive = download_update(manifest, timeout=timeout, progress=progress)

    ensure_state_dirs()
    unpack_parent = UPDATE_DIR / "unpack"
    unpack_parent.mkdir(parents=True, exist_ok=True)
    tmp_dir = Path(tempfile.mkdtemp(prefix="torvis-update-", dir=str(unpack_parent)))
    try:
        _emit(progress, "extract", "Extraindo pacote em área temporária...")
        _safe_extract_zip(archive, tmp_dir)
        root = _locate_update_root(tmp_dir)
        internal = verify_package(root)
        if str(internal.get("version")) != str(manifest.get("version")):
            raise ValueError("a versão do pacote interno difere do manifesto remoto")

        _emit(progress, "backup", "Criando backup dos dados do usuário...")
        from core.recovery import create_backup

        backup = create_backup()
        _emit(progress, "stage", "Preparando a atualização validada...")
        staged = stage_update(
            root,
            backup_path=backup,
            metadata={
                "manifest_url": check["manifest_url"],
                "package_url": check["package_url"],
                "package_sha256": manifest["sha256"],
                "archive": str(archive),
                "release_notes": check.get("release_notes") or "",
            },
        )
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    _emit(progress, "done", f"T.O.R.V.I.S {check['remote_version']} preparado com segurança.")
    return {
        **check,
        "prepared": True,
        "reason": "prepared",
        "archive": str(archive),
        "staged_path": str(staged),
        "backup_path": str(backup),
    }
