from pathlib import Path


def test_version_562_or_newer():
    from core.version import VERSAO
    assert tuple(map(int, VERSAO.split("."))) >= (5, 6, 2)


def test_customise_and_audio_import_names_are_valid():
    text = Path("gui/overlays.py").read_text(encoding="utf-8")
    assert "PADRÃO_VOICE" not in text
    assert "PADRÃO_LABEL" not in text
    assert "DEFAULT_VOICE" in text
    assert "DEFAULT_LABEL" in text


def test_quick_controls_are_wired_in_bottom_dock():
    text = Path("gui/window.py").read_text(encoding="utf-8")
    assert "def _build_bottom_action_bar" in text
    start = text.index("def _build_bottom_action_bar")
    end = text.index("def _build_quick_drawer", start)
    dock = text[start:end]
    for label in (
        "Microfone", "Sempre ouvindo", "WhatsApp",
        "Controle remoto", "COWORK", "Criar / desenvolver", "Computer Use",
        "Segundo plano", "F9",
    ):
        assert label in dock

    controls_start = text.index("def _build_controls_drawer")
    controls_end = text.index("def _warm_wake_state", controls_start)
    controls = text[controls_start:controls_end]
    for moved_label in ("CONECTAR WHATSAPP", "CONTROLE REMOTO", "COWORK SEM PASTA"):
        assert moved_label not in controls

    for method in (
        "_toggle_always_listening", "_connect_whatsapp", "_open_remote",
        "_start_cowork_no_folder", "_toggle_computer_use",
        "_toggle_background_mode", "_start_background_hotkey",
    ):
        assert f"def {method}" in text


def test_computer_use_gate_is_in_action_registry(monkeypatch):
    import memory.config_manager as cfg
    from core.action_loader import ActionRecord, ActionRegistry
    monkeypatch.setattr(cfg, "get_computer_use_enabled", lambda: False)
    called = []
    def handler(parameters, **kwargs):
        called.append(True)
        return "ran"
    reg = ActionRegistry({
        "computer_control": ActionRecord(
            name="computer_control", description="x",
            parameters={"type":"OBJECT","properties":{}},
            handler=handler, file="x.py", valid=True,
        )
    }, lambda *_: None)
    result = reg.run("computer_control", {})
    assert "Computer Use" in result
    assert not called


def test_mutable_task_and_routine_state_use_state_dir():
    tasks = Path("core/tasks/desktop.py").read_text(encoding="utf-8")
    routines = Path("core/routines/desktop.py").read_text(encoding="utf-8")
    control = Path("actions/computer_control.py").read_text(encoding="utf-8")
    assert 'return STATE_DIR / "tasks"' in tasks
    assert 'return STATE_DIR / "reports"' in tasks
    assert 'return STATE_DIR / "routines.json"' in routines
    assert "_MEMORY_PATH  = MEMORY_FILE" in control


def test_windows_build_uses_full_suite_and_official_spec():
    ps1 = Path("build_windows.ps1").read_text(encoding="utf-8")
    bat = Path("CRIAR-EXECUTAVEL.bat").read_text(encoding="utf-8")
    spec = Path("packaging/assistente_inteligente.spec").read_text(encoding="utf-8")
    assert "-m pytest -q" in ps1
    assert "packaging\\assistente_inteligente.spec" in bat
    for pkg in ("actions", "providers", "plugins"):
        assert pkg in spec
    for asset in ("core/prompt.txt", "agents", "dashboard/static"):
        assert asset in spec


def test_conversation_panel_is_portuguese_and_has_clear_button():
    text = Path("gui/window.py").read_text(encoding="utf-8")
    assert 'HoloPanel("CONVERSA", "LOG")' in text
    assert 'QPushButton("LIMPAR CONVERSA")' in text
    assert 'clicked.connect(self._clear_conversation)' in text
    assert 'HoloPanel("COMMUNICATIONS", "LOG")' not in text


def test_clear_conversation_resets_ui_and_live_context():
    window = Path("gui/window.py").read_text(encoding="utf-8")
    widgets = Path("gui/widgets.py").read_text(encoding="utf-8")
    main = Path("main.py").read_text(encoding="utf-8")
    assert "def clear_conversation(self)" in widgets
    assert "self._queue.clear()" in widgets
    assert "self._log.clear_conversation()" in window
    assert "self.on_clear_conversation()" in window
    assert "self.ui.on_clear_conversation = self._clear_conversation" in main
    assert "self._session_log.clear()" in main
    assert "self._resume_handle = None" in main
    assert 'request_reconnect(keep_context=False, reason="conversation cleared")' in main
