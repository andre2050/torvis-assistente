"""Runtime paths for source and packaged builds.

Code/assets remain beside the application. Mutable user state lives in a
per-user writable directory so installed builds never need administrator rights.
"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

APP_NAME = "Assistente Inteligente"


def app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def state_dir() -> Path:
    override = os.getenv("ASSISTENTE_INTELIGENTE_STATE_DIR") or os.getenv("MARK_LVII_STATE_DIR")
    if override:
        return Path(override).expanduser().resolve()
    if sys.platform == "win32":
        root = Path(os.getenv("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    elif sys.platform == "darwin":
        root = Path.home() / "Library" / "Application Support"
    else:
        root = Path(os.getenv("XDG_STATE_HOME", Path.home() / ".local" / "state"))
    return root / APP_NAME


APP_DIR = app_dir()
STATE_DIR = state_dir()
CONFIG_DIR = STATE_DIR / "config"
MEMORY_DIR = STATE_DIR / "memory"
CACHE_DIR = STATE_DIR / "cache"
LOG_DIR = STATE_DIR / "logs"
SESSION_DIR = STATE_DIR / "sessions"
BACKUP_DIR = STATE_DIR / "backups"
CONFIG_FILE = CONFIG_DIR / "api_keys.json"
MEMORY_FILE = MEMORY_DIR / "long_term.json"
COGNITIVE_MEMORY_FILE = MEMORY_DIR / "cognitive_memory.json"


def ensure_state_dirs() -> None:
    for path in (CONFIG_DIR, MEMORY_DIR, CACHE_DIR, LOG_DIR, SESSION_DIR, BACKUP_DIR):
        path.mkdir(parents=True, exist_ok=True)


def migrate_legacy_state() -> list[tuple[Path, Path]]:
    """Copy legacy mutable files once; originals are deliberately preserved."""
    ensure_state_dirs()
    migrated: list[tuple[Path, Path]] = []
    pairs = (
        (APP_DIR / "config" / "api_keys.json", CONFIG_FILE),
        (APP_DIR / "memory" / "long_term.json", MEMORY_FILE),
    )
    for source, target in pairs:
        try:
            if source.exists() and not target.exists() and source.resolve() != target.resolve():
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
                migrated.append((source, target))
        except OSError:
            pass
    return migrated
