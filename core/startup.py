"""Lightweight startup preparation before optional GUI/audio imports."""
from __future__ import annotations
from core.paths import ensure_state_dirs, migrate_legacy_state

def prepare_runtime() -> dict:
    ensure_state_dirs()
    migrated=migrate_legacy_state()
    return {'migrated': [(str(a),str(b)) for a,b in migrated]}
