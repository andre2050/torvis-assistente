# Assistente Inteligente — Development status

Current modernization pass: stages 1–10 foundation completed.

## Implemented
- Per-user writable state (`%LOCALAPPDATA%\\Assistente Inteligente` on Windows), legacy migration and atomic configuration.
- Assistente Inteligente identity and Andre Luiz Lima Menezes project-modification attribution; upstream third-party license attribution retained.
- Runtime diagnostics and smoke/foundation tests.
- Background task engine safeguards: checkpointing, budgets, duplicate-action cache and repeated-call loop guard.
- Transactional backup/restore metadata.
- Update package verification (SHA-256) and transactional staging; network fetching/application intentionally separate.
- PyInstaller Windows build plus optional per-user Inno Setup installer; no administrator privilege required by default.
- Optional desktop shortcut and optional Windows startup entry.

## Still requires real Windows validation
The CI/container used for this pass is not a Windows desktop and cannot prove microphone, speakers, SAPI/COM, pywinauto, global hotkeys, camera, browser automation or the final packaged executable on a real Windows machine. Run `build_windows.ps1` on Windows, then execute the diagnostic/smoke flow and feature tests on that build before calling it production-ready.

## Next product-level work
The remaining work is iterative product quality rather than missing foundation: split more of the large UI/live-session coordinator out of `main.py`, add mocks/integration tests for hardware/provider paths, profile startup/RAM on Windows, and polish HUD/voice UX from real-device feedback.
