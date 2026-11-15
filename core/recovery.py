"""Backup/restore transacional dos dados mutáveis do T.O.R.V.I.S 2026."""
from __future__ import annotations

import json
import shutil
import time
from pathlib import Path

from core.paths import BACKUP_DIR, CONFIG_DIR, MEMORY_DIR, ensure_state_dirs


def create_backup() -> Path:
    """Copia configurações e memórias para um snapshot independente da instalação."""
    ensure_state_dirs()
    dest = BACKUP_DIR / time.strftime("%Y%m%d-%H%M%S")
    suffix = 0
    base = dest
    while dest.exists():
        suffix += 1
        dest = Path(str(base) + f"-{suffix}")
    dest.mkdir(parents=True, exist_ok=False)

    copied: list[str] = []
    for name, source in (("config", CONFIG_DIR), ("memory", MEMORY_DIR)):
        if source.exists():
            target = dest / name
            shutil.copytree(source, target)
            copied.append(name)
    (dest / "backup.json").write_text(
        json.dumps(
            {"created_at": time.time(), "directories": copied, "format": 2},
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return dest


def _replace_dir(source: Path, target: Path) -> None:
    if not source.exists():
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(target.name + ".restore")
    shutil.rmtree(tmp, ignore_errors=True)
    shutil.copytree(source, tmp)
    shutil.rmtree(target, ignore_errors=True)
    tmp.replace(target)


def restore_backup(source: Path) -> None:
    source = Path(source)
    if not source.is_dir():
        raise ValueError("backup directory does not exist")

    # v2: diretórios inteiros. Mantém compatibilidade com snapshots v1.
    if (source / "config").is_dir() or (source / "memory").is_dir():
        _replace_dir(source / "config", CONFIG_DIR)
        _replace_dir(source / "memory", MEMORY_DIR)
        return

    from core.paths import CONFIG_FILE, MEMORY_FILE

    mapping = {"api_keys.json": CONFIG_FILE, "long_term.json": MEMORY_FILE}
    for name, target in mapping.items():
        item = source / name
        if item.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            tmp = target.with_suffix(target.suffix + ".restore")
            shutil.copy2(item, tmp)
            tmp.replace(target)
