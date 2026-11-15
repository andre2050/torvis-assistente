# Assistente Inteligente — hardening plan (1–10)

## Implemented foundation
- Per-user writable runtime state (`core/paths.py`) with legacy migration.
- Central config path adopted by the main configuration manager and key core/actions.
- Runtime diagnostics (`python -m core.diagnostics`).
- Backup/restore primitives (`core/recovery.py`).
- Dependency-light smoke test (`python tests/smoke.py`).
- Windows PyInstaller baseline (`build_windows.ps1`, `packaging/assistente_inteligente.spec`).

## Remaining staged work
1. Security/data: migrate every remaining direct config writer to config_manager; add Windows credential protection for secrets.
2. Architecture: split main.py lifecycle/audio/session/tool registration into services.
3. Startup: bootstrap + friendly dependency/recovery screen.
4. Tests: unit tests for config/memory/actions plus mocked provider integration tests and CI.
5. AI/orchestration: explicit intent/tool router, provider health/fallback policy, bounded retries/timeouts.
6. Performance: measure startup/imports; lazy-load GUI/vision/browser/provider extras.
7. Autonomy: task state machine with preconditions, confirmation policy, result verification, retry/rollback.
8. UI/voice: connect diagnostics/task progress/recovery to HUD; isolate audio lifecycle.
9. Windows distribution: signed per-user installer, shortcuts/startup opt-in, clean-machine verification.
10. Updates/recovery: signed update manifest, staged update, automatic backup, health check and rollback.
